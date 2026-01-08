import logging
from datetime import datetime
from typing import List, Optional
from pymongo import MongoClient
from pymongo.database import Database
from pymongo.collection import Collection
from pymongo.errors import PyMongoError
from pymongo.server_api import ServerApi
from uuid import uuid4
import gridfs
from bson import ObjectId
from fastapi import HTTPException

uri = "mongodb+srv://acad:nPyjuhmdeIgTxySD@creators-copilot-demo.aoq6p75.mongodb.net/?retryWrites=true&w=majority&appName=creators-copilot-demo&tls=true&tlsAllowInvalidCertificates=true"
# Create a new client and connect to the server
client = MongoClient(uri, server_api=ServerApi('1'))
# Send a ping to confirm a successful connection
try:
    client.admin.command('ping')
    print("Pinged your deployment. You successfully connected to MongoDB!")
except Exception as e:
    print(e)

db = client["creators-copilot-demo"]

# Initialize GridFS for file storage
fs = gridfs.GridFS(db)

logger = logging.getLogger(__name__)


# ============== ORG-AWARE DATABASE HELPERS ==============

def get_org_collection(collection_name: str, org_db_name: str = None) -> Collection:
    """
    Get collection from organization database or default database.
    
    Args:
        collection_name: Name of the collection
        org_db_name: Organization database name (if None, uses default db)
    
    Returns:
        MongoDB Collection object
    """
    if org_db_name:
        return client[org_db_name][collection_name]
    return db[collection_name]


def get_org_gridfs(org_db_name: str = None):
    """
    Get GridFS instance for organization database or default database.
    
    Args:
        org_db_name: Organization database name (if None, uses default db)
    
    Returns:
        GridFS instance
    """
    if org_db_name:
        return gridfs.GridFS(client[org_db_name])
    return fs


# ============== BASE CRUD OPERATIONS (ORG-AWARE) ==============

def add_to_collection(collection_name: str, data: dict, org_db_name: str = None):
    collection = get_org_collection(collection_name, org_db_name)
    collection.insert_one(data)

def get_one_from_collection(collection_name: str, query: dict, org_db_name: str = None):
    collection = get_org_collection(collection_name, org_db_name)
    doc = collection.find_one(query)
    if doc and '_id' in doc:
        doc['_id'] = str(doc['_id'])
    return doc

def get_many_from_collection(collection_name: str, query: dict, org_db_name: str = None):
    docs = []
    collection = get_org_collection(collection_name, org_db_name)
    for doc in collection.find(query):
        # Convert ObjectId to string for JSON serialization
        if '_id' in doc:
            doc['_id'] = str(doc['_id'])
        docs.append(doc)
    return docs

def update_in_collection(collection_name: str, query: dict, data: dict, org_db_name: str = None):
    collection = get_org_collection(collection_name, org_db_name)
    collection.update_one(query, {"$set": data})

def delete_from_collection(collection_name: str, query: dict, org_db_name: str = None):
    collection = get_org_collection(collection_name, org_db_name)
    collection.delete_one(query)

# Users
def create_user(user_id: str, email: str, display_name: str = None, role: str = "user", org_db_name: str = None):
    user_data = {"_id": user_id, "email": email, "role": role}
    if display_name:
        user_data["display_name"] = display_name
    add_to_collection("users", user_data, org_db_name)

def update_user_role(user_id: str, role: str, org_db_name: str = None):
    """Update user's role"""
    update_in_collection("users", {"_id": user_id}, {"role": role}, org_db_name)

def delete_user(user_id: str, org_db_name: str = None):
    """Delete a user"""
    delete_from_collection("users", {"_id": user_id}, org_db_name)

def get_user_by_user_id(user_id: str, org_db_name: str = None):
    return get_one_from_collection("users", {"_id": user_id}, org_db_name)

def get_email_by_user_id(user_id: str, org_db_name: str = None):
    user_doc = get_one_from_collection("users", {"_id": user_id}, org_db_name)
    if not user_doc:
        return None
    return user_doc.get("email")

def get_user_display_name(user_id: str, org_db_name: str = None):
    """Get user's display name, falls back to email if display_name not available"""
    user_doc = get_one_from_collection("users", {"_id": user_id}, org_db_name)
    if not user_doc:
        return None
    # Prefer display_name, fallback to email
    return user_doc.get("display_name") or user_doc.get("email")

def get_user_by_email(email: str, org_db_name: str = None):
    """Get user by email address"""
    return get_one_from_collection("users", {"email": email}, org_db_name)

