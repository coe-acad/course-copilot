from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import RedirectResponse, JSONResponse, HTMLResponse
from urllib.parse import quote
from typing import Optional
import requests
import pyrebase
from firebase_admin import auth
import logging
from ..services.firebase import firebase_config, db
from ..services.mongo import create_user, get_user_by_user_id
from ..config.settings import settings
from ..services.mongo import update_in_collection

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
AUTH_URL = (
    f"https://accounts.google.com/o/oauth2/v2/auth?"
    f"client_id={CLIENT_ID}&"
    f"redirect_uri={quote(REDIRECT_URI)}&"
    f"response_type=code&"
    f"scope=openid%20email%20profile&"
    f"hd=atriauniversity.edu.in&"   # This ensures only Atria University users can log in
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
        
        allowed_domains = getattr(settings, "ALLOWED_EMAIL_DOMAINS", ["atriauniversity.edu.in"])
        email_domain = email.split("@")[-1].lower() if "@" in email else ""
        if email_domain not in allowed_domains:
            allowed_str = ", ".join("@" + d for d in allowed_domains)
            raise HTTPException(
                status_code=403, 
                detail=f"Registration is restricted to official organization email addresses ({allowed_str}) only."
            )
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

        # Only organisation domains may log in. Checked before authenticating so a
        # disallowed domain never reaches credential verification.
        # TEMPORARILY BYPASSABLE: set ENFORCE_LOGIN_EMAIL_DOMAIN=false to let an
        # existing account outside the domain sign in. Signup (above) and Google
        # login are NOT affected — they stay restricted regardless of this flag.
        if getattr(settings, "ENFORCE_LOGIN_EMAIL_DOMAIN", True):
            allowed_domains = getattr(settings, "ALLOWED_EMAIL_DOMAINS", ["atriauniversity.edu.in"])
            email_domain = email.split("@")[-1].lower() if "@" in email else ""
            if email_domain not in allowed_domains:
                logger.warning(f"Unauthorized login attempt from restricted domain: {email}")
                allowed_str = ", ".join("@" + d for d in allowed_domains)
                raise HTTPException(
                    status_code=403,
                    detail=f"Login is restricted to official organization email addresses ({allowed_str}) only."
                )
        else:
            logger.warning(
                f"Email domain check BYPASSED for login: {email} "
                "(ENFORCE_LOGIN_EMAIL_DOMAIN=false)"
            )

        user = firebase.auth().sign_in_with_email_and_password(email, password)
        user_id = user["localId"]
        id_token = user["idToken"]
        refresh_token = user["refreshToken"]
        logger.info(f"User logged in: {email}")
        # Ensure user exists in Mongo
        try:
            if not get_user_by_user_id(user_id):
                create_user(user_id, email)
        except Exception as e:
            logger.warning(f"Mongo user create (login) skipped or failed for {email}: {str(e)}")
        return JSONResponse(content={"message": "Login successful", "token": id_token, "refresh_token": refresh_token, "user_id": user_id}, status_code=200)
    except HTTPException:
        # Preserve the status and message of the checks above (400 / 403) instead of
        # reporting them as invalid credentials.
        raise
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
        
        # This is allow the domains belong to the atriauniversity domains only
        allowed_domains = getattr(settings, "ALLOWED_EMAIL_DOMAINS", ["atriauniversity.edu.in"])
        email_domain = email.split("@")[-1].lower() if "@" in email else ""
        if email_domain not in allowed_domains:
            logger.warning(f"Unauthorized login attempt from restricted domain: {email}")
            allowed_domains_str = ", ".join("@" + d for d in allowed_domains)
            return HTMLResponse(
                content=f"""
                <!DOCTYPE html>
                <html>
                <head>
                    <title>Access Denied</title>
                    <style>
                        body {{ font-family: Arial, sans-serif; text-align: center; padding: 50px; background: #f8f9fa; }}
                        .card {{ background: white; border-radius: 8px; padding: 30px; max-width: 420px; margin: 0 auto; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }}
                        .title {{ color: #dc2626; font-size: 22px; font-weight: bold; margin-bottom: 12px; }}
                        .desc {{ color: #4b5563; font-size: 14px; line-height: 1.5; margin-bottom: 20px; }}
                        .btn {{ background: #2563eb; color: white; border: none; padding: 10px 20px; border-radius: 6px; cursor: pointer; font-size: 14px; }}
                    </style>
                </head>
                <body>
                    <div class="card">
                        <div class="title">Access Denied</div>
                        <div class="desc">Only official organization email addresses ({allowed_domains_str}) are permitted to log in.</div>
                        <button class="btn" onclick="window.close()">Close Window</button>
                    </div>
                </body>
                </html>
                """,
                status_code=403
            )

        logger.info(f"Google login successful for user: {email}")

        # Store user info in Firestore (optional, for consistency)
        db.collection("users").document(user_id).set({"email": email}, merge=True)

        # Ensure user exists in Mongo and update email
        try:
            display_name = decoded_token.get("name", "")
            existing_user = get_user_by_user_id(user_id)
            if not existing_user:
                create_user(user_id, email, display_name)
                logger.info(f"Created new MongoDB user for Google sign-in: {email}")
            else:
                # Update email and display name in case they changed
                update_data = {"email": email}
                if display_name:
                    update_data["display_name"] = display_name
                update_in_collection("users", {"_id": user_id}, update_data)
                logger.info(f"Updated MongoDB user email for Google sign-in: {email}")
        except Exception as e:
            logger.warning(f"Mongo user create/update (google) skipped or failed for {email}: {str(e)}")

        # NOTE: the ID token is deliberately NOT kept server-side. It is handed to
        # the opener window below and stored by the browser only. A previous
        # in-memory `_temp_tokens` store existed here and was readable by anyone
        # through an unauthenticated GET /get-token, which leaked a signed-in
        # user's token to any caller. Do not reintroduce a shared token store.

        # Get additional user info from Firebase
        user_info = {
            "email": email,
            "userId": user_id,
            "displayName": decoded_token.get("name", ""),
            "token": firebase_tokens["idToken"]
        }

        # Return HTML with JavaScript to automatically close the tab and notify the parent window
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
                // Try to notify the parent window about successful login
                let messageSent = false;
                
                if (window.opener && !window.opener.closed) {{
                    console.log('Notifying parent window about successful login');
                    try {{
                        window.opener.postMessage({{
                            type: 'GOOGLE_LOGIN_SUCCESS',
                            user: {{
                                email: '{email}',
                                userId: '{user_id}',
                                displayName: '{decoded_token.get("name", "")}',
                                token: '{firebase_tokens["idToken"]}',
                                refreshToken: '{firebase_tokens["refreshToken"]}'
                            }}
                        }}, '*');
                        messageSent = true;
                        console.log('Message sent successfully to parent window');
                    }} catch (e) {{
                        console.log('Could not notify parent window:', e);
                    }}
                }}
                else {{
                    console.log('No parent window found or parent window is closed');
                }}
                
                // If we couldn't send the message, show instructions to the user
                if (!messageSent) {{
                    document.querySelector('.info').innerHTML = 
                        'Login successful! Please close this tab and return to the main application.';
                }}
                
                // Close the tab after a short delay
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

# REMOVED: GET /get-token.
# It was unauthenticated and returned the first token out of a process-global
# store, i.e. it handed a signed-in user's Firebase ID token to any anonymous
# caller, who could then act as that user against every protected endpoint.
# Nothing in the frontend used it. Clients get their token from the login
# response or the OAuth popup, and renew it via POST /refresh-token.