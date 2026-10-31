"""Project-manager workspace for sharing and borrowing spare inventory."""

import csv
from urllib.parse import urlencode

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.paginator import Paginator
from django.db import OperationalError
from django.db.models import F, Prefetch, Q
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_http_methods

from .borrowing import (
    project_role, publish_offer, request_direct_loan, request_loan,
    update_loan, withdraw_offer,
)
from .borrowing_notifications import build_loan_receipt_pdf
from .borrowing_forms import (
    BorrowRequestForm, LoanActionForm, PublishOfferForm, WithdrawOfferForm,
)
from .models import BorrowLoan, BorrowLoanEvent, Consumable, Project, Reagent, StockOffer
from .views import get_sidebar_urls


TABS = ('discover', 'borrowing', 'lending', 'offers')
LOAN_ACTIONS = {
    'approve_borrower': 'Your project approved the borrowing request. It is now with the lending manager.',
    'decline_borrower': 'Your project declined the borrowing request.',
    'approve': 'Loan approved. The packs have been transferred to the borrowing project.',
    'decline': 'Borrowing request declined.',
    'cancel': 'Borrowing request cancelled.',
    'request_return': 'Return submitted. The lending manager can now confirm receipt.',
    'confirm_return': 'Return confirmed. Stock has been restored to the lending project.',
    'reject_return': 'Return sent back for follow-up. The loan remains active.',
}


class BorrowCandidate:
    """A direct inventory candidate that does not need a prior public offer."""
    direct = True
    is_active = True
    notes = ''

    def __init__(self, item, item_kind, source_project):
        self.item = item
        self.item_kind = item_kind
        self.source_project = source_project
        self.pk = None
        self.quantity = self.available_quantity = max(
            item.pack_count - int(item.items_left_in_pack < item.items_per_pack), 0,
        )
        self.request_key = f'item:{source_project.pk}:{item_kind}:{item.pk}'

    @property
    def reference(self):
        return self.request_key


def _candidate_items(current_project):
    candidates = []
    projects = Project.objects.filter(
        is_active=True, project_manager__is_active=True,
    ).select_related('project_manager').order_by('name')
    for source_project in projects:
        for kind, model in (('consumable', Consumable), ('reagent', Reagent)):
            active_ids = set(StockOffer.objects.filter(
                source_project=source_project, is_active=True, quantity__gt=0,
                **{kind + '__isnull': False},
            ).values_list(kind + '_id', flat=True))
            for item in model.objects.filter(project=source_project).filter(
                    _unopened_stock_filter()).exclude(pk__in=active_ids).select_related('project'):
                candidates.append(BorrowCandidate(item, kind, source_project))
    return candidates


def _unopened_stock_filter(prefix=''):
    """A partial current pack is never advertised as an unused full pack."""
    today = timezone.localdate()
    return (
        Q(**{prefix + 'is_active': True, prefix + 'items_per_pack__gt': 0})
        & Q(**{prefix + 'items_left_in_pack__lte': F(prefix + 'items_per_pack')})
        & (Q(**{prefix + 'expiry_date__isnull': True})
           | Q(**{prefix + 'expiry_date__gte': today}))
        & (Q(**{prefix + 'pack_count__gt': 1})
           | Q(**{prefix + 'pack_count': 1,
                  prefix + 'items_left_in_pack': F(prefix + 'items_per_pack')}))
    )


def _lendable_items(project, own_offers):
    items = []
    for kind, model in (('consumable', Consumable), ('reagent', Reagent)):
        listed_ids = own_offers.filter(is_active=True).values_list(kind + '_id', flat=True)
        inventory = model.objects.filter(project=project).filter(
            _unopened_stock_filter()
        ).exclude(pk__in=[pk for pk in listed_ids if pk is not None]).order_by('name')
        for item in inventory:
            unopened = item.pack_count - int(item.items_left_in_pack < item.items_per_pack)
            items.append({
                'value': f'{kind}:{item.pk}',
                'label': f'{item.name} · {kind.title()} · {unopened} unopened packs',
                'available': unopened,
            })
    return sorted(items, key=lambda item: item['label'].casefold())


def _csv_value(value):
    value = '' if value is None else str(value)
    # Project names and notes are user input; avoid spreadsheet formula execution.
    return "'" + value if value.lstrip().startswith(('=', '+', '-', '@')) else value


