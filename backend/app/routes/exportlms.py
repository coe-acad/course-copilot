from fastapi import HTTPException, Depends
from pydantic import BaseModel
from ..services.mongo import get_course, get_asset_by_course_id_and_asset_name
from ..utils.data_formating import format_quiz_content
from ..utils.verify_token import verify_token
from ..utils.lms_curl import login_to_lms, get_lms_courses
from ..config.settings import settings
from fastapi import APIRouter
import logging

logger = logging.getLogger(__name__)
router = APIRouter()

class ExportLMSRequest(BaseModel):
    asset_type: list[str]
    asset_names: list[str]

class LoginLMSRequest(BaseModel):
    email: str
    password: str

class GetCoursesLMSRequest(BaseModel):
    lms_token: str

#route to login to the lms
@router.post("/login-lms")
def login_lms(request: LoginLMSRequest, user_id: str = Depends(verify_token)):
    """
    Login to the LMS platform with user credentials
    
    DEVELOPMENT MODE: If LMS_BASE_URL is not configured, returns a mock success response
    for frontend testing purposes.
    """
    try:
        # Validate input
        if not request.email or not request.password:
            raise HTTPException(status_code=400, detail="Email and password are required")
        
        # Check if LMS_BASE_URL is configured in settings
        if not settings.LMS_BASE_URL:
            # DEVELOPMENT MODE: Return mock response for frontend testing
            logger.warning(f"LMS_BASE_URL not configured. Returning mock response for user {user_id}")
            return {
                "message": "Successfully logged into LMS (MOCK MODE - No LMS_BASE_URL configured)",
                "data": {
                    "token": "mock_lms_token_for_testing_" + user_id[:8],
                    "user": {
                        "id": "mock_user_id",
                        "email": request.email,
                        "name": "Mock User"
                    }
                }
            }
        
        # Call the LMS login utility function
        result = login_to_lms(request.email, request.password)
        
        # Check if login was successful
        if not result.get("success"):
            raise HTTPException(
                status_code=result.get("status_code", 401),
                detail=result.get("error", "LMS authentication failed")
            )
        
        logger.info(f"User {user_id} successfully logged into LMS")
        
        # Return the success response
        return {
            "message": "Successfully logged into LMS",
            "data": result.get("data", {})
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
    Get courses from the LMS platform using the LMS authentication token
    """
    try:
        # Validate input
        if not request.lms_token:
            raise HTTPException(status_code=400, detail="LMS token is required")
        
        # Check if LMS_BASE_URL is configured in settings
        if not settings.LMS_BASE_URL:
            raise HTTPException(status_code=500, detail="LMS base URL is not configured in server settings")
        
        # Log token info for debugging (first 20 chars only for security)
        logger.info(f"Using LMS token: {request.lms_token[:20]}... (length: {len(request.lms_token)})")
        
        # Call the LMS courses utility function
        result = get_lms_courses(request.lms_token)
        
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
        
@router.post("/courses/{course_id}/export-lms")
def export_lms(course_id: str, request: ExportLMSRequest, user_id: str = Depends(verify_token)):
    """
    Export specific assets by name and type to LMS format
    
    This endpoint currently formats assets for export but does not push them to the LMS.
    
    Future Enhancement:
    ---------------------
    To actually push content to LMS platform, create a new endpoint:
    
    @router.post("/courses/{course_id}/push-to-lms")
    def push_to_lms(
        course_id: str,
        request: ExportLMSRequest,
        lms_token: str,  # From frontend via header X-LMS-Token
        user_id: str = Depends(verify_token)
    ):
        # 1. Get formatted assets using current export_lms logic
        # 2. Use lms_token to authenticate with LMS platform
        # 3. Call LMS API endpoint (e.g., POST {LMS_BASE_URL}/api/v1/courses)
        # 4. Handle LMS-specific response format
        # 5. Return success with LMS course/content IDs
        
        Example LMS API call:
        ---------------------
        import requests
        
        headers = {
            'Authorization': f'Bearer {lms_token}',
            'Content-Type': 'application/json'
        }
        
        payload = {
            'sprint_name': course_name,
            'sprint_description': course_description,
            'assets': formatted_assets
        }
        
        lms_response = requests.post(
            f'{settings.LMS_BASE_URL}/api/v1/sprints',
            json=payload,
            headers=headers,
            timeout=30
        )
        
        if lms_response.status_code == 201:
            return {
                'success': True,
                'lms_course_id': lms_response.json()['id'],
                'message': 'Successfully exported to LMS'
            }
    """
    try:
        # Get course data
        course_data = get_course(course_id)
        if not course_data:
            raise HTTPException(status_code=404, detail="Course not found")
        
        course_name = course_data.get("name", "")
        course_description = course_data.get("description", "")

        formatted_assets = []
        
        asset_types = request.asset_type
        # Process each asset name sent from frontend
        for asset_name in request.asset_names:
            # Get the specific asset by name
            asset = get_asset_by_course_id_and_asset_name(course_id, asset_name)
            
            if not asset:
                logger.warning(f"Asset '{asset_name}' not found for course {course_id}")
                continue
            
            # Get the actual asset type from the database
            asset_type = asset.get("asset_type", "")
            asset_content = asset.get("asset_content", "")
            
            if not asset_content:
                logger.warning(f"Asset '{asset_name}' has no content, skipping")
                continue
            
            # Check if this asset type was requested
            if asset_type not in asset_types:
                logger.warning(f"Asset '{asset_name}' has type '{asset_type}' which was not requested")
                continue
            
            # Format based on asset type
            if asset_type == "quiz":
                # Format quiz using structured output
                formatted_data = format_quiz_content(asset_content, course_id, user_id, asset_name, asset_type)
                formatted_assets.append({
                    "asset_name": asset_name,
                    "asset_type": asset_type,
                    "content": formatted_data
                })
            else:
                # Only quiz assets can be exported to LMS
                raise HTTPException(
                    status_code=400, 
                    detail=f"Cannot export '{asset_name}' - only quiz assets can be exported to LMS. Asset type '{asset_type}' is not supported."
                )
        
        logger.info(f"Exported {len(formatted_assets)} assets for course {course_id}")
        
        # Return course data along with formatted assets
        return {
            "course_id": course_id,
            "sprint_name": course_name,
            "sprint_description": course_description,
            "total_assets": len(formatted_assets),
            "assets": formatted_assets
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error exporting assets: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
