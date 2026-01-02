"""
SuperAdmin Routes

Endpoints for SuperAdmin operations:
- Organization management (create, list, delete)
- SuperAdmin user management
"""

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, EmailStr
from typing import Optional
import logging

from ..utils.verify_token import verify_super_admin
from ..services.master_db import (
    create_organization,
    get_all_organizations,
    get_organization_by_id,
    delete_organization,
    create_superadmin,
    get_all_superadmins,
    get_superadmin_by_email,
    get_payment_config,
    set_payment_config
)
from ..services.mongo import (
    get_all_settings,
    add_setting_label,
    remove_setting_label
)

logger = logging.getLogger(__name__)
router = APIRouter()


# ============== REQUEST/RESPONSE MODELS ==============

class CreateOrganizationRequest(BaseModel):
    org_name: str
    admin_email: EmailStr
    admin_password: Optional[str] = None  # Optional, will generate if not provided


class OrganizationResponse(BaseModel):
    org_id: str
    org_name: str
    database_name: str
    admin_email: str
    admin_user_id: str


class CreateSuperAdminRequest(BaseModel):
    email: EmailStr
    password: str
    display_name: Optional[str] = None


# ============== ORGANIZATION ENDPOINTS ==============

@router.post("/superadmin/organizations", response_model=OrganizationResponse)
async def create_org(request: CreateOrganizationRequest, user_id: str = Depends(verify_super_admin)):
    """Create a new organization with admin credentials"""
    logger.info(f"SuperAdmin {user_id} creating organization: {request.org_name}")
    
    try:
        result = create_organization(
            org_name=request.org_name,
            admin_email=request.admin_email,
            admin_password=request.admin_password
        )
        
        return OrganizationResponse(
            org_id=result["org_id"],
            org_name=result["org_name"],
            database_name=result["database_name"],
            admin_email=result["admin_email"],
            admin_user_id=result["admin_user_id"]
        )
    except Exception as e:
        logger.error(f"Failed to create organization: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to create organization: {str(e)}")


@router.get("/superadmin/organizations")
async def list_organizations(user_id: str = Depends(verify_super_admin)):
    """List all organizations"""
    logger.info(f"SuperAdmin {user_id} listing organizations")
    
    try:
        orgs = get_all_organizations()
        return {"organizations": orgs}
    except Exception as e:
        logger.error(f"Failed to list organizations: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to list organizations: {str(e)}")


@router.get("/superadmin/organizations/{org_id}")
async def get_org(org_id: str, user_id: str = Depends(verify_super_admin)):
    """Get organization details"""
    logger.info(f"SuperAdmin {user_id} getting organization: {org_id}")
    
    org = get_organization_by_id(org_id)
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")
    
    return org


@router.delete("/superadmin/organizations/{org_id}")
async def delete_org(org_id: str, user_id: str = Depends(verify_super_admin)):
    """Delete an organization and its database"""
    logger.info(f"SuperAdmin {user_id} deleting organization: {org_id}")
    
    success = delete_organization(org_id)
    if not success:
        raise HTTPException(status_code=404, detail="Organization not found")
    
    return {"message": "Organization deleted successfully", "org_id": org_id}


# ============== SUPERADMIN USER ENDPOINTS ==============

@router.post("/superadmin/create-superadmin")
async def create_new_superadmin(request: CreateSuperAdminRequest, user_id: str = Depends(verify_super_admin)):
    """Create a new superadmin user"""
    from firebase_admin import auth as firebase_auth
    
    logger.info(f"SuperAdmin {user_id} creating new superadmin: {request.email}")
    
    # Check if superadmin already exists
    existing = get_superadmin_by_email(request.email)
    if existing:
        raise HTTPException(status_code=400, detail="SuperAdmin with this email already exists")
    
    try:
        # Create Firebase user
        firebase_user = firebase_auth.create_user(
            email=request.email,
            password=request.password,
            display_name=request.display_name or "SuperAdmin"
        )
        
        # Create superadmin in master database
        create_superadmin(
            user_id=firebase_user.uid,
            email=request.email,
            display_name=request.display_name
        )
        
        return {
            "message": "SuperAdmin created successfully",
            "user_id": firebase_user.uid,
            "email": request.email
        }
    except Exception as e:
        logger.error(f"Failed to create superadmin: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to create superadmin: {str(e)}")


@router.get("/superadmin/superadmins")
async def list_superadmins(user_id: str = Depends(verify_super_admin)):
    """List all superadmin users"""
    logger.info(f"SuperAdmin {user_id} listing superadmins")
    
    superadmins = get_all_superadmins()
    return {"superadmins": superadmins}


# ============== VERIFICATION ENDPOINT ==============

@router.get("/superadmin/verify")
async def verify_superadmin_access(user_id: str = Depends(verify_super_admin)):
    """Verify if current user has superadmin access"""
    return {"message": "SuperAdmin access verified", "user_id": user_id}


# ============== BOOTSTRAP ENDPOINT (NO AUTH) ==============

