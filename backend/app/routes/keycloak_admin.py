"""
Keycloak Admin API routes for organization and user management
Handles organization creation, user management within organizations
"""
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, EmailStr
from typing import Optional
import logging
from ..services.keycloak_admin import keycloak_admin
from ..utils.verify_keycloak_token import verify_keycloak_token, require_role

logger = logging.getLogger(__name__)
router = APIRouter()


# ========== Test Endpoint ==========

@router.get("/test-connection")
async def test_keycloak_connection(
    user_id: str = Depends(require_role("superadmin"))
):
    """Test Keycloak Admin API connection"""
    if not keycloak_admin:
        return {
            "status": "error", 
            "message": "Keycloak Admin service not available - check if it initialized properly",
            "details": "The KeycloakAdminService failed to initialize. Check backend startup logs."
        }
    
    try:
        # Ensure we're in the correct realm
        keycloak_admin._ensure_realm()
        
        # Test connection by getting realm info
        realm_name = keycloak_admin.realm
        current_admin_realm = keycloak_admin.admin.realm_name
        logger.info(f"Testing connection - Target realm: {realm_name}, Admin client realm: {current_admin_realm}")
        
        # Verify realm match
        if current_admin_realm != realm_name:
            logger.warning(f"REALM MISMATCH: Admin client is in '{current_admin_realm}' but should be in '{realm_name}'")
        
        realm_info = keycloak_admin.admin.get_realm(realm_name)
        
        # Get all groups using REST API (more reliable)
        groups = keycloak_admin._get_all_groups_via_rest()
        
        users = keycloak_admin.admin.get_users()
        
        # Log all group names and paths for debugging
        all_group_names = [g.get('name') for g in groups]
        logger.info(f"Found {len(groups)} groups in realm '{current_admin_realm}': {all_group_names}")
        logger.info(f"Group details: {[(g.get('name'), g.get('path'), g.get('id')) for g in groups]}")
        
        # Test if we can get roles
        try:
            roles = keycloak_admin.admin.get_realm_roles()
            org_admin_role = next((r for r in roles if r.get("name") == "org-admin"), None)
            instructor_role = next((r for r in roles if r.get("name") == "instructor"), None)
        except Exception as role_error:
            roles = []
            org_admin_role = None
            instructor_role = None
            logger.warning(f"Could not fetch roles: {str(role_error)}")
        
        return {
            "status": "success",
            "target_realm": realm_name,
            "admin_client_realm": current_admin_realm,
            "realm_match": current_admin_realm == realm_name,
            "realm": realm_info.get("realm"),
            "realm_id": realm_info.get("id"),
            "total_groups": len(groups),
            "total_users": len(users),
            "groups": [{"name": g.get("name"), "path": g.get("path"), "id": g.get("id")} for g in groups[:10]],
            "roles_check": {
                "total_roles": len(roles),
                "all_roles": [r.get("name") for r in roles],
                "org-admin_exists": org_admin_role is not None,
                "instructor_exists": instructor_role is not None,
                "org-admin_id": org_admin_role.get("id") if org_admin_role else None,
                "instructor_id": instructor_role.get("id") if instructor_role else None
            }
        }
    except Exception as e:
        logger.error(f"Keycloak connection test failed: {str(e)}", exc_info=True)
        return {
            "status": "error", 
            "message": str(e),
            "error_type": type(e).__name__
        }


# ========== Request Models ==========

class CreateOrganizationRequest(BaseModel):
    org_name: str

class CreateOrgAdminRequest(BaseModel):
    org_name: str
    email: EmailStr
    password: str
    first_name: Optional[str] = ""
    last_name: Optional[str] = ""

class CreateInstructorRequest(BaseModel):
    org_name: str
    email: EmailStr
    password: str
    first_name: Optional[str] = ""
    last_name: Optional[str] = ""


# ========== Organization Management Endpoints ==========

