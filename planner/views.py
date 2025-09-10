from __future__ import annotations

from datetime import datetime, timedelta, time, date
from typing import List, Tuple

from django.db.models import Q
from django.utils import timezone
from django.utils.dateparse import parse_date
from django.core.cache import cache


from rest_framework import permissions, generics, status, viewsets
from rest_framework.decorators import api_view, permission_classes, action
from rest_framework.response import Response

from accounts.models import Department
from tasks.models import Task
from planner.models import (
    BreakPolicy, AvailabilityTemplate, CalendarEvent, TimeBlock,
    DailyReview, WorkGoal, ProductivityInsight
)
from planner.serializers import (
    TimeBlockSerializer, CalendarEventSerializer, DailyReviewSerializer,
    WorkGoalSerializer, ProductivityInsightSerializer
)
from planner.services import SmartScheduler, ProductivityAnalyzer, SmartRescheduler


def _preview_schedule(user, scope: str, date_str: str) -> dict:
    """Legacy schedule preview - kept for backward compatibility
    
    Compute a schedule preview dictionary without touching HTTP layer.
    Returns a dict matching PlannerPreviewResponse in API guide.
    Raises ValueError for invalid dates.
    """
    if not date_str:
        # Let caller handle required validation
        raise ValueError("date required")

    try:
        day = parse_date(date_str)
        if not day:
            raise ValueError()
        tz = timezone.get_current_timezone()
        day_dt = timezone.make_aware(datetime.combine(day, time(0, 0)), tz)
    except Exception:
        raise ValueError("invalid date format")

    focus, short_break, long_break = _get_breaks(user)

    if scope == 'week':
        start = day_dt - timedelta(days=day_dt.weekday())
        end = start + timedelta(days=7)
        windows: List[Tuple[datetime, datetime]] = []
        cur = start
        while cur < end:
            windows += _subtract_events(user, _day_window(user, cur))
            cur += timedelta(days=1)
    else:
        start = day_dt
        end = day_dt + timedelta(days=1)
        windows = _subtract_events(user, _day_window(user, day_dt))

    tasks = list(_candidate_tasks(user, start, end))
    blocks = _pack(windows, tasks, focus=focus, short_break=short_break)

    def _ser(b):
        return {
            'task_id': b['task_id'],
            'title': b['title'],
            'start': b['start'].isoformat(),
            'end': b['end'].isoformat(),
            'is_break': b['is_break'],
        }

    total_free_minutes = int(sum((e - s).total_seconds() for s, e in windows) / 60)
    planned_minutes = int(sum((b['end'] - b['start']).total_seconds() for b in blocks if not b['is_break']) / 60)
    capacity_usage = planned_minutes / total_free_minutes if total_free_minutes else 0

    return {
        'blocks': [_ser(b) for b in blocks],
        'capacity_usage': capacity_usage,
        'window_minutes': total_free_minutes,
        'planned_minutes': planned_minutes,
    }


def _user_department(user) -> Department | None:
    try:
        return getattr(user, 'staff_profile', None) and user.staff_profile.department
    except Exception:
        return None


def _get_breaks(user) -> Tuple[int, int, int]:
    pol = BreakPolicy.objects.filter(owner_user=user, active=True).first()
    if not pol:
        dept = _user_department(user)
        if dept:
            pol = BreakPolicy.objects.filter(owner_team=dept, active=True).first()
    if not pol:
        return 25, 5, 15
    return pol.focus_minutes, pol.break_minutes, pol.long_break_minutes


def _day_window(user, date_: datetime) -> List[Tuple[datetime, datetime]]:
    # Availability for the weekday
    weekday = date_.weekday()  # 0=Mon
    templates = AvailabilityTemplate.objects.filter(owner_user=user, day_of_week=weekday)
    if not templates.exists():
        dept = _user_department(user)
        if dept:
            templates = AvailabilityTemplate.objects.filter(owner_team=dept, day_of_week=weekday)
    if not templates.exists():
        # default 09:00-17:00
        start_dt = datetime.combine(date_.date(), time(9, 0, tzinfo=timezone.get_current_timezone()))
        end_dt = datetime.combine(date_.date(), time(17, 0, tzinfo=timezone.get_current_timezone()))
        return [(start_dt, end_dt)]
    blocks = []
    tz = timezone.get_current_timezone()
    for t in templates:
        s = datetime.combine(date_.date(), t.start_time, tz)
        e = datetime.combine(date_.date(), t.end_time, tz)
        blocks.append((s, e))
    return blocks


