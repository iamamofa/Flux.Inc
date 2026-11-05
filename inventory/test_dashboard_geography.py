"""Origin extraction does not fabricate vendor or sample locations."""
import json
from types import SimpleNamespace
from django.test import SimpleTestCase
from .dashboard_geography import build_dashboard_geography, normalize_country


class DashboardGeographyTests(SimpleTestCase):
    def sample(self, country='', metadata=None, **kwargs):
        return SimpleNamespace(country=country, metadata=metadata or {}, **kwargs)

    def vendor(self, **kwargs):
        defaults = {'vendor': '', 'vendor_country': '', 'vendor_city': ''}
        defaults.update(kwargs)
        return SimpleNamespace(**defaults)

    def test_country_aliases_and_iso_codes_share_one_country(self):
        for value, code in [(' Ghana ', 'GHA'), ('gh', 'GHA'), ('GHA', 'GHA'),
                            ('Côte d’Ivoire', 'CIV'), ('Ivory Coast', 'CIV'),
                            ('USA', 'USA'), ('UK', 'GBR'), ('Cape Verde', 'CPV')]:
            with self.subTest(value=value):
                self.assertEqual(normalize_country(value), code)
        result = build_dashboard_geography([self.sample(v) for v in ['Ghana', 'GH', 'gha']], 'samples')
        self.assertEqual(result['countries'][0]['count'], 3)
        self.assertEqual(result['summary']['countries'], 1)

    def test_collection_metadata_precedes_general_country(self):
        item = self.sample('Nigeria', {' Country_of_Origin ': 'GH', 'Collection site': 'Accra'})
        result = build_dashboard_geography([item], 'samples')
        point = result['locations'][0]
        self.assertEqual(point['country_code'], 'GHA')
        self.assertEqual(point['precision'], 'city')
        self.assertEqual(point['source'], 'Natural Earth city reference')
        self.assertEqual(result['summary']['ghana'], 1)

    def test_metadata_fallback_and_known_ghana_city_without_country(self):
        result = build_dashboard_geography([
            self.sample(metadata={'Country': 'Senegal'}),
            self.sample(metadata={'City': 'Kumasi'}),
            self.sample(metadata={'Collection site': 'Lagos, Nigeria'}),
        ], 'samples')
        self.assertEqual({c['code'] for c in result['countries']}, {'SEN', 'GHA', 'NGA'})
        self.assertEqual(result['summary']['mapped'], 3)
        self.assertEqual(result['summary']['west_africa'], 3)

    def test_unknown_city_stays_country_level_and_no_country_is_invented(self):
        result = build_dashboard_geography([
            self.sample('Ghana', {'City': 'Unlisted town'}),
            self.sample(metadata={'Storage location': 'Accra', 'Region': 'Unlisted region'}),
            self.sample('Unknown country'),
        ], 'samples')
        self.assertEqual(result['summary']['mapped'], 1)
        self.assertEqual(result['summary']['unmapped'], 2)
        self.assertEqual(result['locations'][0]['precision'], 'country')

    def test_recorded_coordinates_override_approximate_city_reference(self):
        result = build_dashboard_geography([
            self.sample('Ghana', {'City': 'Accra', 'Latitude': '5.6', 'Longitude': '-0.2'}),
            self.sample('Ghana', {'GPS coordinates': '6.7, -1.6'}),
        ], 'samples')
        points = result['locations']
        self.assertEqual({(p['latitude'], p['longitude']) for p in points}, {(5.6, -0.2), (6.7, -1.6)})
        self.assertTrue(all(p['precision'] == 'coordinates' for p in points))

    def test_invalid_or_unpaired_coordinates_never_become_points(self):
        cases = [
            {'Latitude': '5.6'}, {'Latitude': 'nan', 'Longitude': '0'},
            {'Latitude': '91', 'Longitude': '-1'}, {'Latitude': '6', 'Longitude': '181'},
            {'Latitude': '6', 'Storage longitude': '-1'},
        ]
        result = build_dashboard_geography([self.sample('Ghana', m) for m in cases], 'samples')
        self.assertEqual(result['summary']['mapped'], len(cases))
        self.assertEqual(result['locations'][0]['count'], len(cases))
        self.assertEqual(result['locations'][0]['precision'], 'country')
        json.dumps(result, allow_nan=False)

    def test_coordinates_without_country_use_africa_boundaries(self):
        result = build_dashboard_geography([
            self.sample(metadata={'Latitude': '6.7', 'Longitude': '-1.6'}),
            self.sample(metadata={'Latitude': '48.85', 'Longitude': '2.35'}),
        ], 'samples')
        self.assertEqual(result['summary']['mapped'], 1)
        self.assertEqual(result['summary']['unmapped'], 1)
        self.assertEqual(result['locations'][0]['country_code'], 'GHA')
        self.assertEqual(result['locations'][0]['precision'], 'coordinates')
        self.assertIn('Country required', result['unmapped_locations'][0]['reason'])

    def test_vendor_country_is_origin_and_storage_is_ignored(self):
        result = build_dashboard_geography([
            self.vendor(vendor='Lab Supply', vendor_country='Germany', vendor_city='Berlin', cold_storage='Accra'),
            self.vendor(vendor='Unknown lab', cold_storage='Ghana', storage_location='Accra'),
        ], 'reagents')
        self.assertEqual(result['countries'][0]['code'], 'DEU')
        self.assertEqual(result['summary']['outside_africa'], 1)
        self.assertEqual(result['summary']['unmapped'], 1)
        self.assertEqual(result['locations'][0]['vendors'], ['Lab Supply'])

    def test_vendor_name_never_implies_country_without_explicit_location(self):
        result = build_dashboard_geography([
            self.vendor(vendor='Ghana Scientific'),
            self.vendor(vendor='Guinea Diagnostics'),
            self.vendor(vendor='GE'),
            self.vendor(vendor='Lab Supply (Accra, Ghana)'),
            self.vendor(vendor='Ghana / Germany'),
        ], 'consumables')
        self.assertEqual(result['summary']['mapped'], 1)
        self.assertEqual(result['summary']['unmapped'], 4)
        self.assertEqual(result['countries'][0]['code'], 'GHA')

    def test_equipment_uses_source_or_donor_but_never_storage_location(self):
        result = build_dashboard_geography([
            self.vendor(source='Supplier A', donated_by='', vendor_country='Ghana', vendor_city='Tema'),
            self.vendor(source='', donated_by='Donor (UK)', storage_location='Accra'),
            self.vendor(source='Siemens', donated_by='', storage_location='Ghana'),
        ], 'equipment')
        self.assertEqual(result['summary']['mapped'], 2)
        self.assertEqual(result['summary']['unmapped'], 1)
        self.assertEqual({c['code'] for c in result['countries']}, {'GHA', 'GBR'})

    def test_counts_are_inventory_records_not_quantities(self):
        result = build_dashboard_geography([
            self.vendor(vendor='One', vendor_country='Ghana', vendor_city='Accra', pack_count=500),
            self.vendor(vendor='Two', vendor_country='GH', vendor_city='Accra', pack_count=1),
        ], 'consumables')
        self.assertEqual(result['summary']['total'], 2)
        self.assertEqual(result['locations'][0]['count'], 2)
        self.assertEqual(result['locations'][0]['vendors'], ['One', 'Two'])

    def test_empty_inventory_has_no_fabricated_ghana_records(self):
        result = build_dashboard_geography([], 'samples')
        self.assertEqual(result['summary']['mapped'], 0)
        self.assertEqual(result['summary']['ghana'], 0)
        self.assertEqual(result['countries'], [])
        self.assertEqual(result['locations'], [])
        with self.assertRaises(ValueError):
            build_dashboard_geography([], 'other')

    def test_congo_country_variants_keep_the_two_countries_distinct(self):
        for value, code in [('Democratic Republic of Congo', 'COD'),
                            ('Congo Kinshasa', 'COD'), ('Congo Brazzaville', 'COG')]:
            with self.subTest(value=value):
                result = build_dashboard_geography([self.sample(value)], 'samples')
                self.assertEqual(result['countries'][0]['code'], code)

    def test_conflicting_coordinates_keep_country_counts_and_show_review_warning(self):
        result = build_dashboard_geography([
            self.sample('Ghana', {'Latitude': '9.08', 'Longitude': '8.68'}),
            self.sample('Ghana', {'City': 'Accra', 'Latitude': '48.85', 'Longitude': '2.35'}),
            self.sample('Germany', {'Latitude': '6.7', 'Longitude': '-1.6'}),
        ], 'samples')
        self.assertEqual(result['summary']['mapped'], 3)
        self.assertEqual(result['summary']['ghana'], 2)
        self.assertEqual(result['summary']['coordinate_conflicts'], 3)
        self.assertTrue(all(point['precision'] == 'country' for point in result['locations']))
        self.assertTrue(all(point['warning'] for point in result['locations']))
        self.assertEqual(sum(row['count'] for row in result['location_warnings']), 3)
