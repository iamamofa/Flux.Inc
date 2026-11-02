"""Sample inventory helpers shared by its views and exports."""
from datetime import date, datetime
from decimal import Decimal, InvalidOperation

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from .models import Box, Log, Sample, Sample_Locations, TrashSample
from .sample_metadata import normalize_sample_metadata


SAMPLE_FIELDS = (
    'sample_id', 'sample_type', 'collection_date', 'date_recorded', 'country',
    'volume', 'volume_unit', 'concentration', 'concentration_unit',
    'extraction_batch_number', 'grant_code', 'barcode_value', 'threshold_value',
    'is_active', 'notes',
)
LEGACY_METADATA = {
    'description': 'Description', 'storage_location': 'Storage location',
    'cold_storage_id': 'Cold storage ID',
    'storage_temperature': 'Storage temperature (°C)',
}
LOCATION_PREFETCH = 'sample_locations__box__rack__shelf__storage'


def can_read_samples(user, project):
    return (
        project.project_manager_id == user.pk
        or project.project_editors.filter(pk=user.pk).exists()
        or project.project_members.filter(pk=user.pk).exists()
    )


def can_edit_samples(user, project):
    return project.project_manager_id == user.pk or project.project_editors.filter(pk=user.pk).exists()


def sample_queryset():
    return Sample.objects.select_related('project').prefetch_related(LOCATION_PREFETCH)


def metadata_value(metadata, key, default=''):
    return next((value for name, value in metadata.items() if name.casefold() == key.casefold()), default)


def serialize_sample(sample):
    data = {field: getattr(sample, field) for field in SAMPLE_FIELDS}
    data.update({
        'id': sample.pk, 'metadata': sample.metadata,
        'description': metadata_value(sample.metadata, 'Description'),
        'storage_location': sample.storage_location,
        'cold_storage_id': sample.cold_storage_id,
        'storage_temperature': sample.storage_temperature,
        'well_id': sample.well_id,
        'shelf': sample.shelf.pk if sample.shelf else '',
        'rack': sample.rack.pk if sample.rack else '',
        'box': sample.box.pk if sample.box else '',
        'shelf_name': sample.shelf.shelf_label if sample.shelf else '',
        'rack_name': sample.rack.rack_label if sample.rack else '',
        'box_name': sample.box.box_label if sample.box else '',
        'low_stock': sample.is_low_stock,
    })
    return data


def metadata_from_post(post, existing=None):
    metadata = normalize_sample_metadata(post['metadata']) if 'metadata' in post else dict(existing or {})
    for field, label in LEGACY_METADATA.items():
        if field not in post:
            continue
        key = next((name for name in metadata if name.casefold() == label.casefold()), label)
        value = post[field].strip()
        if value:
            metadata[key] = value
        else:
            metadata.pop(key, None)
    return normalize_sample_metadata(metadata)


def _decimal_value(value, label, optional=False):
    if value in (None, '') and optional:
        return None
    try:
        result = Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        raise ValidationError(f'{label} must be a number.')
    if not result.is_finite():
        raise ValidationError(f'{label} must be a finite number.')
    return result


def prepare_sample(post, project, sample=None):
    creating = sample is None
    sample = sample or Sample(project=project)
    for field in ('sample_id', 'sample_type', 'country', 'volume_unit', 'concentration_unit',
                  'extraction_batch_number', 'grant_code', 'notes'):
        if field in post:
            setattr(sample, field, post[field].strip())
    if post.get('sample_type') == 'other' and post.get('sample_type_other'):
        sample.sample_type = post['sample_type_other'].strip()
    if 'barcode_value' in post:
        sample.barcode_value = post['barcode_value'].strip() or None
    if creating or 'volume' in post:
        sample.volume = _decimal_value(post.get('volume'), 'Volume')
    if 'concentration' in post:
        sample.concentration = _decimal_value(post['concentration'], 'Concentration', optional=True)
    if 'collection_date' in post or creating:
        try:
            sample.collection_date = date.fromisoformat(post.get('collection_date', ''))
        except (ValueError, TypeError):
            raise ValidationError('Choose a valid collection date.')
    if 'threshold_value' in post:
        try:
            sample.threshold_value = int(post['threshold_value']) if post['threshold_value'] else None
        except (ValueError, TypeError):
            raise ValidationError('The volume threshold must be a whole number.')
    if 'is_active' in post:
        sample.is_active = str(post['is_active']).lower() in ('true', '1', 'on', 'yes')
    sample.metadata = metadata_from_post(post, sample.metadata)
    sample.clean_fields(exclude=('country', 'notes', 'date_recorded'))
    sample.clean()
    sample.validate_unique()
    return sample


def resolve_sample_box(post, project):
    """Resolve an existing box and validate each supplied parent selection."""
    if any(post.get(field) == 'new' for field in ('shelf', 'rack', 'box')):
        raise ValidationError('Create the storage location first, then select its box.')
    box_id = post.get('box', '')
    if not box_id:
        if post.get('shelf') or post.get('rack'):
            raise ValidationError('Choose a box to save the sample’s storage location.')
        return None
    box = Box.objects.select_related('rack__shelf__storage').filter(
        pk=box_id, project__project_manager_id=project.project_manager_id,
        project__is_active=True,
    ).first()
    if box is None:
        raise ValidationError('Choose a storage box available to this project.')
    if post.get('rack') and post['rack'] != box.rack_id:
        raise ValidationError('The selected box does not belong to the selected rack.')
    if post.get('shelf') and post['shelf'] != box.rack.shelf_id:
        raise ValidationError('The selected box does not belong to the selected shelf.')
    return box


