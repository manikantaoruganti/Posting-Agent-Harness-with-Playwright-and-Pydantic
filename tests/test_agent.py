import pytest
import asyncio
import os
import json
from datetime import datetime, timedelta
import pytz
from unittest.mock import AsyncMock, patch, MagicMock

from src.agent import Agent
from src.models import ScheduleRow, LLMOutput, Trace, Metrics
from src.utils import get_timezone_aware_today

# Fixtures for file paths and mock environment
@pytest.fixture(autouse=True)
def mock_env_vars(monkeypatch, tmp_path):
    monkeypatch.setenv("LLM_BASE_URL", "http://mock-llm:8000/v1")
    monkeypatch.setenv("OPENAI_API_KEY", "mock-api-key")
    monkeypatch.setenv("MOCK_SOCIAL_URL", "http://mock_social:8080")
    monkeypatch.setenv("MOCK_USERNAME", "testuser")
    monkeypatch.setenv("MOCK_PASSWORD", "testpassword")
    monkeypatch.setenv("HITL_ENABLED", "false") # Default to false for most tests

    # Ensure data paths are within tmp_path for isolated tests
    monkeypatch.setattr(Agent, 'schedule_path', str(tmp_path / "schedule.csv"))
    monkeypatch.setattr(Agent, 'posted_ids_path', str(tmp_path / "posted_ids.json"))
    monkeypatch.setattr(Agent, 'traces_path', str(tmp_path / "traces.jsonl"))

    # Create initial empty data files
    (tmp_path / "posted_ids.json").write_text("[]")
    (tmp_path / "traces.jsonl").write_text("")

@pytest.fixture
def agent_instance():
    return Agent()

@pytest.fixture
def mock_llm_service():
    with patch('src.agent.LLMService') as mock_llm_class:
        instance = AsyncMock()
        mock_llm_class.return_value = instance
        yield instance

@pytest.fixture
def mock_guardrail_chain():
    with patch('src.agent.GuardrailChain') as mock_guardrail_class:
        instance = MagicMock()
        mock_guardrail_class.return_value = instance
        yield instance

@pytest.fixture
def mock_browser_actor():
    with patch('src.agent.BrowserActor') as mock_browser_class:
        instance = AsyncMock()
        mock_browser_class.return_value = instance
        yield instance

# Helper to create a schedule CSV
def create_schedule_csv(path, rows):
    content = "row_id,post_date,raw_text\n"
    for row in rows:
        content += f"{row['row_id']},{row['post_date']},{row['raw_text']}\n"
    path.write_text(content)

# Test date filtering and duplicate prevention
@pytest.mark.asyncio
async def test_agent_date_filtering_and_duplicate_prevention(agent_instance, tmp_path, mock_llm_service, mock_guardrail_chain, mock_browser_actor):
    today = get_timezone_aware_today()
    yesterday = today - timedelta(days=1)
    tomorrow = today + timedelta(days=1)

    schedule_rows = [
        {"row_id": "past_post", "post_date": yesterday.strftime("%Y-%m-%d"), "raw_text": "Old post"},
        {"row_id": "due_today_1", "post_date": today.strftime("%Y-%m-%d"), "raw_text": "Due today 1"},
        {"row_id": "due_today_2", "post_date": today.strftime("%Y-%m-%d"), "raw_text": "Due today 2"},
        {"row_id": "already_posted", "post_date": today.strftime("%Y-%m-%d"), "raw_text": "Already posted"},
        {"row_id": "future_post", "post_date": tomorrow.strftime("%Y-%m-%d"), "raw_text": "Future post"},
    ]
    create_schedule_csv(tmp_path / "schedule.csv", schedule_rows)
    (tmp_path / "posted_ids.json").write_text(json.dumps(["already_posted"]))

    # Mock LLM and guardrails to pass, browser to succeed
    mock_llm_service.transform_text.return_value = LLMOutput(tweet_text="Transformed text", source_row_id="due_today_1")
    mock_guardrail_chain.apply_guardrails.return_value = (True, None)
    mock_browser_actor.post_tweet.return_value = True

    await agent_instance.run()

    # Only 'due_today_1' should be processed (first due row)
    mock_llm_service.transform_text.assert_called_once_with("Due today 1", "due_today_1")
    posted_ids = json.loads((tmp_path / "posted_ids.json").read_text())
    assert "due_today_1" in posted_ids
    assert "due_today_2" not in posted_ids # Only one post per day

    traces = [json.loads(line) for line in (tmp_path / "traces.jsonl").read_text().splitlines() if line.strip()]
    assert len(traces) == 1
    assert traces[0]["row_id"] == "due_today_1"
    assert traces[0]["action_status"] == "success"

