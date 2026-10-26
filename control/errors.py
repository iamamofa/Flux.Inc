"""Friendly admin-only error pages. Legacy site retains Django default handling."""
from django.shortcuts import render
from django.contrib import admin
from django.views import defaults


def permission_denied(request, exception):
    if request.path.startswith('/control/'):
        return render(request, 'control/error_access.html', status=403)
    if request.path.startswith('/admin/'):
        return render(request, 'admin/status.html', {
            **admin.site.each_context(request), 'status_code': 403,
            'title': 'Access is restricted.',
            'status_message': 'Your account does not have permission to open this administration resource. Ask an administrator to review your assigned access.',
        }, status=403)
    return defaults.permission_denied(request, exception)


def not_found(request, exception):
    if request.path.startswith('/control/'):
        return render(request, 'control/error_404.html', status=404)
    if request.path.startswith('/admin/'):
        return render(request, 'admin/status.html', {
            **admin.site.each_context(request), 'status_code': 404,
            'title': 'This record is out of reach.',
            'status_message': 'The page may have moved, or the record may no longer be available. Return to administration to find the records you need.',
        }, status=404)
    return defaults.page_not_found(request, exception)
