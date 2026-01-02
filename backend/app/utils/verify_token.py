from firebase_admin import auth
from fastapi import HTTPException, Header
import logging

logger = logging.getLogger(__name__)

def verify_token(authorization: str = Header(...)) -> str:
    try:
        decoded_token = auth.verify_id_token(authorization.replace("Bearer ", ""))
        return decoded_token["uid"]
    except Exception as e:
        logger.error(f"Token verification failed: {str(e)}")
        raise HTTPException(status_code=401, detail="Invalid or expired token")

def verify_admin(authorization: str = Header(...)) -> str:
    """Verify token and check if user has admin role (in org database or default database)"""
    from ..services.mongo import get_user_by_user_id
    from ..services.master_db import get_organization_by_user_id, get_org_db
    
    try:
        # First verify the token
        decoded_token = auth.verify_id_token(authorization.replace("Bearer ", ""))
        user_id = decoded_token["uid"]
        
        logger.info(f"Verifying admin access for user: {user_id}")
        
        # First check if user is in an organization database
        org = get_organization_by_user_id(user_id)
        if org:
            org_db_name = org.get("database_name")
            org_db = get_org_db(org_db_name)
            user = org_db["users"].find_one({"_id": user_id})
            
            if user:
                user_role = user.get("role", "user")
                logger.info(f"User {user_id} found in org {org.get('name')} with role: {user_role}")
                
                if user_role == "admin":
                    logger.info(f"Admin access granted for user: {user_id} (org: {org.get('name')})")
                    return user_id
        
        # Fall back to checking default database (legacy support)
        user = get_user_by_user_id(user_id)
        if user:
            user_role = user.get("role", "user")
            logger.info(f"User {user_id} found in default db with role: {user_role}")
            
            if user_role == "admin":
                logger.info(f"Admin access granted for user: {user_id} (default db)")
                return user_id
        
        # User not found or not admin
        logger.warning(f"User {user_id} does not have admin privileges")
        raise HTTPException(status_code=403, detail="Access denied. You don't have admin privileges.")
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Admin verification failed: {str(e)}")
        raise HTTPException(status_code=401, detail="Invalid or expired token")


def verify_super_admin(authorization: str = Header(...)) -> str:
    """Verify token and check if user is a superadmin (from master database)"""
    from ..services.master_db import is_superadmin
    
    try:
        # First verify the token
        decoded_token = auth.verify_id_token(authorization.replace("Bearer ", ""))
        user_id = decoded_token["uid"]
        
        logger.info(f"Verifying superadmin access for user: {user_id}")
        
        # Check if user is a superadmin in master database
        if not is_superadmin(user_id):
            logger.warning(f"User {user_id} attempted to access superadmin endpoint - DENIED")
            raise HTTPException(status_code=403, detail="SuperAdmin access required.")
        
        logger.info(f"SuperAdmin access granted for user: {user_id}")
        return user_id
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"SuperAdmin verification failed: {str(e)}")
        raise HTTPException(status_code=401, detail="Invalid or expired token")


def get_user_org_context(authorization: str = Header(...)) -> dict:
    """
    Verify token and return user context including organization info.
    Returns: {user_id, org_id, org_db_name, role, is_superadmin}
    """
    from ..services.master_db import is_superadmin, get_organization_by_user_id, get_org_db
    
    try:
        decoded_token = auth.verify_id_token(authorization.replace("Bearer ", ""))
        user_id = decoded_token["uid"]
        
        # Check if superadmin
        if is_superadmin(user_id):
            return {
                "user_id": user_id,
                "org_id": None,
                "org_db_name": None,
                "role": "superadmin",
                "is_superadmin": True
            }
        
        # Get user's organization
        org = get_organization_by_user_id(user_id)
        if not org:
            logger.warning(f"User {user_id} does not belong to any organization")
            raise HTTPException(status_code=403, detail="User not associated with any organization")
        
        org_db_name = org.get("database_name")
        org_db = get_org_db(org_db_name)
        
        # Get user's role from org database
        user = org_db["users"].find_one({"_id": user_id})
        role = user.get("role", "user") if user else "user"
        
        return {
            "user_id": user_id,
            "org_id": org.get("_id"),
            "org_db_name": org_db_name,
            "role": role,
            "is_superadmin": False
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get user org context: {str(e)}")
        raise HTTPException(status_code=401, detail="Invalid or expired token")


def verify_admin_with_org_context(authorization: str = Header(...)) -> dict:
    """
    Verify token, check admin role, and return context with org database info.
    Returns: {user_id, org_id, org_db_name, org_name}
    """
    from ..services.mongo import get_user_by_user_id
    from ..services.master_db import get_organization_by_user_id, get_org_db
    
    try:
        decoded_token = auth.verify_id_token(authorization.replace("Bearer ", ""))
        user_id = decoded_token["uid"]
        
        logger.info(f"Verifying admin access with org context for user: {user_id}")
        
        # First check if user is in an organization database
        org = get_organization_by_user_id(user_id)
        if org:
            org_db_name = org.get("database_name")
            org_db = get_org_db(org_db_name)
            user = org_db["users"].find_one({"_id": user_id})
            
            if user and user.get("role") == "admin":
                logger.info(f"Admin access granted for user: {user_id} (org: {org.get('name')})")
                return {
                    "user_id": user_id,
                    "org_id": org.get("_id"),
                    "org_db_name": org_db_name,
                    "org_name": org.get("name")
                }
        
        # Fall back to checking default database (legacy support)
        user = get_user_by_user_id(user_id)
        if user and user.get("role") == "admin":
            logger.info(f"Admin access granted for user: {user_id} (default db)")
            return {
                "user_id": user_id,
                "org_id": None,
                "org_db_name": None,
                "org_name": None
            }
        
        # User not found or not admin
        logger.warning(f"User {user_id} does not have admin privileges")
        raise HTTPException(status_code=403, detail="Access denied. You don't have admin privileges.")
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Admin verification with org context failed: {str(e)}")
        raise HTTPException(status_code=401, detail="Invalid or expired token")