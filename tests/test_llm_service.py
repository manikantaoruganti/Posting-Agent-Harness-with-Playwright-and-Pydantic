import pytest
import json
from unittest.mock import MagicMock, patch
from pydantic import ValidationError
from openai import OpenAI

from src.llm_service import LLMService
from src.models import LLMOutput

# Mock environment variables for LLMService initialization
@pytest.fixture(autouse=True)
def mock_env_vars(monkeypatch):
    monkeypatch.setenv("LLM_BASE_URL", "http://mock-llm:8000/v1")
    monkeypatch.setenv("OPENAI_API_KEY", "mock-api-key")

@pytest.fixture
def llm_service():
    return LLMService()

@pytest.fixture
def mock_openai_client():
    with patch('src.llm_service.OpenAI') as mock_client_class:
        mock_instance = MagicMock(spec=OpenAI)
        mock_client_class.return_value = mock_instance
        yield mock_instance

# Test successful LLM transformation
@pytest.mark.asyncio
async def test_transform_text_success(llm_service, mock_openai_client):
    mock_response_content = json.dumps({
        "tweet_text": "Transformed tweet!",
        "source_row_id": "test_row_1"
    })
    mock_openai_client.chat.completions.create.return_value = MagicMock(
        choices=[MagicMock(message=MagicMock(content=mock_response_content))]
    )

    llm_output = llm_service.transform_text("Raw text", "test_row_1")
    assert isinstance(llm_output, LLMOutput)
    assert llm_output.tweet_text == "Transformed tweet!"
    assert llm_output.source_row_id == "test_row_1"
    mock_openai_client.chat.completions.create.assert_called_once()

# Test LLM output with invalid JSON
@pytest.mark.asyncio
async def test_transform_text_invalid_json(llm_service, mock_openai_client):
    mock_openai_client.chat.completions.create.return_value = MagicMock(
        choices=[MagicMock(message=MagicMock(content="{'invalid_json'}"))]
    )
    llm_output = llm_service.transform_text("Raw text", "test_row_1")
    assert llm_output is None

# Test LLM output with valid JSON but incorrect Pydantic schema
@pytest.mark.asyncio
async def test_transform_text_invalid_schema(llm_service, mock_openai_client):
    mock_response_content = json.dumps({
        "wrong_field": "Transformed tweet!",
        "source_row_id": "test_row_1"
    })
    mock_openai_client.chat.completions.create.return_value = MagicMock(
        choices=[MagicMock(message=MagicMock(content=mock_response_content))]
    )
    llm_output = llm_service.transform_text("Raw text", "test_row_1")
    assert llm_output is None

# Test LLM output with source_row_id mismatch
@pytest.mark.asyncio
async def test_transform_text_source_row_id_mismatch(llm_service, mock_openai_client):
    mock_response_content = json.dumps({
        "tweet_text": "Transformed tweet!",
        "source_row_id": "mismatched_id"
    })
    mock_openai_client.chat.completions.create.return_value = MagicMock(
        choices=[MagicMock(message=MagicMock(content=mock_response_content))]
    )
    llm_output = llm_service.transform_text("Raw text", "test_row_1")
    assert llm_output is None

# Test LLM returns empty content
@pytest.mark.asyncio
async def test_transform_text_empty_content(llm_service, mock_openai_client):
    mock_openai_client.chat.completions.create.return_value = MagicMock(
        choices=[MagicMock(message=MagicMock(content=None))]
    )
    llm_output = llm_service.transform_text("Raw text", "test_row_1")
    assert llm_output is None

# Test LLM client raises an exception
@pytest.mark.asyncio
async def test_transform_text_llm_exception(llm_service, mock_openai_client):
    mock_openai_client.chat.completions.create.side_effect = Exception("LLM API error")
    llm_output = llm_service.transform_text("Raw text", "test_row_1")
    assert llm_output is None
