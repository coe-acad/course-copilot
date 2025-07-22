from fastapi import APIRouter, HTTPException, Header, Query, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import List, Optional
from ..services.storage_course import storage_service
from ..services import openai_service
from ..utils.exceptions import handle_course_error
import logging
from firebase_admin import auth as admin_auth
import uuid
from datetime import datetime
import json
from ..utils.verify_token import verify_token

logger = logging.getLogger(__name__)
router = APIRouter()

# Models
class CourseOutcomesRequest(BaseModel):
    course_name: str
    ask_clarifying_questions: bool
    file_names: List[str]

class CourseOutcomesResponse(BaseModel):
    thread_id: str
    message: str
    status: str

class CourseOutcomesMessage(BaseModel):
    role: str
    content: str
    timestamp: str

class CourseOutcomesMessageList(BaseModel):
    messages: List[CourseOutcomesMessage]

class CreateThreadResponse(BaseModel):
    thread_id: str
    status: str

class CourseOutcomesMessageRequest(BaseModel):
    message: str

@router.post("/courses/{course_id}/{asset}/create-thread", response_model=CreateThreadResponse)
async def create_asset_thread(course_id: str, user_id: str = Depends(verify_token)):
    """
    Always create a new course outcomes thread (like brainstorm).
    """
    try:
        course = storage_service.get_course(course_id, user_id)
        if not course:
            raise HTTPException(status_code=404, detail="Course not found")
        course_name = course.get("name", "Unknown Course")
        # Always create a new OpenAI thread
        thread = openai_service.client.beta.threads.create()
        thread_id = thread.id
        # Save thread ID in course document for persistence
        course["course_outcomes_thread_id"] = thread_id
        storage_service.update_course(course_id, course)
        # Create the course outcomes thread in storage
        storage_service.create_asset_thread(course_id, "course_outcomes", thread_id)
        # Add all files to the thread (not just checked-in)
        await openai_service.attach_all_files_to_thread(course_id, user_id, thread_id)
        # Gather checked-in files for display
        course_resources = storage_service.get_resources(course_id, user_id=user_id)
        asset_resources = storage_service.get_resources(course_id, thread_id=thread_id, user_id=user_id)
        all_resources = course_resources + asset_resources
        checked_in_files = [
            r.get("title", r.get("fileName", "Unknown file"))
            for r in all_resources
            if r["status"] == "checked_in"
        ]
        if checked_in_files:
            files_text = f"**Checked-in Files:** {', '.join(checked_in_files)} ({len(checked_in_files)} file{'s' if len(checked_in_files) != 1 else ''})"
        else:
            files_text = "**Checked-in Files:** No files currently available"
        # Compose the actionable welcome message
        welcome_message = f"""✅ Course Outcomes Generator Ready\n\nI'm here to help you create comprehensive, measurable course outcomes for your course.\n\n**Course Name:** {course_name}\n{files_text}\n\nThe system is ready to help you generate course outcomes!\n\nType 'proceed' or ask any questions to get started."""
        # Save a welcome message
        await openai_service.save_course_outcomes_message(course_id, thread_id, {
            "role": "assistant",
            "content": welcome_message,
            "timestamp": datetime.utcnow().isoformat(),
            "user_id": user_id,
            "assistant_id": course.get("assistant_id")
        })
        return CreateThreadResponse(
            thread_id=thread_id,
            status="created"
        )
    except Exception as e:
        logger.error(f"Error creating course outcomes thread: {str(e)}")
        raise handle_course_error(e)