def get_all_users(org_db_name: str = None):
    """Get all users from organization or default database"""
    return get_many_from_collection("users", {}, org_db_name)

# Organization Databases
def create_new_organization_database(org_name: str, org_id: str = None):
    """
    Create a complete new database for an organization with all collections and default data.
    This will be used when multi-organization support is added.
    
    Args:
        org_name: Name of the organization
        org_id: Optional organization ID (generates UUID if not provided)
    
    Returns:
        dict: Contains database name, organization ID, and status
    """
    import re
    from datetime import datetime
    
    logger = logging.getLogger(__name__)
    
    try:
        # Generate org_id if not provided
        if not org_id:
            org_id = str(uuid4())
        
        # Create database name from org name (sanitize for MongoDB)
        db_name = re.sub(r'[^a-zA-Z0-9_-]', '_', org_name.lower())
        db_name = f"org_{db_name}_{org_id[:8]}"
        
        logger.info(f"Creating new organization database: {db_name}")
        
        # Create new database reference
        new_db = client[db_name]
        
        # Initialize GridFS for the new database
        new_fs = gridfs.GridFS(new_db)
        
        # Define all collections that need to be created
        collections_to_create = [
            "users",
            "courses",
            "course_shares",
            "resources",
            "assets",
            "evaluations",
            "extracted_data",
            "ai_feedback",
            "system_configurations",
            "admin_files"
        ]
        
        # Create collections
        created_collections = []
        for collection_name in collections_to_create:
            new_db.create_collection(collection_name)
            created_collections.append(collection_name)
            logger.info(f"Created collection: {collection_name}")
        
        # Seed system_configurations with default data
        default_configs = get_default_system_configurations()
        for config in default_configs:
            new_db["system_configurations"].insert_one(config)
        logger.info(f"Seeded {len(default_configs)} system configurations")
        
        # Create indexes for better performance
        create_database_indexes(new_db)
        logger.info("Created database indexes")
        
        # Create organization metadata document
        org_metadata = {
            "_id": org_id,
            "org_name": org_name,
            "database_name": db_name,
            "created_at": datetime.utcnow().isoformat(),
            "status": "active"
        }
        
        logger.info(f"✅ Successfully created organization database: {db_name}")
        
        return {
            "success": True,
            "org_id": org_id,
            "org_name": org_name,
            "database_name": db_name,
            "collections_created": created_collections,
            "configurations_seeded": len(default_configs),
            "metadata": org_metadata
        }
        
    except Exception as e:
        logger.error(f"Error creating organization database: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to create organization database: {str(e)}")

