from fastapi import APIRouter, HTTPException, UploadFile, File, Form, Depends
from typing import Optional
from pydantic import BaseModel
import logging
from ..utils.verify_token import verify_admin, verify_admin_with_org_context
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
    delete_user,
    get_all_users as get_all_users_from_db,
    get_org_collection,
    get_org_gridfs,
    create_payment_record,
    update_payment_record,
    get_payment_by_order_id,
    get_payment_by_id,
    get_payment_history,
    get_non_admin_user_count
)
from ..services.master_db import get_payment_config
from fastapi.responses import StreamingResponse
import io
import razorpay
from datetime import datetime

logger = logging.getLogger(__name__)
router = APIRouter()

class AddLabelRequest(BaseModel):
    label: str

class UpdateRoleRequest(BaseModel):
    role: str

class CreateUserRequest(BaseModel):
    email: str
    display_name: str
    password: str

# User Management
@router.get("/admin/users")
def get_all_users(ctx: dict = Depends(verify_admin_with_org_context)):
    """Get all users from the organization's database"""
    user_id = ctx["user_id"]
    org_db_name = ctx.get("org_db_name")
    try:
        logger.info(f"Admin {user_id} fetching all users from org db: {org_db_name}")
        
        all_users = get_all_users_from_db(org_db_name)
        
        return {"users": all_users, "count": len(all_users), "org_name": ctx.get("org_name")}
    except Exception as e:
        logger.error(f"Error fetching users: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error fetching users: {str(e)}")

@router.post("/admin/users")
def create_new_user(
    request: CreateUserRequest,
    ctx: dict = Depends(verify_admin_with_org_context)
):
    """Create a new user in the organization's database (always as 'user' role)"""
    user_id = ctx["user_id"]
    org_db_name = ctx.get("org_db_name")
    try:
        from firebase_admin import auth as firebase_auth
        
        logger.info(f"Admin {user_id} creating new user: {request.email} in org: {ctx.get('org_name')}")
        
        # Check if user already exists in this org
        existing_user = get_user_by_email(request.email.lower(), org_db_name)
        if existing_user:
            raise HTTPException(status_code=400, detail="User with this email already exists in this organization")
        
        # Validate password
        if len(request.password) < 6:
            raise HTTPException(status_code=400, detail="Password must be at least 6 characters")
        
        # Check if Firebase user exists, if not create one
        try:
            firebase_user = firebase_auth.get_user_by_email(request.email.lower())
            new_user_id = firebase_user.uid
            # Update password for existing user
            firebase_auth.update_user(new_user_id, password=request.password)
            logger.info(f"Using existing Firebase user and updating password: {request.email}")
        except:
            # Create new Firebase user with the provided password
            firebase_user = firebase_auth.create_user(
                email=request.email.lower(),
                password=request.password,
                display_name=request.display_name
            )
            new_user_id = firebase_user.uid
            logger.info(f"Created new Firebase user: {request.email}")
        
        # Create user in org database with role="user" (always)
        create_user(new_user_id, request.email.lower(), request.display_name, "user", org_db_name)
        
        logger.info(f"Successfully created user {new_user_id} with email {request.email} in org {ctx.get('org_name')}")
        
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
    ctx: dict = Depends(verify_admin_with_org_context)
):
    """Update a user's role in the organization's database"""
    user_id = ctx["user_id"]
    org_db_name = ctx.get("org_db_name")
    try:
        logger.info(f"Admin {user_id} updating role for user {target_user_id} to {request.role} in org: {ctx.get('org_name')}")
        
        # Validate role
        if request.role not in ["user", "admin"]:
            raise HTTPException(status_code=400, detail="Role must be 'user' or 'admin'")
        
        update_user_role(target_user_id, request.role, org_db_name)
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
    ctx: dict = Depends(verify_admin_with_org_context)
):
    """Delete a user from the organization's database"""
    user_id = ctx["user_id"]
    org_db_name = ctx.get("org_db_name")
    try:
        logger.info(f"Admin {user_id} deleting user {target_user_id} from org: {ctx.get('org_name')}")
        
        # Prevent deleting yourself
        if target_user_id == user_id:
            raise HTTPException(status_code=400, detail="You cannot delete your own account")
        
        delete_user(target_user_id, org_db_name)
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
    ctx: dict = Depends(verify_admin_with_org_context)
):
    """Upload a document to admin files collection for this organization"""
    user_id = ctx["user_id"]
    org_db_name = ctx.get("org_db_name")
    try:
        logger.info(f"Admin {user_id} uploading admin document: {document_title} to org db: {org_db_name}")
        
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
        
        # Store file in MongoDB GridFS (using org-specific GridFS)
        gridfs_file_id = store_pdf_in_mongo(
            file_content=content,
            filename=file.filename,
            metadata={
                "document_title": document_title,
                "uploaded_by": user_id,
                "content_type": file.content_type
            },
            org_db_name=org_db_name
        )
        
        # Create admin file record in org-specific database
        file_data = {
            "document_title": document_title,
            "filename": file.filename,
            "content_type": file.content_type,
            "gridfs_file_id": gridfs_file_id,
            "uploaded_by": user_id,
            "file_size": len(content)
        }
        
        file_id = create_admin_file(file_data, org_db_name)
        
        logger.info(f"Successfully uploaded admin document {file_id} to org: {org_db_name}")
        
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
async def get_admin_documents(ctx: dict = Depends(verify_admin_with_org_context)):
    """Get all admin documents for this organization"""
    user_id = ctx["user_id"]
    org_db_name = ctx.get("org_db_name")
    try:
        logger.info(f"Admin {user_id} fetching admin documents from org db: {org_db_name}")
        documents = get_all_admin_files(org_db_name)
        
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
async def download_admin_document(file_id: str, ctx: dict = Depends(verify_admin_with_org_context)):
    """Download an admin document"""
    user_id = ctx["user_id"]
    org_db_name = ctx.get("org_db_name")
    try:
        logger.info(f"Admin {user_id} downloading admin document {file_id} from org db: {org_db_name}")
        
        # Get file record from org-specific database
        file_record = get_admin_file_by_id(file_id, org_db_name)
        if not file_record:
            raise HTTPException(status_code=404, detail="Document not found")
        
        # Get file from GridFS (org-specific)
        gridfs_file_id = file_record.get("gridfs_file_id")
        if not gridfs_file_id:
            raise HTTPException(status_code=404, detail="File data not found")
        
        file_content = retrieve_pdf_from_mongo(gridfs_file_id, org_db_name)
        
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
async def delete_admin_document(file_id: str, ctx: dict = Depends(verify_admin_with_org_context)):
    """Delete an admin document"""
    user_id = ctx["user_id"]
    org_db_name = ctx.get("org_db_name")
    try:
        logger.info(f"Admin {user_id} deleting admin document {file_id} from org db: {org_db_name}")
        
        # Get file record from org-specific database
        file_record = get_admin_file_by_id(file_id, org_db_name)
        if not file_record:
            raise HTTPException(status_code=404, detail="Document not found")
        
        # Delete from GridFS (org-specific)
        gridfs_file_id = file_record.get("gridfs_file_id")
        if gridfs_file_id:
            delete_pdf_from_mongo(gridfs_file_id, org_db_name)
        
        # Delete record from admin_files collection (org-specific)
        delete_admin_file(file_id, org_db_name)
        
        logger.info(f"Successfully deleted admin document {file_id} from org: {org_db_name}")
        
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

