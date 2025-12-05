import logging
import asyncio
import time
from io import BytesIO
from typing import Optional
from openai import AssistantEventHandler
from typing_extensions import override
from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from datetime import datetime
from ..utils.verify_keycloak_token import verify_keycloak_token as verify_token
from ..utils.prompt_parser import PromptParser
from ..utils.openai_client import client
from ..utils.text_to_pdf import text_to_pdf
from ..services.mongo import get_course, create_asset, get_assets_by_course_id, get_asset_by_course_id_and_asset_name, delete_asset_from_db, create_resource, get_user_display_name
from ..services.openai_service import clean_text
from ..services.task_manager import task_manager, TaskStatus

logger = logging.getLogger(__name__)
router = APIRouter()

class AssetViewResponse(BaseModel):
    asset_name: str
    asset_type: str
    asset_category: str
    asset_content: str
    asset_last_updated_by: str
    asset_last_updated_at: str
    created_by_user_id: Optional[str] = None

class AssetPromptRequest(BaseModel):
    user_prompt: str

class AssetRequest(BaseModel):
    file_names: list[str]

class AssetResponse(BaseModel):
    response: str
    thread_id: str

class TaskResponse(BaseModel):
    task_id: str
    status: str
    message: str

class TaskStatusResponse(BaseModel):
    task_id: str
    status: str
    result: Optional[dict] = None
    error: Optional[str] = None
    metadata: Optional[dict] = None

class AssetCreateResponse(BaseModel):
    message: str

class AssetCreateRequest(BaseModel):
    content: str

class Asset(BaseModel):
    asset_name: str
    asset_type: str
    asset_category: str
    asset_content: str
    asset_last_updated_by: str
    asset_last_updated_at: str
    created_by_user_id: Optional[str] = None

class AssetListResponse(BaseModel):
    assets: list[Asset]

class ImageRequest(BaseModel):
    prompt: str

class ImageResponse(BaseModel):
    image_url: str

class TextToPdfRequest(BaseModel):
    content: str
    filename: Optional[str] = None

class AssetChatStreamHandler(AssistantEventHandler):
    def __init__(self):
        super().__init__()  # ✅ This is the fix
        self.response_text = ""

    @override
    def on_text_delta(self, delta, snapshot):
        print(delta.value, end="", flush=True)
        self.response_text += delta.value
        

def construct_input_variables(course: dict, file_names: list[str]) -> dict:
    input_variables = {
        "course_name": course.get("name", ""),
        "course_level": course.get("settings", {}).get("course_level", ""),
        "study_area": course.get("settings", {}).get("study_area", ""),
        "pedagogical_components": course.get("settings", {}).get("pedagogical_components", ""),
        "file_names": file_names
    }
    return input_variables

