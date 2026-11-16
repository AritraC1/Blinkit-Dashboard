from django.urls import path

from . import views

app_name = "dashboard"

urlpatterns = [
    path("", views.overview, name="overview"),
    path("predictions/", views.predictions, name="predictions"),
    # HTMX partial endpoints. Each widget refreshes on its own.
    path("partials/kpis/", views.kpi_cards, name="partials_kpis"),
    path("partials/charts/item-type/", views.chart_item_type, name="partials_chart_item_type"),
    path("partials/charts/outlet/", views.chart_outlet, name="partials_chart_outlet"),
    path("partials/charts/tier-size/", views.chart_tier_size, name="partials_chart_tier_size"),
    path("partials/charts/fat-content/", views.chart_fat_content, name="partials_chart_fat_content"),
    path("partials/charts/rating/", views.chart_rating, name="partials_chart_rating"),
    path("partials/charts/year/", views.chart_year, name="partials_chart_year"),
    path("partials/top-items/", views.top_items, name="partials_top_items"),
    # ML partials (page 2).
    path("partials/model-metrics/", views.model_metrics, name="partials_model_metrics"),
    path(
        "partials/feature-importance/",
        views.feature_importance,
        name="partials_feature_importance",
    ),
    path(
        "partials/chart-actual-vs-predicted/",
        views.chart_actual_vs_predicted,
        name="partials_chart_actual_vs_predicted",
    ),
    path(
        "partials/item-type-predictions/",
        views.item_type_predictions,
        name="partials_item_type_predictions",
    ),
    path("partials/predict-form/", views.predict_form, name="partials_predict_form"),
    path(
        "partials/recent-predictions/",
        views.recent_predictions,
        name="partials_recent_predictions",
    ),
    # The what-if form POST endpoint.
    path("predictions/run/", views.run_prediction, name="run_prediction"),
]
