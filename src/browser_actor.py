import asyncio
import os
import json
from playwright.async_api import async_playwright, BrowserContext, Page, Playwright
from typing import Optional

from src.utils import get_env_var

class BrowserActor:
    def __init__(self):
        self.mock_social_url = get_env_var("MOCK_SOCIAL_URL")
        self.mock_username = get_env_var("MOCK_USERNAME")
        self.mock_password = get_env_var("MOCK_PASSWORD")
        self.browser_state_path = os.path.join("data", "browser_state.json")
        self._playwright: Optional[Playwright] = None
        self._browser_context: Optional[BrowserContext] = None

    async def _init_browser_context(self) -> BrowserContext:
        """Initializes Playwright and browser context, handling login state."""
        if self._playwright is None:
            self._playwright = await async_playwright().start()

        if self._browser_context:
            return self._browser_context

        if os.path.exists(self.browser_state_path):
            print(f"Loading browser state from {self.browser_state_path}")
            self._browser_context = await self._playwright.chromium.launch_persistent_context(
                user_data_dir="/tmp/playwright", # Use a temporary directory for persistent context
                headless=True,
                storage_state=self.browser_state_path
            )
        else:
            print("No browser state found. Launching new context and logging in.")
            self._browser_context = await self._playwright.chromium.launch_persistent_context(
                user_data_dir="/tmp/playwright",
                headless=True
            )
            await self._login(self._browser_context)
            await self._browser_context.storage_state(path=self.browser_state_path)
            print(f"Browser state saved to {self.browser_state_path}")

        return self._browser_context

    async def _login(self, context: BrowserContext):
        """Performs login to the mock social server."""
        page = await context.new_page()
        try:
            await page.goto(f"{self.mock_social_url}/login", wait_until="domcontentloaded")
            await page.fill("#username", self.mock_username)
            await page.fill("#password", self.mock_password)
            await page.click("#login-btn")
            await page.wait_for_url(f"{self.mock_social_url}/compose/tweet", timeout=10000) # Wait for redirect
            print("Login successful.")
        except Exception as e:
            print(f"Login failed: {e}")
            raise
        finally:
            await page.close()

    async def post_tweet(self, tweet_text: str) -> bool:
        """Fills the tweet text and posts it."""
        context = await self._init_browser_context()
        page = await context.new_page()
        try:
            # Always navigate to compose page, even if state exists, to ensure correct URL
            await page.goto(f"{self.mock_social_url}/compose/tweet", wait_until="domcontentloaded")

            # Check if we are authenticated by looking for the tweet form
            if not await page.locator("#tweet-text").is_visible():
                print("Not authenticated or compose page not found. Attempting re-login.")
                # Clear existing state and try to re-login
                if os.path.exists(self.browser_state_path):
                    os.remove(self.browser_state_path)
                await self._browser_context.close() # Close current context to force new one
                self._browser_context = None
                context = await self._init_browser_context() # This will trigger re-login
                page = await context.new_page()
                await page.goto(f"{self.mock_social_url}/compose/tweet", wait_until="domcontentloaded")
                if not await page.locator("#tweet-text").is_visible():
                    raise Exception("Failed to authenticate and reach compose page after re-login attempt.")

            await page.fill("#tweet-text", tweet_text)
            await page.click("#post-btn")
            # Wait for a success message or redirect, or simply for the button to disappear
            # For mock server, we assume clicking post-btn is sufficient for success
            await asyncio.sleep(2) # Give some time for the mock server to process
            print(f"Tweet posted successfully: '{tweet_text}'")
            return True
        except Exception as e:
            print(f"Failed to post tweet: {e}")
            return False
        finally:
            await page.close()

    async def close(self):
        """Closes the browser context and Playwright instance."""
        if self._browser_context:
            await self._browser_context.close()
            self._browser_context = None
        if self._playwright:
            await self._playwright.stop()
            self._playwright = None

# Example usage (for testing purposes, not part of main agent loop)
async def main():
    actor = BrowserActor()
    try:
        success = await actor.post_tweet("Hello from Playwright!")
        print(f"Post successful: {success}")
    finally:
        await actor.close()

if __name__ == "__main__":
    # For local testing, ensure .env is loaded
    from dotenv import load_dotenv
    load_dotenv()
    asyncio.run(main())
