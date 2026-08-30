import pytest
import json
import os
from datetime import datetime, timedelta
from src.models import Trace, Metrics
from evaluate import calculate_metrics, main as evaluate_main # Import main from evaluate.py

# Fixture for traces_jsonl_path and metrics_json_path
@pytest.fixture
def traces_jsonl_path(tmp_path):
    return tmp_path / "traces.jsonl"

@pytest.fixture
def metrics_json_path(tmp_path):
    return tmp_path / "metrics.json"

@pytest.fixture(autouse=True)
def mock_paths_for_evaluate_main(monkeypatch, traces_jsonl_path, metrics_json_path):
    monkeypatch.setattr('evaluate.os.path.join', lambda *args: {
        ('data', 'traces.jsonl'): str(traces_jsonl_path),
        ('results', 'metrics.json'): str(metrics_json_path),
    }.get(args, os.path.join(*args)))
    monkeypatch.setattr('src.utils.os.path.join', lambda *args: {
        ('data', 'traces.jsonl'): str(traces_jsonl_path),
        ('results', 'metrics.json'): str(metrics_json_path),
    }.get(args, os.path.join(*args)))


def create_trace(
    row_id: str,
    raw_text: str,
    llm_text: str,
    guardrail_passed: bool,
    guardrail_failure_reason: str,
    final_posted_text: str,
    action_status: str,
    timestamp: datetime = datetime.now()
) -> Trace:
    return Trace(
        timestamp=timestamp,
        row_id=row_id,
        raw_text=raw_text,
        llm_text=llm_text,
        guardrail_passed=guardrail_passed,
        guardrail_failure_reason=guardrail_failure_reason,
        final_posted_text=final_posted_text,
        action_status=action_status
    )

# Test calculate_metrics with various scenarios
def test_calculate_metrics_empty():
    metrics = calculate_metrics([])
    assert metrics.task_completion_rate == 0.0
    assert metrics.groundedness_score == 0.0
    assert metrics.guardrail_trigger_rate == 0.0

def test_calculate_metrics_all_success_and_grounded():
    traces = [
        create_trace("1", "raw1", "llm1", True, None, "llm1", "success"),
        create_trace("2", "raw2", "llm2", True, None, "llm2", "success"),
        create_trace("3", "raw3", "llm3", True, None, "llm3", "success"),
    ]
    metrics = calculate_metrics(traces)
    assert metrics.task_completion_rate == 1.0
    assert metrics.groundedness_score == 1.0
    assert metrics.guardrail_trigger_rate == 0.0

def test_calculate_metrics_some_failures_and_guardrails():
    traces = [
        # Success, all pass
        create_trace("1", "raw1", "llm1", True, None, "llm1", "success"),
        # Success, guardrail failed (banned word), fallback to raw
        create_trace("2", "raw2", "LLM has investment", False, "Banned word 'investment' detected.", "raw2", "success"),
        # Failed to post (e.g., browser issue)
        create_trace("3", "raw3", "llm3", True, None, "llm3", "failed"),
        # Success, guardrail failed (groundedness), fallback to raw
        create_trace("4", "raw4", "LLM with new url https://new.com", False, "Groundedness check failed: LLM introduced new URLs", "raw4", "success"),
        # Skipped (HITL)
        create_trace("5", "raw5", "llm5", True, None, "llm5", "skipped"),
        # LLM failed, fallback to raw, posted successfully
        create_trace("6", "raw6", None, False, "LLM transformation failed or invalid output.", "raw6", "success"),
    ]
    metrics = calculate_metrics(traces)

    # Total posts: 6
    # Completed posts: 4 (1, 2, 4, 6)
    # Triggered guardrails: 3 (2, 4, 6 - LLM failure counts as guardrail not passed)
    # Grounded posts: 2 (1, 2 - LLM output for 2 was grounded, even if it failed banned word)

    assert metrics.task_completion_rate == round(4/6, 4) # 0.6667
    assert metrics.groundedness_score == round(2/6, 4) # 0.3333 (only trace 1 and 2 LLM output was grounded)
    assert metrics.guardrail_trigger_rate == round(3/6, 4) # 0.5

def test_calculate_metrics_only_groundedness_failures():
    traces = [
        create_trace("1", "raw1", "llm1 with new url", False, "Groundedness check failed: LLM introduced new URLs", "raw1", "success"),
        create_trace("2", "raw2", "llm2 with new mention", False, "Groundedness check failed: LLM introduced new @mentions", "raw2", "success"),
    ]
    metrics = calculate_metrics(traces)
    assert metrics.task_completion_rate == 1.0
    assert metrics.groundedness_score == 0.0 # LLM output was not grounded in either case
    assert metrics.guardrail_trigger_rate == 1.0

def test_calculate_metrics_llm_failure_not_grounded():
    traces = [
        create_trace("1", "raw1", None, False, "LLM transformation failed or invalid output.", "raw1", "success"),
    ]
    metrics = calculate_metrics(traces)
    assert metrics.task_completion_rate == 1.0
    assert metrics.groundedness_score == 0.0 # LLM output was None, so not grounded
    assert metrics.guardrail_trigger_rate == 1.0

# Test evaluate.py main function
def test_evaluate_main_function(traces_jsonl_path, metrics_json_path):
    # Create dummy traces
    traces_data = [
        create_trace("1", "raw1", "llm1", True, None, "llm1", "success").model_dump(),
        create_trace("2", "raw2", "LLM has investment", False, "Banned word 'investment' detected.", "raw2", "success").model_dump(),
    ]
    with open(traces_jsonl_path, 'w') as f:
        for trace in traces_data:
            f.write(json.dumps(trace, default=str) + '\n')

    # Run the main evaluation function
    evaluate_main()

    # Check if metrics.json was created and contains expected data
    assert metrics_json_path.exists()
    with open(metrics_json_path, 'r') as f:
        metrics_output = json.load(f)

    expected_metrics = calculate_metrics([Trace(**t) for t in traces_data]).model_dump()
    assert metrics_output == expected_metrics

def test_evaluate_main_no_traces_file(traces_jsonl_path, metrics_json_path):
    # Ensure no traces file exists
    if traces_jsonl_path.exists():
        os.remove(traces_jsonl_path)

    evaluate_main()

    assert metrics_json_path.exists()
    with open(metrics_json_path, 'r') as f:
        metrics_output = json.load(f)

    assert metrics_output == Metrics(task_completion_rate=0.0, groundedness_score=0.0, guardrail_trigger_rate=0.0).model_dump()

def test_evaluate_main_empty_traces_file(traces_jsonl_path, metrics_json_path):
    traces_jsonl_path.write_text("") # Empty file

    evaluate_main()

    assert metrics_json_path.exists()
    with open(metrics_json_path, 'r') as f:
        metrics_output = json.load(f)

    assert metrics_output == Metrics(task_completion_rate=0.0, groundedness_score=0.0, guardrail_trigger_rate=0.0).model_dump()
