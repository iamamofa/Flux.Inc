"""Permission-checked, atomic stock-sharing and borrowing operations."""
from datetime import date, datetime

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import IntegrityError, transaction
from django.db.models import F
from django.utils import timezone

from .models import (
    BorrowLoan, BorrowLoanEvent, Consumable, Log, MSDSFile, Project,
    Reagent, StockOffer,
)


MAX_PACKS = 2147483647
ITEM_MODELS = {'consumable': Consumable, 'reagent': Reagent}


def unopened_packs(item):
    """The current partial pack is excluded from packs available to lend."""
    if (item.items_per_pack <= 0
            or item.items_left_in_pack > item.items_per_pack):
        return 0
    return max(item.pack_count - int(item.items_left_in_pack < item.items_per_pack), 0)


def _manager(project, user):
    try:
        current = Project.objects.select_related('project_manager').get(pk=project.pk)
    except Project.DoesNotExist:
        raise PermissionDenied('This project is unavailable.')
    if (not user.is_authenticated or not user.is_active or not current.is_active
            or current.project_manager_id != user.pk):
        raise PermissionDenied('Only the manager of an active project can manage borrowing and loans.')
    return current


def _quantity(value):
    if isinstance(value, bool) or not str(value).isascii() or not str(value).isdigit():
        raise ValidationError('Enter a positive whole number of packs.')
    value = int(value)
    if not 1 <= value <= MAX_PACKS:
        raise ValidationError(f'Enter between 1 and {MAX_PACKS} packs.')
    return value


def _text(value, label, required=False):
    value = str(value or '').strip()
    if required and not value:
        raise ValidationError(f'{label} is required.')
    if len(value) > 1000:
        raise ValidationError(f'{label} must be 1000 characters or fewer.')
    return value


def _usable(item):
    return (item.is_active and unopened_packs(item) > 0
            and (not item.expiry_date or item.expiry_date >= timezone.localdate()))


def _offer(offer_id):
    try:
        return StockOffer.objects.select_for_update(of=('self',)).select_related(
            'source_project__project_manager', 'consumable', 'reagent',
        ).get(pk=offer_id)
    except (StockOffer.DoesNotExist, ValueError, TypeError, OverflowError):
        raise ValidationError('This shared-stock listing is unavailable.')


def _record(loan, user, action, note=''):
    BorrowLoanEvent.objects.create(
        loan=loan, actor=user, actor_name=user.get_username(), action=action, note=note,
    )
    for project in (loan.offer.source_project, loan.borrower_project):
        Log.objects.create(
            project=project, user=user,
            action=f'{loan.reference}: {action} ({loan.quantity} pack(s) of {loan.item_name})'[:255],
            details={
                'loan_reference': loan.reference,
                'loan_id': loan.pk,
                'quantity': loan.quantity,
                'lender_project': loan.lender_project_name,
                'borrower_project': loan.borrower_project_name,
                'note': note,
            },
        )


def _locked_item(item):
    return type(item).objects.select_for_update().get(pk=item.pk)


def _debit(item, quantity):
    if not _usable(item) or quantity > unopened_packs(item):
        raise ValidationError('There are not enough unexpired, unopened packs available. Refresh the inventory and try again.')
    remaining = item.pack_count - quantity
    # Compare the read stock as well as updating it. This also protects databases
    # whose SELECT FOR UPDATE support is limited, including the development SQLite DB.
    changed = type(item).objects.filter(
        pk=item.pk, pack_count=item.pack_count,
        items_left_in_pack=item.items_left_in_pack, items_per_pack=item.items_per_pack,
        is_active=True, expiry_date=item.expiry_date,
    ).update(
        pack_count=F('pack_count') - quantity,
        items_left_in_pack=item.items_left_in_pack if remaining else 0,
    )
    if changed != 1:
        raise ValidationError('The inventory changed during this action. Refresh and try again.')


def _clone_stock(item, project, quantity, reference):
    """Create a separate receiving batch; never merge different stock batches."""
    excluded = {'id', 'project', 'date_recorded', 'pack_count', 'items_left_in_pack',
                'storage_location', 'threshold_value', 'notes'}
    values = {
        field.name: getattr(item, field.name)
        for field in item._meta.concrete_fields if field.name not in excluded
    }
    received = type(item).objects.create(
        **values, project=project, pack_count=quantity,
        items_left_in_pack=item.items_per_pack,
        storage_location='', threshold_value=None,
        notes=f'{reference}: received from {item.project.name}. Confirm the receiving storage location.',
    )
    if isinstance(item, Reagent):
        # MSDS records retain the same stored document and scan/verification metadata.
        # bulk_create intentionally avoids MSDSFile.save re-reading the shared file.
        MSDSFile.objects.bulk_create([
            MSDSFile(
                reagent=received, file=msds.file.name,
                original_filename=msds.original_filename, file_size=msds.file_size,
                file_hash=msds.file_hash, uploaded_by_id=msds.uploaded_by_id,
                last_verified=msds.last_verified, is_verified=msds.is_verified,
                verification_notes=msds.verification_notes, scan_result=msds.scan_result,
            ) for msds in item.msds_files.all()
        ])
    return received


