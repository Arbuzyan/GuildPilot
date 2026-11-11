
import anthropic

from app.config import settings


def generate_response(
    system_prompt: str,
    messages: list[dict[str, str]],
) -> str:
    """Generate an AI response using the configured Anthropic model."""

    if not settings.ANTHROPIC_API_KEY:
        raise RuntimeError(
            "ANTHROPIC_API_KEY is not configured. "
            "Check your .env file."
        )

    client = anthropic.Anthropic(
        api_key=settings.ANTHROPIC_API_KEY,
    )

    response = client.messages.create(
        model=settings.ANTHROPIC_MODEL,
        max_tokens=300,
        system=system_prompt,
        messages=messages,
    )

    return "".join(
        block.text
        for block in response.content
        if block.type == "text"
    )
