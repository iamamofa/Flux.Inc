"""Regression coverage for manager-to-manager inventory borrowing."""
from datetime import timedelta
from urllib.parse import urlencode

from django.contrib.auth.models import User
from django.core.exceptions import PermissionDenied, ValidationError
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from .borrowing import publish_offer, request_loan, update_loan, withdraw_offer
from .models import (
    BorrowLoan, Consumable, Log, MSDSFile, Project, Reagent, StockOffer, TrashReagent,
)


class BorrowingTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.lender = User.objects.create_user(username='loan-lender')
        cls.borrower = User.objects.create_user(username='loan-borrower')
        cls.other = User.objects.create_user(username='loan-other')
        cls.member = User.objects.create_user(username='loan-member')
        cls.editor = User.objects.create_user(username='loan-editor')
        cls.source = Project.objects.create(name='Lending project', project_manager=cls.lender)
        cls.destination = Project.objects.create(name='Borrowing project', project_manager=cls.borrower)
        cls.unrelated = Project.objects.create(name='Unrelated project', project_manager=cls.other)
        cls.source.project_members.add(cls.member)
        cls.source.project_editors.add(cls.editor)
        cls.expiry = timezone.localdate() + timedelta(days=60)
        cls.due = timezone.localdate() + timedelta(days=7)
        cls.stock = Consumable.objects.create(
            project=cls.source, name='Unopened filter packs', product_code='FILTER-10',
            items_per_pack=10, items_left_in_pack=10, pack_count=6,
            expiry_date=cls.expiry, storage_location='Cabinet A', cold_storage='Ambient',
            vendor='Test supplier', notes='Original inventory notes',
        )

    def offer(self, item=None, quantity=5):
        item = item or self.stock
        return publish_offer(
            project=self.source, user=self.lender,
            item_kind='reagent' if isinstance(item, Reagent) else 'consumable',
            item_id=item.pk, quantity=quantity, notes='Spare unopened packs',
        )

    def loan(self, offer=None, quantity=2, project=None, user=None):
        return request_loan(
            project=project or self.destination, user=user or self.borrower,
            offer_id=(offer or self.offer()).pk, quantity=quantity,
            due_date=self.due, purpose='Temporary project supply',
        )

    def transition(self, loan, action, project=None, user=None, note=''):
        return update_loan(
            project=project or self.source, user=user or self.lender,
            loan_id=loan.pk, action=action, note=note,
        )

    def url(self, project=None):
        return reverse('borrow_loan', kwargs={'project_name': (project or self.source).name})

    def test_publish_only_exposes_explicitly_offered_stock(self):
        offer = self.offer()
        self.assertEqual(offer.source_project, self.source)
        self.assertEqual(offer.item, self.stock)
        self.assertEqual(offer.available_quantity, 5)
        self.assertEqual(offer.created_by, self.lender)
        self.assertEqual(StockOffer.objects.count(), 1)
        self.stock.refresh_from_db()
        self.assertEqual(self.stock.pack_count, 6)

    def test_open_pack_is_excluded_from_available_packs(self):
        self.stock.items_left_in_pack = 3
        self.stock.save(update_fields=['items_left_in_pack'])
        offer = self.offer(quantity=5)
        self.assertEqual(offer.available_quantity, 5)
        with self.assertRaises(ValidationError):
            self.offer(quantity=6)

    def test_invalid_quantity_does_not_publish_an_offer(self):
        for quantity in (0, -1, 7, 'one', '1.5'):
            with self.subTest(quantity=quantity), self.assertRaises(ValidationError):
                self.offer(quantity=quantity)
        self.assertFalse(StockOffer.objects.exists())

    def test_expired_inactive_and_empty_items_cannot_be_offered(self):
        cases = [
            {'expiry_date': timezone.localdate() - timedelta(days=1)},
            {'is_active': False},
            {'pack_count': 0, 'items_left_in_pack': 0},
            {'items_per_pack': 0, 'items_left_in_pack': 0},
        ]
        for changes in cases:
            with self.subTest(changes=changes):
                item = Consumable.objects.create(
                    project=self.source, name='Unavailable supply', items_per_pack=10,
                    items_left_in_pack=10, pack_count=5, cold_storage='Ambient',
                )
                for field, value in changes.items():
                    setattr(item, field, value)
                item.save()
                with self.assertRaises(ValidationError):
                    self.offer(item=item, quantity=1)

    def test_only_current_project_manager_can_publish(self):
        for user in (self.borrower, self.member, self.editor):
            with self.subTest(user=user.username), self.assertRaises(PermissionDenied):
                publish_offer(
                    project=self.source, user=user, item_kind='consumable',
                    item_id=self.stock.pk, quantity=1,
                )
        self.assertFalse(StockOffer.objects.exists())

    def test_cannot_publish_another_projects_item(self):
        with self.assertRaises((PermissionDenied, ValidationError)):
            publish_offer(
                project=self.destination, user=self.borrower, item_kind='consumable',
                item_id=self.stock.pk, quantity=1,
            )
        self.assertFalse(StockOffer.objects.exists())

    def test_equipment_and_samples_are_not_supported(self):
        for kind in ('equipment', 'sample', 'unknown'):
            with self.subTest(kind=kind), self.assertRaises(ValidationError):
                publish_offer(
                    project=self.source, user=self.lender, item_kind=kind,
                    item_id=self.stock.pk, quantity=1,
                )

    def test_request_records_due_date_purpose_and_audit_without_moving_stock(self):
        loan = self.loan()
        self.assertEqual(loan.status, 'pending')
        self.assertEqual(loan.item_name, self.stock.name)
        self.assertEqual(loan.product_code, self.stock.product_code)
        self.assertEqual(loan.items_per_pack, 10)
        self.assertEqual(loan.quantity, 2)
        self.assertEqual(loan.due_date, self.due)
        self.assertEqual(loan.purpose, 'Temporary project supply')
        self.assertEqual(loan.requested_by, self.borrower)
        self.assertEqual(loan.borrower_project, self.destination)
        self.assertEqual(loan.lender_project, self.source)
        self.assertTrue(loan.reference)
        self.assertTrue(loan.events.filter(actor=self.borrower).exists())
        self.stock.refresh_from_db()
        self.assertEqual(self.stock.pack_count, 6)
        self.assertFalse(Consumable.objects.filter(project=self.destination).exists())

    def test_duplicate_pending_request_is_rejected(self):
        offer = self.offer()
        self.loan(offer)
        with self.assertRaises(ValidationError):
            self.loan(offer)
        self.assertEqual(BorrowLoan.objects.count(), 1)

    def test_cannot_borrow_from_own_or_another_self_managed_project(self):
        offer = self.offer()
        for project in (
            self.source,
            Project.objects.create(name='Another lender project', project_manager=self.lender),
        ):
            with self.subTest(project=project.name), self.assertRaises(ValidationError):
                self.loan(offer=offer, project=project, user=self.lender)
        self.assertFalse(BorrowLoan.objects.exists())

    def test_request_rejects_invalid_quantity_and_past_due_date(self):
        offer = self.offer()
        for quantity in (0, -1, 6, '1.2', 'invalid'):
            with self.subTest(quantity=quantity), self.assertRaises(ValidationError):
                self.loan(offer=offer, quantity=quantity)
        with self.assertRaises(ValidationError):
            request_loan(
                project=self.destination, user=self.borrower, offer_id=offer.pk,
                quantity=1, due_date=timezone.localdate() - timedelta(days=1), purpose='Need stock',
            )
        self.assertFalse(BorrowLoan.objects.exists())

    def test_members_and_editors_cannot_request_for_a_project(self):
        offer = self.offer()
        for user in (self.member, self.editor, self.other):
            with self.subTest(user=user.username), self.assertRaises(PermissionDenied):
                self.loan(offer=offer, user=user)

    def test_approval_moves_stock_once_and_preserves_item_metadata(self):
        loan = self.loan()
        self.transition(loan, 'approve', note='Collect from the stock room')
        loan.refresh_from_db()
        self.stock.refresh_from_db()
        offer = StockOffer.objects.get(pk=loan.offer_id)
        received = loan.received_consumable
        self.assertEqual(loan.status, 'active')
        self.assertIsNotNone(loan.approved_at)
        self.assertEqual(loan.approved_by, self.lender)
        self.assertEqual(self.stock.pack_count, 4)
        self.assertEqual(self.stock.items_left_in_pack, 10)
        self.assertEqual(offer.quantity, 3)
        self.assertIsNotNone(received)
        self.assertEqual(received.project, self.destination)
        self.assertEqual(received.pack_count, 2)
        self.assertEqual(received.items_left_in_pack, 10)
        for field in ('name', 'product_code', 'items_per_pack', 'expiry_date', 'vendor', 'cold_storage'):
            self.assertEqual(getattr(received, field), getattr(self.stock, field))
        self.assertTrue(Log.objects.filter(project=self.source).exists())
        self.assertTrue(Log.objects.filter(project=self.destination).exists())
        with self.assertRaises(ValidationError):
            self.transition(loan, 'approve')
        self.stock.refresh_from_db()
        received.refresh_from_db()
        self.assertEqual(self.stock.pack_count, 4)
        self.assertEqual(received.pack_count, 2)

    def test_approval_keeps_an_open_source_pack_untouched(self):
        self.stock.items_left_in_pack = 3
        self.stock.save(update_fields=['items_left_in_pack'])
        loan = self.loan(quantity=5)
        self.transition(loan, 'approve')
        self.stock.refresh_from_db()
        self.assertEqual(self.stock.pack_count, 1)
        self.assertEqual(self.stock.items_left_in_pack, 3)

    def test_reagent_approval_copies_reagent_details_and_safety_documents(self):
        reagent = Reagent.objects.create(
            project=self.source, name='Buffer packs', product_code='BUF-20',
            items_per_pack=20, items_left_in_pack=20, pack_count=4,
            cold_storage='Refrigerated', oem_temperature=4, country_of_origin='Ghana',
            hazard_level=1, expiry_date=self.expiry,
        )
        MSDSFile.objects.create(
            id=991, reagent=reagent, file='msds_files/buffer.pdf',
            original_filename='buffer.pdf', file_size=1234, file_hash='a' * 64,
            uploaded_by=self.lender, scan_result='clean', is_verified=True,
        )
        loan = self.loan(offer=self.offer(item=reagent, quantity=3))
        self.transition(loan, 'approve')
        loan.refresh_from_db()
        received = loan.received_reagent
        reagent.refresh_from_db()
        self.assertEqual(reagent.pack_count, 2)
        self.assertIsNone(loan.received_consumable)
        self.assertEqual(received.project, self.destination)
        self.assertEqual(received.hazard_level, 1)
        self.assertEqual(received.country_of_origin, 'Ghana')
        self.assertEqual(received.oem_temperature, 4)
        self.assertEqual(received.msds_files.count(), 1)
        self.assertEqual(received.msds_files.get().file.name, 'msds_files/buffer.pdf')

    def test_overcommitted_requests_are_rechecked_on_approval(self):
        offer = self.offer(quantity=3)
        first = self.loan(offer, quantity=2)
        second = self.loan(offer, quantity=2, project=self.unrelated, user=self.other)
        self.transition(first, 'approve')
        with self.assertRaises(ValidationError):
            self.transition(second, 'approve')
        second.refresh_from_db()
        self.stock.refresh_from_db()
        self.assertEqual(second.status, 'pending')
        self.assertEqual(self.stock.pack_count, 4)
        self.assertFalse(Consumable.objects.filter(project=self.unrelated).exists())

    def test_approval_rechecks_stock_consumed_after_request(self):
        loan = self.loan(quantity=3)
        self.stock.pack_count = 2
        self.stock.save(update_fields=['pack_count'])
        with self.assertRaises(ValidationError):
            self.transition(loan, 'approve')
        loan.refresh_from_db()
        self.assertEqual(loan.status, 'pending')
        self.assertFalse(Consumable.objects.filter(project=self.destination).exists())

    def test_approval_rechecks_expiry_and_project_activity(self):
        loan = self.loan()
        self.stock.expiry_date = timezone.localdate() - timedelta(days=1)
        self.stock.save(update_fields=['expiry_date'])
        with self.assertRaises(ValidationError):
            self.transition(loan, 'approve')
        self.stock.expiry_date = self.expiry
        self.stock.save(update_fields=['expiry_date'])
        self.destination.is_active = False
        self.destination.save(update_fields=['is_active'])
        with self.assertRaises((PermissionDenied, ValidationError)):
            self.transition(loan, 'approve')
        loan.refresh_from_db()
        self.assertEqual(loan.status, 'pending')

    def test_only_lending_manager_can_approve_and_decline(self):
        loan = self.loan()
        for project, user in ((self.destination, self.borrower), (self.unrelated, self.other)):
            for action in ('approve', 'decline'):
                with self.subTest(user=user.username, action=action), self.assertRaises(PermissionDenied):
                    self.transition(loan, action, project=project, user=user)
        loan.refresh_from_db()
        self.assertEqual(loan.status, 'pending')

    def test_declining_and_cancelling_do_not_change_stock(self):
        first = self.loan()
        self.transition(first, 'decline', note='Stock needed for our next phase')
        first.refresh_from_db()
        self.assertEqual(first.status, 'declined')
        second = self.loan(offer=first.offer)
        self.transition(second, 'cancel', project=self.destination, user=self.borrower)
        second.refresh_from_db()
        self.assertEqual(second.status, 'cancelled')
        self.stock.refresh_from_db()
        self.assertEqual(self.stock.pack_count, 6)
        self.assertFalse(Consumable.objects.filter(project=self.destination).exists())

    def test_only_borrower_can_cancel_pending_request(self):
        loan = self.loan()
        with self.assertRaises(PermissionDenied):
            self.transition(loan, 'cancel')
        self.transition(loan, 'approve')
        with self.assertRaises(ValidationError):
            self.transition(loan, 'cancel', project=self.destination, user=self.borrower)
        loan.refresh_from_db()
        self.assertEqual(loan.status, 'active')

    def test_return_requires_borrower_request_then_lender_confirmation(self):
        loan = self.loan()
        self.transition(loan, 'approve')
        with self.assertRaises(ValidationError):
            self.transition(loan, 'confirm_return')
        with self.assertRaises(PermissionDenied):
            self.transition(loan, 'request_return')
        self.transition(loan, 'request_return', project=self.destination, user=self.borrower)
        loan.refresh_from_db()
        self.stock.refresh_from_db()
        self.assertEqual(loan.status, 'return_pending')
        self.assertEqual(self.stock.pack_count, 4)
        with self.assertRaises(PermissionDenied):
            self.transition(loan, 'confirm_return', project=self.destination, user=self.borrower)
        self.transition(loan, 'confirm_return', note='All packs received')
        loan.refresh_from_db()
        self.stock.refresh_from_db()
        loan.received_consumable.refresh_from_db()
        self.assertEqual(loan.status, 'returned')
        self.assertIsNotNone(loan.returned_at)
        self.assertEqual(self.stock.pack_count, 6)
        self.assertEqual(loan.received_consumable.pack_count, 0)
        self.assertEqual(loan.received_consumable.items_left_in_pack, 0)
        self.assertEqual(loan.offer.quantity, 3)
        with self.assertRaises(ValidationError):
            self.transition(loan, 'confirm_return')
        self.stock.refresh_from_db()
        self.assertEqual(self.stock.pack_count, 6)
        self.assertGreaterEqual(loan.events.count(), 4)

    def test_return_rejects_consumed_open_or_expired_packs_without_stock_change(self):
        loan = self.loan()
        self.transition(loan, 'approve')
        self.transition(loan, 'request_return', project=self.destination, user=self.borrower)
        loan.refresh_from_db()
        received = loan.received_consumable
        for changes in (
            {'pack_count': 1, 'items_left_in_pack': 10, 'expiry_date': self.expiry},
            {'pack_count': 2, 'items_left_in_pack': 5, 'expiry_date': self.expiry},
            {'pack_count': 2, 'items_left_in_pack': 10, 'expiry_date': timezone.localdate() - timedelta(days=1)},
        ):
            with self.subTest(changes=changes):
                for field, value in changes.items():
                    setattr(received, field, value)
                received.save()
                with self.assertRaises(ValidationError):
                    self.transition(loan, 'confirm_return')
                loan.refresh_from_db()
                self.stock.refresh_from_db()
                self.assertEqual(loan.status, 'return_pending')
                self.assertEqual(self.stock.pack_count, 4)

    def test_lender_can_reject_return_and_keep_loan_open(self):
        loan = self.loan()
        self.transition(loan, 'approve')
        self.transition(loan, 'request_return', project=self.destination, user=self.borrower)
        self.transition(loan, 'reject_return', note='Replacement has not arrived yet')
        loan.refresh_from_db()
        self.assertEqual(loan.status, 'active')
        self.stock.refresh_from_db()
        self.assertEqual(self.stock.pack_count, 4)
        self.assertTrue(loan.events.filter(note='Replacement has not arrived yet').exists())

    def test_withdraw_prevents_new_requests_and_pending_approvals(self):
        offer = self.offer()
        pending = self.loan(offer=offer)
        withdraw_offer(project=self.source, user=self.lender, offer_id=offer.pk)
        offer.refresh_from_db()
        self.assertFalse(offer.is_active)
        self.assertEqual(offer.available_quantity, 0)
        with self.assertRaises(ValidationError):
            self.loan(offer=offer, project=self.unrelated, user=self.other)
        with self.assertRaises(ValidationError):
            self.transition(pending, 'approve')

    def test_withdraw_does_not_prevent_repayment_of_an_active_loan(self):
        loan = self.loan()
        self.transition(loan, 'approve')
        withdraw_offer(project=self.source, user=self.lender, offer_id=loan.offer_id)
        self.transition(loan, 'request_return', project=self.destination, user=self.borrower)
        self.transition(loan, 'confirm_return')
        loan.refresh_from_db()
        self.assertEqual(loan.status, 'returned')
        self.stock.refresh_from_db()
        self.assertEqual(self.stock.pack_count, 6)

    def test_other_manager_cannot_withdraw_offer(self):
        offer = self.offer()
        with self.assertRaises(PermissionDenied):
            withdraw_offer(project=self.destination, user=self.borrower, offer_id=offer.pk)
        offer.refresh_from_db()
        self.assertTrue(offer.is_active)

    def test_overdue_only_applies_to_outstanding_loans(self):
        loan = self.loan()
        self.assertFalse(loan.is_overdue)
        self.transition(loan, 'approve')
        BorrowLoan.objects.filter(pk=loan.pk).update(due_date=timezone.localdate() - timedelta(days=1))
        loan.refresh_from_db()
        self.assertTrue(loan.is_overdue)
        self.transition(loan, 'request_return', project=self.destination, user=self.borrower)
        loan.refresh_from_db()
        self.assertTrue(loan.is_overdue)
        self.transition(loan, 'confirm_return')
        loan.refresh_from_db()
        self.assertFalse(loan.is_overdue)

    def test_page_requires_login(self):
        url = self.url()
        self.assertRedirects(
            self.client.get(url), f'{reverse("login")}?{urlencode({"next": url})}',
            fetch_redirect_response=False,
        )

    def test_page_is_manager_only_for_get_and_post(self):
        for user in (self.member, self.editor, self.borrower):
            self.client.force_login(user)
            for method in ('get', 'post'):
                with self.subTest(user=user.username, method=method):
                    response = getattr(self.client, method)(self.url())
                    self.assertEqual(response.status_code, 403)

    def test_inactive_project_cannot_open_exchange(self):
        self.client.force_login(self.lender)
        self.source.is_active = False
        self.source.save(update_fields=['is_active'])
        self.assertIn(self.client.get(self.url()).status_code, (403, 404))

    def test_managers_see_tab_but_team_members_do_not(self):
        inventory_url = reverse('consumables', kwargs={'project_name': self.source.name})
        self.client.force_login(self.lender)
        self.assertContains(self.client.get(inventory_url), self.url())
        self.client.force_login(self.member)
        self.assertNotContains(self.client.get(inventory_url), self.url())

    def test_discovery_shows_only_other_managers_eligible_published_stock(self):
        offer = self.offer()
        self.client.force_login(self.borrower)
        response = self.client.get(self.url(self.destination))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(list(response.context['offers_page']), [offer])
        self.assertContains(response, self.stock.name)
        self.client.force_login(self.lender)
        response = self.client.get(self.url())
        self.assertEqual(list(response.context['offers_page']), [])
        withdraw_offer(project=self.source, user=self.lender, offer_id=offer.pk)
        self.client.force_login(self.borrower)
        self.assertEqual(list(self.client.get(self.url(self.destination)).context['offers_page']), [])

    def test_discovery_does_not_show_unshared_inventory_or_private_notes(self):
        self.client.force_login(self.borrower)
        response = self.client.get(self.url(self.destination))
        self.assertNotContains(response, self.stock.name)
        self.offer()
        response = self.client.get(self.url(self.destination))
        self.assertNotContains(response, self.stock.notes)

    def test_discovery_search_and_category_filters(self):
        offer = self.offer()
        self.client.force_login(self.borrower)
        url = self.url(self.destination)
        self.assertEqual(list(self.client.get(url, {'q': 'filter'}).context['offers_page']), [offer])
        self.assertEqual(list(self.client.get(url, {'q': 'nonexistent'}).context['offers_page']), [])
        self.assertEqual(list(self.client.get(url, {'kind': 'reagent'}).context['offers_page']), [])
        self.assertEqual(list(self.client.get(url, {'kind': 'consumable'}).context['offers_page']), [offer])
        self.assertEqual(list(self.client.get(url, {'source_project': self.source.pk}).context['offers_page']), [offer])
        self.assertEqual(list(self.client.get(url, {'source_project': self.unrelated.pk}).context['offers_page']), [])

    def test_loan_history_is_visible_only_to_participating_projects(self):
        loan = self.loan()
        for user, project, tab in (
            (self.borrower, self.destination, 'borrowing'),
            (self.lender, self.source, 'lending'),
            (self.other, self.unrelated, 'lending'),
        ):
            self.client.force_login(user)
            response = self.client.get(self.url(project), {'tab': tab})
            self.assertEqual(response.status_code, 200)
            if user == self.other:
                self.assertNotContains(response, loan.reference)
            else:
                self.assertContains(response, loan.reference)

    def test_get_with_mutation_parameters_does_not_issue_stock(self):
        loan = self.loan()
        self.client.force_login(self.lender)
        response = self.client.get(self.url(), {'action': 'approve', 'loan_id': loan.pk})
        self.assertEqual(response.status_code, 200)
        loan.refresh_from_db()
        self.stock.refresh_from_db()
        self.assertEqual(loan.status, 'pending')
        self.assertEqual(self.stock.pack_count, 6)

    def test_post_publish_request_approve_and_return_full_workflow(self):
        self.client.force_login(self.lender)
        response = self.client.post(self.url(), {
            'action': 'publish', 'item': f'consumable:{self.stock.pk}',
            'quantity': 3, 'notes': 'Available to other projects', 'tab': 'offers',
        })
        self.assertEqual(response.status_code, 302)
        offer = StockOffer.objects.get()
        self.client.force_login(self.borrower)
        response = self.client.post(self.url(self.destination), {
            'action': 'request', 'offer_id': offer.pk, 'quantity': 2,
            'due_date': self.due.isoformat(), 'purpose': 'Project supply', 'tab': 'borrowing',
        })
        self.assertEqual(response.status_code, 302)
        loan = BorrowLoan.objects.get()
        self.client.force_login(self.lender)
        self.assertEqual(self.client.post(self.url(), {
            'action': 'approve', 'loan_id': loan.pk, 'tab': 'lending',
        }).status_code, 302)
        self.client.force_login(self.borrower)
        self.assertEqual(self.client.post(self.url(self.destination), {
            'action': 'request_return', 'loan_id': loan.pk, 'tab': 'borrowing',
        }).status_code, 302)
        self.client.force_login(self.lender)
        self.assertEqual(self.client.post(self.url(), {
            'action': 'confirm_return', 'loan_id': loan.pk, 'tab': 'lending',
        }).status_code, 302)
        loan.refresh_from_db()
        self.assertEqual(loan.status, 'returned')

    def test_invalid_post_renders_validation_without_stock_changes(self):
        self.client.force_login(self.lender)
        response = self.client.post(self.url(), {
            'action': 'publish', 'item': f'consumable:{self.stock.pk}',
            'quantity': '-3', 'notes': 'Keep this input', 'tab': 'offers',
        })
        self.assertEqual(response.status_code, 400)
        self.assertFalse(StockOffer.objects.exists())
        self.stock.refresh_from_db()
        self.assertEqual(self.stock.pack_count, 6)

    def test_out_of_scope_loan_action_is_denied(self):
        loan = self.loan()
        self.client.force_login(self.other)
        response = self.client.post(self.url(self.unrelated), {
            'action': 'approve', 'loan_id': loan.pk,
        })
        self.assertEqual(response.status_code, 403)
        self.assertNotContains(response, loan.purpose, status_code=403)
        loan.refresh_from_db()
        self.assertEqual(loan.status, 'pending')

    def test_unknown_offer_or_loan_returns_not_found(self):
        self.client.force_login(self.borrower)
        response = self.client.post(self.url(self.destination), {
            'action': 'request', 'offer_id': 999999, 'quantity': 1,
            'due_date': self.due.isoformat(), 'purpose': 'Need supplies',
        })
        self.assertEqual(response.status_code, 404)
        response = self.client.post(self.url(self.destination), {
            'action': 'cancel', 'loan_id': 999999,
        })
        self.assertEqual(response.status_code, 404)

    def test_post_requires_csrf_token(self):
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.lender)
        response = client.post(self.url(), {
            'action': 'publish', 'item': f'consumable:{self.stock.pk}', 'quantity': 1,
        })
        self.assertEqual(response.status_code, 403)
        self.assertFalse(StockOffer.objects.exists())


    def test_csv_history_is_scoped_and_escapes_spreadsheet_formulas(self):
        loan = self.loan()
        BorrowLoan.objects.filter(pk=loan.pk).update(purpose='=HYPERLINK("https://example.invalid")')
        for user, project, tab, present in (
            (self.borrower, self.destination, 'borrowing', True),
            (self.lender, self.source, 'lending', True),
            (self.other, self.unrelated, 'borrowing', False),
            (self.other, self.unrelated, 'lending', False),
        ):
            with self.subTest(user=user.username, tab=tab):
                self.client.force_login(user)
                response = self.client.get(self.url(project), {'tab': tab, 'export': 'csv'})
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response['Content-Type'], 'text/csv; charset=utf-8')
                self.assertIn('attachment;', response['Content-Disposition'])
                content = response.content.decode()
                if present:
                    self.assertIn(loan.reference, content)
                    self.assertIn("'=HYPERLINK", content)
                else:
                    self.assertNotIn(loan.reference, content)
                    self.assertNotIn('HYPERLINK', content)

    def test_source_reagent_with_offer_history_cannot_be_moved_to_trash(self):
        reagent = Reagent.objects.create(
            project=self.source, name='Shared buffer', items_per_pack=10,
            items_left_in_pack=10, pack_count=3, cold_storage='Ambient',
            country_of_origin='Ghana', hazard_level=1,
        )
        self.offer(item=reagent, quantity=2)
        self.client.force_login(self.lender)
        response = self.client.post(reverse('delete_reagent', kwargs={
            'project_name': self.source.name, 'reagent_id': reagent.pk,
        }))
        self.assertEqual(response.status_code, 400)
        self.assertIn('Borrow & Loan', response.json()['error'])
        self.assertTrue(Reagent.objects.filter(pk=reagent.pk).exists())
        self.assertFalse(TrashReagent.objects.filter(project=self.source).exists())

    def test_received_reagent_blocks_entire_bulk_deletion_before_creating_trash(self):
        reagent = Reagent.objects.create(
            project=self.source, name='Shared buffer', items_per_pack=10,
            items_left_in_pack=10, pack_count=3, cold_storage='Ambient',
            country_of_origin='Ghana', hazard_level=1,
        )
        loan = self.loan(offer=self.offer(item=reagent, quantity=2))
        self.transition(loan, 'approve')
        loan.refresh_from_db()
        received = loan.received_reagent
        unrelated_stock = Reagent.objects.create(
            project=self.destination, name='Unrelated stock', items_per_pack=10,
            items_left_in_pack=10, pack_count=1, cold_storage='Ambient',
            country_of_origin='Ghana', hazard_level=1,
        )
        self.client.force_login(self.borrower)
        response = self.client.post(reverse('bulk_delete_reagents', kwargs={
            'project_name': self.destination.name,
        }), {'reagent_ids': [unrelated_stock.pk, received.pk]})
        self.assertEqual(response.status_code, 400)
        self.assertIn('Borrow & Loan', response.json()['error'])
        self.assertTrue(Reagent.objects.filter(pk=received.pk).exists())
        self.assertTrue(Reagent.objects.filter(pk=unrelated_stock.pk).exists())
        self.assertFalse(TrashReagent.objects.filter(project=self.destination).exists())