def get_default_system_configurations():
    """
    Returns default system configurations to be seeded in new organization databases.
    """
    curriculum_configs = [
        {
            "_id": "curr-brainstorm",
            "type": "curriculum",
            "key": "brainstorm",
            "label": "Brainstorm",
            "desc": "Generate and organize initial ideas for your course curriculum.",
            "url": "brainstorm",
            "order": 1
        },
        {
            "_id": "curr-course-outcomes",
            "type": "curriculum",
            "key": "course-outcomes",
            "label": "Course Outcomes",
            "desc": "Set clear learning goals students are expected to achieve by the end of the course.",
            "url": "course-outcomes",
            "order": 2
        },
        {
            "_id": "curr-modules",
            "type": "curriculum",
            "key": "modules",
            "label": "Modules",
            "desc": "Organize content into structured modules and focused topics for easy navigation.",
            "url": "modules",
            "order": 3
        },
        {
            "_id": "curr-lecture",
            "type": "curriculum",
            "key": "lecture",
            "label": "Lecture",
            "desc": "Plan each session with defined objectives, activities, and resources.",
            "url": "lecture",
            "order": 4
        },
        {
            "_id": "curr-course-notes",
            "type": "curriculum",
            "key": "course-notes",
            "label": "Course Notes",
            "desc": "Add notes to support student understanding and revision.",
            "url": "course-notes",
            "order": 5
        },
        {
            "_id": "curr-concept-plan",
            "type": "curriculum",
            "key": "concept-plan",
            "label": "Concept Plan",
            "desc": "Generate a session-by-session concept plan aligned with best-practice learning design.",
            "url": "concept-plan",
            "order": 6
        }
    ]
    
    assessment_configs = [
        {
            "_id": "assess-project",
            "type": "assessment",
            "key": "project",
            "label": "Project",
            "desc": "Encourage deep learning through hands-on, outcome-driven assignments.",
            "url": "project",
            "order": 1
        },
        {
            "_id": "assess-activity",
            "type": "assessment",
            "key": "activity",
            "label": "Activity",
            "desc": "Engage students with interactive tasks that reinforce learning through application.",
            "url": "activity",
            "order": 2
        },
        {
            "_id": "assess-quiz",
            "type": "assessment",
            "key": "quiz",
            "label": "Quiz",
            "desc": "Assess student understanding with short, focused questions on key concepts.",
            "url": "quiz",
            "order": 3
        },
        {
            "_id": "assess-question-paper",
            "type": "assessment",
            "key": "question-paper",
            "label": "Question Paper",
            "desc": "Create formal assessments to evaluate overall learning and subject mastery.",
            "url": "question-paper",
            "order": 4
        },
        {
            "_id": "assess-mark-scheme",
            "type": "assessment",
            "key": "mark-scheme",
            "label": "Mark Scheme",
            "desc": "Create detailed marking criteria and rubrics for fair and consistent assessment.(Select the Question Paper to generate the Mark Scheme)",
            "url": "mark-scheme",
            "order": 5
        },
        {
            "_id": "assess-mock-interview",
            "type": "assessment",
            "key": "mock-interview",
            "label": "Mock Interview",
            "desc": "Simulate real-world interviews to prepare students for job readiness.",
            "url": "mock-interview",
            "order": 6
        }
    ]
    
    settings_configs = [
        {
            "_id": "setting-course-level",
            "type": "setting",
            "category": "course_level",
            "label": "Course level",
            "options": ["Year 1", "Year 2", "Year 3", "Year 4"]
        },
        {
            "_id": "setting-study-area",
            "type": "setting",
            "category": "study_area",
            "label": "Study area",
            "options": [
                "AI & Decentralised Technologies",
                "Life Sciences",
                "Energy Sciences",
                "eMobility",
                "Climate Change",
                "Connected Intelligence"
            ]
        },
        {
            "_id": "setting-pedagogical",
            "type": "setting",
            "category": "pedagogical_components",
            "label": "Pedagogical Components",
            "options": [
                "Theory",
                "Project",
                "Research",
                "Laboratory Experiments",
                "Unplugged Activities",
                "Programming Activities"
            ]
        }
    ]
    
    return curriculum_configs + assessment_configs + settings_configs

def create_database_indexes(database):
    """
    Create indexes for better query performance in the new database.
    """
    logger = logging.getLogger(__name__)
    
    try:
        # Users collection indexes
        database["users"].create_index("email", unique=True)
        database["users"].create_index("role")
        
        # Courses collection indexes
        database["courses"].create_index("user_id")
        database["courses"].create_index("created_at")
        
        # Course shares indexes
        database["course_shares"].create_index([("course_id", 1), ("shared_with_user_id", 1)], unique=True)
        database["course_shares"].create_index("shared_with_user_id")
        
        # Resources indexes
        database["resources"].create_index("course_id")
        database["resources"].create_index([("course_id", 1), ("resource_name", 1)])
        
        # Assets indexes
        database["assets"].create_index("course_id")
        database["assets"].create_index([("course_id", 1), ("asset_type", 1)])
        database["assets"].create_index([("course_id", 1), ("asset_name", 1)])
        
        # Evaluations indexes
        database["evaluations"].create_index("evaluation_id", unique=True)
        database["evaluations"].create_index("course_id")
        
        # Extracted data indexes
        database["extracted_data"].create_index("evaluation_id", unique=True)
        
        # AI feedback indexes
        database["ai_feedback"].create_index("evaluation_id", unique=True)
        
        # System configurations indexes
        database["system_configurations"].create_index("type")
        database["system_configurations"].create_index([("type", 1), ("category", 1)])
        
        # Admin files indexes
        database["admin_files"].create_index("created_at")
        
        logger.info("Successfully created all database indexes")
        
    except Exception as e:
        logger.warning(f"Error creating indexes (non-critical): {str(e)}")

def get_organization_database(org_id: str = None, database_name: str = None):
    """
    Get a database reference for a specific organization.
    Can be called with either org_id or database_name.
    
    Args:
        org_id: Organization ID (will search for database with this org_id)
        database_name: Direct database name
    
    Returns:
        Database object for the organization
    """
    logger = logging.getLogger(__name__)
    
    try:
        if database_name:
            return client[database_name]
        elif org_id:
            # List all databases and find the one matching org_id
            db_list = client.list_database_names()
            for db_name in db_list:
                if org_id[:8] in db_name and db_name.startswith("org_"):
                    return client[db_name]
            raise HTTPException(status_code=404, detail=f"Database for organization {org_id} not found")
        else:
            raise HTTPException(status_code=400, detail="Either org_id or database_name must be provided")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting organization database: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to get organization database: {str(e)}")

