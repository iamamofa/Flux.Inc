"""Integration coverage for dashboard origins and vendor location workflows."""
import csv
from datetime import timedelta
import io
import json
import re

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .models import (
    Consumable, Equipment, Project, Reagent, Sample,
    TrashConsumable, TrashEquipment, TrashReagent,
)


DASHBOARDS = (
    ('dashboard_samples', Sample),
    ('dashboard_consumables', Consumable),
    ('dashboard_reagents', Reagent),
    ('dashboard_equipment_', Equipment),
)


class DashboardMapViewTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.manager = User.objects.create_user(username='map-manager')
        cls.outsider = User.objects.create_user(username='map-outsider')
        cls.project = Project.objects.create(name='Map Project', project_manager=cls.manager)
        cls.other_project = Project.objects.create(name='Other Map Project', project_manager=cls.outsider)

    def setUp(self):
        self.client.force_login(self.manager)

    def make_item(self, model, identifier, *, project=None, country='Ghana', active=True, **extra):
        values = {'project': project or self.project, 'is_active': active}
        if model is Sample:
            values.update(sample_id=identifier, sample_type='Serum', volume=1,
                          collection_date=timezone.localdate(), country=country, notes='')
        elif model is Equipment:
            values.update(name=identifier, equip_id=identifier, vendor_country=country,
                          vendor_city='Accra' if country == 'Ghana' else '', source='Lab vendor')
        else:
            values.update(name=identifier, items_per_pack=10, items_left_in_pack=10,
                          pack_count=2, cold_storage='Room temperature', vendor='Lab vendor',
                          vendor_country=country, vendor_city='Accra' if country == 'Ghana' else '')
        values.update(extra)
        return model.objects.create(**values)

    def test_all_dashboards_make_map_primary_and_count_only_active_project_records(self):
        for route, model in DASHBOARDS:
            with self.subTest(route=route):
                self.make_item(model, route + '-Ghana')
                self.make_item(model, route + '-unknown', country='')
                self.make_item(model, route + '-inactive', country='Senegal', active=False)
                self.make_item(model, route + '-foreign', country='Nigeria', project=self.other_project)
                response = self.client.get(reverse(route, kwargs={'project_name': self.project.name}))

                self.assertEqual(response.status_code, 200)
                geography = response.context['geography_data']
                self.assertEqual(geography['summary']['total'], 2)
                self.assertEqual(geography['summary']['mapped'], 1)
                self.assertEqual(geography['summary']['unmapped'], 1)
                self.assertEqual(geography['summary']['ghana'], 1)
                self.assertEqual(geography['summary']['west_africa'], 1)
                self.assertEqual(geography['summary']['countries'], 1)
                self.assertEqual([country['code'] for country in geography['countries']], ['GHA'])
                markup = response.content.decode()
                self.assertLess(markup.index('id="dashboardGeography"'),
                                markup.index('id="dashboardPrimaryChart"'))
                self.assertContains(response, 'data-map-view="ghana"')
                self.assertContains(response, 'data-map-view="west-africa"')
                self.assertContains(response, 'data-map-view="africa"')
                self.assertContains(response, 'data/africa.geojson')
                self.assertContains(response, 'dashboard_map.js')

    def test_metadata_country_and_city_feed_sample_map_and_country_chart(self):
        self.make_item(Sample, 'METADATA-ORIGIN', country='', metadata={
            'Collection country': 'GH', 'Collection city': 'Kumasi',
        })
        response = self.client.get(reverse('dashboard_samples', kwargs={'project_name': self.project.name}))

        self.assertEqual(response.status_code, 200)
        geography = response.context['geography_data']
        self.assertEqual(geography['summary']['ghana'], 1)
        self.assertEqual(geography['summary']['unmapped'], 0)
        self.assertEqual(geography['countries'][0]['name'], 'Ghana')
        self.assertEqual(response.context['chart_data']['tertiary_labels'], ['Ghana'])
        self.assertEqual(response.context['chart_data']['tertiary_values'], [1])
        point = geography['locations'][0]
        self.assertAlmostEqual(point['latitude'], 6.691937, places=5)
        self.assertAlmostEqual(point['longitude'], -1.63196, places=5)
        self.assertEqual(point['precision'], 'city')

    def test_outsiders_cannot_read_geographical_data_for_any_dashboard(self):
        self.client.force_login(self.outsider)
        for route, _ in DASHBOARDS:
            with self.subTest(route=route):
                response = self.client.get(
                    reverse(route, kwargs={'project_name': self.project.name}),
                    HTTP_ACCEPT='application/json',
                )
                self.assertEqual(response.status_code, 403)
                self.assertNotContains(response, 'dashboard-geography-data', status_code=403)

    def test_location_payload_escapes_script_delimiters_and_remains_valid_json(self):
        unsafe_label = '</script><script>alert("origin")</script>'
        self.make_item(Sample, 'ESCAPED-ORIGIN', metadata={
            'Collection city': 'Accra', 'Collection site': unsafe_label,
        })
        response = self.client.get(reverse('dashboard_samples', kwargs={'project_name': self.project.name}))
        self.assertEqual(response.status_code, 200)
        markup = response.content.decode()
        match = re.search(r'<script id="dashboard-geography-data" type="application/json">(.*?)</script>',
                          markup, re.DOTALL)
        self.assertIsNotNone(match)
        payload = match.group(1)
        self.assertNotIn('<', payload)
        self.assertNotIn(unsafe_label, markup)
        parsed = json.loads(payload)
        self.assertEqual(parsed['summary']['mapped'], 1)
        self.assertEqual(parsed, response.context['geography_data'])


class VendorLocationWorkflowTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.manager = User.objects.create_user(username='vendor-map-manager')
        cls.outsider = User.objects.create_user(username='vendor-map-outsider')
        cls.project = Project.objects.create(name='Vendor Map Project', project_manager=cls.manager)

    def setUp(self):
        self.client.force_login(self.manager)

    def supply_data(self, name):
        return {
            'name': name, 'product_code': name, 'items_per_pack': 10,
            'pack_count': 3, 'expiry_date': (timezone.localdate() + timedelta(days=30)).isoformat(),
            'storage_location': 'Local stockroom', 'cold_storage': 'Room temperature',
            'storage_condition': 'Room temperature', 'oem_temperature': 20,
            'temperature_unit': 'C', 'vendor': 'Regional Lab Supplier',
            'vendor_country': 'Ghana', 'vendor_city': 'Accra',
            'country_of_origin': 'Germany', 'hazard_level': 0, 'threshold_value': 1,
        }

    def test_consumable_and_reagent_locations_survive_creation_edit_and_info(self):
        for kind, model in (('consumable', Consumable), ('reagent', Reagent)):
            with self.subTest(kind=kind):
                response = self.client.post(
                    reverse('add_' + kind, kwargs={'project_name': self.project.name}),
                    self.supply_data('Mapped ' + kind),
                )
                self.assertEqual(response.status_code, 200, response.content)
                item = model.objects.get(pk=response.json()['id'])
                self.assertEqual((item.vendor_country, item.vendor_city), ('Ghana', 'Accra'))
                response = self.client.post(reverse('edit_' + kind, args=[item.pk]), {
                    'vendor_country': 'Senegal', 'vendor_city': 'Dakar',
                    'expiry_date': item.expiry_date.isoformat(),
                })
                self.assertEqual(response.status_code, 200, response.content)
                item.refresh_from_db()
                self.assertEqual((item.vendor_country, item.vendor_city), ('Senegal', 'Dakar'))
                info = self.client.get(reverse('get_' + kind + '_info', args=[item.pk]))
                self.assertEqual(info.status_code, 200, info.content)
                self.assertEqual(info.json()['vendor_country'], 'Senegal')
                self.assertEqual(info.json()['vendor_city'], 'Dakar')

    def test_equipment_location_and_existing_edit_fields_survive_info_and_update(self):
        data = {
            'name': 'Mapped centrifuge', 'equip_id': 'MAP-EQ-1', 'quantity': 2,
            'status': 'operational', 'source': 'Regional Supplier',
            'donated_by': 'Equipment Foundation', 'vendor_country': 'Ghana',
            'vendor_city': 'Accra', 'storage_location': 'Lab A',
        }
        response = self.client.post(reverse('add_equipment', kwargs={'project_name': self.project.name}), data)
        self.assertEqual(response.status_code, 200, response.content)
        equipment = Equipment.objects.get(pk=response.json()['id'])
        self.assertEqual((equipment.vendor_country, equipment.vendor_city), ('Ghana', 'Accra'))
        info = self.client.get(reverse('get_equipment_info', args=[equipment.pk]))
        self.assertEqual(info.status_code, 200, info.content)
        self.assertEqual(info.json()['quantity'], 2)
        self.assertEqual(info.json()['donated_by'], 'Equipment Foundation')
        self.assertEqual(info.json()['source'], 'Regional Supplier')
        self.assertEqual(info.json()['vendor_country'], 'Ghana')
        self.assertEqual(info.json()['vendor_city'], 'Accra')
        edited = self.client.post(reverse('edit_equipment', args=[equipment.pk]), {
            'vendor_country': 'Nigeria', 'vendor_city': 'Lagos',
        })
        self.assertEqual(edited.status_code, 200, edited.content)
        equipment.refresh_from_db()
        self.assertEqual((equipment.vendor_country, equipment.vendor_city), ('Nigeria', 'Lagos'))
        self.assertEqual(equipment.quantity, 2)
        self.assertEqual(equipment.donated_by, 'Equipment Foundation')
        self.client.force_login(self.outsider)
        denied = self.client.get(reverse('get_equipment_info', args=[equipment.pk]))
        self.assertEqual(denied.status_code, 403)

    def test_inventory_add_and_edit_forms_expose_optional_vendor_locations(self):
        for route in ('consumables', 'reagents', 'equipment_'):
            with self.subTest(route=route):
                response = self.client.get(reverse(route, kwargs={'project_name': self.project.name}))
                self.assertEqual(response.status_code, 200)
                self.assertContains(response, 'name="vendor_country"', count=2)
                self.assertContains(response, 'name="vendor_city"', count=2)
                self.assertContains(response, 'Vendor delivery country (optional)')
                self.assertContains(response, 'Vendor delivery city (optional)')

    def test_supply_csv_exports_keep_vendor_origins(self):
        for kind, model in (('consumable', Consumable), ('reagent', Reagent)):
            with self.subTest(kind=kind):
                model.objects.create(project=self.project, name='Export ' + kind,
                                     items_per_pack=10, items_left_in_pack=10,
                                     cold_storage='Room temperature', vendor='Vendor A',
                                     vendor_country='Ghana', vendor_city='Accra')
                response = self.client.get(reverse('export_' + kind + '_csv', kwargs={'project_name': self.project.name}))
                self.assertEqual(response.status_code, 200, response.content)
                rows = list(csv.DictReader(io.StringIO(response.content.decode())))
                self.assertEqual(rows[0]['vendor_country'], 'Ghana')
                self.assertEqual(rows[0]['vendor_city'], 'Accra')

    def test_equipment_csv_exports_keep_vendor_origin_and_source(self):
        Equipment.objects.create(project=self.project, name='Export equipment',
                                 equip_id='MAP-EXPORT-EQ', source='Vendor A',
                                 vendor_country='Ghana', vendor_city='Accra')
        response = self.client.get(reverse('export_equipment_csv', kwargs={'project_name': self.project.name}))
        self.assertEqual(response.status_code, 200, response.content)
        rows = list(csv.DictReader(io.StringIO(response.content.decode())))
        self.assertEqual(rows[0]['vendor_country'], 'Ghana')
        self.assertEqual(rows[0]['vendor_city'], 'Accra')
        self.assertEqual(rows[0]['source'], 'Vendor A')

    def test_restoring_supply_and_equipment_archives_keeps_vendor_origins(self):
        today = timezone.localdate()
        for kind, model, archive_model in (
            ('consumable', Consumable, TrashConsumable),
            ('reagent', Reagent, TrashReagent),
            ('equipment', Equipment, TrashEquipment),
        ):
            with self.subTest(kind=kind):
                fields = dict(project=self.project, original_id='ARCHIVE-' + kind,
                              name='Archived ' + kind, vendor_country='Ghana', vendor_city='Accra')
                if kind == 'equipment':
                    fields.update(equip_id='ARCHIVE-EQ', date_installed=today,
                                  status='operational', source='Vendor A')
                else:
                    fields.update(items_per_pack=10, items_left_in_pack=10, pack_count=2,
                                  cold_storage='room', date_recorded=today)
                archived = archive_model.objects.create(**fields)
                response = self.client.post(reverse('restore_trash_' + kind, kwargs={
                    'project_name': self.project.name, 'trash_id': archived.pk,
                }))
                self.assertEqual(response.status_code, 200, response.content)
                restored = model.objects.get(name='Archived ' + kind)
                self.assertEqual((restored.vendor_country, restored.vendor_city), ('Ghana', 'Accra'))
                self.assertFalse(archive_model.objects.filter(pk=archived.pk).exists())

    def test_bulk_reagent_archive_preserves_vendor_origin(self):
        reagent = Reagent.objects.create(project=self.project, name='Bulk origin',
                                        items_per_pack=10, items_left_in_pack=10,
                                        cold_storage='room', country_of_origin='Germany',
                                        vendor_country='Ghana', vendor_city='Accra')
        response = self.client.post(reverse('bulk_delete_reagents', kwargs={'project_name': self.project.name}), {
            'reagent_ids': [reagent.pk],
        })
        self.assertEqual(response.status_code, 200, response.content)
        archived = TrashReagent.objects.get(original_id=reagent.pk)
        self.assertEqual((archived.vendor_country, archived.vendor_city), ('Ghana', 'Accra'))
