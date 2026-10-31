"""Small, project-scoped tools for genomics operations."""
import csv
import io
import uuid
from datetime import datetime
from decimal import Decimal, InvalidOperation
from datetime import timedelta

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.text import slugify
from django.views.decorators.http import require_http_methods, require_POST
from openpyxl import Workbook, load_workbook
from openpyxl.styles import Alignment, Font, PatternFill

from .models import (
    BaseInventoryItem, BulkImportJob, Consumable, Equipment, EquipmentBooking, Plate, PlateWell,
    ProcurementRequest, Project, Reagent, Sample, StorageTemperatureEvent,
)
from .views import get_sidebar_urls
from .cold_chain import build_cold_chain_audit, parse_audit_window, render_cold_chain_pdf, storage_unit_choices


IMPORT_COLUMNS = [
    'name', 'product_code', 'items_per_pack', 'items_left_in_pack', 'pack_count',
    'cold_storage', 'storage_condition', 'lot_number', 'extraction_batch_number',
    'expiry_date', 'grant_code', 'average_daily_use', 'par_stock', 'hazard_level',
    'country_of_origin',
]
MULTI_IMPORT_COLUMNS = ['project_name', *IMPORT_COLUMNS]


def _access(project, user):
    if not (project.project_manager_id == user.pk or project.project_editors.filter(pk=user.pk).exists()
            or project.project_members.filter(pk=user.pk).exists()):
        raise PermissionDenied('You do not have access to this project.')