# Test multiple due rows (only first processed)
@pytest.mark.asyncio
async def test_agent_multiple_due_rows(agent_instance, tmp_path, mock_llm_service, mock_guardrail_chain, mock_browser_actor):
    today = get_timezone_aware_today()
    schedule_rows = [
        {"row_id": "first_due", "post_date": today.strftime("%Y-%m-%d"), "raw_text": "First due"},
        {"row_id": "second_due", "post_date": today.strftime("%Y-%m-%d"), "raw_text": "Second due"},
    ]
    create_schedule_csv(tmp_path / "schedule.csv", schedule_rows)

    mock_llm_service.transform_text.return_value = LLMOutput(tweet_text="Transformed text", source_row_id="first_due")
    mock_guardrail_chain.apply_guardrails.return_value = (True, None)
    mock_browser_actor.post_tweet.return_value = True

    await agent_instance.run()

    mock_llm_service.transform_text.assert_called_once_with("First due", "first_due")
    posted_ids = json.loads((tmp_path / "posted_ids.json").read_text())
    assert "first_due" in posted_ids
    assert "second_due" not in posted_ids

# Test LLM transformation failure (fallback to raw_text)
@pytest.mark.asyncio
async def test_agent_llm_failure_fallback(agent_instance, tmp_path, mock_llm_service, mock_guardrail_chain, mock_browser_actor):
    today = get_timezone_aware_today()
    schedule_rows = [
        {"row_id": "llm_fail", "post_date": today.strftime("%Y-%m-%d"), "raw_text": "Original text for LLM fail"}
    ]
    create_schedule_csv(tmp_path / "schedule.csv", schedule_rows)

    mock_llm_service.transform_text.return_value = None # Simulate LLM failure
    mock_browser_actor.post_tweet.return_value = True

    await agent_instance.run()

    mock_llm_service.transform_text.assert_called_once()
    mock_guardrail_chain.apply_guardrails.assert_not_called() # Guardrails not called if LLM fails
    mock_browser_actor.post_tweet.assert_called_once_with("Original text for LLM fail")

    traces = [json.loads(line) for line in (tmp_path / "traces.jsonl").read_text().splitlines() if line.strip()]
    assert len(traces) == 1
    assert traces[0]["row_id"] == "llm_fail"
    assert traces[0]["llm_text"] is None
    assert traces[0]["guardrail_passed"] is False
    assert "LLM transformation failed" in traces[0]["guardrail_failure_reason"]
    assert traces[0]["final_posted_text"] == "Original text for LLM fail"
    assert traces[0]["action_status"] == "success"

# Test guardrail failure (fallback to raw_text)
@pytest.mark.asyncio
async def test_agent_guardrail_failure_fallback(agent_instance, tmp_path, mock_llm_service, mock_guardrail_chain, mock_browser_actor):
    today = get_timezone_aware_today()
    schedule_rows = [
        {"row_id": "guardrail_fail", "post_date": today.strftime("%Y-%m-%d"), "raw_text": "Original text for guardrail fail"}
    ]
    create_schedule_csv(tmp_path / "schedule.csv", schedule_rows)

    llm_output = LLMOutput(tweet_text="This is an investment opportunity.", source_row_id="guardrail_fail")
    mock_llm_service.transform_text.return_value = llm_output
    mock_guardrail_chain.apply_guardrails.return_value = (False, "Banned word 'investment' detected.")
    mock_browser_actor.post_tweet.return_value = True

    await agent_instance.run()

    mock_llm_service.transform_text.assert_called_once()
    mock_guardrail_chain.apply_guardrails.assert_called_once_with(llm_output, "Original text for guardrail fail")
    mock_browser_actor.post_tweet.assert_called_once_with("Original text for guardrail fail") # Fallback

    traces = [json.loads(line) for line in (tmp_path / "traces.jsonl").read_text().splitlines() if line.strip()]
    assert len(traces) == 1
    assert traces[0]["row_id"] == "guardrail_fail"
    assert traces[0]["llm_text"] == "This is an investment opportunity."
    assert traces[0]["guardrail_passed"] is False
    assert "Banned word 'investment' detected" in traces[0]["guardrail_failure_reason"]
    assert traces[0]["final_posted_text"] == "Original text for guardrail fail"
    assert traces[0]["action_status"] == "success"

