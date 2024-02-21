from django.contrib import admin

from .models import *

admin.site.register(Project)
admin.site.register(Consumable)
admin.site.register(Reagent)
admin.site.register(Equipment)
admin.site.register(Sample)
admin.site.register(TrashConsumable)
admin.site.register(TrashReagent)
admin.site.register(TrashEquipment)
admin.site.register(TrashSample)
admin.site.register(UserProfile)
admin.site.register(UserApplication)
admin.site.register(Log)