def list_all_organization_databases():
    """
    List all organization databases in the MongoDB instance.
    Useful for admin purposes and migration.
    
    Returns:
        list: List of organization database names
    """
    logger = logging.getLogger(__name__)
    
    try:
        all_databases = client.list_database_names()
        # Filter for organization databases (start with "org_")
        org_databases = [db for db in all_databases if db.startswith("org_")]
        
        logger.info(f"Found {len(org_databases)} organization databases")
        return org_databases
        
    except Exception as e:
        logger.error(f"Error listing organization databases: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to list organization databases: {str(e)}")

# Courses
def create_course(data: dict, org_db_name: str = None):
    course_id = str(uuid4())
    add_to_collection(
        "courses",
        {
            "_id": course_id,
            "created_at": datetime.utcnow(),
            **data,
        },
        org_db_name
    )
    return course_id

def get_course(course_id: str, org_db_name: str = None):
    return get_one_from_collection("courses", {"_id": course_id}, org_db_name)

def get_courses_by_user_id(user_id: str, org_db_name: str = None):
    """Get courses owned by user AND courses shared with user"""
    # Get courses user owns
    owned_courses = get_many_from_collection("courses", {"user_id": user_id}, org_db_name)
    
    # Get courses shared with user
    shared_courses = get_shared_courses(user_id, org_db_name)
    
    # Mark owned courses as owned and shared courses as shared
    for course in owned_courses:
        course["is_owner"] = True
        course["is_shared"] = False
        # Add count of users this course is shared with
        shares = get_course_shares(course["_id"], org_db_name)
        course["shared_count"] = len(shares)
    
    for course in shared_courses:
        course["is_owner"] = False
        course["is_shared"] = True
        course["shared_count"] = 0
        # Add owner email for display
        owner_email = get_email_by_user_id(course.get("user_id"), org_db_name)
        course["owner_email"] = owner_email
    
    return owned_courses + shared_courses

def update_course(course_id: str, data: dict, org_db_name: str = None):
    update_in_collection("courses", {"_id": course_id}, data, org_db_name)

def delete_course(course_id: str, org_db_name: str = None):
    delete_from_collection("courses", {"_id": course_id}, org_db_name)

# Course Sharing
def share_course(course_id: str, owner_id: str, shared_with_user_id: str, shared_with_email: str, org_db_name: str = None):
    """Share a course with another user"""
    from datetime import datetime
    share_data = {
        "course_id": course_id,
        "owner_id": owner_id,
        "shared_with_user_id": shared_with_user_id,
        "shared_with_email": shared_with_email,
        "shared_at": datetime.utcnow().isoformat()
    }
    add_to_collection("course_shares", share_data, org_db_name)

def get_course_shares(course_id: str, org_db_name: str = None):
    """Get list of users a course is shared with"""
    return get_many_from_collection("course_shares", {"course_id": course_id}, org_db_name)

def get_shared_courses(user_id: str, org_db_name: str = None):
    """Get courses shared with a user"""
    shares = get_many_from_collection("course_shares", {"shared_with_user_id": user_id}, org_db_name)
    course_ids = [share["course_id"] for share in shares]
    if not course_ids:
        return []
    return get_many_from_collection("courses", {"_id": {"$in": course_ids}}, org_db_name)

def is_course_shared_with_user(course_id: str, user_id: str, org_db_name: str = None):
    """Check if course is already shared with a specific user"""
    share = get_one_from_collection("course_shares", {
        "course_id": course_id,
        "shared_with_user_id": user_id
    }, org_db_name)
    return share is not None

def revoke_course_share(course_id: str, user_id: str, org_db_name: str = None):
    """Remove sharing access for a user"""
    delete_from_collection("course_shares", {
        "course_id": course_id,
        "shared_with_user_id": user_id
    }, org_db_name)

def is_course_accessible(course_id: str, user_id: str, org_db_name: str = None):
    """Check if user owns or has access to a course"""
    course = get_course(course_id, org_db_name)
    if not course:
        return False
    
    # Check if user owns the course
    if course.get("user_id") == user_id:
        return True
    
    # Check if course is shared with user
    return is_course_shared_with_user(course_id, user_id, org_db_name)

