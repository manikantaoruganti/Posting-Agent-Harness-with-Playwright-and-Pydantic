import pytest
from httpx import AsyncClient
from src.mock_social_server import app

@pytest.fixture(scope="module")
async def test_client():
    async with AsyncClient(app=app, base_url="http://test") as client:
        yield client

@pytest.mark.asyncio
async def test_health_check(test_client):
    response = await test_client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "healthy"}

@pytest.mark.asyncio
async def test_get_login_page(test_client):
    response = await test_client.get("/login")
    assert response.status_code == 200
    assert "#username" in response.text
    assert "#password" in response.text
    assert "#login-btn" in response.text

@pytest.mark.asyncio
async def test_post_login_success(test_client):
    response = await test_client.post("/login", json={"username": "testuser", "password": "testpassword"})
    assert response.status_code == 200
    assert response.json() == {"message": "Login successful", "redirect": "/compose/tweet"}
    assert "session_id" in response.cookies
    assert response.cookies["session_id"] == "mock_session_id_123"

@pytest.mark.asyncio
async def test_get_compose_page_unauthenticated(test_client):
    response = await test_client.get("/compose/tweet")
    assert response.status_code == 302 # Redirect to login
    assert response.headers["location"] == "/login"

@pytest.mark.asyncio
async def test_get_compose_page_authenticated(test_client):
    # First, log in to get a session cookie
    login_response = await test_client.post("/login", json={"username": "testuser", "password": "testpassword"})
    session_cookie = login_response.cookies["session_id"]

    # Then, request compose page with the session cookie
    response = await test_client.get("/compose/tweet", cookies={"session_id": session_cookie})
    assert response.status_code == 200
    assert "#tweet-text" in response.text
    assert "#post-btn" in response.text

@pytest.mark.asyncio
async def test_post_tweet_unauthenticated(test_client):
    response = await test_client.post("/compose/tweet", json={"tweet_text": "Test tweet"})
    assert response.status_code == 401
    assert response.json() == {"detail": "Not authenticated"}

@pytest.mark.asyncio
async def test_post_tweet_authenticated_success(test_client):
    # First, log in to get a session cookie
    login_response = await test_client.post("/login", json={"username": "testuser", "password": "testpassword"})
    session_cookie = login_response.cookies["session_id"]

    tweet_text = "This is a valid test tweet."
    response = await test_client.post("/compose/tweet", json={"tweet_text": tweet_text}, cookies={"session_id": session_cookie})
    assert response.status_code == 200
    assert response.json() == {"message": "Tweet received successfully", "tweet_text": tweet_text}

@pytest.mark.asyncio
async def test_post_tweet_too_long(test_client):
    # First, log in to get a session cookie
    login_response = await test_client.post("/login", json={"username": "testuser", "password": "testpassword"})
    session_cookie = login_response.cookies["session_id"]

    long_tweet = "a" * 281
    response = await test_client.post("/compose/tweet", json={"tweet_text": long_tweet}, cookies={"session_id": session_cookie})
    assert response.status_code == 400
    assert response.json() == {"detail": "Invalid tweet text"}

@pytest.mark.asyncio
async def test_post_tweet_empty(test_client):
    # First, log in to get a session cookie
    login_response = await test_client.post("/login", json={"username": "testuser", "password": "testpassword"})
    session_cookie = login_response.cookies["session_id"]

    response = await test_client.post("/compose/tweet", json={"tweet_text": ""}, cookies={"session_id": session_cookie})
    assert response.status_code == 400
    assert response.json() == {"detail": "Invalid tweet text"}
