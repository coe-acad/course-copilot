from fastapi import APIRouter, HTTPException, UploadFile, File, Depends
from pydantic import BaseModel, HttpUrl
from typing import List
import logging
import os
import io
import base64
import mimetypes
from pathlib import Path
from ..services import openai_service
from ..services.mongo import (
    get_course,
    get_resources_by_course_id,
    create_resource,
    get_resource_by_course_id_and_resource_name,
    delete_resource as delete_resource_in_db,
    save_resource_image,
)
from ..services.openai_service import create_file, connect_file_to_vector_store, discover_resources
from ..services.mongo import get_course, get_resources_by_course_id, create_resource, get_resource_by_course_id_and_resource_name, delete_resource as delete_resource_in_db, save_resource_image, get_resource_image_by_id, delete_resource_image, save_resource_pdf, get_resource_pdf, delete_resource_pdf
from ..utils.course_pdf_utils import generate_course_pdf
from ..utils.verify_token import verify_token
from fastapi.responses import FileResponse
from PyPDF2 import PdfReader

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

def create_course_description_file(course_id: str, user_id: str):
    """Create the course-description resource, stored entirely in Mongo.

    The description text is the resource content (used for prompt injection at
    generation time) and the rendered PDF bytes are stored alongside it so the
    resource can be viewed as a real PDF and sent directly to the model.
    """
    try:
        # Get course information from MongoDB
        course = get_course(course_id)
        if not course:
            logger.error(f"Course not found: {course_id}")
            return None

        # Generate the PDF using the utility, store its bytes in Mongo, and drop
        # the local file — Mongo is the only storage.
        pdf_path = generate_course_pdf(course_id)
        if not pdf_path or not os.path.exists(pdf_path):
            logger.error(f"Failed to generate PDF for course {course_id}")
            return None
        resource_name = os.path.basename(pdf_path)
        with open(pdf_path, "rb") as f:
            pdf_bytes = f.read()
        os.remove(pdf_path)

        course_description = course.get('description', 'No description available')
        create_resource(course_id, resource_name, course_description)
        try:
            pages = len(PdfReader(io.BytesIO(pdf_bytes)).pages)
        except Exception:
            pages = 0
        save_resource_pdf(course_id, resource_name, pdf_bytes, len(pdf_bytes), pages)

        logger.info(f"Created course description resource '{resource_name}' for {course_id} in Mongo")
        return {"resource_name": resource_name}
    except Exception as e:
        logger.error(f"Error creating course description file for {course_id}: {str(e)}")
        return None

_IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp", ".tiff"}


def _process_upload_files(course_id: str, user_id: str, files: List[UploadFile]):
    """Shared logic: upload files to vector store + create resource records.
    For image files the raw bytes are also stored in ``resource_images`` so the
    PDF/DOCX generators can retrieve them later via the
    /courses/{course_id}/images/{image_id} path.
    """
    check_course_exists(course_id)
    course = get_course(course_id)
    vector_store_id = course.get("vector_store_id")
    if not vector_store_id:
        raise HTTPException(status_code=500, detail="No vector_store_id found for course")
