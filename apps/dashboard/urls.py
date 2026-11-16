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
]
