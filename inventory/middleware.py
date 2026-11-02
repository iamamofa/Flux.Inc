# middleware.py
import uuid
import time
import logging
import json

from .errors import ERROR_CONTENT, TEAM_ACTIONS, render_error_page, wants_html_error

security_logger = logging.getLogger('django.security')


class FriendlyErrorMiddleware:
    """Turn document-level JSON/plain failures into a useful workspace page."""
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        status = response.status_code
        if (
            status not in ERROR_CONTENT
            or response.has_header('X-Flux-Error-Page')
            or response.streaming
            or request.path.startswith(('/admin/', '/control/', '/static/', '/media/'))
            or not wants_html_error(request)
        ):
            return response
        content_type = response.get('Content-Type', '').split(';', 1)[0].strip()
        is_json = content_type == 'application/json' or content_type.endswith('+json')
        # HttpResponse defaults to text/html even for a single plain sentence.
        prefix = response.content[:500].lstrip().lower()
        is_bare_html = content_type == 'text/html' and not (
            prefix.startswith(b'<!doctype') or b'<html' in prefix
        )
        if not (is_json or content_type == 'text/plain' or is_bare_html or status in (404, 500, 503)):
            return response
        message = None
        view_name = getattr(getattr(request, 'resolver_match', None), 'url_name', '')
        # Team messages are written for users. Other legacy bodies can contain
        # exception details, so their document fallback uses safe, generic copy.
        if is_json and status < 500 and view_name in TEAM_ACTIONS:
            try:
                body = json.loads(response.content)
                candidate = body.get('message') if isinstance(body, dict) else None
                if isinstance(candidate, str) and len(candidate) <= 500:
                    message = candidate
            except (ValueError, UnicodeDecodeError):
                pass
        if status == 409 and view_name == 'equipment_booking':
            message = 'That equipment slot is unavailable.'
        page = render_error_page(request, status=status, message=message)
        for header in ('Allow', 'Retry-After'):
            if response.has_header(header):
                page[header] = response[header]
        return page


class AuditMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Generate trace ID
        request.trace_id = uuid.uuid4().hex[:8] # Short for readability

        # Security audit
        start_time = time.time()
        response = self.get_response(request)
        duration = int((time.time() - start_time) * 1000) # ms

        # Security logging
        if response.status_code >= 400:
            security_logger.warning(
                    "Security Event",
                    extra={
                        'trace_id': request.trace_id,
                        'path': request.path,
                        'status': response.status_code,
                        'ip': request.META.get('REMOTE_ADDR'),
                        'duration_ms': duration
                    }
                )
        return response
