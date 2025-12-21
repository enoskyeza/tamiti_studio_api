import django.db.models.deletion
import uuid
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('saccos', '0015_passbooksection_withdrawable'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='SaccoWithdrawal',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('deleted_at', models.DateTimeField(blank=True, null=True)),
                ('is_deleted', models.BooleanField(default=False)),
                ('uuid', models.UUIDField(default=uuid.uuid4, editable=False)),
                ('withdrawal_number', models.CharField(max_length=50, unique=True)),
                ('request_date', models.DateField()),
                ('amount', models.DecimalField(decimal_places=2, max_digits=12)),
                ('reason', models.TextField(blank=True)),
                ('notes', models.TextField(blank=True)),
                ('status', models.CharField(choices=[('pending', 'Pending'), ('approved', 'Approved'), ('disbursed', 'Disbursed'), ('rejected', 'Rejected')], default='pending', max_length=20)),
                ('approval_date', models.DateField(blank=True, null=True)),
                ('disbursement_date', models.DateField(blank=True, null=True)),
                ('rejection_reason', models.TextField(blank=True)),
                ('approved_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='approved_withdrawals', to=settings.AUTH_USER_MODEL)),
                ('requested_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='requested_withdrawals', to=settings.AUTH_USER_MODEL)),
                ('member', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='withdrawals', to='saccos.saccomember')),
                ('sacco', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='withdrawals', to='saccos.saccoorganization')),
            ],
            options={
                'ordering': ['-request_date'],
            },
        ),
        migrations.CreateModel(
            name='WithdrawalAllocation',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('deleted_at', models.DateTimeField(blank=True, null=True)),
                ('is_deleted', models.BooleanField(default=False)),
                ('uuid', models.UUIDField(default=uuid.uuid4, editable=False)),
                ('amount', models.DecimalField(decimal_places=2, max_digits=12)),
                ('passbook_entry', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='withdrawal_allocations', to='saccos.passbookentry')),
                ('section', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='withdrawal_allocations', to='saccos.passbooksection')),
                ('withdrawal', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='allocations', to='saccos.saccowithdrawal')),
            ],
            options={
                'unique_together': {('withdrawal', 'section')},
            },
        ),
        migrations.AddIndex(
            model_name='saccowithdrawal',
            index=models.Index(fields=['sacco', 'status'], name='saccos_withdr_sacco_status_idx'),
        ),
        migrations.AddIndex(
            model_name='saccowithdrawal',
            index=models.Index(fields=['member', 'status'], name='saccos_withdr_member_status_idx'),
        ),
    ]
