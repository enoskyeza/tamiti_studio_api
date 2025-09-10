"""
Smart scheduling and productivity services for the planner app.
Algorithmic approaches for intelligent task scheduling and rescheduling.
"""
from datetime import datetime, timedelta, date, time
from typing import List, Dict, Tuple, Optional
from decimal import Decimal
from collections import defaultdict

from django.db import models, transaction
from django.utils import timezone
from django.core.cache import cache
from django.db.models import Q, Avg, Count, Sum

from tasks.models import Task
from .models import (
    TimeBlock, AvailabilityTemplate, CalendarEvent, BreakPolicy,
    DailyReview, WorkGoal, ProductivityInsight
)


class SmartScheduler:
    """Enhanced scheduling service with intelligent algorithms"""
    
    def __init__(self, user):
        self.user = user
        self.cache_timeout = 300  # 5 minutes
    
    def generate_optimized_schedule(self, scope: str, target_date: date) -> Dict:
        """Generate an optimized schedule using advanced algorithms"""
        cache_key = f"schedule_{self.user.id}_{scope}_{target_date}"
        cached = cache.get(cache_key)
        if cached:
            return cached
        
        # Get user's productivity insights for optimization
        insights = self._get_productivity_insights()
        
        # Enhanced task selection with priority optimization
        tasks = self._get_optimized_task_list(target_date, scope, insights)
        
        # Smart time window calculation
        windows = self._get_optimized_time_windows(target_date, scope, insights)
        
        # Advanced packing algorithm
        schedule = self._advanced_pack_algorithm(tasks, windows, insights)
        
        # Cache the result
        cache.set(cache_key, schedule, self.cache_timeout)
        return schedule
    
    def _get_productivity_insights(self) -> Dict:
        """Get user's productivity patterns for optimization"""
        insights = {}
        
        # Peak hours insight
        peak_hours = ProductivityInsight.objects.filter(
            owner_user=self.user,
            insight_type='peak_hours',
            is_active=True
        ).first()
        
        if peak_hours:
            insights['peak_hours'] = peak_hours.data.get('hours', [9, 10, 11, 14, 15])
        else:
            insights['peak_hours'] = [9, 10, 11, 14, 15]  # Default peak hours
        
        # Optimal task duration
        task_duration = ProductivityInsight.objects.filter(
            owner_user=self.user,
            insight_type='task_duration',
            is_active=True
        ).first()
        
        if task_duration:
            insights['optimal_duration'] = task_duration.data.get('minutes', 45)
        else:
            insights['optimal_duration'] = 45  # Default 45 minutes
        
        return insights
    
    def _get_optimized_task_list(self, target_date: date, scope: str, insights: Dict) -> List[Task]:
        """Get tasks optimized for scheduling with smart filtering"""
        from accounts.models import Department
        
        dept = getattr(self.user, 'staff_profile', None) and self.user.staff_profile.department
        
        # Base query for incomplete tasks
        base_query = Task.objects.filter(
            is_completed=False
        ).filter(
            Q(created_by=self.user) | Q(assigned_to=self.user) | 
            Q(project__created_by=self.user) | (Q(assigned_team=dept) if dept else Q(pk__isnull=True))
        ).select_related('project', 'assigned_to').prefetch_related('dependencies')
        
        # Date range filtering
        if scope == 'week':
            start_date = target_date - timedelta(days=target_date.weekday())
            end_date = start_date + timedelta(days=7)
        else:
            start_date = target_date
            end_date = target_date + timedelta(days=1)
        
        # Smart filtering
        tasks = base_query.filter(
            # Not snoozed past the target period
            Q(snoozed_until__isnull=True) | Q(snoozed_until__lte=timezone.make_aware(
                datetime.combine(end_date, time.max)
            )),
            # Respect backlog dates
            Q(backlog_date__isnull=True) | Q(backlog_date__lte=start_date),
            # No incomplete dependencies
            ~Q(dependencies__is_completed=False)
        ).distinct()
        
        # Smart prioritization
        return self._prioritize_tasks(list(tasks), insights)
    
    def _prioritize_tasks(self, tasks: List[Task], insights: Dict) -> List[Task]:
        """Advanced task prioritization algorithm"""
        now = timezone.now()
        
        def calculate_priority_score(task: Task) -> float:
            score = 0.0
            
            # Base priority weight
            priority_weights = {
                'critical': 100, 'urgent': 90, 'high': 70, 
                'medium': 40, 'low': 10
            }
            score += priority_weights.get(task.priority, 40)
            
            # Due date urgency (exponential curve)
            if task.due_date:
                hours_until_due = (task.due_date - now).total_seconds() / 3600
                if hours_until_due < 0:  # Overdue
                    score += 200  # High penalty for overdue
                elif hours_until_due < 24:  # Due today
                    score += 100
                elif hours_until_due < 72:  # Due in 3 days
                    score += 50
                else:
                    score += max(0, 50 - (hours_until_due / 24))
            
            # Hard deadline penalty
            if getattr(task, 'is_hard_due', False):
                score += 50
            
            # Project importance (if linked to work goals)
            if hasattr(task, 'work_goal') and task.work_goal:
                score += 30
            
            # Effort vs impact ratio
            estimated_minutes = getattr(task, 'estimated_minutes', None) or (
                (getattr(task, 'estimated_hours', None) or 1) * 60
            )
            if estimated_minutes < insights['optimal_duration']:
                score += 20  # Bonus for quick wins
            
            return score
        
        # Sort by priority score (descending)
        tasks.sort(key=calculate_priority_score, reverse=True)
        return tasks
    
    def _get_optimized_time_windows(self, target_date: date, scope: str, insights: Dict) -> List[Tuple[datetime, datetime]]:
        """Get time windows optimized for user's peak productivity"""
        if scope == 'week':
            start_date = target_date - timedelta(days=target_date.weekday())
            dates = [start_date + timedelta(days=i) for i in range(7)]
        else:
            dates = [target_date]
        
        all_windows = []
        for date_obj in dates:
            daily_windows = self._get_daily_windows(date_obj, insights)
            all_windows.extend(daily_windows)
        
        return all_windows
    
    def _get_daily_windows(self, date_obj: date, insights: Dict) -> List[Tuple[datetime, datetime]]:
        """Get optimized daily time windows"""
        weekday = date_obj.weekday()
        
        # Get availability templates
        templates = AvailabilityTemplate.objects.filter(
            owner_user=self.user, day_of_week=weekday
        )
        
        if not templates.exists():
            dept = getattr(self.user, 'staff_profile', None) and self.user.staff_profile.department
            if dept:
                templates = AvailabilityTemplate.objects.filter(
                    owner_team=dept, day_of_week=weekday
                )
        
        # Default availability if none set
        if not templates.exists():
            tz = timezone.get_current_timezone()
            start_dt = datetime.combine(date_obj, time(9, 0), tz)
            end_dt = datetime.combine(date_obj, time(17, 0), tz)
            windows = [(start_dt, end_dt)]
        else:
            tz = timezone.get_current_timezone()
            windows = []
            for template in templates:
                start_dt = datetime.combine(date_obj, template.start_time, tz)
                end_dt = datetime.combine(date_obj, template.end_time, tz)
                windows.append((start_dt, end_dt))
        
        # Subtract calendar events
        windows = self._subtract_calendar_events(windows)
        
        # Optimize windows for peak hours
        return self._optimize_for_peak_hours(windows, insights['peak_hours'])
    
    def _subtract_calendar_events(self, windows: List[Tuple[datetime, datetime]]) -> List[Tuple[datetime, datetime]]:
        """Remove busy calendar events from available windows"""
        if not windows:
            return []
        
        start = min(w[0] for w in windows)
        end = max(w[1] for w in windows)
        
        dept = getattr(self.user, 'staff_profile', None) and self.user.staff_profile.department
        q = Q(owner_user=self.user) | (Q(owner_team=dept) if dept else Q(pk__isnull=True))
        
        events = CalendarEvent.objects.filter(
            q, is_busy=True, start__lt=end, end__gt=start
        )
        
        free_windows = windows[:]
        for event in events:
            updated_windows = []
            for window_start, window_end in free_windows:
                if event.end <= window_start or event.start >= window_end:
                    # No overlap
                    updated_windows.append((window_start, window_end))
                else:
                    # Split window around event
                    if window_start < event.start:
                        updated_windows.append((window_start, event.start))
                    if event.end < window_end:
                        updated_windows.append((event.end, window_end))
            
            # Filter out windows too small (< 15 minutes)
            free_windows = [
                (s, e) for s, e in updated_windows 
                if (e - s).total_seconds() >= 900
            ]
        
        return free_windows
    
    def _optimize_for_peak_hours(self, windows: List[Tuple[datetime, datetime]], peak_hours: List[int]) -> List[Tuple[datetime, datetime]]:
        """Reorder windows to prioritize peak productivity hours"""
        peak_windows = []
        regular_windows = []
        
        for start, end in windows:
            window_hours = set(range(start.hour, end.hour + 1))
            if any(hour in peak_hours for hour in window_hours):
                peak_windows.append((start, end))
            else:
                regular_windows.append((start, end))
        
        # Return peak hours first
        return peak_windows + regular_windows
    
    def _advanced_pack_algorithm(self, tasks: List[Task], windows: List[Tuple[datetime, datetime]], insights: Dict) -> Dict:
        """Advanced task packing with break optimization"""
        if not windows:
            return {'blocks': [], 'capacity_usage': 0, 'window_minutes': 0, 'planned_minutes': 0}
        
        # Get break policy
        break_policy = BreakPolicy.objects.filter(owner_user=self.user, active=True).first()
        if not break_policy:
            dept = getattr(self.user, 'staff_profile', None) and self.user.staff_profile.department
            if dept:
                break_policy = BreakPolicy.objects.filter(owner_team=dept, active=True).first()
        
        focus_minutes = break_policy.focus_minutes if break_policy else 25
        break_minutes = break_policy.break_minutes if break_policy else 5
        
        blocks = []
        window_cursor = 0
        current_window_start, current_window_end = windows[window_cursor]
        cursor = current_window_start
        
        for task in tasks:
            if window_cursor >= len(windows):
                break
            
            task_minutes = self._get_task_duration(task, insights)
            remaining_minutes = task_minutes
            
            while remaining_minutes > 0 and window_cursor < len(windows):
                # Advance to next available window if needed
                while cursor >= current_window_end:
                    window_cursor += 1
                    if window_cursor >= len(windows):
                        break
                    current_window_start, current_window_end = windows[window_cursor]
                    cursor = current_window_start
                
                if window_cursor >= len(windows):
                    break
                
                # Calculate optimal block size
                available_time = (current_window_end - cursor).total_seconds() / 60
                block_size = min(remaining_minutes, available_time, focus_minutes)
                
                if block_size < 10:  # Skip if less than 10 minutes available
                    cursor = current_window_end
                    continue
                
                # Create task block
                block_end = cursor + timedelta(minutes=block_size)
                blocks.append({
                    'task_id': task.id,
                    'title': task.title,
                    'start': cursor,
                    'end': block_end,
                    'is_break': False,
                })
                
                remaining_minutes -= block_size
                cursor = block_end
                
                # Add break if there's more work and space
                if remaining_minutes > 0 and cursor + timedelta(minutes=break_minutes) <= current_window_end:
                    break_end = cursor + timedelta(minutes=break_minutes)
                    blocks.append({
                        'task_id': None,
                        'title': 'Break',
                        'start': cursor,
                        'end': break_end,
                        'is_break': True,
                    })
                    cursor = break_end
        
        # Calculate metrics
        total_window_minutes = sum((end - start).total_seconds() / 60 for start, end in windows)
        planned_minutes = sum((b['end'] - b['start']).total_seconds() / 60 for b in blocks if not b['is_break'])
        capacity_usage = (planned_minutes / total_window_minutes) if total_window_minutes > 0 else 0
        
        return {
            'blocks': [self._serialize_block(b) for b in blocks],
            'capacity_usage': capacity_usage,
            'window_minutes': int(total_window_minutes),
            'planned_minutes': int(planned_minutes),
        }
    
    def _get_task_duration(self, task: Task, insights: Dict) -> int:
        """Get optimal task duration based on estimates and insights"""
        if hasattr(task, 'estimated_minutes') and task.estimated_minutes:
            return task.estimated_minutes
        elif hasattr(task, 'estimated_hours') and task.estimated_hours:
            return task.estimated_hours * 60
        else:
            # Use insight-based estimation
            return insights.get('optimal_duration', 60)
    
    def _serialize_block(self, block: Dict) -> Dict:
        """Serialize block for API response"""
        return {
            'task_id': block['task_id'],
            'title': block['title'],
            'start': block['start'].isoformat(),
            'end': block['end'].isoformat(),
            'is_break': block['is_break'],
        }


