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
        prompt = PromptParser().render_prompt("app/prompts/system/evaluation-assistant.json", {})
        logger.info(f"Prompt: {prompt}")
        # Create assistant without default vector store access (files will be attached at thread level)
        assistant = client.beta.assistants.create(
            name="Evaluation Assistant",
            instructions=prompt,
            model=settings.OPENAI_MODEL,
            tools=[{"type": "file_search"}]
            # Note: No tool_resources here - vector stores will be attached at thread level
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

def upload_answer_sheet_files(answer_sheets: List[UploadFile]) -> tuple[List[str], List[str]]:
    """Upload multiple answer sheet files and return both file IDs and filenames"""
    answer_sheet_ids = []
    answer_sheet_filenames = []
    
    for answer_sheet in answer_sheets:
        try:
            file_content = answer_sheet.file.read()
            file_obj = io.BytesIO(file_content)
            file_obj.name = answer_sheet.filename

            file_id = create_file(file_obj)
            answer_sheet_ids.append(file_id)
            answer_sheet_filenames.append(answer_sheet.filename)
        except Exception as e:
            logger.error(f"Failed to upload {answer_sheet.filename}: {str(e)}")
            continue
    
    if not answer_sheet_ids:
        raise HTTPException(status_code=400, detail="No answer sheet files were uploaded successfully")
    
    return answer_sheet_ids, answer_sheet_filenames

def validate_file_ids(file_ids: list) -> list:
    """Validate file_ids by checking if they exist in OpenAI."""
    valid_file_ids = []
    
    for file_id in file_ids:
        try:
            # Try to retrieve the file to check if it exists
            file_info = client.files.retrieve(file_id)
            if file_info.purpose == "vision" and file_info.status == "processed":
                valid_file_ids.append(file_id)
                logger.debug(f"✅ File {file_id} is valid and processed")
            else:
                logger.warning(f"⚠️ File {file_id} exists but status={file_info.status}, purpose={file_info.purpose}")
        except Exception as e:
            logger.error(f"❌ File {file_id} is invalid or inaccessible: {str(e)}")
    
    logger.info(f"📋 Validated {len(valid_file_ids)}/{len(file_ids)} file_ids")
    return valid_file_ids


def extract_file_ids_from_answer_sheets(answer_sheets: list) -> list:
    """Extract all file_ids from answer sheets for image attachments."""
    file_ids = []
    
    logger.info(f"Extracting file_ids from {len(answer_sheets)} answer sheets")
    
    for sheet_idx, sheet in enumerate(answer_sheets):
        sheet_file_id = sheet.get("file_id", f"sheet_{sheet_idx}")
        answers = sheet.get("answers", [])
        logger.debug(f"Sheet {sheet_file_id}: Processing {len(answers)} answers")
        
        for answer_idx, answer in enumerate(answers):
            if isinstance(answer, dict) and answer.get("answer"):
                answer_content = answer["answer"]
                question = answer.get("question", "Unknown question")[:50]
                logger.debug(f"Sheet {sheet_file_id}, Answer {answer_idx + 1}: {question}... - Content type: {type(answer_content)}")
                
                if isinstance(answer_content, list):
                    logger.debug(f"Sheet {sheet_file_id}, Answer {answer_idx + 1}: Found {len(answer_content)} content items")
                    for content_idx, content_item in enumerate(answer_content):
                        if isinstance(content_item, dict):
                            content_type = content_item.get("type")
                            logger.debug(f"Sheet {sheet_file_id}, Answer {answer_idx + 1}, Item {content_idx + 1}: Type = {content_type}")
                            
                            if (content_type == "image" and content_item.get("file_id")):
                                file_id = content_item["file_id"]
                                file_ids.append(file_id)
                                logger.info(f"✅ Found image file_id: {file_id} in Sheet {sheet_file_id}, Answer {answer_idx + 1}")
                            elif content_type == "image" and content_item.get("image_data"):
                                logger.warning(f"⚠️ Found image with base64 data (fallback) in Sheet {sheet_file_id}, Answer {answer_idx + 1}")
                        else:
                            logger.debug(f"Sheet {sheet_file_id}, Answer {answer_idx + 1}, Item {content_idx + 1}: Not a dict - {type(content_item)}")
                else:
                    logger.debug(f"Sheet {sheet_file_id}, Answer {answer_idx + 1}: Answer content is not a list - {type(answer_content)}")
            else:
                logger.debug(f"Sheet {sheet_file_id}, Answer {answer_idx + 1}: No answer content found")
    
    # Remove duplicates while preserving order
    unique_file_ids = list(dict.fromkeys(file_ids))
    logger.info(f"📊 SUMMARY: Found {len(file_ids)} total file_ids, {len(unique_file_ids)} unique file_ids")
    
    if unique_file_ids:
        logger.info(f"🖼️ Raw image file_ids: {unique_file_ids}")
        # Validate file_ids before returning
        validated_file_ids = validate_file_ids(unique_file_ids)
        logger.info(f"🔍 Validated image file_ids for evaluation: {validated_file_ids}")
        return validated_file_ids
    else:
        logger.warning("❌ No image file_ids found in any answer sheets!")
        return []


def evaluate_files_all_in_one(evaluation_id: str, user_id: str, extracted_mark_scheme: dict, extracted_answer_sheets: dict):
    """
    Evaluate answer sheets sequentially in batches of 5 using Chat Completions.
    Uses the already extracted mark scheme and answer sheets JSON to compute scores.
    Returns: { evaluation_id, students: [...] }
    """
    # Get list of answer sheets
    answer_sheets_list = extracted_answer_sheets.get("answer_sheets", [])
    if not answer_sheets_list:
        raise HTTPException(status_code=400, detail="No answer sheets found in extracted data")

    # Store email mapping before evaluation (file_id -> email)
    email_mapping = {}
    for sheet in answer_sheets_list:
        file_id = sheet.get('file_id')
        email = sheet.get('email')
        if file_id and email:
            email_mapping[file_id] = email
            logger.info(f"Stored email mapping: {file_id} -> {email}")

    # Ensure unique answer sheets
    unique_answer_sheets = {sheet.get('file_id'): sheet for sheet in answer_sheets_list}.values()
    answer_sheets_list = list(unique_answer_sheets)

    # Split into batches of 5
    batch_size = 5
    batches = [answer_sheets_list[i:i + batch_size] for i in range(0, len(answer_sheets_list), batch_size)]
    all_evaluated_students = []

    logger.info(f"Processing {len(answer_sheets_list)} unique answer sheets in {len(batches)} batches")

    # Get evaluation assistant
    evaluation = get_evaluation_by_evaluation_id(evaluation_id)
    evaluation_assistant_id = evaluation["evaluation_assistant_id"]

    def evaluate_one_batch(batch_num: int, batch: list) -> list:
        """Inner function to evaluate a single batch and return students list."""
        logger.info(f"Evaluating batch {batch_num}/{len(batches)} with {len(batch)} answer sheets")

        batch_payload = {
            "mark_scheme": json.dumps(extracted_mark_scheme),
            "answer_sheets": json.dumps({"answer_sheets": batch}),
            "evaluation_id": evaluation_id
        }
        logger.info(f"📋 Batch payload created for {len(batch)} answer sheets")
        
        # Log answer sheet structure for debugging
        for idx, sheet in enumerate(batch):
            sheet_id = sheet.get("file_id", f"sheet_{idx}")
            answers = sheet.get("answers", [])
            image_count = 0
            text_count = 0
            
            for answer in answers:
                if isinstance(answer, dict) and answer.get("answer"):
                    answer_content = answer["answer"]
                    if isinstance(answer_content, list):
                        for item in answer_content:
                            if isinstance(item, dict):
                                if item.get("type") == "image":
                                    image_count += 1
                                elif item.get("type") == "text":
                                    text_count += 1
            
            logger.info(f"📊 Sheet {sheet_id}: {len(answers)} answers ({image_count} images, {text_count} text)")
        
        evaluation_prompt = PromptParser().get_evaluation_prompt(evaluation_id, batch_payload)
        logger.info(f"📝 Generated evaluation prompt ({len(evaluation_prompt)} characters)")

        # Extract file_ids from answer sheets for image attachments
        file_ids = extract_file_ids_from_answer_sheets(batch)
        
        # Create message with or without image files
        if file_ids:
            logger.info(f"🖼️ Creating evaluation message with {len(file_ids)} image files: {file_ids}")
            message_content = [
                {"type": "text", "text": evaluation_prompt}
            ]
            # Add each image file to the message content
            for idx, file_id in enumerate(file_ids):
                logger.debug(f"Adding image {idx + 1}/{len(file_ids)}: {file_id}")
                message_content.append({
                    "type": "image_file", 
                    "image_file": {"file_id": file_id}
                })
            
            logger.info(f"📝 Message content has {len(message_content)} items (1 text + {len(file_ids)} images)")
            
            # Log the exact message structure being sent
            logger.debug(f"📋 Message structure preview:")
            logger.debug(f"  - Text content: {message_content[0]['text'][:200]}...")
            for i, img_content in enumerate(message_content[1:], 1):
                logger.debug(f"  - Image {i}: file_id = {img_content['image_file']['file_id']}")
            
            try:
                thread = client.beta.threads.create(messages=[{
                    "role": "user", 
                    "content": message_content
                }])
                logger.info("✅ Thread created successfully with images")
            except Exception as thread_error:
                logger.error(f"❌ Failed to create thread with images: {thread_error}")
                logger.warning("🔄 Falling back to text-only evaluation")
                # Fallback to text-only evaluation
                thread = client.beta.threads.create(messages=[{"role": "user", "content": evaluation_prompt}])
                logger.info("✅ Fallback thread created successfully (text-only)")
        else:
            logger.info("📝 Creating evaluation message without image files")
            thread = client.beta.threads.create(messages=[{"role": "user", "content": evaluation_prompt}])
            logger.info("✅ Thread created successfully without images")
        # Configure run with vision capabilities if images are present
        run_config = {
            "thread_id": thread.id,
            "temperature": 0.3,
            "assistant_id": evaluation_assistant_id,
            "response_format": {
                "type": "json_schema",
                "json_schema": {
                    "name": "evaluation_schema",
                    "schema": {
                        "type": "object",
                        "properties": {
                            "evaluation_id": {"type": "string"},
                            "email": {"type": "string"},
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
                }
            }
        }
        
        # Log run configuration
        if file_ids:
            logger.info(f"🚀 Creating run with VISION SUPPORT for {len(file_ids)} images")
        else:
            logger.info("🚀 Creating run for TEXT-ONLY evaluation")
        
        run = client.beta.threads.runs.create(**run_config)

        # Poll until run finishes
        while run.status in ("queued", "in_progress"):
            run = client.beta.threads.runs.retrieve(thread_id=thread.id, run_id=run.id)

        if run.status == "failed":
            logger.error(f"Batch {batch_num} evaluation failed: {run.last_error}")
            raise HTTPException(status_code=500, detail=f"Batch {batch_num} evaluation failed: {run.last_error}")

        # Get assistant message content with robust structured output handling
        structured_output = None

        # Prefer structured output from run if available
        if hasattr(run, "output") and run.output and hasattr(run.output, "data"):
            try:
                structured_output = run.output.data[0].content[0].text.value
            except Exception:
                pass

        # Fallback to message parsing if run.output missing
        if not structured_output:
            messages = client.beta.threads.messages.list(thread_id=thread.id)
            logger.info(f"📨 Retrieved {len(messages.data)} messages from thread for batch {batch_num}")
            
            for msg in messages.data:
                if msg.role == "assistant" and msg.content:
                    for content in msg.content:
                        if hasattr(content, "text") and content.text.value:
                            structured_output = content.text.value
                            logger.info(f"📄 AI Response length: {len(structured_output)} characters")
                            break
                if structured_output:
                    break

        if not structured_output:
            logger.error(f"❌ No structured content returned for batch {batch_num}")
            raise HTTPException(status_code=500, detail=f"No structured content returned for batch {batch_num}")
        
        # Check for problematic responses
        if "No text answer provided, image not evaluated" in structured_output:
            logger.error(f"❌ Batch {batch_num}: AI returned 'No text answer provided, image not evaluated' - IMAGE PROCESSING FAILED!")
            logger.error(f"🔍 Response preview: {structured_output[:500]}...")
        elif file_ids and len(file_ids) > 0:
            logger.info(f"✅ Batch {batch_num}: AI processed evaluation with {len(file_ids)} images successfully")

        # Parse and enforce minimal invariants
        try:
            evaluation_result = json.loads(structured_output)
            if "properties" in evaluation_result and "type" in evaluation_result:
                raise HTTPException(status_code=500, detail="OpenAI returned schema definition instead of evaluation results, please try again")
            if "evaluation_id" not in evaluation_result:
                evaluation_result["evaluation_id"] = evaluation_id
            if "students" not in evaluation_result:
                raise HTTPException(status_code=500, detail="Invalid evaluation result structure: missing 'students'")
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse evaluation JSON for {evaluation_id}: {structured_output}")
            raise HTTPException(status_code=500, detail=f"Invalid JSON response from OpenAI: {str(e)}")

        logger.info(f"Successfully evaluated batch {batch_num} with {len(evaluation_result['students'])} students")

        # Enrich results with original answer parts (to surface images in UI)
        try:
            file_id_to_parts = {}
            for sheet in batch:
                fid = sheet.get("file_id")
                parts_per_answer = []
                for ans in sheet.get("answers", []) or []:
                    parts_per_answer.append(ans.get("answer", []))
                if fid:
                    file_id_to_parts[fid] = parts_per_answer

            for student in evaluation_result.get("students", []):
                fid = student.get("file_id")
                source_parts = file_id_to_parts.get(fid, [])
                for idx, ans in enumerate(student.get("answers", []) or []):
                    if idx < len(source_parts):
                        ans["original_answer_parts"] = source_parts[idx]
                        # Convenience flag for UI to show an image badge
                        try:
                            has_image = any(
                                isinstance(p, dict) and p.get("type") == "image"
                                for p in (source_parts[idx] or [])
                            )
                            if has_image:
                                ans["has_image"] = True
                        except Exception:
                            pass
        except Exception as enrich_err:
            logger.warning(f"Could not enrich results with original answer parts: {enrich_err}")

        return evaluation_result["students"]

    # Evaluate all batches sequentially
    for idx, batch in enumerate(batches):
        batch_num = idx + 1
        try:
            batch_students = evaluate_one_batch(batch_num, batch)
            all_evaluated_students.extend(batch_students)
        except Exception as e:
            logger.error(f"Batch {batch_num} failed: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Failed to process batch {batch_num}: {str(e)}")

    # Deduplicate by file_id and add email back to each student
    seen_file_ids = set()
    unique_students = []
    for student in all_evaluated_students:
        file_id = student.get('file_id')
        if file_id and file_id not in seen_file_ids:
            seen_file_ids.add(file_id)
            # Add email back to student from mapping
            if file_id in email_mapping:
                student['email'] = email_mapping[file_id]
                logger.info(f"Added email to student {file_id}: {email_mapping[file_id]}")
            unique_students.append(student)

    final_result = {"evaluation_id": evaluation_id, "students": unique_students}
    logger.info(f"Completed evaluation of {len(unique_students)}/{len(answer_sheets_list)} answer sheets "
                f"(removed {len(all_evaluated_students) - len(unique_students)} duplicates)")
    return final_result

def mark_scheme_check(evaluation_assistant_id: str, user_id: str, mark_scheme_file_id: str) -> dict:
    thread = client.beta.threads.create(
        messages=[{"role": "user", "content": "Check if the mark scheme follows the correct format where each question has a Question, an Answer/Correct Answer/Answer Template (wording may vary), and a Marking Scheme/Mark Scheme (wording may vary); There might and might not have notes and deductions, either is excepted; if correct return only 'The format is correct, you can move forward', if not return only 'Mark scheme is not in the correct format'."}]
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

def course_description(description: str, course_name: str):
    #take the description and clean and improve it using chat completion
    chat_completion = client.chat.completions.create(
        model=settings.OPENAI_MODEL,
        messages=[
            {"role": "system", "content": "You are a helpful assistant that rewrites rough course descriptions into clear, realistic, and professional course descriptions written in the style a teacher would use when describing a course. Use the course name and provided description as context. The description should focus only on what the course covers and what students will learn, without marketing language, exaggeration, or phrases like 'join us' or 'your journey'. Only return the improved description as plain text, with no labels or extra commentary."},
            {"role": "user", "content": f"Course name: {course_name}\nCourse description: {description}"}
        ]
    )
    description = chat_completion.choices[0].message.content
    return description
