from django.urls import path
from . import views
from .decorators import project_access_required, reagent_access_required


# Reagent URLs
reagent_urlpatterns = [
    path('reagents/<str:project_name>/',
         project_access_required(views.reagents),
         name="reagents"),

    path('dashboard/reagents/<str:project_name>/',
         project_access_required(views.dashboard_reagents),
         name="dashboard_reagents"),

    path('add_reagent/<str:project_name>',
         project_access_required(views.add_reagent),
         name='add_reagent'),

    path('delete_reagent/<str:project_name>/<str:reagent_id>/',
         project_access_required(views.delete_reagent),
         name="delete_reagent"),

    path('get_reagent_info/<int:id>',
         reagent_access_required(views.get_reagent_info),
         name='get_reagent_info'),

    path('edit_reagent/<int:reagent_id>',
         reagent_access_required(views.edit_reagent),
         name='edit_reagent'),

    path('retrieve_reagent/<int:reagent_id>',
         reagent_access_required(views.retrieve_reagent),
         name='retrieve_reagent'),

    path('restock_reagent/<int:reagent_id>',
         reagent_access_required(views.restock_reagent),
         name='return_reagent'),

    path('export_reagent_csv/<str:project_name>',
         project_access_required(views.export_reagent_csv),
         name='export_reagent_csv'),

    path('export_reagent_excel/<str:project_name>',
         project_access_required(views.export_reagent_excel),
         name='export_reagent_excel'),

    path('export_reagent_txt/<str:project_name>',
         project_access_required(views.export_reagent_txt),
         name='export_reagent_txt'),

    path('trash_reagents/<str:project_name>/',
         project_access_required(views.trash_reagents),
         name="trash_reagents"),

    path('trash/restore_reagent/<str:project_name>/<int:trash_id>/',
         project_access_required(views.restore_reagent),
         name='restore_trash_reagent'),

    path('trash/delete_trash_reagent/<int:trash_id>/',
         project_access_required(views.delete_trash_reagent),
         name="delete_trash_reagent"),

    path('trash/empty_reagent_trash/<str:project_name>',
         project_access_required(views.empty_reagent_trash),
         name='delete_all_reagents_in_trash'),

    path('reagents/<int:reagent_id>/msds/',
         reagent_access_required(views.reagent_msds_files),
         name='reagent_msds_files'),

    path('msds/<int:msds_id>/download/',
         project_access_required(views.download_msds),
         name='download_msds'),

    path('msds/<int:msds_id>/delete/',
         project_access_required(views.delete_msds),
         name='delete_msds'),

    path('reagents/<str:project_name>/<int:reagent_id>/upload-msds/',
         project_access_required(views.upload_msds),
         name='upload_msds'),

    # Bulk operations
    path('reagents/<str:project_name>/bulk-delete/',
         project_access_required(views.bulk_delete_reagents),
         name='bulk_delete_reagents'),

    path('reagents/<str:project_name>/bulk-export/',
         project_access_required(views.bulk_export_reagents),
         name='bulk_export_reagents'),
]

