"""
Keycloak token verification dependency for FastAPI routes
Replaces Firebase verify_token with Keycloak JWT verification
"""
from fastapi import HTTPException, Header
import logging
from typing import Optional
from ..services.keycloak_service import keycloak_service

logger = logging.getLogger(__name__)


def verify_keycloak_token(authorization: str = Header(...)) -> str:
    """
    Verify Keycloak JWT token and return user ID (sub)
    Replaces Firebase verify_token
    """
    try:
        # Extract token from "Bearer <token>"
        if not authorization.startswith("Bearer "):
            raise HTTPException(status_code=401, detail="Invalid authorization header format")
        
        token = authorization.replace("Bearer ", "").strip()
        
        if not token:
            raise HTTPException(status_code=401, detail="Token not provided")
        
        # Verify token using Keycloak service
        decoded_token = keycloak_service.verify_token(token)
        
        if not decoded_token:
            raise HTTPException(status_code=401, detail="Invalid or expired token")
        
        # Extract user ID (sub claim)
        user_id = decoded_token.get("sub")
        if not user_id:
            raise HTTPException(status_code=401, detail="Token missing user ID")
        
        return user_id
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Token verification failed: {str(e)}")
        raise HTTPException(status_code=401, detail="Token verification failed")


def get_user_roles(authorization: str = Header(...)) -> list[str]:
    """
    Extract user roles from Keycloak token
    Useful for role-based access control
    """
    try:
        token = authorization.replace("Bearer ", "").strip()
        roles = keycloak_service.get_user_roles(token)
        return roles
    except Exception as e:
        logger.error(f"Failed to get user roles: {str(e)}")
        return []


def require_role(required_role: str):
    """
    Dependency factory to require a specific role
    Usage: @app.get("/admin", dependencies=[Depends(require_role("superadmin"))])
    """
    def role_checker(authorization: str = Header(...)) -> str:
        token = authorization.replace("Bearer ", "").strip()
        
        # First verify token
        decoded_token = keycloak_service.verify_token(token)
        if not decoded_token:
            logger.error("Token verification failed in require_role")
            raise HTTPException(status_code=401, detail="Invalid token")
        
        # Extract roles from decoded token
        roles = keycloak_service.get_user_roles(token)
        logger.info(f"User roles: {roles}, Required role: {required_role}")
        
        if required_role not in roles:
            logger.warning(f"User missing required role. Has: {roles}, Needs: {required_role}")
            raise HTTPException(status_code=403, detail=f"Required role: {required_role}")
        
        # Return user ID if role check passes
        return decoded_token.get("sub")
    
    return role_checker

