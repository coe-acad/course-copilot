import io
import logging
from typing import List
from fastapi import UploadFile, HTTPException
from ..utils.prompt_parser import PromptParser
from ..utils.openai_client import client
from ..config.settings import settings
import json
from app.services.mongo import create_evaluation, get_evaluation_by_evaluation_id

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
            instructions="You extract data from files and return JSON. Always respond with valid JSON only.",
            model=settings.OPENAI_MODEL,
            tools=[{"type": "file_search"}],
            tool_resources={
                "file_search": {
                    "vector_store_ids": [vector_store.id]
                }
            }
        )
        logger.info(f"Created Evaluation Assistant {assistant.id}")
        
        return assistant.id, vector_store.id
    except Exception as e:
        logger.error(f"Error creating Evaluation Assistant: {str(e)}")
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

def extract_mark_scheme(evaluation_id: str, user_id: str, mark_scheme_file_id: str) -> dict:
    evaluation = get_evaluation_by_evaluation_id(evaluation_id)
    assistant_id = evaluation["evaluation_assistant_id"]
    vector_store_id = evaluation["vector_store_id"]
    logger.info(f"Using assistant {assistant_id} for mark scheme extraction")
    
    # Quick check that vector store is ready
    vector_store = client.vector_stores.retrieve(vector_store_id)
    if vector_store.status != "completed":
        logger.warning(f"Vector store not ready: {vector_store.status}")
        import time
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
    logger.info(f"Got {len(messages.data)} messages")
    
    for msg in messages.data:
        logger.info(f"Message role: {msg.role}")
        if msg.role == "assistant":
            content = msg.content[0].text.value
            logger.info(f"Assistant response: {content[:200]}...")
            return json.loads(content)
    
    raise HTTPException(status_code=500, detail="No assistant response found")



