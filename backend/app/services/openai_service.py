import io
import logging
from typing import List
import time
from fastapi import UploadFile, HTTPException
from ..utils.prompt_parser import PromptParser
from ..utils.openai_client import client
from ..config.settings import settings
import json
from app.services.mongo import get_evaluation_by_evaluation_id
from concurrent.futures import ThreadPoolExecutor


logger = logging.getLogger(__name__)

def create_file(file_obj):
    try:
        openai_file = client.files.create(file=file_obj, purpose="assistants")
        logger.info(f"Uploaded file for vector store: {file_obj.name} -> {openai_file.id}")
        return openai_file.id
    except Exception as e:
        logger.error(f"Error uploading file {file_obj.name}: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


def create_vector_store(name: str):
    try:
        vector_store = client.vector_stores.create(name=f"Course_{name}_files")
        logger.info(f"Created vector store {vector_store.id} for course {name}")
        return vector_store.id
    except Exception as e:
        logger.error(f"Error creating vector store for course {name}: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

def connect_file_to_vector_store(vector_store_id: str, file_id: str):
    import time
    try:
        # Add file to vector store
        batch_add = client.vector_stores.file_batches.create(
            vector_store_id=vector_store_id,
            file_ids=[file_id]
        )
        
        # Polling until upload is complete (new API behavior)
        while True:
            # New Magic Here => retrieve vector store every time
            vs = client.vector_stores.retrieve(vector_store_id)
            status = vs.status
            logger.info(f"Vector store status: {status}")
            
            if status in ("completed", "failed"):
                if status == "completed":
                    logger.info("Upload completed.")
                else:
                    logger.error("Upload failed.")
                    raise HTTPException(status_code=500, detail="Vector store processing failed")
                break
            
            time.sleep(5)
        
        logger.info(f"File {file_id} added to vector store")
        return batch_add
    except Exception as e:
        logger.error(f"Error connecting file {file_id} to vector store {vector_store_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

def _process_single_resource_file(file: UploadFile, vector_store_id: str) -> None:
    """
    Helper to upload a single resource file to OpenAI and connect it to the vector store.
    Raises on error so the caller can decide how to handle failures.
    """
    # Create a BytesIO object with the file content and set the name
    file_content = file.file.read()
    if not file_content:
        raise HTTPException(status_code=400, detail=f"File {file.filename} is empty")

    file_obj = io.BytesIO(file_content)
    file_obj.name = file.filename

    openai_file_id = create_file(file_obj)

    # Connect file to vector store
    connect_file_to_vector_store(vector_store_id, openai_file_id)

    # Optional verification / logging
    vs_files = client.vector_stores.files.list(vector_store_id=vector_store_id)
    for vs_file in vs_files:
        if vs_file.id == openai_file_id:
            logger.info(f"File {file.filename} ({openai_file_id}) found in vector store {vector_store_id}")
            break

    logger.info(f"Connected file {file.filename} to vector store {vector_store_id}")


def upload_resources(user_id: str, course_id: str, vector_store_id: str, files: List[UploadFile]):
    """
    Upload multiple resources for a course.
    This processes files concurrently (bounded thread pool) to improve throughput
    while keeping per-file error handling the same (errors are logged and skipped).
    """
    if not files:
        return "No resources to upload"

    # Use a small thread pool to avoid hitting OpenAI rate limits too hard
    max_workers = min(4, len(files))

    try:
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {
                executor.submit(_process_single_resource_file, file, vector_store_id): file
                for file in files
            }

            for future in futures:
                file = futures[future]
                try:
                    # We don't care about the return value; just ensure it completed
                    future.result()
                except Exception as e:
                    # Preserve previous behavior: log and continue with other files
                    logger.error(f"Error processing file {file.filename}: {str(e)}")
                    continue

    except Exception as e:
        # If the executor itself fails, log and fall back to a simple error
        logger.error(f"Thread pool failure while uploading resources: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to upload resources")

    return "Resources uploaded successfully"

def clean_text(text: str):
    try:
        response = client.responses.create(
            model=settings.OPENAI_MODEL,
            input=[
                {
                    "role": "system",
                    "content": "You are a helpful assistant that cleans AI-generated messages. Your job is to remove any irrelevant or excessive introductory or concluding text — such as apologies, disclaimers, or requests for confirmation — that do not contribute to the core output.\n\nFocus on keeping only the core meaningful content such as course outcomes, summaries, tables, or actual suggestions.\n\nIf there is any core component or content to be saved, preserve that fully.\n\nIf no meaningful content is found (e.g., just a warning or error message), return it as-is without adding any explanation or comment."
                },
                {"role": "user", "content": text}
            ]
        )

        return response.output_text.strip()
    except Exception as e:
        logger.error(f"Error cleaning text: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

def upload_file_to_vector_store(upload_file: UploadFile, vector_store_id: str) -> str:
    """Upload a single file to OpenAI and connect to vector store"""
    upload_file.file.seek(0)
    content = upload_file.file.read()
    
    if not content:
        raise HTTPException(status_code=400, detail=f"File {upload_file.filename} is empty")
    
    file_obj = io.BytesIO(content)
    file_obj.name = upload_file.filename
    
    openai_file_id = create_file(file_obj)
    connect_file_to_vector_store(vector_store_id, openai_file_id)
    
    return openai_file_id

def course_description(description: str, course_name: str) -> str:
    try:
        # Clean and improve the course description using the Responses API
        response = client.responses.create(
            model=settings.OPENAI_MODEL,
            input=f"""You are a helpful assistant that rewrites rough course descriptions into clear,
realistic, and professional course descriptions written in the style a teacher would use
when describing a course.

Use the course name and provided description as context.
Focus only on what the course covers and what students will learn.
Do not use marketing language, exaggeration, or phrases like "join us" or "your journey".

Only return the improved description as plain text, with no labels or extra commentary.

Course name: {course_name}
Course description: {description}
"""
        )

        if not response.output_text:
            raise ValueError("Empty response from OpenAI")

        return response.output_text.strip()
        
    except Exception as e:
        logger.error(f"Error generating course description: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to generate course description")

    
def evaluate_files_all_in_one(evaluation_id: str, user_id: str, extracted_mark_scheme: dict, extracted_answer_sheets: dict):
    """
    Evaluate a batch of answer sheets using OpenAI API.
    
    This function evaluates the answer sheets it receives without internal batching.
    Batching logic should be handled by the caller (routes layer).
    
    Args:
        evaluation_id: Unique identifier for the evaluation
        user_id: User performing the evaluation
        extracted_mark_scheme: Dict containing mark scheme with 'mark_scheme' key
        extracted_answer_sheets: Dict with "answer_sheets" key containing list of sheets to evaluate
        
    Returns:
        Dict with structure: { "evaluation_id": str, "students": [...] }
    """
    # Get list of answer sheets
    answer_sheets_list = extracted_answer_sheets.get("answer_sheets", [])
    if not answer_sheets_list:
        raise HTTPException(status_code=400, detail="No answer sheets found in extracted data")

    # Store email mapping (file_id -> email) for restoration after evaluation
    email_mapping = {}
    for sheet in answer_sheets_list:
        file_id = sheet.get('file_id')
        email = sheet.get('email')
        if file_id and email:
            email_mapping[file_id] = email

    # Get evaluation
    evaluation = get_evaluation_by_evaluation_id(evaluation_id)
    if not evaluation:
        raise HTTPException(status_code=404, detail=f"Evaluation {evaluation_id} not found")
    # Prepare evaluation payload
    payload = {
        "mark_scheme": json.dumps(extracted_mark_scheme),
        "answer_sheets": json.dumps({"answer_sheets": answer_sheets_list}),
        "evaluation_id": evaluation_id
    }
    
    evaluation_prompt = PromptParser().get_evaluation_prompt(evaluation_id, payload)

    # Create thread and run evaluation
    run = client.responses.create(
        model=settings.OPENAI_MODEL,
        input=[{"role": "user", "content": evaluation_prompt}],
        temperature=0.3,
        text={
            "format": {
                "type": "json_schema",
                "name": "evaluation_schema",
                "strict": True,
                "schema": {
                    "type": "object",
                    "properties": {
                        "evaluation_id": {"type": "string"},
                        "students": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "file_id": {"type": "string"},
                                    "answers": {
                                        "type": "array",
                                        "items": {
                                            "type": "object",
                                            "properties": {
                                                "question_number": {"type": "string"},
                                                "question_text": {"type": "string"},
                                                "student_answer": {"type": ["string", "null"]},
                                                "correct_answer": {"type": ["string", "null"]},
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
                                            ],
                                            "additionalProperties": False
                                        }
                                    },
                                    "total_score": {"type": "number"},
                                    "max_total_score": {"type": "number"}
                                },
                                "required": ["file_id", "answers", "total_score", "max_total_score"],
                                "additionalProperties": False
                            }
                        }
                    },
                    "required": ["evaluation_id", "students"],
                    "additionalProperties": False
                }
            }
        }
    )

    # Poll until run completes
    while run.status in ("queued", "in_progress"):
        time.sleep(1) # Add a small sleep to avoid tight loop
        run = client.responses.retrieve(run.id)

    if run.status == "failed":
        logger.error(f"OpenAI evaluation failed: {run.last_error}")
        raise HTTPException(status_code=500, detail=f"Evaluation failed: {run.last_error}")

    # Extract structured output from response
    structured_output = run.output_text.strip() if run.output_text else None

    if not structured_output:
        raise HTTPException(
            status_code=500,
            detail="No structured output returned from OpenAI evaluation"
        )

    # Parse JSON response
    try:
        evaluation_result = json.loads(structured_output)
        
        # Validate response structure
        if "properties" in evaluation_result and "type" in evaluation_result:
            raise HTTPException(
                status_code=500,
                detail="OpenAI returned schema definition instead of evaluation results. Please try again."
            )
        
        if "evaluation_id" not in evaluation_result:
            evaluation_result["evaluation_id"] = evaluation_id
            
        if "students" not in evaluation_result:
            raise HTTPException(
                status_code=500,
                detail="Invalid evaluation result: missing 'students' field"
            )
            
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse OpenAI JSON response: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Invalid JSON response from OpenAI: {str(e)}"
        )

    # Restore emails to students from mapping
    students = evaluation_result.get("students", [])
    for student in students:
        file_id = student.get('file_id')
        if file_id and file_id in email_mapping:
            student['email'] = email_mapping[file_id]

    return {
        "evaluation_id": evaluation_id,
        "students": students
    }