urlpatterns = [
    path('', views.home, name='home'),
    path('registration/', views.registration_page, name='registration_page'),
    path('user_application/', views.user_application, name='user_application'),
    path('register/project-manager/', views.register_project_manager, name='register_project_manager'),
    path('register/user/', views.register_user, name='register_user'),
    path('change_password/', views.change_password, name='change_password'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logoutUser, name ="logout"),
    path('create_project/', views.create_project, name='create_project'),
    path('team/<str:project_name>/', views.team, name ="team"),
    path('log/<str:project_name>/', views.log, name ="log"),
    path('add_user_to_project/<str:project_name>', views.add_user_to_project, name='add_user_to_project'),
    path('edit_user_access/<str:project_name>/<int:id>/', views.edit_user_access, name='edit_user_access'),
    path('remove_user/<str:project_name>/<int:id>/', views.remove_user, name = "remove_user"),
    path('consumables/<str:project_name>/', views.consumables, name ="consumables"),
    path('dashboard/consumables/<str:project_name>/', views.dashboard_consumables, name ="dashboard_consumables"),
    path('add_consumable/<str:project_name>', views.add_consumable, name='add_consumable'),
    path('delete_consumable/<str:project_name>/<str:pk>/', views.delete_consumable, name = "delete_consumable"),
    path('get_consumable_info/<int:id>', views.get_consumable_info, name='get_consumable_info'),
    path('edit_consumable/<int:id>', views.edit_consumable, name='edit_consumable'),
    path('retrieve_consumable/<int:consumable_id>', views.retrieve_consumable, name='retrieve_consumable'),
    path('restock_consumable/<int:consumable_id>', views.restock_consumable, name='return_consumable'),
    path('export_consumable_csv/<str:project_name>', views.export_consumable_csv, name='export_consumable_csv'),
    path('export_consumable_excel/<str:project_name>', views.export_consumable_excel, name='export_consumable_excel'),
    path('export_consumable_txt/<str:project_name>', views.export_consumable_txt, name='export_consumable_txt'),
    path('trash_consumables/<str:project_name>/', views.trash_consumables, name ="trash_consumables"),
    path('trash/restoreConsumable/<str:project_name>/<int:trash_id>/', views.restore_consumable, name='restore_trash_consumable'),
    path('trash/delete_trash_consumable/<int:trash_id>/', views.delete_trash_consumable, name = "delete_trash_consumable"),
    path('trash/deleteAllConsumables/<str:project_name>', views.empty_consumable_trash, name='delete_all_consumables_in_trash'),
    path('equipment_/<str:project_name>/', views.equipment_, name ="equipment_"),
    path('dashboard/equipment_/<str:project_name>/', views.dashboard_equipment_, name ="dashboard_equipment_"),
    path('add_equipment/<str:project_name>', views.add_equipment_, name='add_equipment'),
    path('delete_equipment/<str:project_name>/<str:equipment_id>/', views.delete_equipment, name = "delete_equipment"),
    path('get_equipment_info/<int:id>', views.get_equipment_info, name='get_equipment_info'),
    path('edit_equipment/<int:equipment_id>', views.edit_equipment_, name='edit_equipment'),
    #path('retrieve_equipment/<int:equipment_id>', views.retrieve_equipment, name='retrieve_equipment'),
    #path('restock_equipment/<int:equipment_id>', views.restock_equipment, name='return_equipment'),
    path('export_equipment_csv/<str:project_name>', views.export_equipment_csv, name='export_equipment_csv'),
    path('export_equipment_excel/<str:project_name>', views.export_equipment_excel, name='export_equipment_excel'),
    #path('export_equipment_txt/<str:project_name>', views.export_equipment_txt, name='export_equipment_txt'),
    path('trash_equipment_/<str:project_name>/', views.trash_equipment_, name ="trash_equipment_"),
    path('trash/restoreEquipment/<str:project_name>/<int:trash_id>/', views.restore_equipment, name='restore_trash_equipment'),
    path('trash/delete_trash_equipment/<int:trash_id>/', views.delete_trash_equipment, name = "delete_trash_equipment"),
    path('trash/empty_equipment_trash/<str:project_name>', views.empty_equipment_trash, name='delete_all_equipment__in_trash'),
    path('samples/<str:project_name>/', views.samples, name ="samples"),
    path('dashboard/samples/<str:project_name>/', views.dashboard_samples, name ="dashboard_samples"),
    path('add_sample/<str:project_name>', views.add_sample, name='add_sample'),
    path('delete_sample/<str:project_name>/<str:sample_id>/', views.delete_sample, name = "delete_sample"),
    path('get_sample_info/<int:id>', views.get_sample_info, name='get_sample_info'),
    path('edit_sample/<int:sample_id>', views.edit_sample, name='edit_sample'),
    path('retrieve_sample/<int:sample_id>', views.retrieve_sample, name='retrieve_sample'),
    path('return_sample/<int:sample_id>', views.restock_sample, name='return_sample'),
    path('export_sample_csv/<str:project_name>', views.export_sample_csv, name='export_sample_csv'),
    path('export_sample_excel/<str:project_name>', views.export_sample_excel, name='export_sample_excel'),
    path('export_sample_txt/<str:project_name>', views.export_sample_txt, name='export_sample_txt'),
    path('trash_samples/<str:project_name>/', views.trash_samples, name ="trash_samples"),
    path('trash/restore_sample/<str:project_name>/<int:trash_id>/', views.restore_sample, name='restore_trash_sample'),
    path('trash/delete_trash_sample/<int:trash_id>/', views.delete_trash_sample, name = "delete_trash_sample"),
    path('trash/empty_sample_trash/<str:project_name>', views.empty_sample_trash, name='delete_all_samples_in_trash'),

    # Reagents
    *reagent_urlpatterns,
]
