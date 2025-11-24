from django.db import migrations, models


def set_account_domain(apps, schema_editor):
    Account = apps.get_model("finance", "Account")
    SaccoAccount = apps.get_model("saccos", "SaccoAccount")
    SaccoOrganization = apps.get_model("saccos", "SaccoOrganization")

    # Mark accounts linked via SaccoAccount as sacco-domain
    for sacco_account in SaccoAccount.objects.select_related("account"):
        if sacco_account.account_id:
            Account.objects.filter(id=sacco_account.account_id).update(domain="sacco")

    # Also mark accounts referenced in sacco.settings["finance_accounts"] as sacco-domain
    for sacco in SaccoOrganization.objects.all():
        settings = getattr(sacco, "settings", None)
        if isinstance(settings, dict):
            finance_accounts = settings.get("finance_accounts") or {}
            if isinstance(finance_accounts, dict):
                account_ids = [pk for pk in finance_accounts.values() if pk]
                if account_ids:
                    Account.objects.filter(id__in=account_ids).update(domain="sacco")


class Migration(migrations.Migration):

    dependencies = [
        ("finance", "0014_alter_account_scope_alter_transaction_category"),
        ("saccos", "0013_saccoloan_repayment_frequency"),
    ]

    operations = [
        migrations.AddField(
            model_name="account",
            name="domain",
            field=models.CharField(
                max_length=20,
                choices=[("studio", "Studio"), ("sacco", "Sacco")],
                default="studio",
            ),
        ),
        migrations.RunPython(set_account_domain, migrations.RunPython.noop),
    ]
