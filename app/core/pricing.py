MODEL_PRICING: dict[str, dict[str, float]] = {
    # OpenAI
    "gpt-4o": {"input": 2.50, "output": 10.00},
    "gpt-4o-mini": {"input": 0.15, "output": 0.60},
    "gpt-4.1": {"input": 2.00, "output": 8.00},
    "gpt-4.1-mini": {"input": 0.40, "output": 1.60},
    "gpt-3.5-turbo": {"input": 0.50, "output": 1.50},
    # Anthropic
    "claude-3-5-sonnet-20241022": {"input": 3.00, "output": 15.00},
    "claude-3-5-haiku-20241022": {"input": 0.80, "output": 4.00},
    # xAI Grok
    "grok-4.6": {"input": 2.00, "output": 6.00},
    "grok-4.5": {"input": 2.00, "output": 6.00},
    "grok-4.3": {"input": 1.25, "output": 2.50},
    "grok-4.20-0309-reasoning": {"input": 1.25, "output": 2.50},
    "grok-4.20-0309-non-reasoning": {"input": 1.25, "output": 2.50},
    "grok-build-0.1": {"input": 1.00, "output": 2.00},
    # Groq
    "openai/gpt-oss-120b": {"input": 0.15, "output": 0.60},
    "openai/gpt-oss-20b": {"input": 0.075, "output": 0.30},
}


def estimate_cost_usd(model: str, prompt_tokens: int, completion_tokens: int) -> float:
    price = MODEL_PRICING.get(model)
    if price is None:
        return 0.0
    return (
        prompt_tokens / 1_000_000 * price["input"]
        + completion_tokens / 1_000_000 * price["output"]
    )