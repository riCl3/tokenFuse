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

# Backwards-compat: keep sync estimator for scripts/tests where project context is N/A.
# New code should use estimate_cost_usd_for_project.


def estimate_cost_usd(model: str, prompt_tokens: int, completion_tokens: int) -> float:
    price = MODEL_PRICING.get(model)
    if price is None:
        return 0.0
    return (
        prompt_tokens / 1_000_000 * price["input"]
        + completion_tokens / 1_000_000 * price["output"]
    )


def _price_from_project(project, model: str) -> dict[str, float] | None:
    """Return per-project override if present."""
    if project is None:
        return None
    overrides = getattr(project, "custom_pricing", None)
    if not overrides or not isinstance(overrides, dict):
        return None
    raw = overrides.get(model)
    if not raw or not isinstance(raw, dict):
        return None
    try:
        return {"input": float(raw["input"]), "output": float(raw["output"])}
    except Exception:
        return None


async def estimate_cost_usd_for_project(
    model: str,
    prompt_tokens: int,
    completion_tokens: int,
    project=None,
    session=None,
) -> float:
    """
    Cost lookup order:
      1) per-project custom_pricing (Project.custom_pricing JSON)
      2) global ModelPricing table (if session provided, else skipped)
      3) hardcoded MODEL_PRICING
      4) 0.0 for unknown models
    """
    # 1) per-project override — no DB query needed
    price = _price_from_project(project, model)
    if price is not None:
        return (
            prompt_tokens / 1_000_000 * price["input"]
            + completion_tokens / 1_000_000 * price["output"]
        )

    # 2) global DB table — only if we have a session
    if session is not None:
        try:
            from sqlalchemy import select
            from app.db.models import ModelPricing

            row = (
                await session.execute(
                    select(ModelPricing).where(
                        ModelPricing.model == model,
                        ModelPricing.is_active.is_(True),
                    )
                )
            ).scalar_one_or_none()
            if row is not None:
                return (
                    prompt_tokens / 1_000_000 * float(row.input_price)
                    + completion_tokens / 1_000_000 * float(row.output_price)
                )
        except Exception:
            # If the table doesn't exist yet (tests without migration) or session is closed,
            # fall through to hardcoded map.
            pass

    # 3) hardcoded fallback
    return estimate_cost_usd(model, prompt_tokens, completion_tokens)