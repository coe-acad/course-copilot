from fastapi import APIRouter, HTTPException, UploadFile, File, Header, Query, Depends
from pydantic import BaseModel
from typing import List, Optional
import logging
import os
from pathlib import Path
from ..services import openai_service
from ..services.mongo import get_course, get_resources_by_course_id, create_resource
from ..services.openai_service import create_file, connect_file_to_vector_store
from ..utils.exceptions import handle_course_error
from ..utils.course_pdf_utils import generate_course_pdf
from ..utils.verify_token import verify_token

logger = logging.getLogger(__name__)
router = APIRouter()

# Inline models
class ResourceResponse(BaseModel):
    fileId: str
    fileName: str
    status: str
    checkedOutBy: Optional[str] = None
    url: Optional[str] = None

class ResourceListResponse(BaseModel):
    courseId: str
    resources: List[ResourceResponse]

class DeleteResponse(BaseModel):
    message: str

class ResourceCreateResponse(BaseModel):
    message: str

def check_course_exists(course_id: str):
    # check if the course exists
    # if it exists, return True
    # if it doesn't exist, raise error
    course = get_course(course_id)
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")
    return True

def create_course_description_file(course_id: str, user_id: str):
    """
    Create a course description file using PDF utility and add it to vector store
    """
    try:
        # Get course information from MongoDB
        course = get_course(course_id)
        if not course:
            logger.error(f"Course not found: {course_id}")
            return None
        
        # Generate PDF using the utility
        pdf_path = generate_course_pdf(course_id, user_id)
        if not pdf_path or not os.path.exists(pdf_path):
            logger.error(f"Failed to generate PDF for course {course_id}")
            return None
        
        # Get relative path starting from 'local_storage'
        pdf_relative_path = Path(pdf_path).as_posix().split("local_storage", 1)[-1]
        pdf_relative_path = "local_storage" + pdf_relative_path
        
        #name of the pdf should be the title
        title = pdf_relative_path.split("/")[-1].split(".")[0]

        # Create resource in MongoDB
        create_resource(course_id, title, "checked-out", pdf_relative_path)

        # Upload the PDF to OpenAI for vector store
        openai_file_id = create_file(pdf_relative_path)
        
        # Get vector store for the course
        assistant_id = course.get('assistant_id')
        if not assistant_id:
            logger.error(f"No assistant ID found for course {course_id}")
            return None
        
        # Check if vector store exists, if not create one
        vector_store_id = course.get('vector_store_id')
        if not vector_store_id:
            logger.error(f"No vector_store_id found for course {course_id}")
            return None
        
        # Connect file to vector store
        batch_id = connect_file_to_vector_store(vector_store_id, openai_file_id)
        
        logger.info(f"Created course description PDF for {course_id}: {openai_file_id}")
        logger.info(f"Connected to vector store {vector_store_id}, batch: {batch_id}")
        
        return {
            "file_id": openai_file_id,
            "vector_store_id": vector_store_id,
            "batch_id": batch_id,
            "pdf_path": pdf_path
        }
    except Exception as e:
        logger.error(f"Error creating course description file for {course_id}: {str(e)}")
        return None

# Keep this route, we add the file to the vector store attached to the Assistant
@router.post("/courses/{course_id}/resources", response_model=ResourceCreateResponse)
def upload_resources(user_id: str, course_id: str, files: List[UploadFile] = File(...), thread_id: str = Query(None)):
    try:
        check_course_exists(course_id)
        # if course exists, get the assistant id and vector store id from the course
        course = get_course(course_id)
        openai_service.upload_resources(course_id, course["assistant_id"], course["vector_store_id"], files, user_id)
        return ResourceCreateResponse(message="Resources uploaded successfully")
    except Exception as e:
        logger.error(f"Error uploading resources: {str(e)}")
        raise handle_course_error(e)

@router.get("/courses/{course_id}/resources", response_model=ResourceListResponse)
def list_resources(user_id: str, course_id: str):
    try:
        check_course_exists(course_id)
        resources = get_resources_by_course_id(course_id)
        return ResourceListResponse(
            courseId=course_id,
            resources=[ResourceResponse(
                fileId=data.get("fileId", ""),
                fileName=data["title"],
                url=data.get("url")
            ) for data in resources]
        )
    except Exception as e:
        logger.error(f"Error listing resources: {str(e)}")
        raise handle_course_error(e)

@router.delete("/courses/{course_id}/resources/{file_id}", response_model=DeleteResponse)
def delete_resource(user_id: str,course_id: str, file_id: str):
    try:
        check_course_exists(course_id)
        result = openai_service.delete_single_resource(course_id, file_id, user_id)
        return DeleteResponse(message=result["message"])
    except Exception as e:
        logger.error(f"Error deleting resource: {str(e)}")
        raise handle_course_error(e)