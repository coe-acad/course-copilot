"""
Initialize First SuperAdmin

This script creates the first superadmin user in the master database.
Run this once to bootstrap the system.

Usage:
    python -m app.utils.init_superadmin <email> <password>
"""

import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from firebase_admin import auth as firebase_auth
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def create_first_superadmin(email: str, password: str, display_name: str = "SuperAdmin"):
    """Create the first superadmin user"""
    # Import here to ensure Firebase is initialized
    from app.services.master_db import create_superadmin, get_superadmin_by_email
    
    # Check if superadmin already exists
    existing = get_superadmin_by_email(email)
    if existing:
        logger.info(f"SuperAdmin with email {email} already exists")
        return existing
    
    try:
        # Create Firebase user
        firebase_user = firebase_auth.create_user(
            email=email,
            password=password,
            display_name=display_name
        )
        user_id = firebase_user.uid
        logger.info(f"Created Firebase user: {email} with UID: {user_id}")
    except Exception as e:
        # User might already exist in Firebase
        try:
            firebase_user = firebase_auth.get_user_by_email(email)
            user_id = firebase_user.uid
            logger.info(f"Using existing Firebase user: {email}")
        except Exception as e2:
            logger.error(f"Failed to create/get Firebase user: {str(e2)}")
            raise
    
    # Create superadmin in master database
    create_superadmin(
        user_id=user_id,
        email=email,
        display_name=display_name
    )
    
    logger.info(f"✅ SuperAdmin created successfully!")
    logger.info(f"   Email: {email}")
    logger.info(f"   User ID: {user_id}")
    logger.info(f"   Login at: /superadmin")
    
    return {"user_id": user_id, "email": email}


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python -m app.utils.init_superadmin <email> <password> [display_name]")
        print("Example: python -m app.utils.init_superadmin admin@example.com mypassword123")
        sys.exit(1)
    
    email = sys.argv[1]
    password = sys.argv[2]
    display_name = sys.argv[3] if len(sys.argv) > 3 else "SuperAdmin"
    
    result = create_first_superadmin(email, password, display_name)
    print(f"\nSuperAdmin ready: {result}")
