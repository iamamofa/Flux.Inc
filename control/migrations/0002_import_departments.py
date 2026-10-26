"""Non-destructive import: preserve existing profile.department text values."""
from django.db import migrations
from django.utils.text import slugify


def import_departments(apps, schema_editor):
    Department = apps.get_model('control', 'Department')
    UserProfile = apps.get_model('inventory', 'UserProfile')
    values = UserProfile.objects.exclude(department='').values_list('department', flat=True).distinct()
    for original in values:
        name = original.strip()
        if not name or Department.objects.filter(name=name).exists():
            continue
        base = (slugify(name)[:43] or 'unit')
        code = base
        i = 2
        while Department.objects.filter(code=code).exists():
            code = f'{base}-{i}'
            i += 1
        Department.objects.create(name=name[:160], code=code)


class Migration(migrations.Migration):
    dependencies = [('control', '0001_initial'), ('inventory', '0001_initial')]
    operations = [migrations.RunPython(import_departments, migrations.RunPython.noop)]
