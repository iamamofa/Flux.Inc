"""Cold-chain excursion evidence collection and compliance PDF rendering."""
from datetime import datetime, time, timedelta
from io import BytesIO

from django.db.models import Q
from django.utils import timezone
try:
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_CENTER
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import mm
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
    REPORTLAB_IMPORT_ERROR = None
except ImportError as exc:  # Keep the server bootable if optional PDF dependencies are missing.
    REPORTLAB_IMPORT_ERROR = exc

from .models import (Consumable, Log, Project, Reagent, Sample_Locations,
                     Storages, StorageTemperatureEvent)


def _parse_window_value(value, end=False):
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value)
    except (TypeError, ValueError):
        try:
            parsed_date = datetime.strptime(value, '%Y-%m-%d').date()
        except (TypeError, ValueError):
            return None
        parsed = datetime.combine(parsed_date, time.max if end else time.min)
    if timezone.is_naive(parsed):
        parsed = timezone.make_aware(parsed)
    return parsed


def parse_audit_window(start_value, end_value):
    """Return an aware start/end pair, or a human-readable validation error."""
    start = _parse_window_value(start_value, end=False)
    end = _parse_window_value(end_value, end=True)
    if not start or not end:
        return None, None, 'Choose both a valid start and end time.'
    if start >= end:
        return None, None, 'The excursion end must be after the start.'
    return start, end, ''


def storage_unit_choices(project_id=None):
    """Return stable storage identifiers from the current data model."""
    values = set()
    events = StorageTemperatureEvent.objects.all()
    reagents = Reagent.objects.all()
    consumables = Consumable.objects.all()
    if project_id:
        events = events.filter(project_id=project_id)
        reagents = reagents.filter(project_id=project_id)
        consumables = consumables.filter(project_id=project_id)
    values.update(item.strip() for item in events.values_list('item_id', flat=True) if item and item.strip())
    values.update(item.strip() for item in reagents.values_list('storage_location', flat=True) if item and item.strip())
    values.update(item.strip() for item in consumables.values_list('storage_location', flat=True) if item and item.strip())
    values.update(item.strip() for item in Storages.objects.values_list('storage_name', flat=True) if item and item.strip())
    return sorted(values, key=str.casefold)


def _item_matches(project_filter, storage_unit):
    match = Q(storage_location__iexact=storage_unit) | Q(cold_storage__iexact=storage_unit)
    return match & project_filter


def build_cold_chain_audit(*, storage_unit, start, end, project_id=None):
    """Collect temperature, inventory, sample and audit evidence for an excursion."""
    projects = Project.objects.filter(is_active=True)
    if project_id:
        projects = projects.filter(pk=project_id)
    project_ids = list(projects.values_list('pk', flat=True))
    project_filter = Q(project_id__in=project_ids)
    events = list(StorageTemperatureEvent.objects.filter(
        project_filter, item_id__iexact=storage_unit, recorded_at__gte=start, recorded_at__lte=end
    ).select_related('project', 'recorded_by').order_by('recorded_at'))

    inventory = []
    item_filter = _item_matches(project_filter, storage_unit)
    for model, category in ((Reagent, 'Reagent'), (Consumable, 'Consumable')):
        for item in model.objects.filter(item_filter, is_active=True).select_related('project').order_by('project__name', 'name'):
            inventory.append({
                'category': category, 'project': item.project.name, 'name': item.name,
                'identifier': item.product_code or str(item.pk),
                'lot': item.lot_number or '-', 'batch': item.extraction_batch_number or '-',
                'quantity': f'{item.pack_count} pack(s) / {item.items_left_in_pack} left',
                'expiry': item.expiry_date.strftime('%Y-%m-%d') if item.expiry_date else 'Not recorded',
                'location': item.storage_location or item.cold_storage or '-',
            })

    location_filter = Q(box__rack__shelf__storage__storage_name__iexact=storage_unit) | Q(box__rack__shelf__storage__pk=storage_unit)
    location_filter &= Q(sample__project_id__in=project_ids)
    locations = (Sample_Locations.objects.filter(
        location_filter, moved_in_at__lte=end.date()
    ).filter(Q(moved_out_at__isnull=True) | Q(moved_out_at__gte=start.date()))
                  .select_related('sample', 'sample__project', 'box', 'box__rack', 'box__rack__shelf', 'box__rack__shelf__storage')
                  .order_by('sample__project__name', 'sample__sample_id', '-moved_in_at'))
    samples = []
    seen_samples = set()
    for location in locations:
        if location.sample_id in seen_samples:
            continue
        seen_samples.add(location.sample_id)
        sample = location.sample
        samples.append({
            'project': sample.project.name, 'sample_id': sample.sample_id,
            'sample_type': sample.sample_type or '-', 'volume': sample.volume_display,
            'batch': sample.extraction_batch_number or '-',
            'box': f'{location.box.rack.shelf.storage.storage_name} / {location.box.box_label} / {location.well_id or "Unassigned"}',
            'moved_in': location.moved_in_at.strftime('%Y-%m-%d') if location.moved_in_at else '-',
            'moved_out': location.moved_out_at.strftime('%Y-%m-%d') if location.moved_out_at else 'Still present',
        })

    logs = list(Log.objects.filter(
        Q(project_id__in=project_ids), timestamp__gte=start, timestamp__lte=end
    ).select_related('project', 'user').order_by('timestamp')[:200])
    critical_count = sum(1 for event in events if event.alert_level == 'critical')
    return {
        'storage_unit': storage_unit,
        'start': start,
        'end': end,
        'projects': list(projects.order_by('name')),
        'events': events,
        'inventory': inventory,
        'samples': samples,
        'logs': logs,
        'critical_count': critical_count,
        'project_count': len(project_ids),
        'inventory_count': len(inventory),
        'sample_count': len(samples),
        'log_count': len(logs),
    }


