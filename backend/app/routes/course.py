from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from ..services import openai_service
import logging
from ..utils.verify_token import verify_token
from ..services.mongo import get_course, get_courses_by_user_id, create_course as create_course_in_db, update_course, delete_course as delete_course_in_db, create_evaluation
from ..routes.resources import create_course_description_file
from app.utils.openai_client import client
from ..services.openai_service import create_vector_store, create_evaluation_assistant_and_vector_store, course_description
from uuid import uuid4

logger = logging.getLogger(__name__)
router = APIRouter()

class CourseCreateRequest(BaseModel):
    name: str
    description: str

class CourseSettingsRequest(BaseModel):
    course_level: list[str]
    study_area: list[str]   
    pedagogical_components: list[str]
    ask_clarifying_questions: bool

class CourseResponse(BaseModel):
    name: str
    id: str

class CourseDescriptionRequest(BaseModel):
    course_name: str
    description: str

@router.get("/courses", response_model=list[CourseResponse])
def get_courses(user_id: str = Depends(verify_token)):
    logger.info(f"Fetching courses for user {user_id}")
    try:
        courses = get_courses_by_user_id(user_id)
        logger.info(f"Fetched courses for user {user_id}: {len(courses)} courses")
        return [CourseResponse(name = course["name"], id = course["_id"]) for course in courses]
    except Exception as e:
        logger.error(f"Error fetching courses for user {user_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error fetching courses: {str(e)}")

@router.post("/courses", response_model=CourseResponse)
def create_course(request: CourseCreateRequest, user_id: str = Depends(verify_token)):
    try:
        assistant_id = openai_service.create_assistant()
        vector_store_id = create_vector_store(assistant_id)
        # Link the vector store to the assistant
        client.beta.assistants.update(
            assistant_id,
            tool_resources={
                "file_search": {
                    "vector_store_ids": [vector_store_id]
                }
            }
        )
        # Save the course with the vector store ID
        course_id = create_course_in_db({
            "name": request.name,
            "description": request.description,
            "user_id": user_id,
            "assistant_id": assistant_id,
            "vector_store_id": vector_store_id
        })
        create_course_description_file(course_id, user_id)
        
        # Create a default evaluation scheme for the course
        # Create evaluation assistant and vector store for the default scheme
        # eval_id = str(uuid4())
        # eval_info = create_evaluation_assistant_and_vector_store(eval_id)
        # eval_assistant_id = eval_info[0]
        # eval_vector_store_id = eval_info[1]
        
        # Create default evaluation scheme
        # create_evaluation(
        #     course_id=course_id,
        #     scheme_name=f"{request.name}_Default_Scheme",
        #     scheme_description=f"Default evaluation scheme for {request.name}",
        #     evaluation_assistant_id=eval_assistant_id,
        #     vector_store_id=eval_vector_store_id,
        #     mark_scheme_file_id=""  # Will be set when mark scheme is uploaded
        # )
        
        return CourseResponse(name = request.name, id = course_id)
    except Exception as e:
        logger.error(f"Error creating course: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/courses/{course_id}")
async def delete_course(course_id: str, user_id: str = Depends(verify_token)):
    delete_course_in_db(course_id)
    return {"message": "Course deleted successfully"}

@router.put("/courses/{course_id}/settings")
def save_course_settings(course_id: str, request: CourseSettingsRequest, user_id: str = Depends(verify_token)):
    try:
        course = get_course(course_id)
        if not course:
            # TODO: This error does not propagate to the except block below. It prints empty detail. Check why and fix.
            raise HTTPException(status_code=404, detail="Course not found")
        # Replace existing settings with new ones. If not present, add them.
        print(request.dict())
        course["settings"] = request.dict()
        # Update the course in the database
        update_course(course_id, course)
        logger.info(f"Updated settings for course {course_id}")
        return {"message": "Settings updated"}

    except Exception as e:
        logger.error(f"Error updating settings for course {course_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/courses/{course_id}/settings")
def get_course_settings(course_id: str, user_id: str = Depends(verify_token)):
    try:
        course = get_course(course_id)
        if not course:
            raise HTTPException(status_code=404, detail="Course not found")
        return course.get("settings", {})
    except Exception as e:
        logger.error(f"Error getting settings for course {course_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.put("/courses/description", response_model=str)
def update_course_description(request: CourseDescriptionRequest, user_id: str = Depends(verify_token)):
    try:
        logger.info(f"Generating course description for user {user_id}, course: {request.course_name}")
        description = course_description(request.description, request.course_name)
        logger.info(f"Successfully generated description: {description[:100]}...")
        return description
    except Exception as e:
        logger.error(f"Error updating course description: {str(e)}")
        logger.error(f"Request data: course_name={request.course_name}, description={request.description}")
        raise HTTPException(status_code=500, detail=f"Failed to generate course description: {str(e)}")