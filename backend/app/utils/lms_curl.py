import requests
import logging
from typing import Dict, Any
from ..config.settings import settings

logger = logging.getLogger(__name__)

def login_to_lms(email: str, password: str) -> Dict[str, Any]:
    """
    Authenticate with the LMS platform using email and password
    
    Args:
        email: User's email for LMS platform
        password: User's password for LMS platform
        lms_base_url: Base URL of the LMS platform (e.g., 'https://lms.example.com')
    
    Returns:
        Dictionary containing the response from LMS authentication endpoint
    """
    lms_base_url = settings.LMS_BASE_URL
    try:
        # Construct the full URL
        url = f"{lms_base_url}/api/v1/auth/signin"
        
        # Prepare headers
        headers = {
            'Content-Type': 'application/json'
        }
        
        # Prepare request body
        payload = {
            "email": email,
            "password": password
        }
        
        logger.info(f"Attempting to login to LMS at {url} with email: {email}")
        
        # Make the POST request
        response = requests.post(url, json=payload, headers=headers, timeout=30)
        
        # Log the response status
        logger.info(f"LMS login response status: {response.status_code}")
        
        # Raise an exception for bad status codes
        response.raise_for_status()
        
        # Parse and return the JSON response
        response_data = response.json()
        logger.info(f"Successfully logged into LMS")
        logger.info(f"LMS login response structure: {list(response_data.keys()) if isinstance(response_data, dict) else type(response_data)}")
        
        # Log token info if present
        if isinstance(response_data, dict):
            if 'token' in response_data:
                logger.info(f"Token found at root level: {response_data['token'][:20]}...")
            elif 'accessToken' in response_data:
                logger.info(f"Token found as accessToken: {response_data['accessToken'][:20]}...")
            elif 'access_token' in response_data:
                logger.info(f"Token found as access_token: {response_data['access_token'][:20]}...")
            elif 'data' in response_data and isinstance(response_data['data'], dict):
                logger.info(f"Data object keys: {list(response_data['data'].keys())}")
        
        return {
            "success": True,
            "status_code": response.status_code,
            "data": response_data
        }
        
    except requests.exceptions.Timeout:
        logger.error(f"Timeout while connecting to LMS at {url}")
        return {
            "success": False,
            "error": "Request timeout - LMS server took too long to respond",
            "status_code": 408
        }
    
    except requests.exceptions.ConnectionError:
        logger.error(f"Connection error while connecting to LMS at {url}")
        return {
            "success": False,
            "error": "Connection error - Could not connect to LMS server",
            "status_code": 503
        }
    
    except requests.exceptions.HTTPError as e:
        logger.error(f"HTTP error during LMS login: {str(e)}")
        error_message = "Authentication failed"
        try:
            error_data = response.json()
            error_message = error_data.get("message", error_message)
        except:
            error_message = response.text or error_message
            
        return {
            "success": False,
            "error": error_message,
            "status_code": response.status_code
        }
    
    except Exception as e:
        logger.error(f"Unexpected error during LMS login: {str(e)}")
        return {
            "success": False,
            "error": f"Unexpected error: {str(e)}",
            "status_code": 500
        }

def get_lms_courses(lms_token: str) -> Dict[str, Any]:
    """
    Get courses from the LMS platform
    
    Args:
        lms_token: Authentication token from LMS login
    
    Returns:
        Dictionary containing the response from LMS courses endpoint
    """
    lms_base_url = settings.LMS_BASE_URL
    
    try:
        # Construct the full URL
        url = f"{lms_base_url}/api/v1/course"
        
        # Prepare headers with authentication token
        headers = {
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {lms_token}'
        }
        
        logger.info(f"Fetching courses from LMS at {url}")
        logger.info(f"Authorization header: Bearer {lms_token[:20]}... (total length: {len(lms_token)})")
        
        # Make the GET request
        response = requests.get(url, headers=headers, timeout=30)
        
        # Log the response status
        logger.info(f"LMS courses response status: {response.status_code}")
        
        # Raise an exception for bad status codes
        response.raise_for_status()
        
        # Parse and return the JSON response
        response_data = response.json()
        logger.info(f"Successfully fetched {len(response_data) if isinstance(response_data, list) else 'unknown'} courses from LMS")
        
        return {
            "success": True,
            "status_code": response.status_code,
            "data": response_data
        }
        
    except requests.exceptions.Timeout:
        logger.error(f"Timeout while fetching courses from LMS at {url}")
        return {
            "success": False,
            "error": "Request timeout - LMS server took too long to respond",
            "status_code": 408
        }
    
    except requests.exceptions.ConnectionError:
        logger.error(f"Connection error while fetching courses from LMS at {url}")
        return {
            "success": False,
            "error": "Connection error - Could not connect to LMS server",
            "status_code": 503
        }
    
    except requests.exceptions.HTTPError as e:
        logger.error(f"HTTP error during LMS courses fetch: {str(e)}")
        error_message = "Failed to fetch courses"
        try:
            error_data = response.json()
            logger.error(f"LMS error response: {error_data}")
            error_message = error_data.get("message", error_message)
        except:
            error_message = response.text or error_message
            logger.error(f"LMS error response (raw): {response.text}")
            
        return {
            "success": False,
            "error": error_message,
            "status_code": response.status_code
        }
    
    except Exception as e:
        logger.error(f"Unexpected error during LMS courses fetch: {str(e)}")
        return {
            "success": False,
            "error": f"Unexpected error: {str(e)}",
            "status_code": 500
        }