def get_course_owner_email(course_id: str, org_db_name: str = None):
    """Get the email of the course owner"""
    course = get_course(course_id, org_db_name)
    if not course:
        return None
    owner_id = course.get("user_id")
    if not owner_id:
        return None
    return get_email_by_user_id(owner_id, org_db_name)

# Resources
def create_resource(course_id: str, resource_name: str, content: str = None, org_db_name: str = None):
    resource_data = {"course_id": course_id, "resource_name": resource_name}
    if content is not None:
        resource_data["content"] = content
    add_to_collection("resources", resource_data, org_db_name)

def get_resources_by_course_id(course_id: str, org_db_name: str = None):
    return get_many_from_collection("resources", {"course_id": course_id}, org_db_name)

def get_resource_by_course_id_and_resource_name(course_id: str, resource_name: str, org_db_name: str = None):
    return get_one_from_collection("resources", {"course_id": course_id, "resource_name": resource_name}, org_db_name)

def delete_resource(course_id: str, resource_name: str, org_db_name: str = None):
    delete_from_collection("resources", {"course_id": course_id, "resource_name": resource_name}, org_db_name)

# Assets
def create_asset(course_id: str, asset_name: str, asset_category: str, asset_type: str, asset_content: str, asset_last_updated_by: str, asset_last_updated_at: str, created_by_user_id: str = None, org_db_name: str = None):
    asset_data = {
        "course_id": course_id, 
        "asset_name": asset_name, 
        "asset_category": asset_category, 
        "asset_type": asset_type, 
        "asset_content": asset_content, 
        "asset_last_updated_by": asset_last_updated_by, 
        "asset_last_updated_at": asset_last_updated_at
    }
    if created_by_user_id:
        asset_data["created_by_user_id"] = created_by_user_id
    add_to_collection("assets", asset_data, org_db_name)

def get_assets_by_course_id(course_id: str, org_db_name: str = None):
    return get_many_from_collection("assets", {"course_id": course_id}, org_db_name)

def get_asset_by_course_id_and_asset_name(course_id: str, asset_name: str, org_db_name: str = None):
    return get_one_from_collection("assets", {"course_id": course_id, "asset_name": asset_name}, org_db_name)

def get_asset_by_course_id_and_asset_type(course_id: str, asset_type: str, org_db_name: str = None):
    return get_one_from_collection("assets", {"course_id": course_id, "asset_type": asset_type}, org_db_name)

def get_asset_by_evaluation_id(evaluation_id: str, org_db_name: str = None):
    """Get asset that references this evaluation_id"""
    return get_one_from_collection("assets", {"asset_content": evaluation_id, "asset_type": "evaluation"}, org_db_name)

def delete_asset_from_db(course_id: str, asset_name: str, org_db_name: str = None):
    delete_from_collection("assets", {"course_id": course_id, "asset_name": asset_name}, org_db_name)

# Evaluation    
def create_evaluation(evaluation_id: str, course_id: str, evaluation_assistant_id: str, vector_store_id: str, 
                     mark_scheme_path: str = None, mark_scheme_file_id: str = None,
                     answer_sheet_paths: list[str] = None, answer_sheet_file_ids: list[str] = None, 
                     answer_sheet_filenames: list[str] = None, evaluation_type: str = "digital", org_db_name: str = None):
    """Create evaluation record supporting both local paths and OpenAI file IDs
    
    Args:
        evaluation_id: Unique ID for the evaluation
        course_id: Course ID this evaluation belongs to
        evaluation_assistant_id: OpenAI assistant ID
        vector_store_id: OpenAI vector store ID
        mark_scheme_path: Local path to mark scheme file
        mark_scheme_file_id: OpenAI file ID for mark scheme
        answer_sheet_paths: List of local paths to answer sheets
        answer_sheet_file_ids: List of OpenAI file IDs for answer sheets
        answer_sheet_filenames: Original filenames of answer sheets
        evaluation_type: Type of evaluation - "digital" or "handwritten" (default: "digital")
        org_db_name: Organization database name for multi-tenant support
    """
    evaluation = {
        "evaluation_id": evaluation_id, 
        "course_id": course_id,
        "evaluation_assistant_id": evaluation_assistant_id, 
        "vector_store_id": vector_store_id,
        "mark_scheme_path": mark_scheme_path,
        "mark_scheme_file_id": mark_scheme_file_id,
        "answer_sheet_paths": answer_sheet_paths or [],
        "answer_sheet_file_ids": answer_sheet_file_ids or [],
        "answer_sheet_filenames": answer_sheet_filenames or [],
        "evaluation_type": evaluation_type
    }
    add_to_collection("evaluations", evaluation, org_db_name)
    return evaluation