@router.post("/courses/{course_id}/course-outcomes/start", response_model=CourseOutcomesResponse)
async def start_course_outcomes(course_id: str, request: CourseOutcomesRequest, user_id: str = Depends(verify_token)):
    """
    Start a course outcomes generation session with user inputs.
    """
    try:
        course = storage_service.get_course(course_id, user_id)
        if not course:
            raise HTTPException(status_code=404, detail="Course not found")
        
        # Get the actual course name from the database
        actual_course_name = course.get("name", "Unknown Course")
        
        # Check if a course outcomes thread already exists
        existing_thread_id = course.get("course_outcomes_thread_id")
        if existing_thread_id:
            logger.info(f"Using existing course outcomes thread {existing_thread_id} for course {course_id}")
            # Get existing messages to return the last one
            messages = storage_service.get_course_outcomes_history(course_id, existing_thread_id)
            last_message = messages[-1]["content"] if messages else "Thread exists but no messages found."
            return CourseOutcomesResponse(
                thread_id=existing_thread_id,
                message=last_message,
                status="existing"
            )
        
        # Create a proper OpenAI thread (like brainstorm)
        thread = openai_service.client.beta.threads.create()
        thread_id = thread.id
        
        # Save thread ID in course document for persistence
        course["course_outcomes_thread_id"] = thread_id
        storage_service.update_course(course_id, course)
        
        # Create the course outcomes thread in storage
        storage_service.create_asset_thread(course_id, "course_outcomes", thread_id)
        
        # Add all files to the thread (not just checked-in)
        await openai_service.attach_all_files_to_thread(course_id, user_id, thread_id)
        
        # Get the actual checked-in files from the database
        course_resources = storage_service.get_resources(course_id, user_id=user_id)
        asset_resources = storage_service.get_resources(course_id, thread_id=thread_id, user_id=user_id)
        all_resources = course_resources + asset_resources
        
        checked_in_files = [
            r.get("title", r.get("fileName", "Unknown file"))
            for r in all_resources
            if r["status"] == "checked_in"
        ]
        
        # Generate the system prompt with actual course name and checked-in files
        system_prompt = _generate_course_outcomes_system_prompt(
            actual_course_name,
            request.ask_clarifying_questions,
            checked_in_files
        )
        
        # Create the default welcome message
        if checked_in_files:
            files_text = f"**Checked-in Files:** {', '.join(checked_in_files)} ({len(checked_in_files)} file{'s' if len(checked_in_files) != 1 else ''})"
        else:
            files_text = "**Checked-in Files:** No files currently available"
        
        default_message = f"""Welcome to the Course Outcomes Generator! 

I have gathered the following information for your course:

**Course Name:** {actual_course_name}
{files_text}

The course outcomes will be generated based on the information above and any additional context you provide.

**Do you want to add any other information, or should I proceed with generating the course outcomes?**

What would you like to do?"""

        # Save the assistant's default message
        await openai_service.save_course_outcomes_message(course_id, thread_id, {
            "role": "assistant",
            "content": default_message,
            "timestamp": datetime.utcnow().isoformat(),
            "user_id": user_id,
            "assistant_id": course.get("assistant_id")
        })
        
        return CourseOutcomesResponse(
            thread_id=thread_id,
            message=default_message,
            status="started"
        )
        
    except Exception as e:
        logger.error(f"Error starting course outcomes: {str(e)}")
        raise handle_course_error(e)

@router.post("/courses/{course_id}/course-outcomes/{thread_id}/message", response_model=CourseOutcomesResponse)
async def send_course_outcomes_message(
    course_id: str, 
    thread_id: str, 
    request: CourseOutcomesMessageRequest,
    user_id: str = Depends(verify_token)
):
    """
    Send a message in the course outcomes thread.
    """
    try:
        course = storage_service.get_course(course_id, user_id)
        if not course:
            raise HTTPException(status_code=404, detail="Course not found")
        
        response = await openai_service.send_course_outcomes_message(
            course_id, 
            thread_id, 
            request.message, 
            user_id
        )
        
        return CourseOutcomesResponse(
            thread_id=thread_id,
            message=response,
            status="success"
        )
        
    except Exception as e:
        logger.error(f"Error sending course outcomes message: {str(e)}")
        raise handle_course_error(e)

@router.post("/courses/{course_id}/course-outcomes/{thread_id}/message/stream")
async def send_course_outcomes_message_stream(
    course_id: str, 
    thread_id: str, 
    request: CourseOutcomesMessageRequest,
    user_id: str = Depends(verify_token)
):
    """
    Send a message in the course outcomes thread and stream the response token by token.
    """
    try:
        course = storage_service.get_course(course_id, user_id)
        if not course:
            raise HTTPException(status_code=404, detail="Course not found")
        
        async def generate_stream():
            async for token_data in openai_service.send_course_outcomes_message_stream(
                course_id=course_id,
                thread_id=thread_id,
                message=request.message,
                user_id=user_id
            ):
                yield f"data: {token_data}\n\n"
        
        return StreamingResponse(
            generate_stream(),
            media_type="text/plain",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "Content-Type": "text/event-stream",
            }
        )
        
    except Exception as e:
        logger.error(f"Error sending course outcomes message stream: {str(e)}")
        raise handle_course_error(e)