# Note: Delete label endpoint removed - only SuperAdmin can remove labels


# ============== PAYMENT MANAGEMENT ==============

import os

# Razorpay configuration from environment variables
RAZORPAY_KEY_ID = os.getenv("RAZORPAY_KEY_ID", "")
RAZORPAY_KEY_SECRET = os.getenv("RAZORPAY_KEY_SECRET", "")

# Initialize Razorpay client
razorpay_client = razorpay.Client(auth=(RAZORPAY_KEY_ID, RAZORPAY_KEY_SECRET))


@router.get("/admin/payment-summary")
def get_payment_summary(ctx: dict = Depends(verify_admin_with_org_context)):
    """Get payment summary for the organization - user count, price, total"""
    user_id = ctx["user_id"]
    org_db_name = ctx.get("org_db_name")
    
    try:
        logger.info(f"Admin {user_id} fetching payment summary for org: {org_db_name}")
        
        # Get non-admin user count
        user_count = get_non_admin_user_count(org_db_name)
        
        # Get payment config from master DB
        payment_config = get_payment_config()
        
        if not payment_config:
            return {
                "configured": False,
                "message": "Payment not configured by SuperAdmin",
                "user_count": user_count,
                "price_per_user_paise": 0,
                "total_amount_paise": 0,
                "currency": "INR"
            }
        
        price_per_user = payment_config.get("price_per_user_paise", 0)
        total_amount = price_per_user * user_count
        currency = payment_config.get("currency", "INR")
        
        return {
            "configured": True,
            "user_count": user_count,
            "price_per_user_paise": price_per_user,
            "total_amount_paise": total_amount,
            "currency": currency
        }
        
    except Exception as e:
        logger.error(f"Error fetching payment summary: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error fetching payment summary: {str(e)}")


