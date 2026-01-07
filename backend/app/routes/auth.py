from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import RedirectResponse, JSONResponse, HTMLResponse
from urllib.parse import quote, urlencode
from typing import Optional
import requests
import pyrebase
from firebase_admin import auth
import logging
import base64
import json
from ..services.firebase import firebase_config, db
from ..services.mongo import create_user, get_user_by_user_id
from ..config.settings import settings
from ..services.mongo import update_in_collection
from ..services.google_auth import validate_google_login

router = APIRouter()
logger = logging.getLogger(__name__)

# Initialize pyrebase
try:
    firebase = pyrebase.initialize_app(firebase_config)
except Exception as e:
    logger.error(f"Failed to initialize pyrebase: {str(e)}")
    raise ValueError(f"Failed to initialize pyrebase: {str(e)}")

# Google OAuth configuration
CLIENT_ID = settings.GOOGLE_CLIENT_ID
CLIENT_SECRET = settings.GOOGLE_CLIENT_SECRET
REDIRECT_URI = settings.GOOGLE_REDIRECT_URI
FIREBASE_API_KEY = settings.FIREBASE_API_KEY

# Check if required environment variables are set
if not CLIENT_ID or not CLIENT_SECRET or not FIREBASE_API_KEY:
    logger.warning("Google OAuth environment variables are not set. Google login will not work.")
    logger.warning("Please set GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET, and FIREBASE_API_KEY in your .env file")

