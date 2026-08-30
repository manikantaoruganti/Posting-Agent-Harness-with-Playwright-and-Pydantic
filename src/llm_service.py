import os
from openai import OpenAI
from pydantic import ValidationError
from typing import Optional

from src.models import LLMOutput
from src.utils import get_env_var

class LLMService:
    def __init__(self):
        self.llm_base_url = get_env_var("LLM_BASE_URL")
        self.openai_api_key = get_env_var("OPENAI_API_KEY")
        self.client = OpenAI(
            base_url=self.llm_base_url,
            api_key=self.openai_api_key,
        )

    def transform_text(self, raw_text: str, source_row_id: str) -> Optional[LLMOutput]:
        """
        Transforms raw text into a tweet using the LLM.
        Requires strict structured output using Pydantic.
        """
        try:
            response = self.client.chat.completions.create(
                model="gpt-4o-mini", # Or any other suitable model
                messages=[
                    {"role": "system", "content": "You are a helpful assistant that transforms raw text into concise social media posts (tweets). Ensure the output is a JSON object with 'tweet_text' and 'source_row_id'. The tweet_text should be engaging and within 280 characters. Do not introduce new URLs or @mentions unless they are explicitly in the raw text."},
                    {"role": "user", "content": f"Transform the following text into a tweet. The source row ID is '{source_row_id}'.\n\nRaw text: {raw_text}"}
                ],
                temperature=0, # For deterministic output
                response_model=LLMOutput, # Pydantic for strict structured output
                # Note: The 'response_model' feature is specific to certain LLM client libraries
                # or custom wrappers. For standard OpenAI client, you'd typically parse JSON
                # and then validate with Pydantic.
                # For this implementation, we'll assume a client that supports response_model
                # or manually parse and validate.
                # Let's adjust to a more standard OpenAI client approach for broader compatibility.
                response_format={"type": "json_object"}
            )

            # Manually parse and validate the JSON output
            llm_response_content = response.choices[0].message.content
            if not llm_response_content:
                print("LLM returned empty content.")
                return None

            try:
                llm_output_data = LLMOutput.model_validate_json(llm_response_content)
                if llm_output_data.source_row_id != source_row_id:
                    print(f"LLM output source_row_id mismatch. Expected {source_row_id}, got {llm_output_data.source_row_id}")
                    return None
                return llm_output_data
            except ValidationError as e:
                print(f"LLM output Pydantic validation failed: {e}")
                print(f"Raw LLM response: {llm_response_content}")
                return None
            except json.JSONDecodeError as e:
                print(f"LLM output is not valid JSON: {e}")
                print(f"Raw LLM response: {llm_response_content}")
                return None

        except Exception as e:
            print(f"Error calling LLM service: {e}")
            return None

# Example of a mock LLM endpoint for testing purposes
# This would typically be a separate service or a test fixture
# For the purpose of this project, the LLM_BASE_URL can point to a simple FastAPI mock
# that returns a hardcoded or simple transformation.
# A full mock LLM service is beyond the scope of this single file, but the client
# is configured to point to one.
