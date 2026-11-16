"""Forms: the dashboard filter form and the what-if prediction form.

Both load their choices from the database so a value only shows up once data
exists for it. The filter form is GET-based and all-optional; the prediction
form is POST-based and fully required, with the observed data ranges enforced.
"""

from __future__ import annotations

from django import forms

from apps.core.models import Item, Outlet
from apps.ml.predict import VISIBILITY_RANGE, WEIGHT_RANGE, YEAR_RANGE


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


class PredictionForm(forms.Form):
    """The what-if prediction form: one full item/outlet profile.

    Every field is required (a prediction needs a complete row) and validated
    against the observed dataset ranges, mirroring apps.ml.predict so a bad
    value is caught before it ever reaches the model.
    """

    item_type = forms.ChoiceField()
    fat_content = forms.ChoiceField()
    category = forms.ChoiceField()
    weight = forms.FloatField(
        min_value=WEIGHT_RANGE[0],
        max_value=WEIGHT_RANGE[1],
        help_text=f"Between {WEIGHT_RANGE[0]:g} and {WEIGHT_RANGE[1]:g}.",
    )
    visibility = forms.FloatField(
        min_value=VISIBILITY_RANGE[0],
        max_value=VISIBILITY_RANGE[1],
        help_text=f"Between {VISIBILITY_RANGE[0]:g} and {VISIBILITY_RANGE[1]:g}.",
    )
    outlet_type = forms.ChoiceField()
    location_tier = forms.ChoiceField()
    establishment_year = forms.ChoiceField()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.fields["item_type"].choices = _choices(
            list(Item.objects.values_list("item_type", flat=True))
        )
        self.fields["fat_content"].choices = _choices(
            list(Item.objects.values_list("fat_content", flat=True))
        )
        self.fields["category"].choices = _choices(
            list(Item.objects.values_list("category", flat=True))
        )
        self.fields["outlet_type"].choices = _choices(
            list(Outlet.objects.values_list("outlet_type", flat=True))
        )
        self.fields["location_tier"].choices = _choices(
            list(Outlet.objects.values_list("location_tier", flat=True))
        )
        self.fields["establishment_year"].choices = _choices(
            list(Outlet.objects.values_list("establishment_year", flat=True))
        )
