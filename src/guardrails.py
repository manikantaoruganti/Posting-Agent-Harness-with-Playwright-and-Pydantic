from typing import Tuple, Optional, List
import re

from src.models import LLMOutput
from src.utils import extract_urls_and_mentions

class GuardrailChain:
    def __init__(self):
        self.banned_words = ["guarantee", "investment"]
        self.max_length = 280

    def _check_length(self, text: str) -> Tuple[bool, Optional[str]]:
        """Rejects if text > 280 characters."""
        if len(text) > self.max_length:
            return False, f"Length check failed: text exceeds {self.max_length} characters."
        return True, None

    def _check_banned_words(self, text: str) -> Tuple[bool, Optional[str]]:
        """Rejects if text contains banned words (case-insensitive)."""
        text_lower = text.lower()
        for word in self.banned_words:
            if word in text_lower:
                return False, f"Banned word '{word}' detected."
        return True, None

    def _check_groundedness(self, llm_text: str, raw_text: str) -> Tuple[bool, Optional[str]]:
        """
        Rejects URLs or @mentions introduced by the LLM that were not present in the source.
        """
        raw_extracted = extract_urls_and_mentions(raw_text)
        llm_extracted = extract_urls_and_mentions(llm_text)

        # Check for new URLs
        new_urls = [url for url in llm_extracted["urls"] if url not in raw_extracted["urls"]]
        if new_urls:
            return False, f"Groundedness check failed: LLM introduced new URLs: {', '.join(new_urls)}"

        # Check for new @mentions
        new_mentions = [mention for mention in llm_extracted["mentions"] if mention not in raw_extracted["mentions"]]
        if new_mentions:
            return False, f"Groundedness check failed: LLM introduced new @mentions: {', '.join(new_mentions)}"

        return True, None

    def apply_guardrails(self, llm_output: LLMOutput, raw_text: str) -> Tuple[bool, Optional[str]]:
        """
        Applies all guardrails to the LLM output.
        Returns (True, None) if all pass, else (False, reason).
        """
        # Length check (already done by Pydantic, but good to have here for explicit guardrail chain)
        passed, reason = self._check_length(llm_output.tweet_text)
        if not passed:
            return False, reason

        # Banned words check
        passed, reason = self._check_banned_words(llm_output.tweet_text)
        if not passed:
            return False, reason

        # Groundedness check
        passed, reason = self._check_groundedness(llm_output.tweet_text, raw_text)
        if not passed:
            return False, reason

        return True, None
