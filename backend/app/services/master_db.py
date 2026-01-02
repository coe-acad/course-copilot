"""
Master Database Service

Handles operations on the master database containing:
- superadmins: SuperAdmin users (global access)
- organizations: All organizations with their database names

Organization databases are separate and created via create_new_organization_database()
"""

import logging
from datetime import datetime
from typing import Optional, List
from pymongo import MongoClient
from pymongo.server_api import ServerApi
from uuid import uuid4
from firebase_admin import auth as firebase_auth
import re

logger = logging.getLogger(__name__)

# Use same connection as mongo.py
uri = "mongodb+srv://acad:nPyjuhmdeIgTxySD@creators-copilot-demo.aoq6p75.mongodb.net/?retryWrites=true&w=majority&appName=creators-copilot-demo&tls=true&tlsAllowInvalidCertificates=true"
client = MongoClient(uri, server_api=ServerApi('1'))

# Master database - stores superadmins and organization registry
master_db = client["creators-copilot-master"]

# Collections
superadmins_collection = master_db["superadmins"]
organizations_collection = master_db["organizations"]


# ============== SUPERADMIN OPERATIONS ==============

def create_superadmin(user_id: str, email: str, display_name: str = None):
    """Create a superadmin user in the master database"""
    superadmin_data = {
        "_id": user_id,
        "email": email,
        "display_name": display_name,
        "role": "superadmin",
        "created_at": datetime.utcnow().isoformat()
    }
    superadmins_collection.insert_one(superadmin_data)
    logger.info(f"Created superadmin: {email}")
    return user_id


def get_superadmin_by_user_id(user_id: str):
    """Get superadmin by Firebase user ID"""
    doc = superadmins_collection.find_one({"_id": user_id})
    if doc and '_id' in doc:
        doc['_id'] = str(doc['_id'])
    return doc


def get_superadmin_by_email(email: str):
    """Get superadmin by email"""
    doc = superadmins_collection.find_one({"email": email})
    if doc and '_id' in doc:
        doc['_id'] = str(doc['_id'])
    return doc


def is_superadmin(user_id: str) -> bool:
    """Check if user is a superadmin"""
    return get_superadmin_by_user_id(user_id) is not None


def get_all_superadmins() -> List[dict]:
    """Get all superadmins"""
    docs = []
    for doc in superadmins_collection.find():
        if '_id' in doc:
            doc['_id'] = str(doc['_id'])
        docs.append(doc)
    return docs


# ============== ORGANIZATION OPERATIONS ==============

def create_organization(org_name: str, admin_email: str, admin_password: str = None) -> dict:
    """
    Create a new organization with its own database and admin user.
    
    Args:
        org_name: Name of the organization
        admin_email: Email for the organization's admin user
        admin_password: Password for admin (if creating Firebase user)
    
    Returns:
        dict with org_id, database_name, admin_user_id
    """
    from .mongo import create_new_organization_database
    
    org_id = str(uuid4())
    
    # Create database name from org name (sanitize for MongoDB)
    db_name = re.sub(r'[^a-zA-Z0-9_-]', '_', org_name.lower())
    db_name = f"org_{db_name}_{org_id[:8]}"
    
    logger.info(f"Creating organization: {org_name} with database: {db_name}")
    
    # Create the organization's database with all collections
    db_result = create_new_organization_database(org_name, org_id)
    
    # Create admin user in Firebase
    try:
        firebase_user = firebase_auth.create_user(
            email=admin_email,
            password=admin_password or str(uuid4())[:12],  # Generate random password if not provided
            display_name=f"{org_name} Admin"
        )
        admin_user_id = firebase_user.uid
        logger.info(f"Created Firebase admin user: {admin_email} with UID: {admin_user_id}")
    except Exception as e:
        # User might already exist
        try:
            firebase_user = firebase_auth.get_user_by_email(admin_email)
            admin_user_id = firebase_user.uid
            logger.info(f"Using existing Firebase user: {admin_email}")
        except Exception as e2:
            logger.error(f"Failed to create/get Firebase user: {str(e2)}")
            raise Exception(f"Failed to create admin user: {str(e2)}")
    
    # Store organization in master database
    org_data = {
        "_id": org_id,
        "name": org_name,
        "database_name": db_name,
        "admin_user_id": admin_user_id,
        "admin_email": admin_email,
        "created_at": datetime.utcnow().isoformat(),
        "status": "active"
    }
    organizations_collection.insert_one(org_data)
    
    # Create admin user in organization's database
    org_db = client[db_name]
    org_db["users"].insert_one({
        "_id": admin_user_id,
        "email": admin_email,
        "display_name": f"{org_name} Admin",
        "role": "admin",
        "created_at": datetime.utcnow().isoformat()
    })
    
    logger.info(f"✅ Organization '{org_name}' created successfully")
    
    return {
        "org_id": org_id,
        "org_name": org_name,
        "database_name": db_name,
        "admin_user_id": admin_user_id,
        "admin_email": admin_email
    }