def _subtract_events(user, windows: List[Tuple[datetime, datetime]]) -> List[Tuple[datetime, datetime]]:
    if not windows:
        return []
    start = min(w[0] for w in windows)
    end = max(w[1] for w in windows)
    dept = _user_department(user)
    q = Q(owner_user=user) | (Q(owner_team=dept) if dept else Q(pk__isnull=True))
    events = CalendarEvent.objects.filter(q, is_busy=True, start__lt=end, end__gt=start)
    free = windows[:]
    for ev in events:
        updated: List[Tuple[datetime, datetime]] = []
        for s, e in free:
            if ev.end <= s or ev.start >= e:
                updated.append((s, e))
            else:
                if s < ev.start:
                    updated.append((s, ev.start))
                if ev.end < e:
                    updated.append((ev.end, e))
        free = [(s, e) for s, e in updated if (e - s).total_seconds() >= 60]
    return free


def _candidate_tasks(user, scope_start: datetime, scope_end: datetime):
    dept = _user_department(user)
    qs = Task.objects.filter(
        is_completed=False
    ).filter(
        Q(created_by=user) | Q(assigned_to=user) | Q(project__created_by=user) | (Q(assigned_team=dept) if dept else Q(pk__isnull=True))
    ).exclude(
        snoozed_until__gt=scope_end
    ).exclude(
        dependencies__is_completed=False
    ).distinct()
    # respect backlog_date: not before this date
    return qs.filter(Q(backlog_date__isnull=True) | Q(backlog_date__lte=scope_start.date()))


def _minutes_for(task: Task) -> int:
    if task.estimated_minutes:
        return int(task.estimated_minutes)
    if task.estimated_hours:
        return int(task.estimated_hours) * 60
    return 60


def _priority_weight(p: str) -> int:
    return {
        'critical': 100,
        'high': 70,
        'medium': 40,
        'low': 10,
    }.get(p or 'medium', 40)


def _score(task: Task, ref: datetime) -> float:
    base = _priority_weight(task.priority)
    due_bonus = 0
    if task.due_date:
        delta = (task.due_date - ref).total_seconds() / 3600.0
        # closer due dates get higher
        due_bonus = max(0, 48 - max(0, delta))
    overdue_bonus = 20 if (task.due_date and task.due_date < ref) else 0
    return base + due_bonus + overdue_bonus


def _pack(time_windows: List[Tuple[datetime, datetime]], tasks: List[Task], focus: int, short_break: int) -> List[dict]:
    blocks: List[dict] = []
    if not time_windows:
        return blocks
    # tasks sorted by score descending, then due asc
    now = timezone.now()
    tasks_sorted = sorted(
        tasks,
        key=lambda t: (-_score(t, now), t.due_date or (now + timedelta(days=365)))
    )
    # cursor per window
    windows = list(time_windows)
    wi = 0
    cur_start, cur_end = windows[wi]

    def advance_cursor(dt: datetime) -> Tuple[datetime, datetime, int]:
        nonlocal wi
        while dt >= windows[wi][1]:
            wi += 1
            if wi >= len(windows):
                return None, None, wi
            dt = windows[wi][0]
        return dt, windows[wi][1], wi

    cursor = cur_start
    for task in tasks_sorted:
        remaining = _minutes_for(task)
        while remaining > 0 and wi < len(windows):
            cursor, cur_end, wi = advance_cursor(cursor)
            if cursor is None:
                break
            # place a focus block
            end_block = min(cursor + timedelta(minutes=focus), cur_end)
            actual = int((end_block - cursor).total_seconds() / 60)
            if actual <= 0:
                cursor = cur_end
                continue
            blocks.append({
                'task_id': task.id,
                'title': task.title,
                'start': cursor,
                'end': end_block,
                'is_break': False,
            })
            remaining -= actual
            cursor = end_block
            # add a break if there is still time and remaining work
            if remaining > 0 and cursor + timedelta(minutes=short_break) <= cur_end:
                b_end = cursor + timedelta(minutes=short_break)
                blocks.append({
                    'task_id': None,
                    'title': 'Break',
                    'start': cursor,
                    'end': b_end,
                    'is_break': True,
                })
                cursor = b_end
            if cursor >= cur_end:
                wi += 1
                if wi < len(windows):
                    cursor = windows[wi][0]

    return blocks