def save_sample_location(sample, post, box, creating=False):
    current = sample.current_location
    if not creating and 'box' not in post:
        box = current.box if current else None
    well = post.get('well_id', current.well_id if current else '').strip()
    if len(well) > 10:
        raise ValidationError('Well ID must contain at most 10 characters.')
    if not box:
        if well:
            key = next((name for name in sample.metadata if name.casefold() == 'well id'), 'Well ID')
            sample.metadata[key] = well
            sample.metadata = normalize_sample_metadata(sample.metadata)
            sample.save(update_fields=['metadata'])
        if creating or 'box' not in post:
            return
    if current and box and current.box_id == box.pk and current.well_id == well:
        return
    today = timezone.localdate()
    sample.sample_locations.filter(moved_out_at__isnull=True).update(moved_out_at=today)
    if box:
        Sample_Locations.objects.create(sample=sample, box=box, well_id=well, moved_in_at=today)
    sample.__dict__.pop('current_location', None)
    sample._prefetched_objects_cache = {}


def archive_sample(sample, user):
    """Keep the full sample and all storage history before removing live rows."""
    with transaction.atomic():
        sample = sample_queryset().select_for_update().get(pk=sample.pk)
        trash_fields = {field.name for field in TrashSample._meta.fields}
        values = {
            field.name: getattr(sample, field.name)
            for field in Sample._meta.fields
            if field.name in trash_fields and field.name not in ('id', 'project')
        }
        values['country'] = values.get('country') or ''
        history = [
            {'id': location.pk, 'box_id': location.box_id, 'well_id': location.well_id,
             'moved_in_at': location.moved_in_at.isoformat(),
             'moved_out_at': location.moved_out_at.isoformat() if location.moved_out_at else None}
            for location in sample.sample_locations.all()
        ]
        TrashSample.objects.create(
            project=sample.project, original_id=sample.pk, deleted_by=user,
            shelf=sample.shelf, rack=sample.rack, box=sample.box,
            well_id=sample.well_id, storage_location=sample.storage_location,
            cold_storage_id=sample.cold_storage_id,
            location_history=history, **values,
        )
        sample.sample_locations.all().delete()
        sample.delete()
        Log.objects.create(project=sample.project, user=user, action=f'Moved sample {sample.sample_id} to trash')


def restore_archived_sample(archived, user):
    if not archived.collection_date:
        raise ValidationError('This archived sample is missing its collection date and cannot be restored.')
    if archived.volume is None:
        raise ValidationError('This archived sample is missing its volume and cannot be restored.')
    with transaction.atomic():
        archived = TrashSample.objects.select_for_update().get(pk=archived.pk)
        fields = {field.name for field in Sample._meta.fields}
        values = {
            field.name: getattr(archived, field.name)
            for field in TrashSample._meta.fields
            if field.name in fields and field.name not in ('id', 'project')
        }
        sample = Sample.objects.create(id=archived.original_id, project=archived.project, **values)
        Sample.objects.filter(pk=sample.pk).update(date_recorded=archived.date_recorded)
        history = archived.location_history
        if not history and archived.box_id:
            history = [{'box_id': archived.box_id, 'well_id': archived.well_id or '',
                        'moved_in_at': timezone.localdate().isoformat(), 'moved_out_at': None}]
        for location in history:
            if not Box.objects.filter(pk=location['box_id']).exists():
                raise ValidationError('An archived storage box is unavailable; restore its storage location before this sample.')
            data = {'sample': sample, 'box_id': location['box_id'], 'well_id': location['well_id'],
                    'moved_in_at': location['moved_in_at'], 'moved_out_at': location['moved_out_at']}
            if location.get('id'):
                data['id'] = location['id']
            Sample_Locations.objects.create(**data)
        archived.delete()
        Log.objects.create(project=sample.project, user=user, action=f'Restored sample {sample.sample_id} from trash')
        sample.refresh_from_db()
        return sample


def sample_export_rows(project):
    samples = list(sample_queryset().filter(project=project, is_active=True))
    canonical_keys = {}
    for sample in samples:
        for key in sample.metadata:
            canonical_keys.setdefault(key.casefold(), key)
    keys = sorted(canonical_keys.values(), key=str.casefold)
    storage_fields = ('storage_location', 'cold_storage_id', 'storage_temperature',
                      'shelf_name', 'rack_name', 'box_name', 'well_id')
    fields = (*SAMPLE_FIELDS, *storage_fields)
    headers = list(fields) + [f'Metadata: {key}' for key in keys]
    rows = []
    for sample in samples:
        serialized = serialize_sample(sample)
        values = [serialized[field] for field in fields]
        values.extend(metadata_value(sample.metadata, key) for key in keys)
        rows.append([value.isoformat() if isinstance(value, (datetime, date)) else value for value in values])
    return headers, rows


def csv_literal(value):
    if isinstance(value, str) and (value.startswith(('\t', '\r', '\n')) or value.lstrip().startswith(('=', '+', '-', '@'))):
        return "'" + value
    return value
