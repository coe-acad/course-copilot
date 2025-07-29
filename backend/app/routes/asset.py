import asyncio
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from pymongo import response
from ..utils.prompt_parser import PromptParser
from ..utils.openai_client import client
import logging
from ..services.storage_course import storage_service
from ..utils.input_variables import gather_input_variables
from ..services.mongo import get_course, get_resources_by_course_id, create_resource

logger = logging.getLogger(__name__)
router = APIRouter()

class AssetRequest(BaseModel):
    input_variables: dict

class AssetResponse(BaseModel):
    response: str
    thread_id: str

@router.post("/courses/{course_id}/assets/{asset_name}", response_model=AssetResponse)
async def create_asset(user_id: str, course_id: str, asset_name: str, request: AssetRequest):
    """
    Create an asset by sending the constructed prompt (for the given asset_name) to a new OpenAI chat thread.
    """
    try:
        # Get the course and assistant_id
        course = get_course(course_id)
        if not course or "assistant_id" not in course:
            raise HTTPException(status_code=404, detail="Course or assistant not found")
        assistant_id = course["assistant_id"]
        print(assistant_id)
        vector_store_id = course["vector_store_id"]

        vs_files = client.vector_stores.files.list(vector_store_id=vector_store_id)

        for file_obj in vs_files.data:
            file_details = client.files.retrieve(file_obj.id)
            print(f"File ID: {file_obj.id}, Name: {file_details.filename}, Status: {file_obj.status}")

        # Construct the prompt using PromptParser
        parser = PromptParser()
        prompt = parser.get_asset_prompt(asset_name, request.input_variables)
        logger.info(f"Prompt for asset '{asset_name}': {prompt}")

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
        # The thread is linked to the assistant by passing assistant_id here
        run = client.beta.threads.runs.create(
            thread_id=thread_id,
            assistant_id=assistant_id  # Use the course's assistant_id here
        )

        # Wait for the run to complete (async polling)
        
        while run.status != "completed":
            run = client.beta.threads.runs.retrieve(thread_id=thread.id, run_id=run.id)
            print(f"Current run status: {run.status}")
            await asyncio.sleep(1)
            # In a real application, you would introduce a delay here

        messages = client.beta.threads.messages.list(thread_id=thread.id)
        response_text= messages.data[0].content[0].text.value
        print(response_text)
        return AssetResponse(response=response_text, thread_id=thread_id)
    except Exception as e:
        logger.error(f"Exception in create_asset for asset '{asset_name}': {e}")
        raise HTTPException(status_code=500, detail=str(e)) 