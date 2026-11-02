"""Browser failures are readable while programmatic clients keep JSON contracts."""
from django.contrib.auth.models import AnonymousUser, User
from django.http import HttpResponse, JsonResponse
from django.test import Client, RequestFactory, SimpleTestCase, TestCase, override_settings
from django.urls import resolve, reverse

from .middleware import FriendlyErrorMiddleware
from .models import Project, ProjectInvitation


HTML_HEADERS = {
    'HTTP_ACCEPT': 'text/html,application/xhtml+xml',
    'HTTP_SEC_FETCH_DEST': 'document',
    'HTTP_SEC_FETCH_MODE': 'navigate',
}


class BrowserErrorPageTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.manager = User.objects.create_user(
            username='error-page-manager', email='manager@example.invalid',
        )
        cls.member = User.objects.create_user(
            username='error-page-member', email='member@example.invalid',
        )
        cls.outside_user = User.objects.create_user(
            username='error-page-outsider', email='outside@example.invalid',
        )
        cls.project = Project.objects.create(
            name='Error page project', project_manager=cls.manager,
        )
        cls.project.project_members.add(cls.member)

    def setUp(self):
        self.client.force_login(self.manager)
        self.invite_url = reverse('invite_project_user', args=[self.project.name])
        self.duplicate_payload = {'email': self.member.email, 'role': 'researcher'}

    def test_browser_duplicate_invitation_has_context_and_safe_recovery(self):
        response = self.client.post(
            self.invite_url, self.duplicate_payload,
            HTTP_REFERER='https://attacker.invalid/untrusted-return', **HTML_HEADERS,
        )
        self.assertEqual(response.status_code, 409)
        self.assertTrue(response['Content-Type'].startswith('text/html'))
        self.assertContains(response, 'Already on the team', status_code=409)
        self.assertContains(
            response, 'This account already belongs to the project.', status_code=409,
        )
        self.assertContains(response, 'Back to team', status_code=409)
        self.assertContains(
            response, reverse('team', args=[self.project.name]), status_code=409,
        )
        self.assertNotContains(response, 'https://attacker.invalid', status_code=409)
        self.assertEqual(ProjectInvitation.objects.count(), 0)

    def test_invitation_json_contract_survives_all_programmatic_request_styles(self):
        variants = (
            {},
            {'HTTP_ACCEPT': '*/*'},
            {'HTTP_ACCEPT': 'application/json'},
            {'HTTP_ACCEPT': 'text/html,application/json'},
            {'HTTP_ACCEPT': 'text/html', 'HTTP_X_REQUESTED_WITH': 'XMLHttpRequest'},
        )
        for headers in variants:
            with self.subTest(headers=headers):
                response = self.client.post(
                    self.invite_url, self.duplicate_payload, **headers,
                )
                self.assertEqual(response.status_code, 409)
                self.assertEqual(response.json(), {
                    'success': False,
                    'message': 'This account already belongs to the project.',
                })

    def test_project_access_rejection_is_a_readable_browser_page(self):
        self.client.force_login(self.outside_user)
        url = reverse('trash_reagents', args=[self.project.name])
        response = self.client.get(url, **HTML_HEADERS)
        self.assertEqual(response.status_code, 403)
        self.assertContains(
            response, 'You don’t have access to this project', status_code=403,
        )
        self.assertTrue(response['Content-Type'].startswith('text/html'))
        self.assertNotContains(response, '{"error":', status_code=403)

    def test_project_access_rejection_remains_json_for_ajax(self):
        self.client.force_login(self.outside_user)
        response = self.client.get(
            reverse('trash_reagents', args=[self.project.name]),
            HTTP_ACCEPT='text/html', HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json(), {'error': 'Unauthorized access'})

    @override_settings(DEBUG=False, ALLOWED_HOSTS=['testserver'])
    def test_unknown_browser_url_uses_the_friendly_not_found_handler(self):
        response = self.client.get('/this-flux-page-does-not-exist/', **HTML_HEADERS)
        self.assertEqual(response.status_code, 404)
        self.assertTrue(response['Content-Type'].startswith('text/html'))
        self.assertEqual(response.get('X-Flux-Error-Page'), '1')
        self.assertContains(response, 'Flux', status_code=404)
        self.assertNotContains(response, 'Page not found at', status_code=404)

    def test_csrf_rejection_has_the_same_browser_error_treatment(self):
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.manager)
        response = client.post(self.invite_url, self.duplicate_payload, **HTML_HEADERS)
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.get('X-Flux-Error-Page'), '1')
        self.assertTrue(response['Content-Type'].startswith('text/html'))
        self.assertEqual(ProjectInvitation.objects.count(), 0)


