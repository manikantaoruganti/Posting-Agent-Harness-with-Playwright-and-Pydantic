import pytest
import asyncio
import os
import json
from unittest.mock import AsyncMock, patch
from playwright.async_api import BrowserContext, Page, Playwright, Browser

from src.browser_actor import BrowserActor

# Mock environment variables for BrowserActor initialization
@pytest.fixture(autouse=True)
def mock_env_vars(monkeypatch, tmp_path):
    monkeypatch.setenv("MOCK_SOCIAL_URL", "http://mock_social:8080")
    monkeypatch.setenv("MOCK_USERNAME", "testuser")
    monkeypatch.setenv("MOCK_PASSWORD", "testpassword")
    # Ensure browser_state.json path is within tmp_path for isolated tests
    monkeypatch.setattr(BrowserActor, 'browser_state_path', str(tmp_path / "browser_state.json"))

@pytest.fixture
def browser_actor():
    return BrowserActor()

@pytest.fixture
async def mock_playwright_context():
    with patch('src.browser_actor.async_playwright') as mock_async_playwright:
        mock_playwright = AsyncMock(spec=Playwright)
        mock_browser = AsyncMock(spec=Browser)
        mock_context = AsyncMock(spec=BrowserContext)
        mock_page = AsyncMock(spec=Page)
        mock_locator = AsyncMock()

        mock_async_playwright.start.return_value = mock_playwright
        mock_playwright.chromium.launch_persistent_context.return_value = mock_context
        mock_context.new_page.return_value = mock_page
        mock_page.locator.return_value = mock_locator
        mock_locator.is_visible.return_value = True # Assume selectors are visible by default

        yield mock_context, mock_page, mock_locator, mock_playwright

# Test _init_browser_context without existing state (forces login)
@pytest.mark.asyncio
async def test_init_browser_context_no_state(browser_actor, mock_playwright_context, tmp_path):
    mock_context, mock_page, mock_locator, mock_playwright = mock_playwright_context

    # Ensure no browser_state.json initially
    browser_state_file = tmp_path / "browser_state.json"
    if browser_state_file.exists():
        os.remove(browser_state_file)

    context = await browser_actor._init_browser_context()

    mock_playwright.chromium.launch_persistent_context.assert_called_once_with(
        user_data_dir="/tmp/playwright",
        headless=True
    )
    mock_page.goto.assert_called_with(f"{browser_actor.mock_social_url}/login", wait_until="domcontentloaded")
    mock_page.fill.assert_any_call("#username", browser_actor.mock_username)
    mock_page.fill.assert_any_call("#password", browser_actor.mock_password)
    mock_page.click.assert_called_with("#login-btn")
    mock_page.wait_for_url.assert_called_with(f"{browser_actor.mock_social_url}/compose/tweet", timeout=10000)
    mock_context.storage_state.assert_called_once_with(path=str(browser_state_file))
    assert browser_state_file.exists()
    await browser_actor.close()

# Test _init_browser_context with existing state (skips login)
@pytest.mark.asyncio
async def test_init_browser_context_with_state(browser_actor, mock_playwright_context, tmp_path):
    mock_context, mock_page, mock_locator, mock_playwright = mock_playwright_context

    # Create a dummy browser_state.json
    browser_state_file = tmp_path / "browser_state.json"
    browser_state_file.write_text(json.dumps({"cookies": [], "origins": []}))

    context = await browser_actor._init_browser_context()

    mock_playwright.chromium.launch_persistent_context.assert_called_once_with(
        user_data_dir="/tmp/playwright",
        headless=True,
        storage_state=str(browser_state_file)
    )
    mock_page.goto.assert_not_called() # Login should be skipped
    mock_page.fill.assert_not_called()
    mock_page.click.assert_not_called()
    mock_context.storage_state.assert_not_called() # State should not be re-saved on load
    await browser_actor.close()

# Test post_tweet success
@pytest.mark.asyncio
async def test_post_tweet_success(browser_actor, mock_playwright_context):
    mock_context, mock_page, mock_locator, mock_playwright = mock_playwright_context

    tweet_text = "Hello from test!"
    result = await browser_actor.post_tweet(tweet_text)

    mock_page.goto.assert_called_with(f"{browser_actor.mock_social_url}/compose/tweet", wait_until="domcontentloaded")
    mock_locator.is_visible.assert_called_once() # Check for #tweet-text visibility
    mock_page.fill.assert_called_with("#tweet-text", tweet_text)
    mock_page.click.assert_called_with("#post-btn")
    assert result is True
    await browser_actor.close()

# Test post_tweet failure (e.g., selectors not found, re-login fails)
@pytest.mark.asyncio
async def test_post_tweet_failure_relogin_fails(browser_actor, mock_playwright_context, tmp_path):
    mock_context, mock_page, mock_locator, mock_playwright = mock_playwright_context

    # Simulate #tweet-text not being visible initially, and re-login also fails
    mock_locator.is_visible.side_effect = [False, False] # First check fails, then re-login check also fails
    mock_page.goto.side_effect = [
        None, # Initial goto
        AsyncMock(side_effect=Exception("Login page not found during re-login")) # Re-login goto fails
    ]

    tweet_text = "Hello from test!"
    result = await browser_actor.post_tweet(tweet_text)

    assert result is False
    # Expect initial goto, then attempt to remove state, close context, re-init, and re-goto
    assert os.path.exists(tmp_path / "browser_state.json") is False # State should be removed
    await browser_actor.close()

# Test close method
@pytest.mark.asyncio
async def test_close(browser_actor, mock_playwright_context):
    mock_context, mock_page, mock_locator, mock_playwright = mock_playwright_context

    # Initialize context first so there's something to close
    await browser_actor._init_browser_context()
    await browser_actor.close()

    mock_context.close.assert_called_once()
    mock_playwright.stop.assert_called_once()
    assert browser_actor._browser_context is None
    assert browser_actor._playwright is None
