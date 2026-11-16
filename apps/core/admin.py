from django.contrib import admin

from .models import Item, Outlet, SalesRecord


@admin.register(Outlet)
class OutletAdmin(admin.ModelAdmin):
    list_display = ("outlet_id", "establishment_year", "location_tier", "outlet_type")
    list_filter = ("outlet_type", "location_tier")
    search_fields = ("outlet_id",)


@admin.register(Item)
class ItemAdmin(admin.ModelAdmin):
    list_display = ("item_id", "item_type", "fat_content", "weight", "category")
    list_filter = ("item_type", "fat_content", "category")
    search_fields = ("item_id",)


@admin.register(SalesRecord)
class SalesRecordAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "item",
        "outlet",
        "outlet_size",
        "visibility",
        "sales",
        "rating",
        "weight_imputed",
        "visibility_imputed",
    )
    list_filter = ("outlet_size",)
    search_fields = ("item__item_id", "outlet__outlet_id")
