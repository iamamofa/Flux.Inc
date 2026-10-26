from django.db.models import Q

from .models import Project


def admin_dashboard_projects(request):
    if (
        not request.path.startswith('/admin/')
        or not request.user.is_authenticated
        or not request.user.has_perm('inventory.view_project')
    ):
        return {'admin_dashboard_projects': ()}

    projects = Project.objects.filter(is_active=True).filter(
        Q(project_manager=request.user)
        | Q(project_editors=request.user)
        | Q(project_members=request.user)
    ).distinct().order_by('name')
    return {'admin_dashboard_projects': projects}