def _export_history(loans):
    response = HttpResponse(content_type='text/csv; charset=utf-8')
    response['Content-Disposition'] = 'attachment; filename="flux-borrow-loan-history.csv"'
    writer = csv.writer(response)
    writer.writerow([
        'Reference', 'Item', 'Category', 'Product code', 'Lending project',
        'Borrowing project', 'Packs', 'Items per pack', 'Due date', 'Status',
        'Requested by', 'Requested at', 'Approved at', 'Returned at',
        'Purpose', 'Decision note',
    ])
    for loan in loans.iterator():
        writer.writerow([_csv_value(value) for value in (
            loan.reference, loan.item_name, loan.offer.item_kind, loan.product_code,
            loan.lender_project.name, loan.borrower_project.name, loan.quantity,
            loan.items_per_pack, loan.due_date, loan.get_status_display(),
            loan.requested_by.get_username() if loan.requested_by else 'Former user',
            loan.created_at.isoformat(),
            loan.approved_at.isoformat() if loan.approved_at else '',
            loan.returned_at.isoformat() if loan.returned_at else '',
            loan.purpose, loan.decision_note,
        )])
    return response


def _validated(form):
    if not form.is_valid():
        errors = [f'{form.fields[name].label or name.replace("_", " ").title()}: {message}'
                  for name, errors in form.errors.items() for message in errors]
        raise ValidationError(errors)
    return form.cleaned_data


