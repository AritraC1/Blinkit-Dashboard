"""Dashboard views.

`overview` and `predictions` render the full page shells. Each widget is a
small partial view so HTMX can refresh it on its own. All overview views read
the filters through the same helper (`_filters`), which delegates to selectors.
Prediction views go through apps.ml.predict, which owns validation and logging.
"""

from __future__ import annotations

from django.db.models import Count
from django.shortcuts import render

from apps.core.models import Item, LocationTier, Outlet, OutletType
from apps.ml import predict, registry
from apps.ml.models import PredictionLog

from . import selectors
from .forms import FilterForm, PredictionForm


def _filters(request) -> dict:
    """One helper every view reads filters through."""
    return selectors.filters_from_params(request.GET)


def _records(request):
    """SalesRecord queryset with the request's filters applied."""
    return selectors.base_queryset(_filters(request))


def _recent_predictions(n: int = 10):
    """The last n PredictionLog rows, newest first."""
    return list(PredictionLog.objects.select_related("model_run")[:n])


def overview(request):
    """Full page on normal requests; only the dashboard area for HTMX ones
    (used by the filter form, which targets #dashboard-area)."""
    context = {
        "filter_form": FilterForm(request.GET or None),
        "filters": _filters(request),
    }
    if request.headers.get("HX-Request"):
        return render(request, "dashboard/_dashboard_area.html", context)
    return render(request, "dashboard/overview.html", context)


def predictions(request):
    """Page 2 shell: model card on top, charts in the middle, form + result at
    the bottom. Without a trained model every widget shows the empty state."""
    run = registry.get_active_run()
    return render(
        request,
        "dashboard/predictions.html",
        {"has_model": run is not None, "run": run},
    )


def _empty_state(request):
    """The "no model yet" message any ML partial falls back to."""
    return render(request, "dashboard/partials/_empty_state.html")


def model_metrics(request):
    run = registry.get_active_run()
    if run is None:
        return _empty_state(request)
    return render(
        request,
        "dashboard/partials/_model_metrics.html",
        {
            "run": run,
            "baseline": {
                key: run.baseline_metrics.get(key)
                for key in ("r2", "mae", "rmse")
            },
        },
    )


def feature_importance(request):
    run = registry.get_active_run()
    if run is None:
        return _empty_state(request)
    importances = (run.evaluation or {}).get("feature_importances") or []
    return render(
        request,
        "dashboard/partials/_feature_importance.html",
        {
            "rows": [
                {"label": entry["feature"], "value": entry["importance"]}
                for entry in importances
            ]
        },
    )


def chart_actual_vs_predicted(request):
    run = registry.get_active_run()
    if run is None:
        return _empty_state(request)
    points = (run.evaluation or {}).get("actual_vs_predicted") or []
    return render(
        request,
        "dashboard/partials/_chart_actual_vs_predicted.html",
        {"points": points},
    )


def _profile_options(profile: dict) -> dict:
    """Select options for the item-type profile form: every DB value, with the
    currently chosen one flagged."""
    return {
        "outlet_type": [
            {"value": value, "selected": value == profile["outlet_type"]}
            for value in sorted(set(Outlet.objects.values_list("outlet_type", flat=True)))
        ],
        "location_tier": [
            {"value": value, "selected": value == profile["location_tier"]}
            for value in sorted(set(Outlet.objects.values_list("location_tier", flat=True)))
        ],
        "establishment_year": [
            {"value": value, "selected": value == profile["establishment_year"]}
            for value in sorted(
                set(Outlet.objects.values_list("establishment_year", flat=True))
            )
        ],
    }


def _default_profile() -> dict:
    """The busiest outlet in the database, as the default what-if profile."""
    outlet = (
        Outlet.objects.annotate(record_count=Count("sales_records"))
        .order_by("-record_count", "outlet_id")
        .first()
    )
    if outlet is None:
        return {
            "outlet_type": OutletType.SUPERMARKET_TYPE1,
            "location_tier": LocationTier.TIER_1,
            "establishment_year": int(sum(predict.YEAR_RANGE) / 2),
        }
    return {
        "outlet_type": outlet.outlet_type,
        "location_tier": outlet.location_tier,
        "establishment_year": outlet.establishment_year,
    }