class ProductivityAnalyzer:
    """Service for computing productivity insights and analytics"""
    
    def __init__(self, user):
        self.user = user
    
    def compute_daily_review(self, target_date: date) -> DailyReview:
        """Compute or update daily review with metrics"""
        review, created = DailyReview.objects.get_or_create(
            owner_user=self.user,
            date=target_date,
            defaults={'summary': ''}
        )
        
        review.calculate_metrics()
        return review
    
    def generate_productivity_insights(self) -> Dict[str, ProductivityInsight]:
        """Generate algorithmic productivity insights"""
        insights = {}
        
        # Only generate if we have enough data (at least 7 days)
        review_count = DailyReview.objects.filter(owner_user=self.user).count()
        if review_count < 7:
            return insights
        
        # Peak hours analysis
        insights['peak_hours'] = self._analyze_peak_hours()
        
        # Optimal task duration
        insights['task_duration'] = self._analyze_task_duration()
        
        # Break pattern analysis
        insights['break_pattern'] = self._analyze_break_patterns()
        
        # Weekly trend analysis
        insights['weekly_trend'] = self._analyze_weekly_trends()
        
        return insights
    
    def _analyze_peak_hours(self) -> ProductivityInsight:
        """Analyze when user is most productive"""
        # Get completed time blocks from last 30 days
        thirty_days_ago = timezone.now() - timedelta(days=30)
        
        completed_blocks = TimeBlock.objects.filter(
            owner_user=self.user,
            status='completed',
            is_break=False,
            start__gte=thirty_days_ago
        )
        
        # Count completions by hour
        hour_productivity = defaultdict(int)
        for block in completed_blocks:
            hour = block.start.hour
            hour_productivity[hour] += 1
        
        # Find peak hours (top 40% of productive hours)
        if hour_productivity:
            sorted_hours = sorted(hour_productivity.items(), key=lambda x: x[1], reverse=True)
            peak_count = max(1, len(sorted_hours) * 2 // 5)  # Top 40%
            peak_hours = [hour for hour, _ in sorted_hours[:peak_count]]
        else:
            peak_hours = [9, 10, 11, 14, 15]  # Default
        
        confidence = min(100, len(completed_blocks) * 2)  # 2% per completed block
        
        insight, created = ProductivityInsight.objects.update_or_create(
            owner_user=self.user,
            insight_type='peak_hours',
            defaults={
                'data': {'hours': peak_hours},
                'confidence_score': confidence,
                'sample_size': len(completed_blocks),
                'valid_from': timezone.now().date(),
                'is_active': True
            }
        )
        
        return insight
    
    def _analyze_task_duration(self) -> ProductivityInsight:
        """Analyze optimal task duration for user"""
        # Get completed tasks from last 30 days
        thirty_days_ago = timezone.now() - timedelta(days=30)
        
        completed_tasks = Task.objects.filter(
            Q(created_by=self.user) | Q(assigned_to=self.user),
            is_completed=True,
            completed_at__gte=thirty_days_ago,
            estimated_minutes__isnull=False
        )
        
        # Calculate average duration of successfully completed tasks
        if completed_tasks.exists():
            avg_duration = completed_tasks.aggregate(
                avg=Avg('estimated_minutes')
            )['avg']
            optimal_duration = int(avg_duration) if avg_duration else 45
        else:
            optimal_duration = 45
        
        confidence = min(100, completed_tasks.count() * 5)  # 5% per completed task
        
        insight, created = ProductivityInsight.objects.update_or_create(
            owner_user=self.user,
            insight_type='task_duration',
            defaults={
                'data': {'minutes': optimal_duration},
                'confidence_score': confidence,
                'sample_size': completed_tasks.count(),
                'valid_from': timezone.now().date(),
                'is_active': True
            }
        )
        
        return insight
    
    def _analyze_break_patterns(self) -> ProductivityInsight:
        """Analyze optimal break patterns"""
        # Get daily reviews from last 30 days
        thirty_days_ago = timezone.now().date() - timedelta(days=30)
        
        reviews = DailyReview.objects.filter(
            owner_user=self.user,
            date__gte=thirty_days_ago,
            focus_time_minutes__gt=0,
            break_time_minutes__gt=0
        )
        
        if reviews.exists():
            # Find correlation between break ratio and productivity score
            optimal_ratio = 0.2  # Default 20%
            best_score = 0
            
            for review in reviews:
                break_ratio = review.break_time_minutes / review.focus_time_minutes
                if review.productivity_score > best_score:
                    best_score = review.productivity_score
                    optimal_ratio = break_ratio
            
            # Clamp to reasonable range
            optimal_ratio = max(0.1, min(0.4, optimal_ratio))
        else:
            optimal_ratio = 0.2
        
        confidence = min(100, reviews.count() * 3)  # 3% per review
        
        insight, created = ProductivityInsight.objects.update_or_create(
            owner_user=self.user,
            insight_type='break_pattern',
            defaults={
                'data': {'optimal_break_ratio': optimal_ratio},
                'confidence_score': confidence,
                'sample_size': reviews.count(),
                'valid_from': timezone.now().date(),
                'is_active': True
            }
        )
        
        return insight
    
    def _analyze_weekly_trends(self) -> ProductivityInsight:
        """Analyze weekly productivity trends"""
        # Get daily reviews from last 8 weeks
        eight_weeks_ago = timezone.now().date() - timedelta(weeks=8)
        
        reviews = DailyReview.objects.filter(
            owner_user=self.user,
            date__gte=eight_weeks_ago
        )
        
        # Calculate average productivity by day of week
        weekday_scores = defaultdict(list)
        for review in reviews:
            weekday = review.date.weekday()  # 0=Monday
            weekday_scores[weekday].append(float(review.productivity_score))
        
        # Calculate averages
        weekday_averages = {}
        for weekday, scores in weekday_scores.items():
            weekday_averages[weekday] = sum(scores) / len(scores) if scores else 0
        
        confidence = min(100, reviews.count())  # 1% per review
        
        insight, created = ProductivityInsight.objects.update_or_create(
            owner_user=self.user,
            insight_type='weekly_trend',
            defaults={
                'data': {'weekday_averages': weekday_averages},
                'confidence_score': confidence,
                'sample_size': reviews.count(),
                'valid_from': timezone.now().date(),
                'is_active': True
            }
        )
        
        return insight


class SmartRescheduler:
    """Service for intelligent task rescheduling"""
    
    def __init__(self, user):
        self.user = user
        self.scheduler = SmartScheduler(user)
    
    def reschedule_incomplete_tasks(self, from_date: date, to_date: date = None) -> Dict:
        """Intelligently reschedule incomplete tasks"""
        if not to_date:
            to_date = from_date + timedelta(days=7)  # Default to next week
        
        # Find incomplete tasks from the specified date
        incomplete_tasks = self._find_incomplete_tasks(from_date)
        
        if not incomplete_tasks:
            return {'rescheduled_count': 0, 'tasks': []}
        
        # Clear existing future time blocks for these tasks
        self._clear_future_blocks(incomplete_tasks, from_date)
        
        # Generate new schedule for the target period
        new_schedule = self.scheduler.generate_optimized_schedule('week', to_date)
        
        # Update task scheduling hints
        rescheduled_tasks = self._update_task_hints(incomplete_tasks, new_schedule)
        
        return {
            'rescheduled_count': len(rescheduled_tasks),
            'tasks': [{'id': task.id, 'title': task.title} for task in rescheduled_tasks],
            'new_schedule': new_schedule
        }
    
    def _find_incomplete_tasks(self, from_date: date) -> List[Task]:
        """Find tasks that were scheduled but not completed"""
        day_start = timezone.make_aware(datetime.combine(from_date, time.min))
        day_end = day_start + timedelta(days=1)
        
        # Tasks that had time blocks on this date but weren't completed
        incomplete_tasks = Task.objects.filter(
            time_blocks__start__gte=day_start,
            time_blocks__start__lt=day_end,
            is_completed=False
        ).distinct()
        
        return list(incomplete_tasks)
    
    def _clear_future_blocks(self, tasks: List[Task], from_date: date):
        """Clear future time blocks for rescheduling"""
        task_ids = [task.id for task in tasks]
        future_start = timezone.make_aware(datetime.combine(from_date, time.min))
        
        TimeBlock.objects.filter(
            task_id__in=task_ids,
            start__gte=future_start,
            status='planned'
        ).delete()
    
    def _update_task_hints(self, tasks: List[Task], new_schedule: Dict) -> List[Task]:
        """Update task scheduling hints based on new schedule"""
        rescheduled = []
        
        # Map blocks back to tasks
        task_blocks = defaultdict(list)
        for block in new_schedule.get('blocks', []):
            if block['task_id']:
                task_blocks[block['task_id']].append(block)
        
        for task in tasks:
            if task.id in task_blocks:
                # Update task with new scheduling hints
                first_block = min(task_blocks[task.id], key=lambda b: b['start'])
                task.start_at = datetime.fromisoformat(first_block['start'].replace('Z', '+00:00'))
                task.save(update_fields=['start_at'])
                rescheduled.append(task)
        
        return rescheduled
