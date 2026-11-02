"""Friendly errors for research workspaces and administration."""
from django.shortcuts import render
from django.contrib import admin
from django.views import defaults
from inventory.errors import render_error_page, wants_html_error


def permission_denied(request, exception):
    if request.path.startswith('/control/'):
        return render(request, 'control/error_access.html', status=403)
    if request.path.startswith('/admin/'):
        return render(request, 'admin/status.html', {
            **admin.site.each_context(request), 'status_code': 403,
            'title': 'Access is restricted.',
            'status_message': 'Your account does not have permission to open this administration resource. Ask an administrator to review your assigned access.',
        }, status=403)
    if wants_html_error(request):
        return render_error_page(request, status=403)
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
    if wants_html_error(request):
        return render_error_page(request, status=404)
    return defaults.page_not_found(request, exception)


def bad_request(request, exception):
    if not request.path.startswith(('/control/', '/admin/')) and wants_html_error(request):
        return render_error_page(request, status=400)
    return defaults.bad_request(request, exception)


def server_error(request):
    if not request.path.startswith(('/control/', '/admin/')) and wants_html_error(request):
        return render_error_page(request, status=500)
    return defaults.server_error(request)