@transaction.atomic
def publish_offer(*, project, user, item_kind, item_id, quantity, notes=''):
    project = _manager(project, user)
    quantity = _quantity(quantity)
    notes = _text(notes, 'Sharing notes')
    model = ITEM_MODELS.get(item_kind)
    if not model:
        raise ValidationError('Only consumables and reagents can be shared.')
    try:
        item = model.objects.get(pk=item_id, project=project)
    except model.DoesNotExist:
        raise ValidationError('Choose a consumable or reagent from this project.')
    if not _usable(item) or quantity > unopened_packs(item):
        raise ValidationError('Only available, unexpired and unopened packs can be shared.')
    if isinstance(item, Reagent) and (item.hazard_level or 0) >= 3 and not item.msds_files.exists():
        raise ValidationError('Add the required safety data sheet before sharing this reagent.')
    if StockOffer.objects.filter(**{item_kind: item}, is_active=True).exists():
        raise ValidationError('This item already has an active listing. Withdraw it before listing it again.')
    offer = StockOffer(
        source_project=project, created_by=user, quantity=quantity,
        notes=notes, **{item_kind: item},
    )
    offer.full_clean()
    try:
        with transaction.atomic():
            offer.save()
    except IntegrityError:
        raise ValidationError('This item already has an active listing.')
    Log.objects.create(
        project=project, user=user, action=f'Listed {quantity} pack(s) of {item.name} for borrowing'[:255],
        details={'stock_offer_id': offer.pk, 'quantity': quantity},
    )
    return offer


@transaction.atomic
def withdraw_offer(*, project, user, offer_id):
    project = _manager(project, user)
    offer = _offer(offer_id)
    if offer.source_project_id != project.pk:
        raise PermissionDenied('Only the lending project manager can withdraw this listing.')
    changed = StockOffer.objects.filter(pk=offer.pk, is_active=True).update(
        is_active=False, updated_at=timezone.now(),
    )
    if not changed:
        raise ValidationError('This listing has already been withdrawn.')
    offer.is_active = False
    Log.objects.create(
        project=project, user=user, action=f'Withdrew shared-stock listing for {offer.item.name}'[:255],
        details={'stock_offer_id': offer.pk},
    )
    return offer


@transaction.atomic
def request_loan(*, project, user, offer_id, quantity, due_date, purpose):
    project = _manager(project, user)
    quantity = _quantity(quantity)
    purpose = _text(purpose, 'Purpose', required=True)
    if (not isinstance(due_date, date) or isinstance(due_date, datetime)
            or due_date < timezone.localdate()):
        raise ValidationError('Choose a return date of today or later.')
    offer = _offer(offer_id)
    if (offer.source_project_id == project.pk
            or offer.source_project.project_manager_id == user.pk):
        raise ValidationError('Choose stock from another project manager’s project.')
    if quantity > offer.available_quantity:
        raise ValidationError('This quantity is no longer available from the shared-stock listing.')
    loan = BorrowLoan(
        offer=offer, borrower_project=project, requested_by=user,
        quantity=quantity, due_date=due_date, purpose=purpose,
        item_name=offer.item.name, product_code=offer.item.product_code,
        items_per_pack=offer.item.items_per_pack,
        lender_project_name=offer.source_project.name,
        borrower_project_name=project.name, requester_name=user.get_username(),
    )
    loan.full_clean()
    try:
        with transaction.atomic():
            loan.save()
    except IntegrityError:
        raise ValidationError('Your project already has a pending request for this listing.')
    _record(loan, user, 'Requested', purpose)
    return loan