@router.post("/superadmin/bootstrap")
async def bootstrap_first_superadmin(request: CreateSuperAdminRequest):
    """
    Create the first superadmin user. This endpoint only works if no superadmin exists.
    After the first superadmin is created, this endpoint will reject all requests.
    """
    from firebase_admin import auth as firebase_auth
    
    # Check if any superadmin already exists
    existing_superadmins = get_all_superadmins()
    if len(existing_superadmins) > 0:
        logger.warning("Bootstrap attempted but superadmins already exist")
        raise HTTPException(status_code=403, detail="System already has superadmin(s). Use the authenticated endpoint instead.")
    
    logger.info(f"Bootstrapping first superadmin: {request.email}")
    
    try:
        # Create Firebase user
        try:
            firebase_user = firebase_auth.create_user(
                email=request.email,
                password=request.password,
                display_name=request.display_name or "SuperAdmin"
            )
            user_id = firebase_user.uid
        except Exception as e:
            # User might already exist in Firebase - update their password
            try:
                firebase_user = firebase_auth.get_user_by_email(request.email)
                user_id = firebase_user.uid
                # Update the password to the provided one
                firebase_auth.update_user(user_id, password=request.password)
                logger.info(f"Updated password for existing Firebase user: {request.email}")
            except:
                raise e
        
        # Create superadmin in master database
        create_superadmin(
            user_id=user_id,
            email=request.email,
            display_name=request.display_name
        )
        
        logger.info(f"✅ First superadmin bootstrapped successfully: {request.email}")
        
        return {
            "message": "First SuperAdmin created successfully! You can now login at /superadmin",
            "user_id": user_id,
            "email": request.email
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to bootstrap superadmin: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to bootstrap superadmin: {str(e)}")


class ResetPasswordRequest(BaseModel):
    email: EmailStr
    new_password: str


@router.post("/superadmin/reset-password")
async def reset_superadmin_password(request: ResetPasswordRequest):
    """
    Reset password for a superadmin. Only works for existing superadmins.
    This is a privileged endpoint - use with caution.
    """
    from firebase_admin import auth as firebase_auth
    
    # Check if user is a superadmin
    superadmin = get_superadmin_by_email(request.email)
    if not superadmin:
        raise HTTPException(status_code=404, detail="SuperAdmin not found with this email")
    
    try:
        user_id = superadmin.get("_id")
        firebase_auth.update_user(user_id, password=request.new_password)
        logger.info(f"Password reset for superadmin: {request.email}")
        
        return {"message": f"Password reset successfully for {request.email}"}
    except Exception as e:
        logger.error(f"Failed to reset password: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to reset password: {str(e)}")


# ============== PAYMENT CONFIGURATION ==============

class PaymentConfigRequest(BaseModel):
    price_per_user_paise: int  # Amount in paise (e.g., 50000 = ₹500.00)
    currency: str = "INR"


@router.get("/superadmin/payment-config")
async def get_payment_configuration(user_id: str = Depends(verify_super_admin)):
    """Get the current payment configuration (price per user)"""
    logger.info(f"SuperAdmin {user_id} getting payment config")
    
    config = get_payment_config()
    if not config:
        return {
            "configured": False,
            "price_per_user_paise": 0,
            "currency": "INR",
            "message": "Payment configuration not set"
        }
    
    return {
        "configured": True,
        "price_per_user_paise": config.get("price_per_user_paise", 0),
        "currency": config.get("currency", "INR"),
        "updated_at": config.get("updated_at")
    }


@router.post("/superadmin/payment-config")
async def update_payment_configuration(request: PaymentConfigRequest, user_id: str = Depends(verify_super_admin)):
    """Set the payment configuration (price per user)"""
    logger.info(f"SuperAdmin {user_id} updating payment config to {request.price_per_user_paise} paise")
    
    if request.price_per_user_paise < 0:
        raise HTTPException(status_code=400, detail="Price cannot be negative")
    
    config = set_payment_config(
        price_per_user_paise=request.price_per_user_paise,
        currency=request.currency
    )
    
    return {
        "message": "Payment configuration updated successfully",
        "price_per_user_paise": config["price_per_user_paise"],
        "currency": config["currency"],
        "updated_at": config["updated_at"]
    }


# ============== SETTING LABELS MANAGEMENT ==============

class AddLabelRequest(BaseModel):
    label: str


@router.get("/superadmin/settings")
async def get_all_setting_labels(user_id: str = Depends(verify_super_admin)):
    """Get all setting configurations"""
    logger.info(f"SuperAdmin {user_id} fetching all settings")
    
    try:
        settings = get_all_settings()
        return {"settings": settings}
    except Exception as e:
        logger.error(f"Error fetching settings: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error fetching settings: {str(e)}")


@router.post("/superadmin/settings/{category}/labels")
async def add_label_to_setting(
    category: str,
    request: AddLabelRequest,
    user_id: str = Depends(verify_super_admin)
):
    """Add a label to a setting category"""
    logger.info(f"SuperAdmin {user_id} adding label '{request.label}' to category '{category}'")
    
    try:
        add_setting_label(category, request.label)
        return {"message": "Label added successfully", "category": category, "label": request.label}
    except ValueError as ve:
        logger.warning(f"Validation error adding label: {str(ve)}")
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        logger.error(f"Error adding label: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error adding label: {str(e)}")


@router.delete("/superadmin/settings/{category}/labels/{label}")
async def remove_label_from_setting(
    category: str,
    label: str,
    user_id: str = Depends(verify_super_admin)
):
    """Remove a label from a setting category"""
    logger.info(f"SuperAdmin {user_id} removing label '{label}' from category '{category}'")
    
    try:
        remove_setting_label(category, label)
        return {"message": "Label removed successfully", "category": category, "label": label}
    except ValueError as ve:
        logger.warning(f"Validation error removing label: {str(ve)}")
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        logger.error(f"Error removing label: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error removing label: {str(e)}")
