from datetime import datetime
import pytest
from pydantic import ValidationError

from src.models import ScheduleRow, LLMOutput, Trace, Metrics

def test_schedule_row_model():
    now = datetime.now()
    row = ScheduleRow(row_id="1", post_date=now, raw_text="Hello")
    assert row.row_id == "1"
    assert row.post_date == now
    assert row.raw_text == "Hello"

def test_llm_output_model_valid():
    output = LLMOutput(tweet_text="Short tweet", source_row_id="abc")
    assert output.tweet_text == "Short tweet"
    assert output.source_row_id == "abc"

def test_llm_output_model_length_validation_fail():
    long_text = "a" * 281
    with pytest.raises(ValidationError, match="Tweet text exceeds 280 characters."):
        LLMOutput(tweet_text=long_text, source_row_id="abc")

def test_llm_output_model_length_validation_pass():
    long_text = "a" * 280
    output = LLMOutput(tweet_text=long_text, source_row_id="abc")
    assert output.tweet_text == long_text

def test_trace_model():
    now = datetime.now()
    trace = Trace(
        timestamp=now,
        row_id="1",
        raw_text="raw",
        llm_text="llm",
        guardrail_passed=True,
        guardrail_failure_reason=None,
        final_posted_text="final",
        action_status="success"
    )
    assert trace.timestamp == now
    assert trace.row_id == "1"
    assert trace.action_status == "success"

def test_metrics_model_valid():
    metrics = Metrics(
        task_completion_rate=0.8,
        groundedness_score=0.9,
        guardrail_trigger_rate=0.1
    )
    assert metrics.task_completion_rate == 0.8

def test_metrics_model_invalid_range():
    with pytest.raises(ValidationError):
        Metrics(task_completion_rate=1.1, groundedness_score=0.5, guardrail_trigger_rate=0.5)
    with pytest.raises(ValidationError):
        Metrics(task_completion_rate=-0.1, groundedness_score=0.5, guardrail_trigger_rate=0.5)
