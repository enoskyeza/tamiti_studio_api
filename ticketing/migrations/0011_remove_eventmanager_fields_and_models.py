# Generated manually to remove EventManager fields and models after constraints are removed

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('ticketing', '0010_remove_eventmanager_constraints'),
    ]

    operations = [
        # Remove fields from EventManager
        migrations.RemoveField(
            model_name='eventmanager',
            name='assigned_by',
        ),
        migrations.RemoveField(
            model_name='eventmanager',
            name='event',
        ),
        migrations.RemoveField(
            model_name='eventmanager',
            name='temp_user',
        ),
        migrations.RemoveField(
            model_name='eventmanager',
            name='user',
        ),
        # Delete models
        migrations.DeleteModel(
            name='BatchManager',
        ),
        migrations.DeleteModel(
            name='EventManager',
        ),
    ]