@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def schedule_preview(request):
    """Enhanced schedule preview with smart algorithms"""
    scope = request.data.get('scope', 'day')
    date_str = request.data.get('date')
    use_smart = request.data.get('smart', True)  # Use smart scheduler by default
    
    if not date_str:
        return Response({'error': 'date is required'}, status=status.HTTP_400_BAD_REQUEST)
    
    try:
        target_date = parse_date(date_str)
        if not target_date:
            raise ValueError("Invalid date format")
        
        if use_smart:
            # Use enhanced smart scheduler
            scheduler = SmartScheduler(request.user)
            data = scheduler.generate_optimized_schedule(scope, target_date)
        else:
            # Fallback to original algorithm
            data = _preview_schedule(request.user, scope, date_str)
            
    except ValueError:
        return Response({'error': 'invalid date format (YYYY-MM-DD)'}, status=status.HTTP_400_BAD_REQUEST)
    
    return Response(data)


@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def schedule_commit(request):
    scope = request.data.get('scope', 'day')
    date_str = request.data.get('date')
    print(f"🔥 COMMIT API DEBUG - User: {request.user.username}, Date: {date_str}")
    
    if not date_str:
        return Response({'error': 'date is required'}, status=status.HTTP_400_BAD_REQUEST)
    try:
        data = _preview_schedule(request.user, scope, date_str)
    except ValueError:
        return Response({'error': 'invalid date format (YYYY-MM-DD)'}, status=status.HTTP_400_BAD_REQUEST)
    blocks = data.get('blocks', [])
    print(f"🔥 Blocks to create: {len(blocks)}")
    
    created = []
    from django.utils.dateparse import parse_datetime
    for i, b in enumerate(blocks):
        start_dt = parse_datetime(b['start']) if isinstance(b['start'], str) else b['start']
        end_dt = parse_datetime(b['end']) if isinstance(b['end'], str) else b['end']
        
        print(f"🔥 Creating block {i+1}: {b['title']}, start: {start_dt}, end: {end_dt}")
        
        tb = TimeBlock.objects.create(
            owner_user=request.user,
            task_id=b['task_id'],
            title=b['title'],
            start=start_dt,
            end=end_dt,
            status='committed',
            is_break=b['is_break'],
            source='auto'
        )
        created.append(tb)
        print(f"🔥 Created TimeBlock ID: {tb.id}")
    
    print(f"🔥 Total created blocks: {len(created)}")
    return Response(TimeBlockSerializer(created, many=True).data, status=201)


@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def replan(request):
    """Smart replanning with rescheduling of incomplete tasks"""
    from_date_str = request.data.get('from_date')
    to_date_str = request.data.get('to_date')
    
    if not from_date_str:
        return Response({'error': 'from_date is required'}, status=status.HTTP_400_BAD_REQUEST)
    
    try:
        from_date = parse_date(from_date_str)
        to_date = parse_date(to_date_str) if to_date_str else None
        
        if not from_date:
            raise ValueError("Invalid from_date format")
        
        # Use smart rescheduler
        rescheduler = SmartRescheduler(request.user)
        result = rescheduler.reschedule_incomplete_tasks(from_date, to_date)
        
        return Response(result)
        
    except ValueError as e:
        return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)


class BlockListView(generics.ListAPIView):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = TimeBlockSerializer

    def get_queryset(self):
        user = self.request.user
        print(f"🔍 BlockListView DEBUG - User: {user.username}")
        
        qs = TimeBlock.objects.filter(owner_user=user)
        print(f"🔍 Initial queryset count: {qs.count()}")
        
        # Print all blocks for this user
        all_blocks = list(qs.values('id', 'title', 'start', 'end', 'status'))
        print(f"🔍 All user blocks: {all_blocks}")
        
        start = self.request.query_params.get('start')
        end = self.request.query_params.get('end')
        print(f"🔍 Query params - start: {start}, end: {end}")
        
        if start:
            from django.utils.dateparse import parse_datetime, parse_date
            from django.utils import timezone
            from datetime import datetime, time
            from zoneinfo import ZoneInfo
            # Try parsing as datetime first, then as date
            s = parse_datetime(start)
            if not s:
                date_obj = parse_date(start)
                if date_obj:
                    s = timezone.make_aware(datetime.combine(date_obj, time.min), ZoneInfo("UTC"))
            print(f"🔍 Parsed start datetime: {s}")
            if s:
                qs = qs.filter(start__gte=s)
                print(f"🔍 After start filter count: {qs.count()}")
        if end:
            from django.utils.dateparse import parse_datetime, parse_date
            from django.utils import timezone
            from datetime import datetime, time
            from zoneinfo import ZoneInfo
            # Try parsing as datetime first, then as date
            e = parse_datetime(end)
            if not e:
                date_obj = parse_date(end)
                if date_obj:
                    e = timezone.make_aware(datetime.combine(date_obj, time(23, 59, 59)), ZoneInfo("UTC"))
            print(f"🔍 Parsed end datetime: {e}")
            if e:
                qs = qs.filter(start__lte=e)
                print(f"🔍 After end filter count: {qs.count()}")
        
        final_blocks = list(qs.values('id', 'title', 'start', 'end', 'status'))
        print(f"🔍 Final filtered blocks: {final_blocks}")
        
        return qs.order_by('start')