def _process_asset_chat_background(task_id: str, course_id: str, asset_type_name: str, file_names: list, user_id: str):
    """Background task to process asset chat generation"""
    thread_id = None  # Initialize thread_id for recovery purposes
    try:
        task_manager.mark_processing(task_id)
        logger.info(f"Starting background task {task_id} for asset '{asset_type_name}'")
        
        course = get_course(course_id)
        if not course or "assistant_id" not in course:
            task_manager.mark_failed(task_id, "Course or assistant not found")
            return

        assistant_id = course["assistant_id"]

        # Check if mark-scheme and extract questions first
        extracted_questions = ""
        if asset_type_name == "mark-scheme":
            # First extract questions using qp-extraction
            input_variables_qp = construct_input_variables(course, file_names)
            parser_qp = PromptParser()
            prompt_qp = parser_qp.get_asset_prompt("qp-extraction", input_variables_qp)
            
            thread_qp = client.beta.threads.create()
            client.beta.threads.messages.create(
                thread_id=thread_qp.id,
                role="user",
                content=prompt_qp
            )
            
            handler_qp = AssetChatStreamHandler()
            try:
                with client.beta.threads.runs.stream(
                    thread_id=thread_qp.id,
                    assistant_id=assistant_id,
                    event_handler=handler_qp
                ) as stream:
                    stream.until_done()
            except Exception as stream_error:
                logger.warning(f"Stream interrupted during question extraction in task {task_id}: {stream_error}")
                # Continue - we can still get the response from thread messages
            
            try:
                messages_qp = client.beta.threads.messages.list(thread_id=thread_qp.id)
                if not messages_qp.data or len(messages_qp.data) == 0:
                    raise Exception("No messages found in question extraction thread")
                extracted_questions = messages_qp.data[0].content[0].text.value
                logger.info(f"Extracted questions: {extracted_questions}")
            except Exception as msg_error:
                logger.error(f"Error retrieving extracted questions from thread {thread_qp.id}: {msg_error}")
                # Don't fail the entire task - continue without extracted questions
                extracted_questions = ""

        # Prepare prompt
        input_variables = construct_input_variables(course, file_names)
        
        # Add extracted_questions to input_variables if mark-scheme
        if asset_type_name == "mark-scheme":
            input_variables["extracted_questions"] = extracted_questions
        
        parser = PromptParser()
        prompt = parser.get_asset_prompt(asset_type_name, input_variables)
        logger.info(f"Prompt for asset '{asset_type_name}': {prompt}")

        # Create a new thread
        thread = client.beta.threads.create()
        thread_id = thread.id

        # Send message to thread
        client.beta.threads.messages.create(
            thread_id=thread_id,
            role="user",
            content=prompt
        )

        # Stream run with proper error handling
        handler = AssetChatStreamHandler()
        stream_was_interrupted = False
        try:
            with client.beta.threads.runs.stream(
                thread_id=thread_id,
                assistant_id=assistant_id,
                event_handler=handler
            ) as stream:
                stream.until_done()
        except Exception as stream_error:
            stream_was_interrupted = True
            logger.warning(f"Stream interrupted in task {task_id}, but continuing to retrieve response: {stream_error}")
            # Continue - we can still get the response from thread messages even if stream was interrupted

        # Get complete response from thread messages with retry logic
        complete_response = None
        
        # First, check if handler accumulated any response text during streaming
        if handler.response_text and len(handler.response_text.strip()) > 0:
            logger.info(f"Using accumulated response text from handler for task {task_id}")
            complete_response = handler.response_text
        
        # If stream was interrupted, wait a bit for message to be written to thread
        if stream_was_interrupted:
            time.sleep(2)  # Wait 2 seconds for message to be persisted
        
        # Try to get response from thread messages with polling
        max_retries = 5
        retry_delay = 2
        for attempt in range(max_retries):
            try:
                messages = client.beta.threads.messages.list(thread_id=thread_id)
                if messages.data and len(messages.data) > 0:
                    latest_message = messages.data[0]
                    if latest_message.content and len(latest_message.content) > 0:
                        thread_response = latest_message.content[0].text.value
                        if thread_response and len(thread_response.strip()) > 0:
                            # Prefer thread response over handler response as it's more complete
                            complete_response = thread_response
                            logger.info(f"Retrieved response from thread messages for task {task_id}")
                            break
                else:
                    logger.warning(f"No messages found in thread on attempt {attempt + 1}")
            except Exception as msg_error:
                logger.warning(f"Error retrieving messages on attempt {attempt + 1}: {msg_error}")
            
            # Wait before next retry (except on last attempt)
            if attempt < max_retries - 1:
                time.sleep(retry_delay)
        
        # Use handler response if thread messages failed
        if not complete_response or len(complete_response.strip()) == 0:
            if handler.response_text and len(handler.response_text.strip()) > 0:
                logger.info(f"Falling back to handler accumulated text for task {task_id}")
                complete_response = handler.response_text
            else:
                raise Exception("No response available from stream handler or thread messages")

        # Mark task as completed with result
        result = {
            "response": complete_response,
            "thread_id": thread_id
        }
        task_manager.mark_completed(task_id, result)
        logger.info(f"Completed background task {task_id} for asset '{asset_type_name}'")

    except Exception as e:
        error_msg = str(e)
        # Don't fail the task if it's just a connection interruption - response might still be available
        if "incomplete chunked read" in error_msg.lower() or "peer closed connection" in error_msg.lower():
            logger.warning(f"Connection interrupted in background task {task_id} for asset '{asset_type_name}': {error_msg}")
            # Try to get the response anyway if thread_id exists
            if thread_id:
                try:
                    messages = client.beta.threads.messages.list(thread_id=thread_id)
                    if messages.data and len(messages.data) > 0:
                        latest_message = messages.data[0]
                        if latest_message.content and len(latest_message.content) > 0:
                            complete_response = latest_message.content[0].text.value
                            result = {
                                "response": complete_response,
                                "thread_id": thread_id
                            }
                            task_manager.mark_completed(task_id, result)
                            logger.info(f"Retrieved response after connection interruption for task {task_id}")
                            return
                except Exception as recovery_error:
                    logger.error(f"Failed to recover response after connection error: {recovery_error}")
        
        logger.error(f"Exception in background task {task_id} for asset '{asset_type_name}': {error_msg}")
        task_manager.mark_failed(task_id, error_msg)

