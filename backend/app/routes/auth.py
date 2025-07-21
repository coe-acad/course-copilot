from fastapi import APIRouter, Request, HTTPException, status
from fastapi.responses import RedirectResponse, JSONResponse, HTMLResponse
from dotenv import load_dotenv
from urllib.parse import quote
from typing import Optional
import os
import requests
import pyrebase
from firebase_admin import auth
import logging
from ..config.firebase import firebase_config, db

router = APIRouter()
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# Initialize pyrebase
try:
    firebase = pyrebase.initialize_app(firebase_config)
except Exception as e:
    logger.error(f"Failed to initialize pyrebase: {str(e)}")
    raise ValueError(f"Failed to initialize pyrebase: {str(e)}")

# Google OAuth configuration
CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")
CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET")
REDIRECT_URI = os.getenv("GOOGLE_REDIRECT_URI", "http://localhost:8000/auth/callback")
FIREBASE_API_KEY = os.getenv("FIREBASE_API_KEY")

# Check if required environment variables are set
if not CLIENT_ID or not CLIENT_SECRET or not FIREBASE_API_KEY:
    logger.warning("Google OAuth environment variables are not set. Google login will not work.")
    logger.warning("Please set GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET, and FIREBASE_API_KEY in your .env file")
AUTH_URL = (
    f"https://accounts.google.com/o/oauth2/v2/auth?"
    f"client_id={CLIENT_ID}&"
    f"redirect_uri={quote(REDIRECT_URI)}&"
    f"response_type=code&"
    f"scope=openid%20email%20profile&"
    f"access_type=offline&"
    f"prompt=select_account"
)

@router.post("/signup")
async def signup(request: Request):
    try:
        data = await request.json()
        email = data.get("email")
        password = data.get("password")
        name = data.get("name")
        if not email or not password or not name:
            raise HTTPException(status_code=400, detail="Missing email, password, or name")
        user = auth.create_user(email=email, password=password, display_name=name)
        logger.info(f"User signed up: {email}")
        return JSONResponse(content={"message": "Signup successful", "user_id": user.uid}, status_code=200)
    except Exception as e:
        logger.error(f"Signup failed: {str(e)}")
        raise HTTPException(status_code=400, detail=f"Signup failed: {str(e)}")

@router.post("/login")
async def login(request: Request):
    try:
        data = await request.json()
        email = data.get("email")
        password = data.get("password")
        if not email or not password:
            raise HTTPException(status_code=400, detail="Missing email or password")
        user = firebase.auth().sign_in_with_email_and_password(email, password)
        user_id = user["localId"]
        id_token = user["idToken"]
        logger.info(f"User logged in: {email}")
        return JSONResponse(content={"message": "Login successful", "token": id_token, "user_id": user_id}, status_code=200)
    except Exception as e:
        logger.error(f"Login failed: {str(e)}")
        raise HTTPException(status_code=401, detail="Invalid credentials")

@router.get("/google-login")
async def start_google_login():
    logger.info("Redirecting to Google OAuth")
    
    # Check if environment variables are set
    if not CLIENT_ID or not CLIENT_SECRET or not FIREBASE_API_KEY:
        raise HTTPException(
            status_code=500, 
            detail="Google OAuth is not configured. Please set GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET, and FIREBASE_API_KEY in your .env file"
        )
    
    # Store a session identifier or use a simple approach
    # For now, we'll redirect to Google OAuth
    return RedirectResponse(AUTH_URL)

@router.get("/test-callback")
async def test_callback():
    """Test endpoint to verify the callback route is accessible"""
    return {"message": "Callback route is working!"}

@router.get("/callback")
async def google_callback(code: Optional[str] = None, error: Optional[str] = None):
    logger.info(f"Google callback received - code: {code is not None}, error: {error}")
    if error:
        logger.error(f"Google login failed: {error}")
        raise HTTPException(status_code=400, detail=f"Google login failed: {error}")
    if not code:
        logger.error("No authorization code provided")
        raise HTTPException(status_code=400, detail="No authorization code provided")

    try:
        # Exchange code for Google tokens
        token_url = "https://oauth2.googleapis.com/token"
        data = {
            "code": code,
            "client_id": CLIENT_ID,
            "client_secret": CLIENT_SECRET,
            "redirect_uri": REDIRECT_URI,
            "grant_type": "authorization_code"
        }
        response = requests.post(token_url, data=data, timeout=10)
        response.raise_for_status()
        tokens = response.json()
        if "id_token" not in tokens:
            logger.error("Failed to get Google ID token")
            raise HTTPException(status_code=400, detail="Failed to get Google ID token")

        # Exchange Google ID token for Firebase ID token
        firebase_url = f"https://identitytoolkit.googleapis.com/v1/accounts:signInWithIdp?key={FIREBASE_API_KEY}"
        firebase_data = {
            "postBody": f"id_token={tokens['id_token']}&providerId=google.com",
            "requestUri": REDIRECT_URI,
            "returnIdpCredential": True,
            "returnSecureToken": True
        }
        firebase_response = requests.post(firebase_url, json=firebase_data, timeout=10)
        firebase_response.raise_for_status()
        firebase_tokens = firebase_response.json()
        if "idToken" not in firebase_tokens:
            logger.error("Failed to get Firebase ID token")
            raise HTTPException(status_code=400, detail="Failed to get Firebase ID token")

        # Verify Firebase ID token
        decoded_token = auth.verify_id_token(firebase_tokens["idToken"])
        user_id = decoded_token["uid"]
        email = decoded_token.get("email", "unknown")
        logger.info(f"Google login successful for user: {email}")

        # Store user info in Firestore (optional, for consistency)
        db.collection("users").document(user_id).set({"email": email}, merge=True)

        # Store token in a simple in-memory store (for demo purposes)
        # In production, use Redis or a proper session store
        global _temp_tokens
        if '_temp_tokens' not in globals():
            _temp_tokens = {}
        
        # Store token with a simple key (in production, use proper session management)
        token_key = f"google_token_{user_id}"
        _temp_tokens[token_key] = firebase_tokens["idToken"]

        # Return a simple HTML page indicating success
        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Login Successful</title>
            <style>
                body {{ font-family: Arial, sans-serif; text-align: center; padding: 50px; }}
                .success {{ color: green; font-size: 24px; }}
                .info {{ color: #666; margin: 20px 0; }}
            </style>
        </head>
        <body>
            <div class="success">✅ Google Login Successful!</div>
            <div class="info">Welcome, {email}</div>
            <div class="info">You can now close this tab and return to the Streamlit app.</div>
            <div class="info">Click "Check Google Login Status" in the Streamlit app to continue.</div>
        </body>
        </html>
        """
        
        return HTMLResponse(content=html_content, status_code=200)
    except requests.RequestException as e:
        logger.error(f"Token exchange failed: {str(e)}")
        raise HTTPException(status_code=400, detail=f"Token exchange failed: {str(e)}")

@router.get("/get-token")
async def get_token(request: Request):
    # First try to get token from cookie
    id_token = request.cookies.get("id_token")
    if id_token:
        logger.info("Retrieved token from cookie")
        return {"id_token": id_token}
    
    # If no cookie, check if we have any stored tokens (for demo purposes)
    global _temp_tokens
    if '_temp_tokens' in globals() and _temp_tokens:
        # Return the first available token (in production, use proper session management)
        first_token = list(_temp_tokens.values())[0]
        logger.info("Retrieved token from temporary storage")
        return {"id_token": first_token}
    
    logger.error("No token available")
    raise HTTPException(status_code=400, detail="No token available")