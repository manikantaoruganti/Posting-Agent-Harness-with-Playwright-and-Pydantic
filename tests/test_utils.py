import os
import json
from datetime import datetime, date
import pytz
import pandas as pd
import pytest

from src.utils import (
    get_timezone_aware_today,
    load_schedule,
    load_posted_ids,
    save_posted_id,
    append_trace,
    extract_urls_and_mentions,
    get_env_var
)
from src.models import ScheduleRow, Trace

# Fixtures for file paths
@pytest.fixture
def schedule_csv_path(tmp_path):
    return tmp_path / "schedule.csv"

@pytest.fixture
def posted_ids_json_path(tmp_path):
    return tmp_path / "posted_ids.json"

@pytest.fixture
def traces_jsonl_path(tmp_path):
    return tmp_path / "traces.jsonl"

# Test get_timezone_aware_today
def test_get_timezone_aware_today():
    today = get_timezone_aware_today()
    assert isinstance(today, date)
    assert today == datetime.now(pytz.utc).date()

# Test load_schedule
def test_load_schedule_success(schedule_csv_path):
    content = """row_id,post_date,raw_text
    1,2024-01-01,Test post 1
    2,2024-01-02,Test post 2"""
    schedule_csv_path.write_text(content)
    schedule = load_schedule(schedule_csv_path)
    assert len(schedule) == 2
    assert schedule[0].row_id == "1"
    assert schedule[0].post_date.date() == date(2024, 1, 1)
    assert schedule[0].raw_text == "Test post 1"

def test_load_schedule_file_not_found(tmp_path):
    with pytest.raises(FileNotFoundError):
        load_schedule(tmp_path / "non_existent.csv")

# Test load_posted_ids
def test_load_posted_ids_success(posted_ids_json_path):
    posted_ids_json_path.write_text(json.dumps(["1", "2"]))
    ids = load_posted_ids(posted_ids_json_path)
    assert ids == ["1", "2"]

def test_load_posted_ids_empty_file(posted_ids_json_path):
    posted_ids_json_path.write_text("")
    ids = load_posted_ids(posted_ids_json_path)
    assert ids == []

def test_load_posted_ids_file_not_found(tmp_path):
    ids = load_posted_ids(tmp_path / "non_existent.json")
    assert ids == []

# Test save_posted_id
def test_save_posted_id(posted_ids_json_path):
    posted_ids_json_path.write_text(json.dumps(["1"]))
    save_posted_id(posted_ids_json_path, "2")
    ids = load_posted_ids(posted_ids_json_path)
    assert ids == ["1", "2"]

def test_save_posted_id_no_duplicates(posted_ids_json_path):
    posted_ids_json_path.write_text(json.dumps(["1", "2"]))
    save_posted_id(posted_ids_json_path, "2")
    ids = load_posted_ids(posted_ids_json_path)
    assert ids == ["1", "2"]

def test_save_posted_id_new_file(posted_ids_json_path):
    save_posted_id(posted_ids_json_path, "1")
    ids = load_posted_ids(posted_ids_json_path)
    assert ids == ["1"]

# Test append_trace
def test_append_trace(traces_jsonl_path):
    trace_data = Trace(
        row_id="test_id",
        raw_text="raw",
        llm_text="llm",
        guardrail_passed=True,
        guardrail_failure_reason=None,
        final_posted_text="final",
        action_status="success"
    ).model_dump()
    append_trace(traces_jsonl_path, trace_data)
    with open(traces_jsonl_path, 'r') as f:
        lines = f.readlines()
    assert len(lines) == 1
    loaded_trace = json.loads(lines[0])
    assert loaded_trace["row_id"] == "test_id"
    assert loaded_trace["action_status"] == "success"

# Test extract_urls_and_mentions
def test_extract_urls_and_mentions():
    text = "Check out https://example.com and @user1. Also visit http://test.org and @user_two."
    extracted = extract_urls_and_mentions(text)
    assert set(extracted["urls"]) == {"https://example.com", "http://test.org"}
    assert set(extracted["mentions"]) == {"user1", "user_two"}

def test_extract_urls_and_mentions_no_matches():
    text = "Just some plain text."
    extracted = extract_urls_and_mentions(text)
    assert extracted["urls"] == []
    assert extracted["mentions"] == []

def test_extract_urls_and_mentions_empty_string():
    text = ""
    extracted = extract_urls_and_mentions(text)
    assert extracted["urls"] == []
    assert extracted["mentions"] == []

# Test get_env_var
def test_get_env_var_exists(monkeypatch):
    monkeypatch.setenv("TEST_VAR", "value")
    assert get_env_var("TEST_VAR") == "value"

def test_get_env_var_not_exists_with_default():
    assert get_env_var("NON_EXISTENT_VAR", default="default_value") == "default_value"

def test_get_env_var_not_exists_no_default():
    with pytest.raises(ValueError, match="Environment variable 'NON_EXISTENT_VAR' not set."):
        get_env_var("NON_EXISTENT_VAR")
