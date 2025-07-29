from fastapi import APIRouter, Header, HTTPException, Depends
from pydantic import BaseModel
from typing import Optional
from ..services.storage_course import storage_service
from ..services import openai_service
from ..utils.exceptions import handle_course_error
from firebase_admin import auth
import logging
from ..utils.verify_token import verify_token
from ..services.mongo import get_courses_by_user_id
from ..routes.resources import create_course_description_file

logger = logging.getLogger(__name__)
router = APIRouter()

class CourseCreateRequest(BaseModel):
    name: str
    description: str

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

@router.get("/courses?user_id={user_id}")
def get_courses_for_user(user_id: str = Depends(verify_token)):
    try:
        courses = get_courses_by_user_id(user_id)
        logger.info(f"Fetched courses for user {user_id}: {len(courses)} courses")
        return courses
    except Exception as e:
        logger.error(f"Error fetching courses for user {user_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error fetching courses: {str(e)}")

@router.post("/courses")
def create_course(request: CourseCreateRequest, user_id: str = Depends(verify_token)):
    try:
        assistant_id = openai_service.create_assistant()
        course_id = create_course({"name": request.name, "description": request.description, "user_id": user_id, "assistant_id": assistant_id})
        create_course_description_file(course_id, user_id)
        return {"courseId": course_id}
    except Exception as e:
        logger.error(f"Error creating course: {str(e)}")
        raise handle_course_error(e)

@router.put("/courses/{course_id}")
async def update_course(course_id: str, request: CourseUpdateRequest, user_id: str = Depends(verify_token)):
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
async def delete_course(course_id: str, user_id: str = Depends(verify_token)):
    try:
        await openai_service.delete_course(course_id, user_id)
        logger.info(f"Deleted course {course_id} for user {user_id}")
        return {"message": "Course deleted successfully"}
    except Exception as e:
        logger.error(f"Error deleting course {course_id}: {str(e)}")
        raise handle_course_error(e)

@router.put("/courses/{course_id}/settings")
async def update_course_settings(course_id: str, request: CourseSettingsRequest, user_id: str = Depends(verify_token)):
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
async def get_course_settings(course_id: str, user_id: str = Depends(verify_token)):
    try:
        course = storage_service.get_course(course_id, user_id)
        if not course:
            raise HTTPException(status_code=404, detail="Course not found")
        return course.get("settings", {})
    except Exception as e:
        logger.error(f"Error getting settings for course {course_id}: {str(e)}")
        raise handle_course_error(e)