import logging
import time

perf_logger = logging.getLogger('django.performance')


def log_performance(view_func):
    """Decorator for view timing"""
    def wrapped(request, *args, **kwargs):
        start = time.time()
        response = view_func(request, *args, **kwargs)
        duration = int((time.time() - start) * 1000)

        perf_logger.info(
            "View Timing",
            extra={
                'trace_id': getattr(request, 'trace_id', 'none'),
                'view': view_func.__name__,
                'duration_ms': duration,
                'user': request.user.username or 'anon'
            }
        )
        return response
    return wrapped
