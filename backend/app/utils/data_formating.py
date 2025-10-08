import json
import re
import logging
from fastapi import HTTPException
from typing import Dict, List, Optional, Any
from datetime import datetime
from ..utils.openai_client import client
from ..config.settings import settings
from app.services.mongo import (
    get_course, 
    get_assets_by_course_id,
    get_asset_by_course_id_and_asset_name,
    get_asset_by_course_id_and_asset_type
)

logger = logging.getLogger(__name__)

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

# fuction which will take course_id asset name, asset type and give the json output of the details of that from mongo db
def get_asset_details(course_id, asset_name):
    asset = get_asset_by_course_id_and_asset_name(course_id, asset_name)
    if not asset:
        raise HTTPException(status_code=404, detail="Asset not found")

    asset_details = {
        "asset_name": asset["asset_name"],
        "asset_type": asset["asset_type"],
        "asset_category": asset["asset_category"],
        "asset_content": asset["asset_content"],
        "asset_last_updated_by": asset["asset_last_updated_by"],
        "asset_last_updated_at": asset["asset_last_updated_at"]
    }
    return asset_details

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

def format_quiz_content(course_id: str, asset_name: str):
    """
    Format quiz content using OpenAI structured output
    """
    # Get the quiz content from mongo
    asset = get_asset_by_course_id_and_asset_name(course_id, asset_name)
    if not asset:
        raise HTTPException(status_code=404, detail=f"Asset '{asset_name}' not found")
    
    asset_content = asset.get("asset_content", "")
    
    # Get the assistant from mongo 
    course = get_course(course_id)
    if not course:
        raise HTTPException(status_code=404, detail=f"Course '{course_id}' not found")
    
    assistant_id = course.get("assistant_id", "")
    
    # Prepare the prompt
    system_prompt = """You are a quiz formatting assistant. Your task is to take quiz content (which may be in various formats) and convert it into a well-structured JSON format.

Extract or infer the following:
- A clear title for the quiz
- A brief description of what the quiz covers
- Estimated time in hours (contentHours) to complete the quiz
- All questions with their options, correct answer index, marks, and explanations

Guidelines:
- Each question should have multiple choice options in an array
- correctOptionIndex is 0-based (0 for first option, 1 for second, etc.)
- If marks are not specified, default to 1 mark per question
- Provide helpful explanations for each answer
- Ensure options are clear and distinct"""

    user_prompt = f"Please format the following quiz content into the required JSON structure:\n\n{asset_content}"
    if asset_name:
        user_prompt = f"Quiz: {asset_name}\n\n" + user_prompt
    
    # Use chat completions with structured output
    response = client.chat.completions.create(
        model=settings.OPENAI_MODEL,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ],
        response_format={
            "type": "json_schema",
            "json_schema": {
                "name": "quiz_schema",
                "strict": True,
                "schema": {
                    "type": "object",
                    "properties": {
                        "title": {
                            "type": "string",
                            "description": "The title of the quiz"
                        },
                        "description": {
                            "type": "string",
                            "description": "A brief description of what the quiz covers"
                        },
                        "contentHours": {
                            "type": "number",
                            "description": "Estimated time in hours to complete the quiz"
                        },
                        "questions": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "question": {
                                        "type": "string",
                                        "description": "The question text"
                                    },
                                    "options": {
                                        "type": "array",
                                        "items": {
                                            "type": "string"
                                        },
                                        "description": "Array of answer options"
                                    },
                                    "correctOptionIndex": {
                                        "type": "integer",
                                        "description": "0-based index of the correct answer"
                                    },
                                    "marks": {
                                        "type": "number",
                                        "description": "Points for this question"
                                    },
                                    "explanation": {
                                        "type": "string",
                                        "description": "Explanation of the correct answer"
                                    }
                                },
                                "required": ["question", "options", "correctOptionIndex", "marks", "explanation"],
                                "additionalProperties": False
                            }
                        }
                    },
                    "required": ["title", "description", "contentHours", "questions"],
                    "additionalProperties": False
                }
            }
        }
    )
    
    # Parse the response
    structured_output = response.choices[0].message.content
    
    if not structured_output:
        raise HTTPException(status_code=500, detail="No content returned from OpenAI")
    
    # Parse JSON
    try:
        quiz_data = json.loads(structured_output)
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse quiz JSON: {structured_output}")
        raise HTTPException(status_code=500, detail=f"Invalid JSON response from OpenAI: {str(e)}")
    
    logger.info(f"Successfully formatted quiz with {len(quiz_data.get('questions', []))} questions")
    return quiz_data

