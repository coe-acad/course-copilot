from fastapi import APIRouter, HTTPException, UploadFile, File, Form, Depends
from typing import Optional
from pydantic import BaseModel
import logging
from ..utils.verify_token import verify_admin
from ..services.mongo import (
    create_admin_file,
    get_all_admin_files,
    get_admin_file_by_id,
    delete_admin_file,
    store_pdf_in_mongo,
    retrieve_pdf_from_mongo,
    delete_pdf_from_mongo,
    get_all_settings,
    add_setting_label,
    remove_setting_label,
    get_one_from_collection,
    update_user_role,
    create_user,
    get_user_by_email,
    delete_user
)
from fastapi.responses import StreamingResponse
import io

logger = logging.getLogger(__name__)
router = APIRouter()

class AddLabelRequest(BaseModel):
    label: str

class UpdateRoleRequest(BaseModel):
    role: str

class CreateUserRequest(BaseModel):
    email: str
    display_name: str
    role: str = "user"

# User Management
@router.get("/admin/users")
def get_all_users(user_id: str = Depends(verify_admin)):
    """Get all users"""
    try:
        logger.info(f"Admin {user_id} fetching all users")
        # Get all users from collection
        from ..services.mongo import db
        users_collection = db["users"]
        all_users = list(users_collection.find({}))
        # Convert ObjectId to string
        for user in all_users:
            if '_id' in user:
                user['_id'] = str(user['_id'])
        return {"users": all_users, "count": len(all_users)}
    except Exception as e:
        logger.error(f"Error fetching users: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error fetching users: {str(e)}")

@router.post("/admin/users")
def create_new_user(
    request: CreateUserRequest,
    user_id: str = Depends(verify_admin)
):
    """Create a new user"""
    try:
        from uuid import uuid4
        logger.info(f"Admin {user_id} creating new user: {request.email}")
        
        # Check if user already exists
        existing_user = get_user_by_email(request.email.lower())
        if existing_user:
            raise HTTPException(status_code=400, detail="User with this email already exists")
        
        # Validate role
        if request.role not in ["user", "admin"]:
            raise HTTPException(status_code=400, detail="Role must be 'user' or 'admin'")
        
        # Create new user with generated ID
        new_user_id = str(uuid4())
        create_user(new_user_id, request.email.lower(), request.display_name, request.role)
        
        logger.info(f"Successfully created user {new_user_id} with email {request.email}")
        
        return {"message": "User created successfully", "user_id": new_user_id, "email": request.email}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating user: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error creating user: {str(e)}")

@router.put("/admin/users/{target_user_id}/role")
def update_user_role_endpoint(
    target_user_id: str,
    request: UpdateRoleRequest,
    user_id: str = Depends(verify_admin)
):
    """Update a user's role"""
    try:
        logger.info(f"Admin {user_id} updating role for user {target_user_id} to {request.role}")
        
        # Validate role
        if request.role not in ["user", "admin"]:
            raise HTTPException(status_code=400, detail="Role must be 'user' or 'admin'")
        
        update_user_role(target_user_id, request.role)
        logger.info(f"Successfully updated user {target_user_id} role to {request.role}")
        
        return {"message": "User role updated successfully", "user_id": target_user_id, "role": request.role}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating user role: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error updating user role: {str(e)}")

@router.delete("/admin/users/{target_user_id}")
def delete_user_endpoint(
    target_user_id: str,
    user_id: str = Depends(verify_admin)
):
    """Delete a user"""
    try:
        logger.info(f"Admin {user_id} deleting user {target_user_id}")
        
        # Prevent deleting yourself
        if target_user_id == user_id:
            raise HTTPException(status_code=400, detail="You cannot delete your own account")
        
        # delete_user(target_user_id)
        logger.info(f"Successfully deleted user {target_user_id}")
        
        return {"message": "User deleted successfully", "user_id": target_user_id}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting user: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error deleting user: {str(e)}")

