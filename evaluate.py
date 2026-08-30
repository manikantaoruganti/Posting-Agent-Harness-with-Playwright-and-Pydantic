import json
import os
from typing import List, Dict, Any
from src.models import Trace, Metrics
from src.utils import extract_urls_and_mentions

def calculate_metrics(traces: List[Trace]) -> Metrics:
    """Calculates evaluation metrics from a list of traces."""
    total_posts = len(traces)
    if total_posts == 0:
        return Metrics(task_completion_rate=0.0, groundedness_score=0.0, guardrail_trigger_rate=0.0)

    completed_posts = 0
    grounded_posts = 0
    triggered_guardrails = 0
    groundedness_failures = 0

    for trace in traces:
        if trace.action_status == "success":
            completed_posts += 1

        if not trace.guardrail_passed:
            triggered_guardrails += 1
            if trace.guardrail_failure_reason and "Groundedness check failed" in trace.guardrail_failure_reason:
                groundedness_failures += 1

        # Groundedness score: LLM did not introduce new URLs or @mentions
        # This is true if guardrail_passed is true, OR if the guardrail failed for a reason *other* than groundedness,
        # AND the final_posted_text (which might be raw_text) is considered "grounded" relative to raw_text.
        # The most direct way to measure LLM groundedness is if the LLM output itself passed the groundedness check.
        # If the LLM output was rejected *specifically* for groundedness, it's not grounded.
        # If it was rejected for length/banned words, its groundedness is not directly assessed by the guardrail_passed flag alone.
        # Let's refine: A post is "grounded" if the LLM output (if used) did not introduce new URLs/mentions.
        # If LLM output was used AND it passed groundedness check, it's grounded.
        # If LLM output was NOT used (fallback to raw_text), then the LLM's output was implicitly not trusted or failed other checks.
        # For groundedness_score, we specifically care if the LLM *itself* produced grounded content.
        # So, if guardrail_passed is True, or if guardrail_passed is False but the failure was NOT due to groundedness.
        # This means the LLM's output was considered grounded, even if it failed other checks.

        # Re-evaluating groundedness_score:
        # A trace contributes to groundedness_score if the LLM's output (if present)
        # would have passed the groundedness check.
        # This means:
        # 1. If guardrail_passed is True (all guardrails passed, including groundedness).
        # 2. If guardrail_passed is False, but the failure reason was NOT a groundedness failure.
        #    In this case, the LLM's output was grounded, but failed another check (e.g., length, banned words).
        # 3. If llm_text is None (LLM failed), it cannot be grounded.
        if trace.llm_text:
            if trace.guardrail_passed:
                grounded_posts += 1
            elif trace.guardrail_failure_reason and "Groundedness check failed" not in trace.guardrail_failure_reason:
                # LLM output was grounded, but failed another guardrail
                grounded_posts += 1
        # If llm_text is None, it doesn't contribute to groundedness_score positively.

    task_completion_rate = completed_posts / total_posts
    groundedness_score = grounded_posts / total_posts
    guardrail_trigger_rate = triggered_guardrails / total_posts

    return Metrics(
        task_completion_rate=round(task_completion_rate, 4),
        groundedness_score=round(groundedness_score, 4),
        guardrail_trigger_rate=round(guardrail_trigger_rate, 4)
    )

def main():
    traces_path = os.path.join("data", "traces.jsonl")
    metrics_path = os.path.join("results", "metrics.json")

    if not os.path.exists(traces_path) or os.path.getsize(traces_path) == 0:
        print(f"No traces found at {traces_path}. Cannot calculate metrics.")
        # Write empty metrics or default to 0.0
        metrics = Metrics(task_completion_rate=0.0, groundedness_score=0.0, guardrail_trigger_rate=0.0)
        with open(metrics_path, 'w') as f:
            json.dump(metrics.model_dump(), f, indent=2)
        return

    traces: List[Trace] = []
    with open(traces_path, 'r') as f:
        for line in f:
            try:
                trace_data = json.loads(line)
                traces.append(Trace(**trace_data))
            except Exception as e:
                print(f"Error parsing trace line: {line.strip()} - {e}")
                continue

    metrics = calculate_metrics(traces)

    os.makedirs(os.path.dirname(metrics_path), exist_ok=True)
    with open(metrics_path, 'w') as f:
        json.dump(metrics.model_dump(), f, indent=2)

    print(f"Metrics calculated and saved to {metrics_path}")
    print(json.dumps(metrics.model_dump(), indent=2))

if __name__ == "__main__":
    main()
