from decimal import Decimal

from django.db.models import Sum
from django.test import TestCase
from django.urls import reverse

from apps.core.models import Item, Outlet, SalesRecord

from . import selectors
from .forms import FilterForm
from .templatetags.dashboard_extras import compact, one_decimal, thousands

# Small, fully-known fixture so every selector can be checked against
# hand-computed numbers.
OUTLETS = [
    # outlet_id, year, tier, outlet_type
    ("OUT010", 1999, "Tier 1", "Supermarket Type1"),
    ("OUT011", 2004, "Tier 2", "Supermarket Type1"),
    ("OUT012", 2009, "Tier 3", "Supermarket Type2"),
    ("OUT013", 2014, "Tier 1", "Grocery Store"),
    ("OUT014", 2018, "Tier 2", "Supermarket Type3"),
    ("OUT015", 2022, "Tier 3", "Supermarket Type1"),
]
ITEMS = [
    # item_id, item_type, fat_content
    ("FDA01", "Dairy", "Regular"),
    ("FDA02", "Dairy", "Low Fat"),
    ("DRK01", "Soft Drinks", "Regular"),
    ("HOU01", "Household", "Non-Edible"),
    ("FRU01", "Fruits and Vegetables", "Low Fat"),
]
# (item, outlet, size, visibility, sales, rating)
SALES = [
    ("FDA01", "OUT010", "Small", 0.10, 1000.0, 4.0),
    ("FDA01", "OUT011", "Small", 0.11, 900.0, 4.0),
    ("FDA01", "OUT012", "Medium", 0.12, 800.0, 3.5),
    ("FDA01", "OUT013", "High", 0.13, 700.0, 3.0),
    ("FDA02", "OUT010", "Small", 0.14, 600.0, 4.5),
    ("FDA02", "OUT011", "Medium", 0.15, 500.0, 5.0),
    ("DRK01", "OUT012", "Medium", 0.16, 400.0, 2.5),
    ("DRK01", "OUT013", "High", 0.17, 300.0, 4.0),
    ("HOU01", "OUT014", "Small", 0.18, 200.0, 3.5),
    ("HOU01", "OUT015", "Medium", 0.19, 100.0, 4.0),
    ("FRU01", "OUT014", "Small", 0.20, 50.0, 2.0),
    ("FRU01", "OUT015", "High", 0.21, 25.0, 4.5),
]
TOTAL_SALES = sum(row[4] for row in SALES)  # 5575.0
RECORD_COUNT = len(SALES)


class SelectorTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        outlet_pks = {}
        for outlet_id, year, tier, outlet_type in OUTLETS:
            outlet = Outlet.objects.create(
                outlet_id=outlet_id,
                establishment_year=year,
                location_tier=tier,
                outlet_type=outlet_type,
            )
            outlet_pks[outlet_id] = outlet.pk
        item_pks = {}
        for item_id, item_type, fat_content in ITEMS:
            item = Item.objects.create(
                item_id=item_id,
                item_type=item_type,
                fat_content=fat_content,
                weight=5.0,
                category="Food",
            )
            item_pks[item_id] = item.pk
        SalesRecord.objects.bulk_create(
            SalesRecord(
                item_id=item_pks[item],
                outlet_id=outlet_pks[outlet],
                outlet_size=size,
                visibility=visibility,
                sales=sales,
                rating=rating,
            )
            for item, outlet, size, visibility, sales, rating in SALES
        )


class FilterTests(SelectorTestCase):
    def test_filters_from_params_ignores_blanks_and_unknowns(self):
        self.assertEqual(selectors.filters_from_params({}), {})
        self.assertEqual(
            selectors.filters_from_params(
                {"outlet_type": "", "page": "2", "item_type": "Dairy"}
            ),
            {"item_type": "Dairy"},
        )

    def test_no_filters_returns_everything(self):
        self.assertEqual(
            selectors.base_queryset({}).count(), RECORD_COUNT
        )

    def test_each_filter_reduces_the_record_count(self):
        unfiltered = SalesRecord.objects.count()
        cases = [
            {"outlet": "OUT010"},
            {"outlet_type": "Grocery Store"},
            {"location_tier": "Tier 1"},
            {"item_type": "Dairy"},
            {"fat_content": "Regular"},
            {"year_min": 2009},
            {"year_max": 2009},
        ]
        for filters in cases:
            with self.subTest(filters=filters):
                filtered = selectors.apply_filters(
                    SalesRecord.objects.all(), filters
                )
                self.assertLess(filtered.count(), unfiltered)
                self.assertGreater(filtered.count(), 0)

    def test_year_range_keeps_both_ends(self):
        records = selectors.base_queryset({"year_min": 2009, "year_max": 2018})
        years = set(records.values_list("outlet__establishment_year", flat=True))
        self.assertEqual(years, {2009, 2014, 2018})

    def test_combined_filters_narrow_further(self):
        dairy = selectors.base_queryset({"item_type": "Dairy"}).count()
        dairy_tier_1 = selectors.base_queryset(
            {"item_type": "Dairy", "location_tier": "Tier 1"}
        ).count()
        self.assertLess(dairy_tier_1, dairy)


