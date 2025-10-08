from fastapi import HTTPException, Depends, APIRouter
from pydantic import BaseModel
from ..services.mongo import get_course, get_asset_by_course_id_and_asset_name
from ..utils.data_formating import format_quiz_content
from ..utils.verify_token import verify_token
from ..utils.lms_curl import login_to_lms, get_lms_courses, get_all_modules, post_quiz_data_to_lms, link_activity_to_course
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

class GetModulesLMSRequest(BaseModel):
    lms_cookies: str  # LMS authentication cookies from Set-Cookie header
    lms_course_id: str  # The ID of the course to get modules for

class PostQuizRequest(BaseModel):
    lms_cookies: str  # LMS authentication cookies from Set-Cookie header
    course_id: str  # Course ID in our system (to get quiz data)
    asset_name: str  # Name of the quiz asset to export
    lms_course_id: str  # LMS course ID (destination)
    lms_module_id: str  # LMS module ID (destination)
    order: int = 0  # Order of the activity in the module (optional, defaults to 0)

class PostAssetRequest(BaseModel):
    lms_cookies: str  # LMS authentication cookies from Set-Cookie header
    course_id: str  # Course ID in our system (to get asset data)
    asset_name: str  # Name of the asset to export
    asset_type: str  # Type of asset (quiz, activity, project, etc.)
    lms_course_id: str  # LMS course ID (destination)
    lms_module_id: str  # LMS module ID (destination)
    order: int = 0  # Order of the activity in the module (optional, defaults to 0)

