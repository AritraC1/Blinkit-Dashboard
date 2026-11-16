"""Dashboard views.

`overview` renders the full page shell. Each widget is a small partial view so
HTMX can refresh it on its own. All views read the filters through the same
helper (`_filters`), which delegates to selectors.
"""

from __future__ import annotations

from django.shortcuts import render

from apps.core.models import SalesRecord

from . import selectors
from .forms import FilterForm


def _filters(request) -> dict:
    """One helper every view reads filters through."""
    return selectors.filters_from_params(request.GET)


def _records(request):
    """SalesRecord queryset with the request's filters applied."""
    return selectors.base_queryset(_filters(request))


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
    return render(request, "dashboard/predictions.html")


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
