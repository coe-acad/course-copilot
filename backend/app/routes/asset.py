from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from ..utils.prompt_parser import PromptParser
from ..utils.openai_client import client
import logging
from ..services.storage_course import storage_service
from ..utils.input_variables import gather_input_variables

logger = logging.getLogger(__name__)
router = APIRouter()

class AssetRequest(BaseModel):
    input_variables: dict

class AssetResponse(BaseModel):
    response: str
    thread_id: str

@router.post("/courses/{course_id}/assets/{asset_name}", response_model=AssetResponse)
async def create_asset(course_id: str, asset_name: str, request: AssetRequest):
    """
    Create an asset by sending the constructed prompt (for the given asset_name) to a new OpenAI chat thread.
    """
    try:
        # Get the course and assistant_id
        course = storage_service.get_course(course_id)
        if not course or "assistant_id" not in course:
            raise HTTPException(status_code=404, detail="Course or assistant not found")
        assistant_id = course["assistant_id"]

        # Gather all input variables (course info, settings, resources, user input)
        input_variables = gather_input_variables(
            course_id=course_id,
            user_id=course.get("user_id"),
            thread_id=None,  # If asset-level resources are needed, pass thread_id
            user_input=request.input_variables
        )
        logger.info(f"Input variables for asset '{asset_name}': {input_variables}")

        # Construct the prompt using PromptParser
        parser = PromptParser()
        prompt = parser.get_asset_prompt(asset_name, input_variables)
        logger.info(f"Prompt for asset '{asset_name}': {prompt}")

        # Create a new OpenAI thread
        thread = client.beta.threads.create()
        thread_id = thread.id

        # Link the thread to the course in the database for this asset
        storage_service.create_asset_thread(course_id, asset_name, thread_id)

        # Send the prompt as a message to the thread
        message_response = client.beta.threads.messages.create(
            thread_id=thread_id,
            role="user",
            content=prompt
        )

        # If this is a course-outcomes asset, send the default welcome message
        if asset_name == "course-outcomes":
            # Gather checked-in files for display
            course_resources = storage_service.get_resources(course_id, user_id=course.get("user_id"))
            asset_resources = storage_service.get_resources(course_id, thread_id=thread_id, user_id=course.get("user_id"))
            all_resources = course_resources + asset_resources
            checked_in_files = [
                r.get("title", r.get("fileName", "Unknown file"))
                for r in all_resources
                if r.get("status") == "checked_in"
            ]
            if checked_in_files:
                files_text = f"**Checked-in Files:** {', '.join(checked_in_files)} ({len(checked_in_files)} file{'s' if len(checked_in_files) != 1 else ''})"
            else:
                files_text = "**Checked-in Files:** No files currently available"
            course_name = course.get("name", "Unknown Course")
            welcome_message = f"""✅ Course Outcomes Generator Ready\n\nI'm here to help you create comprehensive, measurable course outcomes for your course.\n\n**Course Name:** {course_name}\n{files_text}\n\nThe system is ready to help you generate course outcomes!\n\nType 'proceed' or ask any questions to get started."""
            from datetime import datetime
            from ..services import openai_service
            await openai_service.save_course_outcomes_message(course_id, thread_id, {
                "role": "assistant",
                "content": welcome_message,
                "timestamp": datetime.utcnow().isoformat(),
                "user_id": course.get("user_id"),
                "assistant_id": assistant_id
            })

        # Run the assistant to get a response
        # The thread is linked to the assistant by passing assistant_id here
        run = client.beta.threads.runs.create(
            thread_id=thread_id,
            assistant_id=assistant_id  # Use the course's assistant_id here
        )

        # Wait for the run to complete (async polling)
        import asyncio
        while True:
            run_status = client.beta.threads.runs.retrieve(thread_id=thread_id, run_id=run.id)
            if run_status.status in ("completed", "failed", "cancelled", "expired"):
                break
            await asyncio.sleep(1)

        if run_status.status != "completed":
            raise Exception(f"OpenAI run did not complete successfully: {run_status.status}")

        # Get the latest message from the thread
        messages = client.beta.threads.messages.list(thread_id=thread_id)
        # Find the latest assistant message
        assistant_message = next((m for m in reversed(messages.data) if m.role == "assistant"), None)
        if not assistant_message:
            raise Exception("No assistant response found in thread.")
        response_text = "\n".join([c.text.value for c in assistant_message.content if hasattr(c, 'text') and hasattr(c.text, 'value')])
        return AssetResponse(response=response_text, thread_id=thread_id)
    except Exception as e:
        logger.error(f"Exception in create_asset for asset '{asset_name}': {e}")
        raise HTTPException(status_code=500, detail=str(e)) 