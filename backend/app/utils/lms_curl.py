import requests
import logging
from typing import Dict, Any
from ..config.settings import settings

logger = logging.getLogger(__name__)

def login_to_lms(email: str, password: str) -> Dict[str, Any]:
    """
    Authenticate with the LMS platform using email and password
    Matches curl: curl --location 'learnx-dev.atriauniversity.in/api/v1/auth/signin'
    """
    lms_base_url = settings.LMS_BASE_URL
    
    # Ensure URL has protocol
    if not lms_base_url.startswith('http://') and not lms_base_url.startswith('https://'):
        lms_base_url = f"https://{lms_base_url}"
    
    url = f"{lms_base_url}/api/v1/auth/signin"
    
    payload = {
        "email": email,
        "password": password
    }
    
    headers = {
        'Content-Type': 'application/json'
    }
    
    try:
        logger.info(f"Attempting LMS login at {url} with email: {email}")
        
        response = requests.post(url, json=payload, headers=headers, timeout=30)
        
        logger.info(f"LMS Response Status: {response.status_code}")
        logger.info(f"LMS Response Headers: {dict(response.headers)}")
        
        # Get response data
        response_data = response.json()
        logger.info(f"LMS Response Keys: {list(response_data.keys())}")
        
        # Check if successful
        if response.status_code == 200:
            # Extract cookies from Set-Cookie header
            cookies = response.headers.get('Set-Cookie', '')
            logger.info(f"Login successful! Set-Cookie header: {cookies[:100]}...")
            
            # Also check for token in response body (some APIs use both)
            token = response_data.get('token') or response_data.get('accessToken')
            if token:
                logger.info(f"Also found token in response: {token[:30]}...")
            
            return {
                "success": True,
                "status_code": response.status_code,
                "data": response_data,
                "cookies": cookies,
                "token": token  # Keep this for backward compatibility
            }
        else:
            # Non-200 status code
            error_msg = response_data.get('message') or response_data.get('error') or response_data.get('detail') or 'Authentication failed'
            logger.error(f"LMS login failed: {error_msg}")
            logger.error(f"Full response: {response_data}")
            
            return {
                "success": False,
                "status_code": response.status_code,
                "error": error_msg,
                "data": response_data
            }
            
    except requests.exceptions.Timeout:
        logger.error(f"Timeout connecting to LMS at {url}")
        return {
            "success": False,
            "error": "Request timeout - LMS server took too long to respond",
            "status_code": 408
        }
    
    except requests.exceptions.ConnectionError as e:
        logger.error(f"Connection error to LMS at {url}: {str(e)}")
        return {
            "success": False,
            "error": "Connection error - Could not connect to LMS server",
            "status_code": 503
        }
    
    except Exception as e:
        logger.error(f"Unexpected error during LMS login: {str(e)}")
        return {
            "success": False,
            "error": f"Unexpected error: {str(e)}",
            "status_code": 500
        }

def get_lms_courses(lms_cookies: str) -> Dict[str, Any]:
    """
    Get courses from the LMS platform using authentication cookies
    
    Args:
        lms_cookies: Cookie string from Set-Cookie header (session-based auth)
    """
    lms_base_url = settings.LMS_BASE_URL
    
    # Ensure URL has protocol
    if not lms_base_url.startswith('http://') and not lms_base_url.startswith('https://'):
        lms_base_url = f"https://{lms_base_url}"
    
    url = f"{lms_base_url}/api/v1/course"
    
    headers = {
        'Content-Type': 'application/json',
        'Cookie': lms_cookies  # Use Cookie header for session-based auth
    }
    
    try:
        logger.info(f"📚 Fetching courses from LMS at {url}")
        logger.info(f"🍪 Using cookies: {lms_cookies[:50]}...")
        
        response = requests.get(url, headers=headers, timeout=30)
        response_data = response.json()
        
        if response.status_code == 200:
            logger.info(f"✅ Fetched courses successfully!")
            return {
                "success": True,
                "status_code": response.status_code,
                "data": response_data
            }
        else:
            error_msg = response_data.get('message') or response_data.get('error') or 'Failed to fetch courses'
            logger.error(f"❌ Failed to fetch courses: {error_msg}")
            return {
                "success": False,
                "status_code": response.status_code,
                "error": error_msg
            }
            
    except Exception as e:
        logger.error(f"💥 Error fetching courses: {str(e)}")
        return {
            "success": False,
            "error": f"Unexpected error: {str(e)}",
            "status_code": 500
        }