def _safe_text(value):
    return str(value if value not in (None, '') else '-').encode('ascii', 'replace').decode('ascii')


def _paragraph(value, style):
    return Paragraph(_safe_text(value).replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;'), style)


def render_cold_chain_pdf(audit, *, generated_by):
    """Render an audit package as a paginated, printable compliance PDF."""
    if REPORTLAB_IMPORT_ERROR:
        raise RuntimeError('PDF export is unavailable. Install the reportlab dependency and restart the server.') from REPORTLAB_IMPORT_ERROR
    buffer = BytesIO()
    document = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=15 * mm, leftMargin=15 * mm,
                                 topMargin=17 * mm, bottomMargin=16 * mm, title='Cold-Chain Excursion Audit')
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name='AuditTitle', parent=styles['Title'], fontName='Helvetica-Bold', fontSize=22, leading=25, textColor=colors.HexColor('#1d1d1f'), spaceAfter=4))
    styles.add(ParagraphStyle(name='AuditKicker', parent=styles['Normal'], fontName='Helvetica-Bold', fontSize=7, leading=9, textColor=colors.HexColor('#c04d0b'), tracking=1.3, spaceAfter=6))
    styles.add(ParagraphStyle(name='AuditSub', parent=styles['Normal'], fontSize=9, leading=13, textColor=colors.HexColor('#6e6e73'), spaceAfter=12))
    styles.add(ParagraphStyle(name='AuditH2', parent=styles['Heading2'], fontName='Helvetica-Bold', fontSize=12, leading=15, textColor=colors.HexColor('#24242a'), spaceBefore=14, spaceAfter=7))
    styles.add(ParagraphStyle(name='AuditCell', parent=styles['Normal'], fontSize=7.1, leading=9, textColor=colors.HexColor('#34343b')))
    styles.add(ParagraphStyle(name='AuditCellSmall', parent=styles['Normal'], fontSize=6.4, leading=8, textColor=colors.HexColor('#55555e')))
    styles.add(ParagraphStyle(name='AuditNote', parent=styles['Normal'], fontSize=7.5, leading=10, textColor=colors.HexColor('#6e6e73')))
    styles.add(ParagraphStyle(name='AuditMetricLabel', parent=styles['Normal'], fontName='Helvetica-Bold', fontSize=6.4, leading=8, textColor=colors.HexColor('#c8c8ce'), alignment=TA_CENTER))
    styles.add(ParagraphStyle(name='AuditMetric', parent=styles['Normal'], fontName='Helvetica-Bold', fontSize=17, leading=19, textColor=colors.white, alignment=TA_CENTER))
    story = [_paragraph('COLD-CHAIN EXCURSION AUDIT', styles['AuditKicker']), _paragraph('Storage integrity report', styles['AuditTitle']),
             _paragraph(f'Compliance evidence package for {_safe_text(audit["storage_unit"])}. This report captures recorded readings and inventory locations intersecting the selected excursion window.', styles['AuditSub'])]
    metadata = [
        [_paragraph('Storage unit', styles['AuditCellSmall']), _paragraph(audit['storage_unit'], styles['AuditCellSmall']), _paragraph('Projects in scope', styles['AuditCellSmall']), _paragraph(audit['project_count'], styles['AuditCellSmall'])],
        [_paragraph('Window start', styles['AuditCellSmall']), _paragraph(audit['start'].astimezone().strftime('%Y-%m-%d %H:%M %Z'), styles['AuditCellSmall']), _paragraph('Window end', styles['AuditCellSmall']), _paragraph(audit['end'].astimezone().strftime('%Y-%m-%d %H:%M %Z'), styles['AuditCellSmall'])],
        [_paragraph('Generated by', styles['AuditCellSmall']), _paragraph(getattr(generated_by, 'get_full_name', lambda: '')() or generated_by.username, styles['AuditCellSmall']), _paragraph('Generated at', styles['AuditCellSmall']), _paragraph(timezone.localtime().strftime('%Y-%m-%d %H:%M %Z'), styles['AuditCellSmall'])],
    ]
    story.extend([Table(metadata, colWidths=[29 * mm, 62 * mm, 31 * mm, 48 * mm], style=TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#faf7f5')), ('BOX', (0, 0), (-1, -1), .5, colors.HexColor('#eadfd8')),
        ('INNERGRID', (0, 0), (-1, -1), .25, colors.HexColor('#eee5e0')), ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'), ('LEFTPADDING', (0, 0), (-1, -1), 7), ('RIGHTPADDING', (0, 0), (-1, -1), 7), ('TOPPADDING', (0, 0), (-1, -1), 6), ('BOTTOMPADDING', (0, 0), (-1, -1), 6)
    ])), Spacer(1, 8 * mm)])

    summary = [[_paragraph('TEMPERATURE READINGS', styles['AuditMetricLabel']), _paragraph('CRITICAL FLAGS', styles['AuditMetricLabel']), _paragraph('INVENTORY PACKAGES', styles['AuditMetricLabel']), _paragraph('SAMPLE PACKAGES', styles['AuditMetricLabel'])],
               [_paragraph(len(audit['events']), styles['AuditMetric']), _paragraph(audit['critical_count'], styles['AuditMetric']), _paragraph(audit['inventory_count'], styles['AuditMetric']), _paragraph(audit['sample_count'], styles['AuditMetric'])]]
    story.extend([Table(summary, colWidths=[43 * mm] * 4, style=TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#1d1d1f')), ('TEXTCOLOR', (0, 0), (-1, -1), colors.white), ('BOX', (0, 0), (-1, -1), .5, colors.HexColor('#1d1d1f')), ('INNERGRID', (0, 0), (-1, -1), .25, colors.HexColor('#46464c')), ('ALIGN', (0, 0), (-1, -1), 'CENTER'), ('TOPPADDING', (0, 0), (-1, 0), 7), ('BOTTOMPADDING', (0, 0), (-1, 0), 3), ('TOPPADDING', (0, 1), (-1, 1), 5), ('BOTTOMPADDING', (0, 1), (-1, 1), 8)
    ])), Spacer(1, 4 * mm), _paragraph('EVIDENCE SUMMARY', styles['AuditH2']), _paragraph('Every record below was matched to the selected storage identifier and time window. Inventory locations reflect the latest recorded location that overlaps the excursion dates; temperature readings are shown exactly as logged.', styles['AuditNote'])])

    if audit['events']:
        story.append(_paragraph('Temperature log', styles['AuditH2']))
        rows = [[_paragraph(h, styles['AuditCellSmall']) for h in ('Project', 'Recorded at', 'Temperature', 'Condition', 'Alert', 'Recorded by')]]
        for event in audit['events']:
            rows.append([_paragraph(event.project.name, styles['AuditCell']), _paragraph(timezone.localtime(event.recorded_at).strftime('%Y-%m-%d %H:%M'), styles['AuditCellSmall']), _paragraph(f'{event.temperature} deg {event.temperature_unit}', styles['AuditCell']), _paragraph(event.storage_condition, styles['AuditCellSmall']), _paragraph(event.alert_level.upper(), styles['AuditCell']), _paragraph(event.recorded_by.username if event.recorded_by else 'System', styles['AuditCellSmall'])])
        story.append(Table(rows, repeatRows=1, colWidths=[30 * mm, 31 * mm, 26 * mm, 26 * mm, 21 * mm, 36 * mm], style=_table_style()))
    else:
        story.extend([Spacer(1, 3 * mm), _paragraph('No temperature readings were logged for this storage unit during the selected window.', styles['AuditNote'])])

    story.append(_paragraph('Reagent and consumable packages', styles['AuditH2']))
    if audit['inventory']:
        rows = [[_paragraph(h, styles['AuditCellSmall']) for h in ('Type', 'Project', 'Item / code', 'Lot / batch', 'Quantity', 'Expiry', 'Location')]]
        for item in audit['inventory']:
            rows.append([_paragraph(item['category'], styles['AuditCellSmall']), _paragraph(item['project'], styles['AuditCellSmall']), _paragraph(f"{item['name']} / {item['identifier']}", styles['AuditCell']), _paragraph(f"{item['lot']} / {item['batch']}", styles['AuditCellSmall']), _paragraph(item['quantity'], styles['AuditCellSmall']), _paragraph(item['expiry'], styles['AuditCellSmall']), _paragraph(item['location'], styles['AuditCellSmall'])])
        story.append(Table(rows, repeatRows=1, colWidths=[19 * mm, 25 * mm, 42 * mm, 29 * mm, 28 * mm, 23 * mm, 24 * mm], style=_table_style()))
    else:
        story.append(_paragraph('No reagent or consumable package was located against this storage identifier.', styles['AuditNote']))

    story.append(_paragraph('Sample packages', styles['AuditH2']))
    if audit['samples']:
        rows = [[_paragraph(h, styles['AuditCellSmall']) for h in ('Project', 'Sample ID', 'Type / volume', 'Extraction batch', 'Box / well', 'Presence')]]
        for sample in audit['samples']:
            rows.append([_paragraph(sample['project'], styles['AuditCellSmall']), _paragraph(sample['sample_id'], styles['AuditCell']), _paragraph(f"{sample['sample_type']} / {sample['volume']}", styles['AuditCellSmall']), _paragraph(sample['batch'], styles['AuditCellSmall']), _paragraph(sample['box'], styles['AuditCellSmall']), _paragraph(f"{sample['moved_in']} to {sample['moved_out']}", styles['AuditCellSmall'])])
        story.append(Table(rows, repeatRows=1, colWidths=[25 * mm, 28 * mm, 32 * mm, 29 * mm, 42 * mm, 31 * mm], style=_table_style()))
    else:
        story.append(_paragraph('No sample location record overlapped this storage identifier and excursion window.', styles['AuditNote']))

    story.append(_paragraph('Audit trail', styles['AuditH2']))
    if audit['logs']:
        rows = [[_paragraph(h, styles['AuditCellSmall']) for h in ('Timestamp', 'Project', 'Actor', 'Action', 'Details')]]
        for log in audit['logs']:
            details = ', '.join(f'{key}: {value}' for key, value in (log.details or {}).items())
            rows.append([_paragraph(timezone.localtime(log.timestamp).strftime('%Y-%m-%d %H:%M'), styles['AuditCellSmall']), _paragraph(log.project.name, styles['AuditCellSmall']), _paragraph(log.user.username if log.user else 'System', styles['AuditCellSmall']), _paragraph(log.action, styles['AuditCell']), _paragraph(details[:180], styles['AuditCellSmall'])])
        story.append(Table(rows, repeatRows=1, colWidths=[29 * mm, 28 * mm, 28 * mm, 48 * mm, 54 * mm], style=_table_style()))
    else:
        story.append(_paragraph('No project audit log entries were recorded in this window.', styles['AuditNote']))

    story.extend([Spacer(1, 8 * mm), _paragraph('Compliance note', styles['AuditH2']), _paragraph('This export is a point-in-time evidence package generated from Flux records. It should be reviewed alongside facility power, alarm, maintenance and corrective-action records before final sign-off.', styles['AuditNote'])])
    document.build(story, onFirstPage=_footer, onLaterPages=_footer)
    return buffer.getvalue()


def _table_style():
    return TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#f2f0ee')), ('TEXTCOLOR', (0, 0), (-1, 0), colors.HexColor('#66666d')),
        ('BOX', (0, 0), (-1, -1), .5, colors.HexColor('#dfdfe4')), ('INNERGRID', (0, 0), (-1, -1), .25, colors.HexColor('#e9e9ec')),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'), ('LEFTPADDING', (0, 0), (-1, -1), 5), ('RIGHTPADDING', (0, 0), (-1, -1), 5), ('TOPPADDING', (0, 0), (-1, -1), 5), ('BOTTOMPADDING', (0, 0), (-1, -1), 5)
    ])


def _footer(canvas, document):
    canvas.saveState()
    canvas.setStrokeColor(colors.HexColor('#e5e5e7'))
    canvas.line(15 * mm, 11 * mm, A4[0] - 15 * mm, 11 * mm)
    canvas.setFont('Helvetica', 7)
    canvas.setFillColor(colors.HexColor('#81818a'))
    canvas.drawString(15 * mm, 7 * mm, 'FLUX.INC - COLD-CHAIN AUDIT')
    canvas.drawRightString(A4[0] - 15 * mm, 7 * mm, f'Page {document.page}')
    canvas.restoreState()