class FriendlyErrorMiddlewareTests(SimpleTestCase):
    def request(self, path='/team/project/invite/', **headers):
        request = RequestFactory().post(path, **{**HTML_HEADERS, **headers})
        request.user = AnonymousUser()
        return request

    def test_unhandled_browser_json_failure_becomes_an_html_page(self):
        original = JsonResponse({'error': 'Choose a valid record.'}, status=400)
        response = FriendlyErrorMiddleware(lambda request: original)(self.request())
        self.assertEqual(response.status_code, 400)
        self.assertTrue(response['Content-Type'].startswith('text/html'))
        self.assertEqual(response.get('X-Flux-Error-Page'), '1')
        self.assertIn('A few details need another look.', response.content.decode())
        self.assertNotIn('{"error":', response.content.decode())

    def test_server_failures_do_not_expose_internal_json_details(self):
        detail = 'Database password=private-value; internal traceback'
        original = JsonResponse({'error': detail}, status=500)
        response = FriendlyErrorMiddleware(lambda request: original)(self.request())
        self.assertEqual(response.status_code, 500)
        self.assertTrue(response['Content-Type'].startswith('text/html'))
        self.assertNotIn(detail, response.content.decode())
        self.assertNotIn('private-value', response.content.decode())

    def test_method_not_allowed_keeps_its_allow_header(self):
        original = JsonResponse({'error': 'Use POST to save this record.'}, status=405)
        original['Allow'] = 'POST'
        response = FriendlyErrorMiddleware(lambda request: original)(self.request())
        self.assertEqual(response.status_code, 405)
        self.assertEqual(response['Allow'], 'POST')
        self.assertTrue(response['Content-Type'].startswith('text/html'))

    def test_plain_html_sentence_gets_a_page_and_returns_to_its_tool(self):
        url = reverse('equipment_booking', args=['Project'])
        request = self.request(url)
        request.resolver_match = resolve(url)
        original = HttpResponse('That equipment slot is unavailable.', status=409)
        response = FriendlyErrorMiddleware(lambda request: original)(request)
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.get('X-Flux-Error-Page'), '1')
        self.assertIn('This equipment slot is unavailable.', response.content.decode())
        self.assertIn(
            reverse('genomics_hub', args=['Project']) + '#equipment-bookings',
            response.content.decode(),
        )

    def test_default_and_json_fetches_keep_original_response_bodies(self):
        for accept in ('', '*/*', 'application/json', 'text/html,application/json'):
            with self.subTest(accept=accept):
                original = JsonResponse({'error': 'JSON client error'}, status=409)
                request = self.request(HTTP_ACCEPT=accept)
                response = FriendlyErrorMiddleware(lambda request: original)(request)
                self.assertEqual(response.status_code, 409)
                self.assertEqual(response.content, original.content)
                self.assertTrue(response['Content-Type'].startswith('application/json'))

    def test_admin_control_and_asset_paths_are_left_to_their_own_handlers(self):
        for path in ('/admin/private/', '/control/private/', '/static/missing.css', '/media/missing.pdf'):
            with self.subTest(path=path):
                original = JsonResponse({'error': 'Existing specialized error'}, status=403)
                response = FriendlyErrorMiddleware(lambda request: original)(self.request(path))
                self.assertEqual(response.content, original.content)
                self.assertTrue(response['Content-Type'].startswith('application/json'))

    def test_already_styled_responses_are_not_wrapped_again(self):
        original = JsonResponse({'error': 'Already styled response'}, status=409)
        original['X-Flux-Error-Page'] = '1'
        response = FriendlyErrorMiddleware(lambda request: original)(self.request())
        self.assertEqual(response.content, original.content)