def get_evaluation_by_evaluation_id(evaluation_id: str, org_db_name: str = None):
    return get_one_from_collection("evaluations", {"evaluation_id": evaluation_id}, org_db_name)

def get_evaluations_by_course_id(course_id: str, org_db_name: str = None):
    return get_many_from_collection("evaluations", {"course_id": course_id}, org_db_name)

def update_evaluation(evaluation_id: str, data: dict, org_db_name: str = None):
    """Update an evaluation record with new data"""
    logger = logging.getLogger(__name__)
    logger.info(f"Updating evaluation {evaluation_id} with data: {list(data.keys())}")
    update_in_collection("evaluations", {"evaluation_id": evaluation_id}, data, org_db_name)
    
def update_evaluation_with_result(evaluation_id: str, evaluation_result: dict):
    """
    Update an evaluation with the evaluation result.
    Stores the complete evaluation result including all student scores and feedback.
    """
    logger = logging.getLogger(__name__)
    
    # Log the update operation
    students_count = len(evaluation_result.get('students', []))
    logger.info(f"Updating evaluation {evaluation_id} with results for {students_count} students")
    # Store the evaluation result with timestamp
    update_data = {
        "evaluation_result": evaluation_result,
        "evaluation_completed_at": datetime.utcnow().isoformat(),
        "status": "completed"
    }
    
    update_in_collection("evaluations", {"evaluation_id": evaluation_id}, update_data)
    logger.info(f"Successfully updated evaluation {evaluation_id} in MongoDB")

# Minimal helper: update one question's score and feedback

def update_question_score_feedback(evaluation_id: str, file_id: str, question_number: str, score, feedback):
    collection = db["evaluations"]
    
    # First, try the correct array filter approach
    result = collection.update_one(
        {"evaluation_id": evaluation_id},
        {"$set": {
            "evaluation_result.students.$[s].answers.$[a].score": score,
            "evaluation_result.students.$[s].answers.$[a].feedback": feedback
        }},
        array_filters=[
            {"s.file_id": file_id},
            {"a.question_number": {"$in": [question_number, int(question_number)]}}
        ]
    )
    
    # Log the result for debugging
    logger = logging.getLogger(__name__)
    logger.info(f"Updated question {question_number} for file {file_id} in evaluation {evaluation_id}. Modified count: {result.modified_count}")
    
    if result.modified_count == 0:
        logger.warning(f"No questions were updated with array filters. Trying alternative approach...")
        
        # Alternative approach: Update the specific student and answer directly
        try:
            # First, find the evaluation to get the exact structure
            evaluation = collection.find_one({"evaluation_id": evaluation_id})
            if evaluation and "evaluation_result" in evaluation:
                for student_idx, student in enumerate(evaluation["evaluation_result"].get("students", [])):
                    if student.get("file_id") == file_id:
                        # Find the answer index
                        for answer_idx, answer in enumerate(student.get("answers", [])):
                            if str(answer.get("question_number")) == question_number or answer.get("question_number") == int(question_number):
                                # Update using positional operators
                                update_result = collection.update_one(
                                    {"evaluation_id": evaluation_id},
                                    {"$set": {
                                        f"evaluation_result.students.{student_idx}.answers.{answer_idx}.score": score,
                                        f"evaluation_result.students.{student_idx}.answers.{answer_idx}.feedback": feedback
                                    }}
                                )
                                logger.info(f"Alternative update successful. Modified count: {update_result.modified_count}")
                                return
                
                logger.warning(f"Could not find student with file_id {file_id} or question {question_number}")
            else:
                logger.warning(f"Evaluation {evaluation_id} not found or missing evaluation_result")
        except Exception as e:
            logger.error(f"Error in alternative update approach: {str(e)}")
            raise

# AI Feedback
def create_ai_feedback(evaluation_id: str, ai_feedback: dict):
    add_to_collection("ai_feedback", {"evaluation_id": evaluation_id, "ai_feedback": ai_feedback})

def get_ai_feedback_by_evaluation_id(evaluation_id: str):
    return get_one_from_collection("ai_feedback", {"evaluation_id": evaluation_id})

