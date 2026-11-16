"""Dashboard views. Currently placeholders - replace with real full-page + HTMX partial views."""
from django.shortcuts import render


def overview(request):
    return render(request, "dashboard/overview.html")


def predictions(request):
    return render(request, "dashboard/predictions.html")
