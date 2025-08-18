import io
import logging
from typing import List
from fastapi import UploadFile, HTTPException
from ..utils.prompt_parser import PromptParser
from ..utils.openai_client import client
from ..config.settings import settings
import json
from app.services.mongo import get_evaluation_by_evaluation_id

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
            # Create a BytesIO object with the file content and set the name
            file_content = file.file.read()
            file_obj = io.BytesIO(file_content)
            file_obj.name = file.filename
            
            openai_file_id = create_file(file_obj)

            # Connect file to vector store
            batch = connect_file_to_vector_store(vector_store_id, openai_file_id)

            vs_files = client.vector_stores.files.list(vector_store_id=vector_store_id)
            for vs_file in vs_files:
                if vs_file.id==openai_file_id:
                    print("file found in vector store")

            logger.info(f"Connected file {file.filename} to vector store {vector_store_id}")

        except Exception as e:
            logger.error(f"Error processing file {file.filename}: {str(e)}")
            continue

    return "Resources uploaded successfully"

def clean_text(text: str):
    try:
        response = client.chat.completions.create(
            model=settings.OPENAI_MODEL,
            messages=[
                {
                    "role": "system",
                    "content": "You are a helpful assistant that cleans AI-generated messages. Your job is to remove any irrelevant or excessive introductory or concluding text — such as apologies, disclaimers, or requests for confirmation — that do not contribute to the core output.\n\nFocus on keeping only the core meaningful content such as course outcomes, summaries, tables, or actual suggestions.\n\nIf there is any core component or content to be saved, preserve that fully.\n\nIf no meaningful content is found (e.g., just a warning or error message), return it as-is without adding any explanation or comment."
                },
                {"role": "user", "content": text}
            ]
        )

        return response.choices[0].message.content
    except Exception as e:
        logger.error(f"Error cleaning text: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

def upload_evaluation_files(user_id: str, course_id: str, vector_store_id: str, mark_scheme: UploadFile, answer_sheets: List[UploadFile]) -> dict:
    content = mark_scheme.file.read()
    file_obj = io.BytesIO(content)
    file_obj.name = mark_scheme.filename
    openai_mark_scheme_file_id = create_file(file_obj)
    connect_file_to_vector_store(vector_store_id, openai_mark_scheme_file_id)

    answer_sheet_ids = []
    for answer_sheet in answer_sheets:
        content = answer_sheet.file.read()
        file_obj = io.BytesIO(content)
        file_obj.name = answer_sheet.filename
        openai_answer_sheet_file_id = create_file(file_obj)
        connect_file_to_vector_store(vector_store_id, openai_answer_sheet_file_id)
        answer_sheet_ids.append(openai_answer_sheet_file_id)

    return {"mark_scheme": openai_mark_scheme_file_id, "answer_sheet": answer_sheet_ids}

def create_evaluation_assistant():
    try:
        assistant = client.beta.assistants.create(
            name="Evaluation Assistant",
            instructions="You are an assistant that extracts structured evaluation data from files.",
            model=settings.OPENAI_MODEL,
            tools=[{"type": "file_search"}]
        )
        logger.info(f"Created Evaluation Assistant {assistant.id}")
        return assistant.id
    except Exception as e:
        logger.error(f"Error creating Evaluation Assistant: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

def extract_mark_scheme(evaluation_id: str, user_id: str, mark_scheme_file_id: str) -> dict:
    """
    Extract evaluation content from mark scheme and answer sheets using
    OpenAI structured outputs.

    Returns structured JSON matching the defined schema.
    """
    evaluation_assistant_id = create_evaluation_assistant()
    
    extraction_schema = {
        "type": "object",
        "properties": {
            "mark_scheme": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "question_number": {"type": "string"},
                        "question_text": {"type": "string"},
                        "correct_answer": {"type": "string"},
                        "mark_scheme": {"type": "string"}
                    },
                    "required": ["question_number", "question_text", "correct_answer", "mark_scheme"]
                }
            }
        },
        "required": ["mark_scheme"]
    }

    # Create thread with attachments
    thread = client.beta.threads.create(
        messages=[
            {
                "role": "user",
                "content": "Extract ALL questions, their correct answers, and the marking scheme from the provided mark scheme document; do not skip any questions; preserve original numbering/order; return ONLY valid JSON.",
                "attachments": [
                    {"file_id": mark_scheme_file_id, "tools": [{"type": "file_search"}]}
                ]
            }
        ]
    )

    # Run assistant with structured output
    run = client.beta.threads.runs.create(
        thread_id=thread.id,
        assistant_id=evaluation_assistant_id,
        response_format={
            "type": "json_schema",
            "json_schema": {"name": "mark_scheme_schema", "schema": extraction_schema}
        }
    )

    # Wait for completion
    while run.status in ["queued", "in_progress"]:
        run = client.beta.threads.runs.retrieve(thread_id=thread.id, run_id=run.id)

    # Get the response
    messages = client.beta.threads.messages.list(thread_id=thread.id)
    structured_output = messages.data[0].content[0].text.value
    
    # Parse JSON string to dictionary
    try:
        mark_scheme_result = json.loads(structured_output)
        return mark_scheme_result
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse mark scheme extraction as JSON: {structured_output}")
        raise HTTPException(status_code=500, detail=f"Invalid JSON response from OpenAI: {str(e)}")
    except Exception as e:
        logger.error(f"Error processing mark scheme extraction: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))



def extract_answer_sheets(evaluation_id: str, user_id: str, answer_sheet_file_ids: list[str]) -> dict:
    """
    Extract evaluation content from answer sheets using OpenAI structured outputs.
    Processes all answer sheet files and returns structured data with file attribution.

    Returns structured JSON matching the defined schema.
    """
    evaluation_assistant_id = create_evaluation_assistant()
    
    extraction_schema = {
        "type": "object",
        "properties": {
            "answer_sheets": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "file_id": {"type": "string"},
                        "student_name": {"type": "string"},
                        "answers": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "question_number": {"type": "string"},
                                    "question_text": {"type": "string"},
                                    "student_answer": {"type": "string"}
                                },
                                "required": ["question_number", "question_text", "student_answer"]
                            }
                        }
                    },
                    "required": ["file_id", "student_name", "answers"]
                }
            }
        },
        "required": ["answer_sheets"]
    }

    # Create thread with attachments
    thread = client.beta.threads.create(
        messages=[
            {
                "role": "user",
                "content": f"Extract ALL questions and answers from each of the {len(answer_sheet_file_ids)} provided answer sheet files; include student name if available; for every question always include question text, preserving numbering/order; if the answer is missing, blank, or 'N/A', set 'answer' to null; capture answers exactly as written; return ONLY valid JSON.",
                "attachments": [
                    {"file_id": fid, "tools": [{"type": "file_search"}]}
                    for fid in answer_sheet_file_ids
                ]
            }
        ]
    )

    # Run assistant with structured output
    run = client.beta.threads.runs.create(
        thread_id=thread.id,
        assistant_id=evaluation_assistant_id,
        response_format={
            "type": "json_schema",
            "json_schema": {"name": "answer_sheets_schema", "schema": extraction_schema}
        }
    )

    # Wait for completion
    while run.status in ["queued", "in_progress"]:
        run = client.beta.threads.runs.retrieve(thread_id=thread.id, run_id=run.id)

    # Get the response
    messages = client.beta.threads.messages.list(thread_id=thread.id)
    structured_output = messages.data[0].content[0].text.value
    
    # Parse JSON string to dictionary
    try:
        answer_sheets_result = json.loads(structured_output)
        return answer_sheets_result
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse answer sheets extraction as JSON: {structured_output}")
        raise HTTPException(status_code=500, detail=f"Invalid JSON response from OpenAI: {str(e)}")
    except Exception as e:
        logger.error(f"Error processing answer sheets extraction: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


def evaluate_files(evaluation_id: str, user_id: str):
    """
    Evaluate student answers against mark scheme using previously extracted structured data.
    
    Returns structured JSON with scores and feedback for each answer.
    """
    
    # Get evaluation data from MongoDB
    evaluation = get_evaluation_by_evaluation_id(evaluation_id)
    mark_scheme_file_id = evaluation["mark_scheme_file_id"]
    answer_sheet_file_ids = evaluation["answer_sheet_file_ids"]
    
    # Extract structured data from files first
    extracted_mark_scheme = extract_mark_scheme(evaluation_id, user_id, mark_scheme_file_id)
    extracted_answer_sheets = extract_answer_sheets(evaluation_id, user_id, answer_sheet_file_ids)
    
    evaluation_assistant_id = create_evaluation_assistant()
    
    # Build payload for prompt rendering with extracted data
    payload = {
        "evaluation_id": evaluation_id,
        "user_id": user_id,
        "mark_scheme": json.dumps(extracted_mark_scheme, indent=2),
        "answer_sheets": json.dumps(extracted_answer_sheets, indent=2),
        "num_answer_sheets": len(answer_sheet_file_ids)
    }
    
    # Render evaluation prompt
    evaluation_prompt = PromptParser().render_prompt(
        "app/prompts/evaluation/evaluation.json",
        payload
    )
    
    logger.info(f"Evaluation prompt rendered for evaluation {evaluation_id}")
    
    evaluation_schema = {
        "type": "object",
        "properties": {
            "evaluation_id": {"type": "string"},
            "students": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "student_name": {"type": "string"},
                        "file_id": {"type": "string"},
                        "answers": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "question_number": {"type": "string"},
                                    "question_text": {"type": "string"},
                                    "student_answer": {"type": "string"},
                                    "correct_answer": {"type": "string"},
                                    "score": {"type": "number"},
                                    "max_score": {"type": "number"},
                                    "feedback": {"type": "string"}
                                },
                                "required": [
                                    "question_number",
                                    "question_text",
                                    "student_answer",
                                    "correct_answer",
                                    "score",
                                    "max_score",
                                    "feedback"
                                ]
                            }
                        },
                        "total_score": {"type": "number"},
                        "max_total_score": {"type": "number"}
                    },
                    "required": ["student_name", "file_id", "answers", "total_score", "max_total_score"]
                }
            }
        },
        "required": ["evaluation_id", "students"]
    }

    # Create thread without file attachments since we're using extracted data
    thread = client.beta.threads.create(
        messages=[
            {
                "role": "user",
                "content": evaluation_prompt
            }
        ]
    )

    # Run assistant with structured output
    run = client.beta.threads.runs.create(
        thread_id=thread.id,
        assistant_id=evaluation_assistant_id,
        response_format={
            "type": "json_schema",
            "json_schema": {"name": "evaluation_schema", "schema": evaluation_schema}
        }
    )

    # Wait for completion with better error handling
    max_attempts = 60  # 5 minutes max wait time
    attempts = 0
    while run.status in ["queued", "in_progress"] and attempts < max_attempts:
        import time
        time.sleep(5)  # Wait 5 seconds between checks
        run = client.beta.threads.runs.retrieve(thread_id=thread.id, run_id=run.id)
        attempts += 1
        logger.info(f"Evaluation run status: {run.status} (attempt {attempts})")

    # Check final run status
    if run.status == "failed":
        logger.error(f"OpenAI run failed for evaluation {evaluation_id}: {run.last_error}")
        raise HTTPException(status_code=500, detail=f"OpenAI evaluation failed: {run.last_error}")
    elif run.status == "cancelled":
        logger.error(f"OpenAI run was cancelled for evaluation {evaluation_id}")
        raise HTTPException(status_code=500, detail="OpenAI evaluation was cancelled")
    elif run.status not in ["completed"]:
        logger.error(f"OpenAI run did not complete successfully. Status: {run.status}")
        raise HTTPException(status_code=500, detail=f"OpenAI evaluation timeout or unexpected status: {run.status}")

    # Get the response
    messages = client.beta.threads.messages.list(thread_id=thread.id)
    if not messages.data:
        logger.error(f"No messages found in thread for evaluation {evaluation_id}")
        raise HTTPException(status_code=500, detail="No response from OpenAI")

    # Get the latest assistant message
    assistant_message = None
    for message in messages.data:
        if message.role == "assistant":
            assistant_message = message
            break
    
    if not assistant_message:
        logger.error(f"No assistant message found for evaluation {evaluation_id}")
        raise HTTPException(status_code=500, detail="No assistant response found")

    structured_output = assistant_message.content[0].text.value
    logger.info(f"Raw OpenAI response for evaluation {evaluation_id}: {structured_output[:500]}...")
    
    # Parse JSON string to dictionary
    try:
        evaluation_result = json.loads(structured_output)
        
        # Validate that we got actual data, not schema
        if "properties" in evaluation_result and "type" in evaluation_result:
            logger.error(f"OpenAI returned schema instead of data for evaluation {evaluation_id}")
            raise HTTPException(status_code=500, detail="OpenAI returned schema definition instead of evaluation results")
        
        # Validate required fields
        if "evaluation_id" not in evaluation_result or "students" not in evaluation_result:
            logger.error(f"Invalid evaluation result structure for evaluation {evaluation_id}: {evaluation_result}")
            raise HTTPException(status_code=500, detail="Invalid evaluation result structure")
        
        logger.info(f"Successfully completed evaluation {evaluation_id} for {len(evaluation_result.get('students', []))} students")
        return evaluation_result
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse OpenAI response as JSON for evaluation {evaluation_id}: {structured_output}")
        raise HTTPException(status_code=500, detail=f"Invalid JSON response from OpenAI: {str(e)}")
    except Exception as e:
        logger.error(f"Error processing evaluation result for evaluation {evaluation_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))