class SelectorTotalsTests(SelectorTestCase):
    def test_kpi_summary_matches_manual_aggregation(self):
        kpis = selectors.kpi_summary(SalesRecord.objects.all())
        self.assertAlmostEqual(kpis["total_sales"], TOTAL_SALES)
        self.assertEqual(kpis["item_count"], len(ITEMS))
        self.assertEqual(kpis["outlet_count"], len(OUTLETS))
        self.assertAlmostEqual(
            kpis["avg_sales"], TOTAL_SALES / RECORD_COUNT
        )
        self.assertAlmostEqual(
            kpis["avg_rating"], sum(row[5] for row in SALES) / RECORD_COUNT
        )

    def test_breakdowns_sum_to_the_unfiltered_total(self):
        qs = SalesRecord.objects.all()
        for selector, key in [
            (selectors.sales_by_item_type, "sales"),
            (selectors.sales_by_outlet_type, "sales"),
            (selectors.sales_by_fat_content, "sales"),
            (selectors.sales_by_establishment_year, "sales"),
            (selectors.sales_by_tier_size, "sales"),
        ]:
            with self.subTest(selector=selector.__name__):
                self.assertAlmostEqual(
                    sum(row[key] for row in selector(qs)), TOTAL_SALES
                )

    def test_top_and_bottom_items_are_disjoint(self):
        top_bottom = selectors.top_bottom_items(SalesRecord.objects.all(), n=2)
        combined = top_bottom["top"] + top_bottom["bottom"]
        # 4 distinct items of 5; the middle item (DRK01, 700) is left out.
        self.assertAlmostEqual(
            sum(entry["sales"] for entry in combined), TOTAL_SALES - 700.0
        )
        top_ids = {entry["item_id"] for entry in top_bottom["top"]}
        bottom_ids = {entry["item_id"] for entry in top_bottom["bottom"]}
        self.assertFalse(top_ids & bottom_ids)

    def test_top_items_are_ranked_by_sales(self):
        top = selectors.top_bottom_items(SalesRecord.objects.all(), n=2)["top"]
        self.assertEqual([entry["item_id"] for entry in top], ["FDA01", "FDA02"])
        self.assertEqual(top[0]["rank"], 1)
        self.assertGreater(top[0]["sales"], top[1]["sales"])

    def test_bottom_items_are_ranked_descending(self):
        # The bottom table continues the ranking: higher of the low items
        # first, very worst last.
        bottom = selectors.top_bottom_items(SalesRecord.objects.all(), n=2)[
            "bottom"
        ]
        self.assertEqual(
            [entry["item_id"] for entry in bottom], ["HOU01", "FRU01"]
        )
        self.assertGreater(bottom[0]["sales"], bottom[1]["sales"])

    def test_rating_distribution_is_binned_and_counts_every_row(self):
        distribution = selectors.rating_distribution(SalesRecord.objects.all())
        self.assertEqual(
            sum(bin_["count"] for bin_ in distribution), RECORD_COUNT
        )
        self.assertEqual(len(distribution), 8)  # 1.0-5.0 in 0.5 steps
        # All four rows sitting at exactly 4.0 land in the 4.0-4.5 bin.
        bin_4_0 = next(b for b in distribution if b["label"] == "4.0-4.5")
        self.assertEqual(bin_4_0["count"], 4)

    def test_rating_distribution_with_empty_queryset(self):
        distribution = selectors.rating_distribution(
            SalesRecord.objects.none()
        )
        self.assertEqual(sum(bin_["count"] for bin_ in distribution), 0)

    def test_filtered_selectors_match_the_filtered_queryset(self):
        qs = selectors.base_queryset({"location_tier": "Tier 1"})
        expected = qs.aggregate(total=Sum("sales"))["total"]
        self.assertAlmostEqual(
            selectors.kpi_summary(qs)["total_sales"], expected
        )
        self.assertAlmostEqual(
            sum(r["sales"] for r in selectors.sales_by_item_type(qs)), expected
        )


class FormTests(SelectorTestCase):
    def test_choices_come_from_the_database(self):
        form = FilterForm()
        self.assertIn(("Dairy", "Dairy"), form.fields["item_type"].choices)
        self.assertIn(("", "All outlet types"), form.fields["outlet_type"].choices)
        self.assertIn((1999, 1999), form.fields["year_min"].choices)

    def test_all_fields_optional(self):
        form = FilterForm(data={})
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(selectors.filters_from_params(form.cleaned_data), {})


