from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class ChatCompletionRequest(BaseModel):
    model_config = ConfigDict(extra="allow")

    provider: Literal["openai", "openrouter", "grok"] = "openai"
    model: str = Field(min_length=1)
    messages: list[dict]