def _profile_from_params(params) -> dict:
    """The outlet profile for the item-type predictions: GET params where they
    validate, the busiest outlet's profile for anything missing or invalid."""
    default = _default_profile()
    params = params or {}
    try:
        return predict.validate_profile(
            params.get("outlet_type") or default["outlet_type"],
            params.get("location_tier") or default["location_tier"],
            params.get("establishment_year") or default["establishment_year"],
        )
    except predict.InvalidInputError:
        return default


def item_type_predictions(request):
    run = registry.get_active_run()
    if run is None:
        return _empty_state(request)

    profile = _profile_from_params(request.GET)
    error = None
    try:
        rows = predict.predict_by_item_type(**profile)
    except predict.PredictionError as exc:
        rows, error = [], str(exc)
    return render(
        request,
        "dashboard/partials/_item_type_predictions.html",
        {
            "rows": rows,
            "error": error,
            "profile": profile,
            "options": _profile_options(profile),
        },
    )


def predict_form(request):
    run = registry.get_active_run()
    if run is None:
        return _empty_state(request)
    return render(
        request,
        "dashboard/partials/_predict_form.html",
        {"form": PredictionForm()},
    )


def run_prediction(request):
    """POST target for the what-if form.

    Success renders the result partial (plus an out-of-band refresh of the
    recent-predictions widget). Errors re-render the errored form with
    messages and return 200, because HTMX does not swap 4xx responses by
    default; the form itself swaps back into the form box out-of-band.
    """
    form = PredictionForm(request.POST or None)
    if request.method != "POST":
        return render(
            request,
            "dashboard/partials/_predict_form.html",
            {"form": form},
        )
    if not form.is_valid():
        return render(
            request,
            "dashboard/partials/_predict_form_error.html",
            {"form": form},
        )

    try:
        result = predict.predict_sales(**form.cleaned_data)
    except predict.PredictionError as exc:
        form.add_error(None, str(exc))
        return render(
            request,
            "dashboard/partials/_predict_form_error.html",
            {"form": form},
        )

    return render(
        request,
        "dashboard/partials/_predict_result.html",
        {"result": result, "logs": _recent_predictions()},
    )


def recent_predictions(request):
    return render(
        request,
        "dashboard/partials/_recent_predictions.html",
        {"logs": _recent_predictions()},
    )


def kpi_cards(request):
    return render(
        request,
        "dashboard/partials/_kpi_cards.html",
        {"kpis": selectors.kpi_summary(_records(request))},
    )


def chart_item_type(request):
    return render(
        request,
        "dashboard/partials/_chart_item_type.html",
        {"rows": selectors.sales_by_item_type(_records(request))},
    )


def chart_outlet(request):
    return render(
        request,
        "dashboard/partials/_chart_outlet.html",
        {"rows": selectors.sales_by_outlet_type(_records(request))},
    )


def chart_tier_size(request):
    return render(
        request,
        "dashboard/partials/_chart_tier_size.html",
        {"rows": selectors.sales_by_tier_size(_records(request))},
    )


def chart_fat_content(request):
    return render(
        request,
        "dashboard/partials/_chart_fat_content.html",
        {"rows": selectors.sales_by_fat_content(_records(request))},
    )


def chart_rating(request):
    return render(
        request,
        "dashboard/partials/_chart_rating.html",
        {"rows": selectors.rating_distribution(_records(request))},
    )


def chart_year(request):
    return render(
        request,
        "dashboard/partials/_chart_year.html",
        {"rows": selectors.sales_by_establishment_year(_records(request))},
    )


def top_items(request):
    return render(
        request,
        "dashboard/partials/_table_top_items.html",
        {"top_bottom": selectors.top_bottom_items(_records(request))},
    )
