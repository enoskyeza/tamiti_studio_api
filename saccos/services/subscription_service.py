from decimal import Decimal
from django.db import transaction
from django.db.models import Sum
from django.utils import timezone
from dateutil.relativedelta import relativedelta


class SubscriptionService:
    """
    Service for managing SACCO subscriptions
    Phase 6: SaaS Features
    """
    
    @staticmethod
    @transaction.atomic
    def create_trial_subscription(sacco, plan, trial_days=30):
        """
        Create a trial subscription for a new SACCO
        
        Args:
            sacco: SaccoOrganization instance
            plan: SubscriptionPlan instance
            trial_days: Number of trial days (default 30)
            
        Returns:
            SaccoSubscription instance
        """
        from saccos.models import SaccoSubscription
        
        today = timezone.now().date()
        trial_end = today + relativedelta(days=trial_days)
        
        subscription = SaccoSubscription.objects.create(
            sacco=sacco,
            plan=plan,
            billing_cycle='monthly',
            start_date=today,
            end_date=trial_end,
            trial_end_date=trial_end,
            status='trial',
            next_billing_date=trial_end + relativedelta(days=1),
            billing_email=sacco.email,
            billing_phone=sacco.phone
        )
        
        # Update SACCO subscription status
        sacco.subscription_status = 'trial'
        sacco.subscription_expires_at = trial_end
        sacco.save()
        
        return subscription
    
    @staticmethod
    @transaction.atomic
    def upgrade_subscription(subscription, new_plan):
        """
        Upgrade subscription to a different plan
        
        Args:
            subscription: SaccoSubscription instance
            new_plan: SubscriptionPlan instance
            
        Returns:
            Updated subscription
        """
        # Calculate prorated refund/charge if needed
        # For simplicity, apply change from next billing cycle
        
        subscription.plan = new_plan
        subscription.save()
        
        return subscription
    
    @staticmethod
    @transaction.atomic
    def activate_subscription(subscription, payment_method='manual', reference=''):
        """
        Activate a subscription after payment
        
        Args:
            subscription: SaccoSubscription instance
            payment_method: Payment method used
            reference: Payment reference
            
        Returns:
            dict with subscription and invoice
        """
        from saccos.models import SubscriptionInvoice
        
        # Calculate amount based on billing cycle
        if subscription.billing_cycle == 'monthly':
            amount = subscription.plan.monthly_price
            period_delta = relativedelta(months=1)
        else:  # yearly
            amount = subscription.plan.yearly_price
            period_delta = relativedelta(years=1)
        
        today = timezone.now().date()
        
        # Update subscription
        subscription.status = 'active'
        subscription.start_date = today
        subscription.end_date = today + period_delta
        subscription.trial_end_date = None
        subscription.next_billing_date = subscription.end_date
        subscription.last_payment_date = today
        subscription.save()
        
        # Update SACCO
        subscription.sacco.subscription_status = 'active'
        subscription.sacco.subscription_expires_at = subscription.end_date
        subscription.sacco.save()
        
        # Create invoice
        invoice = SubscriptionInvoice.objects.create(
            subscription=subscription,
            due_date=today,
            amount=amount,
            currency=subscription.plan.currency,
            status='paid',
            paid_date=today,
            payment_method=payment_method,
            payment_reference=reference,
            period_start=today,
            period_end=subscription.end_date
        )
        
        return {
            'subscription': subscription,
            'invoice': invoice
        }
    
    @staticmethod
    @transaction.atomic
    def renew_subscription(subscription, payment_method='auto', reference=''):
        """
        Renew an existing subscription
        
        Args:
            subscription: SaccoSubscription instance
            payment_method: Payment method
            reference: Payment reference
            
        Returns:
            dict with subscription and invoice
        """
        from saccos.models import SubscriptionInvoice
        
        if not subscription.auto_renew and payment_method == 'auto':
            return {
                'success': False,
                'error': 'Auto-renewal is disabled'
            }
        
        # Calculate amount
        if subscription.billing_cycle == 'monthly':
            amount = subscription.plan.monthly_price
        else:
            amount = subscription.plan.yearly_price
        
        today = timezone.now().date()
        
        # Renew subscription
        subscription.renew()
        
        # Update SACCO
        subscription.sacco.subscription_status = 'active'
        subscription.sacco.subscription_expires_at = subscription.end_date
        subscription.sacco.save()
        
        # Create invoice
        invoice = SubscriptionInvoice.objects.create(
            subscription=subscription,
            due_date=today,
            amount=amount,
            currency=subscription.plan.currency,
            status='paid',
            paid_date=today,
            payment_method=payment_method,
            payment_reference=reference,
            period_start=subscription.last_payment_date or today,
            period_end=subscription.end_date
        )
        
        return {
            'success': True,
            'subscription': subscription,
            'invoice': invoice
        }
    
    @staticmethod
    @transaction.atomic
    def suspend_subscription(subscription, reason=''):
        """
        Suspend a subscription (e.g., non-payment)
        
        Args:
            subscription: SaccoSubscription instance
            reason: Reason for suspension
            
        Returns:
            Updated subscription
        """
        subscription.status = 'suspended'
        subscription.save()
        
        # Update SACCO
        subscription.sacco.subscription_status = 'suspended'
        subscription.sacco.save()
        
        return subscription
    
    @staticmethod
    @transaction.atomic
    def cancel_subscription(subscription, immediate=False):
        """
        Cancel a subscription
        
        Args:
            subscription: SaccoSubscription instance
            immediate: Cancel immediately or at period end
            
        Returns:
            Updated subscription
        """
        if immediate:
            subscription.status = 'cancelled'
            subscription.end_date = timezone.now().date()
        else:
            subscription.cancel_at_period_end = True
        
        subscription.auto_renew = False
        subscription.save()
        
        if immediate:
            subscription.sacco.subscription_status = 'cancelled'
            subscription.sacco.save()
        
        return subscription
    
    @staticmethod
    def check_usage_limits(sacco):
        """
        Check if SACCO is within subscription limits
        
        Args:
            sacco: SaccoOrganization instance
            
        Returns:
            dict with limit checks
        """
        if not hasattr(sacco, 'subscription'):
            return {
                'has_subscription': False,
                'error': 'No active subscription'
            }
        
        subscription = sacco.subscription
        plan = subscription.plan
        
        # Check member count
        active_members = sacco.members.filter(status='active').count()
        members_ok = active_members <= plan.max_members
        
        # Check meetings this year
        current_year = timezone.now().year
        meetings_this_year = sacco.weekly_meetings.filter(year=current_year).count()
        meetings_ok = meetings_this_year <= plan.max_weekly_meetings
        
        # Storage check (simplified - would need actual file size calculation)
        storage_ok = True  # Placeholder
        
        return {
            'has_subscription': True,
            'is_active': subscription.is_active(),
            'limits': {
                'members': {
                    'used': active_members,
                    'limit': plan.max_members,
                    'ok': members_ok,
                    'percentage': (active_members / plan.max_members * 100) if plan.max_members > 0 else 0
                },
                'meetings': {
                    'used': meetings_this_year,
                    'limit': plan.max_weekly_meetings,
                    'ok': meetings_ok,
                    'percentage': (meetings_this_year / plan.max_weekly_meetings * 100) if plan.max_weekly_meetings > 0 else 0
                },
                'storage': {
                    'ok': storage_ok
                }
            },
            'within_limits': members_ok and meetings_ok and storage_ok
        }
    
    @staticmethod
    @transaction.atomic
    def record_usage_metrics(sacco, period_start, period_end):
        """
        Record usage metrics for a period
        
        Args:
            sacco: SaccoOrganization instance
            period_start: Start date
            period_end: End date
            
        Returns:
            UsageMetrics instance
        """
        from saccos.models import UsageMetrics
        
        # Calculate metrics
        active_members = sacco.members.filter(status='active').count()
        
        meetings = sacco.weekly_meetings.filter(
            meeting_date__gte=period_start,
            meeting_date__lte=period_end
        )
        meetings_held = meetings.count()
        
        total_contributions = meetings.filter(
            status='completed'
        ).aggregate(
            total=Sum('total_collected')
        )['total'] or Decimal('0')
        
        loans = sacco.loans.filter(
            disbursement_date__gte=period_start,
            disbursement_date__lte=period_end
        )
        loans_created = loans.count()
        
        total_loans_disbursed = loans.aggregate(
            total=Sum('principal_amount')
        )['total'] or Decimal('0')
        
        # Create or update metrics
        metrics, created = UsageMetrics.objects.update_or_create(
            sacco=sacco,
            period_start=period_start,
            defaults={
                'period_end': period_end,
                'active_members_count': active_members,
                'meetings_held': meetings_held,
                'loans_created': loans_created,
                'total_contributions': total_contributions,
                'total_loans_disbursed': total_loans_disbursed
            }
        )
        
        return metrics
    
    @staticmethod
    def get_subscription_status(sacco):
        """
        Get comprehensive subscription status
        
        Args:
            sacco: SaccoOrganization instance
            
        Returns:
            dict with status information
        """
        if not hasattr(sacco, 'subscription'):
            return {
                'has_subscription': False,
                'message': 'No subscription found'
            }
        
        subscription = sacco.subscription
        limits = SubscriptionService.check_usage_limits(sacco)
        
        return {
            'has_subscription': True,
            'subscription': {
                'plan': subscription.plan.name,
                'status': subscription.status,
                'billing_cycle': subscription.billing_cycle,
                'start_date': subscription.start_date,
                'end_date': subscription.end_date,
                'trial_end_date': subscription.trial_end_date,
                'days_remaining': subscription.days_until_expiry(),
                'auto_renew': subscription.auto_renew,
                'next_billing_date': subscription.next_billing_date
            },
            'usage': limits,
            'is_valid': subscription.is_active() and limits.get('within_limits', False)
        }
