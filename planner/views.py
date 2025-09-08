from __future__ import annotations

from datetime import datetime, timedelta, time
from typing import List, Tuple

from django.db.models import Q
from django.utils import timezone
from django.utils.dateparse import parse_date

from rest_framework import permissions, generics, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

from accounts.models import Department
from tasks.models import Task
from planner.models import BreakPolicy, AvailabilityTemplate, CalendarEvent, TimeBlock
from planner.serializers import TimeBlockSerializer, CalendarEventSerializer


def _preview_schedule(user, scope: str, date_str: str) -> dict:
    """Compute a schedule preview dictionary without touching HTTP layer.

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
    scope = request.data.get('scope', 'day')
    date_str = request.data.get('date')
    if not date_str:
        return Response({'error': 'date is required'}, status=status.HTTP_400_BAD_REQUEST)
    try:
        data = _preview_schedule(request.user, scope, date_str)
    except ValueError:
        return Response({'error': 'invalid date format (YYYY-MM-DD)'}, status=status.HTTP_400_BAD_REQUEST)
    return Response(data)


@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def schedule_commit(request):
    scope = request.data.get('scope', 'day')
    date_str = request.data.get('date')
    if not date_str:
        return Response({'error': 'date is required'}, status=status.HTTP_400_BAD_REQUEST)
    try:
        data = _preview_schedule(request.user, scope, date_str)
    except ValueError:
        return Response({'error': 'invalid date format (YYYY-MM-DD)'}, status=status.HTTP_400_BAD_REQUEST)
    blocks = data.get('blocks', [])
    created = []
    from django.utils.dateparse import parse_datetime
    for b in blocks:
        tb = TimeBlock.objects.create(
            owner_user=request.user,
            task_id=b['task_id'],
            title=b['title'],
            start=parse_datetime(b['start']) if isinstance(b['start'], str) else b['start'],
            end=parse_datetime(b['end']) if isinstance(b['end'], str) else b['end'],
            status='committed',
            is_break=b['is_break'],
            source='auto'
        )
        created.append(tb)
    return Response(TimeBlockSerializer(created, many=True).data, status=201)


@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def replan(request):
    # Alias to preview for now
    return schedule_preview(request)


class BlockListView(generics.ListAPIView):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = TimeBlockSerializer

    def get_queryset(self):
        user = self.request.user
        qs = TimeBlock.objects.filter(owner_user=user)
        start = self.request.query_params.get('start')
        end = self.request.query_params.get('end')
        if start:
            from django.utils.dateparse import parse_datetime
            s = parse_datetime(start)
            if s:
                qs = qs.filter(end__gte=s)
        if end:
            from django.utils.dateparse import parse_datetime
            e = parse_datetime(end)
            if e:
                qs = qs.filter(start__lte=e)
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