class ViewTests(SelectorTestCase):
    def test_overview_full_page(self):
        response = self.client.get(reverse("dashboard:overview"))
        self.assertEqual(response.status_code, 200)
        content = response.content.decode()
        self.assertIn('id="dashboard-area"', content)
        self.assertIn('id="filter-form"', content)
        self.assertIn(reverse("dashboard:partials_kpis"), content)

    def test_overview_htmx_request_returns_only_the_area(self):
        response = self.client.get(
            reverse("dashboard:overview"), HTTP_HX_REQUEST="true"
        )
        self.assertEqual(response.status_code, 200)
        content = response.content.decode()
        self.assertIn('id="dashboard-area"', content)
        self.assertNotIn('id="filter-form"', content)

    def test_filter_querystring_propagates_to_widget_urls(self):
        response = self.client.get(
            reverse("dashboard:overview"), {"item_type": "Dairy"}
        )
        self.assertIn("item_type=Dairy", response.content.decode())

    def test_kpi_partial(self):
        response = self.client.get(reverse("dashboard:partials_kpis"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Total Sales")

    def test_chart_partials_render_canvas_and_data(self):
        cases = [
            (
                "dashboard:partials_chart_item_type",
                "chart-item-type-data",
                "bar-horizontal",
            ),
            ("dashboard:partials_chart_outlet", "chart-outlet-data", "pie"),
            (
                "dashboard:partials_chart_tier_size",
                "chart-tier-size-data",
                "bar-stacked-h",
            ),
            (
                "dashboard:partials_chart_fat_content",
                "chart-fat-content-data",
                "polar-area",
            ),
            ("dashboard:partials_chart_rating", "chart-rating-data", "histogram"),
            ("dashboard:partials_chart_year", "chart-year-data", "line"),
        ]
        for url_name, data_id, chart_type in cases:
            with self.subTest(url_name=url_name):
                response = self.client.get(reverse(url_name))
                self.assertEqual(response.status_code, 200)
                content = response.content.decode()
                self.assertIn("<canvas", content)
                self.assertIn(data_id, content)
                self.assertIn(f'data-chart="{chart_type}"', content)

    def test_top_items_partial(self):
        response = self.client.get(reverse("dashboard:partials_top_items"))
        self.assertEqual(response.status_code, 200)
        content = response.content.decode()
        self.assertIn("Top 10 Items by Sales", content)
        self.assertIn("Bottom 10 Items by Sales", content)
        self.assertIn("FDA01", content)

    def test_partials_respect_filters(self):
        response = self.client.get(
            reverse("dashboard:partials_kpis"), {"item_type": "Household"}
        )
        content = response.content.decode()
        # HOU01 sells only 300 across 2 outlets.
        self.assertIn("300", content)
        self.assertIn('2</span>', content)  # outlet count stays as markup

    def test_overview_shows_empty_state_when_no_data_loaded(self):
        SalesRecord.objects.all().delete()
        response = self.client.get(reverse("dashboard:overview"))
        self.assertEqual(response.status_code, 200)
        content = response.content.decode()
        self.assertIn("No data loaded yet", content)
        self.assertIn("run_etl", content)

    def test_footer_shows_data_source_and_etl_status(self):
        SalesRecord.objects.all().delete()
        response = self.client.get(reverse("dashboard:overview"))
        self.assertEqual(response.status_code, 200)
        content = response.content.decode()
        self.assertIn("BlinkIT_Grocery_Data.xlsx", content)
        # The test database has no cleaned CSV, so ETL has not been run.
        self.assertIn("Last ETL", content)

    def test_kpis_show_empty_state_when_filter_excludes_everything(self):
        response = self.client.get(
            reverse("dashboard:partials_kpis"), {"outlet": "DOES-NOT-EXIST"}
        )
        self.assertEqual(response.status_code, 200)
        content = response.content.decode()
        self.assertIn("No records match the current filters", content)

    def test_chart_partial_shows_empty_state_when_filter_excludes_everything(self):
        response = self.client.get(
            reverse("dashboard:partials_chart_item_type"),
            {"outlet": "DOES-NOT-EXIST"},
        )
        self.assertEqual(response.status_code, 200)
        content = response.content.decode()
        self.assertIn("No records match the current filters", content)
        self.assertNotIn("<canvas", content)

    def test_top_items_shows_empty_state_when_no_data_loaded(self):
        SalesRecord.objects.all().delete()
        response = self.client.get(reverse("dashboard:partials_top_items"))
        self.assertEqual(response.status_code, 200)
        content = response.content.decode()
        self.assertIn("No data loaded yet", content)
        self.assertIn("run_etl", content)


class TemplateTagTests(TestCase):
    def test_thousands(self):
        self.assertEqual(thousands(1234567.8), "1,234,568")
        self.assertEqual(thousands(None), "0")

    def test_compact(self):
        self.assertEqual(compact(1234567.8), "1.2M")
        self.assertEqual(compact(1234.0), "1.2K")
        self.assertEqual(compact(999), "999")
        self.assertEqual(compact(None), "0")

    def test_one_decimal(self):
        self.assertEqual(one_decimal(3.966), "4.0")
        self.assertEqual(one_decimal(141.0), "141.0")
        self.assertEqual(one_decimal(None), "0.0")

    def test_no_currency_symbol_assumed(self):
        self.assertNotIn("$", thousands(1234.0))
        self.assertNotIn("$", compact(1234.0))