@router.get("/courses/{course_id}/course-outcomes/{thread_id}/messages", response_model=CourseOutcomesMessageList)
async def get_course_outcomes_messages(
    course_id: str, 
    thread_id: str, 
    user_id: str = Depends(verify_token)
):
    """
    Get all messages from a course outcomes thread.
    """
    try:
        course = storage_service.get_course(course_id, user_id)
        if not course:
            raise HTTPException(status_code=404, detail="Course not found")
        
        messages = await openai_service.get_course_outcomes_history(course_id, thread_id)
        
        return CourseOutcomesMessageList(
            messages=[
                CourseOutcomesMessage(
                    role=msg.get("role", ""),
                    content=msg.get("content", ""),
                    timestamp=msg.get("timestamp", "")
                ) for msg in messages
            ]
        )
        
    except Exception as e:
        logger.error(f"Error getting course outcomes messages: {str(e)}")
        raise handle_course_error(e)

@router.get("/courses/{course_id}/course-outcomes/threads")
async def list_course_outcomes_threads(course_id: str, user_id: str = Depends(verify_token)):
    """
    List all course outcomes threads for a course.
    """
    try:
        course = storage_service.get_course(course_id, user_id)
        if not course:
            raise HTTPException(status_code=404, detail="Course not found")
        
        threads = storage_service.get_course_outcomes_threads(course_id, user_id)
        return {"threads": threads}
        
    except Exception as e:
        logger.error(f"Error listing course outcomes threads: {str(e)}")
        raise handle_course_error(e)

def _generate_course_outcomes_system_prompt(course_name: str, ask_clarifying_questions: bool, file_names: List[str]) -> str:
    """
    Generate the system prompt for course outcomes generation.
    """
    file_names_str = ", ".join(file_names) if file_names else "No specific files provided"
    
    prompt = f"""You are a helpful Course Outcomes Generator assistant. Your role is to help instructors create comprehensive, measurable course outcomes for their courses.

**Current Context:**
- Course Name: {course_name}
- Ask Clarifying Questions: {ask_clarifying_questions}
- Reference Files: {file_names_str}

**Your Approach:**
1. **First, show the information you have** and ask if the user wants to provide additional context or proceed with the current information.

2. **If the user wants to proceed** or doesn't provide additional information, generate comprehensive course outcomes.

3. **If the user provides additional context**, incorporate it into your course outcomes generation.

**Course Outcomes Guidelines:**
- Label each outcome sequentially as CO1, CO2, CO3, etc. (minimum 3 outcomes)
- Use clear, measurable language
- Align with the provided reference materials
- Focus on transdisciplinary and project-based learning
- Include critical thinking, communication, collaboration, and technology integration
- Consider ethical considerations, global perspective, and sustainability
- Ensure career readiness and professional success preparation

**Output Format for Course Outcomes:**
```
CO1: [Brief, informative name]
Description: [Detailed description referencing provided materials]
Bloom's Level(s): [Relevant learning levels]
Assessment Ideas: [Suggestions for assessment]

CO2: [Brief, informative name]
Description: [Detailed description referencing provided materials]
Bloom's Level(s): [Relevant learning levels]
Assessment Ideas: [Suggestions for assessment]

[Continue for CO3, CO4, etc.]
```

**Be conversational and helpful.** Start by showing the information you have and asking what the user would like to do next.

**If the user asks to see the information again or asks "what information do you have", repeat the current context information above.**

**If the user says "proceed", "continue", "generate", or similar, immediately start generating comprehensive course outcomes based on the available information.**

**Quick Action Responses:**
- If user types "proceed" → Generate course outcomes immediately
- If user types "show info" → Show the current context information
- If user types "add context" → Ask what additional context they'd like to provide"""
    
    return prompt 