def extract_single_answer_sheet(evaluation_id: str, user_id: str, answer_sheet_file_id: str) -> dict:
    """
    Extract evaluation content from a single answer sheet using OpenAI structured outputs.
    
    Returns structured JSON for a single student.
    """
    evaluation = get_evaluation_by_evaluation_id(evaluation_id)
    assistant_id = evaluation["evaluation_assistant_id"]
    vector_store_id = evaluation["vector_store_id"]
    
    # Quick check that vector store is ready
    vector_store = client.vector_stores.retrieve(vector_store_id)
    if vector_store.status != "completed":
        logger.warning(f"Vector store not ready: {vector_store.status}")
        import time
        time.sleep(5)  # Brief wait
    
    extraction_schema = {
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

    # Create thread with single file attachment
    thread = client.beta.threads.create(
        messages=[
            {
                "role": "user",
                "content": f"Extract ALL questions and answers from this answer sheet file; include student name if available; for every question always include question text, preserving numbering/order; if the answer is missing, blank, or 'N/A', set 'student_answer' to null; capture answers exactly as written; include the file_id '{answer_sheet_file_id}' in the response; return ONLY valid JSON.",
                "attachments": [
                    {"file_id": answer_sheet_file_id, "tools": [{"type": "file_search"}]}
                ]
            }
        ]
    )

    # Run assistant with structured output
    run = client.beta.threads.runs.create(
        thread_id=thread.id,
        assistant_id=assistant_id,
        response_format={
            "type": "json_schema",
            "json_schema": {"name": "single_answer_sheet_schema", "schema": extraction_schema}
        }
    )

    # Wait for completion
    while run.status in ["queued", "in_progress"]:
        run = client.beta.threads.runs.retrieve(thread_id=thread.id, run_id=run.id)

    if run.status == "failed":
        logger.error(f"Extraction failed for file {answer_sheet_file_id}: {run.last_error}")
        raise HTTPException(status_code=500, detail=f"Extraction failed: {run.last_error}")

    # Get the response
    messages = client.beta.threads.messages.list(thread_id=thread.id)
    for msg in messages.data:
        if msg.role == "assistant":
            result = json.loads(msg.content[0].text.value)
            # Ensure file_id is set correctly
            result["file_id"] = answer_sheet_file_id
            logger.info(f"Successfully extracted answers for student: {result.get('student_name', 'Unknown')} from file {answer_sheet_file_id}")
            return result
    
    raise HTTPException(status_code=500, detail="No response from assistant")

# def extract_answer_sheets(evaluation_id: str, user_id: str, answer_sheet_file_ids: list[str]) -> dict:
#     """
#     Extract evaluation content from answer sheets using OpenAI structured outputs.
#     Processes all answer sheet files and returns structured data with file attribution.

#     Returns structured JSON matching the defined schema.
#     """
#     evaluation = get_evaluation_by_evaluation_id(evaluation_id)
#     assistant_id = evaluation["evaluation_assistant_id"]
#     vector_store_id = evaluation["vector_store_id"]
    
#     # Quick check that vector store is ready
#     vector_store = client.vector_stores.retrieve(vector_store_id)
#     if vector_store.status != "completed":
#         logger.warning(f"Vector store not ready: {vector_store.status}")
#         import time
#         time.sleep(5)  # Brief wait
    
#     extraction_schema = {
#         "type": "object",
#         "properties": {
#             "answer_sheets": {
#                 "type": "array",
#                 "items": {
#                     "type": "object",
#                     "properties": {
#                         "file_id": {"type": "string"},
#                         "student_name": {"type": "string"},
#                         "answers": {
#                             "type": "array",
#                             "items": {
#                                 "type": "object",
#                                 "properties": {
#                                     "question_number": {"type": "string"},
#                                     "question_text": {"type": "string"},
#                                     "student_answer": {"type": "string"}
#                                 },
#                                 "required": ["question_number", "question_text", "student_answer"]
#                             }
#                         }
#                     },
#                     "required": ["file_id", "student_name", "answers"]
#                 }
#             }
#         },
#         "required": ["answer_sheets"]
#     }

#     # Create thread with attachments
#     thread = client.beta.threads.create(
#         messages=[
#             {
#                 "role": "user",
#                 "content": f"Extract ALL questions and answers from each of the {len(answer_sheet_file_ids)} provided answer sheet files; include student name if available; for every question always include question text, preserving numbering/order; if the answer is missing, blank, or 'N/A', set 'answer' to null; capture answers exactly as written; return ONLY valid JSON.",
#                 "attachments": [
#                     {"file_id": fid, "tools": [{"type": "file_search"}]}
#                     for fid in answer_sheet_file_ids
#                 ]
#             }
#         ]
#     )

#     # Run assistant with structured output
#     run = client.beta.threads.runs.create(
#         thread_id=thread.id,
#         assistant_id=assistant_id,
#         response_format={
#             "type": "json_schema",
#             "json_schema": {"name": "answer_sheets_schema", "schema": extraction_schema}
#         }
#     )

#     # Wait for completion
#     while run.status in ["queued", "in_progress"]:
#         run = client.beta.threads.runs.retrieve(thread_id=thread.id, run_id=run.id)

#     # Get the response
#     messages = client.beta.threads.messages.list(thread_id=thread.id)
#     for msg in messages.data:
#         if msg.role == "assistant":
#             return json.loads(msg.content[0].text.value)
    
#     raise HTTPException(status_code=500, detail="No response from assistant")


def evaluate_single_student(evaluation_id: str, user_id: str, extracted_mark_scheme: dict, student_answer_sheet: dict):
    """
    Evaluate a single student's answers against the mark scheme.
    
    Returns structured JSON with scores and feedback for the individual student.
    """
    evaluation = get_evaluation_by_evaluation_id(evaluation_id)
    evaluation_assistant_id = evaluation["evaluation_assistant_id"]
    
    # Build payload for prompt rendering with extracted data
    payload = {
        "mark_scheme": json.dumps(extracted_mark_scheme, indent=2),
        "student_answer_sheet": json.dumps(student_answer_sheet, indent=2),
        "evaluation_id": evaluation_id
    }
    
    # Render evaluation prompt for single student
    evaluation_prompt = PromptParser().render_prompt(
        "app/prompts/evaluation/evaluation.json",
        payload
    )
    print(evaluation_prompt)
    
    logger.info(f"Evaluating student: {student_answer_sheet.get('student_name', 'Unknown')} for evaluation {evaluation_id}")
    
    evaluation_schema = {
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

    # Create thread for single student evaluation
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
            "json_schema": {"name": "single_student_evaluation_schema", "schema": evaluation_schema}
        }
    )
    
    # Wait for completion with logging
    while run.status in ["queued", "in_progress"]:
        logger.info(f"Single student evaluation {evaluation_id} status: {run.status}")
        run = client.beta.threads.runs.retrieve(thread_id=thread.id, run_id=run.id)
    
    logger.info(f"Single student evaluation {evaluation_id} completed with status: {run.status}")
    
    if run.status == "failed":
        logger.error(f"Single student evaluation {evaluation_id} failed: {run.last_error}")
        raise HTTPException(status_code=500, detail=f"Single student evaluation failed: {run.last_error}")

    # Get the response
    messages = client.beta.threads.messages.list(thread_id=thread.id)
    if not messages.data:
        logger.error(f"No messages found in thread for single student evaluation {evaluation_id}")
        raise HTTPException(status_code=500, detail="No response from OpenAI")

    # Get the latest assistant message
    assistant_message = None
    for message in messages.data:
        if message.role == "assistant":
            assistant_message = message
            break
    
    if not assistant_message:
        logger.error(f"No assistant message found for single student evaluation {evaluation_id}")
        raise HTTPException(status_code=500, detail="No assistant response found")

    structured_output = assistant_message.content[0].text.value
    logger.info(f"Raw OpenAI response for single student evaluation {evaluation_id}: {structured_output[:200]}...")
    
    # Parse JSON string to dictionary
    try:
        evaluation_result = json.loads(structured_output)
        
        # Validate that we got actual data, not schema
        if "properties" in evaluation_result and "type" in evaluation_result:
            logger.error(f"OpenAI returned schema instead of data for single student evaluation {evaluation_id}")
            raise HTTPException(status_code=500, detail="OpenAI returned schema definition instead of evaluation results")
        
        # Ensure required fields are present
        if not all(field in evaluation_result for field in ['student_name', 'file_id', 'answers', 'total_score', 'max_total_score']):
            logger.error(f"Invalid single student evaluation result structure for evaluation {evaluation_id}")
            raise HTTPException(status_code=500, detail="Invalid single student evaluation result structure")
        
        # Ensure file_id matches
        evaluation_result["file_id"] = student_answer_sheet["file_id"]
        
        logger.info(f"Successfully evaluated student: {evaluation_result['student_name']} with total score: {evaluation_result['total_score']}/{evaluation_result['max_total_score']}")
        return evaluation_result
        
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse OpenAI response as JSON for single student evaluation {evaluation_id}: {structured_output}")
        raise HTTPException(status_code=500, detail=f"Invalid JSON response from OpenAI: {str(e)}")
    except Exception as e:
        logger.error(f"Error processing single student evaluation result for evaluation {evaluation_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

def evaluate_files_individually(evaluation_id: str, user_id: str, answer_sheet_file_ids: list[str]):
    """
    Evaluate each answer sheet file individually against the mark scheme.
    Iterates through each file ID and processes them one by one.
    
    Returns combined evaluation results for all students.
    """
    evaluation = get_evaluation_by_evaluation_id(evaluation_id)
    mark_scheme_file_id = evaluation["mark_scheme_file_id"]
    
    logger.info(f"Starting individual evaluation for {len(answer_sheet_file_ids)} answer sheets in evaluation {evaluation_id}")
    
    # Extract mark scheme once (it's the same for all students)
    extracted_mark_scheme = extract_mark_scheme(evaluation_id, user_id, mark_scheme_file_id)
    logger.info(f"Extracted mark scheme with {len(extracted_mark_scheme.get('mark_scheme', []))} questions")
    
    # Store individual evaluation results
    all_student_evaluations = []
    
    # Process each answer sheet file individually
    for i, answer_sheet_file_id in enumerate(answer_sheet_file_ids, 1):
        try:
            logger.info(f"Processing answer sheet {i}/{len(answer_sheet_file_ids)}: {answer_sheet_file_id}")
            
            # Extract single answer sheet
            student_answer_sheet = extract_single_answer_sheet(evaluation_id, user_id, answer_sheet_file_id)
            
            # Evaluate single student
            student_evaluation = evaluate_single_student(evaluation_id, user_id, extracted_mark_scheme, student_answer_sheet)
            
            # Add to results
            all_student_evaluations.append(student_evaluation)
            
            logger.info(f"Completed evaluation for student: {student_evaluation['student_name']} "
                       f"(Score: {student_evaluation['total_score']}/{student_evaluation['max_total_score']})")
            
        except Exception as e:
            logger.error(f"Failed to process answer sheet {answer_sheet_file_id}: {str(e)}")
            # Continue with other files even if one fails
            continue
    
    # Combine all results into final structure
    final_evaluation_result = {
        "evaluation_id": evaluation_id,
        "students": all_student_evaluations
    }
    
    logger.info(f"Successfully completed individual evaluation for {len(all_student_evaluations)} students in evaluation {evaluation_id}")
    
    return final_evaluation_result

# def evaluate_files(evaluation_id: str, user_id: str, extracted_mark_scheme: dict, extracted_answer_sheets: dict):
#     """
#     Evaluate student answers against mark scheme using previously extracted structured data.
    
#     Returns structured JSON with scores and feedback for each answer.
#     """
#     evaluation = get_evaluation_by_evaluation_id(evaluation_id)
#     evaluation_assistant_id = evaluation["evaluation_assistant_id"]
    
#     # Build payload for prompt rendering with extracted data
#     payload = {
#         "mark_scheme": json.dumps(extracted_mark_scheme, indent=2),
#         "answer_sheets": json.dumps(extracted_answer_sheets, indent=2),
#         "evaluation_id": evaluation_id
#     }
    
#     # Render evaluation prompt
#     evaluation_prompt = PromptParser().render_prompt(
#         "app/prompts/evaluation/evaluation.json",
#         payload
#     )
#     print(evaluation_prompt)
#     logger.info(f"Evaluation prompt rendered for evaluation {evaluation_id}")
    
#     evaluation_schema = {
#         "type": "object",
#         "properties": {
#             "evaluation_id": {"type": "string"},
#             "students": {
#                 "type": "array",
#                 "items": {
#                     "type": "object",
#                     "properties": {
#                         "student_name": {"type": "string"},
#                         "file_id": {"type": "string"},
#                         "answers": {
#                             "type": "array",
#                             "items": {
#                                 "type": "object",
#                                 "properties": {
#                                     "question_number": {"type": "string"},
#                                     "question_text": {"type": "string"},
#                                     "student_answer": {"type": "string"},
#                                     "correct_answer": {"type": "string"},
#                                     "score": {"type": "number"},
#                                     "max_score": {"type": "number"},
#                                     "feedback": {"type": "string"}
#                                 },
#                                 "required": [
#                                     "question_number",
#                                     "question_text",
#                                     "student_answer",
#                                     "correct_answer",
#                                     "score",
#                                     "max_score",
#                                     "feedback"
#                                 ]
#                             }
#                         },
#                         "total_score": {"type": "number"},
#                         "max_total_score": {"type": "number"}
#                     },
#                     "required": ["student_name", "file_id", "answers", "total_score", "max_total_score"]
#                 }
#             }
#         },
#         "required": ["evaluation_id", "students"]
#     }

#     # Log the number of students being evaluated
#     num_students = len(extracted_answer_sheets.get("answer_sheets", []))
#     logger.info(f"Starting evaluation for {num_students} students in evaluation {evaluation_id}")
    
#     # Create thread without file attachments since we're using extracted data
#     thread = client.beta.threads.create(
#         messages=[
#             {
#                 "role": "user",
#                 "content": evaluation_prompt
#             }
#         ]
#     )

#     # Run assistant with structured output
#     run = client.beta.threads.runs.create(
#         thread_id=thread.id,
#         assistant_id=evaluation_assistant_id,
#         response_format={
#             "type": "json_schema",
#             "json_schema": {"name": "evaluation_schema", "schema": evaluation_schema}
#         }
#     )
    
#     # Wait for completion with better logging
#     while run.status in ["queued", "in_progress"]:
#         logger.info(f"Evaluation {evaluation_id} status: {run.status}")
#         run = client.beta.threads.runs.retrieve(thread_id=thread.id, run_id=run.id)
    
#     logger.info(f"Evaluation {evaluation_id} completed with status: {run.status}")
    
#     if run.status == "failed":
#         logger.error(f"Evaluation {evaluation_id} failed: {run.last_error}")
#         raise HTTPException(status_code=500, detail=f"Evaluation failed: {run.last_error}")

#     # Get the response
#     messages = client.beta.threads.messages.list(thread_id=thread.id)
#     if not messages.data:
#         logger.error(f"No messages found in thread for evaluation {evaluation_id}")
#         raise HTTPException(status_code=500, detail="No response from OpenAI")

#     # Get the latest assistant message
#     assistant_message = None
#     for message in messages.data:
#         if message.role == "assistant":
#             assistant_message = message
#             break
    
#     if not assistant_message:
#         logger.error(f"No assistant message found for evaluation {evaluation_id}")
#         raise HTTPException(status_code=500, detail="No assistant response found")

#     structured_output = assistant_message.content[0].text.value
#     logger.info(f"Raw OpenAI response for evaluation {evaluation_id}: {structured_output[:500]}...")
    
#     # Parse JSON string to dictionary
#     try:
#         evaluation_result = json.loads(structured_output)
        
#         # Validate that we got actual data, not schema
#         if "properties" in evaluation_result and "type" in evaluation_result:
#             logger.error(f"OpenAI returned schema instead of data for evaluation {evaluation_id}")
#             raise HTTPException(status_code=500, detail="OpenAI returned schema definition instead of evaluation results")
        
#         # Set evaluation_id if not present (sometimes OpenAI doesn't include it)
#         if "evaluation_id" not in evaluation_result:
#             evaluation_result["evaluation_id"] = evaluation_id
#             logger.info(f"Added missing evaluation_id to result for evaluation {evaluation_id}")
        
#         # Validate required fields
#         if "students" not in evaluation_result:
#             logger.error(f"Invalid evaluation result structure for evaluation {evaluation_id}: missing 'students' field")
#             raise HTTPException(status_code=500, detail="Invalid evaluation result structure: missing 'students' field")
        
#         # Log detailed information about the evaluation
#         students_evaluated = len(evaluation_result.get('students', []))
#         total_answers = sum(len(student.get('answers', [])) for student in evaluation_result.get('students', []))
#         logger.info(f"Successfully completed evaluation {evaluation_id}: {students_evaluated} students, {total_answers} total answers evaluated")
        
#         # Validate each student has required fields
#         for i, student in enumerate(evaluation_result.get('students', [])):
#             if not all(field in student for field in ['student_name', 'file_id', 'answers', 'total_score', 'max_total_score']):
#                 logger.warning(f"Student {i} missing required fields in evaluation {evaluation_id}")
        
#         return evaluation_result
#     except json.JSONDecodeError as e:
#         logger.error(f"Failed to parse OpenAI response as JSON for evaluation {evaluation_id}: {structured_output}")
#         raise HTTPException(status_code=500, detail=f"Invalid JSON response from OpenAI: {str(e)}")
#     except Exception as e:
#         logger.error(f"Error processing evaluation result for evaluation {evaluation_id}: {str(e)}")
#         raise HTTPException(status_code=500, detail=str(e))