def _barcode_svg(value, label):
    value = str(value)
    bars = ''.join(f'<rect x="{20 + index * 4}" y="25" width="{2 if bit == "1" else 1}" height="100"/>'
                   for index, bit in enumerate(''.join(f'{ord(char):08b}' for char in value)))
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="420" height="190" viewBox="0 0 420 190"><rect width="420" height="190" fill="white"/><g fill="#111">{bars}</g><text x="20" y="155" font-family="Arial" font-size="16">{label}</text><text x="20" y="178" font-family="monospace" font-size="13">{value}</text></svg>'''


@login_required
def genomics_hub(request, project_name):
    project = get_object_or_404(Project, name=project_name)
    _access(project, request.user)
    today = timezone.localdate()
    qs = list(Reagent.objects.filter(project=project, is_active=True)) + list(Consumable.objects.filter(project=project, is_active=True))
    expiry = {
        'expiring_30': [item for item in qs if item.expiry_date and today <= item.expiry_date <= today + timedelta(days=30)],
        'expiring_60': [item for item in qs if item.expiry_date and today <= item.expiry_date <= today + timedelta(days=60)],
        'expiring_90': [item for item in qs if item.expiry_date and today <= item.expiry_date <= today + timedelta(days=90)],
    }
    runway = [item for item in qs if item.days_of_stock_remaining is not None and item.days_of_stock_remaining <= 30]
    context = {
        'project': project, 'expiry': expiry, 'runway': runway,
        'procurement_requests': project.procurement_requests.select_related('requested_by').order_by('-created_at')[:20],
        'bookings': project.equipment_bookings.select_related('equipment', 'booked_by').filter(ends_at__gte=timezone.now())[:30],
        'plates': project.plates.order_by('-created_at')[:20],
        'equipment': Equipment.objects.filter(project=project, is_active=True),
        'today': today, **get_sidebar_urls(project.name),
    }
    return render(request, 'inventory/genomics_hub.html', context)


@login_required
def cold_chain_audit(request, project_name):
    project = get_object_or_404(Project, name=project_name)
    if project.project_manager_id != request.user.pk:
        raise PermissionDenied('Only the project manager can export a cold-chain audit.')
    start_value = request.GET.get('from', '')
    end_value = request.GET.get('to', '')
    storage_unit = request.GET.get('storage_unit', '').strip()[:100]
    audit = None
    error = ''
    if storage_unit and start_value and end_value:
        start, end, error = parse_audit_window(start_value, end_value)
        if not error:
            audit = build_cold_chain_audit(storage_unit=storage_unit, start=start, end=end, project_id=project.pk)
            if request.GET.get('format') == 'pdf':
                from .models import Log
                Log.objects.create(project=project, user=request.user, action='Cold-chain audit exported', details={'storage_unit': storage_unit, 'from': start.isoformat(), 'to': end.isoformat()})
                try:
                    pdf_bytes = render_cold_chain_pdf(audit, generated_by=request.user)
                except RuntimeError as exc:
                    return HttpResponse(str(exc), status=503)
                response = HttpResponse(pdf_bytes, content_type='application/pdf')
                response['Content-Disposition'] = f'attachment; filename="flux-cold-chain-{slugify(project.name)[:40] or "project"}.pdf"'
                return response
    elif any((storage_unit, start_value, end_value)):
        error = 'Choose a storage unit, start time and end time to build the evidence package.'
    now = timezone.localtime()
    return render(request, 'inventory/cold_chain_audit.html', {
        'project': project, 'audit': audit, 'error': error, 'storage_unit': storage_unit,
        'storage_units': storage_unit_choices(project.pk), 'from_value': start_value or (now - timedelta(hours=24)).strftime('%Y-%m-%dT%H:%M'),
        'to_value': end_value or now.strftime('%Y-%m-%dT%H:%M'), **get_sidebar_urls(project.name),
    })


@login_required
def barcode_label(request, project_name, item_type, item_id):
    project = get_object_or_404(Project, name=project_name)
    _access(project, request.user)
    model = {'reagent': Reagent, 'consumable': Consumable, 'sample': Sample, 'equipment': Equipment}.get(item_type)
    if model is None:
        return HttpResponse('Unknown label type', status=400)
    item = get_object_or_404(model, pk=item_id, project=project)
    value = getattr(item, 'barcode_value', None) or f'FLUX-{item_type.upper()}-{item.pk}'
    return HttpResponse(_barcode_svg(value, getattr(item, 'name', getattr(item, 'sample_id', str(item)))), content_type='image/svg+xml')


@login_required
def barcode_scanner(request, project_name):
    project = get_object_or_404(Project, name=project_name)
    _access(project, request.user)
    return render(request, 'inventory/barcode_scanner.html', {'project': project, **get_sidebar_urls(project.name)})


def _template_response(columns, filename, file_format):
    """Return a polished, empty import template with a separate instruction sheet."""
    if file_format == 'csv':
        output = io.StringIO(newline='')
        csv.writer(output).writerow(columns)
        response = HttpResponse(output.getvalue(), content_type='text/csv; charset=utf-8')
    else:
        workbook = Workbook()
        sheet = workbook.active
        sheet.title = 'Reagents'
        sheet.append(columns)
        header_fill = PatternFill('solid', fgColor='D14D0B')
        for cell in sheet[1]:
            cell.font = Font(bold=True, color='FFFFFF')
            cell.fill = header_fill
            cell.alignment = Alignment(horizontal='center')
        sheet.freeze_panes = 'A2'
        sheet.auto_filter.ref = sheet.dimensions
        for index, column in enumerate(columns, start=1):
            sheet.column_dimensions[chr(64 + index) if index <= 26 else 'A'].width = max(16, len(column) + 3)
        instructions = workbook.create_sheet('Instructions')
        instructions.append(['Flux import template', 'How to use this file'])
        instructions.append(['Required', 'name, items_per_pack, pack_count'])
        instructions.append(['Dates', 'Use YYYY-MM-DD for expiry_date'])
        instructions.append(['Storage', 'Use room, 4c, minus20, minus80 or ln2'])
        instructions.append(['Multi-project files', 'Include the exact project name in project_name'])
        instructions.append(['Tip', 'Leave optional cells blank; do not rename the column headers'])
        instructions.column_dimensions['A'].width = 24
        instructions.column_dimensions['B'].width = 78
        instructions.freeze_panes = 'A2'
        for cell in instructions[1]:
            cell.font = Font(bold=True, color='FFFFFF')
            cell.fill = header_fill
        buffer = io.BytesIO()
        workbook.save(buffer)
        response = HttpResponse(buffer.getvalue(), content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response


@login_required
def bulk_import_template(request, project_name, file_format, scope='single'):
    project = get_object_or_404(Project, name=project_name)
    _access(project, request.user)
    file_format = file_format.lower()
    if file_format not in {'csv', 'xlsx'} or scope not in {'single', 'multi'}:
        return HttpResponse('Unknown template format.', status=400)
    columns = MULTI_IMPORT_COLUMNS if scope == 'multi' else IMPORT_COLUMNS
    return _template_response(columns, f'flux-reagents-{scope}-project-template.{file_format}', file_format)


@login_required
def bulk_import_template_multi(request, project_name, file_format):
    return bulk_import_template(request, project_name, file_format, scope='multi')


@login_required
@require_POST
def barcode_scan(request, project_name):
    project = get_object_or_404(Project, name=project_name)
    _access(project, request.user)
    code = request.POST.get('code', '').strip()[:120]
    action = request.POST.get('action', 'check_in')
    from .models import Log
    Log.objects.create(project=project, user=request.user, action=f'Barcode {action}: {code}', details={'barcode': code, 'action': action})
    return HttpResponse('Recorded')


@login_required
@require_POST
def procurement_request(request, project_name):
    project = get_object_or_404(Project, name=project_name)
    _access(project, request.user)
    ProcurementRequest.objects.create(
        project=project, requested_by=request.user,
        item_name=request.POST.get('item_name', '').strip()[:150],
        product_code=request.POST.get('product_code', '').strip()[:100],
        quantity=max(int(request.POST.get('quantity', 1) or 1), 1),
        grant_code=request.POST.get('grant_code', '').strip()[:100],
        justification=request.POST.get('justification', '').strip()[:1000],
    )
    return redirect('genomics_hub', project_name=project.name)


@login_required
@require_POST
def record_temperature(request, project_name):
    project = get_object_or_404(Project, name=project_name)
    _access(project, request.user)
    value = float(request.POST.get('temperature', 0))
    condition = request.POST.get('storage_condition', 'room')
    critical = {'minus80': -60, 'minus20': -10, '4c': 12, 'ln2': -150}.get(condition)
    alert = 'critical' if critical is not None and value > critical else 'normal'
    StorageTemperatureEvent.objects.create(
        project=project, item_type=request.POST.get('item_type', 'storage'),
        item_id=request.POST.get('item_id', ''), temperature=value,
        temperature_unit=request.POST.get('temperature_unit', 'C'),
        storage_condition=condition, recorded_by=request.user, alert_level=alert,
    )
    return redirect('genomics_hub', project_name=project.name)


@login_required
@require_POST
def equipment_booking(request, project_name):
    project = get_object_or_404(Project, name=project_name)
    _access(project, request.user)
    start = timezone.make_aware(timezone.datetime.fromisoformat(request.POST['starts_at']))
    end = timezone.make_aware(timezone.datetime.fromisoformat(request.POST['ends_at']))
    equipment = get_object_or_404(Equipment, pk=request.POST['equipment_id'], project=project)
    if end <= start or EquipmentBooking.objects.filter(equipment=equipment, status__in=['requested', 'approved'], starts_at__lt=end, ends_at__gt=start).exists():
        return HttpResponse('That equipment slot is unavailable.', status=409)
    EquipmentBooking.objects.create(project=project, equipment=equipment, booked_by=request.user, starts_at=start, ends_at=end, purpose=request.POST.get('purpose', '')[:500])
    return redirect('genomics_hub', project_name=project.name)


@login_required
@require_http_methods(['GET', 'POST'])
def plate_visualizer(request, project_name, plate_id=None):
    project = get_object_or_404(Project, name=project_name)
    _access(project, request.user)
    if request.method == 'POST':
        plate = get_object_or_404(Plate, pk=plate_id, project=project)
        PlateWell.objects.update_or_create(plate=plate, coordinate=request.POST['coordinate'].upper(), defaults={'label': request.POST.get('label', '')[:150], 'notes': request.POST.get('notes', '')[:500]})
        return redirect('plate_visualizer', project_name=project.name, plate_id=plate.pk)
    plate = get_object_or_404(Plate, pk=plate_id, project=project) if plate_id else Plate.objects.create(project=project, name='New plate', plate_type='96', barcode_value=f'FLUX-PLATE-{uuid.uuid4().hex[:10].upper()}', created_by=request.user)
    rows = 'ABCDEFGH' if plate.plate_type == '96' else 'ABCDEFGHIJKLMNOP'
    columns = range(1, 13 if plate.plate_type == '96' else 25)
    wells = {well.coordinate: well for well in plate.wells.all()}
    cells = [[(f'{row}{column}', wells.get(f'{row}{column}')) for column in columns] for row in rows]
    return render(request, 'inventory/plate_visualizer.html', {'project': project, 'plate': plate, 'rows': rows, 'columns': columns, 'cells': cells, **get_sidebar_urls(project.name)})


@login_required
@require_POST
def bulk_import_reagents(request, project_name):
    project = get_object_or_404(Project, name=project_name)
    if project.project_manager_id != request.user.pk:
        raise PermissionDenied('Only the project manager can import inventory.')
    upload = request.FILES.get('file')
    if not upload:
        return HttpResponse('Upload a CSV or XLSX file.', status=400)
    job = BulkImportJob.objects.create(project=project, uploaded_by=request.user, filename=upload.name)
    try:
        rows = _read_import_rows(upload)
        imported = 0
        for row in rows:
            name = _row_value(row, 'name')
            if not name:
                continue
            Reagent.objects.create(project=project, **_reagent_fields(row))
            imported += 1
        job.row_count, job.imported_count, job.status = len(rows), imported, 'imported'
        job.save(update_fields=['row_count', 'imported_count', 'status'])
    except Exception as exc:
        job.status, job.error_report = 'failed', str(exc)
        job.save(update_fields=['status', 'error_report'])
        return HttpResponse(f'Import failed: {exc}', status=400)
    return redirect('genomics_hub', project_name=project.name)


def _normalise_header(value):
    return ''.join(char.lower() if char.isalnum() else '_' for char in str(value or '').strip()).strip('_')


def _read_import_rows(upload):
    if upload.name.lower().endswith('.csv'):
        raw = upload.read()
        if isinstance(raw, bytes):
            raw = raw.decode('utf-8-sig')
        return [{_normalise_header(key): value for key, value in row.items()} for row in csv.DictReader(io.StringIO(raw))]
    workbook = load_workbook(upload, read_only=True, data_only=True)
    sheet = workbook['Reagents'] if 'Reagents' in workbook.sheetnames else workbook.active
    values = list(sheet.values)
    if not values:
        return []
    headers = [_normalise_header(value) for value in values[0]]
    return [dict(zip(headers, row)) for row in values[1:] if any(value not in (None, '') for value in row)]


def _row_value(row, key):
    return str(row.get(key) or '').strip()


def _safe_int(value, default=0, minimum=0, maximum=None):
    try:
        parsed = int(float(str(value).strip())) if str(value).strip() else default
    except (TypeError, ValueError):
        parsed = default
    parsed = max(parsed, minimum)
    return min(parsed, maximum) if maximum is not None else parsed


def _reagent_fields(row):
    items_per_pack = _safe_int(row.get('items_per_pack'), 1, minimum=1)
    storage_condition = _row_value(row, 'storage_condition') or 'room'
    if storage_condition not in dict(BaseInventoryItem.STORAGE_CONDITIONS):
        storage_condition = 'room'
    expiry_date = None
    raw_expiry = row.get('expiry_date')
    if raw_expiry:
        if hasattr(raw_expiry, 'date'):
            expiry_date = raw_expiry.date()
        else:
            for date_format in ('%Y-%m-%d', '%d/%m/%Y', '%m/%d/%Y'):
                try:
                    expiry_date = datetime.strptime(str(raw_expiry).strip(), date_format).date()
                    break
                except ValueError:
                    continue
    average_daily_use = None
    raw_average = _row_value(row, 'average_daily_use')
    if raw_average:
        try:
            average_daily_use = Decimal(raw_average)
        except InvalidOperation:
            average_daily_use = None
    return {
        'name': _row_value(row, 'name')[:100],
        'product_code': _row_value(row, 'product_code')[:100],
        'items_per_pack': items_per_pack,
        'items_left_in_pack': min(_safe_int(row.get('items_left_in_pack'), items_per_pack, minimum=0), items_per_pack),
        'pack_count': _safe_int(row.get('pack_count'), 1, minimum=0),
        'cold_storage': (_row_value(row, 'cold_storage') or 'Ambient')[:50],
        'storage_condition': storage_condition,
        'lot_number': _row_value(row, 'lot_number')[:100],
        'extraction_batch_number': _row_value(row, 'extraction_batch_number')[:100],
        'expiry_date': expiry_date,
        'grant_code': _row_value(row, 'grant_code')[:100],
        'average_daily_use': average_daily_use,
        'par_stock': _safe_int(row.get('par_stock'), 0, minimum=0) or None,
        'hazard_level': _safe_int(row.get('hazard_level'), 0, minimum=0, maximum=4) or None,
        'country_of_origin': _row_value(row, 'country_of_origin')[:100],
    }


@login_required
@require_POST
def bulk_import_reagents_multi(request, project_name):
    """Import a multi-project workbook for projects managed by the current user."""
    context_project = get_object_or_404(Project, name=project_name)
    if context_project.project_manager_id != request.user.pk:
        raise PermissionDenied('Only a project manager can run a multi-project import.')
    upload = request.FILES.get('file')
    if not upload:
        return HttpResponse('Upload a CSV or XLSX file.', status=400)
    job = BulkImportJob.objects.create(project=context_project, uploaded_by=request.user, filename=upload.name)
    allowed_projects = {project.name.casefold(): project for project in Project.objects.filter(project_manager=request.user, is_active=True)}
    errors = []
    imported = 0
    try:
        rows = _read_import_rows(upload)
        for row_number, row in enumerate(rows, start=2):
            target_name = _row_value(row, 'project_name')
            target_project = allowed_projects.get(target_name.casefold())
            if not target_project:
                errors.append(f'Row {row_number}: project_name must match one of your active projects.')
                continue
            if not _row_value(row, 'name'):
                errors.append(f'Row {row_number}: name is required.')
                continue
            Reagent.objects.create(project=target_project, **_reagent_fields(row))
            imported += 1
        job.row_count, job.imported_count = len(rows), imported
        job.status = 'imported' if not errors else 'failed'
        job.error_report = '\n'.join(errors)[:5000]
        job.save(update_fields=['row_count', 'imported_count', 'status', 'error_report'])
    except Exception as exc:
        job.status, job.error_report = 'failed', str(exc)
        job.save(update_fields=['status', 'error_report'])
        return HttpResponse(f'Import failed: {exc}', status=400)
    return redirect('genomics_hub', project_name=context_project.name)
