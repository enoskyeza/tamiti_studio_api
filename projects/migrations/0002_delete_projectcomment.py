from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('projects', '0001_initial'),
    ]

    operations = [
        migrations.DeleteModel(
            name='ProjectComment',
        ),
    ]