def update_ai_feedback(evaluation_id: str, ai_feedback: dict):
    """Update AI feedback in ai_feedback collection"""
    update_in_collection("ai_feedback", {"evaluation_id": evaluation_id}, {"ai_feedback": ai_feedback})

# System Configurations
def get_configurations_by_type(config_type: str):
    """Get all configurations by type (curriculum, assessment, setting)"""
    configs = get_many_from_collection("system_configurations", {"type": config_type})
    # Sort by order if available
    configs.sort(key=lambda x: x.get("order", 999))
    return configs

def get_setting_by_category(category: str, org_db_name: str = None):
    """Get a specific setting by category (e.g., course_level, study_area, pedagogical_components)"""
    return get_one_from_collection("system_configurations", {"type": "setting", "category": category}, org_db_name)

def get_all_settings(org_db_name: str = None):
    """Get all setting configurations from org database"""
    return get_many_from_collection("system_configurations", {"type": "setting"}, org_db_name)

def create_configuration(config_data: dict, org_db_name: str = None):
    """Create a new system configuration"""
    add_to_collection("system_configurations", config_data, org_db_name)

def update_configuration(config_id: str, config_data: dict, org_db_name: str = None):
    """Update a system configuration"""
    update_in_collection("system_configurations", {"_id": config_id}, config_data, org_db_name)

def delete_configuration(config_id: str, org_db_name: str = None):
    """Delete a system configuration"""
    delete_from_collection("system_configurations", {"_id": config_id}, org_db_name)

def add_setting_label(category: str, label: str, org_db_name: str = None):
    """Add a label to an org-specific setting category's options array"""
    setting = get_setting_by_category(category, org_db_name)
    
    # If setting doesn't exist in org DB, create it first
    if not setting:
        # Create a new org-specific setting for this category
        setting_data = {
            "_id": f"org-setting-{category}",
            "type": "setting",
            "category": category,
            "label": category.replace("_", " ").title(),
            "options": []
        }
        create_configuration(setting_data, org_db_name)
        setting = setting_data
    
    options = setting.get("options", [])
    if label in options:
        raise ValueError(f"Label '{label}' already exists in category '{category}'")
    
    options.append(label)
    update_configuration(setting["_id"], {"options": options}, org_db_name)

def remove_setting_label(category: str, label: str, org_db_name: str = None):
    """Remove a label from an org-specific setting category's options array"""
    setting = get_setting_by_category(category, org_db_name)
    if not setting:
        raise ValueError(f"Setting category '{category}' not found in this organization")
    
    options = setting.get("options", [])
    if label not in options:
        raise ValueError(f"Label '{label}' not found in category '{category}'")
    
    options.remove(label)
    update_configuration(setting["_id"], {"options": options}, org_db_name)

def get_merged_settings(org_db_name: str = None):
    """
    Get merged settings: global labels from master DB + org-specific labels.
    Each option is tagged with its source ('global' or 'org').
    """
    from .master_db import get_global_settings, initialize_global_settings
    
    # Initialize and get global settings
    initialize_global_settings()
    global_settings = get_global_settings()
    
    # Get org-specific settings
    org_settings = get_all_settings(org_db_name) if org_db_name else []
    
    # Build a map of org settings by category
    org_settings_map = {s.get("category"): s for s in org_settings}
    
    # Merge settings
    merged = []
    for global_setting in global_settings:
        category = global_setting.get("category")
        merged_setting = {
            "_id": global_setting.get("_id"),
            "type": "setting",
            "category": category,
            "label": global_setting.get("label"),
            "options": []
        }
        
        # Add global options with source tag
        for option in global_setting.get("options", []):
            merged_setting["options"].append({
                "label": option,
                "source": "global"
            })
        
        # Add org-specific options if any
        if category in org_settings_map:
            org_setting = org_settings_map[category]
            for option in org_setting.get("options", []):
                # Check if not already in global
                if option not in global_setting.get("options", []):
                    merged_setting["options"].append({
                        "label": option,
                        "source": "org"
                    })
        
        merged.append(merged_setting)
    
    return merged

# GridFS File Storage Functions
def store_pdf_in_mongo(file_content: bytes, filename: str, metadata: dict = None, org_db_name: str = None) -> str:
    """Store file binary data in MongoDB using GridFS (org-specific if org_db_name provided)"""
    logger = logging.getLogger(__name__)
    target_fs = get_org_gridfs(org_db_name) if org_db_name else fs
    file_id = target_fs.put(
        file_content,
        filename=filename,
        content_type=metadata.get("content_type", "application/pdf") if metadata else "application/pdf",
        metadata=metadata or {}
    )
    logger.info(f"Stored file '{filename}' in MongoDB with file_id: {file_id} (org: {org_db_name or 'default'})")
    return str(file_id)

