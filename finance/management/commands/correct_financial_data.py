from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import transaction

from common.enums import (
    FinanceScope,
    PersonalExpenseCategory,
    PersonalIncomeSource,
)
from finance.models import (
    Account,
    PersonalAccountTransfer,
    PersonalTransaction,
    DebtPayment,
    LoanRepayment,
)


class Command(BaseCommand):
    help = (
        "Normalise historical personal finance records so transfers, debts, and loans "
        "follow the updated accounting treatment."
    )

    @transaction.atomic
    def handle(self, *args, **options):
        summaries = {}
        summaries['transfers'] = self._fix_transfers()
        summaries['debt_payments'] = self._fix_debt_payments()
        summaries['loan_repayments'] = self._fix_loan_repayments()
        summaries['transactions'] = self._flag_transaction_affects_profit()
        summaries['accounts'] = self._rebalance_accounts()

        self.stdout.write(self.style.SUCCESS("Financial data correction complete."))
        for key, value in summaries.items():
            self.stdout.write(f"- {key}: {value}")

    def _fix_transfers(self):
        updated_transfers = 0
        updated_transactions = 0
        for transfer in PersonalAccountTransfer.objects.select_related(
            'debit_transaction', 'credit_transaction', 'fee_transaction'
        ):
            expected_received = (transfer.amount * transfer.exchange_rate).quantize(Decimal('0.01'))
            if transfer.received_amount != expected_received:
                transfer.received_amount = expected_received
                transfer.save(update_fields=['received_amount'])
                updated_transfers += 1

            if transfer.debit_transaction:
                tx = transfer.debit_transaction
                fields_to_update = []
                if tx.amount != transfer.amount:
                    tx.amount = transfer.amount
                    fields_to_update.append('amount')
                if tx.expense_category != PersonalExpenseCategory.TRANSFER:
                    tx.expense_category = PersonalExpenseCategory.TRANSFER
                    fields_to_update.append('expense_category')
                if tx.affects_profit:
                    tx.affects_profit = False
                    fields_to_update.append('affects_profit')
                if fields_to_update:
                    tx.save(update_fields=fields_to_update)
                    updated_transactions += 1

            if transfer.credit_transaction:
                tx = transfer.credit_transaction
                fields_to_update = []
                if tx.amount != transfer.received_amount:
                    tx.amount = transfer.received_amount
                    fields_to_update.append('amount')
                if tx.income_source != PersonalIncomeSource.TRANSFER:
                    tx.income_source = PersonalIncomeSource.TRANSFER
                    fields_to_update.append('income_source')
                if tx.affects_profit:
                    tx.affects_profit = False
                    fields_to_update.append('affects_profit')
                if fields_to_update:
                    tx.save(update_fields=fields_to_update)
                    updated_transactions += 1

            if transfer.fee_transaction:
                tx = transfer.fee_transaction
                fields_to_update = []
                if tx.expense_category != PersonalExpenseCategory.TRANSFER_FEE:
                    tx.expense_category = PersonalExpenseCategory.TRANSFER_FEE
                    fields_to_update.append('expense_category')
                if not tx.affects_profit:
                    tx.affects_profit = True
                    fields_to_update.append('affects_profit')
                if fields_to_update:
                    tx.save(update_fields=fields_to_update)
                    updated_transactions += 1

        return {
            'transfers_updated': updated_transfers,
            'transfer_transactions_updated': updated_transactions,
        }

    def _fix_debt_payments(self):
        updates = 0
        tx_updates = 0
        for payment in DebtPayment.objects.select_related('transaction', 'debt', 'account'):
            principal = payment.principal_amount or Decimal('0')
            interest = payment.interest_amount or Decimal('0')
            if principal == 0 and interest == 0:
                payment.principal_amount = payment.amount
                payment.interest_amount = Decimal('0')
                payment.save(update_fields=['principal_amount', 'interest_amount'])
                updates += 1
                principal = payment.principal_amount

            if payment.transaction:
                tx = payment.transaction
                fields_to_update = []
                if tx.amount != payment.principal_amount:
                    tx.amount = payment.principal_amount
                    fields_to_update.append('amount')
                if tx.expense_category != PersonalExpenseCategory.DEBT:
                    tx.expense_category = PersonalExpenseCategory.DEBT
                    fields_to_update.append('expense_category')
                if tx.affects_profit:
                    tx.affects_profit = False
                    fields_to_update.append('affects_profit')
                if fields_to_update:
                    tx.save(update_fields=fields_to_update)
                    tx_updates += 1

        return {
            'payments_updated': updates,
            'payment_transactions_updated': tx_updates,
        }

    def _fix_loan_repayments(self):
        updates = 0
        tx_updates = 0
        for repayment in LoanRepayment.objects.select_related('transaction', 'loan', 'account'):
            principal = repayment.principal_amount or Decimal('0')
            interest = repayment.interest_amount or Decimal('0')
            if principal == 0 and interest == 0:
                repayment.principal_amount = repayment.amount
                repayment.interest_amount = Decimal('0')
                repayment.save(update_fields=['principal_amount', 'interest_amount'])
                updates += 1
                principal = repayment.principal_amount

            if repayment.transaction:
                tx = repayment.transaction
                fields_to_update = []
                if tx.amount != repayment.principal_amount:
                    tx.amount = repayment.principal_amount
                    fields_to_update.append('amount')
                if tx.income_source != PersonalIncomeSource.LOAN_REPAYMENT:
                    tx.income_source = PersonalIncomeSource.LOAN_REPAYMENT
                    fields_to_update.append('income_source')
                if tx.affects_profit:
                    tx.affects_profit = False
                    fields_to_update.append('affects_profit')
                if fields_to_update:
                    tx.save(update_fields=fields_to_update)
                    tx_updates += 1

        return {
            'repayments_updated': updates,
            'repayment_transactions_updated': tx_updates,
        }

    def _flag_transaction_affects_profit(self):
        updated = 0
        principal_categories = [
            PersonalExpenseCategory.TRANSFER,
            PersonalExpenseCategory.LOAN_GIVEN,
            PersonalExpenseCategory.DEBT,
        ]
        updated += PersonalTransaction.objects.filter(
            expense_category__in=principal_categories,
            affects_profit=True,
        ).update(affects_profit=False)

        updated += PersonalTransaction.objects.filter(
            income_source__in=[
                PersonalIncomeSource.TRANSFER,
                PersonalIncomeSource.LOAN_REPAYMENT,
            ],
            affects_profit=True,
        ).update(affects_profit=False)

        # Ensure interest-related transactions continue to affect profit
        updated += PersonalTransaction.objects.filter(
            expense_category=PersonalExpenseCategory.DEBT_INTEREST,
            affects_profit=False,
        ).update(affects_profit=True)

        updated += PersonalTransaction.objects.filter(
            income_source=PersonalIncomeSource.LOAN_INTEREST,
            affects_profit=False,
        ).update(affects_profit=True)

        return {'transactions_flagged': updated}

    def _rebalance_accounts(self):
        recalculated = 0
        for account in Account.objects.filter(scope=FinanceScope.PERSONAL):
            account.update_balance()
            recalculated += 1
        return {'accounts_rebalanced': recalculated}
