"""Project sample metadata persists, stays scoped, and can be reused as a dataset."""
import csv
from datetime import timedelta
from decimal import Decimal
import io
import json
import zipfile

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.test import SimpleTestCase, TestCase
from django.urls import reverse
from django.utils import timezone
from openpyxl import load_workbook

from .models import Box, Project, Rack, Rooms, Sample, Sample_Locations, Shelf, Storages, TrashSample
from .sample_metadata import normalize_sample_metadata


class SampleMetadataValidationTests(SimpleTestCase):
    def test_metadata_normalizes_names_and_preserves_text_values(self):
        self.assertEqual(
            normalize_sample_metadata(json.dumps({
                ' Study ID ': 'Study-001',
                'Collection site': 'Accra & Kumasi',
                'Notes': '<b>Keep as text</b>',
            })),
            {
                'Study ID': 'Study-001',
                'Collection site': 'Accra & Kumasi',
                'Notes': '<b>Keep as text</b>',
            },
        )
        self.assertEqual(normalize_sample_metadata({}), {})

    def test_metadata_rejects_invalid_shapes_and_duplicate_names(self):
        invalid_values = [
            'not JSON',
            '[]',
            'null',
            {'': 'Unnamed'},
            {'   ': 'Unnamed'},
            {'Study ID': 'A', ' study id ': 'B'},
            '{"Site": "A", "Site": "B"}',
            {'Nested': {'value': 'A'}},
            {'List': ['A']},
            {'Number': 3},
            {'Boolean': True},
            {'Empty': None},
        ]
        for value in invalid_values:
            with self.subTest(value=value), self.assertRaises(ValidationError):
                normalize_sample_metadata(value)

    def test_metadata_limits_bound_user_supplied_data(self):
        for value in (
            {f'Field {index}': 'Value' for index in range(51)},
            {'x' * 81: 'Value'},
            {'Field': 'x' * 2001},
        ):
            with self.subTest(value=value), self.assertRaises(ValidationError):
                normalize_sample_metadata(value)
        self.assertEqual(
            normalize_sample_metadata({'x' * 80: 'y' * 2000}),
            {'x' * 80: 'y' * 2000},
        )


class SampleMetadataTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.manager = User.objects.create_user(username='sample-manager')
        cls.editor = User.objects.create_user(username='sample-editor')
        cls.member = User.objects.create_user(username='sample-member')
        cls.outsider = User.objects.create_user(username='sample-outsider')
        cls.project = Project.objects.create(
            name='Sample metadata project', project_manager=cls.manager,
        )
        cls.project.project_editors.add(cls.editor)
        cls.project.project_members.add(cls.member)
        cls.other_project = Project.objects.create(
            name='Private sample project', project_manager=cls.outsider,
        )
        cls.sample = Sample.objects.create(
            project=cls.project,
            sample_id='SAMPLE-001', sample_type='Blood', country='Ghana',
            collection_date=timezone.localdate() - timedelta(days=1),
            volume=Decimal('10.00'), volume_unit='mL',
            concentration=Decimal('2.50'), concentration_unit='ng/µL',
            threshold_value=1, notes='Original notes',
            extraction_batch_number='BATCH-1', grant_code='GRANT-1',
            barcode_value='SAMPLE-BARCODE-001',
            metadata={'Study ID': 'STUDY-1', 'Collection site': 'Accra'},
        )

    def setUp(self):
        self.client.force_login(self.manager)

    def project_url(self, route, **kwargs):
        return reverse(route, kwargs={'project_name': self.project.name, **kwargs})

    def metadata_url(self, sample=None):
        return self.project_url('sample_metadata', sample_id=(sample or self.sample).pk)

    def sample_data(self, **kwargs):
        return {
            'sample_id': 'SAMPLE-NEW', 'sample_type': 'Blood', 'country': 'Ghana',
            'collection_date': (timezone.localdate() - timedelta(days=1)).isoformat(),
            'volume': '12.5', 'volume_unit': 'mL', 'concentration': '2.5',
            'concentration_unit': 'ng/µL', 'threshold_value': '1', 'notes': '',
            **kwargs,
        }

    def test_create_sample_persists_metadata_and_optional_metadata_defaults_empty(self):
        response = self.client.post(self.project_url('add_sample'), self.sample_data(
            metadata=json.dumps({' Study ID ': 'STUDY-2', 'Collection site': 'Kumasi'}),
        ))
        self.assertEqual(response.status_code, 200, response.content)
        sample = Sample.objects.get(sample_id='SAMPLE-NEW')
        self.assertEqual(sample.metadata, {'Study ID': 'STUDY-2', 'Collection site': 'Kumasi'})
        response = self.client.post(self.project_url('add_sample'), self.sample_data(
            sample_id='SAMPLE-WITHOUT-METADATA',
        ))
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(Sample.objects.get(sample_id='SAMPLE-WITHOUT-METADATA').metadata, {})

    def test_invalid_create_metadata_does_not_create_a_sample(self):
        response = self.client.post(self.project_url('add_sample'), self.sample_data(
            metadata=json.dumps({'Study ID': {'nested': 'value'}}),
        ))
        self.assertEqual(response.status_code, 400, response.content)
        self.assertFalse(Sample.objects.filter(sample_id='SAMPLE-NEW').exists())

    def test_edit_preserves_omitted_metadata_and_can_replace_or_clear_it(self):
        url = reverse('edit_sample', kwargs={'sample_id': self.sample.pk})
        for payload, expected in (
            ({'notes': 'Updated notes'}, self.sample.metadata),
            ({'metadata': json.dumps({'Study ID': 'STUDY-UPDATED'})}, {'Study ID': 'STUDY-UPDATED'}),
            ({'metadata': '{}'}, {}),
        ):
            with self.subTest(payload=payload):
                response = self.client.post(url, payload)
                self.assertEqual(response.status_code, 200, response.content)
                self.sample.refresh_from_db()
                self.assertEqual(self.sample.metadata, expected)
        self.assertEqual(self.sample.notes, 'Updated notes')
        self.assertEqual(self.sample.volume, Decimal('10.00'))
        self.assertEqual(self.sample.concentration, Decimal('2.50'))

    def test_invalid_edit_is_atomic_and_keeps_existing_metadata(self):
        response = self.client.post(reverse('edit_sample', kwargs={'sample_id': self.sample.pk}), {
            'notes': 'Should not be saved',
            'metadata': json.dumps({'Study ID': 'A', ' study id ': 'B'}),
        })
        self.assertEqual(response.status_code, 400, response.content)
        self.sample.refresh_from_db()
        self.assertEqual(self.sample.notes, 'Original notes')
        self.assertEqual(self.sample.metadata['Study ID'], 'STUDY-1')

    def test_team_can_read_sample_metadata_and_info(self):
        info_url = reverse('get_sample_info', kwargs={'id': self.sample.pk})
        for user in (self.manager, self.editor, self.member):
            with self.subTest(user=user.username):
                self.client.force_login(user)
                response = self.client.get(self.metadata_url())
                self.assertEqual(response.status_code, 200, response.content)
                self.assertEqual(response.json()['metadata'], self.sample.metadata)
                response = self.client.get(info_url)
                self.assertEqual(response.status_code, 200, response.content)
                self.assertEqual(response.json()['metadata'], self.sample.metadata)
                self.assertEqual(response.json()['sample_id'], self.sample.sample_id)
                self.assertEqual(response.json()['collection_date'], self.sample.collection_date.isoformat())

    def test_only_managers_and_editors_can_update_metadata(self):
        for user in (self.manager, self.editor):
            with self.subTest(user=user.username):
                self.client.force_login(user)
                response = self.client.post(self.metadata_url(), {'metadata': json.dumps({'Study ID': user.username})})
                self.assertEqual(response.status_code, 200, response.content)
                self.sample.refresh_from_db()
                self.assertEqual(self.sample.metadata, {'Study ID': user.username})
        self.client.force_login(self.member)
        response = self.client.post(self.metadata_url(), {'metadata': '{}'})
        self.assertEqual(response.status_code, 403, response.content)
        self.sample.refresh_from_db()
        self.assertEqual(self.sample.metadata, {'Study ID': self.editor.username})
        response = self.client.post(reverse('edit_sample', kwargs={'sample_id': self.sample.pk}), {'metadata': '{}'})
        self.assertEqual(response.status_code, 403, response.content)

    def test_outsiders_cannot_read_or_modify_project_sample_data(self):
        self.client.force_login(self.outsider)
        read_urls = [
            self.metadata_url(),
            reverse('get_sample_info', kwargs={'id': self.sample.pk}),
            self.project_url('samples'),
            self.project_url('export_sample_csv'),
            self.project_url('export_sample_excel'),
            self.project_url('export_sample_txt'),
        ]
        for url in read_urls:
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 403)
        self.assertEqual(self.client.post(self.metadata_url(), {'metadata': '{}'}).status_code, 403)
        self.assertEqual(self.client.post(self.project_url('add_sample'), self.sample_data()).status_code, 403)
        self.sample.refresh_from_db()
        self.assertEqual(self.sample.metadata['Study ID'], 'STUDY-1')

    def test_metadata_endpoint_validation_preserves_stored_values(self):
        response = self.client.post(self.metadata_url(), {'metadata': '["invalid"]'})
        self.assertEqual(response.status_code, 400, response.content)
        self.assertIn('error', response.json())
        self.sample.refresh_from_db()
        self.assertEqual(self.sample.metadata['Study ID'], 'STUDY-1')

    def test_csv_and_excel_export_reusable_aligned_metadata_columns(self):
        Sample.objects.create(
            project=self.project, sample_id='SAMPLE-002', sample_type='Blood',
            collection_date=self.sample.collection_date, volume=4, notes='',
            metadata={'Study ID': 'STUDY-2', 'Custom field': 'Value, with comma'},
        )
        Sample.objects.create(
            project=self.other_project, sample_id='PRIVATE-SAMPLE', sample_type='Blood',
            collection_date=self.sample.collection_date, volume=4, notes='',
            metadata={'Secret key': 'Private value'},
        )
        Sample.objects.create(
            project=self.project, sample_id='INACTIVE-SAMPLE', sample_type='Blood',
            collection_date=self.sample.collection_date, volume=4, notes='', is_active=False,
            metadata={'Archived key': 'Archived value'},
        )
        csv_response = self.client.get(self.project_url('export_sample_csv'))
        self.assertEqual(csv_response.status_code, 200, csv_response.content)
        csv_rows = list(csv.reader(io.StringIO(csv_response.content.decode('utf-8-sig'))))
        excel_response = self.client.get(self.project_url('export_sample_excel'))
        self.assertEqual(excel_response.status_code, 200, excel_response.content)
        workbook = load_workbook(io.BytesIO(excel_response.content), data_only=True)
        excel_rows = list(workbook.active.values)
        self.assertEqual(csv_rows[0], list(excel_rows[0]))
        metadata_headers = [name for name in csv_rows[0] if name.startswith('Metadata: ')]
        self.assertEqual(set(metadata_headers), {'Metadata: Study ID', 'Metadata: Collection site', 'Metadata: Custom field'})
        self.assertEqual(len(csv_rows), 3)
        headers = csv_rows[0]
        sample_column = headers.index('sample_id') if 'sample_id' in headers else headers.index('Sample ID')
        rows = {row[sample_column]: row for row in csv_rows[1:]}
        self.assertEqual(rows['SAMPLE-001'][headers.index('Metadata: Collection site')], 'Accra')
        self.assertEqual(rows['SAMPLE-001'][headers.index('Metadata: Custom field')], '')
        self.assertEqual(rows['SAMPLE-002'][headers.index('Metadata: Custom field')], 'Value, with comma')
        self.assertEqual(rows['SAMPLE-002'][headers.index('Metadata: Collection site')], '')
        excel_by_sample = {row[sample_column]: row for row in excel_rows[1:]}
        self.assertEqual(excel_by_sample['SAMPLE-002'][headers.index('Metadata: Custom field')], 'Value, with comma')

    def test_text_export_and_project_backup_include_metadata(self):
        response = self.client.get(self.project_url('export_sample_txt'))
        self.assertEqual(response.status_code, 200, response.content)
        self.assertContains(response, 'Metadata: Study ID')
        self.assertContains(response, 'STUDY-1')
        self.client.force_login(self.member)
        response = self.client.get(self.project_url('export_project_backup'))
        self.assertEqual(response.status_code, 200)
        contents = b''.join(response.streaming_content)
        with zipfile.ZipFile(io.BytesIO(contents)) as backup:
            samples = json.loads(backup.read('data/samples.json'))
        self.assertEqual(len(samples), 1)
        self.assertEqual(samples[0]['fields']['metadata'], self.sample.metadata)

    def test_excel_metadata_is_literal_text_instead_of_a_formula(self):
        self.sample.metadata = {'Study ID': '=1+1'}
        self.sample.save(update_fields=['metadata'])
        response = self.client.get(self.project_url('export_sample_excel'))
        self.assertEqual(response.status_code, 200, response.content)
        workbook = load_workbook(io.BytesIO(response.content), data_only=False)
        sheet = workbook.active
        headers = [cell.value for cell in sheet[1]]
        metadata_cell = sheet.cell(row=2, column=headers.index('Metadata: Study ID') + 1)
        self.assertEqual(metadata_cell.value, '=1+1')
        self.assertEqual(metadata_cell.data_type, 's')

    def test_exports_align_field_name_case_and_include_storage_details(self):
        self.sample.metadata.update({'storage location': 'Freezer A', 'well id': 'B2'})
        self.sample.save(update_fields=['metadata'])
        Sample.objects.create(
            project=self.project, sample_id='SAMPLE-002', sample_type='Blood',
            collection_date=self.sample.collection_date, volume=4, notes='',
            metadata={'study id': 'STUDY-2'},
        )
        response = self.client.get(self.project_url('export_sample_csv'))
        self.assertEqual(response.status_code, 200, response.content)
        rows = list(csv.DictReader(io.StringIO(response.content.decode())))
        study_headers = [key for key in rows[0] if key.casefold() == 'metadata: study id']
        self.assertEqual(len(study_headers), 1)
        self.assertEqual(rows[0][study_headers[0]], 'STUDY-1')
        self.assertEqual(rows[1][study_headers[0]], 'STUDY-2')
        self.assertEqual(rows[0]['storage_location'], 'Freezer A')
        self.assertEqual(rows[0]['well_id'], 'B2')

    def test_archive_and_restore_preserve_metadata_and_actual_sample_fields(self):
        room = Rooms.objects.create(room_name='Lab', building='Research building')
        storage = Storages.objects.create(
            room_id=room, storage_name='Freezer', storage_type='Freezer', temperature=-20,
        )
        shelf = Shelf.objects.create(
            storage=storage, project=self.project, project_manager=self.manager,
            shelf_label='Shelf 1', notes='',
        )
        rack = Rack.objects.create(
            project=self.project, project_manager=self.manager, shelf=shelf,
            rack_label='Rack 1', capacity=10,
        )
        box = Box.objects.create(
            project=self.project, project_manager=self.manager, rack=rack,
            box_label='Box 1', notes='',
        )
        Sample_Locations.objects.create(
            sample=self.sample, box=box, well_id='A1', moved_in_at=self.sample.collection_date,
        )
        original_id = self.sample.pk
        original = {
            field: getattr(self.sample, field)
            for field in (
                'sample_id', 'sample_type', 'collection_date', 'volume', 'volume_unit',
                'concentration', 'concentration_unit', 'country', 'threshold_value',
                'notes', 'extraction_batch_number', 'grant_code', 'barcode_value', 'metadata',
            )
        }
        response = self.client.post(self.project_url('delete_sample', sample_id=original_id))
        self.assertEqual(response.status_code, 200, response.content)
        self.assertFalse(Sample.objects.filter(pk=original_id).exists())
        archived = TrashSample.objects.get(project=self.project, sample_id='SAMPLE-001')
        self.assertEqual(archived.metadata, original['metadata'])
        response = self.client.post(self.project_url('restore_trash_sample', trash_id=archived.pk))
        self.assertEqual(response.status_code, 200, response.content)
        restored = Sample.objects.get(project=self.project, sample_id='SAMPLE-001')
        for field, expected in original.items():
            with self.subTest(field=field):
                self.assertEqual(getattr(restored, field), expected)
        location = restored.sample_locations.get(moved_out_at__isnull=True)
        self.assertEqual(location.box_id, box.pk)
        self.assertEqual(location.well_id, 'A1')
        self.assertFalse(TrashSample.objects.filter(pk=archived.pk).exists())