#use the web search to discover resources for the input typed on the UI
def discover_resources(query):
    system_prompt = """You are a resource discovery assistant specialized in finding high-quality, authoritative, and up-to-date web resources.

Your task:
1. Search the web to find the most relevant and trustworthy resources for the user's query
2. Prioritize sources in this order:
   - Official documentation or official websites
   - Reputable organizations, standards bodies, or well-known platforms
   - High-quality educational resources from established publishers
3. Avoid low-quality blogs, SEO-driven content, forums, or opinion pieces unless no authoritative source exists
4. Only include sources that are currently accessible and actively maintained
5. Always include working, direct URLs

CRITICAL: You must respond with ONLY a valid JSON array. No preamble, no markdown code blocks, no explanation text.

Response format (JSON only):
[
  {
    "title": "Resource title",
    "url": "https://example.com",
    "description": "Brief 1-2 sentence description of what this resource provides and why it's authoritative"
  }
]

Additional guidelines:
- Return 5-10 resources maximum
- Prefer primary sources over summaries or secondary explanations
- Do not repeat the same platform or website excessively unless clearly justified
- Each resource must have all three fields: title, url, and description
- Ensure all URLs are complete and valid (starting with https://)

Focus on accuracy, credibility, and usefulness over quantity."""

    run = client.responses.create(
        model=settings.OPENAI_MODEL,
        input=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": query}
        ],
        tools=[{"type": "web_search"}],
        temperature=0.2
    )

    # Get the output
    output = run.output_text.strip()
    
    # Parse JSON (with error handling)
    try:
        # Remove markdown code blocks if present
        if output.startswith("```json"):
            output = output.replace("```json", "").replace("```", "").strip()
        elif output.startswith("```"):
            output = output.replace("```", "").strip()
        
        resources_json = json.loads(output)
        return resources_json
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse JSON response: {output}")
        # Fallback: return empty list or raise exception
        raise ValueError(f"Invalid JSON response from API: {str(e)}")