# utils/decorators.py
def log_perf(view_func):
    @wraps(view_func)
    def wrapped(request, *args, **kwargs):
        start = time.time()
        response = view_func(request, *args, **kwargs)
        logger.info(
            "View timing",
            extra={
                'duration_ms': (time.time() - start) * 1000,
                'view': view_func.__name__
            }
        )
        return response
    return wrapped
