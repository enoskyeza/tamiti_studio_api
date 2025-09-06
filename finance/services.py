from django.db import transaction
from django.core.exceptions import ValidationError
from decimal import Decimal
from common.enums import TransactionType, InvoiceDirection

from finance.models import Payment, Transaction

class FinanceService:
    @staticmethod
    @transaction.atomic
    def record_invoice_payment(*, invoice, amount, account, method, date=None, note=None, created_by=None):
        amount = Decimal(amount)
        invoice = invoice.__class__.objects.with_paid_and_due().get(pk=invoice.pk)

        if amount <= 0:
            raise ValidationError("Amount must be > 0.")
        if amount > invoice.amount_due:
            raise ValidationError("Payment exceeds amount due.")

        payment = Payment.objects.create(
            invoice=invoice,
            amount=amount,
            account=account,
            method=method,
            date=date or timezone.now().date(),
            note=note or f"Payment for invoice {invoice.number}",
            created_by=created_by,
        )

        tx_type = TransactionType.EXPENSE if invoice.direction == InvoiceDirection.INCOMING else TransactionType.INCOME

        Transaction.objects.create(
            party=invoice.party,
            amount=amount,
            type=tx_type,
            account=account,
            date=payment.date,
            currency=invoice.currency,
            description=payment.note,
            reference=f"INV:{invoice.number}/PAY:{payment.pk}",
        )

        return payment