@router.post("/organizations")
async def create_organization(
    request: CreateOrganizationRequest,
    user_id: str = Depends(require_role("superadmin"))
):
    """
    Create a new organization (group) with Admins and Instructors subgroups
    Only superadmin can create organizations
    """
    if not keycloak_admin:
        raise HTTPException(status_code=500, detail="Keycloak Admin service not available")
    
    try:
        result = keycloak_admin.setup_organization_with_roles(request.org_name)
        
        if not result:
            logger.error(f"setup_organization_with_roles returned None for {request.org_name}")
            raise HTTPException(status_code=400, detail=f"Failed to create organization: {request.org_name}. Check backend logs for details.")
        
        return {
            "message": f"Organization '{request.org_name}' created successfully",
            "organization": {
                "id": result["organization"].get("id"),
                "name": result["organization"].get("name")
            },
            "admins_group_id": result["admins_group"].get("id"),
            "instructors_group_id": result["instructors_group"].get("id")
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating organization: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error creating organization: {str(e)}")


@router.post("/organizations/{org_name}/complete-setup")
async def complete_org_setup(
    org_name: str,
    user_id: str = Depends(require_role("superadmin"))
):
    """
    Complete setup for an existing organization (add subgroups and roles if missing)
    Useful if organization was created but setup didn't complete
    """
    if not keycloak_admin:
        raise HTTPException(status_code=500, detail="Keycloak Admin service not available")
    
    try:
        # Get organization
        org = keycloak_admin.get_organization(org_name)
        if not org:
            raise HTTPException(status_code=404, detail=f"Organization {org_name} not found")
        
        org_id = org.get("id")
        
        # Check if subgroups exist using REST API
        org_groups = keycloak_admin._get_group_children_via_rest(org_id)
        admins_group = next((g for g in org_groups if g.get("name") == "Admins"), None)
        instructors_group = next((g for g in org_groups if g.get("name") == "Instructors"), None)
        
        # Create subgroups if they don't exist
        if not admins_group:
            logger.info(f"Creating Admins subgroup for {org_name}")
            admins_group_id = keycloak_admin.admin.create_group({"name": "Admins"}, parent=org_id)
            admins_group = keycloak_admin.admin.get_group(admins_group_id)
        
        if not instructors_group:
            logger.info(f"Creating Instructors subgroup for {org_name}")
            instructors_group_id = keycloak_admin.admin.create_group({"name": "Instructors"}, parent=org_id)
            instructors_group = keycloak_admin.admin.get_group(instructors_group_id)
        
        # Assign roles
        admins_role_success = keycloak_admin.assign_role_to_group(admins_group.get("id"), "org-admin")
        instructors_role_success = keycloak_admin.assign_role_to_group(instructors_group.get("id"), "instructor")
        
        return {
            "message": f"Setup completed for organization '{org_name}'",
            "organization": {
                "id": org.get("id"),
                "name": org.get("name")
            },
            "admins_group": {
                "id": admins_group.get("id"),
                "name": admins_group.get("name"),
                "role_assigned": admins_role_success
            },
            "instructors_group": {
                "id": instructors_group.get("id"),
                "name": instructors_group.get("name"),
                "role_assigned": instructors_role_success
            }
        }
    except Exception as e:
        logger.error(f"Error completing setup for {org_name}: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error completing setup: {str(e)}")


@router.get("/organizations")
async def list_organizations(
    user_id: str = Depends(require_role("superadmin"))
):
    """
    List all organizations
    Only superadmin can list organizations
    """
    if not keycloak_admin:
        raise HTTPException(status_code=500, detail="Keycloak Admin service not available")
    
    try:
        # Use REST API method to get all groups (more reliable)
        groups = keycloak_admin._get_all_groups_via_rest()
        logger.info(f"Total groups found: {len(groups)}")
        
        # Debug: log all groups to see their structure
        for g in groups[:5]:  # Log first 5 groups
            logger.info(f"Group: {g.get('name')}, Path: {g.get('path')}, ID: {g.get('id')}")
        
        # Filter to only top-level groups (organizations)
        # Top-level groups have paths like "/GroupName" (single level, no parent)
        # Subgroups have paths like "/ParentGroup/SubGroup" (multiple levels)
        organizations = []
        for g in groups:
            path = g.get("path", "")
            # Count path segments - top-level groups have exactly 1 segment (e.g., "/Atria University")
            # Empty path or path with only "/" means it's a special case
            if path:
                path_segments = [seg for seg in path.split("/") if seg.strip()]
                if len(path_segments) == 1:  # Top-level group
                    organizations.append(g)
        
        return {
            "organizations": [
                {
                    "id": org.get("id"),
                    "name": org.get("name"),
                    "path": org.get("path")
                }
                for org in organizations
            ],
            "debug": {
                "total_groups": len(groups),
                "top_level_groups": len(organizations)
            }
        }
    except Exception as e:
        logger.error(f"Error listing organizations: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error listing organizations: {str(e)}")


# ========== User Management Endpoints ==========

@router.post("/organizations/{org_name}/admin")
async def create_org_admin(
    org_name: str,
    request: CreateOrgAdminRequest,
    user_id: str = Depends(require_role("superadmin"))
):
    """
    Create an organization admin user
    User will be added to the org's Admins group and automatically get org-admin role
    Only superadmin can create org admins
    """
    if not keycloak_admin:
        raise HTTPException(status_code=500, detail="Keycloak Admin service not available")
    
    try:
        result = keycloak_admin.create_org_admin(
            org_name=org_name,
            email=request.email,
            password=request.password,
            first_name=request.first_name,
            last_name=request.last_name
        )
        
        if not result:
            raise HTTPException(status_code=400, detail=f"Failed to create org admin for {org_name}")
        
        return {
            "message": f"Organization admin created successfully",
            "user_id": result["user_id"],
            "email": result["email"],
            "org_name": result["org_name"]
        }
    except Exception as e:
        logger.error(f"Error creating org admin: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error creating org admin: {str(e)}")


@router.post("/organizations/{org_name}/instructor")
async def create_instructor(
    org_name: str,
    request: CreateInstructorRequest,
    user_id: str = Depends(require_role("superadmin"))
):
    """
    Create an instructor user
    User will be added to the org's Instructors group and automatically get instructor role
    Only superadmin can create instructors
    """
    if not keycloak_admin:
        raise HTTPException(status_code=500, detail="Keycloak Admin service not available")
    
    try:
        result = keycloak_admin.create_instructor(
            org_name=org_name,
            email=request.email,
            password=request.password,
            first_name=request.first_name,
            last_name=request.last_name
        )
        
        if not result:
            raise HTTPException(status_code=400, detail=f"Failed to create instructor for {org_name}")
        
        return {
            "message": f"Instructor created successfully",
            "user_id": result["user_id"],
            "email": result["email"],
            "org_name": result["org_name"]
        }
    except Exception as e:
        logger.error(f"Error creating instructor: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error creating instructor: {str(e)}")

