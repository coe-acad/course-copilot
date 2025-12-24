from fastapi import APIRouter, HTTPException, UploadFile, File, Depends
from pydantic import BaseModel, HttpUrl
from typing import List
import logging
import os
import io
from pathlib import Path
from ..services import openai_service
from ..services.mongo import get_course, get_resources_by_course_id, create_resource, get_resource_by_course_id_and_resource_name, delete_resource as delete_resource_in_db
from ..services.openai_service import create_file, connect_file_to_vector_store, discover_resources
from ..utils.course_pdf_utils import generate_course_pdf
from ..utils.verify_token import verify_token
from fastapi.responses import FileResponse

logger = logging.getLogger(__name__)
router = APIRouter()

# Inline models
class ResourceResponse(BaseModel):
    resourceName: str

class ResourceListResponse(BaseModel):
    resources: List[ResourceResponse]

class DeleteResponse(BaseModel):
    message: str

class ResourceCreateResponse(BaseModel):
    message: str

class ResourceViewResponse(BaseModel):
    resource_name: str
    content: str

class Resource(BaseModel):
    title: str
    url: str  # or HttpUrl for validation
    description: str

class DiscoverResourcesResponse(BaseModel):
    resources: List[Resource]  # Changed from str to List[Resource]

class DiscoverResourcesRequest(BaseModel):
    query: str

def check_course_exists(course_id: str):
    # check if the course exists
    # if it exists, return True
    # if it doesn't exist, raise error
    course = get_course(course_id)
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")
    return True

def create_course_description_file(course_id: str, user_id: str = Depends(verify_token)):
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
        pdf_path = generate_course_pdf(course_id)
        if not pdf_path or not os.path.exists(pdf_path):
            logger.error(f"Failed to generate PDF for course {course_id}")
            return None
        
        # Get relative path starting from 'local_storage'
        pdf_relative_path = Path(pdf_path).as_posix().split("local_storage", 1)[-1]
        pdf_relative_path = "local_storage" + pdf_relative_path
        
        #name of the pdf should be the title
        resource_name = os.path.basename(pdf_path)

        # Create resource in MongoDB
        create_resource(course_id, resource_name)

        # Upload the PDF to OpenAI (open as binary stream)
        with open(pdf_path, "rb") as f:
            content = f.read()
            file_obj = io.BytesIO(content)
            file_obj.name = resource_name  # ✅ Required for OpenAI
            openai_file_id = create_file(file_obj)
        
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

# Keep this route, we add the file to the vector store attached 
@router.post("/courses/{course_id}/resources", response_model=ResourceCreateResponse)
def upload_resources(course_id: str, files: List[UploadFile] = File(...), user_id: str = Depends(verify_token)):
    try:
        check_course_exists(course_id)
        # if course exists, get the vector store id from the course
        course = get_course(course_id)
        vector_store_id = course.get('vector_store_id')
        if not vector_store_id:
            logger.error(f"No vector_store_id found for course {course_id}")
            return None

        # Build a set of existing resource names for collision handling
        existing_resources = get_resources_by_course_id(course_id) or []
        existing_names = set([r.get("resource_name") for r in existing_resources if r.get("resource_name")])

        def ensure_unique_name(filename: str, used: set[str]) -> str:
            base, ext = os.path.splitext(filename or "")
            if not base:
                base = "resource"
            candidate = f"{base}{ext}"
            n = 1
            while candidate in used:
                candidate = f"{base} ({n}){ext}"
                n += 1
            used.add(candidate)
            return candidate

        # Rename duplicates in-place so downstream uses the new name
        for f in files:
            f.filename = ensure_unique_name(f.filename, existing_names)

        # Upload files to vector store (this uses f.filename for the OpenAI file name)
        openai_service.upload_resources(user_id, course_id, vector_store_id, files)

        # Create resource records with the possibly renamed filenames
        for file in files:
            create_resource(course_id, file.filename)

        return ResourceCreateResponse(message="Resources uploaded successfully")
    except Exception as e:
        logger.error(f"Error uploading resources: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/courses/{course_id}/resources", response_model=ResourceListResponse) 
def list_resources(course_id: str, user_id: str = Depends(verify_token)):
    try:
        check_course_exists(course_id)
        resources = get_resources_by_course_id(course_id)
        resource_list = [
            ResourceResponse(resourceName=data.get("resource_name", "Unknown Name"))
            for data in resources
        ]
        return ResourceListResponse(resources=resource_list)
    except Exception as e:
        logger.error(f"Error listing resources: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/courses/{course_id}/resources/{resource_name}", response_model=DeleteResponse)
def delete_resource(course_id: str, resource_name: str, user_id: str = Depends(verify_token)):
    try:    
        check_course_exists(course_id)
        delete_resource_in_db(course_id, resource_name)
        return DeleteResponse(message="Resource deleted successfully")
    except Exception as e:
        logger.error(f"Error deleting resource: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/courses/{course_id}/resources/{resource_name}/content", response_model=ResourceViewResponse)
