from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel
from typing import Optional
from ..utils.storage_course import storage_service
from ..utils import openai_service
from ..utils.exceptions import handle_course_error
from firebase_admin import auth
import logging

logger = logging.getLogger(__name__)
router = APIRouter()

class CourseCreateRequest(BaseModel):
    name: str
    description: str
    year: Optional[int] = None
    level: Optional[str] = None

class CourseUpdateRequest(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    archived: Optional[bool] = None

class CourseSettingsRequest(BaseModel):
    course_level: list[str]
    study_area: str
    pedagogical_components: list[str]
    use_reference_material_only: bool
    ask_clarifying_questions: bool

def verify_token(token: str) -> str:
    try:
        decoded_token = auth.verify_id_token(token.replace("Bearer ", ""))
        return decoded_token["uid"]
    except Exception as e:
        logger.error(f"Token verification failed: {str(e)}")
        raise HTTPException(status_code=401, detail="Invalid or expired token")

@router.get("/courses")
async def get_user_courses(authorization: str = Header(...)):
    user_id = verify_token(authorization)
    try:
        courses = storage_service.get_user_courses(user_id)
        # Map 'name' to 'title' for frontend compatibility
        for course in courses:
            if 'name' in course:
                course['title'] = course['name']
        logger.info(f"Fetched courses for user {user_id}: {len(courses)} courses")
        return courses
    except Exception as e:
        logger.error(f"Error fetching courses for user {user_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error fetching courses: {str(e)}")

@router.post("/courses")
async def create_course(request: CourseCreateRequest, authorization: str = Header(...)):
    user_id = verify_token(authorization)
    try:
        # Provide default values if not supplied
        year = request.year if request.year is not None else 2024
        level = request.level if request.level is not None else "Beginner"
        course_id, assistant_id = await openai_service.create_course_and_assistant(
            request.name, request.description, year, level, user_id
        )
        logger.info(f"Created course {course_id} for user {user_id}")
        
        # Get the created course from storage
        course = storage_service.get_course(course_id, user_id)
        if not course:
            raise HTTPException(status_code=500, detail="Failed to retrieve created course")
        # Map 'name' to 'title' for frontend compatibility
        course['title'] = course['name']
        return {
            "courseId": course_id,
            "title": course["name"],
            "description": course["description"],
            "year": course["year"],
            "level": course["level"],
            "status": course["status"],
            "assistant_id": course["assistant_id"],
            "created_at": course.get("created_at"),
            "updated_at": course.get("updated_at")
        }
    except Exception as e:
        logger.error(f"Error creating course: {str(e)}")
        raise handle_course_error(e)

@router.put("/courses/{course_id}")
async def update_course(course_id: str, request: CourseUpdateRequest, authorization: str = Header(...)):
    user_id = verify_token(authorization)
    try:
        course = await openai_service.update_course(
            course_id, request.name, request.description, request.archived, user_id
        )
        logger.info(f"Updated course {course_id} for user {user_id}")
        return course
    except Exception as e:
        logger.error(f"Error updating course {course_id}: {str(e)}")
        raise handle_course_error(e)

@router.delete("/courses/{course_id}")
async def delete_course(course_id: str, authorization: str = Header(...)):
    user_id = verify_token(authorization)
    try:
        await openai_service.delete_course(course_id, user_id)
        logger.info(f"Deleted course {course_id} for user {user_id}")
        return {"message": "Course deleted successfully"}
    except Exception as e:
        logger.error(f"Error deleting course {course_id}: {str(e)}")
        raise handle_course_error(e)

@router.put("/courses/{course_id}/settings")
async def update_course_settings(course_id: str, request: CourseSettingsRequest, authorization: str = Header(...)):
    user_id = verify_token(authorization)
    try:
        course = storage_service.get_course(course_id, user_id)
        if not course:
            raise HTTPException(status_code=404, detail="Course not found")
        course["settings"] = request.dict()
        storage_service.update_course(course_id, course)
        logger.info(f"Updated settings for course {course_id}")
        return {"message": "Settings updated"}
    except Exception as e:
        logger.error(f"Error updating settings for course {course_id}: {str(e)}")
        raise handle_course_error(e)

@router.get("/courses/{course_id}/settings")
async def get_course_settings(course_id: str, authorization: str = Header(...)):
    user_id = verify_token(authorization)
    try:
        course = storage_service.get_course(course_id, user_id)
        if not course:
            raise HTTPException(status_code=404, detail="Course not found")
        return course.get("settings", {})
    except Exception as e:
        logger.error(f"Error getting settings for course {course_id}: {str(e)}")
        raise handle_course_error(e)