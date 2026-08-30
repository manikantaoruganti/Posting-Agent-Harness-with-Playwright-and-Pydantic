import pytest
from src.guardrails import GuardrailChain
from src.models import LLMOutput

@pytest.fixture
def guardrail_chain():
    return GuardrailChain()

# Test length check
def test_length_check_pass(guardrail_chain):
    llm_output = LLMOutput(tweet_text="Short tweet", source_row_id="1")
    passed, reason = guardrail_chain._check_length(llm_output.tweet_text)
    assert passed is True
    assert reason is None

def test_length_check_fail(guardrail_chain):
    long_text = "a" * 281
    llm_output = LLMOutput(tweet_text=long_text, source_row_id="1")
    passed, reason = guardrail_chain._check_length(llm_output.tweet_text)
    assert passed is False
    assert "exceeds 280 characters" in reason

# Test banned words check
def test_banned_words_check_pass(guardrail_chain):
    llm_output = LLMOutput(tweet_text="This is a safe post.", source_row_id="1")
    passed, reason = guardrail_chain._check_banned_words(llm_output.tweet_text)
    assert passed is True
    assert reason is None

def test_banned_words_check_fail_guarantee(guardrail_chain):
    llm_output = LLMOutput(tweet_text="I guarantee success.", source_row_id="1")
    passed, reason = guardrail_chain._check_banned_words(llm_output.tweet_text)
    assert passed is False
    assert "Banned word 'guarantee' detected" in reason

def test_banned_words_check_fail_investment_case_insensitive(guardrail_chain):
    llm_output = LLMOutput(tweet_text="Great Investment opportunity.", source_row_id="1")
    passed, reason = guardrail_chain._check_banned_words(llm_output.tweet_text)
    assert passed is False
    assert "Banned word 'investment' detected" in reason

# Test groundedness check
def test_groundedness_check_pass_no_new_elements(guardrail_chain):
    raw_text = "Visit example.com and @user1"
    llm_text = "Check out example.com and @user1 for details."
    passed, reason = guardrail_chain._check_groundedness(llm_text, raw_text)
    assert passed is True
    assert reason is None

def test_groundedness_check_fail_new_url(guardrail_chain):
    raw_text = "Hello world."
    llm_text = "Hello world. Visit new-site.com"
    passed, reason = guardrail_chain._check_groundedness(llm_text, raw_text)
    assert passed is False
    assert "LLM introduced new URLs: new-site.com" in reason

def test_groundedness_check_fail_new_mention(guardrail_chain):
    raw_text = "Hello world."
    llm_text = "Hello world. Shoutout to @new_user"
    passed, reason = guardrail_chain._check_groundedness(llm_text, raw_text)
    assert passed is False
    assert "LLM introduced new @mentions: new_user" in reason

def test_groundedness_check_fail_multiple_new_elements(guardrail_chain):
    raw_text = "Old content."
    llm_text = "New content with https://new.com and @another_user."
    passed, reason = guardrail_chain._check_groundedness(llm_text, raw_text)
    assert passed is False
    assert "LLM introduced new URLs: https://new.com" in reason # Only first failure reason is returned

# Test apply_guardrails (integration of all checks)
def test_apply_guardrails_all_pass(guardrail_chain):
    raw_text = "This is a safe post."
    llm_output = LLMOutput(tweet_text="This is a safe post from LLM.", source_row_id="1")
    passed, reason = guardrail_chain.apply_guardrails(llm_output, raw_text)
    assert passed is True
    assert reason is None

def test_apply_guardrails_fail_length(guardrail_chain):
    raw_text = "Short text."
    long_text = "a" * 281
    llm_output = LLMOutput(tweet_text=long_text, source_row_id="1")
    passed, reason = guardrail_chain.apply_guardrails(llm_output, raw_text)
    assert passed is False
    assert "Length check failed" in reason

def test_apply_guardrails_fail_banned_word(guardrail_chain):
    raw_text = "Safe text."
    llm_output = LLMOutput(tweet_text="This is an investment opportunity.", source_row_id="1")
    passed, reason = guardrail_chain.apply_guardrails(llm_output, raw_text)
    assert passed is False
    assert "Banned word 'investment' detected" in reason

def test_apply_guardrails_fail_groundedness(guardrail_chain):
    raw_text = "Safe text."
    llm_output = LLMOutput(tweet_text="Safe text with new url https://new.com", source_row_id="1")
    passed, reason = guardrail_chain.apply_guardrails(llm_output, raw_text)
    assert passed is False
    assert "Groundedness check failed: LLM introduced new URLs" in reason