@router.post("/admin/documents")
async def upload_admin_document(
    document_title: str = Form(...),
    file: UploadFile = File(...),
    user_id: str = Depends(verify_admin)
):
    """Upload a document to admin files collection"""
    try:
        logger.info(f"User {user_id} uploading admin document: {document_title}")
        
        # Validate file type - Only PDF and TXT
        allowed_types = ["application/pdf", "text/plain"]
        allowed_extensions = [".pdf", ".txt"]
        
        file_extension = "." + file.filename.split(".")[-1].lower()
        
        if file.content_type not in allowed_types or file_extension not in allowed_extensions:
            raise HTTPException(status_code=400, detail="Only PDF and TXT files are allowed")
        
        # Read file content
        content = await file.read()
        
        # Validate file size - 10MB limit (10 * 1024 * 1024 bytes)
        MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB in bytes
        if len(content) > MAX_FILE_SIZE:
            raise HTTPException(
                status_code=400, 
                detail=f"File size exceeds maximum limit of 10MB. Your file is {len(content) / (1024 * 1024):.2f}MB"
            )
        
        # Store file in MongoDB GridFS
        gridfs_file_id = store_pdf_in_mongo(
            file_content=content,
            filename=file.filename,
            metadata={
                "document_title": document_title,
                "uploaded_by": user_id,
                "content_type": file.content_type
            }
        )
        
        # Create admin file record
        file_data = {
            "document_title": document_title,
            "filename": file.filename,
            "content_type": file.content_type,
            "gridfs_file_id": gridfs_file_id,
            "uploaded_by": user_id,
            "file_size": len(content)
        }
        
        file_id = create_admin_file(file_data)
        
        logger.info(f"Successfully uploaded admin document {file_id}")
        
        return {
            "file_id": file_id,
            "message": "Document uploaded successfully",
            "filename": file.filename
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error uploading admin document: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error uploading document: {str(e)}")

@router.get("/admin/documents")
async def get_admin_documents(user_id: str = Depends(verify_admin)):
    """Get all admin documents"""
    try:
        logger.info(f"User {user_id} fetching admin documents")
        documents = get_all_admin_files()
        
        # Sort by created_at descending (newest first)
        documents.sort(key=lambda x: x.get("created_at", ""), reverse=True)
        
        return {
            "documents": documents,
            "count": len(documents)
        }
        
    except Exception as e:
        logger.error(f"Error fetching admin documents: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error fetching documents: {str(e)}")

@router.get("/admin/documents/{file_id}/download")
async def download_admin_document(file_id: str, user_id: str = Depends(verify_admin)):
    """Download an admin document"""
    try:
        logger.info(f"User {user_id} downloading admin document {file_id}")
        
        # Get file record
        file_record = get_admin_file_by_id(file_id)
        if not file_record:
            raise HTTPException(status_code=404, detail="Document not found")
        
        # Get file from GridFS
        gridfs_file_id = file_record.get("gridfs_file_id")
        if not gridfs_file_id:
            raise HTTPException(status_code=404, detail="File data not found")
        
        file_content = retrieve_pdf_from_mongo(gridfs_file_id)
        
        # Create response with file
        return StreamingResponse(
            io.BytesIO(file_content),
            media_type=file_record.get("content_type", "application/octet-stream"),
            headers={
                "Content-Disposition": f'attachment; filename="{file_record.get("filename", "document")}"'
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error downloading admin document: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error downloading document: {str(e)}")

@router.delete("/admin/documents/{file_id}")
async def delete_admin_document(file_id: str, user_id: str = Depends(verify_admin)):
    """Delete an admin document"""
    try:
        logger.info(f"User {user_id} deleting admin document {file_id}")
        
        # Get file record
        file_record = get_admin_file_by_id(file_id)
        if not file_record:
            raise HTTPException(status_code=404, detail="Document not found")
        
        # Delete from GridFS
        gridfs_file_id = file_record.get("gridfs_file_id")
        if gridfs_file_id:
            delete_pdf_from_mongo(gridfs_file_id)
        
        # Delete record from admin_files collection
        delete_admin_file(file_id)
        
        logger.info(f"Successfully deleted admin document {file_id}")
        
        return {"message": "Document deleted successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting admin document: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error deleting document: {str(e)}")

# Setting Labels Management
@router.get("/admin/settings")
def get_all_setting_labels(user_id: str = Depends(verify_admin)):
    """Get all setting configurations"""
    try:
        logger.info(f"User {user_id} fetching all setting labels")
        settings = get_all_settings()
        return {"settings": settings}
    except Exception as e:
        logger.error(f"Error fetching settings: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error fetching settings: {str(e)}")

@router.post("/admin/settings/{category}/labels")
def add_label_to_setting(
    category: str, 
    request: AddLabelRequest,
    user_id: str = Depends(verify_admin)
):
    """Add a label to a setting category"""
    try:
        logger.info(f"User {user_id} adding label '{request.label}' to category '{category}'")
        add_setting_label(category, request.label)
        logger.info(f"Successfully added label '{request.label}' to category '{category}'")
        return {"message": "Label added successfully", "category": category, "label": request.label}
    except ValueError as ve:
        logger.warning(f"Validation error adding label: {str(ve)}")
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        logger.error(f"Error adding label: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error adding label: {str(e)}")

@router.delete("/admin/settings/{category}/labels/{label}")
def remove_label_from_setting(
    category: str,
    label: str,
    user_id: str = Depends(verify_admin)
):
    """Remove a label from a setting category"""
    try:
        logger.info(f"User {user_id} removing label '{label}' from category '{category}'")
        remove_setting_label(category, label)
        logger.info(f"Successfully removed label '{label}' from category '{category}'")
        return {"message": "Label removed successfully", "category": category, "label": label}
    except ValueError as ve:
        logger.warning(f"Validation error removing label: {str(ve)}")
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        logger.error(f"Error removing label: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error removing label: {str(e)}")

