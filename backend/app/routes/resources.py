from fastapi import APIRouter, HTTPException, UploadFile, File, Header, Query, Depends
from pydantic import BaseModel
from typing import List, Optional
from ..services import openai_service
from ..services.mongo import get_course, update_course, get_resources_by_course_id, create_resource
from ..services.storage_course import storage_service
from ..services.openai_service import create_file, create_vector_store, connect_file_to_vector_store
from ..services.mongo import get_course, update_course
from ..utils.exceptions import handle_course_error
from ..utils.course_pdf_utils import generate_course_pdf
from ..services.openai_service import connect_file_to_vector_store
import logging
from firebase_admin import auth as admin_auth
from ..utils.verify_token import verify_token
import os
from pathlib import Path

logger = logging.getLogger(__name__)
router = APIRouter()

# Inline models
class ResourceResponse(BaseModel):
    fileId: str
    fileName: str
    status: str
    checkedOutBy: Optional[str] = None
    url: Optional[str] = None

class ResourceCheckoutRequest(BaseModel):
    userId: str

class ResourceListResponse(BaseModel):
    courseId: str
    resources: List[ResourceResponse]

class DeleteResponse(BaseModel):
    message: str

class ResourceCreateRequest(BaseModel):
    title: str
    url: str

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

@router.post("/courses/{course_id}/resources", response_model=ResourceListResponse)
async def upload_resources(course_id: str, files: List[UploadFile] = File(...), user_id: str = Depends(verify_token), thread_id: str = Query(None)):
    try:
        course = get_course(course_id, user_id)
        if not course:
            raise HTTPException(status_code=404, detail="Course not found")
        resources = await openai_service.upload_resources(course_id, course["assistant_id"], files, user_id, thread_id=thread_id)
        openai_service.add_files_to_assistant_vector_store(course_id, user_id, resources)
        return ResourceListResponse(courseId=course_id, resources=resources)
    except Exception as e:
        logger.error(f"Error uploading resources: {str(e)}")
        raise handle_course_error(e)

@router.post("/courses/{course_id}/resources/url", response_model=ResourceResponse)
async def create_url_resource(course_id: str, request: ResourceCreateRequest, user_id: str = Depends(verify_token), thread_id: str = Query(None)):
    try:
        resource = await openai_service.create_resource(course_id, request.title, request.url, user_id, thread_id=thread_id)
        return resource
    except Exception as e:
        logger.error(f"Error creating URL resource: {str(e)}")
        raise handle_course_error(e)

@router.get("/courses/{course_id}/resources", response_model=ResourceListResponse)
async def list_resources(course_id: str, user_id: str = Depends(verify_token)):
    try:
        resources = get_resources_by_course_id(course_id)
        
        return ResourceListResponse(
            courseId=course_id,
            resources=[ResourceResponse(
                fileId=data.get("fileId", ""),
                fileName=data["title"],
                status=data["status"],
                # checkedOutBy=data["checkedOutBy"],
                url=data.get("url")
            ) for data in resources]
        )
    except Exception as e:
        logger.error(f"Error listing resources: {str(e)}")
        raise handle_course_error(e)

@router.put("/courses/{course_id}/resources/{file_id}/checkout", response_model=ResourceResponse)
async def checkout_resource(course_id: str, file_id: str, request: ResourceCheckoutRequest, user_id: str = Depends(verify_token)):
    try:
        course = storage_service.get_course(course_id, user_id)
        if not course:
            raise HTTPException(status_code=404, detail="Course not found")
        resource = await openai_service.checkout_resource(course_id, course["assistant_id"], file_id, user_id)
        return resource
    except Exception as e:
        logger.error(f"Error checking out resource: {str(e)}")
        raise handle_course_error(e)

@router.put("/courses/{course_id}/resources/{file_id}/checkin", response_model=ResourceResponse)
async def checkin_resource(course_id: str, file_id: str, user_id: str = Depends(verify_token)):
    try:
        course = storage_service.get_course(course_id, user_id)
        if not course:
            raise HTTPException(status_code=404, detail="Course not found")
        resource = await openai_service.checkin_resource(course_id, course["assistant_id"], file_id, user_id)
        return resource
    except Exception as e:
        logger.error(f"Error checking in resource: {str(e)}")
        raise handle_course_error(e)

