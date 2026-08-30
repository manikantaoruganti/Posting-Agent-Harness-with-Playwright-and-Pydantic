import asyncio
import os
from datetime import datetime
from typing import Optional, List
from dotenv import load_dotenv

from src.models import ScheduleRow, LLMOutput, Trace
from src.utils import (
    get_timezone_aware_today,
    load_schedule,
    load_posted_ids,
    save_posted_id,
    append_trace,
    get_env_var
)
from src.llm_service import LLMService
from src.guardrails import GuardrailChain
from src.browser_actor import BrowserActor

class Agent:
    def __init__(self):
        load_dotenv() # Load environment variables from .env
        self.schedule_path = os.path.join("data", "schedule.csv")
        self.posted_ids_path = os.path.join("data", "posted_ids.json")
        self.traces_path = os.path.join("data", "traces.jsonl")
        self.llm_service = LLMService()
        self.guardrail_chain = GuardrailChain()
        self.browser_actor = BrowserActor()
        self.hitl_enabled = get_env_var("HITL_ENABLED").lower() == "true"

    async def run(self):
        """Main deterministic control loop for the agent."""
        print("Agent started.")
        today = get_timezone_aware_today()
        schedule = load_schedule(self.schedule_path)
        posted_ids = load_posted_ids(self.posted_ids_path)

        due_rows: List[ScheduleRow] = []
        for row in schedule:
            if row.post_date.date() == today and row.row_id not in posted_ids:
                due_rows.append(row)

        if not due_rows:
            print(f"No posts due for today ({today}) or all due posts already processed.")
            return

        # Process at most ONE row per day
        # If multiple rows are due, process the first deterministically and log/alert about the others.
        selected_row = due_rows[0]
        if len(due_rows) > 1:
            print(f"Warning: Multiple rows due for today. Processing row '{selected_row.row_id}'. Other due rows: {[r.row_id for r in due_rows[1:]]}")

        print(f"Processing row_id: {selected_row.row_id}")
        print(f"Raw text: {selected_row.raw_text}")

        llm_output: Optional[LLMOutput] = None
        guardrail_passed = False
        guardrail_failure_reason: Optional[str] = None
        final_posted_text: str = selected_row.raw_text
        action_status = "failed" # Default to failed, update on success

        try:
            # 1. LLM Transformation
            llm_output = self.llm_service.transform_text(selected_row.raw_text, selected_row.row_id)

            if llm_output:
                # 2. Deterministic Guardrails
                guardrail_passed, guardrail_failure_reason = self.guardrail_chain.apply_guardrails(llm_output, selected_row.raw_text)

                if guardrail_passed:
                    final_posted_text = llm_output.tweet_text
                    print(f"LLM output passed all guardrails. Final text: {final_posted_text}")
                else:
                    final_posted_text = selected_row.raw_text
                    print(f"Guardrail failed: {guardrail_failure_reason}. Falling back to raw text: {final_posted_text}")
            else:
                print("LLM transformation failed or returned invalid output. Falling back to raw text.")
                guardrail_passed = False # LLM failure implies guardrail didn't pass on LLM output
                guardrail_failure_reason = "LLM transformation failed or invalid output."
                final_posted_text = selected_row.raw_text

            # 3. Human-in-the-Loop (HITL)
            if self.hitl_enabled:
                print(f"\n--- HUMAN-IN-THE-LOOP APPROVAL REQUIRED ---")
                print(f"Proposed Tweet: '{final_posted_text}'")
                approval = input("Approve posting? (yes/no): ").lower().strip()
                if approval != "yes":
                    print("Posting disapproved by human. Skipping this post.")
                    action_status = "skipped"
                    return # Exit without posting
                print("Posting approved.")

            # 4. Playwright Execution
            post_success = await self.browser_actor.post_tweet(final_posted_text)

            if post_success:
                save_posted_id(self.posted_ids_path, selected_row.row_id)
                action_status = "success"
                print(f"Successfully posted and recorded row_id: {selected_row.row_id}")
            else:
                action_status = "failed"
                print(f"Failed to post tweet for row_id: {selected_row.row_id}")

        except Exception as e:
            print(f"An unexpected error occurred during agent run: {e}")
            action_status = "failed"
        finally:
            # 5. Observability
            trace_data = Trace(
                row_id=selected_row.row_id,
                raw_text=selected_row.raw_text,
                llm_text=llm_output.tweet_text if llm_output else None,
                guardrail_passed=guardrail_passed,
                guardrail_failure_reason=guardrail_failure_reason,
                final_posted_text=final_posted_text,
                action_status=action_status
            )
            append_trace(self.traces_path, trace_data.model_dump())
            await self.browser_actor.close()
            print("Agent run finished.")

if __name__ == "__main__":
    agent = Agent()
    asyncio.run(agent.run())
