"""Forms: the dashboard filter form.

GET-based and all fields optional; choices are loaded from the database so a
value only shows up once data exists for it.
"""

from __future__ import annotations

from django import forms

from apps.core.models import Item, Outlet


def _choices(values: list) -> list[tuple]:
    return [(value, value) for value in sorted(set(values))]


class FilterForm(forms.Form):
    """Every dashboard filter. All optional; blank values are ignored."""

    outlet_type = forms.ChoiceField(required=False)
    location_tier = forms.ChoiceField(required=False)
    item_type = forms.ChoiceField(required=False)
    fat_content = forms.ChoiceField(required=False)
    year_min = forms.ChoiceField(required=False)
    year_max = forms.ChoiceField(required=False)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        outlet_types = Outlet.objects.values_list("outlet_type", flat=True)
        tiers = Outlet.objects.values_list("location_tier", flat=True)
        item_types = Item.objects.values_list("item_type", flat=True)
        fat_contents = Item.objects.values_list("fat_content", flat=True)
        years = Outlet.objects.values_list("establishment_year", flat=True)

        self.fields["outlet_type"].choices = [("", "All outlet types")] + _choices(
            list(outlet_types)
        )
        self.fields["location_tier"].choices = [("", "All tiers")] + _choices(
            list(tiers)
        )
        self.fields["item_type"].choices = [("", "All item types")] + _choices(
            list(item_types)
        )
        self.fields["fat_content"].choices = [("", "All fat contents")] + _choices(
            list(fat_contents)
        )
        year_choices = _choices(list(years))
        self.fields["year_min"].choices = [("", "From year")] + year_choices
        self.fields["year_max"].choices = [("", "To year")] + year_choices