def build_auth_url(login_type: str = "user") -> str:
    """Build Google OAuth URL with login_type encoded in state parameter"""
    # Encode login_type in base64 state parameter
    state_data = {"login_type": login_type}
    state = base64.urlsafe_b64encode(json.dumps(state_data).encode()).decode()
    
    return (
        f"https://accounts.google.com/o/oauth2/v2/auth?"
        f"client_id={CLIENT_ID}&"
        f"redirect_uri={quote(REDIRECT_URI)}&"
        f"response_type=code&"
        f"scope=openid%20email%20profile&"
        f"access_type=offline&"
        f"prompt=select_account&"
        f"state={state}"
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
        # Ensure user exists in Mongo
        try:
            if not get_user_by_user_id(user.uid):
                create_user(user.uid, email, name)
        except Exception as e:
            logger.warning(f"Mongo user create (signup) skipped or failed for {email}: {str(e)}")
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
        refresh_token = user["refreshToken"]
        logger.info(f"User logged in: {email}")
        
        # Import here to avoid circular imports
        from ..services.master_db import is_superadmin, get_organization_by_user_id, get_org_db
        
        # Check if superadmin
        if is_superadmin(user_id):
            logger.info(f"SuperAdmin logged in: {email}")
            return JSONResponse(content={
                "message": "Login successful", 
                "token": id_token, 
                "refresh_token": refresh_token, 
                "user_id": user_id,
                "role": "superadmin",
                "is_superadmin": True
            }, status_code=200)
        
        # Find user's organization
        org = get_organization_by_user_id(user_id)
        if org:
            org_db_name = org.get("database_name")
            org_db = get_org_db(org_db_name)
            user_doc = org_db["users"].find_one({"_id": user_id})
            role = user_doc.get("role", "user") if user_doc else "user"
            
            logger.info(f"User {email} logged in with org: {org.get('name')}, role: {role}")
            return JSONResponse(content={
                "message": "Login successful", 
                "token": id_token, 
                "refresh_token": refresh_token, 
                "user_id": user_id,
                "role": role,
                "org_id": org.get("_id"),
                "org_name": org.get("name"),
                "is_superadmin": False
            }, status_code=200)
        
        # Fallback to legacy behavior for users not in any org
        # (backward compatibility - ensure user exists in default Mongo)
        try:
            if not get_user_by_user_id(user_id):
                create_user(user_id, email)
        except Exception as e:
            logger.warning(f"Mongo user create (login) skipped or failed for {email}: {str(e)}")
        
        return JSONResponse(content={
            "message": "Login successful", 
            "token": id_token, 
            "refresh_token": refresh_token, 
            "user_id": user_id,
            "role": "user",
            "is_superadmin": False
        }, status_code=200)
    except Exception as e:
        logger.error(f"Login failed: {str(e)}")
        raise HTTPException(status_code=401, detail="Invalid credentials")

@router.get("/google-login")
async def start_google_login(login_type: str = "user"):
    """
    Start Google OAuth flow with login type.
    
    Args:
        login_type: "superadmin" | "admin" | "user" (default: "user")
    """
    logger.info(f"Redirecting to Google OAuth (login_type: {login_type})")
    
    # Check if environment variables are set
    if not CLIENT_ID or not CLIENT_SECRET or not FIREBASE_API_KEY:
        raise HTTPException(
            status_code=500, 
            detail="Google OAuth is not configured. Please set GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET, and FIREBASE_API_KEY in your .env file"
        )
    
    # Build auth URL with login_type in state
    auth_url = build_auth_url(login_type)
    return RedirectResponse(auth_url)

@router.get("/callback")
async def google_callback(code: Optional[str] = None, error: Optional[str] = None, state: Optional[str] = None):
    logger.info(f"Google callback received - code: {code is not None}, error: {error}, state: {state is not None}")
    
    # Extract login_type from state parameter
    login_type = "user"  # Default
    if state:
        try:
            state_data = json.loads(base64.urlsafe_b64decode(state).decode())
            login_type = state_data.get("login_type", "user")
            logger.info(f"Extracted login_type from state: {login_type}")
        except Exception as e:
            logger.warning(f"Failed to decode state parameter: {e}")
    
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
        display_name = decoded_token.get("name", "")
        logger.info(f"Google login for user: {email} (login_type: {login_type})")

        # ========== AUTHORIZATION CHECK ==========
        auth_result = validate_google_login(email, login_type)
        
        if not auth_result["allowed"]:
            logger.warning(f"Google login denied for {email}: {auth_result['error']}")
            # Return HTML with error message
            error_html = f"""
            <!DOCTYPE html>
            <html>
            <head>
                <title>Login Failed</title>
                <style>
                    body {{ 
                        font-family: Arial, sans-serif; 
                        text-align: center; 
                        padding: 50px; 
                        background: #f8f9fa;
                    }}
                    .error {{ 
                        color: #dc3545; 
                        font-size: 24px; 
                        margin-bottom: 20px;
                    }}
                    .info {{ 
                        color: #666; 
                        margin: 10px 0; 
                    }}
                    .container {{
                        background: white;
                        border-radius: 8px;
                        padding: 30px;
                        box-shadow: 0 2px 10px rgba(0,0,0,0.1);
                        max-width: 400px;
                        margin: 0 auto;
                    }}
                </style>
            </head>
            <body>
                <div class="container">
                    <div class="error">❌ Access Denied</div>
                    <div class="info">{auth_result['error']}</div>
                    <div class="info" style="margin-top: 20px;">This tab will close in 5 seconds...</div>
                </div>
                <script>
                    setTimeout(() => {{
                        window.close();
                    }}, 5000);
                </script>
            </body>
            </html>
            """
            return HTMLResponse(content=error_html, status_code=200)

        # ========== AUTO-REGISTRATION FOR NORMAL USERS ==========
        from ..services.master_db import get_org_db
        from datetime import datetime
        
        role = auth_result.get("role", "user")
        org_id = auth_result.get("org_id")
        org_name = auth_result.get("org_name")
        database_name = auth_result.get("database_name")
        is_superadmin = auth_result.get("is_superadmin", False)
        
        # For normal users and admins, ensure they exist in the org database
        if database_name and not is_superadmin:
            org_db = get_org_db(database_name)
            existing_user = org_db["users"].find_one({"_id": user_id})
            
            if not existing_user:
                # Auto-register the user
                new_user = {
                    "_id": user_id,
                    "email": email,
                    "display_name": display_name,
                    "role": role,
                    "auth_provider": "google",
                    "auto_registered": True,
                    "created_at": datetime.utcnow().isoformat()
                }
                org_db["users"].insert_one(new_user)
                logger.info(f"Auto-registered new user via Google: {email} in org {org_name} with role {role}")
            else:
                # Update existing user's display name if needed
                if display_name and existing_user.get("display_name") != display_name:
                    org_db["users"].update_one(
                        {"_id": user_id},
                        {"$set": {"display_name": display_name}}
                    )
                # Use existing role for this user
                role = existing_user.get("role", role)
                logger.info(f"Existing user logged in via Google: {email} in org {org_name}")

        # Store user info in Firestore (optional, for consistency)
        db.collection("users").document(user_id).set({"email": email}, merge=True)

        # Store token in a simple in-memory store (for demo purposes)
        global _temp_tokens
        if '_temp_tokens' not in globals():
            _temp_tokens = {}
        token_key = f"google_token_{user_id}"
        _temp_tokens[token_key] = firebase_tokens["idToken"]

        # Prepare user data for JavaScript - use JSON encoding for proper escaping
        user_data = {
            "email": email,
            "userId": user_id,
            "displayName": display_name or "",
            "token": firebase_tokens["idToken"],
            "refreshToken": firebase_tokens["refreshToken"],
            "role": role,
            "orgId": org_id or "",
            "orgName": org_name or "",
            "isSuperAdmin": is_superadmin
        }
        # JSON encode the user data to safely embed in JavaScript
        user_data_json = json.dumps(user_data)
        
        # Return HTML with JavaScript to notify the parent window
        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Login Successful</title>
            <style>
                body {{ 
                    font-family: Arial, sans-serif; 
                    text-align: center; 
                    padding: 50px; 
                    background: #f8f9fa;
                }}
                .success {{ 
                    color: #28a745; 
                    font-size: 24px; 
                    margin-bottom: 20px;
                }}
                .info {{ 
                    color: #666; 
                    margin: 10px 0; 
                }}
                .container {{
                    background: white;
                    border-radius: 8px;
                    padding: 30px;
                    box-shadow: 0 2px 10px rgba(0,0,0,0.1);
                    max-width: 400px;
                    margin: 0 auto;
                }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="success">✅ Login Successful!</div>
                <div class="info">Welcome, {email}</div>
                <div class="info">Closing this tab automatically...</div>
            </div>
            <script>
                let messageSent = false;
                
                if (window.opener && !window.opener.closed) {{
                    console.log('Notifying parent window about successful login');
                    try {{
                        const userData = {user_data_json};
                        window.opener.postMessage({{
                            type: 'GOOGLE_LOGIN_SUCCESS',
                            user: userData
                        }}, '*');
                        messageSent = true;
                        console.log('Message sent successfully to parent window');
                    }} catch (e) {{
                        console.log('Could not notify parent window:', e);
                    }}
                }}
                
                if (!messageSent) {{
                    document.querySelector('.info').innerHTML = 
                        'Login successful! Please close this tab and return to the main application.';
                }}
                
                setTimeout(() => {{
                    window.close();
                }}, 3000);
            </script>
        </body>
        </html>
        """
        
        return HTMLResponse(content=html_content, status_code=200)
    except requests.RequestException as e:
        logger.error(f"Token exchange failed: {str(e)}")
        raise HTTPException(status_code=400, detail=f"Token exchange failed: {str(e)}")

@router.post("/refresh-token")
async def refresh_token_endpoint(request: Request):
    """Refresh Firebase ID token using refresh token"""
    try:
        data = await request.json()
        refresh_token = data.get("refresh_token")
        
        if not refresh_token:
            raise HTTPException(status_code=400, detail="Missing refresh token")
        
        # Call Firebase to refresh the token
        response = requests.post(
            f"https://securetoken.googleapis.com/v1/token?key={FIREBASE_API_KEY}",
            data={
                "grant_type": "refresh_token",
                "refresh_token": refresh_token
            },
            timeout=10
        )
        response.raise_for_status()
        token_data = response.json()
        
        return JSONResponse(content={
            "token": token_data["id_token"],
            "refresh_token": token_data["refresh_token"]
        }, status_code=200)
        
    except requests.RequestException as e:
        logger.error(f"Token refresh failed: {str(e)}")
        raise HTTPException(status_code=401, detail="Failed to refresh token")
    except Exception as e:
        logger.error(f"Token refresh error: {str(e)}")
        raise HTTPException(status_code=500, detail="Token refresh failed")

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