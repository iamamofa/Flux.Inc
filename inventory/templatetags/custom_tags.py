from django import template

register = template.Library()

@register.filter
def user_in_group(user, group_name):
    return user.groups.filter(name=group_name).exists()


@register.filter
def admin_label(value):
    """Readable admin labels without changing legacy model or database names."""
    labels = {
        'Portal settingss': 'Portal settings',
        'Low stock email deliverys': 'Low-stock email deliveries',
        'Roomss': 'Rooms',
        'Sample_ locationss': 'Sample locations',
        'Storagess': 'Storage locations',
    }
    return labels.get(str(value), value)