# Test successful end-to-end run
@pytest.mark.asyncio
async def test_agent_e2e_success(agent_instance, tmp_path, mock_llm_service, mock_guardrail_chain, mock_browser_actor):
    today = get_timezone_aware_today()
    schedule_rows = [
        {"row_id": "e2e_success", "post_date": today.strftime("%Y-%m-%d"), "raw_text": "Raw text for success"}
    ]
    create_schedule_csv(tmp_path / "schedule.csv", schedule_rows)

    llm_output = LLMOutput(tweet_text="LLM transformed text for success", source_row_id="e2e_success")
    mock_llm_service.transform_text.return_value = llm_output
    mock_guardrail_chain.apply_guardrails.return_value = (True, None)
    mock_browser_actor.post_tweet.return_value = True

    await agent_instance.run()

    mock_llm_service.transform_text.assert_called_once_with("Raw text for success", "e2e_success")
    mock_guardrail_chain.apply_guardrails.assert_called_once_with(llm_output, "Raw text for success")
    mock_browser_actor.post_tweet.assert_called_once_with("LLM transformed text for success")

    posted_ids = json.loads((tmp_path / "posted_ids.json").read_text())
    assert "e2e_success" in posted_ids

    traces = [json.loads(line) for line in (tmp_path / "traces.jsonl").read_text().splitlines() if line.strip()]
    assert len(traces) == 1
    assert traces[0]["row_id"] == "e2e_success"
    assert traces[0]["llm_text"] == "LLM transformed text for success"
    assert traces[0]["guardrail_passed"] is True
    assert traces[0]["guardrail_failure_reason"] is None
    assert traces[0]["final_posted_text"] == "LLM transformed text for success"
    assert traces[0]["action_status"] == "success"

# Test browser actor failure
@pytest.mark.asyncio
async def test_agent_browser_actor_failure(agent_instance, tmp_path, mock_llm_service, mock_guardrail_chain, mock_browser_actor):
    today = get_timezone_aware_today()
    schedule_rows = [
        {"row_id": "browser_fail", "post_date": today.strftime("%Y-%m-%d"), "raw_text": "Raw text for browser fail"}
    ]
    create_schedule_csv(tmp_path / "schedule.csv", schedule_rows)

    llm_output = LLMOutput(tweet_text="LLM text", source_row_id="browser_fail")
    mock_llm_service.transform_text.return_value = llm_output
    mock_guardrail_chain.apply_guardrails.return_value = (True, None)
    mock_browser_actor.post_tweet.return_value = False # Simulate browser failure

    await agent_instance.run()

    mock_browser_actor.post_tweet.assert_called_once()
    posted_ids = json.loads((tmp_path / "posted_ids.json").read_text())
    assert "browser_fail" not in posted_ids # Should not be marked as posted

    traces = [json.loads(line) for line in (tmp_path / "traces.jsonl").read_text().splitlines() if line.strip()]
    assert len(traces) == 1
    assert traces[0]["row_id"] == "browser_fail"
    assert traces[0]["action_status"] == "failed"

# Test HITL enabled and approved
@pytest.mark.asyncio
async def test_agent_hitl_approved(agent_instance, tmp_path, mock_llm_service, mock_guardrail_chain, mock_browser_actor, monkeypatch):
    monkeypatch.setenv("HITL_ENABLED", "true")
    monkeypatch.setattr('builtins.input', lambda x: 'yes') # Mock input for approval

    today = get_timezone_aware_today()
    schedule_rows = [
        {"row_id": "hitl_approved", "post_date": today.strftime("%Y-%m-%d"), "raw_text": "Raw text for HITL"}
    ]
    create_schedule_csv(tmp_path / "schedule.csv", schedule_rows)

    llm_output = LLMOutput(tweet_text="LLM text for HITL", source_row_id="hitl_approved")
    mock_llm_service.transform_text.return_value = llm_output
    mock_guardrail_chain.apply_guardrails.return_value = (True, None)
    mock_browser_actor.post_tweet.return_value = True

    await agent_instance.run()

    mock_browser_actor.post_tweet.assert_called_once_with("LLM text for HITL")
    traces = [json.loads(line) for line in (tmp_path / "traces.jsonl").read_text().splitlines() if line.strip()]
    assert len(traces) == 1
    assert traces[0]["row_id"] == "hitl_approved"
    assert traces[0]["action_status"] == "success"

# Test HITL enabled and disapproved
@pytest.mark.asyncio
async def test_agent_hitl_disapproved(agent_instance, tmp_path, mock_llm_service, mock_guardrail_chain, mock_browser_actor, monkeypatch):
    monkeypatch.setenv("HITL_ENABLED", "true")
    monkeypatch.setattr('builtins.input', lambda x: 'no') # Mock input for disapproval

    today = get_timezone_aware_today()
    schedule_rows = [
        {"row_id": "hitl_disapproved", "post_date": today.strftime("%Y-%m-%d"), "raw_text": "Raw text for HITL"}
    ]
    create_schedule_csv(tmp_path / "schedule.csv", schedule_rows)

    llm_output = LLMOutput(tweet_text="LLM text for HITL", source_row_id="hitl_disapproved")
    mock_llm_service.transform_text.return_value = llm_output
    mock_guardrail_chain.apply_guardrails.return_value = (True, None)

    await agent_instance.run()

    mock_browser_actor.post_tweet.assert_not_called() # Should not post if disapproved
    traces = [json.loads(line) for line in (tmp_path / "traces.jsonl").read_text().splitlines() if line.strip()]
    assert len(traces) == 1
    assert traces[0]["row_id"] == "hitl_disapproved"
    assert traces[0]["action_status"] == "skipped"
