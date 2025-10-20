from decimal import Decimal
from django.db import transaction
from django.utils import timezone


class FinanceIntegrationService:
    """
    Service for integrating SACCO operations with finance module
    Phase 5: Integration & Reporting
    """
    
    @staticmethod
    @transaction.atomic
    def setup_sacco_accounts(sacco):
        """
        Create finance accounts for a SACCO
        
        Args:
            sacco: SaccoOrganization instance
            
        Returns:
            dict: Created accounts
        """
        from finance.models import Account
        from common.enums import AccountType, FinanceScope
        
        accounts = {}
        
        # Main SACCO Bank Account
        bank_account = Account.objects.create(
            name=f"{sacco.name} - Bank Account",
            account_type=AccountType.BANK.value,
            scope=FinanceScope.SACCO.value,
            balance=Decimal('0'),
            description=f"Main bank account for {sacco.name}"
        )
        accounts['bank'] = bank_account
        
        # SACCO Cash Box
        cash_account = Account.objects.create(
            name=f"{sacco.name} - Cash Box",
            account_type=AccountType.CASHBOX.value,
            scope=FinanceScope.SACCO.value,
            balance=Decimal('0'),
            description=f"Cash box for {sacco.name} weekly meetings"
        )
        accounts['cash'] = cash_account
        
        # Loan Portfolio Account
        loan_account = Account.objects.create(
            name=f"{sacco.name} - Loan Portfolio",
            account_type=AccountType.BANK.value,
            scope=FinanceScope.SACCO.value,
            balance=Decimal('0'),
            description=f"Loan portfolio for {sacco.name}"
        )
        accounts['loans'] = loan_account
        
        # Store account IDs in SACCO settings
        sacco.settings['finance_accounts'] = {
            'bank': bank_account.id,
            'cash': cash_account.id,
            'loans': loan_account.id
        }
        sacco.save()
        
        return accounts
    
    @staticmethod
    @transaction.atomic
    def sync_weekly_meeting_to_finance(meeting):
        """
        Sync weekly meeting to finance module
        
        Creates transactions for:
        - Amount collected (cash to bank)
        - Amount to recipient (bank to member)
        
        Args:
            meeting: WeeklyMeeting instance
            
        Returns:
            dict: Created transactions
        """
        from finance.models import Transaction, Account
        from common.enums import TransactionType, PaymentCategory
        
        if not meeting.sacco.settings.get('finance_accounts'):
            return {'error': 'Finance accounts not set up for this SACCO'}
        
        transactions = []
        account_ids = meeting.sacco.settings['finance_accounts']
        
        # 1. Record total collection (Income to cash box)
        cash_account = Account.objects.get(id=account_ids['cash'])
        
        collection_txn = Transaction.objects.create(
            account=cash_account,
            transaction_type=TransactionType.INCOME.value,
            category=PaymentCategory.SACCO_SAVINGS.value,
            amount=meeting.total_collected,
            description=f"Weekly collection - Week {meeting.week_number}",
            transaction_date=meeting.meeting_date,
            reference=f"MEETING-{meeting.id}"
        )
        transactions.append(collection_txn)
        
        # Update cash account balance
        cash_account.balance += meeting.total_collected
        cash_account.save()
        
        # 2. Record amount to bank (Transfer from cash to bank)
        if meeting.amount_to_bank > 0:
            bank_account = Account.objects.get(id=account_ids['bank'])
            
            bank_deposit_txn = Transaction.objects.create(
                account=bank_account,
                transaction_type=TransactionType.INCOME.value,
                category=PaymentCategory.SACCO_SAVINGS.value,
                amount=meeting.amount_to_bank,
                description=f"Bank deposit - Week {meeting.week_number}",
                transaction_date=meeting.meeting_date,
                reference=f"MEETING-{meeting.id}-BANK"
            )
            transactions.append(bank_deposit_txn)
            
            # Update balances
            bank_account.balance += meeting.amount_to_bank
            bank_account.save()
            
            cash_account.balance -= meeting.amount_to_bank
            cash_account.save()
        
        # 3. Record amount to recipient (Payment from cash)
        if meeting.amount_to_recipient > 0:
            recipient_txn = Transaction.objects.create(
                account=cash_account,
                transaction_type=TransactionType.EXPENSE.value,
                category=PaymentCategory.SACCO_SAVINGS.value,
                amount=meeting.amount_to_recipient,
                description=f"Cash round payment to {meeting.cash_round_recipient.member_number}",
                transaction_date=meeting.meeting_date,
                reference=f"MEETING-{meeting.id}-RECIPIENT"
            )
            transactions.append(recipient_txn)
            
            # Update cash account balance
            cash_account.balance -= meeting.amount_to_recipient
            cash_account.save()
        
        return {
            'success': True,
            'transactions': transactions,
            'total_synced': len(transactions)
        }
    
    @staticmethod
    @transaction.atomic
    def sync_loan_disbursement_to_finance(loan):
        """
        Sync loan disbursement to finance module
        
        Args:
            loan: SaccoLoan instance
            
        Returns:
            dict: Created transaction
        """
        from finance.models import Transaction, Account
        from common.enums import TransactionType, PaymentCategory
        
        if not loan.sacco.settings.get('finance_accounts'):
            return {'error': 'Finance accounts not set up for this SACCO'}
        
        account_ids = loan.sacco.settings['finance_accounts']
        loan_account = Account.objects.get(id=account_ids['loans'])
        
        # Record loan disbursement (Expense from loan portfolio)
        txn = Transaction.objects.create(
            account=loan_account,
            transaction_type=TransactionType.EXPENSE.value,
            category=PaymentCategory.SACCO_LOAN_DISBURSEMENT.value,
            amount=loan.principal_amount,
            description=f"Loan disbursement - {loan.loan_number} to {loan.member.member_number}",
            transaction_date=loan.disbursement_date,
            reference=loan.loan_number
        )
        
        # Update loan account balance (negative = money out)
        loan_account.balance -= loan.principal_amount
        loan_account.save()
        
        return {
            'success': True,
            'transaction': txn
        }
    
    @staticmethod
    @transaction.atomic
    def sync_loan_payment_to_finance(payment):
        """
        Sync loan payment to finance module
        
        Args:
            payment: LoanPayment instance
            
        Returns:
            dict: Created transactions
        """
        from finance.models import Transaction, Account
        from common.enums import TransactionType, PaymentCategory
        
        loan = payment.loan
        
        if not loan.sacco.settings.get('finance_accounts'):
            return {'error': 'Finance accounts not set up for this SACCO'}
        
        transactions = []
        account_ids = loan.sacco.settings['finance_accounts']
        
        # Record principal payment (Income to loan portfolio)
        if payment.principal_amount > 0:
            loan_account = Account.objects.get(id=account_ids['loans'])
            
            principal_txn = Transaction.objects.create(
                account=loan_account,
                transaction_type=TransactionType.INCOME.value,
                category=PaymentCategory.SACCO_LOAN_REPAYMENT.value,
                amount=payment.principal_amount,
                description=f"Loan repayment (principal) - {loan.loan_number}",
                transaction_date=payment.payment_date,
                reference=f"{loan.loan_number}-P-{payment.id}"
            )
            transactions.append(principal_txn)
            
            # Update loan account balance
            loan_account.balance += payment.principal_amount
            loan_account.save()
        
        # Record interest payment (Income to bank)
        if payment.interest_amount > 0:
            bank_account = Account.objects.get(id=account_ids['bank'])
            
            interest_txn = Transaction.objects.create(
                account=bank_account,
                transaction_type=TransactionType.INCOME.value,
                category=PaymentCategory.SACCO_LOAN_REPAYMENT.value,
                amount=payment.interest_amount,
                description=f"Loan interest - {loan.loan_number}",
                transaction_date=payment.payment_date,
                reference=f"{loan.loan_number}-I-{payment.id}"
            )
            transactions.append(interest_txn)
            
            # Update bank account balance
            bank_account.balance += payment.interest_amount
            bank_account.save()
        
        return {
            'success': True,
            'transactions': transactions,
            'total_synced': len(transactions)
        }
    
    @staticmethod
    def get_sacco_financial_summary(sacco, start_date=None, end_date=None):
        """
        Get financial summary from finance module
        
        Args:
            sacco: SaccoOrganization instance
            start_date: Start date filter
            end_date: End date filter
            
        Returns:
            dict: Financial summary
        """
        from finance.models import Transaction, Account
        from django.db.models import Sum, Q
        
        if not sacco.settings.get('finance_accounts'):
            return {'error': 'Finance accounts not set up for this SACCO'}
        
        account_ids = sacco.settings['finance_accounts']
        accounts = Account.objects.filter(id__in=account_ids.values())
        
        # Filter transactions
        txn_filter = Q(account__in=accounts)
        if start_date:
            txn_filter &= Q(transaction_date__gte=start_date)
        if end_date:
            txn_filter &= Q(transaction_date__lte=end_date)
        
        transactions = Transaction.objects.filter(txn_filter)
        
        # Calculate totals
        income = transactions.filter(
            transaction_type='income'
        ).aggregate(total=Sum('amount'))['total'] or Decimal('0')
        
        expenses = transactions.filter(
            transaction_type='expense'
        ).aggregate(total=Sum('amount'))['total'] or Decimal('0')
        
        return {
            'accounts': [
                {
                    'name': acc.name,
                    'type': acc.account_type,
                    'balance': acc.balance
                }
                for acc in accounts
            ],
            'total_income': income,
            'total_expenses': expenses,
            'net_position': income - expenses,
            'transaction_count': transactions.count()
        }