@router.post("/admin/payments/create-order")
def create_razorpay_order(ctx: dict = Depends(verify_admin_with_org_context)):
    """Create a Razorpay order for payment"""
    user_id = ctx["user_id"]
    org_db_name = ctx.get("org_db_name")
    
    try:
        logger.info(f"Admin {user_id} creating Razorpay order for org: {org_db_name}")
        
        # Get user count and price
        user_count = get_non_admin_user_count(org_db_name)
        payment_config = get_payment_config()
        
        if not payment_config:
            raise HTTPException(status_code=400, detail="Payment not configured by SuperAdmin")
        
        price_per_user = payment_config.get("price_per_user_paise", 0)
        total_amount = price_per_user * user_count
        currency = payment_config.get("currency", "INR")
        
        if total_amount <= 0:
            raise HTTPException(status_code=400, detail="Invalid payment amount")
        
        # Create Razorpay order
        order_data = {
            "amount": total_amount,
            "currency": currency
        }
        razorpay_order = razorpay_client.order.create(data=order_data)
        
        # Store pending payment record
        payment_data = {
            "razorpay_order_id": razorpay_order['id'],
            "amount_paise": total_amount,
            "user_count": user_count,
            "price_per_user_paise": price_per_user,
            "currency": currency,
            "status": "pending",
            "paid_by_user_id": user_id,
            "org_name": ctx.get("org_name")
        }
        payment_id = create_payment_record(payment_data, org_db_name)
        
        logger.info(f"Created Razorpay order {razorpay_order['id']} for org {org_db_name}")
        
        return {
            "order_id": razorpay_order['id'],
            "amount": total_amount,
            "currency": currency,
            "key_id": RAZORPAY_KEY_ID,
            "payment_id": payment_id
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating Razorpay order: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error creating order: {str(e)}")


class VerifyPaymentRequest(BaseModel):
    razorpay_order_id: str
    razorpay_payment_id: str
    razorpay_signature: str


@router.post("/admin/payments/verify")
def verify_razorpay_payment(request: VerifyPaymentRequest, ctx: dict = Depends(verify_admin_with_org_context)):
    """Verify Razorpay payment and update record"""
    user_id = ctx["user_id"]
    org_db_name = ctx.get("org_db_name")
    
    try:
        logger.info(f"Admin {user_id} verifying payment for order {request.razorpay_order_id}")
        
        # Verify signature
        try:
            razorpay_client.utility.verify_payment_signature({
                "razorpay_order_id": request.razorpay_order_id,
                "razorpay_payment_id": request.razorpay_payment_id,
                "razorpay_signature": request.razorpay_signature
            })
        except razorpay.errors.SignatureVerificationError:
            logger.error(f"Payment signature verification failed for order {request.razorpay_order_id}")
            raise HTTPException(status_code=400, detail="Payment verification failed")
        
        # Get payment record
        payment = get_payment_by_order_id(request.razorpay_order_id, org_db_name)
        if not payment:
            raise HTTPException(status_code=404, detail="Payment record not found")
        
        # Update payment record
        update_data = {
            "razorpay_payment_id": request.razorpay_payment_id,
            "razorpay_signature": request.razorpay_signature,
            "status": "captured",
            "captured_at": datetime.utcnow().isoformat()
        }
        update_payment_record(payment["_id"], update_data, org_db_name)
        
        logger.info(f"Payment verified successfully for order {request.razorpay_order_id}")
        
        return {
            "success": True,
            "message": "Payment verified successfully",
            "payment_id": payment["_id"],
            "amount_paise": payment.get("amount_paise"),
            "user_count": payment.get("user_count")
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error verifying payment: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error verifying payment: {str(e)}")


@router.get("/admin/payments/history")
def get_payments_history(ctx: dict = Depends(verify_admin_with_org_context)):
    """Get payment history for the organization"""
    user_id = ctx["user_id"]
    org_db_name = ctx.get("org_db_name")
    
    try:
        logger.info(f"Admin {user_id} fetching payment history for org: {org_db_name}")
        
        payments = get_payment_history(org_db_name)
        
        return {
            "payments": payments,
            "count": len(payments)
        }
        
    except Exception as e:
        logger.error(f"Error fetching payment history: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error fetching payment history: {str(e)}")


@router.get("/admin/payments/{payment_id}/receipt")
def get_payment_receipt(payment_id: str, ctx: dict = Depends(verify_admin_with_org_context)):
    """Get payment receipt details"""
    user_id = ctx["user_id"]
    org_db_name = ctx.get("org_db_name")
    
    try:
        logger.info(f"Admin {user_id} fetching receipt for payment {payment_id}")
        
        payment = get_payment_by_id(payment_id, org_db_name)
        if not payment:
            raise HTTPException(status_code=404, detail="Payment not found")
        
        if payment.get("status") != "captured":
            raise HTTPException(status_code=400, detail="Payment not completed")
        
        # Return receipt data
        return {
            "receipt": {
                "payment_id": payment["_id"],
                "razorpay_payment_id": payment.get("razorpay_payment_id"),
                "razorpay_order_id": payment.get("razorpay_order_id"),
                "amount_paise": payment.get("amount_paise"),
                "amount_display": f"₹{payment.get('amount_paise', 0) / 100:.2f}",
                "currency": payment.get("currency", "INR"),
                "user_count": payment.get("user_count"),
                "price_per_user_paise": payment.get("price_per_user_paise"),
                "org_name": payment.get("org_name") or ctx.get("org_name"),
                "status": payment.get("status"),
                "created_at": payment.get("created_at"),
                "captured_at": payment.get("captured_at")
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching receipt: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error fetching receipt: {str(e)}")
