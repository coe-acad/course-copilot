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
    """Verify token and check if user has admin role"""
    from ..services.mongo import get_user_by_user_id
    
    try:
        # First verify the token
        decoded_token = auth.verify_id_token(authorization.replace("Bearer ", ""))
        user_id = decoded_token["uid"]
        
        logger.info(f"Verifying admin access for user: {user_id}")
        
        # Check user role in database
        user = get_user_by_user_id(user_id)
        if not user:
            logger.warning(f"User {user_id} not found in database")
            raise HTTPException(status_code=403, detail="User not found")
        
        user_role = user.get("role", "user")  # Default to "user" if role not set
        logger.info(f"User {user_id} has role: {user_role}")
        
        if user_role != "admin":
            logger.warning(f"User {user_id} (role: {user_role}) attempted to access admin endpoint - DENIED")
            raise HTTPException(status_code=403, detail="Admin access required. You must have admin role to access this area.")
        
        logger.info(f"Admin access granted for user: {user_id}")
        return user_id
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Admin verification failed: {str(e)}")
        raise HTTPException(status_code=401, detail="Invalid or expired token")