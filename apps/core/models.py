from django.db import models


class LocationTier(models.TextChoices):
    TIER_1 = "Tier 1", "Tier 1"
    TIER_2 = "Tier 2", "Tier 2"
    TIER_3 = "Tier 3", "Tier 3"


class OutletType(models.TextChoices):
    GROCERY_STORE = "Grocery Store", "Grocery Store"
    SUPERMARKET_TYPE1 = "Supermarket Type1", "Supermarket Type1"
    SUPERMARKET_TYPE2 = "Supermarket Type2", "Supermarket Type2"
    SUPERMARKET_TYPE3 = "Supermarket Type3", "Supermarket Type3"


class OutletSize(models.TextChoices):
    SMALL = "Small", "Small"
    MEDIUM = "Medium", "Medium"
    HIGH = "High", "High"


class FatContent(models.TextChoices):
    LOW_FAT = "Low Fat", "Low Fat"
    REGULAR = "Regular", "Regular"


class ItemCategory(models.TextChoices):
    FOOD = "Food", "Food"
    DRINK = "Drink", "Drink"
    NON_CONSUMABLE = "Non-Consumable", "Non-Consumable"


class Outlet(models.Model):
    outlet_id = models.CharField(max_length=10, unique=True)
    establishment_year = models.PositiveIntegerField()
    location_tier = models.CharField(max_length=10, choices=LocationTier.choices)
    outlet_type = models.CharField(max_length=30, choices=OutletType.choices)

    class Meta:
        ordering = ["outlet_id"]

    def __str__(self) -> str:
        return self.outlet_id


class Item(models.Model):
    item_id = models.CharField(max_length=10, unique=True)
    item_type = models.CharField(max_length=50)
    fat_content = models.CharField(max_length=10, choices=FatContent.choices)
    weight = models.FloatField(null=True, blank=True)
    category = models.CharField(max_length=20, choices=ItemCategory.choices)

    class Meta:
        ordering = ["item_id"]

    def __str__(self) -> str:
        return self.item_id


class SalesRecord(models.Model):
    item = models.ForeignKey(
        Item, on_delete=models.CASCADE, related_name="sales_records", db_index=True
    )
    outlet = models.ForeignKey(
        Outlet, on_delete=models.CASCADE, related_name="sales_records", db_index=True
    )
    outlet_size = models.CharField(max_length=10, choices=OutletSize.choices)
    visibility = models.FloatField()
    sales = models.FloatField()
    rating = models.FloatField()
    weight_imputed = models.BooleanField(default=False)
    visibility_imputed = models.BooleanField(default=False)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["item", "outlet"], name="unique_item_outlet_sales_record"
            )
        ]
        indexes = [
            models.Index(fields=["item"]),
            models.Index(fields=["outlet"]),
        ]

    def __str__(self) -> str:
        return f"{self.item.item_id} @ {self.outlet.outlet_id}"
