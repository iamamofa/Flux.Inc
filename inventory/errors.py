"""Readable workspace errors, with JSON preserved for API and fetch clients."""
from django.http import JsonResponse
from django.shortcuts import render
from django.urls import reverse
from django.utils.cache import patch_vary_headers


ERROR_CONTENT = {
    400: ('CHECK YOUR DETAILS', 'A few details need another look.',
          'We couldn’t complete this request with the information provided.',
          'Return to the page, check your details and try again.'),
    403: ('ACCESS & PERMISSIONS', 'You don’t have access to this project',
          'Your account doesn’t have permission to open this page or complete this action.',
          'Ask the project manager to review your access, or return to Flux.'),
    404: ('PAGE NOT FOUND', 'This page is out of reach.',
          'The link may have changed, or this page or record may no longer be available.',
          'Check the address or return to Flux to find your workspace.'),
    405: ('ACTION UNAVAILABLE', 'This action needs a different approach.',
          'This page can’t complete the request in this way.',
          'Return to the page and use its buttons to continue.'),
    409: ('REQUEST CONFLICT', 'This action is already accounted for.',
          'The request conflicts with an existing record or a recent change.',
          'Review the current details before trying again.'),
    410: ('LINK EXPIRED', 'This link has reached its end.',
          'This invitation or resource is no longer available.',
          'Ask the project manager for a new link.'),
    429: ('PLEASE WAIT', 'Let’s give that a moment.',
          'There have been too many requests in a short time.',
          'Wait a little before trying again.'),
    500: ('SOMETHING WENT WRONG', 'We couldn’t finish that request.',
          'Flux ran into a problem while opening this page or completing this action.',
          'Return to your workspace. If the problem continues, contact your administrator.'),
    503: ('TEMPORARILY UNAVAILABLE', 'We’ll be ready again soon.',
          'This part of Flux is temporarily unavailable.',
          'Please try again in a little while.'),
}
TEAM_ACTIONS = {'invite_project_user', 'add_user_to_project', 'remove_user', 'edit_user_access'}
TOOL_ACTIONS = {
    'equipment_booking': ('equipment-bookings', 'Back to equipment bookings'),
    'record_temperature': ('cold-chain', 'Back to cold chain'),
    'procurement_request': ('purchasing', 'Back to purchasing'),
    'bulk_import_reagents': ('spreadsheet-import', 'Back to spreadsheet import'),
    'bulk_import_reagents_multi': ('spreadsheet-import', 'Back to spreadsheet import'),
}


def wants_html_error(request):
    """Only document requests opt in; fetch's default */* must remain JSON."""
    accept = request.headers.get('Accept', '').lower()
    return (
        request.headers.get('X-Requested-With', '').lower() != 'xmlhttprequest'
        and 'application/json' not in accept
        and 'text/html' in accept
        and request.headers.get('Sec-Fetch-Dest', 'document') in ('', 'document', 'iframe')
    )


def render_error_page(request, status=500, message=None, title=None):
    eyebrow, default_title, default_message, hint = ERROR_CONTENT.get(status, ERROR_CONTENT[500])
    # Server failures never include exception text or data from response bodies.
    if status >= 500:
        message, title = None, None
    view = getattr(request, 'resolver_match', None)
    view_name = getattr(view, 'url_name', '')
    project_name = getattr(view, 'kwargs', {}).get('project_name')
    primary_url, primary_label = reverse('home'), 'Return to Flux'
    secondary_url, secondary_label = None, None
    if view_name in TEAM_ACTIONS and project_name and status in (400, 405, 409):
        primary_url = reverse('team', kwargs={'project_name': project_name})
        primary_label = 'Back to team'
        secondary_url, secondary_label = reverse('home'), 'Return to Flux'
    elif view_name in TOOL_ACTIONS and project_name and status in (400, 405, 409):
        section, primary_label = TOOL_ACTIONS[view_name]
        primary_url = reverse('genomics_hub', kwargs={'project_name': project_name}) + '#' + section
        secondary_url, secondary_label = reverse('home'), 'Return to Flux'
    if status == 409 and message:
        if 'already belongs to the project' in message or 'already part of the project' in message:
            title = title or 'Already on the team'
            hint = 'This person already has project access. Review their current role in the member directory.'
        elif 'pending invitation already exists' in message:
            title = title or 'An invitation is already on its way.'
            hint = 'Review the pending invitations on your team page before sending another.'
        elif view_name == 'equipment_booking':
            title = title or 'This equipment slot is unavailable.'
            hint = 'Review the upcoming bookings and choose another time for your reservation.'
    response = render(request, 'inventory/error_page.html', {
        'status_code': status, 'error_eyebrow': eyebrow,
        'error_title': title or default_title, 'error_message': message or default_message,
        'error_hint': hint, 'primary_url': primary_url, 'primary_label': primary_label,
        'secondary_url': secondary_url, 'secondary_label': secondary_label,
        'reference': getattr(request, 'trace_id', None),
    }, status=status)
    response['X-Flux-Error-Page'] = '1'
    response['Cache-Control'] = 'private, no-store'
    patch_vary_headers(response, ('Accept', 'X-Requested-With', 'Sec-Fetch-Dest'))
    return response


def error_response(request, message, status=400, payload=None):
    if wants_html_error(request):
        return render_error_page(request, status=status, message=message)
    response = JsonResponse(payload if payload is not None else {
        'success': False, 'message': message,
    }, status=status)
    patch_vary_headers(response, ('Accept', 'X-Requested-With', 'Sec-Fetch-Dest'))
    response['Cache-Control'] = 'private, no-store'
    return response


def csrf_failure(request, reason=''):
    # The internal CSRF reason stays in Django's log, not in the user-facing page.
    message = 'Your form session has expired or could not be verified. Return to the page, refresh it and try again.'
    if wants_html_error(request):
        response = render_error_page(request, status=403, message=message, title='Let’s refresh your session.')
    else:
        response = error_response(request, message, status=403, payload={'error': message, 'success': False, 'message': message})
    return response
