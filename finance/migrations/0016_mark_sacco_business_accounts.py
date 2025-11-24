from django.db import migrations


def mark_sacco_business_accounts(apps, schema_editor):
    Account = apps.get_model("finance", "Account")
    SaccoEnterprise = apps.get_model("businesses", "SaccoEnterprise")

    # For each sacco-owned enterprise, mark its business chart of accounts as sacco-domain.
    for enterprise in SaccoEnterprise.objects.all():
        # BusinessService.setup_finance_accounts creates accounts with names starting with enterprise.name
        # and scope='company'. We use the same heuristic here.
        qs = Account.objects.filter(scope='company', name__startswith=enterprise.name)
        qs.update(domain='sacco')


class Migration(migrations.Migration):

    dependencies = [
        ("finance", "0015_account_domain"),
        ("businesses", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(mark_sacco_business_accounts, migrations.RunPython.noop),
    ]
