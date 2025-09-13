# tests/test_assistants_models.py
import pytest
from django.core.exceptions import ValidationError

from assistants.models import VACommand, DefaultResponse, AssistantLog
from accounts.models import StaffRole
from users.models import User
from tests.factories import UserFactory


@pytest.mark.django_db
class TestAssistantsModels:

    def test_va_command_creation_and_str(self):
        """Test VACommand model creation and string representation"""
        assistant = StaffRole.objects.create(
            title="AI Assistant",
            is_virtual=True
        )
        
        command = VACommand.objects.create(
            assistant=assistant,
            trigger_text="help me",
            match_type='exact',
            response_mode='text',
            response_text="How can I help you?",
            requires_auth=True
        )
        
        assert str(command) == "AI Assistant → help me"
        assert command.assistant == assistant
        assert command.trigger_text == "help me"
        assert command.match_type == 'exact'
        assert command.response_mode == 'text'
        assert command.response_text == "How can I help you?"
        assert command.requires_auth is True

    def test_va_command_api_mode(self):
        """Test VACommand with API response mode"""
        assistant = StaffRole.objects.create(title="API Bot")
        
        command = VACommand.objects.create(
            assistant=assistant,
            trigger_text="get weather",
            match_type='contains',
            response_mode='api',
            api_endpoint='/api/weather',
            requires_auth=False
        )
        
        assert command.response_mode == 'api'
        assert command.api_endpoint == '/api/weather'
        assert command.requires_auth is False
        assert command.response_text == ""  # Should be empty for API mode

    def test_va_command_match_types(self):
        """Test VACommand different match types"""
        assistant = StaffRole.objects.create(title="Test Assistant")
        
        # Exact match
        exact_cmd = VACommand.objects.create(
            assistant=assistant,
            trigger_text="hello",
            match_type='exact'
        )
        assert exact_cmd.match_type == 'exact'
        
        # Contains match
        contains_cmd = VACommand.objects.create(
            assistant=assistant,
            trigger_text="help",
            match_type='contains'
        )
        assert contains_cmd.match_type == 'contains'

    def test_default_response_creation_and_str(self):
        """Test DefaultResponse model creation and string representation"""
        assistant = StaffRole.objects.create(title="Fallback Assistant")
        
        default_response = DefaultResponse.objects.create(
            assistant=assistant,
            fallback_text="I'm sorry, I didn't understand that.",
            condition="unknown_command"
        )
        
        assert str(default_response) == "Fallback for Fallback Assistant"
        assert default_response.assistant == assistant
        assert default_response.fallback_text == "I'm sorry, I didn't understand that."
        assert default_response.condition == "unknown_command"

    def test_default_response_without_condition(self):
        """Test DefaultResponse without specific condition"""
        assistant = StaffRole.objects.create(title="General Assistant")
        
        default_response = DefaultResponse.objects.create(
            assistant=assistant,
            fallback_text="Please try again."
        )
        
        assert default_response.condition == ""
        assert default_response.fallback_text == "Please try again."

    def test_assistant_log_creation_and_str(self):
        """Test AssistantLog model creation and string representation"""
        user = UserFactory()
        assistant = StaffRole.objects.create(title="Chat Assistant")
        
        log = AssistantLog.objects.create(
            user=user,
            assistant=assistant,
            message_sent="Hello, how are you?",
            response_text="I'm doing well, thank you!",
            used_gpt=True
        )
        
        assert str(log) == f"Chat Assistant log @ {log.timestamp}"
        assert log.user == user
        assert log.assistant == assistant
        assert log.message_sent == "Hello, how are you?"
        assert log.response_text == "I'm doing well, thank you!"
        assert log.used_gpt is True

    def test_assistant_log_without_gpt(self):
        """Test AssistantLog without GPT usage"""
        user = UserFactory()
        assistant = StaffRole.objects.create(title="Rule-based Assistant")
        
        log = AssistantLog.objects.create(
            user=user,
            assistant=assistant,
            message_sent="status",
            response_text="System is running normally",
            used_gpt=False
        )
        
        assert log.used_gpt is False

    def test_assistant_log_with_null_user(self):
        """Test AssistantLog can have null user (anonymous interaction)"""
        assistant = StaffRole.objects.create(title="Public Assistant")
        
        log = AssistantLog.objects.create(
            user=None,
            assistant=assistant,
            message_sent="public query",
            response_text="public response"
        )
        
        assert log.user is None
        assert log.assistant == assistant

    def test_assistant_log_with_null_assistant(self):
        """Test AssistantLog can have null assistant (deleted assistant)"""
        user = UserFactory()
        assistant = StaffRole.objects.create(title="Temp Assistant")
        
        log = AssistantLog.objects.create(
            user=user,
            assistant=assistant,
            message_sent="test message",
            response_text="test response"
        )
        
        # Delete assistant
        assistant.delete()
        log.refresh_from_db()
        assert log.assistant is None
        assert log.user == user

    def test_assistant_log_timestamp_auto_set(self):
        """Test AssistantLog timestamp is automatically set"""
        user = UserFactory()
        assistant = StaffRole.objects.create(title="Time Assistant")
        
        log = AssistantLog.objects.create(
            user=user,
            assistant=assistant,
            message_sent="what time is it?",
            response_text="It's time to test!"
        )
        
        assert log.timestamp is not None
        # Timestamp should be recent (within last minute)
        from django.utils import timezone
        import datetime
        now = timezone.now()
        assert (now - log.timestamp) < datetime.timedelta(minutes=1)

    def test_va_command_cascade_on_assistant_delete(self):
        """Test VACommand is deleted when assistant is deleted"""
        assistant = StaffRole.objects.create(title="Temp Assistant")
        
        command = VACommand.objects.create(
            assistant=assistant,
            trigger_text="test command"
        )
        command_id = command.id
        
        assistant.delete()
        assert not VACommand.objects.filter(id=command_id).exists()

    def test_default_response_cascade_on_assistant_delete(self):
        """Test DefaultResponse is deleted when assistant is deleted"""
        assistant = StaffRole.objects.create(title="Temp Assistant")
        
        response = DefaultResponse.objects.create(
            assistant=assistant,
            fallback_text="Default text"
        )
        response_id = response.id
        
        assistant.delete()
        assert not DefaultResponse.objects.filter(id=response_id).exists()

    def test_multiple_commands_per_assistant(self):
        """Test assistant can have multiple commands"""
        assistant = StaffRole.objects.create(title="Multi-Command Assistant")
        
        cmd1 = VACommand.objects.create(
            assistant=assistant,
            trigger_text="hello",
            response_text="Hi there!"
        )
        
        cmd2 = VACommand.objects.create(
            assistant=assistant,
            trigger_text="goodbye",
            response_text="See you later!"
        )
        
        commands = assistant.commands.all()
        assert cmd1 in commands
        assert cmd2 in commands
        assert commands.count() == 2

    def test_multiple_default_responses_per_assistant(self):
        """Test assistant can have multiple default responses"""
        assistant = StaffRole.objects.create(title="Multi-Response Assistant")
        
        resp1 = DefaultResponse.objects.create(
            assistant=assistant,
            fallback_text="General fallback",
            condition=""
        )
        
        resp2 = DefaultResponse.objects.create(
            assistant=assistant,
            fallback_text="Error fallback",
            condition="error"
        )
        
        responses = assistant.default_responses.all()
        assert resp1 in responses
        assert resp2 in responses
        assert responses.count() == 2

    def test_base_model_inheritance(self):
        """Test that all models inherit BaseModel fields"""
        assistant = StaffRole.objects.create(title="Base Test Assistant")
        
        command = VACommand.objects.create(
            assistant=assistant,
            trigger_text="test"
        )
        
        response = DefaultResponse.objects.create(
            assistant=assistant,
            fallback_text="test"
        )
        
        log = AssistantLog.objects.create(
            assistant=assistant,
            message_sent="test",
            response_text="test"
        )
        
        # Check BaseModel fields exist
        for obj in [command, response, log]:
            assert hasattr(obj, 'created_at')
            assert hasattr(obj, 'updated_at')
            assert hasattr(obj, 'uuid')
            assert hasattr(obj, 'is_deleted')
            assert hasattr(obj, 'deleted_at')
