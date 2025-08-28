import logging
from datetime import datetime
from typing import List, Optional
from pymongo import MongoClient
from pymongo.database import Database
from pymongo.collection import Collection
from pymongo.errors import PyMongoError
from pymongo.server_api import ServerApi
from uuid import uuid4

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

def add_to_collection(collection_name: str, data: dict):
    collection = db[collection_name]
    collection.insert_one(data)

def get_one_from_collection(collection_name: str, query: dict):
    collection = db[collection_name]
    doc = collection.find_one(query)
    if doc and '_id' in doc:
        doc['_id'] = str(doc['_id'])
    return doc

def get_many_from_collection(collection_name: str, query: dict):
    docs = []
    collection = db[collection_name]
    for doc in collection.find(query):
        # Convert ObjectId to string for JSON serialization
        if '_id' in doc:
            doc['_id'] = str(doc['_id'])
        docs.append(doc)
    return docs

def update_in_collection(collection_name: str, query: dict, data: dict):
    collection = db[collection_name]
    collection.update_one(query, {"$set": data})

def delete_from_collection(collection_name: str, query: dict):
    collection = db[collection_name]
    collection.delete_one(query)

# Courses
def create_course(data: dict):
    course_id = str(uuid4())
    add_to_collection("courses", {"_id": course_id, **data})
    return course_id

def get_course(course_id: str):
    return get_one_from_collection("courses", {"_id": course_id})

def get_courses_by_user_id(user_id: str):
    return get_many_from_collection("courses", {"user_id": user_id})

def update_course(course_id: str, data: dict):
    update_in_collection("courses", {"_id": course_id}, data)

def delete_course(course_id: str):
    delete_from_collection("courses", {"_id": course_id})

# Resources
def create_resource(course_id: str, resource_name: str):
    add_to_collection("resources", {"course_id": course_id, "resource_name": resource_name})

def get_resources_by_course_id(course_id: str):
    return get_many_from_collection("resources", {"course_id": course_id})

def delete_resource(course_id: str, resource_name: str):
    delete_from_collection("resources", {"course_id": course_id, "resource_name": resource_name})

# Assets
def create_asset(course_id: str, asset_name: str, asset_category: str, asset_type: str, asset_content: str, asset_last_updated_by: str, asset_last_updated_at: str):
    add_to_collection("assets", {"course_id": course_id, "asset_name": asset_name, "asset_category": asset_category, "asset_type": asset_type, "asset_content": asset_content, "asset_last_updated_by": asset_last_updated_by, "asset_last_updated_at": asset_last_updated_at})

def get_assets_by_course_id(course_id: str):
    return get_many_from_collection("assets", {"course_id": course_id})

def get_asset_by_course_id_and_asset_name(course_id: str, asset_name: str):
    return get_one_from_collection("assets", {"course_id": course_id, "asset_name": asset_name})

# Evaluation    
def create_evaluation(evaluation_id: str, course_id: str,evaluation_assistant_id: str, vector_store_id: str, mark_scheme_file_id: str, answer_sheet_file_ids: list[str]):
    evaluation = {"evaluation_id": evaluation_id, "course_id": course_id,"evaluation_assistant_id": evaluation_assistant_id, "vector_store_id": vector_store_id, "mark_scheme_file_id": mark_scheme_file_id, "answer_sheet_file_ids": answer_sheet_file_ids}
    add_to_collection("evaluations", evaluation)
    return evaluation

def get_evaluation_by_evaluation_id(evaluation_id: str):
    return get_one_from_collection("evaluations", {"evaluation_id": evaluation_id})

def update_evaluation(evaluation_id: str, data: dict):
    """Update an evaluation record with new data"""
    logger = logging.getLogger(__name__)
    logger.info(f"Updating evaluation {evaluation_id} with data: {list(data.keys())}")
    update_in_collection("evaluations", {"evaluation_id": evaluation_id}, data)
    
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

def update_student_result(evaluation_id: str, student_index: int, question_scores: List[int], feedback: str, total_score: int, status: str = "modified") -> bool:
    """
    Update individual student result with manual marks and feedback.
    
    Args:
        evaluation_id: The evaluation ID
        student_index: Index of the student in the students array
        question_scores: List of scores for each question
        feedback: General feedback for the student
        total_score: Calculated total score
        status: New status for the student (default: "modified")
        
    Returns:
        bool: True if update was successful, False otherwise
    """
    logger = logging.getLogger(__name__)
    
    try:
        # Get the current evaluation
        evaluation = get_evaluation_by_evaluation_id(evaluation_id)
        if not evaluation or "evaluation_result" not in evaluation:
            logger.error(f"Evaluation {evaluation_id} not found or has no results")
            return False
        
        evaluation_result = evaluation["evaluation_result"]
        if "students" not in evaluation_result or student_index >= len(evaluation_result["students"]):
            logger.error(f"Student index {student_index} out of range for evaluation {evaluation_id}")
            return False
        
        # Update the specific student's data
        student = evaluation_result["students"][student_index]
        student["question_scores"] = question_scores
        student["feedback"] = feedback
        student["total_score"] = total_score
        student["status"] = status
        student["manually_updated"] = True
        student["updated_at"] = datetime.utcnow().isoformat()
        
        # Update the evaluation in MongoDB
        update_evaluation_with_result(evaluation_id, evaluation_result)
        
        logger.info(f"Successfully updated student {student_index} result for evaluation {evaluation_id}")
        return True
        
    except Exception as e:
        logger.error(f"Error updating student result for evaluation {evaluation_id}, student {student_index}: {str(e)}")
        return False

