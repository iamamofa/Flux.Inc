from django.urls import path, reverse_lazy
from django.contrib.auth import views as auth_views
from . import views

app_name = 'control'
urlpatterns = [
    path('', views.overview, name='overview'),
    path('users/', views.users, name='users'),
    path('users/create/', views.user_create, name='user_create'),
    path('users/<int:pk>/', views.user_detail, name='user_detail'),
    path('users/<int:pk>/edit/', views.user_edit, name='user_edit'),
    path('users/<int:pk>/status/', views.user_status, name='user_status'),
    path('users/<int:pk>/roles/', views.assign_role, name='assign_role'),
    path('users/<int:pk>/staff/', views.user_staff_access, name='user_staff_access'),
    path('users/<int:pk>/reset-password/', views.request_password_reset, name='request_password_reset'),
    path('roles/', views.roles, name='roles'),
    path('roles/create/', views.group_form, name='role_create'),
    path('roles/<int:pk>/edit/', views.group_form, name='role_edit'),
    path('departments/', views.departments, name='departments'),
    path('departments/create/', views.department_form, name='department_create'),
    path('departments/<int:pk>/edit/', views.department_form, name='department_edit'),
    path('notifications/', views.notifications, name='notifications'),
    path('notifications/<int:pk>/read/', views.notification_read, name='notification_read'),
    path('notifications/read-all/', views.notifications_read_all, name='notifications_read_all'),
    path('audit/', views.audit_logs, name='audit'),
    path('settings/', views.portal_settings, name='settings'),
    path('profile/', views.profile, name='profile'),
    path('security/', views.security, name='security'),
    path('auth/reset/<uidb64>/<token>/', auth_views.PasswordResetConfirmView.as_view(
        template_name='control/reset_confirm.html',
        success_url=reverse_lazy('control:reset_complete')), name='password_reset_confirm'),
    path('auth/reset/complete/', auth_views.PasswordResetCompleteView.as_view(
        template_name='control/reset_complete.html'), name='reset_complete'),
    path('reports/', views.reports, name='reports'),
    path('cold-chain/', views.cold_chain_audit, name='cold_chain_audit'),
    path('reports/<str:report>.csv', views.report_csv, name='report_csv'),
    path('search/', views.search, name='search'),
]
