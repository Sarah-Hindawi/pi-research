"""
LLM client (LLM_PROVIDER=anthropic)
"""
from config import get_settings
import anthropic

settings = get_settings()


class PlaceholderLLM:
    """Stands in for Claude until API key is provided day-of."""

    def invoke(self, messages: list[dict]) -> str:
        last = messages[-1].get("content", "") if messages else ""
        return (
            f"[PLACEHOLDER -Claude not yet connected]\n\n"
            f"Your query: '{last[:200]}'\n\n"
            f"Once ANTHROPIC_API_KEY is set and LLM_PROVIDER=anthropic, "
            f"this will return a real cited answer."
        )

    async def ainvoke(self, messages: list[dict]) -> str:
        return self.invoke(messages)


class AnthropicLLM:
    def __init__(self):
        self._client = anthropic.Anthropic(api_key=settings.anthropic_api_key)

    def invoke(self, messages: list[dict], system: str = "") -> str:
        response = self._client.messages.create(
            model=settings.llm_model,
            max_tokens=2048,
            system=system,
            messages=messages,
        )
        return response.content[0].text

    async def ainvoke(self, messages: list[dict], system: str = "") -> str:
        # For now wraps sync — swap to async client if needed
        return self.invoke(messages, system)


def get_llm():
    if settings.llm_provider == "anthropic" and settings.anthropic_api_key:
        return AnthropicLLM()
    return PlaceholderLLM()
