import json
import re
from typing import Dict, List, Optional, Any
from datetime import datetime
from app.services.mongo import (
    get_course, 
    get_assets_by_course_id
)

def fetch_course_data(course_id: str, user_id: str) -> Dict[str, Any]:
    """
    Fetch all data for a given course and user ID from MongoDB
    Returns a formatted dictionary with all course information
    """
    try:
        # Step 1: Get basic course information
        course = get_course(course_id)
        if not course:
            raise ValueError(f"Course with ID {course_id} not found")
        
        # Verify user access
        if course.get("user_id") != user_id:
            raise ValueError("User does not have access to this course")
        
        # Step 2: Get all related data
        assets = get_assets_by_course_id(course_id)
        
        # Step 3: Format the data according to the required structure
        formatted_data = format_course_data(course, assets)
        
        return formatted_data
        
    except Exception as e:
        raise Exception(f"Error fetching course data: {str(e)}")

def format_course_data(course: Dict, assets: List[Dict]) -> Dict[str, Any]:
    """
    Format the raw course data into a simple structure with course info and all assets
    """
    formatted_data = {
        "course_info": {
            "course_id": course.get("_id"),
            "course_name": course.get("name", ""),
            "description": course.get("description", ""),
            "user_id": course.get("user_id"),
            "settings": course.get("settings", {}),
            "created_at": course.get("created_at", ""),
            "updated_at": course.get("updated_at", "")
        },
        "assets": []
    }
    
    # Include curriculum modules
    modules_assets = [asset for asset in assets if asset.get("asset_type") == "modules-topics"]
    for asset in modules_assets:
        asset_data = {
            "asset_id": asset.get("_id"),
            "asset_name": asset.get("asset_name", ""),
            "asset_type": asset.get("asset_type", ""),
            "asset_category": asset.get("asset_category", ""),
            "asset_content": asset.get("asset_content", ""),
            "last_updated_by": asset.get("asset_last_updated_by", ""),
            "last_updated_at": asset.get("asset_last_updated_at", ""),
            "course_id": asset.get("course_id", "")
        }
        formatted_data["assets"].append(asset_data)

    # Include assessment assets (projects, activities, quizzes, question papers, mark schemes, mock interviews)
    assessment_types = {"project", "activity", "quiz", "question-paper", "mark-scheme", "mock-interview"}
    assessment_assets = [asset for asset in assets if asset.get("asset_type") in assessment_types]
    for asset in assessment_assets:
        asset_data = {
            "asset_id": asset.get("_id"),
            "asset_name": asset.get("asset_name", ""),
            "asset_type": asset.get("asset_type", ""),
            "asset_category": asset.get("asset_category", ""),
            "asset_content": asset.get("asset_content", ""),
            "last_updated_by": asset.get("asset_last_updated_by", ""),
            "last_updated_at": asset.get("asset_last_updated_at", ""),
            "course_id": asset.get("course_id", "")
        }
        formatted_data["assets"].append(asset_data)

    return formatted_data


def get_formatted_course_data(course_id: str, user_id: str) -> str:
    """
    Main function to get formatted course data as JSON string
    """
    try:
        data = fetch_course_data(course_id, user_id)
        return json.dumps(data, indent=2)
    except Exception as e:
        return json.dumps({"error": str(e)}, indent=2)

def get_formatted_course_data_dict(course_id: str, user_id: str) -> Dict[str, Any]:
    """
    Alternative function that returns the formatted data as a dictionary instead of JSON string
    """
    try:
        return fetch_course_data(course_id, user_id)
    except Exception as e:
        return {"error": str(e)}

# Example usage function (for testing purposes)
def example_usage():
    """
    Example of how to use the data formatting functions
    """
    # Example course_id and user_id
    course_id = "example-course-id"
    user_id = "example-user-id"
    
    try:
        # Get formatted data as JSON string
        json_data = get_formatted_course_data(course_id, user_id)
        print("JSON formatted data:")
        print(json_data)
        
        # Get formatted data as dictionary
        dict_data = get_formatted_course_data_dict(course_id, user_id)
        print("\nDictionary formatted data:")
        print(dict_data)
        
    except Exception as e:
        print(f"Error: {e}")