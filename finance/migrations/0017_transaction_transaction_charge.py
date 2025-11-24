from decimal import Decimal

from django.core.validators import MinValueValidator
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("finance", "0016_mark_sacco_business_accounts"),
    ]

    operations = [
        migrations.AddField(
            model_name="transaction",
            name="transaction_charge",
            field=models.DecimalField(
                max_digits=10,
                decimal_places=2,
                default=0,
                validators=[MinValueValidator(Decimal("0"))],
                help_text="Fees/charges associated with this transaction",
            ),
        ),
    ]
