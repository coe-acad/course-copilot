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

def create_evaluation_assistant_and_vector_store(evaluation_id: str):
    try:
        # Create vector store first
        vector_store = client.vector_stores.create(name=f"Evaluation_{evaluation_id}_files")
        logger.info(f"Created vector store {vector_store.id}")
        
        # Create assistant with vector store linked
        assistant = client.beta.assistants.create(
            name="Evaluation Assistant",
            instructions="""You are an expert document extraction assistant specialized in educational assessments.

Your task is to extract COMPLETE and ACCURATE information from mark schemes and answer sheets.

CRITICAL INSTRUCTIONS:
1. Extract EVERY SINGLE question from documents - never skip any questions
2. When extracting mark schemes, ensure you capture ALL questions, answers, and marking criteria
3. When extracting answer sheets, ensure you capture ALL student responses
4. Always number questions sequentially (1, 2, 3, etc.)
5. If you see questions numbered differently (like 1a, 1b, 2a), treat each as a separate question
6. For missing or blank answers, use null (not empty string)
7. Double-check your work before responding
8. Always respond with valid JSON only
9. If a document is long, take your time to process every section completely

Quality over speed - it's better to take longer and extract everything correctly than to miss questions.""",

            model=settings.OPENAI_MODEL,
            tools=[{"type": "file_search"}],
            tool_resources={
                "file_search": {
                    "vector_store_ids": [vector_store.id],
                }
            }
        )
        logger.info(f"Created Evaluation Assistant {assistant.id}")
        
        return assistant.id, vector_store.id
    except Exception as e:
        logger.error(f"Error creating Evaluation Assistant: {str(e)}")
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

def upload_mark_scheme_file(mark_scheme: UploadFile, vector_store_id: str) -> str:
    """Upload mark scheme file"""
    return upload_file_to_vector_store(mark_scheme, vector_store_id)

def upload_answer_sheet_files(answer_sheets: List[UploadFile], vector_store_id: str) -> List[str]:
    """Upload multiple answer sheet files"""
    answer_sheet_ids = []
    
    for answer_sheet in answer_sheets:
        try:
            file_id = upload_file_to_vector_store(answer_sheet, vector_store_id)
            answer_sheet_ids.append(file_id)
        except Exception as e:
            logger.error(f"Failed to upload {answer_sheet.filename}: {str(e)}")
            continue
    
    if not answer_sheet_ids:
        raise HTTPException(status_code=400, detail="No answer sheet files were uploaded successfully")
    
    return answer_sheet_ids

def extract_mark_scheme(evaluation_id: str, user_id: str, mark_scheme_file_id: str) -> dict:
    evaluation = get_evaluation_by_evaluation_id(evaluation_id)
    if not evaluation:
        raise HTTPException(status_code=404, detail=f"Evaluation {evaluation_id} not found")
    if not mark_scheme_file_id:
        raise HTTPException(status_code=400, detail="mark_scheme_file_id is required for extraction")
    assistant_id = evaluation["evaluation_assistant_id"]
    vector_store_id = evaluation["vector_store_id"]
    logger.info(f"Using assistant {assistant_id} for mark scheme extraction")
    
    # Quick check that vector store is ready
    vector_store = client.vector_stores.retrieve(vector_store_id)
    if vector_store.status != "completed":
        logger.warning(f"Vector store not ready: {vector_store.status}")
        time.sleep(5)  # Brief wait
    
    # Create thread with file
    thread = client.beta.threads.create(
        messages=[{
            "role": "user",
            "content": "Extract questions, answers, and marking scheme. Return JSON format: {\"mark_scheme\": [{\"question_number\": \"1\", \"question_text\": \"...\", \"correct_answer\": \"...\", \"mark_scheme\": \"...\"}]}",
            "attachments": [{"file_id": mark_scheme_file_id, "tools": [{"type": "file_search"}]}]
        }]
    )

    # Run with structured output
    run = client.beta.threads.runs.create(
        thread_id=thread.id,
        assistant_id=assistant_id,
        response_format={
            "type": "json_schema",
            "json_schema": {
                "name": "mark_scheme",
                "schema": {
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
                                }
                            }
                        }
                    }
                }
            }
        }
    )

    # Wait and get result
    while run.status in ["queued", "in_progress"]:
        run = client.beta.threads.runs.retrieve(thread_id=thread.id, run_id=run.id)
    
    logger.info(f"Run completed with status: {run.status}")
    if run.status == "failed":
        logger.error(f"Run failed: {run.last_error}")
        raise HTTPException(status_code=500, detail=f"Run failed: {run.last_error}")

    messages = client.beta.threads.messages.list(thread_id=thread.id)
    for msg in messages.data:
        if msg.role == "assistant":
            content = msg.content[0].text.value
            return json.loads(content)
    
    raise HTTPException(status_code=500, detail="No assistant response found")