@router.post("/courses/{course_id}/asset_chat/{asset_type_name}", response_model=TaskResponse)
async def create_asset_chat(
    course_id: str, 
    asset_type_name: str, 
    request: AssetRequest, 
    background_tasks: BackgroundTasks,
    user_id: str = Depends(verify_token)
):
    """
    Create asset chat generation task (runs in background)
    Returns task_id immediately - use /tasks/{task_id} to check status
    """
    try:
        # Backwards compatibility: Convert old "lesson-plans" to "lecture"
        if asset_type_name == "lesson-plans":
            asset_type_name = "lecture"
        
        # Validate course exists
        course = get_course(course_id)
        if not course or "assistant_id" not in course:
            raise HTTPException(status_code=404, detail="Course or assistant not found")

        # Create task
        task_id = task_manager.create_task(
            task_type="asset_chat_create",
            metadata={
                "course_id": course_id,
                "asset_type_name": asset_type_name,
                "user_id": user_id,
                "file_count": len(request.file_names)
            }
        )

        # Schedule background task
        background_tasks.add_task(
            _process_asset_chat_background,
            task_id,
            course_id,
            asset_type_name,
            request.file_names,
            user_id
        )

        return TaskResponse(
            task_id=task_id,
            status="pending",
            message=f"Asset generation task created for '{asset_type_name}'"
        )

    except Exception as e:
        logger.error(f"Exception in create_asset_chat for asset '{asset_type_name}': {e}")
        raise HTTPException(status_code=500, detail=str(e))

def _process_continue_asset_chat_background(task_id: str, course_id: str, asset_name: str, thread_id: str, user_prompt: str, user_id: str):
    """Background task to process asset chat continuation"""
    try:
        task_manager.mark_processing(task_id)
        logger.info(f"Starting background task {task_id} for continue asset '{asset_name}'")
        
        course = get_course(course_id)
        if not course or "assistant_id" not in course:
            task_manager.mark_failed(task_id, "Course or assistant not found")
            return
        assistant_id = course["assistant_id"]

        # Send user prompt to the thread
        client.beta.threads.messages.create(
            thread_id=thread_id,
            role="user",
            content=user_prompt
        )

        # Create and stream the run
        handler = AssetChatStreamHandler()
        with client.beta.threads.runs.stream(
            thread_id=thread_id,
            assistant_id=assistant_id,
            event_handler=handler
        ) as stream:
            stream.until_done()

        # Get complete response from thread messages
        messages = client.beta.threads.messages.list(thread_id=thread_id)
        latest_message = messages.data[0]
        complete_response = latest_message.content[0].text.value
        
        # Mark task as completed with result
        result = {
            "response": complete_response,
            "thread_id": thread_id
        }
        task_manager.mark_completed(task_id, result)
        logger.info(f"Completed background task {task_id} for continue asset '{asset_name}'")

    except Exception as e:
        logger.error(f"Exception in background task {task_id} for continue asset '{asset_name}': {e}")
        task_manager.mark_failed(task_id, str(e))

