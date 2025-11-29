# core/logging.py
import logging
from .utils import get_current_request

class TraceLogger(logging.Logger):
    def _log(self, level, msg, args, **kwargs):
        request = get_current_request()
        if request and hasattr(request, 'trace_id'):
            kwargs.setdefault('extra', {}).update(
                trace_id=request.trace_id
            )
        super()._log(level, msg, args, **kwargs)

logging.setLoggerClass(TraceLogger)
