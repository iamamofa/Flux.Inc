from django.db.models import F
from django.urls import reverse

from .models import Consumable, Reagent, Sample


def get_low_stock_alerts(project):
    alerts = []
    for model, route_name, category, quantity_field, unit_field in (
        (Consumable, 'consumables', 'Consumable', 'pack_count', None),
        (Reagent, 'reagents', 'Reagent', 'pack_count', None),
        (Sample, 'samples', 'Sample', 'volume', 'volume_unit'),
    ):
        comparison_field = 'volume' if model is Sample else 'pack_count'
        items = model.objects.filter(
            project=project,
            is_active=True,
            threshold_value__isnull=False,
            **{f'{comparison_field}__lt': F('threshold_value')}
        )
        for item in items:
            alerts.append({
                'name': item.sample_id if model is Sample else item.name,
                'category': category,
                'quantity': getattr(item, quantity_field),
                'unit': getattr(item, unit_field) if unit_field else 'packs',
                'threshold': item.threshold_value,
                'url': reverse(route_name, kwargs={'project_name': project.name}),
            })
    return alerts