def extract_answer_sheets_batched(evaluation_id: str, user_id: str, answer_sheet_file_ids: list[str]) -> dict:
    """
    Multi-file extraction with batching (up to 10 attachments per run) to respect API limits.
    Returns: { "answer_sheets": [ { file_id, student_name, answers: [...] }, ... ] }
    """
    evaluation = get_evaluation_by_evaluation_id(evaluation_id)
    if not evaluation:
        raise HTTPException(status_code=404, detail=f"Evaluation {evaluation_id} not found")
    
    assistant_id = evaluation.get("evaluation_assistant_id")
    vector_store_id = evaluation.get("vector_store_id")
    
    if not assistant_id:
        raise HTTPException(status_code=400, detail="Evaluation assistant not found")
    if not vector_store_id:
        raise HTTPException(status_code=400, detail="Vector store not found")

    if not answer_sheet_file_ids:
        raise HTTPException(status_code=400, detail="answer_sheet_file_ids must be a non-empty list")

    # Coerce to list and deduplicate while preserving order
    if isinstance(answer_sheet_file_ids, str):
        answer_sheet_file_ids = [answer_sheet_file_ids]
    
    # Validate file IDs
    seen = set()
    unique_ids: list[str] = []
    for fid in answer_sheet_file_ids:
        if not fid or not isinstance(fid, str) or len(fid.strip()) == 0:
            logger.warning(f"Invalid file_id encountered: {repr(fid)}; skipping")
            continue
        if fid not in seen:
            seen.add(fid)
            unique_ids.append(fid)

    if not unique_ids:
        raise HTTPException(status_code=400, detail="No valid answer sheet file_ids provided")

    logger.info(f"Processing {len(unique_ids)} unique answer sheet files")

        # Ensure vector store is ready with retry
    max_vector_store_retries = 3
    for vs_attempt in range(max_vector_store_retries):
        vector_store = client.vector_stores.retrieve(vector_store_id)
        if vector_store.status == "completed":
            break
        elif vector_store.status == "failed":
            raise HTTPException(status_code=500, detail=f"Vector store failed: {vector_store.status}")
        else:
            logger.warning(f"Vector store not ready (attempt {vs_attempt + 1}/{max_vector_store_retries}): {vector_store.status}")
            if vs_attempt < max_vector_store_retries - 1:
                time.sleep(5 * (vs_attempt + 1))  # Progressive wait: 5s, 10s, 15s
    else:
        raise HTTPException(status_code=500, detail=f"Vector store not ready after {max_vector_store_retries} attempts")
    
    # Extract each file individually using ThreadPoolExecutor with retry
    results = []
    failed_files = []
    
    try:
        with ThreadPoolExecutor(max_workers=3) as executor:
            # Submit all extraction tasks
            future_to_file_id = {
                executor.submit(extract_single_answer_sheet, evaluation_id, user_id, assistant_id, vector_store_id, file_id): file_id
                for file_id in unique_ids
            }
            
            # Collect results as they complete
            for future in future_to_file_id:
                try:
                    result = future.result(timeout=300)  # 5 minute timeout per file
                    results.append(result)
                    logger.info(f"Successfully extracted file {future_to_file_id[future]}")
                except Exception as e:
                    file_id = future_to_file_id[future]
                    failed_files.append(file_id)
                    logger.error(f"Failed to extract file {file_id}: {str(e)}")
                    # Continue with other files instead of failing completely
                    continue
    except Exception as e:
        logger.error(f"ThreadPoolExecutor failed: {str(e)}")
        # Fallback to sequential processing
        logger.info("Falling back to sequential processing...")
        for file_id in unique_ids:
            try:
                result = extract_single_answer_sheet(evaluation_id, user_id, assistant_id, vector_store_id, file_id)
                results.append(result)
                logger.info(f"Sequential extraction successful for file {file_id}")
            except Exception as seq_e:
                failed_files.append(file_id)
                logger.error(f"Sequential extraction failed for file {file_id}: {str(seq_e)}")
                continue
    
    # Retry failed files once more
    if failed_files:
        logger.info(f"Retrying {len(failed_files)} failed files: {failed_files}")
        retry_success = 0
        for file_id in failed_files:
            try:
                result = extract_single_answer_sheet(evaluation_id, user_id, assistant_id, vector_store_id, file_id)
                results.append(result)
                retry_success += 1
                logger.info(f"Retry successful for file {file_id}")
            except Exception as e:
                logger.error(f"Retry failed for file {file_id}: {str(e)}")
                continue
        logger.info(f"Retry summary: {retry_success}/{len(failed_files)} files recovered")
        
        # Final check - if we still have no results, provide detailed error
        if not results:
            error_details = f"All {len(unique_ids)} files failed extraction. Failed files: {failed_files}"
            logger.error(error_details)
            raise HTTPException(status_code=500, detail=error_details)
    
    if not results:
        raise HTTPException(status_code=500, detail="No answer sheets were successfully extracted")
    
    success_rate = (len(results) / len(unique_ids)) * 100
    logger.info(f"Extraction completed: {len(results)}/{len(unique_ids)} files successful ({success_rate:.1f}%)")
    return {"answer_sheets": results}

