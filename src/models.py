from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field, HttpUrl, model_validator

class ScheduleRow(BaseModel):
    """Pydantic model for a row in the schedule.csv."""
    row_id: str
    post_date: datetime
    raw_text: str

class LLMOutput(BaseModel):
    """Pydantic model for the expected output from the LLM."""
    tweet_text: str = Field(..., description="The generated tweet text.")
    source_row_id: str = Field(..., description="The row_id from the original schedule.")

    @model_validator(mode='after')
    def check_tweet_length(self) -> 'LLMOutput':
        if len(self.tweet_text) > 280:
            raise ValueError("Tweet text exceeds 280 characters.")
        return self

class Trace(BaseModel):
    """Pydantic model for an observability trace entry."""
    timestamp: datetime = Field(default_factory=datetime.now)
    row_id: str
    raw_text: str
    llm_text: Optional[str]
    guardrail_passed: bool
    guardrail_failure_reason: Optional[str]
    final_posted_text: str
    action_status: str # "success", "skipped", "failed"

class Metrics(BaseModel):
    """Pydantic model for evaluation metrics."""
    task_completion_rate: float = Field(..., ge=0.0, le=1.0)
    groundedness_score: float = Field(..., ge=0.0, le=1.0)
    guardrail_trigger_rate: float = Field(..., ge=0.0, le=1.0)
