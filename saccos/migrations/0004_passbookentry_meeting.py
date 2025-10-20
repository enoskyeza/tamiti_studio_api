# Generated migration

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('saccos', '0003_subscriptionplan_saccosubscription_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='passbookentry',
            name='meeting',
            field=models.ForeignKey(blank=True, help_text='Link to the weekly meeting where this transaction occurred', null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='passbook_entries', to='saccos.weeklymeeting'),
        ),
    ]
