"""
Groq API client for Smart Study Generator.
API key is loaded exclusively from environment variables — never exposed to the frontend.
"""

import os
from groq import Groq
from dotenv import load_dotenv

load_dotenv()

MODEL_ID = "qwen/qwen3.8-27b"   # Groq-hosted Qwen 3 27B (verified model ID)
# Free-tier OTPM limit for this model is 1000 tokens/min — stay well under it.
MAX_TOKENS = 900
TEMPERATURE = 0.6


def _get_client() -> Groq:
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        raise EnvironmentError(
            "GROQ_API_KEY is not set. "
            "Copy .env.example to .env and add your key."
        )
    return Groq(api_key=api_key)


def chat_completion(
    messages: list[dict],
    temperature: float = TEMPERATURE,
    max_tokens: int = MAX_TOKENS,
    system_override: str | None = None,
) -> str:
    """
    Send a chat-completion request to Groq and return the assistant's text.

    Parameters
    ----------
    messages       : list of {"role": ..., "content": ...} dicts
    temperature    : sampling temperature (default 0.6 for Qwen reasoning models)
    max_tokens     : max tokens in the response
    system_override: optional system prompt prepended before messages
    """
    client = _get_client()

    final_messages = []
    if system_override:
        final_messages.append({"role": "system", "content": system_override})
    final_messages.extend(messages)

    response = client.chat.completions.create(
        model=MODEL_ID,
        messages=final_messages,
        temperature=temperature,
        max_tokens=max_tokens,
    )
    return response.choices[0].message.content


def structured_chat(
    system_prompt: str,
    user_prompt: str,
    temperature: float = TEMPERATURE,
    max_tokens: int = MAX_TOKENS,
) -> str:
    """Convenience wrapper for a single-turn system + user message."""
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]
    client = _get_client()
    response = client.chat.completions.create(
        model=MODEL_ID,
        messages=messages,
        temperature=temperature,
        max_tokens=max_tokens,
    )
    return response.choices[0].message.content
