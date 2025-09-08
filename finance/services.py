from decimal import Decimal
from django.core.exceptions import ValidationError
from django.db import transaction as db_transaction

from finance.models import Payment, Transaction, Invoice
from common.enums import TransactionType, PaymentMethod, InvoiceDirection


class FinanceService:
    @staticmethod
    @db_transaction.atomic
    def record_invoice_payment(*, invoice: Invoice, amount, account=None, method=None, date=None, notes: str = '', created_by=None) -> Payment:
        amount = Decimal(str(amount))
        if amount <= 0:
            raise ValidationError({'amount': 'Payment amount must be greater than zero'})
        if amount > invoice.amount_due:
            raise ValidationError({'amount': 'Payment exceeds amount due'})

        # Payment direction follows cash flow: paying supplier (incoming invoice) is outgoing; collecting from customer (outgoing invoice) is incoming
        payment = Payment.objects.create(
            direction='outgoing' if invoice.direction == InvoiceDirection.INCOMING else 'incoming',
            amount=amount,
            party=invoice.party,
            invoice=invoice,
            account=account,
            notes=notes or '',
            method=method or PaymentMethod.CASH,
        )

        # Map invoice direction to transaction type
        # Paying INCOMING invoice => EXPENSE; Paying OUTGOING invoice => INCOME
        tx_type = TransactionType.EXPENSE if invoice.direction == InvoiceDirection.INCOMING else TransactionType.INCOME
        tx = Transaction.objects.create(
            type=tx_type,
            amount=amount,
            description=notes or f"Payment for invoice {invoice.number}",
            account=account,
            related_invoice=invoice,
            related_payment=payment,
            is_automated=True,
        )
        payment.transaction = tx
        payment.save(update_fields=['transaction'])
        return payment