def get_resource_content(course_id: str, resource_name: str, user_id: str = Depends(verify_token)):
    """Get resource content for viewing"""
    try:
        # 1. Check course exists
        check_course_exists(course_id)
        
        # 2. Get resource from database
        resource = get_resource_by_course_id_and_resource_name(course_id, resource_name)
        print(resource)
        print(resource_name)
        print(resource["content"])
        if not resource:
            raise HTTPException(status_code=404, detail="Uploaded resources can't be viewed")
        
        # 3. Check if content exists
        content = resource.get("content")
        logger.info(f"Content found: {content is not None}, Length: {len(content) if content else 0}")
        if not content:
            raise HTTPException(status_code=404, detail="Uploaded resources can't be viewed")
        
        # 4. Return resource content
        return ResourceViewResponse(resource_name=resource_name, content=content)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting resource content: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/courses/{course_id}/resources/discover", response_model=DiscoverResourcesResponse)
def discover_resources_endpoint(course_id: str, request: DiscoverResourcesRequest, user_id: str = Depends(verify_token)):
    try:
        check_course_exists(course_id)
        resources_list = openai_service.discover_resources(request.query)  # Now returns list
        return DiscoverResourcesResponse(resources=resources_list)  # Pass list directly
    except ValueError as e:
        logger.error(f"Error parsing resources response: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to parse AI response")
    except Exception as e:
        logger.error(f"Error discovering resources: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

# Add the checked resources to the knowledge base 
class AddDiscoveredResourcesRequest(BaseModel):
    resources: List[Resource]  # List of selected resources with title, url, description

@router.post("/courses/{course_id}/resources/add-discovered", response_model=ResourceCreateResponse)
def add_discovered_resources(
    course_id: str, 
    request: AddDiscoveredResourcesRequest, 
    user_id: str = Depends(verify_token)
):
    """
    Add selected discovered resources to the knowledge base.
    Creates a text file for each resource containing the URL and adds it to the vector store.
    """
    try:
        check_course_exists(course_id)
        
        if not request.resources or len(request.resources) == 0:
            raise HTTPException(status_code=400, detail="No resources provided")
        
        # Get course and vector store
        course = get_course(course_id)
        vector_store_id = course.get('vector_store_id')
        if not vector_store_id:
            raise HTTPException(status_code=404, detail="Vector store not found for this course")
        
        # Get existing resources to avoid duplicates
        existing_resources = get_resources_by_course_id(course_id) or []
        existing_names = set([r.get("resource_name") for r in existing_resources if r.get("resource_name")])
        
        added_count = 0
        skipped_count = 0
        
        for resource in request.resources:
            try:
                # Create a unique resource name based on title
                base_name = f"Link: {resource.title}"
                resource_name = base_name
                counter = 1
                
                # Ensure unique name
                while resource_name in existing_names:
                    resource_name = f"{base_name} ({counter})"
                    counter += 1
                
                existing_names.add(resource_name)
                
                # Create text content with URL and description
                content = f"{resource.title}\n\n{resource.url}\n\n{resource.description}"
                
                # Create a text file in memory
                file_obj = io.BytesIO(content.encode('utf-8'))
                file_obj.name = f"{resource_name}.txt"
                
                # Upload to OpenAI
                openai_file_id = create_file(file_obj)
                
                # Connect to vector store
                connect_file_to_vector_store(vector_store_id, openai_file_id)
                
                # Create resource record in database
                create_resource(course_id, resource_name)
                
                added_count += 1
                logger.info(f"Added discovered resource: {resource_name}")
                
            except Exception as e:
                logger.error(f"Error adding resource '{resource.title}': {str(e)}")
                skipped_count += 1
                continue
        
        if added_count == 0:
            raise HTTPException(status_code=500, detail="Failed to add any resources")
        
        message = f"Successfully added {added_count} resource(s) to knowledge base"
        if skipped_count > 0:
            message += f" ({skipped_count} skipped due to errors)"
        
        return ResourceCreateResponse(message=message)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error adding discovered resources: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e)) 


# @router.get("/courses/{course_id}/resources/{resource_name}/download")
# def download_resource(course_id: str, resource_name: str, user_id: str = Depends(verify_token)):
#     check_course_exists(course_id)
#     resources = get_resources_by_course_id(course_id)
#     if not resources:
#         raise HTTPException(status_code=404, detail="Resource not found")
#     resource = next((r for r in resources if r.get("resource_name") == resource_name), None)
#     if not resource:
#         raise HTTPException(status_code=404, detail="Resource not found")
#     path_to_file = resource.get("file_path")
#     if not path_to_file:
#         raise HTTPException(status_code=404, detail="File path not found")
#     return FileResponse(path_to_file, filename=resource_name, media_type='application/octet-stream', headers={"Content-Disposition": f"attachment; filename={resource_name}"})