import json
import re
import logging
import markdown
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
    
    # Convert markdown to HTML for quiz fields that may contain markdown
    if 'description' in quiz_data and isinstance(quiz_data['description'], str):
        quiz_data['description'] = markdown.markdown(
            quiz_data['description'],
            extensions=['markdown.extensions.fenced_code', 'markdown.extensions.nl2br']
        )
    
    # Convert markdown in questions, options, and explanations
    if 'questions' in quiz_data and isinstance(quiz_data['questions'], list):
        for question in quiz_data['questions']:
            if 'question' in question and isinstance(question['question'], str):
                question['question'] = markdown.markdown(
                    question['question'],
                    extensions=['markdown.extensions.fenced_code', 'markdown.extensions.nl2br']
                )
            if 'explanation' in question and isinstance(question['explanation'], str):
                question['explanation'] = markdown.markdown(
                    question['explanation'],
                    extensions=['markdown.extensions.fenced_code', 'markdown.extensions.nl2br']
                )
            # Convert markdown in options
            if 'options' in question and isinstance(question['options'], list):
                question['options'] = [
                    markdown.markdown(opt, extensions=['markdown.extensions.fenced_code', 'markdown.extensions.nl2br']) 
                    if isinstance(opt, str) else opt 
                    for opt in question['options']
                ]
        logger.info("Converted markdown to HTML in quiz content")
    
    logger.info(f"Successfully formatted quiz with {len(quiz_data.get('questions', []))} questions")
    return quiz_data

def format_activity_content(course_id: str, asset_name: str):
    """
    Format activity content using OpenAI structured output
    """
    # Get the activity content from mongo
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
    system_prompt = """You are an activity formatting assistant. Your task is to take activity content (which may be in various formats) and convert it into a well-structured JSON format.

Extract or infer the following:
- A clear title for the activity
- A brief description of what the activity covers
- The main content or text of the activity
- The type should always be "assignment"

The activity will be formatted as an assignment activity by default."""

    user_prompt = f"Please format the following activity content into the required JSON structure:\n\n{asset_content}"
    if asset_name:
        user_prompt = f"Activity: {asset_name}\n\n" + user_prompt
    
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
                "name": "activity_schema",
                "strict": True,
                "schema": {
                    "type": "object",
                    "properties": {
                        "type": {
                            "type": "string",
                            "description": "The type of activity"
                        },
                        "payload": {
                            "type": "object",
                            "properties": {
                                "title": {
                                    "type": "string",
                                    "description": "The title of the activity"
                                },
                                "description": {
                                    "type": "string",
                                    "description": "A brief description of the activity"
                                },
                                "content": {
                                    "type": "string",
                                    "description": "The main content or text of the activity"
                                }
                            },
                            "required": ["title", "description", "content"],
                            "additionalProperties": False
                        },
                        "isLocked": {
                            "type": "boolean",
                            "description": "Indicates whether the activity is locked for editing (default: false)"
                        },
                        "isGraded": {
                            "type": "boolean",
                            "description": "Indicates whether the activity is graded (default: true for assignments)"
                        }
                    },
                    "required": ["type", "payload", "isLocked", "isGraded"],
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
        activity_data = json.loads(structured_output)
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse activity JSON: {structured_output}")
        raise HTTPException(status_code=500, detail=f"Invalid JSON response from OpenAI: {str(e)}")
    
    # Ensure payload is an object, not a string
    if isinstance(activity_data.get('payload'), str):
        try:
            activity_data['payload'] = json.loads(activity_data['payload'])
            logger.warning("Payload was a string, converted to object")
        except:
            logger.error(f"Failed to parse payload string: {activity_data.get('payload')}")
    
    # Ensure boolean fields are actual booleans
    if 'isLocked' in activity_data:
        activity_data['isLocked'] = bool(activity_data['isLocked'])
    if 'isGraded' in activity_data:
        activity_data['isGraded'] = bool(activity_data['isGraded'])
    
    # Set a more appropriate type if it's generic
    if activity_data.get('type') in ['object', 'activity', '']:
        activity_data['type'] = 'assignment'  # Default to assignment activity
    
    # For assignment type activities, ensure isGraded is true
    if activity_data.get('type') == 'assignment':
        activity_data['isGraded'] = False
    
    # Convert markdown content to HTML for proper rendering in LMS
    if isinstance(activity_data.get('payload'), dict):
        payload = activity_data['payload']
        if 'content' in payload and isinstance(payload['content'], str):
            # Convert markdown to HTML with extensions for better formatting
            html_content = markdown.markdown(
                payload['content'],
                extensions=[
                    'markdown.extensions.fenced_code',
                    'markdown.extensions.tables',
                    'markdown.extensions.nl2br',
                    'markdown.extensions.sane_lists'
                ]
            )
            payload['content'] = html_content
            logger.info("Converted markdown content to HTML")
    
    logger.info(f"Successfully formatted activity: {activity_data.get('payload', {}).get('title', 'Unknown')}")
    logger.info(f"Activity data structure - type: {activity_data.get('type')}, payload type: {type(activity_data.get('payload'))}, isLocked: {activity_data.get('isLocked')}, isGraded: {activity_data.get('isGraded')}")
    return activity_data