from fastapi import APIRouter, HTTPException, Header, Depends, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import List
from ..services.storage_course import storage_service
from ..services import openai_service
from ..utils.exceptions import handle_course_error, CourseNotFoundError
from firebase_admin import auth as auth
import logging
from ..utils.verify_token import verify_token
import requests

logger = logging.getLogger(__name__)
router = APIRouter()

# Pydantic Models
class ChatMessage(BaseModel):
    message: str

class ChatResponse(BaseModel):
    response: str

class ThreadResponse(BaseModel):
    thread_id: str

class MessagesResponse(BaseModel):
    messages: List[dict]

class BrainstormRequest(BaseModel):
    message: str

# --- Chat Endpoints ---

@router.post("/courses/{course_id}/threads", response_model=ThreadResponse)
async def create_chat_thread(course_id: str, user_id: str = Depends(verify_token)):
    """
    Create a new chat thread for a course
    """
    try:
        course = storage_service.get_course(course_id, user_id)
        if not course:
            raise CourseNotFoundError(f"Course {course_id} not found for user {user_id}")
        
        thread = openai_service.client.beta.threads.create()
        thread_id = thread.id
        
        # Store thread reference in course
        course["free_chat_thread_id"] = thread_id
        storage_service.update_course(course_id, course)
        
        # Add all files to the thread (not just checked-in)
        await openai_service.attach_all_files_to_thread(course_id, user_id, thread_id)
        
        return ThreadResponse(thread_id=thread_id)
    except Exception as e:
        logger.error(f"Exception in create_chat_thread: {e}")
        raise handle_course_error(e)

@router.get("/courses/{course_id}/threads/{thread_id}/messages", response_model=MessagesResponse)
async def get_chat_messages(course_id: str, thread_id: str, user_id: str = Depends(verify_token)):
    """
    Get chat messages for a specific thread
    """
    try:
        messages = await openai_service.get_chat_history(course_id, thread_id)
        return MessagesResponse(messages=messages)
    except Exception as e:
        logger.error(f"Error fetching chat messages: {str(e)}")
        raise handle_course_error(e)

@router.post("/courses/{course_id}/threads/{thread_id}/messages", response_model=ChatResponse)
async def send_chat_message(
    course_id: str, 
    thread_id: str, 
    message: ChatMessage, 
    user_id: str = Depends(verify_token)
):
    """
    Send a message to a chat thread
    """
    try:
        response = await openai_service.send_message(
            course_id=course_id,
            thread_id=thread_id,
            message=message.message,
            user_id=user_id
        )
        logger.info(f"Generated response for thread {thread_id}: {response[:50]}...")
        return ChatResponse(response=response)
    except Exception as e:
        logger.error(f"Error in send_chat_message: {str(e)}")
        raise handle_course_error(e)

@router.post("/courses/{course_id}/threads/{thread_id}/messages/stream")
async def send_chat_message_stream(
    course_id: str, 
    thread_id: str, 
    message: ChatMessage, 
    user_id: str = Depends(verify_token)
):
    """
    Send a message to a chat thread and stream the response token by token
    """
    try:
        async def generate_stream():
            async for token_data in openai_service.send_message_stream(
                course_id=course_id,
                thread_id=thread_id,
                message=message.message,
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
        logger.error(f"Error in send_chat_message_stream: {str(e)}")
        raise handle_course_error(e)

# --- Brainstorm Endpoints ---

@router.post("/courses/{course_id}/brainstorm/threads", response_model=ThreadResponse)
async def create_brainstorm_thread(course_id: str, user_id: str = Depends(verify_token), request: Request = None):
    # Debug: print the request body to see if anything is being sent
    if request is not None:
        body = await request.body()
        logger.info(f"[DEBUG] Brainstorm thread creation request body: {body}")
    """
    Always create a new brainstorm thread for a course
    """
    try:
        course = storage_service.get_course(course_id, user_id)
        if not course:
            raise CourseNotFoundError(f"Course {course_id} not found for user {user_id}")
        
        thread = openai_service.client.beta.threads.create()
        thread_id = thread.id
        
        # Save thread ID in course document for persistence
        course["brainstorm_thread_id"] = thread_id
        storage_service.update_course(course_id, course)
        
        # Create a new asset-named collection and document for the thread
        storage_service.create_asset_thread(course_id, "brainstorm", thread_id)
        
        # Add all files to the thread (not just checked-in)
        await openai_service.attach_all_files_to_thread(course_id, user_id, thread_id)
        
        logger.info(f"Created brainstorm thread {thread_id} for course {course_id}")
        return ThreadResponse(thread_id=thread_id)
    except Exception as e:
        logger.error(f"Exception in create_brainstorm_thread: {e}")
        raise handle_course_error(e)

@router.get("/courses/{course_id}/brainstorm/{thread_id}/messages", response_model=MessagesResponse)
async def get_brainstorm_messages(course_id: str, thread_id: str, user_id: str = Depends(verify_token)):
    """
    Get brainstorm messages for a specific thread
    """
    try:
        messages = storage_service.get_brainstorm_messages(course_id, thread_id, user_id)
        logger.info(f"Fetched {len(messages)} brainstorm messages for course {course_id}, thread {thread_id}")
        return MessagesResponse(messages=messages)
    except Exception as e:
        logger.error(f"Error fetching brainstorm messages: {str(e)}")
        raise handle_course_error(e)

@router.post("/courses/{course_id}/brainstorm/{thread_id}/messages", response_model=ChatResponse)
async def send_brainstorm_message(
    course_id: str, 
    thread_id: str, 
    message: BrainstormRequest, 
    user_id: str = Depends(verify_token)
):
    """
    Send a message to a brainstorm thread
    """
    try:
        response = await openai_service.send_brainstorm_message(
            course_id=course_id,
            thread_id=thread_id,
            message=message.message,
            user_id=user_id
        )
        logger.info(f"Generated brainstorm response for thread {thread_id}: {response[:50]}...")
        return ChatResponse(response=response)
    except Exception as e:
        logger.error(f"Error in send_brainstorm_message: {str(e)}")
        raise handle_course_error(e)

@router.post("/courses/{course_id}/brainstorm/{thread_id}/messages/stream")
async def send_brainstorm_message_stream(
    course_id: str, 
    thread_id: str, 
    message: BrainstormRequest, 
    user_id: str = Depends(verify_token)
):
    """
    Send a message to a brainstorm thread and stream the response token by token
    """
    try:
        async def generate_stream():
            async for token_data in openai_service.send_brainstorm_message_stream(
                course_id=course_id,
                thread_id=thread_id,
                message=message.message,
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
        logger.error(f"Error in send_brainstorm_message_stream: {str(e)}")
        raise handle_course_error(e)