def extract_single_answer_sheet(evaluation_id: str, user_id: str, assistant_id: str, vector_store_id: str, file_id: str) -> dict:
    """Extract a single answer sheet file with retry logic"""
    max_retries = 3
    for attempt in range(max_retries):
        try:
            # Create individual thread for this file
            thread = client.beta.threads.create(
                messages=[{
                    "role": "user",
                    "content": f"""Extract ALL questions and answers from this answer sheet file. 

CRITICAL REQUIREMENTS:
1. Extract EVERY question from the file - do not skip any questions
2. Include the complete question text for each question
3. For missing/blank/'N/A' answers, set 'student_answer' to null
4. Return the exact format specified

Return JSON format: {{"file_id": "{file_id}", "student_name": "...", "answers": [{{"question_number": "1", "question_text": "...", "student_answer": "..."}}]}}""",
                    "attachments": [{"file_id": file_id, "tools": [{"type": "file_search"}]}]
                }]
            )

            run = client.beta.threads.runs.create(
                thread_id=thread.id,
                assistant_id=assistant_id,
                response_format={
                    "type": "json_schema",
                    "json_schema": {
                        "name": "single_answer_sheet_schema",
                        "schema": {
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
                                            "student_answer": {"type": ["string", "null"]}
                                        },
                                        "required": ["question_number", "question_text", "student_answer"]
                                    }
                                }
                            },
                            "required": ["file_id", "student_name", "answers"]
                        }
                    }
                }
            )

            # Wait for completion with timeout
            max_wait_time = 300  # 5 minutes
            start_time = time.time()
            
            while run.status in ["queued", "in_progress"]:
                if time.time() - start_time > max_wait_time:
                    raise HTTPException(status_code=408, detail=f"Extraction timeout for file {file_id}")
                time.sleep(1)
                run = client.beta.threads.runs.retrieve(thread_id=thread.id, run_id=run.id)

            if run.status == "failed":
                error_detail = run.last_error or "Unknown error"
                raise HTTPException(status_code=500, detail=f"Extraction failed for file {file_id}: {error_detail}")

            # Get response
            messages = client.beta.threads.messages.list(thread_id=thread.id)
            for msg in messages.data:
                if msg.role == "assistant":
                    try:
                        result = json.loads(msg.content[0].text.value)
                        # Validate the extraction
                        if not result.get("file_id") or not result.get("answers"):
                            raise HTTPException(status_code=500, detail=f"Invalid extraction result for file {file_id}: missing required fields")
                        if not isinstance(result.get("answers"), list):
                            raise HTTPException(status_code=500, detail=f"Invalid extraction result for file {file_id}: answers must be a list")
                        return result
                    except json.JSONDecodeError as json_e:
                        raise HTTPException(status_code=500, detail=f"Invalid JSON response for file {file_id}: {str(json_e)}")

            raise HTTPException(status_code=500, detail=f"No assistant response found for file {file_id}")

        except Exception as e:
            error_type = type(e).__name__
            error_msg = str(e)
            
            # Handle specific OpenAI errors
            if "rate_limit" in error_msg.lower() or "quota" in error_msg.lower():
                wait_time = 10 * (attempt + 1)  # Longer wait for rate limits
                logger.warning(f"Rate limit hit for file {file_id}, waiting {wait_time}s before retry {attempt + 1}/{max_retries}")
                time.sleep(wait_time)
            elif "timeout" in error_msg.lower():
                logger.warning(f"Timeout for file {file_id}, attempt {attempt + 1}/{max_retries}")
                time.sleep(2 ** attempt)  # Exponential backoff
            else:
                logger.warning(f"Attempt {attempt + 1}/{max_retries} failed for file {file_id}: {error_type}: {error_msg}")
                if attempt < max_retries - 1:  # Not the last attempt
                    time.sleep(2 ** attempt)  # Exponential backoff
            
            if attempt == max_retries - 1:  # Last attempt
                logger.error(f"All {max_retries} attempts failed for file {file_id}. Final error: {error_type}: {error_msg}")
                raise e

    # This should never be reached, but just in case
    raise HTTPException(status_code=500, detail=f"Unexpected error in extraction for file {file_id}")