@login_required
@require_http_methods(['GET', 'POST'])
def borrow_loan(request, project_name):
    project = get_object_or_404(Project, name=project_name)
    if (not project.is_active or not request.user.is_active
            or not project_role(project, request.user)):
        raise PermissionDenied('Join this project before using Borrow & Loan for it.')

    active_tab = request.POST.get('tab', request.GET.get('tab', 'discover'))
    if active_tab not in TABS:
        active_tab = 'discover'
    own_offers = StockOffer.objects.filter(source_project=project).select_related(
        'source_project__project_manager', 'consumable', 'reagent', 'created_by',
    ).order_by('-created_at', '-pk')
    lendable_items = _lendable_items(project, own_offers)
    error = ''
    action = ''
    status = 200

    if request.method == 'POST':
        action = request.POST.get('action', '')
        try:
            if action == 'publish':
                data = _validated(PublishOfferForm(request.POST, items=lendable_items))
                kind, item_id = data.pop('item').split(':', 1)
                publish_offer(project=project, user=request.user,
                              item_kind=kind, item_id=item_id, **data)
                message = 'Spare stock listed. Other project managers can now request these packs.'
            elif action == 'request':
                data = _validated(BorrowRequestForm(request.POST))
                source_ref = request.POST.get('source_ref', '').strip()
                if source_ref:
                    parts = source_ref.split(':')
                    if len(parts) != 4 or parts[0] != 'item':
                        raise ValidationError('Choose a valid inventory item.')
                    _, source_project_id, item_kind, item_id = parts
                    data.pop('offer_id', None)
                    request_direct_loan(
                        project=project, user=request.user,
                        source_project_id=source_project_id,
                        item_kind=item_kind, item_id=item_id, **data,
                    )
                else:
                    get_object_or_404(StockOffer, pk=data['offer_id'])
                    request_loan(project=project, user=request.user, **data)
                message = 'Borrowing request sent to the lending project manager.'
            elif action == 'withdraw':
                data = _validated(WithdrawOfferForm(request.POST))
                get_object_or_404(StockOffer, pk=data['offer_id'])
                withdraw_offer(project=project, user=request.user, **data)
                message = 'Listing withdrawn. Existing active loans remain in your history.'
            elif action in LOAN_ACTIONS:
                data = _validated(LoanActionForm(request.POST))
                get_object_or_404(BorrowLoan, pk=data['loan_id'])
                update_loan(project=project, user=request.user, action=action, **data)
                message = LOAN_ACTIONS[action]
            else:
                raise ValidationError('Choose a valid Borrow & Loan action.')
        except ValidationError as exc:
            error = ' '.join(exc.messages)
            status = 400
        except OperationalError as exc:
            if 'locked' not in str(exc).lower() and 'busy' not in str(exc).lower():
                raise
            error = 'Another stock update is in progress. Refresh this page and try again.'
            status = 409
        else:
            messages.success(request, message)
            url = reverse('borrow_loan', kwargs={'project_name': project.name})
            return redirect(f'{url}?{urlencode({"tab": active_tab})}')

    published_discovery = StockOffer.objects.filter(
        is_active=True, quantity__gt=0, source_project__is_active=True,
        source_project__project_manager__is_active=True,
    ).filter(
        _unopened_stock_filter('consumable__') | _unopened_stock_filter('reagent__')
    ).select_related('source_project__project_manager', 'consumable', 'reagent').order_by(
        'source_project__name', '-created_at', '-pk',
    )
    direct_candidates = _candidate_items(project)
    discovery = list(published_discovery) + direct_candidates
    search_query = request.GET.get('q', '').strip()[:200]
    kind_filter = request.GET.get('kind', '')
    if kind_filter not in ('consumable', 'reagent'):
        kind_filter = ''
    project_filter = request.GET.get('source_project', '')
    if search_query:
        needle = search_query.casefold()
        discovery = [candidate for candidate in discovery if needle in ' '.join([
            candidate.item.name, candidate.item.product_code or '', candidate.source_project.name,
        ]).casefold()]
    if kind_filter:
        discovery = [candidate for candidate in discovery if candidate.item_kind == kind_filter]
    if project_filter.isdecimal() and len(project_filter) <= 19 and int(project_filter) <= 9223372036854775807:
        discovery = [candidate for candidate in discovery if str(candidate.source_project.pk) == project_filter]
    else:
        project_filter = ''
    discovery.sort(key=lambda candidate: (candidate.source_project.name.casefold(), candidate.item.name.casefold()))
    source_projects = sorted({candidate.source_project for candidate in discovery}, key=lambda item: item.name.casefold())
    available_count = len(discovery)

    scoped_loans = BorrowLoan.objects.filter(
        Q(borrower_project=project) | Q(offer__source_project=project)
    ).select_related(
        'offer__source_project__project_manager', 'offer__consumable', 'offer__reagent',
        'borrower_project__project_manager', 'requested_by', 'approved_by',
    ).order_by('-created_at', '-pk')
    loans = scoped_loans.filter(
        offer__source_project=project
    ) if active_tab == 'lending' else scoped_loans.filter(borrower_project=project)
    if request.method == 'GET' and request.GET.get('export') == 'csv':
        return _export_history(loans)
    loan_status = request.GET.get('status', '')
    if loan_status in dict(BorrowLoan._meta.get_field('status').choices):
        loans = loans.filter(status=loan_status)
    events = BorrowLoanEvent.objects.select_related('actor').order_by('created_at', 'pk')
    loans = loans.prefetch_related(Prefetch('events', queryset=events))
    outstanding = scoped_loans.filter(
        borrower_project=project, status__in=('active', 'return_pending'),
    )
    stats = {
        'available': available_count,
        'incoming': scoped_loans.filter(offer__source_project=project, status='pending').count(),
        'active': outstanding.count(),
        'overdue': outstanding.filter(due_date__lt=timezone.localdate()).count(),
    }
    page_params = request.GET.copy()
    page_params.pop('page', None)
    page_params['tab'] = active_tab
    context = {
        'project': project,
        'is_project_manager': project.project_manager_id == request.user.pk,
        'projects': Project.objects.filter(project_manager=request.user, is_active=True),
        'active_tab': active_tab, 'search_query': search_query, 'kind_filter': kind_filter,
        'project_filter': project_filter, 'source_projects': source_projects,
        'offers_page': Paginator(discovery, 12).get_page(request.GET.get('page')),
        'own_offers': own_offers, 'loans_page': Paginator(loans, 12).get_page(request.GET.get('page')),
        'stats': stats, 'lendable_items': lendable_items, 'today': timezone.localdate(),
        'error': error, 'error_action': action,
        'error_id': request.POST.get('offer_id', request.POST.get('loan_id', request.POST.get('source_ref', ''))),
        'post_data': request.POST if error else {}, 'page_query': page_params.urlencode(),
        **get_sidebar_urls(project.name),
    }
    return render(request, 'inventory/borrow_loan.html', context, status=status)


@login_required
def borrow_loan_receipt(request, project_name, loan_id):
    project = get_object_or_404(Project, name=project_name)
    if not project_role(project, request.user):
        raise PermissionDenied('You do not have access to this project receipt.')
    loan = get_object_or_404(
        BorrowLoan.objects.select_related('offer__source_project', 'borrower_project'),
        pk=loan_id,
    )
    if loan.offer.source_project_id != project.pk and loan.borrower_project_id != project.pk:
        raise PermissionDenied('This receipt belongs to another project.')
    event = 'Return confirmed' if loan.status == BorrowLoan.Status.RETURNED else 'Approved & issued'
    response = HttpResponse(build_loan_receipt_pdf(loan, event), content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="{loan.reference.lower()}-receipt.pdf"'
    response['Cache-Control'] = 'private, no-store'
    return response