def get_organization_by_id(org_id: str) -> Optional[dict]:
    """Get organization by ID"""
    doc = organizations_collection.find_one({"_id": org_id})
    if doc and '_id' in doc:
        doc['_id'] = str(doc['_id'])
    return doc


def get_organization_by_admin_email(admin_email: str) -> Optional[dict]:
    """Get organization by admin email"""
    doc = organizations_collection.find_one({"admin_email": admin_email})
    if doc and '_id' in doc:
        doc['_id'] = str(doc['_id'])
    return doc


def get_organization_by_user_id(user_id: str) -> Optional[dict]:
    """
    Find which organization a user belongs to by searching all org databases.
    This is used during login to resolve the user's tenant.
    """
    # First check if user is an org admin in master DB
    org = organizations_collection.find_one({"admin_user_id": user_id})
    if org:
        if '_id' in org:
            org['_id'] = str(org['_id'])
        return org
    
    # Search through all organization databases
    for org_doc in organizations_collection.find():
        db_name = org_doc.get("database_name")
        if db_name:
            org_db = client[db_name]
            user = org_db["users"].find_one({"_id": user_id})
            if user:
                if '_id' in org_doc:
                    org_doc['_id'] = str(org_doc['_id'])
                return org_doc
    
    return None


def get_all_organizations() -> List[dict]:
    """Get all organizations"""
    docs = []
    for doc in organizations_collection.find():
        if '_id' in doc:
            doc['_id'] = str(doc['_id'])
        # Get user count from org database
        db_name = doc.get("database_name")
        if db_name:
            try:
                org_db = client[db_name]
                doc["user_count"] = org_db["users"].count_documents({})
            except:
                doc["user_count"] = 0
        docs.append(doc)
    return docs


def delete_organization(org_id: str) -> bool:
    """Delete an organization and its database"""
    org = get_organization_by_id(org_id)
    if not org:
        return False
    
    db_name = org.get("database_name")
    
    # Drop the organization's database
    if db_name:
        try:
            client.drop_database(db_name)
            logger.info(f"Dropped database: {db_name}")
        except Exception as e:
            logger.error(f"Failed to drop database {db_name}: {str(e)}")
    
    # Remove from organizations collection
    organizations_collection.delete_one({"_id": org_id})
    logger.info(f"Deleted organization: {org_id}")
    
    return True


# ============== TENANT RESOLUTION ==============

def get_user_org_database(user_id: str) -> Optional[str]:
    """
    Get the database name for a user's organization.
    Returns None if user is a superadmin or not found.
    """
    # Check if superadmin (they don't belong to any org)
    if is_superadmin(user_id):
        return None
    
    org = get_organization_by_user_id(user_id)
    if org:
        return org.get("database_name")
    
    return None


def get_org_db(database_name: str):
    """Get a database reference by name"""
    return client[database_name]


# ============== PAYMENT CONFIGURATION ==============

# Payment config collection in master database
payment_config_collection = master_db["payment_config"]

def get_payment_config() -> Optional[dict]:
    """Get the global payment configuration (price per user)"""
    config = payment_config_collection.find_one({"_id": "global_payment_config"})
    if config and '_id' in config:
        config['_id'] = str(config['_id'])
    return config


def set_payment_config(price_per_user_paise: int, currency: str = "INR") -> dict:
    """
    Set the global payment configuration.
    
    Args:
        price_per_user_paise: Price per user in paise (e.g., 50000 = ₹500.00)
        currency: Currency code (default: INR)
    
    Returns:
        The updated payment config
    """
    config_data = {
        "_id": "global_payment_config",
        "price_per_user_paise": price_per_user_paise,
        "currency": currency,
        "updated_at": datetime.utcnow().isoformat()
    }
    
    # Upsert the config
    payment_config_collection.update_one(
        {"_id": "global_payment_config"},
        {"$set": config_data},
        upsert=True
    )
    
    logger.info(f"Updated payment config: ₹{price_per_user_paise / 100} per user")
    return config_data

