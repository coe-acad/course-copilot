from fastapi import HTTPException, Depends, APIRouter
from pydantic import BaseModel
from ..services.mongo import get_course, get_asset_by_course_id_and_asset_name
from ..utils.data_formating import format_quiz_content
from ..utils.verify_token import verify_token
from ..utils.lms_curl import login_to_lms, get_lms_courses
from ..config.settings import settings
import logging

logger = logging.getLogger(__name__)
router = APIRouter()

class ExportLMSRequest(BaseModel):
    asset_type: list[str]
    asset_names: list[str]

class LoginLMSRequest(BaseModel):
    email: str
    password: str

class GoogleLoginLMSRequest(BaseModel):
    email: str

class GetCoursesLMSRequest(BaseModel):
    lms_cookies: str  # LMS authentication cookies from Set-Cookie header

#route to login to the lms
@router.post("/login-lms")
def login_lms(request: LoginLMSRequest, user_id: str=Depends(verify_token)):
    """
    Login to the LMS platform with user credentials
    
    Returns authentication cookies that must be used for subsequent LMS requests.
    """
    try:
        # Validate input
        if not request.email or not request.password:
            raise HTTPException(status_code=400, detail="Email and password are required")
        
        # Call the LMS login utility function
        result = login_to_lms(request.email, request.password)
        
        # Check if login was successful
        if not result.get("success"):
            raise HTTPException(
                status_code=result.get("status_code", 401),
                detail=result.get("error", "LMS authentication failed")
            )
        
        logger.info(f"User {user_id} successfully logged into LMS")
        
        # Return the success response with cookies from Set-Cookie header
        return {
            "message": "Successfully logged into LMS",
            "data": result.get("data", {}),
            "cookies": result.get("cookies", ""),  # Cookies for session-based auth
            "token": result.get("token")  # Keep for backward compatibility if API also returns token
        }
        
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error during LMS login: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


#route to get the courses from the lms
@router.post("/courses-lms")
def get_courses_lms(request: GetCoursesLMSRequest, user_id: str):
    """
    Get courses from the LMS platform using session cookies from login
    """
    try:
        # Validate input
        if not request.lms_cookies:
            raise HTTPException(status_code=400, detail="LMS authentication cookies are required")
        
        # Check if LMS_BASE_URL is configured in settings
        if not settings.LMS_BASE_URL:
            raise HTTPException(status_code=500, detail="LMS base URL is not configured in server settings")
        
        # Log cookie info (first few characters only for security)
        logger.info(f"Using LMS cookies to fetch courses: {request.lms_cookies[:50]}...")
        
        # Call the LMS courses utility function with the cookies
        result = get_lms_courses(request.lms_cookies)
        
        # Check if request was successful
        if not result.get("success"):
            raise HTTPException(
                status_code=result.get("status_code", 500),
                detail=result.get("error", "Failed to fetch courses from LMS")
            )
        
        logger.info(f"User {user_id} successfully fetched courses from LMS")
        
        # Return the success response
        return {
            "message": "Successfully fetched courses from LMS",
            "data": result.get("data", [])
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching LMS courses: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")
        