# Everything uploaded here is stored in Mongo only — nothing goes to OpenAI.
@router.post("/courses/{course_id}/resources", response_model=ResourceCreateResponse)
def upload_resources(course_id: str, files: List[UploadFile] = File(...), user_id: str = Depends(verify_token)):
    try:
        check_course_exists(course_id)

    # Collision-safe renaming
    existing_resources = get_resources_by_course_id(course_id) or []
    existing_names = {r.get("resource_name") for r in existing_resources if r.get("resource_name")}

    def ensure_unique_name(filename: str) -> str:
        base, ext = os.path.splitext(filename or "")
        if not base:
            base = "resource"
        candidate = f"{base}{ext}"
        n = 1
        while candidate in existing_names:
            candidate = f"{base} ({n}){ext}"
            n += 1
        existing_names.add(candidate)
        return candidate

    for f in files:
        f.filename = ensure_unique_name(f.filename)

    # Read each file's bytes BEFORE uploading (upload_resources seeks internally)
    file_bytes_map: dict[str, bytes] = {}
    for f in files:
        f.file.seek(0)
        file_bytes_map[f.filename] = f.file.read()
        f.file.seek(0)

    # Upload to OpenAI vector store
    openai_service.upload_resources(user_id, course_id, vector_store_id, files)

    # Create resource records and, for images, persist base64 bytes to Mongo
    for file in files:
        ext = os.path.splitext(file.filename)[1].lower()
        raw_bytes = file_bytes_map.get(file.filename, b"")

        if ext in _IMAGE_EXTENSIONS and raw_bytes:
            # Store image bytes as base64 in resource_images collection.
            # We first create the resource record to obtain its _id, then use
            # that _id as the image_id so asset.py's path lookup will succeed.
            create_resource(course_id, file.filename, "")  # create with empty content
            resource_doc = get_resource_by_course_id_and_resource_name(course_id, file.filename)
            resource_id = str(resource_doc["_id"]) if resource_doc else None

            if resource_id:
                image_base64 = base64.b64encode(raw_bytes).decode("utf-8")
                mime_type = mimetypes.guess_type(file.filename)[0] or "image/png"
        # Build a set of existing resource names for collision handling
        existing_resources = get_resources_by_course_id(course_id) or []
        existing_names = set([r.get("resource_name") for r in existing_resources if r.get("resource_name")])

        # Rename duplicates in-place so downstream uses the new name
        for f in files:
            f.filename = ensure_unique_name(f.filename, existing_names)

        for file in files:
            content = ""

            if is_image_filename(file.filename):
                # Directly-uploaded png/jpeg -> store the bytes (base64) in Mongo so
                # the image can be used as a figure and rendered later.
                file.file.seek(0)
                data = file.file.read()
                ext = os.path.splitext(file.filename)[1].lower().lstrip(".")
                mime = "image/jpeg" if ext in ("jpg", "jpeg") else f"image/{ext}"
                create_resource(course_id, file.filename, "")
                save_resource_image(
                    course_id=course_id,
                    resource_name=file.filename,
                    image_id=resource_id,
                    image_base64=image_base64,
                    image_mime=mime_type,
                    image_ext=ext,
                )
                logger.info(
                    f"[UPLOAD] Saved image to resource_images: "
                    f"{file.filename} -> image_id={resource_id}"
                )
            else:
                logger.warning(f"[UPLOAD] Could not retrieve _id for image resource: {file.filename}")

        elif ext == ".pdf" and raw_bytes:
            try:
                pdf_reader = PdfReader(io.BytesIO(raw_bytes))
                content = ""
                for page in pdf_reader.pages:
                    content += page.extract_text() or ""
            except Exception as e:
                logger.warning(f"[UPLOAD] PDF text extraction failed for {file.filename}: {e}")
                content = ""
            create_resource(course_id, file.filename, content)

        else:
            # Text / other files — decode as UTF-8
            try:
                content = raw_bytes.decode("utf-8", errors="ignore")
            except Exception:
                content = ""
                continue

            if file.filename.endswith(".pdf"):
                # Store the raw bytes (<= 15 MB) so the real PDF can be viewed and
                # sent directly to the model, plus the extracted text as a fallback
                # for oversized files and for prompt injection.
                file.file.seek(0)
                data = file.file.read()
                if data and len(data) <= _MAX_PDF_BYTES:
                    try:
                        pages = len(PdfReader(io.BytesIO(data)).pages)
                    except Exception:
                        pages = 0
                    save_resource_pdf(course_id, file.filename, data, len(data), pages)
                try:
                    pdf_reader = PdfReader(io.BytesIO(data))
                    for page in pdf_reader.pages:
                        content += page.extract_text() or ""
                except Exception as text_err:
                    logger.warning(f"Text extraction failed for '{file.filename}': {text_err}")
            else:
                file.file.seek(0)
                content = file.file.read().decode("utf-8", errors="ignore")

            create_resource(course_id, file.filename, content)


# Keep this route, we add the file to the vector store attached
@router.post("/courses/{course_id}/resources", response_model=ResourceCreateResponse)
def upload_resources(course_id: str, files: List[UploadFile] = File(...), user_id: str = Depends(verify_token)):
    try:
        _process_upload_files(course_id, user_id, files)
        return ResourceCreateResponse(message="Resources uploaded successfully")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error uploading resources: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


# Alias used by the frontend (extract-images pipeline).
# Behaves identically to the main upload route — images are stored to
# resource_images automatically in _process_upload_files.
@router.post("/courses/{course_id}/resources/extract-images", response_model=ResourceCreateResponse)
def extract_and_upload_resources(
    course_id: str,
    files: List[UploadFile] = File(...),
    user_id: str = Depends(verify_token),
):
    try:
        _process_upload_files(course_id, user_id, files)
        return ResourceCreateResponse(message="Resources uploaded and images stored successfully")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in extract-images upload: {str(e)}")
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
        if not resource:
            raise HTTPException(status_code=404, detail="Resource not found")

        # 3. Check if content exists
        content = resource.get("content")
        logger.info(f"Content found: {content is not None}, Length: {len(content) if content else 0}")
        if not content:
            raise HTTPException(status_code=404, detail="Resource has no content stored")
        
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
    Stores each resource's title, URL and description as Mongo resource content.
    """
    try:
        check_course_exists(course_id)

        if not request.resources or len(request.resources) == 0:
            raise HTTPException(status_code=400, detail="No resources provided")

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
                
                # Store the link's text as the resource content in Mongo so
                # generation can inject it like any other knowledge-base entry.
                content = f"{resource.title}\n\n{resource.url}\n\n{resource.description}"
                create_resource(course_id, resource_name, content)

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