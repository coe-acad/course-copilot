"""
Google Authentication Authorization Service

Handles validation logic for Google Sign-In across three login types:
- superadmin: Only the configured SUPERADMIN_EMAIL allowed
- admin: Only exact match to registered org admin_email allowed
- user: Domain match to org's admin_email domain allowed (with auto-registration)
"""

import os
import logging
from typing import Optional
from .master_db import (
    get_superadmin_by_email,
    get_organization_by_admin_email,
    get_all_organizations,
    get_org_db,
)

logger = logging.getLogger(__name__)

# Get superadmin email from environment
SUPERADMIN_EMAIL = os.getenv("SUPERADMIN_EMAIL", "").lower().strip()


def get_email_domain(email: str) -> str:
    """Extract domain from email (e.g., 'user@example.com' -> 'example.com')"""
    if not email or "@" not in email:
        return ""
    return email.lower().split("@")[1]


def find_organization_by_domain(domain: str) -> Optional[dict]:
    """
    Find an organization whose admin email has the given domain.
    
    Args:
        domain: Email domain to match (e.g., 'christuniversity.com')
    
    Returns:
        Organization dict if found, None otherwise
    """
    if not domain:
        return None
    
    orgs = get_all_organizations()
    for org in orgs:
        admin_email = org.get("admin_email", "")
        if admin_email and get_email_domain(admin_email) == domain:
            return org
    
    return None


def validate_superadmin_login(email: str) -> dict:
    """
    Validate Google login for superadmin panel.
    Only the configured SUPERADMIN_EMAIL is allowed.
    """
    email_lower = email.lower().strip()
    
    if not SUPERADMIN_EMAIL:
        logger.error("SUPERADMIN_EMAIL not configured in environment")
        return {
            "allowed": False,
            "error": "SuperAdmin login is not configured",
            "org_id": None,
            "role": None
        }
    
    if email_lower == SUPERADMIN_EMAIL:
        # Check if superadmin exists in database
        superadmin = get_superadmin_by_email(email_lower)
        if superadmin:
            logger.info(f"SuperAdmin Google login allowed: {email}")
            return {
                "allowed": True,
                "error": None,
                "org_id": None,
                "role": "superadmin",
                "user_id": superadmin.get("_id"),
                "is_superadmin": True
            }
        else:
            logger.warning(f"Email matches SUPERADMIN_EMAIL but not in database: {email}")
            return {
                "allowed": False,
                "error": "SuperAdmin account not found in database",
                "org_id": None,
                "role": None
            }
    
    logger.warning(f"Unauthorized superadmin login attempt: {email}")
    return {
        "allowed": False,
        "error": "This email is not authorized for SuperAdmin access",
        "org_id": None,
        "role": None
    }


def validate_admin_login(email: str) -> dict:
    """
    Validate Google login for admin panel.
    Only exact match to a registered organization's admin_email is allowed.
    """
    email_lower = email.lower().strip()
    
    org = get_organization_by_admin_email(email_lower)
    
    if org:
        logger.info(f"Admin Google login allowed: {email} for org: {org.get('name')}")
        return {
            "allowed": True,
            "error": None,
            "org_id": org.get("_id"),
            "org_name": org.get("name"),
            "database_name": org.get("database_name"),
            "role": "admin",
            "user_id": org.get("admin_user_id"),
            "is_superadmin": False
        }
    
    logger.warning(f"Unauthorized admin login attempt: {email}")
    return {
        "allowed": False,
        "error": "This email is not registered as an admin",
        "org_id": None,
        "role": None
    }


def validate_user_login(email: str) -> dict:
    """
    Validate Google login for normal user portal.
    Email domain must match an organization's admin email domain.
    If valid, returns org info for auto-registration if needed.
    """
    email_lower = email.lower().strip()
    domain = get_email_domain(email_lower)
    
    if not domain:
        return {
            "allowed": False,
            "error": "Invalid email format",
            "org_id": None,
            "role": None
        }
    
    org = find_organization_by_domain(domain)
    
    if org:
        logger.info(f"User Google login allowed: {email} for org: {org.get('name')} (domain: {domain})")
        return {
            "allowed": True,
            "error": None,
            "org_id": org.get("_id"),
            "org_name": org.get("name"),
            "database_name": org.get("database_name"),
            "role": "user",
            "domain": domain,
            "is_superadmin": False
        }
    
    logger.warning(f"No organization found for domain: {domain} (email: {email})")
    return {
        "allowed": False,
        "error": f"No organization found for email domain @{domain}",
        "org_id": None,
        "role": None
    }


def validate_google_login(email: str, login_type: str) -> dict:
    """
    Main validation function for Google login.
    
    Args:
        email: Google account email
        login_type: "superadmin" | "admin" | "user"
    
    Returns:
        dict with: allowed, error, org_id, org_name, database_name, role, is_superadmin
    """
    login_type = login_type.lower().strip() if login_type else "user"
    
    if login_type == "superadmin":
        return validate_superadmin_login(email)
    elif login_type == "admin":
        return validate_admin_login(email)
    else:
        return validate_user_login(email)