@router.put("/courses/{course_id}/asset_chat/{asset_name}", response_model=TaskResponse)
async def continue_asset_chat(
    course_id: str, 
    asset_name: str, 
    thread_id: str, 
    request: AssetPromptRequest, 
    background_tasks: BackgroundTasks,
    user_id: str = Depends(verify_token)
):
    """
    Continue asset chat conversation (runs in background)
    Returns task_id immediately - use /tasks/{task_id} to check status
    """
    try:
        # Validate course exists
        course = get_course(course_id)
        if not course or "assistant_id" not in course:
            raise HTTPException(status_code=404, detail="Course or assistant not found")

        # Create task
        task_id = task_manager.create_task(
            task_type="asset_chat_continue",
            metadata={
                "course_id": course_id,
                "asset_name": asset_name,
                "thread_id": thread_id,
                "user_id": user_id
            }
        )

        # Schedule background task
        background_tasks.add_task(
            _process_continue_asset_chat_background,
            task_id,
            course_id,
            asset_name,
            thread_id,
            request.user_prompt,
            user_id
        )

        return TaskResponse(
            task_id=task_id,
            status="pending",
            message=f"Asset chat continuation task created for '{asset_name}'"
        )

    except Exception as e:
        logger.error(f"Exception in continue_asset_chat for asset '{asset_name}': {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/courses/{course_id}/assets", response_model=AssetCreateResponse)
def save_asset(course_id: str, asset_name: str, asset_type: str, request: AssetCreateRequest, user_id: str = Depends(verify_token)):
    # TODO: Make this a configuration for the app overall, add the remaining categories and asset types here
    category_map = {
        "brainstorm": "curriculum",
        "course-outcomes": "curriculum",
        "concept-plan": "curriculum",
        "modules": "curriculum",
        "lecture": "curriculum",
        "course-notes": "curriculum",
        "project": "assessments",
        "activity": "assessments",
        "quiz": "assessments",
        "question-paper": "assessments",
        "mark-scheme": "assessments",
        "mock-interview": "assessments",
    }
    # Default to a safe category so saving never fails due to unmapped type
    asset_category = category_map.get(asset_type, "content")
    #this text should go to openai and get cleaned up and than use the text to create the asset
    #TODO: do the cleaning for all except for mark-scheme
    if asset_type != "mark-scheme":
        cleaned_text = clean_text(request.content)
    else:
        cleaned_text = request.content
    
    # Get user's display name for the asset
    user_display_name = get_user_display_name(user_id)
    if not user_display_name:
        user_display_name = "Unknown User"
    
    try:
        create_asset(course_id, asset_name, asset_category, asset_type, cleaned_text, user_display_name, datetime.now().strftime("%d %B %Y %H:%M:%S"), user_id)
    except ValueError as e:
        # Duplicate asset name or other validation errors
        raise HTTPException(status_code=409, detail=str(e))
    return AssetCreateResponse(message=f"Asset '{asset_name}' created successfully")

@router.post("/courses/{course_id}/assets/pdf")
def generate_asset_pdf(
    course_id: str,
    request: TextToPdfRequest,
    user_id: str = Depends(verify_token),
):
    """Generate a PDF from provided text content and stream it back to the client."""

    course = get_course(course_id)
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")

    content = request.content.strip()
    if not content:
        raise HTTPException(status_code=400, detail="Content must not be empty")

    pdf_bytes = text_to_pdf(content)
    filename = request.filename or f"{course_id}-asset.pdf"

    return StreamingResponse(
        BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )

@router.get("/courses/{course_id}/assets", response_model=AssetListResponse)
def get_assets(course_id: str, user_id: str = Depends(verify_token)):
    assets = get_assets_by_course_id(course_id)
    return AssetListResponse(assets=assets)