def update_student_status(evaluation_id: str, student_index: int, status: str) -> bool:
    """
    Update only the status of a specific student.
    
    Args:
        evaluation_id: The evaluation ID
        student_index: Index of the student in the students array
        status: New status for the student
        
    Returns:
        bool: True if update was successful, False otherwise
    """
    logger = logging.getLogger(__name__)
    
    try:
        # Get the current evaluation
        evaluation = get_evaluation_by_evaluation_id(evaluation_id)
        if not evaluation or "evaluation_result" not in evaluation:
            logger.error(f"Evaluation {evaluation_id} not found or has no results")
            return False
        
        evaluation_result = evaluation["evaluation_result"]
        if "students" not in evaluation_result or student_index >= len(evaluation_result["students"]):
            logger.error(f"Student index {student_index} out of range for evaluation {evaluation_id}")
            return False
        
        # Update only the status
        student = evaluation_result["students"][student_index]
        student["status"] = status
        student["status_updated_at"] = datetime.utcnow().isoformat()
        
        # Update the evaluation in MongoDB
        update_evaluation_with_result(evaluation_id, evaluation_result)
        
        logger.info(f"Successfully updated student {student_index} status to '{status}' for evaluation {evaluation_id}")
        return True
        
    except Exception as e:
        logger.error(f"Error updating student status for evaluation {evaluation_id}, student {student_index}: {str(e)}")
        return False

def get_student_evaluation_details(evaluation_id: str, student_index: int) -> dict:
    """
    Get detailed evaluation data for a specific student.
    
    Args:
        evaluation_id: The evaluation ID
        student_index: Index of the student in the students array
        
    Returns:
        dict: Student evaluation details or None if not found
    """
    try:
        evaluation = get_evaluation_by_evaluation_id(evaluation_id)
        if not evaluation or "evaluation_result" not in evaluation:
            return None
        
        evaluation_result = evaluation["evaluation_result"]
        if "students" not in evaluation_result or student_index >= len(evaluation_result["students"]):
            return None
        
        return evaluation_result["students"][student_index]
        
    except Exception as e:
        logger = logging.getLogger(__name__)
        logger.error(f"Error getting student evaluation details for evaluation {evaluation_id}, student {student_index}: {str(e)}")
        return None

# Evaluation Schemes
def create_evaluation_scheme(course_id: str, scheme_name: str, scheme_description: str, evaluation_assistant_id: str, vector_store_id: str, mark_scheme_file_id: str):
    """Create a new evaluation scheme (mark scheme) for a course"""
    scheme_id = str(uuid4())
    scheme_data = {
        "scheme_id": scheme_id,
        "course_id": course_id,
        "scheme_name": scheme_name,
        "scheme_description": scheme_description,
        "evaluation_assistant_id": evaluation_assistant_id,
        "vector_store_id": vector_store_id,
        "mark_scheme_file_id": mark_scheme_file_id,
        "created_at": datetime.utcnow().isoformat()
    }
    add_to_collection("evaluation_schemes", scheme_data)
    return scheme_id

def get_evaluation_schemes_by_course_id(course_id: str):
    """Get all evaluation schemes for a course"""
    schemes = get_many_from_collection("evaluation_schemes", {"course_id": course_id})
    # Sort by creation date, newest first
    schemes.sort(key=lambda x: x.get('created_at', ''), reverse=True)
    return schemes

def update_question_score_feedback(evaluation_id: str, file_id: str, question_number: str, score: float, feedback: str) -> bool:
    """
    Update a specific question's score and feedback for a specific student.
    
    Args:
        evaluation_id: The evaluation ID
        file_id: The student's file ID
        question_number: The question number to update
        score: The new score for the question
        feedback: The new feedback for the question
        
    Returns:
        bool: True if update was successful, False otherwise
    """
    logger = logging.getLogger(__name__)
    
    try:
        collection = db["evaluations"]
        
        # Update the specific question score and feedback
        result = collection.update_one(
            {"evaluation_id": evaluation_id},
            {"$set": {
                "evaluation_result.students.$[s].answers.$[a].score": score,
                "evaluation_result.students.$[s].answers.$[a].feedback": feedback
            }},
            array_filters=[
                {"s.file_id": file_id},
                {"a.question_number": str(question_number)}
            ]
        )
        
        if result.modified_count > 0:
            logger.info(f"Successfully updated question {question_number} for file {file_id} in evaluation {evaluation_id}")
            return True
        else:
            logger.warning(f"No documents were modified for question {question_number} in file {file_id} for evaluation {evaluation_id}")
            return False
            
    except Exception as e:
        logger.error(f"Error updating question score and feedback for evaluation {evaluation_id}, file {file_id}, question {question_number}: {str(e)}")
        return False
    