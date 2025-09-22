# Generated manually to fix constraint removal issue

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('ticketing', '0009_add_permission_denied_scan_result'),
    ]

    operations = [
        # Remove all constraints from EventManager before removing fields
        migrations.RemoveConstraint(
            model_name='eventmanager',
            name='exactly_one_user_type',
        ),
        migrations.RemoveConstraint(
            model_name='eventmanager',
            name='unique_regular_user_per_event',
        ),
        migrations.RemoveConstraint(
            model_name='eventmanager',
            name='unique_temp_user_per_event_manager',
        ),
    ]
