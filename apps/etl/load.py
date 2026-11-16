"""LOAD: fill the database. Re-runnable, never duplicates rows."""

from __future__ import annotations

import pandas as pd
from django.db import transaction

from apps.core.models import Item, Outlet, SalesRecord

BATCH_SIZE = 1000


def load(df: pd.DataFrame) -> int:
    """Upsert Outlets, upsert Items, then replace SalesRecords.

    Everything happens in one transaction: either the database ends up fully
    refreshed or unchanged. Re-running is idempotent - SalesRecords are
    replaced wholesale and Outlets/Items are upserted on their unique id.

    Returns the number of SalesRecords inserted.
    """
    outlets = (
        df[["outlet_id", "establishment_year", "location_tier", "outlet_type"]]
        .drop_duplicates(subset="outlet_id")
        .to_dict("records")
    )
    items = (
        df[["item_id", "item_type", "fat_content", "weight", "category"]]
        .drop_duplicates(subset="item_id")
        .to_dict("records")
    )
    sales = df.to_dict("records")

    with transaction.atomic():
        # 1. Upsert Outlets.
        Outlet.objects.bulk_create(
            [Outlet(**row) for row in outlets],
            batch_size=BATCH_SIZE,
            update_conflicts=True,
            unique_fields=["outlet_id"],
            update_fields=["establishment_year", "location_tier", "outlet_type"],
        )
        outlet_ids = dict(Outlet.objects.values_list("outlet_id", "pk"))

        # 2. Upsert Items.
        Item.objects.bulk_create(
            [Item(**row) for row in items],
            batch_size=BATCH_SIZE,
            update_conflicts=True,
            unique_fields=["item_id"],
            update_fields=["item_type", "fat_content", "weight", "category"],
        )
        item_ids = dict(Item.objects.values_list("item_id", "pk"))

        # 3. Replace SalesRecords with a bulk insert, in batches.
        SalesRecord.objects.all().delete()
        SalesRecord.objects.bulk_create(
            [
                SalesRecord(
                    item_id=item_ids[row["item_id"]],
                    outlet_id=outlet_ids[row["outlet_id"]],
                    outlet_size=row["outlet_size"],
                    visibility=row["visibility"],
                    sales=row["sales"],
                    rating=row["rating"],
                    weight_imputed=bool(row["weight_imputed"]),
                    visibility_imputed=bool(row["visibility_imputed"]),
                )
                for row in sales
            ],
            batch_size=BATCH_SIZE,
        )

    return len(sales)
