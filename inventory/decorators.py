from functools import wraps
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from .models import Project, Reagent


def project_access_required(view_func):
    """Decorator to check if user has access to a project"""
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        project_name = kwargs.get('project_name')

        if project_name:
            project = get_object_or_404(Project, name=project_name)

            # Check access
            if not (request.user == project.project_manager or 
                    request.user in project.project_editors.all() or
                    request.user in project.project_members.all()):

                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return JsonResponse({'error': 'Unauthorized access'}, status=403)
                else:
                    # Redirect to appropriate error page
                    from django.shortcuts import render
                    return render(request, 'inventory/403.html', status=403)

        return view_func(request, *args, **kwargs)
    return _wrapped_view


def reagent_access_required(view_func):
    """Decorator to check if user has access to a specific reagent"""
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        reagent_id = kwargs.get('id')

        if reagent_id:
            reagent = get_object_or_404(Reagent, id=reagent_id)

            if not (request.user == reagent.project.project_manager or
                    request.user in reagent.project.project_editors.all() or
                    request.user in reagent.project.project_members.all()):

                return JsonResponse({'error': 'Unauthorized access'}, status=403)

        return view_func(request, *args, **kwargs)
    return _wrapped_view
