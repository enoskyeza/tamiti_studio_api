# tests/test_timezone.py
from datetime import datetime, date
from zoneinfo import ZoneInfo
from django.test import TestCase
from django.utils import timezone
from django.contrib.auth import get_user_model
from common.timezone_utils import day_bounds_utc, get_user_timezone, convert_to_user_timezone
from users.models import UserPreferences

User = get_user_model()


class TimezoneTestCase(TestCase):
    """Test timezone handling across the application"""
    
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.preferences, created = UserPreferences.objects.get_or_create(
            user=self.user,
            defaults={'timezone': 'Africa/Kampala'}
        )
    
    def test_timestamps_are_aware(self):
        """Test that model timestamps are timezone-aware"""
        self.assertTrue(timezone.is_aware(self.user.date_joined))
        self.assertTrue(timezone.is_aware(self.user.last_login or timezone.now()))
        self.assertTrue(timezone.is_aware(self.preferences.created_at))
    
    def test_day_bounds_utc_conversion(self):
        """Test local date to UTC bounds conversion"""
        local_date = date(2025, 1, 15)
        start_utc, end_utc = day_bounds_utc(local_date, 'Africa/Kampala')
        
        # Kampala is UTC+3, so local midnight should be 21:00 UTC previous day
        expected_start = datetime(2025, 1, 14, 21, 0, 0, tzinfo=ZoneInfo("UTC"))
        expected_end = datetime(2025, 1, 15, 21, 0, 0, tzinfo=ZoneInfo("UTC"))
        
        self.assertEqual(start_utc, expected_start)
        self.assertEqual(end_utc, expected_end)
    
    def test_day_bounds_utc_invalid_timezone(self):
        """Test fallback behavior with invalid timezone"""
        local_date = date(2025, 1, 15)
        start_utc, end_utc = day_bounds_utc(local_date, 'Invalid/Timezone')
        
        # Should fallback to UTC
        expected_start = datetime(2025, 1, 15, 0, 0, 0, tzinfo=ZoneInfo("UTC"))
        expected_end = datetime(2025, 1, 16, 0, 0, 0, tzinfo=ZoneInfo("UTC"))
        
        self.assertEqual(start_utc, expected_start)
        self.assertEqual(end_utc, expected_end)
    
    def test_get_user_timezone(self):
        """Test user timezone retrieval"""
        user_tz = get_user_timezone(self.user)
        self.assertEqual(user_tz, 'Africa/Kampala')
        
        # Test user without preferences
        user_no_prefs = User.objects.create_user(
            username='noprofs',
            email='noprofs@example.com',
            password='testpass123'
        )
        user_tz = get_user_timezone(user_no_prefs)
        self.assertEqual(user_tz, 'Africa/Kampala')  # Default fallback
    
    def test_convert_to_user_timezone(self):
        """Test UTC to user timezone conversion"""
        utc_dt = datetime(2025, 1, 15, 12, 0, 0, tzinfo=ZoneInfo("UTC"))
        user_dt = convert_to_user_timezone(utc_dt, 'Africa/Kampala')
        
        # UTC 12:00 should be 15:00 in Kampala (UTC+3)
        expected = datetime(2025, 1, 15, 15, 0, 0, tzinfo=ZoneInfo("Africa/Kampala"))
        self.assertEqual(user_dt, expected)
    
    def test_timezone_now_usage(self):
        """Test that timezone.now() is used instead of datetime.now()"""
        now = timezone.now()
        self.assertTrue(timezone.is_aware(now))
        # Django's timezone.now() uses datetime.timezone.utc, not zoneinfo.ZoneInfo
        self.assertEqual(str(now.tzinfo), 'UTC')
    
    def test_user_preferences_default_timezone(self):
        """Test that user preferences have correct default timezone"""
        new_user = User.objects.create_user(
            username='newuser',
            email='new@example.com',
            password='testpass123'
        )
        prefs, created = UserPreferences.objects.get_or_create(user=new_user)
        self.assertEqual(prefs.timezone, 'Africa/Kampala')
