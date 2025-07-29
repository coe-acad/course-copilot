import asyncio
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from datetime import datetime
from ..utils.prompt_parser import PromptParser
from ..utils.openai_client import client
import logging
from ..services.mongo import get_course, create_asset, get_assets_by_course_id

logger = logging.getLogger(__name__)
router = APIRouter()

class AssetPromptRequest(BaseModel):
    user_prompt: str

class AssetRequest(BaseModel):
    file_names: list[str]

class AssetResponse(BaseModel):
    response: str

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

class AssetListResponse(BaseModel):
    assets: list[Asset]

def construct_input_variables(course: dict, file_names: list[str]) -> dict:
    input_variables = {
        "course_name": course.get("name", ""),
        "course_level": course.get("settings", {}).get("course_level", ""),
        "study_area": course.get("settings", {}).get("study_area", ""),
        "pedagogical_components": course.get("settings", {}).get("pedagogical_components", ""),
        "ask_clarifying_questions": course.get("settings", {}).get("ask_clarifying_questions", ""),
        "file_names": file_names
    }
    return input_variables

@router.post("/courses/{course_id}/asset_chat/{asset_type_name}", response_model=AssetResponse)
async def create_asset_chat(user_id: str, course_id: str, asset_type_name: str, request: AssetRequest):
    """
    Create an asset chat by sending the constructed prompt (for the given asset_name) to a new OpenAI chat thread.
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

        # Construct input variables dict using course settings and selected files
        input_variables = construct_input_variables(course, request.file_names)
        # Construct the prompt using PromptParser
        parser = PromptParser()
        prompt = parser.get_asset_prompt(asset_type_name, input_variables)
        logger.info(f"Prompt for asset '{asset_type_name}': {prompt}")

        # Create a new OpenAI thread
        thread = client.beta.threads.create()
        thread_id = thread.id
        print(thread_id)
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
            asyncio.sleep(1)
            # In a real application, you would introduce a delay here

        messages = client.beta.threads.messages.list(thread_id=thread.id)
        response_text= messages.data[0].content[0].text.value
        print(response_text)
        return AssetResponse(response=response_text, thread_id=thread_id)
    except Exception as e:
        logger.error(f"Exception in create_asset for asset '{asset_type_name}': {e}")
        raise HTTPException(status_code=500, detail=str(e)) 

@router.put("/courses/{course_id}/asset_chat/{asset_name}", response_model=AssetResponse)
def continue_asset_chat(user_id: str, course_id: str, asset_name: str, thread_id: str, request: AssetPromptRequest):
    try:
        course = get_course(course_id)
        if not course or "assistant_id" not in course:
            raise HTTPException(status_code=404, detail="Course or assistant not found")
        assistant_id = course["assistant_id"]

        # Send the prompt as a message to the thread
        message_response = client.beta.threads.messages.create(
            thread_id=thread_id,
            role="user",
            content= request.user_prompt
        )

        run = client.beta.threads.runs.create(
            thread_id=thread_id,
            assistant_id=assistant_id  # Use the course's assistant_id here
        )

        # Wait for the run to complete (async polling)
        
        while run.status != "completed":
            run = client.beta.threads.runs.retrieve(thread_id=thread_id, run_id=run.id)
            print(f"Current run status: {run.status}")
            asyncio.sleep(1)
            # In a real application, you would introduce a delay here

        messages = client.beta.threads.messages.list(thread_id=thread_id)
        response_text= messages.data[0].content[0].text.value
        print(response_text)
        return AssetResponse(response=response_text, thread_id=thread_id)
    except Exception as e:
        logger.error(f"Exception in continue_asset for asset '{asset_name}': {e}")
        raise HTTPException(status_code=500, detail=str(e)) 



@router.post("/courses/{course_id}/assets", response_model=AssetCreateResponse)
def save_asset(user_id: str, course_id: str, asset_name: str, asset_type: str, request: AssetCreateRequest):
    # TODO: Make this a configuration for the app overall, add the remaining categories and asset types here
    category_map = {
        "course-outcomes": "curriculum"
    }
    asset_category = category_map.get(asset_type)
    if not asset_category:
        raise HTTPException(status_code=400, detail=f"Invalid asset type: {asset_type}")
    create_asset(course_id, asset_name, asset_category, asset_type, request.content, "You", datetime.now().strftime("%d %B %Y %H:%M:%S"))
    return AssetCreateResponse(message=f"Asset '{asset_name}' created successfully")

@router.get("/courses/{course_id}/assets", response_model=AssetListResponse)
def get_assets(user_id: str, course_id: str):
    assets = get_assets_by_course_id(course_id)
    return AssetListResponse(assets=assets)