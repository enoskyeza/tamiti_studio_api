import logging
import openai
from openai import OpenAIError
from django.conf import settings
from .models import VACommand, AssistantLog, DefaultResponse


logger = logging.getLogger(__name__)


def resolve_va_command(assistant, user_input, user=None):
    """Attempt to resolve a VACommand from input."""
    commands = assistant.commands.all()
    for cmd in commands:
        if cmd.match_type == 'exact' and user_input.strip().lower() == cmd.trigger_text.strip().lower():
            return {'type': cmd.response_mode, 'value': cmd.response_text if cmd.response_mode == 'text' else cmd.api_endpoint}
        elif cmd.match_type == 'contains' and cmd.trigger_text.lower() in user_input.lower():
            return {'type': cmd.response_mode, 'value': cmd.response_text if cmd.response_mode == 'text' else cmd.api_endpoint}
    return None


def get_default_response(assistant):
    fallback = assistant.default_responses.first()
    return fallback.fallback_text if fallback else "I'm currently unavailable. Please try again later."


def generate_gpt_response(assistant, user_input):
    prompt = assistant.prompt_context or "You are a helpful assistant."
    openai_key = getattr(settings, "OPENAI_API_KEY", None)
    if not openai_key:
        return get_default_response(assistant)
    try:
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            api_key=openai_key,
            messages=[
                {"role": "system", "content": prompt},
                {"role": "user", "content": user_input},
            ],
            temperature=0.7,
        )
        return response.choices[0].message.content
    except OpenAIError as exc:
        logger.exception("OpenAI request failed", exc_info=exc)
        return get_default_response(assistant)


def process_va_chat(assistant, user_input, user=None):
    resolved = resolve_va_command(assistant, user_input, user)
    if resolved:
        response = resolved['value']
        used_gpt = False
    else:
        response = generate_gpt_response(assistant, user_input)
        used_gpt = True

    AssistantLog.objects.create(
        user=user,
        assistant=assistant,
        message_sent=user_input,
        response_text=response,
        used_gpt=used_gpt
    )
    return response
