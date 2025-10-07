from fastapi import HTTPException, Depends
from pydantic import BaseModel
from ..services.mongo import get_course, get_asset_by_course_id_and_asset_name
from ..utils.data_formating import format_quiz_content
from ..utils.verify_token import verify_token
from ..utils.lms_curl import login_to_lms
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

#route to login to the lms
@router.post("/login-lms")
def login_lms(request: LoginLMSRequest, user_id: str):
    """
    Login to the LMS platform with user credentials
    """
    try:
        # Validate input
        if not request.email or not request.password:
            raise HTTPException(status_code=400, detail="Email and password are required")
        
        # Check if LMS_BASE_URL is configured in settings
        if not settings.LMS_BASE_URL:
            raise HTTPException(status_code=500, detail="LMS base URL is not configured in server settings")
        
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
        
@router.post("/courses/{course_id}/export-lms")
def export_lms(course_id: str, request: ExportLMSRequest, user_id: str = Depends(verify_token)):
    """
    Export specific assets by name and type to LMS format
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