def retrieve_pdf_from_mongo(file_id: str, org_db_name: str = None) -> bytes:
    """Retrieve file binary data from MongoDB using GridFS (org-specific if org_db_name provided)"""
    logger = logging.getLogger(__name__)
    target_fs = get_org_gridfs(org_db_name) if org_db_name else fs
    try:
        grid_out = target_fs.get(ObjectId(file_id))
        logger.info(f"Retrieved file with file_id: {file_id}, filename: {grid_out.filename} (org: {org_db_name or 'default'})")
        return grid_out.read()
    except gridfs.NoFile:
        logger.error(f"File not found in MongoDB with file_id: {file_id} (org: {org_db_name or 'default'})")
        raise HTTPException(status_code=404, detail="File not found in database")

def delete_pdf_from_mongo(file_id: str, org_db_name: str = None):
    """Delete file from MongoDB GridFS (org-specific if org_db_name provided)"""
    logger = logging.getLogger(__name__)
    target_fs = get_org_gridfs(org_db_name) if org_db_name else fs
    try:
        target_fs.delete(ObjectId(file_id))
        logger.info(f"Deleted file with file_id: {file_id} (org: {org_db_name or 'default'})")
    except gridfs.NoFile:
        logger.warning(f"Attempted to delete non-existent file: {file_id}")

# Admin Files
def create_admin_file(file_data: dict, org_db_name: str = None):
    """Create a new admin file record"""
    from uuid import uuid4
    file_id = str(uuid4())
    file_data["_id"] = file_id
    file_data["created_at"] = datetime.utcnow().isoformat()
    add_to_collection("admin_files", file_data, org_db_name)
    return file_id

def get_all_admin_files(org_db_name: str = None):
    """Get all admin files for an organization"""
    return get_many_from_collection("admin_files", {}, org_db_name)

def get_admin_file_by_id(file_id: str, org_db_name: str = None):
    """Get admin file by ID"""
    return get_one_from_collection("admin_files", {"_id": file_id}, org_db_name)

def delete_admin_file(file_id: str, org_db_name: str = None):
    """Delete an admin file"""
    delete_from_collection("admin_files", {"_id": file_id}, org_db_name)


# ============== PAYMENT RECORDS ==============

def create_payment_record(payment_data: dict, org_db_name: str = None) -> str:
    """
    Create a new payment record in the organization's database.
    
    Args:
        payment_data: Payment details including razorpay_order_id, amount, etc.
        org_db_name: Organization database name
    
    Returns:
        The payment record ID
    """
    payment_id = str(uuid4())
    payment_data["_id"] = payment_id
    payment_data["created_at"] = datetime.utcnow().isoformat()
    add_to_collection("payments", payment_data, org_db_name)
    logger.info(f"Created payment record: {payment_id} (org: {org_db_name or 'default'})")
    return payment_id


def update_payment_record(payment_id: str, update_data: dict, org_db_name: str = None):
    """Update a payment record with verification details"""
    update_in_collection("payments", {"_id": payment_id}, update_data, org_db_name)
    logger.info(f"Updated payment record: {payment_id}")


def get_payment_by_order_id(razorpay_order_id: str, org_db_name: str = None) -> Optional[dict]:
    """Get payment record by Razorpay order ID"""
    return get_one_from_collection("payments", {"razorpay_order_id": razorpay_order_id}, org_db_name)


def get_payment_by_id(payment_id: str, org_db_name: str = None) -> Optional[dict]:
    """Get payment record by ID"""
    return get_one_from_collection("payments", {"_id": payment_id}, org_db_name)


def get_payment_history(org_db_name: str = None) -> List[dict]:
    """Get all payment records for an organization, sorted by date descending"""
    payments = get_many_from_collection("payments", {}, org_db_name)
    # Sort by created_at descending
    payments.sort(key=lambda x: x.get("created_at", ""), reverse=True)
    return payments


def get_non_admin_user_count(org_db_name: str = None) -> int:
    """Get count of non-admin users in the organization"""
    collection = get_org_collection("users", org_db_name)
    count = collection.count_documents({"role": {"$ne": "admin"}})
    return count