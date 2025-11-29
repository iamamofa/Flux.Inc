# middleware.py
import uuid
import time
import logging

security_logger = logging.getLogger('django.security')


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