class BlockDetailView(generics.RetrieveUpdateDestroyAPIView):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = TimeBlockSerializer

    def get_queryset(self):
        return TimeBlock.objects.filter(owner_user=self.request.user)


class CalendarEventListCreateView(generics.ListCreateAPIView):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = CalendarEventSerializer

    def get_queryset(self):
        return CalendarEvent.objects.filter(owner_user=self.request.user)

    def perform_create(self, serializer):
        serializer.save(owner_user=self.request.user)


class CalendarEventDetailView(generics.RetrieveUpdateDestroyAPIView):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = CalendarEventSerializer

    def get_queryset(self):
        return CalendarEvent.objects.filter(owner_user=self.request.user)


class DailyReviewViewSet(viewsets.ModelViewSet):
    """ViewSet for daily reviews and productivity tracking"""
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = DailyReviewSerializer

    def get_queryset(self):
        return DailyReview.objects.filter(owner_user=self.request.user)

    def perform_create(self, serializer):
        serializer.save(owner_user=self.request.user)

    @action(detail=False, methods=['post'])
    def compute_metrics(self, request):
        """Compute productivity metrics for a specific date"""
        date_str = request.data.get('date')
        if not date_str:
            return Response({'error': 'date is required'}, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            target_date = parse_date(date_str)
            if not target_date:
                raise ValueError("Invalid date format")
            
            analyzer = ProductivityAnalyzer(request.user)
            review = analyzer.compute_daily_review(target_date)
            
            return Response(DailyReviewSerializer(review).data)
            
        except ValueError:
            return Response({'error': 'invalid date format (YYYY-MM-DD)'}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=False, methods=['get'])
    def productivity_stats(self, request):
        """Get productivity statistics and trends"""
        days = int(request.query_params.get('days', 30))
        start_date = timezone.now().date() - timedelta(days=days)
        
        reviews = self.get_queryset().filter(date__gte=start_date)
        
        if not reviews.exists():
            return Response({
                'avg_productivity_score': 0,
                'avg_completion_rate': 0,
                'current_streak': 0,
                'total_focus_hours': 0,
                'trend': 'no_data'
            })
        
        # Calculate aggregated stats
        total_reviews = reviews.count()
        avg_productivity = sum(float(r.productivity_score) for r in reviews) / total_reviews
        avg_completion = sum(float(r.completion_rate) for r in reviews) / total_reviews
        total_focus_minutes = sum(r.focus_time_minutes for r in reviews)
        current_streak = reviews.order_by('-date').first().current_streak
        
        # Calculate trend (last 7 days vs previous 7 days)
        recent_reviews = reviews.filter(date__gte=timezone.now().date() - timedelta(days=7))
        older_reviews = reviews.filter(
            date__gte=timezone.now().date() - timedelta(days=14),
            date__lt=timezone.now().date() - timedelta(days=7)
        )
        
        trend = 'stable'
        if recent_reviews.exists() and older_reviews.exists():
            recent_avg = sum(float(r.productivity_score) for r in recent_reviews) / recent_reviews.count()
            older_avg = sum(float(r.productivity_score) for r in older_reviews) / older_reviews.count()
            
            if recent_avg > older_avg + 5:
                trend = 'improving'
            elif recent_avg < older_avg - 5:
                trend = 'declining'
        
        return Response({
            'avg_productivity_score': round(avg_productivity, 2),
            'avg_completion_rate': round(avg_completion, 2),
            'current_streak': current_streak,
            'total_focus_hours': round(total_focus_minutes / 60, 1),
            'trend': trend,
            'total_days': total_reviews
        })


class WorkGoalViewSet(viewsets.ModelViewSet):
    """ViewSet for work goals management"""
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = WorkGoalSerializer

    def get_queryset(self):
        qs = WorkGoal.objects.filter(
            Q(owner_user=self.request.user) | 
            Q(owner_team__in=self.request.user.staff_profile.department if hasattr(self.request.user, 'staff_profile') else [])
        )
        
        # Filter by active status
        if self.request.query_params.get('active_only', 'true').lower() == 'true':
            qs = qs.filter(is_active=True)
        
        return qs.order_by('-created_at')

    def perform_create(self, serializer):
        serializer.save(owner_user=self.request.user)

    @action(detail=True, methods=['post'])
    def update_progress(self, request, pk=None):
        """Manually trigger progress update for a goal"""
        goal = self.get_object()
        goal.update_progress()
        return Response(WorkGoalSerializer(goal).data)


class ProductivityInsightViewSet(viewsets.ReadOnlyModelViewSet):
    """ViewSet for productivity insights (read-only)"""
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = ProductivityInsightSerializer

    def get_queryset(self):
        return ProductivityInsight.objects.filter(
            owner_user=self.request.user,
            is_active=True
        )

    @action(detail=False, methods=['post'])
    def generate_insights(self, request):
        """Generate fresh productivity insights"""
        analyzer = ProductivityAnalyzer(request.user)
        insights = analyzer.generate_productivity_insights()
        
        serialized_insights = {}
        for insight_type, insight in insights.items():
            serialized_insights[insight_type] = ProductivityInsightSerializer(insight).data
        
        return Response({
            'generated_count': len(insights),
            'insights': serialized_insights
        })


@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def bulk_reschedule(request):
    """Bulk reschedule multiple tasks"""
    task_ids = request.data.get('task_ids', [])
    target_date_str = request.data.get('target_date')
    
    if not task_ids:
        return Response({'error': 'task_ids is required'}, status=status.HTTP_400_BAD_REQUEST)
    
    if not target_date_str:
        return Response({'error': 'target_date is required'}, status=status.HTTP_400_BAD_REQUEST)
    
    try:
        target_date = parse_date(target_date_str)
        if not target_date:
            raise ValueError("Invalid target_date format")
        
        # Verify user has access to these tasks
        user_tasks = Task.objects.filter(
            Q(created_by=request.user) | Q(assigned_to=request.user) | Q(project__created_by=request.user),
            id__in=task_ids
        )
        
        if user_tasks.count() != len(task_ids):
            return Response({'error': 'Some tasks not found or not accessible'}, status=status.HTTP_404_NOT_FOUND)
        
        # Clear existing future blocks
        future_start = timezone.make_aware(datetime.combine(target_date, time.min))
        TimeBlock.objects.filter(
            task__in=user_tasks,
            start__gte=future_start,
            status='planned'
        ).delete()
        
        # Generate new schedule
        scheduler = SmartScheduler(request.user)
        new_schedule = scheduler.generate_optimized_schedule('week', target_date)
        
        return Response({
            'rescheduled_tasks': user_tasks.count(),
            'new_schedule': new_schedule
        })
        
    except ValueError:
        return Response({'error': 'invalid target_date format (YYYY-MM-DD)'}, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def productivity_dashboard(request):
    """Get comprehensive productivity dashboard data"""
    # Get recent daily review
    latest_review = DailyReview.objects.filter(owner_user=request.user).order_by('-date').first()
    
    # Get active work goals
    active_goals = WorkGoal.objects.filter(
        Q(owner_user=request.user) | Q(owner_team__in=[
            request.user.staff_profile.department if hasattr(request.user, 'staff_profile') else None
        ]),
        is_active=True
    )[:5]
    
    # Get productivity insights
    insights = ProductivityInsight.objects.filter(
        owner_user=request.user,
        is_active=True
    )
    
    # Get upcoming scheduled tasks
    tomorrow = timezone.now().date() + timedelta(days=1)
    tomorrow_start = timezone.make_aware(datetime.combine(tomorrow, time.min))
    tomorrow_end = tomorrow_start + timedelta(days=1)
    
    upcoming_blocks = TimeBlock.objects.filter(
        owner_user=request.user,
        start__gte=tomorrow_start,
        start__lt=tomorrow_end,
        status='planned',
        is_break=False
    ).select_related('task')[:10]
    
    return Response({
        'latest_review': DailyReviewSerializer(latest_review).data if latest_review else None,
        'active_goals': WorkGoalSerializer(active_goals, many=True).data,
        'insights': ProductivityInsightSerializer(insights, many=True).data,
        'upcoming_tasks': TimeBlockSerializer(upcoming_blocks, many=True).data,
        'dashboard_generated_at': timezone.now().isoformat()
    })