@router.delete("/courses/{course_id}/resources", response_model=DeleteResponse)
async def delete_resources(course_id: str, user_id: str = Depends(verify_token)):
    try:
        course = storage_service.get_course(course_id, user_id)
        if not course:
            raise HTTPException(status_code=404, detail="Course not found")
        await openai_service.delete_resources(course_id, course["assistant_id"], user_id)
        return DeleteResponse(message="deleted")
    except Exception as e:
        logger.error(f"Error deleting resources: {str(e)}")
        raise handle_course_error(e)

@router.delete("/courses/{course_id}/resources/{file_id}", response_model=DeleteResponse)
async def delete_resource(course_id: str, file_id: str, user_id: str = Depends(verify_token)):
    try:
        result = await openai_service.delete_single_resource(course_id, file_id, user_id)
        return DeleteResponse(message=result["message"])
    except Exception as e:
        logger.error(f"Error deleting resource: {str(e)}")
        raise handle_course_error(e)

@router.post("/courses/{course_id}/assistant/fix-files")
async def fix_incompatible_files(course_id: str, user_id: str = Depends(verify_token)):
    """
    Fix incompatible files by re-uploading them with proper extensions.
    """
    try:
        handled_file_ids = openai_service._handle_missing_files(course_id, user_id)
        return {"message": f"Handled {len(handled_file_ids)} files", "handled_file_ids": handled_file_ids}
    except Exception as e:
        logger.error(f"Error handling files: {str(e)}")
        raise handle_course_error(e)

@router.post("/courses/{course_id}/assistant/resources")
async def add_all_files_to_assistant_route(course_id: str, user_id: str = Depends(verify_token), thread_id: str = Query(...)):
    """
    Add all resources (regardless of status) to the assistant's file search (vector store).
    """
    try:
        # Fetch all resources for the course and thread
        course_resources = storage_service.get_resources(course_id, user_id=user_id)
        asset_resources = storage_service.get_resources(course_id, thread_id=thread_id, user_id=user_id)
        all_resources = course_resources + asset_resources
        result = openai_service.add_files_to_assistant_vector_store(course_id, user_id, all_resources)
        return result
    except Exception as e:
        logger.error(f"Error adding files to assistant: {str(e)}")
        raise handle_course_error(e)

@router.get("/courses/{course_id}/brainstorm/{thread_id}/messages", response_model=ResourceListResponse)
async def list_brainstorm_messages(course_id: str, thread_id: str, user_id: str = Depends(verify_token)):
    try:
        resources = storage_service.get_brainstorm_messages(course_id, thread_id, user_id)
        return ResourceListResponse(
            courseId=course_id,
            resources=[ResourceResponse(
                fileId=data.get("fileId", ""),
                fileName=data.get("title", ""),
                status=data.get("status", ""),
                checkedOutBy=data.get("checkedOutBy", None),
                url=data.get("url", None)
            ) for data in resources]
        )
    except Exception as e:
        logger.error(f"Error listing brainstorm messages: {str(e)}")
        raise handle_course_error(e)

@router.get("/courses/{course_id}/brainstorm/{thread_id}/resources", response_model=ResourceListResponse)
async def list_brainstorm_resources(course_id: str, thread_id: str, user_id: str = Depends(verify_token)):
    try:
        resources = storage_service.get_brainstorm_resources(course_id, thread_id, user_id)
        return ResourceListResponse(
            courseId=course_id,
            resources=[ResourceResponse(
                fileId=data["fileId"],
                fileName=data["title"],
                status=data["status"],
                checkedOutBy=data["checkedOutBy"],
                url=data.get("url")
            ) for data in resources]
        )
    except Exception as e:
        logger.error(f"Error listing brainstorm resources: {str(e)}")
        raise handle_course_error(e)