@router.get("/courses/{course_id}/assets/{asset_name}/view", response_model=AssetViewResponse)
def view_asset(course_id: str, asset_name: str, user_id: str = Depends(verify_token)):
    asset = get_asset_by_course_id_and_asset_name(course_id, asset_name)
    if not asset:
        raise HTTPException(status_code=404, detail="Asset not found")
    return AssetViewResponse(
        asset_name=asset["asset_name"], 
        asset_type=asset["asset_type"], 
        asset_category=asset["asset_category"], 
        asset_content=asset["asset_content"], 
        asset_last_updated_by=asset["asset_last_updated_by"], 
        asset_last_updated_at=asset["asset_last_updated_at"],
        created_by_user_id=asset.get("created_by_user_id")
    )

@router.post("/courses/{course_id}/assets/image", response_model=ImageResponse)
def create_image(course_id: str, asset_type_name: str, user_id: str = Depends(verify_token)):
    course = get_course(course_id)
    if not course or "assistant_id" not in course:
        raise HTTPException(status_code=404, detail="Course or assistant not found")

    input_variables = construct_input_variables(course, [])
    parser = PromptParser()
    prompt = parser.get_asset_prompt(asset_type_name, input_variables)

    image = client.images.generate(
        model="dall-e-3",
        prompt=prompt,
        n=1,
        size="1024x1024"
    )

    # Extract URL
    image_url = image.data[0].url

    return ImageResponse(image_url=image_url)

#delete asset
@router.delete("/courses/{course_id}/assets/{asset_name}", response_model=AssetCreateResponse)
def delete_asset(course_id: str, asset_name: str, user_id: str = Depends(verify_token)):
    try:
        # Check if asset exists
        asset = get_asset_by_course_id_and_asset_name(course_id, asset_name)
        if not asset:
            raise HTTPException(status_code=404, detail="Asset not found")
        
        # Delete asset using the dedicated function
        delete_asset_from_db(course_id, asset_name)
        
        return AssetCreateResponse(message=f"Asset '{asset_name}' deleted successfully")
    except Exception as e:
        logger.error(f"Error deleting asset '{asset_name}': {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/courses/{course_id}/assets/{asset_name}/save-as-resource", response_model=AssetCreateResponse)
def save_asset_as_resource(course_id: str, asset_name: str, request: AssetCreateRequest, user_id: str = Depends(verify_token)):
    """Save an existing asset as a resource so it can be viewed in the resource view modal"""
    try:
        
        # 2. Get the content from the frontend request
        content = request.content
        logger.info(f"Received content for asset '{asset_name}': {content[:100] if content else 'None'}...")
        if not content:
            raise HTTPException(status_code=404, detail="Content not provided")

        
        # 5. Save the content as a resource
        logger.info(f"Saving resource: {asset_name} with content length: {len(content)}")
        create_resource(course_id, asset_name, content)
        logger.info(f"Resource saved successfully: {asset_name}")
        
        return AssetCreateResponse(message=f"Asset '{asset_name}' saved as resource '{asset_name}' successfully")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error saving asset '{asset_name}' as resource: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

# Task Status Endpoints
@router.get("/tasks/{task_id}", response_model=TaskStatusResponse)
async def get_task_status(task_id: str, user_id: str = Depends(verify_token)):
    """
    Get the status of a background task
    Use this to poll for task completion after starting an async asset generation
    """
    task = task_manager.get_task(task_id)
    
    if not task:
        raise HTTPException(status_code=404, detail=f"Task {task_id} not found")
    
    return TaskStatusResponse(
        task_id=task.task_id,
        status=task.status.value,
        result=task.result,
        error=task.error,
        metadata=task.metadata
    )

@router.delete("/tasks/{task_id}")
async def cancel_task(task_id: str, user_id: str = Depends(verify_token)):
    """
    Cancel a pending or running task
    Note: Tasks already in progress will complete but results won't be stored
    """
    task = task_manager.get_task(task_id)
    
    if not task:
        raise HTTPException(status_code=404, detail=f"Task {task_id} not found")
    
    if task.status in [TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED]:
        return {"message": f"Task {task_id} already finished with status: {task.status.value}"}
    
    task_manager.mark_cancelled(task_id)
    return {"message": f"Task {task_id} cancelled"}