@transaction.atomic
def update_loan(*, project, user, loan_id, action, note=''):
    project = _manager(project, user)
    note = _text(note, 'Note')
    try:
        loan = BorrowLoan.objects.select_for_update(of=('self',)).select_related(
            'borrower_project', 'offer__source_project__project_manager',
            'offer__consumable', 'offer__reagent',
            'received_consumable', 'received_reagent',
        ).get(pk=loan_id)
    except (BorrowLoan.DoesNotExist, ValueError, TypeError, OverflowError):
        raise ValidationError('This borrowing request is unavailable.')
    lender = loan.offer.source_project_id == project.pk
    borrower = loan.borrower_project_id == project.pk
    transitions = {
        'approve': ('pending', 'active', lender, 'Approved & issued'),
        'decline': ('pending', 'declined', lender, 'Declined'),
        'cancel': ('pending', 'cancelled', borrower, 'Cancelled'),
        'request_return': ('active', 'return_pending', borrower, 'Return requested'),
        'confirm_return': ('return_pending', 'returned', lender, 'Return confirmed'),
        'reject_return': ('return_pending', 'active', lender, 'Return not confirmed'),
    }
    if action not in transitions:
        raise ValidationError('Choose a valid borrowing action.')
    previous, following, permitted, event_action = transitions[action]
    if not permitted:
        raise PermissionDenied('You cannot perform this action on another project’s loan.')
    if loan.status != previous:
        raise ValidationError('This loan has already changed. Refresh before trying again.')
    now = timezone.now()
    changed = BorrowLoan.objects.filter(pk=loan.pk, status=previous).update(
        status=following, decision_note=note, updated_at=now,
    )
    if changed != 1:
        raise ValidationError('This loan has already changed. Refresh before trying again.')
    loan.status = following
    loan.decision_note = note

    if action == 'approve':
        offer = _offer(loan.offer_id)
        source = _locked_item(offer.item)
        offer.consumable = source if offer.consumable_id else None
        offer.reagent = source if offer.reagent_id else None
        if (not loan.borrower_project.is_active
                or not loan.borrower_project.project_manager_id
                or not loan.borrower_project.project_manager.is_active
                or loan.borrower_project.project_manager_id == user.pk):
            raise ValidationError('The borrowing project must have another active project manager.')
        if loan.due_date < timezone.localdate():
            raise ValidationError('The requested return date has passed. Ask the borrower to submit a new request.')
        if (source.name != loan.item_name or source.product_code != loan.product_code
                or source.items_per_pack != loan.items_per_pack):
            raise ValidationError('The listed item changed after this request. Ask the borrower to submit a new request.')
        if loan.quantity > offer.available_quantity:
            raise ValidationError('There are not enough shared, unopened packs available to approve this request.')
        if isinstance(source, Reagent) and (source.hazard_level or 0) >= 3 and not source.msds_files.exists():
            raise ValidationError('Add the required safety data sheet before approving this reagent loan.')
        _debit(source, loan.quantity)
        changed = StockOffer.objects.filter(
            pk=offer.pk, is_active=True, quantity__gte=loan.quantity,
        ).update(quantity=F('quantity') - loan.quantity, updated_at=now)
        if not changed:
            raise ValidationError('The shared-stock quantity changed. Refresh and try again.')
        received = _clone_stock(source, loan.borrower_project, loan.quantity, loan.reference)
        received_field = f'received_{offer.item_kind}'
        setattr(loan, received_field, received)
        loan.approved_by = user
        loan.approved_at = now
        BorrowLoan.objects.filter(pk=loan.pk).update(
            **{f'{received_field}_id': received.pk}, approved_by=user, approved_at=now,
        )
    elif action in ('request_return', 'confirm_return'):
        if not loan.received_item:
            raise ValidationError('This loan has no receiving inventory record.')
        received = _locked_item(loan.received_item)
        if (received.project_id != loan.borrower_project_id
                or received.name != loan.item_name
                or received.product_code != loan.product_code
                or received.items_per_pack != loan.items_per_pack):
            raise ValidationError('The received stock no longer matches this loan. Restore the matching stock details before returning it.')
        if not _usable(received) or unopened_packs(received) < loan.quantity:
            raise ValidationError('Restock the received inventory with the full quantity of unexpired, unopened return or replacement packs first.')
        if action == 'confirm_return':
            source = _locked_item(loan.offer.item)
            _debit(received, loan.quantity)
            if (source.project_id == loan.offer.source_project_id
                    and source.name == received.name and source.product_code == received.product_code
                    and source.items_per_pack == received.items_per_pack
                    and source.expiry_date == received.expiry_date):
                if source.pack_count + loan.quantity > MAX_PACKS:
                    raise ValidationError('The returned quantity would exceed the inventory pack limit.')
                changed = type(source).objects.filter(
                    pk=source.pk, pack_count=source.pack_count,
                    items_left_in_pack=source.items_left_in_pack,
                    items_per_pack=source.items_per_pack,
                ).update(
                    pack_count=F('pack_count') + loan.quantity, is_active=True,
                    items_left_in_pack=(source.items_left_in_pack if source.pack_count
                                        else source.items_per_pack),
                )
                if not changed:
                    raise ValidationError('The lending inventory changed. Refresh and try again.')
            else:
                # A replacement batch may have a different expiry. Preserve it in
                # its own inventory row instead of mislabelling the original batch.
                _clone_stock(received, loan.lender_project, loan.quantity, loan.reference)
            loan.returned_at = now
            BorrowLoan.objects.filter(pk=loan.pk).update(returned_at=now)
    _record(loan, user, event_action, note)
    return loan