def evaluate_files_all_in_one(evaluation_id: str, user_id: str, extracted_mark_scheme: dict, extracted_answer_sheets: dict) -> dict:
    """
    Evaluate all students in one go using Chat Completions.
    Uses the already extracted mark scheme and answer sheets JSON to compute scores.
    Returns: { evaluation_id, extracted_file_ids, students: [...] }
    """
    # Build prompt payload
    payload = {
        "mark_scheme": json.dumps(extracted_mark_scheme, indent=2),
        "answer_sheets": json.dumps(extracted_answer_sheets, indent=2),
        "evaluation_id": evaluation_id
    }

    evaluation_prompt = PromptParser().get_evaluation_prompt(evaluation_id, payload)
    print(evaluation_prompt)

    # Schema: covers all files, grouped in students with file_id attribution
    evaluation_schema = {
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
                                ]
                            }
                        },
                        "total_score": {"type": "number"},
                        "max_total_score": {"type": "number"}
                    },
                    "required": ["file_id", "answers", "total_score", "max_total_score"]
                }
            }
        },
        "required": ["evaluation_id", "students"]
    }

    # Use Assistants API for evaluation again
    evaluation = get_evaluation_by_evaluation_id(evaluation_id)
    evaluation_assistant_id = evaluation["evaluation_assistant_id"]

    thread = client.beta.threads.create(
        messages=[{"role": "user", "content": evaluation_prompt}]
    )

    run = client.beta.threads.runs.create(
        thread_id=thread.id,
        assistant_id=evaluation_assistant_id,
        response_format={
            "type": "json_schema",
            "json_schema": {"name": "evaluation_schema", "schema": evaluation_schema}
        }
    )

    while run.status in ["queued", "in_progress"]:
        run = client.beta.threads.runs.retrieve(thread_id=thread.id, run_id=run.id)

    if run.status == "failed":
        logger.error(f"All-in-one evaluation {evaluation_id} failed: {run.last_error}")
        raise HTTPException(status_code=500, detail=f"All-in-one evaluation failed: {run.last_error}")

    messages = client.beta.threads.messages.list(thread_id=thread.id)
    assistant_message = None
    for m in messages.data:
        if m.role != "assistant":
            continue
        # Ensure content is present and has text
        if getattr(m, "content", None) and len(m.content) > 0:
            first = m.content[0]
            if getattr(first, "text", None) and getattr(first.text, "value", None):
                assistant_message = m
                break
    if not assistant_message:
        raise HTTPException(status_code=500, detail="Assistant returned no text content for evaluation")

    structured_output = assistant_message.content[0].text.value

    # Parse result and enforce minimal invariants
    try:
        evaluation_result = json.loads(structured_output)
        if "properties" in evaluation_result and "type" in evaluation_result:
            raise HTTPException(status_code=500, detail="OpenAI returned schema definition instead of evaluation results")
        if "evaluation_id" not in evaluation_result:
            evaluation_result["evaluation_id"] = evaluation_id
        if "students" not in evaluation_result:
            raise HTTPException(status_code=500, detail="Invalid evaluation result structure: missing 'students'")
        return evaluation_result
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse evaluation JSON for {evaluation_id}: {structured_output}")
        raise HTTPException(status_code=500, detail=f"Invalid JSON response from OpenAI: {str(e)}")

def mark_scheme_check(evaluation_assistant_id: str, user_id: str, mark_scheme_file_id: str) -> dict:
    thread = client.beta.threads.create(
        messages=[{"role": "user", "content": "Check if the mark scheme follows the correct format where each question has a Question, an Answer/Correct Answer (wording may vary), and a Marking Scheme/Mark Scheme (wording may vary); if correct return only 'The format is correct, you can move forward', if not return only 'Mark scheme is not in the correct format'."}]
    )
    run = client.beta.threads.runs.create(
        thread_id=thread.id,
        assistant_id=evaluation_assistant_id
    )

    while run.status in ["queued", "in_progress"]:
        run = client.beta.threads.runs.retrieve(thread_id=thread.id, run_id=run.id)

    if run.status == "failed":
        logger.error(f"Mark scheme check failed: {run.last_error}")
        raise HTTPException(status_code=500, detail=f"Mark scheme check failed: {run.last_error}")

    messages = client.beta.threads.messages.list(thread_id=thread.id)
    assistant_message = None
    for m in messages.data:
        if m.role != "assistant":
            continue
        # Ensure content is present and has text
        if getattr(m, "content", None) and len(m.content) > 0:
            first = m.content[0]
            if getattr(first, "text", None) and getattr(first.text, "value", None):
                assistant_message = m
                break
    if not assistant_message:
        raise HTTPException(status_code=500, detail="Assistant returned no text content for evaluation")
    return assistant_message.content[0].text.value