def post_quiz_to_lms(request: PostQuizRequest, user_id: str):
    """
    Post quiz data to the LMS platform and link it to course/module
    
    This endpoint:
    1. Gets the quiz asset from MongoDB
    2. Formats it using OpenAI into the LMS-compatible structure
    3. Posts it to the LMS platform
    4. Links the activity to the specified course and module
    """
    try:
        # Validate input
        if not request.lms_cookies:
            raise HTTPException(status_code=400, detail="LMS authentication cookies are required")
        if not request.course_id:
            raise HTTPException(status_code=400, detail="Course ID is required")
        if not request.asset_name:
            raise HTTPException(status_code=400, detail="Asset name is required")
        if not request.lms_course_id:
            raise HTTPException(status_code=400, detail="LMS course ID is required")
        if not request.lms_module_id:
            raise HTTPException(status_code=400, detail="LMS module ID is required")
        
        logger.info(f"User {user_id} posting quiz '{request.asset_name}' to LMS course {request.lms_course_id}")
        
        # Step 1: Format the quiz content using OpenAI
        formatted_quiz_data = format_quiz_content(
            course_id=request.course_id,
            asset_name=request.asset_name
        )
        
        logger.info(f"Formatted quiz data: {formatted_quiz_data.get('title', 'Unknown')}")
        
        # Step 2: Post the formatted quiz to LMS
        result = post_quiz_data_to_lms(
            lms_cookies=request.lms_cookies,
            quiz_data=formatted_quiz_data
        )
        
        # Check if request was successful
        if not result.get("success"):
            raise HTTPException(
                status_code=result.get("status_code", 500),
                detail=result.get("error", "Failed to post quiz to LMS")
            )
        
        logger.info(f"Successfully posted quiz '{request.asset_name}' to LMS")
        
        # Step 3: Extract activity ID from response and link to course/module
        activity_data = result.get("data", {})
        activity_id = activity_data.get("id") or activity_data.get("activityId") or activity_data.get("_id")
        
        if not activity_id:
            logger.warning("No activity ID found in response, skipping linking step")
            return {
                "message": "Successfully posted quiz to LMS (but could not link - no activity ID returned)",
                "quiz_data": activity_data
            }
        
        logger.info(f"Linking activity {activity_id} to course {request.lms_course_id}, module {request.lms_module_id}")
        
        # Link the activity to the course and module
        link_result = link_activity_to_course(
            lms_cookies=request.lms_cookies,
            lms_course_id=request.lms_course_id,
            lms_module_id=request.lms_module_id,
            lms_activity_id=str(activity_id),
            order=request.order
        )
        
        # Check if linking was successful
        if not link_result.get("success"):
            logger.error(f"Failed to link activity: {link_result.get('error')}")
            # Return success for posting but warn about linking failure
            return {
                "message": "Quiz posted successfully but failed to link to course/module",
                "quiz_data": activity_data,
                "link_error": link_result.get("error")
            }
        
        logger.info(f"Successfully linked activity to course/module")
        
        # Return complete success response
        return {
            "message": "Successfully posted quiz to LMS and linked to course/module",
            "quiz_data": activity_data,
            "link_data": link_result.get("data", {})
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error posting quiz to LMS: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")
        
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
def get_courses_lms(request: GetCoursesLMSRequest, user_id: str=Depends(verify_token)):
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
        
        # Normalize and down-select fields: only return id and name
        raw_data = result.get("data", [])
        courses_list = []
        if isinstance(raw_data, list):
            for course in raw_data:
                if not isinstance(course, dict):
                    continue
                course_id = (
                    course.get("id") or course.get("_id") or course.get("course_id") or course.get("uuid")
                )
                course_name = course.get("name") or course.get("title") or course.get("course_title")
                if course_id is None and course_name is None:
                    # Skip malformed item
                    continue
                courses_list.append({
                    "id": course_id,
                    "name": course_name or str(course_id) or "Unnamed Course"
                })
        else:
            logger.warning("Unexpected LMS courses payload; expected list, got %s", type(raw_data))

        # Return the success response
        return {
            "message": "Successfully fetched courses from LMS",
            "data": courses_list
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching LMS courses: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")
        
#route to get all modules for a course
@router.post("/modules-lms")
def get_modules_lms(request: GetModulesLMSRequest, user_id: str=Depends(verify_token)):
    """
    Get all modules for a course from the LMS platform using authentication cookies
    """
    result = get_all_modules(request.lms_cookies, request.lms_course_id)
    
    # Filter to only include id and name fields
    if result.get("success") and "data" in result:
        filtered_data = [
            {"id": module.get("id"), "name": module.get("name")}
            for module in result["data"]
        ]
        return {
            "data": filtered_data
        }
    
    return result

#post asset to lms which will take the asset name and type and use the function to post to lms
@router.post("/post-asset-to-lms")
def post_asset_to_lms_endpoint(request: PostAssetRequest, user_id: str):
    """
    Post asset to the LMS platform based on asset type
    
    This is a generic endpoint that routes to specific asset handlers:
    - quiz: posts quiz and links to course/module
    - activity: (future implementation)
    - project: (future implementation)
    """
    try:
        # Validate input
        if not request.asset_name:
            raise HTTPException(status_code=400, detail="Asset name is required")
        if not request.asset_type:
            raise HTTPException(status_code=400, detail="Asset type is required")
        
        logger.info(f"User {user_id} posting {request.asset_type} '{request.asset_name}' to LMS")
        
        # Route to appropriate handler based on asset type
        if request.asset_type == "quiz":
            # Create PostQuizRequest from PostAssetRequest
            quiz_request = PostQuizRequest(
                lms_cookies=request.lms_cookies,
                course_id=request.course_id,
                asset_name=request.asset_name,
                lms_course_id=request.lms_course_id,
                lms_module_id=request.lms_module_id,
                order=request.order
            )
            # Call the quiz posting function
            return post_quiz_to_lms(quiz_request, user_id)
        
        # Add more asset types here in the future
        # elif request.asset_type == "activity":
        #     return post_activity_to_lms(request, user_id)
        # elif request.asset_type == "project":
        #     return post_project_to_lms(request, user_id)
        
        else:
            raise HTTPException(
                status_code=400, 
                detail=f"Asset type '{request.asset_type}' is not supported yet. Supported types: quiz"
            )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error posting asset to LMS: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")