from fastapi import FastAPI, Request, Response, HTTPException, status
from fastapi.responses import HTMLResponse, RedirectResponse
from pydantic import BaseModel
from typing import Dict, Any
import uvicorn

app = FastAPI()

# In-memory store for session (simple for mock)
sessions: Dict[str, bool] = {}

class LoginRequest(BaseModel):
    username: str
    password: str

class TweetRequest(BaseModel):
    tweet_text: str

@app.get("/health")
async def health_check():
    return {"status": "healthy"}

@app.get("/login", response_class=HTMLResponse)
async def get_login_page(request: Request):
    session_id = request.cookies.get("session_id")
    if session_id and sessions.get(session_id):
        return RedirectResponse(url="/compose/tweet", status_code=status.HTTP_302_FOUND)

    return """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Login to Mock Social</title>
        <style>
            body { font-family: sans-serif; display: flex; justify-content: center; align-items: center; height: 100vh; background-color: #f0f2f5; }
            .login-container { background: white; padding: 2em; border-radius: 8px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); text-align: center; }
            input { display: block; width: 100%; padding: 0.8em; margin: 0.5em 0; border: 1px solid #ccc; border-radius: 4px; }
            button { background-color: #1877f2; color: white; padding: 0.8em 1.5em; border: none; border-radius: 4px; cursor: pointer; font-size: 1em; }
            button:hover { background-color: #166fe5; }
        </style>
    </head>
    <body>
        <div class="login-container">
            <h1>Login</h1>
            <form id="login-form" action="/login" method="post">
                <input type="text" id="username" name="username" placeholder="Username" required>
                <input type="password" id="password" name="password" placeholder="Password" required>
                <button type="submit" id="login-btn">Login</button>
            </form>
        </div>
        <script>
            document.getElementById('login-form').addEventListener('submit', async function(event) {
                event.preventDefault();
                const username = document.getElementById('username').value;
                const password = document.getElementById('password').value;
                const response = await fetch('/login', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ username, password })
                });
                if (response.ok) {
                    window.location.href = '/compose/tweet';
                } else {
                    alert('Login failed!');
                }
            });
        </script>
    </body>
    </html>
    """

@app.post("/login")
async def post_login(login_data: LoginRequest, response: Response):
    # For mock, any username/password is considered valid
    session_id = "mock_session_id_123" # Deterministic session ID
    sessions[session_id] = True
    response.set_cookie(key="session_id", value=session_id, httponly=True, samesite="Lax")
    return {"message": "Login successful", "redirect": "/compose/tweet"}

@app.get("/compose/tweet", response_class=HTMLResponse)
async def get_compose_page(request: Request):
    session_id = request.cookies.get("session_id")
    if not (session_id and sessions.get(session_id)):
        return RedirectResponse(url="/login", status_code=status.HTTP_302_FOUND)

    return """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Compose Tweet</title>
        <style>
            body { font-family: sans-serif; display: flex; justify-content: center; align-items: center; height: 100vh; background-color: #f0f2f5; }
            .compose-container { background: white; padding: 2em; border-radius: 8px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); text-align: center; }
            textarea { display: block; width: 100%; padding: 0.8em; margin: 0.5em 0; border: 1px solid #ccc; border-radius: 4px; resize: vertical; min-height: 100px; }
            button { background-color: #1da1f2; color: white; padding: 0.8em 1.5em; border: none; border-radius: 4px; cursor: pointer; font-size: 1em; }
            button:hover { background-color: #1a91da; }
        </style>
    </head>
    <body>
        <div class="compose-container">
            <h1>Compose New Tweet</h1>
            <form id="tweet-form" action="/compose/tweet" method="post">
                <textarea id="tweet-text" name="tweet_text" placeholder="What's happening?" maxlength="280" required></textarea>
                <button type="submit" id="post-btn">Post Tweet</button>
            </form>
            <div id="post-status" style="margin-top: 1em; color: green;"></div>
        </div>
        <script>
            document.getElementById('tweet-form').addEventListener('submit', async function(event) {
                event.preventDefault();
                const tweetText = document.getElementById('tweet-text').value;
                const response = await fetch('/compose/tweet', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ tweet_text: tweetText })
                });
                const statusDiv = document.getElementById('post-status');
                if (response.ok) {
                    statusDiv.textContent = 'Tweet posted successfully!';
                    statusDiv.style.color = 'green';
                    document.getElementById('tweet-text').value = ''; // Clear textarea
                } else {
                    const errorData = await response.json();
                    statusDiv.textContent = 'Failed to post tweet: ' + (errorData.detail || response.statusText);
                    statusDiv.style.color = 'red';
                }
            });
        </script>
    </body>
    </html>
    """

@app.post("/compose/tweet")
async def post_tweet(tweet_data: TweetRequest, request: Request):
    session_id = request.cookies.get("session_id")
    if not (session_id and sessions.get(session_id)):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")

    if not tweet_data.tweet_text or len(tweet_data.tweet_text) > 280:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid tweet text")

    print(f"Mock Social Server received tweet: '{tweet_data.tweet_text}'")
    return {"message": "Tweet received successfully", "tweet_text": tweet_data.tweet_text}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8080)
