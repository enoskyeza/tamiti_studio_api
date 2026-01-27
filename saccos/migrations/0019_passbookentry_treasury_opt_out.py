from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('saccos', '0018_passbookentry_sacco_transaction'),
    ]

    operations = [
        migrations.AddField(
            model_name='passbookentry',
            name='treasury_opt_out',
            field=models.BooleanField(default=False),
        ),
    ]
