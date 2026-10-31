"""Email alerts and printable receipts for Borrow & Loan events."""

import logging
from datetime import datetime

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.utils import timezone

from .models import BorrowLoan


logger = logging.getLogger('django.security')


def _pdf_escape(value):
    return str(value or '').replace('\\', '\\\\').replace('(', '\\(').replace(')', '\\)')


def build_loan_receipt_pdf(loan, event='Approved & issued'):
    """Build a small dependency-free PDF receipt for email and download."""
    lines = [
        'FLUX · BORROW & LOAN RECEIPT',
        f'Reference: {loan.reference}',
        f'Event: {event}',
        f'Item: {loan.item_name}',
        f'Category: {loan.offer.item_kind}',
        f'Product code: {loan.product_code or "Not recorded"}',
        f'Quantity: {loan.quantity} pack(s) · {loan.items_per_pack} items per pack',
        f'Lending project: {loan.lender_project_name}',
        f'Borrowing project: {loan.borrower_project_name}',
        f'Requested by: {loan.requester_name}',
        f'Approved by: {loan.approved_by.get_username() if loan.approved_by else "Pending"}',
        f'Due date: {loan.due_date.isoformat()}',
        f'Purpose: {loan.purpose}',
        f'Generated: {timezone.localtime().strftime("%Y-%m-%d %H:%M %Z")}',
        'This receipt is generated from the Flux audit trail.',
    ]
    objects = []
    offsets = [0]

    def add(value):
        offsets.append(sum(len(part) for part in objects) + len(value))
        objects.append(value)

    add(b'%PDF-1.4\n')
    add(b'1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n')
    add(b'2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n')
    add(b'3 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>\nendobj\n')
    add(b'4 0 obj\n<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>\nendobj\n')
    content = ['BT', '/F1 12 Tf', '50 750 Td']
    for index, line in enumerate(lines):
        if index:
            content.append('0 -22 Td')
        content.append(f'({_pdf_escape(line)}) Tj')
    content.append('ET')
    stream = ('\n'.join(content) + '\n').encode('latin-1', 'replace')
    add(f'5 0 obj\n<< /Length {len(stream)} >>\nstream\n'.encode('ascii') + stream + b'endstream\nendobj\n')
    body = b''.join(objects)
    xref_offset = len(body)
    # Recompute offsets from the final object stream, which keeps the PDF valid
    # when a line contains non-ASCII characters replaced above.
    object_offsets = [0]
    cursor = 0
    for chunk in objects:
        object_offsets.append(cursor)
        cursor += len(chunk)
    xref = [b'xref\n0 6\n', b'0000000000 65535 f \n']
    xref.extend(f'{offset:010d} 00000 n \n'.encode('ascii') for offset in object_offsets[1:])
    trailer = (b'trailer\n<< /Size 6 /Root 1 0 R >>\nstartxref\n'
               + str(xref_offset).encode('ascii') + b'\n%%EOF\n')
    return body + b''.join(xref) + trailer


def _recipient_emails(loan):
    recipients = set()
    lender = loan.lender_project.project_manager
    borrower = loan.borrower_project.project_manager
    for user in (lender, borrower, loan.requested_by):
        if user and user.is_active and user.email:
            recipients.add(user.email)
    return sorted(recipients)


def send_loan_notification(loan_id, event, note=''):
    """Send event mail after commit; mail failures never roll back stock."""
    try:
        loan = BorrowLoan.objects.select_related(
            'offer__source_project__project_manager',
            'borrower_project__project_manager', 'requested_by',
        ).get(pk=loan_id)
        recipients = _recipient_emails(loan)
        if not recipients:
            return
        subject = f'Flux Borrow & Loan {loan.reference}: {event}'
        body = render_to_string('inventory/borrowing_notification.txt', {
            'loan': loan, 'event': event, 'note': note,
            'receipt_url': f'{settings.SITE_URL}/borrow-loan/{loan.borrower_project.name}/{loan.pk}/receipt.pdf',
        })
        message = EmailMultiAlternatives(
            subject, body, settings.DEFAULT_FROM_EMAIL, recipients,
        )
        if event in ('Approved & issued', 'Return confirmed'):
            message.attach(
                f'{loan.reference.lower()}-{event.lower().replace(" ", "-")}.pdf',
                build_loan_receipt_pdf(loan, event),
                'application/pdf',
            )
        message.send(fail_silently=True)
    except Exception:
        logger.exception('Borrow & Loan notification failed')
