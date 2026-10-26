"""Friendly admin-only error pages. Legacy site retains Django default handling."""
from django.shortcuts import render
from django.views import defaults


def permission_denied(request, exception):
    if request.path.startswith('/control/'):
        return render(request, 'control/error_access.html', status=403)
    return defaults.permission_denied(request, exception)


def not_found(request, exception):
    if request.path.startswith('/control/'):
        return render(request, 'control/error_404.html', status=404)
    return defaults.page_not_found(request, exception)
