from django.urls import path

from . import views

app_name = "dashboard"

urlpatterns = [
    path("", views.overview, name="overview"),
    path("predictions/", views.predictions, name="predictions"),
    # Add HTMX partial endpoints here, e.g. path("partials/kpis/", ...)
]
