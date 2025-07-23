from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from ..utils.prompt_parser import PromptParser
from ..utils.openai_client import client
import logging
from ..services.storage_course import storage_service

logger = logging.getLogger(__name__)
router = APIRouter()

class AssetRequest(BaseModel):
    input_variables: dict

class AssetResponse(BaseModel):
    response: str

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

        # Construct the prompt using PromptParser
        parser = PromptParser()
        prompt = parser.get_asset_prompt(asset_name, request.input_variables)

        # Create a new OpenAI thread
        thread = client.beta.threads.create()
        thread_id = thread.id

        # Send the prompt as a message to the thread
        message_response = client.beta.threads.messages.create(
            thread_id=thread_id,
            role="user",
            content=prompt
        )

        # Run the assistant to get a response
        run = client.beta.threads.runs.create(
            thread_id=thread_id,
            assistant_id=assistant_id  # Use the course's assistant_id here
        )

        # Wait for the run to complete (polling)
        import time
        while True:
            run_status = client.beta.threads.runs.retrieve(thread_id=thread_id, run_id=run.id)
            if run_status.status in ("completed", "failed", "cancelled", "expired"):
                break
            time.sleep(1)

        if run_status.status != "completed":
            raise Exception(f"OpenAI run did not complete successfully: {run_status.status}")

        # Get the latest message from the thread
        messages = client.beta.threads.messages.list(thread_id=thread_id)
        # Find the latest assistant message
        assistant_message = next((m for m in reversed(messages.data) if m.role == "assistant"), None)
        if not assistant_message:
            raise Exception("No assistant response found in thread.")
        response_text = "\n".join([c.text.value for c in assistant_message.content if hasattr(c, 'text') and hasattr(c.text, 'value')])
        return AssetResponse(response=response_text)
    except Exception as e:
        logger.error(f"Exception in create_asset for asset '{asset_name}': {e}")
        raise HTTPException(status_code=500, detail=str(e)) 