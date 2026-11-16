"""Selectors: every DB aggregation the dashboard needs, in one testable place.

All widget functions take a SalesRecord queryset (filtered or not) and return
plain lists and dicts, so views and templates stay thin.
"""

from __future__ import annotations

from django.db.models import Avg, Count, FloatField, Sum, Value
from django.db.models.functions import Coalesce

from apps.core.models import SalesRecord

# The shared filter names. Everything is optional; blank values are ignored.
FILTER_FIELDS = (
    "outlet_type",
    "location_tier",
    "item_type",
    "fat_content",
    "year_min",
    "year_max",
)


def filters_from_params(params) -> dict:
    """Read the shared filters out of a QueryDict (or plain dict).

    Unknown keys and blank values are dropped, so empty form fields never
    narrow the queryset.
    """
    filters: dict = {}
    for name in FILTER_FIELDS:
        value = params.get(name) if hasattr(params, "get") else None
        if value not in (None, ""):
            filters[name] = value
    return filters


def apply_filters(queryset, filters: dict | None):
    """Apply the shared dashboard filters to a SalesRecord queryset.

    outlet_type / location_tier / year range live on Outlet, item_type /
    fat_content on Item; both reached through the SalesRecord joins.
    """
    filters = filters or {}
    if filters.get("outlet_type"):
        queryset = queryset.filter(outlet__outlet_type=filters["outlet_type"])
    if filters.get("location_tier"):
        queryset = queryset.filter(outlet__location_tier=filters["location_tier"])
    if filters.get("year_min"):
        queryset = queryset.filter(
            outlet__establishment_year__gte=int(filters["year_min"])
        )
    if filters.get("year_max"):
        queryset = queryset.filter(
            outlet__establishment_year__lte=int(filters["year_max"])
        )
    if filters.get("item_type"):
        queryset = queryset.filter(item__item_type=filters["item_type"])
    if filters.get("fat_content"):
        queryset = queryset.filter(item__fat_content=filters["fat_content"])
    return queryset


def base_queryset(filters: dict | None = None):
    """The single entry point views use: unfiltered records + shared filters."""
    return apply_filters(SalesRecord.objects.select_related("item", "outlet"), filters)


# ---- Widgets ---------------------------------------------------------------


def kpi_summary(qs) -> dict:
    """Headline numbers: total sales, average sales, average rating, item and
    outlet counts."""
    agg = qs.aggregate(
        total_sales=Coalesce(Sum("sales"), Value(0.0), output_field=FloatField()),
        avg_sales=Avg("sales"),
        avg_rating=Avg("rating"),
        item_count=Count("item", distinct=True),
        outlet_count=Count("outlet", distinct=True),
    )
    return {
        "total_sales": agg["total_sales"],
        "avg_sales": agg["avg_sales"],
        "avg_rating": agg["avg_rating"],
        "item_count": agg["item_count"],
        "outlet_count": agg["outlet_count"],
    }


def sales_by_item_type(qs) -> list[dict]:
    """Total sales per item type, highest first."""
    rows = (
        qs.values("item__item_type")
        .annotate(total=Sum("sales"))
        .order_by("-total", "item__item_type")
    )
    return [{"label": row["item__item_type"], "sales": row["total"]} for row in rows]


def sales_by_outlet_type(qs) -> list[dict]:
    """Total and average sales per outlet type, highest total first."""
    rows = (
        qs.values("outlet__outlet_type")
        .annotate(total=Sum("sales"), average=Avg("sales"))
        .order_by("-total", "outlet__outlet_type")
    )
    return [
        {
            "label": row["outlet__outlet_type"],
            "sales": row["total"],
            "avg": row["average"],
        }
        for row in rows
    ]


def sales_by_tier_size(qs) -> list[dict]:
    """Total sales per (location tier, outlet size) pair.

    Note: the outlet size grouping is distorted by a few inconsistent outlets,
    so the chart carrying this data shows a caption.
    """
    rows = qs.values(
        "outlet__location_tier", "outlet_size"
    ).annotate(total=Sum("sales"))
    return [
        {
            "tier": row["outlet__location_tier"],
            "size": row["outlet_size"],
            "sales": row["total"],
        }
        for row in rows
    ]


def sales_by_fat_content(qs) -> list[dict]:
    """Total sales per fat content value, highest first."""
    rows = (
        qs.values("item__fat_content")
        .annotate(total=Sum("sales"))
        .order_by("-total", "item__fat_content")
    )
    return [{"label": row["item__fat_content"], "sales": row["total"]} for row in rows]


# Rating bins: 1.0 up to and including 5.0, in 0.5 steps. Rows sitting at
# exactly 4.0 (3,339 of them in the unfiltered data) land in the 4.0-4.5 bin.
_RATING_BIN_WIDTH = 0.5
_RATING_MIN = 1.0
_RATING_MAX = 5.0
_RATING_BIN_COUNT = int(round((_RATING_MAX - _RATING_MIN) / _RATING_BIN_WIDTH))


def rating_distribution(qs) -> list[dict]:
    """Count of records per rating bin (0.5 wide, 1.0-5.0 inclusive)."""
    counts = [0] * _RATING_BIN_COUNT
    for rating in qs.values_list("rating", flat=True):
        if rating is None:
            continue
        index = int((rating - _RATING_MIN) / _RATING_BIN_WIDTH)
        # Ratings below 1.0 (should not exist) fall in the first bin; exactly
        # 5.0 and anything above fall in the last bin.
        index = max(0, min(index, _RATING_BIN_COUNT - 1))
        counts[index] += 1
    labels = [
        f"{_RATING_MIN + i * _RATING_BIN_WIDTH:.1f}-{_RATING_MIN + (i + 1) * _RATING_BIN_WIDTH:.1f}"
        for i in range(_RATING_BIN_COUNT)
    ]
    return [{"label": label, "count": count} for label, count in zip(labels, counts)]


def sales_by_establishment_year(qs) -> list[dict]:
    """Total sales per outlet establishment year, earliest first."""
    rows = (
        qs.values("outlet__establishment_year")
        .annotate(total=Sum("sales"))
        .order_by("outlet__establishment_year")
    )
    return [
        {"label": row["outlet__establishment_year"], "sales": row["total"]}
        for row in rows
    ]


def top_bottom_items(qs, n: int = 10) -> dict:
    """The n items with the highest and the n with the lowest total sales.

    Returns {"top": [...], "bottom": [...]}; each entry is a plain dict with
    rank, item id, item type, outlet count and total sales. The bottom list is
    ordered lowest-sales first.
    """
    rows = (
        qs.values("item__item_id", "item__item_type")
        .annotate(
            total=Sum("sales"), outlets=Count("outlet", distinct=True)
        )
        .order_by("item__item_id")
    )
    ordered = list(rows.order_by("-total"))

    def entry(rank: int, row: dict) -> dict:
        return {
            "rank": rank,
            "item_id": row["item__item_id"],
            "item_type": row["item__item_type"],
            "outlets": row["outlets"],
            "sales": row["total"],
        }

    top = [entry(i + 1, row) for i, row in enumerate(ordered[:n])]
    bottom_rows = list(reversed(list(rows.order_by("total")[:n])))
    bottom = [entry(i + 1, row) for i, row in enumerate(bottom_rows)]
    return {"top": top, "bottom": bottom}
