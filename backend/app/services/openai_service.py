from ..utils.prompt_parser import PromptParser
from ..utils.openai_client import client
from ..config.settings import settings
import logging
from typing import List
from fastapi import UploadFile, HTTPException

logger = logging.getLogger(__name__)

def create_assistant():
    try:
        assistant_prompt = PromptParser().render_prompt("app/prompts/system/overall_context.json" , {})
        assistant = client.beta.assistants.create(
            name="Course Design Assistant",
            instructions=assistant_prompt,
            model=settings.OPENAI_MODEL,
            tools=[{"type": "file_search"}]
        )
        logger.info(f"Created Course Design Assistant {assistant.id}")
        return assistant.id
    except Exception as e:
        logger.error(f"Error creating Course Design Assistant: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

def create_file(file_obj):
    try:
        openai_file = client.files.create(file=file_obj, purpose="assistants")
        logger.info(f"Uploaded file for vector store: {file_obj.name} -> {openai_file.id}")
        return openai_file.id
    except Exception as e:
        logger.error(f"Error uploading file {file_obj.name}: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


def create_vector_store(assistant_id: str):
    try:
        vector_store = client.vector_stores.create(name=f"Course_{assistant_id}_files")
        logger.info(f"Created vector store {vector_store.id} for assistant {assistant_id}")
        return vector_store.id
    except Exception as e:
        logger.error(f"Error creating vector store for assistant {assistant_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

def connect_file_to_vector_store(vector_store_id: str, file_id: str):
    import time
    try:
        batch_add = client.vector_stores.file_batches.create(
            vector_store_id=vector_store_id,
            file_ids=[file_id]
        )

        logger.info(f"Connected file {file_id} to vector store {vector_store_id}, status: {batch_add.status}")
        return batch_add
    except Exception as e:
        logger.error(f"Error connecting file {file_id} to vector store {vector_store_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

def upload_resources(user_id: str, course_id: str, vector_store_id: str, files: List[UploadFile]):
    for file in files:
        try:
            file.file.name = file.filename
            openai_file_id = create_file(file.file)

            # Connect file to vector store
            batch = connect_file_to_vector_store(vector_store_id, openai_file_id)
            print(batch)

            vs_files = client.vector_stores.files.list(vector_store_id=vector_store_id)
            for file in vs_files:
                if file.id==openai_file_id:
                    print("file found in vector store")

            logger.info(f"Connected file {file.filename} to vector store {vector_store_id}")
            logger.info(f"Created resource {file.filename} in MongoDB")

        except Exception as e:
            logger.error(f"Error processing file {file.filename}: {str(e)}")
            continue

    return "Resources uploaded successfully"