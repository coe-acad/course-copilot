from fastapi import APIRouter, Request, UploadFile, Depends
from pydantic import BaseModel
from fastapi import Form, File, HTTPException
from fastapi.responses import StreamingResponse
from typing import List, Optional
import logging
import json
from uuid import uuid4
import shutil
import asyncio
from datetime import datetime
from flask import request
import os
from pathlib import Path
import csv
import io
from ..utils.verify_token import verify_token
from app.services.mongo import create_evaluation, get_evaluation_by_evaluation_id, update_evaluation_with_result, update_question_score_feedback, update_evaluation, get_evaluations_by_course_id, create_asset, db, get_email_by_user_id, create_ai_feedback, get_ai_feedback_by_evaluation_id, update_ai_feedback, get_user_display_name, create_qa_data, update_evaluation, get_qa_data_by_evaluation_id
from app.services.openai_service import create_evaluation_assistant_and_vector_store, evaluate_files_all_in_one
from concurrent.futures import ThreadPoolExecutor, as_completed
from app.utils.eval_mail import send_eval_completion_email, send_eval_error_email
from app.utils.extraction_answersheet import extract_text_tables, split_into_qas
from app.utils.extraction_markscheme import extract_text_from_mark_scheme
logger = logging.getLogger(__name__)
router = APIRouter()

class UploadFilesRequest(BaseModel):
    user_id: str
    course_id: str
    files: List[UploadFile]

class EvaluationResponse(BaseModel):
    evaluation_id: str
    evaluation_result: dict

class EditresultRequest(BaseModel):
    evaluation_id: str
    file_id: str
    question_number: str
    score: float
    feedback: str

@router.post("/evaluation/upload-mark-scheme")
def upload_mark_scheme(course_id: str = Form(...), user_id: str = Depends(verify_token), mark_scheme: UploadFile = File(...)):
    try:
        evaluation_id = str(uuid4())
        
        # Create directory for this evaluation
        eval_dir = Path(f"local_storage/temp_evaluations/{evaluation_id}")
        eval_dir.mkdir(parents=True, exist_ok=True)
        
        # Save mark scheme file locally
        mark_scheme_filename = f"mark_scheme_{mark_scheme.filename}"
        mark_scheme_path = eval_dir / mark_scheme_filename
        
        with open(mark_scheme_path, "wb") as f:
            content = mark_scheme.file.read()
            f.write(content)
        
        logger.info(f"Saved mark scheme to {mark_scheme_path}")
        
        # Create evaluation assistant for LLM evaluation later
        eval_info = create_evaluation_assistant_and_vector_store(evaluation_id)
        evaluation_assistant_id = eval_info[0]
        vector_store_id = eval_info[1]
        
        # Create evaluation record
        create_evaluation(
            evaluation_id=evaluation_id,
            course_id=course_id,
            evaluation_assistant_id=evaluation_assistant_id,
            vector_store_id=vector_store_id,
            mark_scheme_path=str(mark_scheme_path),
            answer_sheet_paths=[],
            answer_sheet_filenames=[]
        )
        
        # Verify creation
        created_evaluation = get_evaluation_by_evaluation_id(evaluation_id)
        if not created_evaluation:
            logger.error(f"Failed to create evaluation {evaluation_id}")
            raise HTTPException(status_code=500, detail="Failed to create evaluation record")
        
        logger.info(f"Successfully created evaluation {evaluation_id}")
        
        return {
            "evaluation_id": evaluation_id,
            "message": "Mark scheme uploaded successfully"
        }
        
    except Exception as e:
        logger.error(f"Error uploading mark scheme: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error uploading mark scheme: {str(e)}")

@router.post("/evaluation/upload-answer-sheets")
def upload_answer_sheets(evaluation_id: str = Form(...), answer_sheets: List[UploadFile] = File(...), user_id: str = Depends(verify_token)):
    try:
        # Validate inputs
        if not answer_sheets:
            raise HTTPException(status_code=400, detail="No answer sheet files provided")
        
        logger.info(f"Uploading {len(answer_sheets)} answer sheets for evaluation {evaluation_id}")
        
        # Get evaluation record
        evaluation = get_evaluation_by_evaluation_id(evaluation_id)
        if not evaluation:
            raise HTTPException(status_code=404, detail="Evaluation not found")
        
        # Check if mark scheme exists
        if not evaluation.get("mark_scheme_path"):
            raise HTTPException(status_code=400, detail="Mark scheme must be uploaded first")
        
        # Save answer sheets locally
        eval_dir = Path(f"local_storage/temp_evaluations/{evaluation_id}")
        eval_dir.mkdir(parents=True, exist_ok=True)
        
        answer_sheet_paths = []
        answer_sheet_filenames = []
        
        for i, answer_sheet in enumerate(answer_sheets):
            filename = f"answer_sheet_{i+1}_{answer_sheet.filename}"
            file_path = eval_dir / filename
            
            with open(file_path, "wb") as f:
                content = answer_sheet.file.read()
                f.write(content)
            
            answer_sheet_paths.append(str(file_path))
            answer_sheet_filenames.append(answer_sheet.filename)
            logger.info(f"Saved answer sheet to {file_path}")
        
        # Update evaluation record
        update_evaluation(evaluation_id, {
            "answer_sheet_paths": answer_sheet_paths,
            "answer_sheet_filenames": answer_sheet_filenames
        })
        
        logger.info(f"Successfully uploaded {len(answer_sheet_paths)} answer sheets for evaluation {evaluation_id}")

        return {
            "evaluation_id": evaluation_id,
            "answer_sheet_count": len(answer_sheet_paths),
            "answer_sheet_filenames": answer_sheet_filenames
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error uploading answer sheets for evaluation {evaluation_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error uploading answer sheets: {str(e)}")

def _process_evaluation(evaluation_id: str, user_id: str):
    """Process evaluation in background using local file extraction with parallel workers"""
    partial_result = None  # Store whatever we have so we can return partial output on failure
    try:
        # Check if evaluation is already completed
        evaluation = get_evaluation_by_evaluation_id(evaluation_id)
        if not evaluation:
            logger.error(f"Evaluation {evaluation_id} not found")
            return
        
        mark_scheme_path = evaluation.get("mark_scheme_path")
        answer_sheet_paths = evaluation.get("answer_sheet_paths")
        answer_sheet_filenames = evaluation.get("answer_sheet_filenames")
        
        if not mark_scheme_path or not answer_sheet_paths:
            logger.error(f"Missing file paths for evaluation {evaluation_id}")
            return
        
        # Extract mark scheme
        logger.info(f"Extracting mark scheme from {mark_scheme_path}")
        extracted_mark_scheme = extract_text_from_mark_scheme(mark_scheme_path)
        question_count = len(extracted_mark_scheme.get('mark_scheme', []))
        logger.info(f"Mark scheme extracted: {extracted_mark_scheme}")
        
        # Extract answer sheets
        logger.info(f"Extracting {len(answer_sheet_paths)} answer sheets")
        extracted_answer_sheets = []
        all_qas_data = []
        for i, answer_sheet_path in enumerate(answer_sheet_paths):
            try:
                pages = extract_text_tables(answer_sheet_path)
                extraction_result = split_into_qas(pages, pdf_path=answer_sheet_path)
                
                extracted_email = extraction_result.get("email", None)
                qas_list = extraction_result.get("answers", [])                
                qas_data = extraction_result.get("full_data", [])

                # Collect QA data to save in bulk later
                all_qas_data.append({
                    "student_index": i,
                    "qa_data": qas_data
                })

                answer_sheet_data = {
                    "file_id": f"answer_sheet_{i+1}",
                    "filename": answer_sheet_filenames[i] if i < len(answer_sheet_filenames) else f"answer_sheet_{i+1}.pdf",
                    "student_name": answer_sheet_filenames[i].replace('.pdf', '').replace('_', ' ') if i < len(answer_sheet_filenames) else f"Student {i+1}",
                    "email": extracted_email,
                    "answers": qas_list
                }
                extracted_answer_sheets.append(answer_sheet_data)
                logger.info(f"Answer sheet {i+1} extracted: {answer_sheet_data}")
            except Exception as extraction_error:
                logger.error(f"Failed to extract answer sheet {i+1}: {str(extraction_error)}")
                continue
        
        logger.info(f"Successfully extracted {len(extracted_answer_sheets)}/{len(answer_sheet_paths)} answer sheets")

        # Save all QA data at once
        if all_qas_data:
            create_qa_data(evaluation_id, all_qas_data)
            logger.info(f"QAs created for evaluation {evaluation_id} with {len(all_qas_data)} entries")

        # Determine batch size based on question count
        total_sheets = len(extracted_answer_sheets)
        BATCH_SIZE = 5 if question_count < 15 else 3
        total_batches = (total_sheets + BATCH_SIZE - 1) // BATCH_SIZE
        
        logger.info(f"Starting evaluation: {total_sheets} answer sheets, {total_batches} batches (size: {BATCH_SIZE})")
        
        # Helper function to process a single batch
        def process_batch(batch_num: int, batch_sheets: list):
            """Process a single batch and return results"""
            filenames = [sheet.get('filename', 'Unknown') for sheet in batch_sheets]
            logger.info(f"→ Batch {batch_num} of {total_batches} started: {filenames}")
            
            batch_data = {"answer_sheets": batch_sheets}
            batch_result = evaluate_files_all_in_one(evaluation_id, user_id, extracted_mark_scheme, batch_data)
            
            logger.info(f"✓ Batch {batch_num} of{total_batches} completed")
            
            return batch_num, batch_result.get("students", [])
        
        # Process answer sheets in batches in parallel
        batch_results = {}  # Store results by batch number to preserve order
        
        # First, log which files go to which batch
        logger.info("=" * 60)
        logger.info("BATCH ASSIGNMENT:")
        for batch_start in range(0, total_sheets, BATCH_SIZE):
            batch_end = min(batch_start + BATCH_SIZE, total_sheets)
            batch_sheets = extracted_answer_sheets[batch_start:batch_end]
            batch_num = (batch_start // BATCH_SIZE) + 1
            filenames = [sheet.get('filename', 'Unknown') for sheet in batch_sheets]
            logger.info(f"  Batch {batch_num}: {filenames}")
        logger.info("=" * 60)
        
        # Limit workers based on batch size to control concurrency
        max_workers = 2 if BATCH_SIZE == 5 else 3
        logger.info(f"Using {max_workers} workers for parallel processing")
        
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # Submit all batch jobs
            futures = {}
            for batch_start in range(0, total_sheets, BATCH_SIZE):
                batch_end = min(batch_start + BATCH_SIZE, total_sheets)
                batch_sheets = extracted_answer_sheets[batch_start:batch_end]
                batch_num = (batch_start // BATCH_SIZE) + 1
                
                future = executor.submit(process_batch, batch_num, batch_sheets)
                futures[future] = batch_num
            
            # Collect results as they complete (may be out of order)
            for future in as_completed(futures):
                batch_num = futures[future]
                try:
                    result_batch_num, batch_students = future.result()
                    batch_results[result_batch_num] = batch_students  # Store by batch number
                except Exception as e:
                    logger.error(f"✗ Batch {batch_num} FAILED: {str(e)}")
                    raise HTTPException(status_code=500, detail=f"Batch {batch_num} evaluation failed: {str(e)}")
        
        # Reconstruct students in correct order by batch number
        all_students = []
        for batch_num in sorted(batch_results.keys()):
            all_students.extend(batch_results[batch_num])
        
        logger.info("=" * 60)
        logger.info(f"ALL BATCHES COMPLETED: {sorted(batch_results.keys())} | Total students: {len(all_students)}")
        logger.info("=" * 60)
        
        # Track what came back so we can surface partial results in case of failure
        partial_result = {
            "evaluation_id": evaluation_id,
            "students": all_students
        }
        expected_file_ids = [sheet.get("file_id") for sheet in extracted_answer_sheets if sheet.get("file_id")]
        returned_file_ids = [s.get("file_id") for s in all_students if s.get("file_id")]
        missing_file_ids = [fid for fid in expected_file_ids if fid not in returned_file_ids]
        duplicate_file_ids = [fid for fid in set(returned_file_ids) if returned_file_ids.count(fid) > 1]

        # Verify all students were evaluated
        if len(all_students) != len(extracted_answer_sheets):
            logger.error(f"Student count mismatch: expected {len(extracted_answer_sheets)}, got {len(all_students)}")
            if missing_file_ids:
                logger.error(f"Missing file_ids: {missing_file_ids}")
            if duplicate_file_ids:
                logger.error(f"Duplicate file_ids in evaluation results: {duplicate_file_ids}")
            raise HTTPException(status_code=500, detail=f"Evaluation incomplete: student count mismatch. Missing: {missing_file_ids or 'unknown'}")
        
        logger.info(f"All batches completed: {len(all_students)} students evaluated successfully")
        
        # Create final evaluation result
        evaluation_result = {
            "evaluation_id": evaluation_id,
            "students": all_students
        }
        logger.info(f"Final evaluation result: {evaluation_result}")
        # Verify and recalculate scores for each student
        for student in evaluation_result.get("students", []):
            answers = student.get("answers", [])
            calculated_total = sum((a.get("score") or 0) for a in answers if a.get("score") is not None)
            calculated_max = sum((a.get("max_score") or 0) for a in answers)
            student["total_score"] = calculated_total
            student["max_total_score"] = calculated_max

        # Calculate aggregate totals
        overall_total = sum(s.get("total_score", 0) for s in evaluation_result.get("students", []))
        overall_max = sum(s.get("max_total_score", 0) for s in evaluation_result.get("students", []))
        evaluation_result["total_score"] = overall_total
        evaluation_result["max_total_score"] = overall_max

        
        # Save evaluation result to MongoDB
        try:
            update_evaluation_with_result(evaluation_id, evaluation_result)
            logger.info(f"Evaluation result saved to database")
        except Exception as save_error:
            logger.error(f"Failed to save evaluation result: {str(save_error)}")
            raise save_error
        
        # Extract all feedback from students' answers
        all_feedback = []
        
        # Get answer sheet filenames from evaluation record
        evaluation = get_evaluation_by_evaluation_id(evaluation_id)
        answer_sheet_filenames = evaluation.get("answer_sheet_filenames", [])
        
        for i, student in enumerate(evaluation_result.get("students", [])):
            # Extract student name from filename
            student_name = "Unknown Student"
            if i < len(answer_sheet_filenames):
                filename = answer_sheet_filenames[i]
                # Remove .pdf extension and extract name before underscore
                if filename.endswith('.pdf'):
                    filename = filename[:-4]  # Remove .pdf
                # Extract name before first underscore (e.g., "Vaibhav Shukla_exam_answers" -> "Vaibhav Shukla")
                if '_' in filename:
                    student_name = filename.split('_')[0]
                else:
                    student_name = filename
            
            student_feedback = {
                "file_id": student.get("file_id"),
                "student_name": student_name,
                "answers_feedback": []
            }
            
            for answer in student.get("answers", []):
                if answer.get("feedback"):
                    student_feedback["answers_feedback"].append({
                        "question_number": answer.get("question_number"),
                        "feedback": answer.get("feedback")
                    })
            
            if student_feedback["answers_feedback"]:  # Only add if there's feedback
                all_feedback.append(student_feedback)
        
        # Save AI feedback to MongoDB
        if all_feedback:
            create_ai_feedback(evaluation_id, {"feedback": all_feedback})
            
        # Send completion email
        try:
            send_eval_completion_email(evaluation_id, user_id)
            update_evaluation(evaluation_id, {"email_sent": True})
            logger.info(f"Completion email sent")
        except Exception as email_error:
            logger.error(f"Failed to send completion email: {str(email_error)}")
        
        # Clean up temporary files
        try:
            eval_dir = Path(f"local_storage/temp_evaluations/{evaluation_id}")
            if eval_dir.exists():
                shutil.rmtree(eval_dir)
                logger.info(f"Temporary files cleaned up")
        except Exception as cleanup_error:
            logger.error(f"Failed to cleanup temporary files: {str(cleanup_error)}")
        
        return evaluation_result
    except Exception as e:
        logger.error(f"Evaluation failed: {str(e)}", exc_info=True)

        # Send error email to user
        try:
            send_eval_error_email(evaluation_id, user_id, str(e))
        except Exception as email_error:
            logger.error(f"Failed to send error email: {str(email_error)}")

        # Update evaluation status to failed
        try:
            update_evaluation(evaluation_id, {"status": "failed"})
        except Exception as status_error:
            logger.error(f"Failed to update evaluation status: {str(status_error)}")
        # Persist partial results so they can be surfaced via status API
        try:
            if partial_result:
                update_evaluation(evaluation_id, {"partial_result": partial_result})
        except Exception as partial_error:
            logger.error(f"Failed to store partial_result for {evaluation_id}: {str(partial_error)}")

        # Clean up temporary files
        try:
            eval_dir = Path(f"local_storage/temp_evaluations/{evaluation_id}")
            if eval_dir.exists():
                shutil.rmtree(eval_dir)
        except Exception as cleanup_error:
            logger.error(f"Failed to cleanup temporary files: {str(cleanup_error)}")
        
        result_payload = {
            "error": str(e)
        }
        if partial_result:
            result_payload["partial_result"] = partial_result
        return result_payload

@router.get("/evaluation/evaluate-files")
async def evaluate_files(evaluation_id: str, user_id: str = Depends(verify_token)):
    try:
        evaluation = get_evaluation_by_evaluation_id(evaluation_id)
        if not evaluation:
            raise HTTPException(status_code=404, detail=f"Evaluation {evaluation_id} not found")
        
        # If results already exist, return completed immediately (idempotent)
        if "evaluation_result" in evaluation:
            return {
                "evaluation_id": evaluation_id,
                "evaluation_result": evaluation["evaluation_result"]
            }
        
        # If already processing, return processing status (prevent duplicate runs)
        if evaluation.get("status") == "processing":
            return {
                "evaluation_id": evaluation_id,
                "message": "Evaluation already in progress"
            }
        
        # Verify files are uploaded
        if not evaluation.get("mark_scheme_path"):
            raise HTTPException(status_code=400, detail="Mark scheme not uploaded")
        
        if not evaluation.get("answer_sheet_paths"):
            raise HTTPException(status_code=400, detail="Answer sheets not uploaded")

        # Mark as processing and start evaluation in background
        update_evaluation(evaluation_id, {"status": "processing"})
        asyncio.create_task(asyncio.to_thread(_process_evaluation, evaluation_id, user_id))
        
        return {
            "evaluation_id": evaluation_id,
            "message": "Evaluation started in background"
        }
        
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error starting evaluation {evaluation_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error starting evaluation: {str(e)}")

@router.get("/evaluation/get-qas")
def get_qas(evaluation_id: str, user_id: str, student_index: int = 0):
    try:
        qas_doc = get_qa_data_by_evaluation_id(evaluation_id)
        if not qas_doc:
            return {
                "question_data": [],
                "answer_data": []
            }

        stored_data = qas_doc.get("qa_data", [])
        
        target_data = []

        # Check if stored_data is our new wrapper structure (list of dicts with student_index)
        if isinstance(stored_data, list) and len(stored_data) > 0:
            first_item = stored_data[0]
            if isinstance(first_item, dict) and "student_index" in first_item and "qa_data" in first_item:
                 # It's the new structure
                 found = next((item for item in stored_data if item.get("student_index") == int(student_index)), None)
                 if found:
                     target_data = found.get("qa_data", [])
            else:
                 # It's likely the old structure (directly the QA list for one student)
                 # In this case we just return it, ignoring student_index as we likely only have one
                 target_data = stored_data
        
        question_data = []
        answer_data = []

        for item in target_data:
            question_data.append(item.get("question", ""))

            answer_list = item.get("answer", [])
            if answer_list:
                answer_data.append(answer_list[0].get("content", ""))
            else:
                answer_data.append("")

        return {
            "question_data": question_data,
            "answer_data": answer_data
        }

    except Exception as e:
        logger.error(f"Error getting qas data for evaluation {evaluation_id}: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Error getting qas data: {str(e)}"
        )

@router.put("/evaluation/edit-results")
def edit_results(request: EditresultRequest, user_id: str = Depends(verify_token)):
    try:
        # Update the question score and feedback
        update_question_score_feedback(request.evaluation_id, request.file_id, request.question_number, request.score, request.feedback)
        
        # Get current evaluation to calculate new total score
        evaluation = get_evaluation_by_evaluation_id(request.evaluation_id)
        if evaluation and "evaluation_result" in evaluation:
            for student in evaluation["evaluation_result"].get("students", []):
                if student.get("file_id") == request.file_id:
                    # Calculate new total score
                    total_score = sum(
                        answer.get("score", 0) 
                        for answer in student.get("answers", [])
                        if answer.get("score") is not None
                    )
                    
                    # Update the total score using MongoDB directly with proper positional operator
                    db["evaluations"].update_one(
                        {"evaluation_id": request.evaluation_id, "evaluation_result.students.file_id": request.file_id},
                        {"$set": {"evaluation_result.students.$.total_score": total_score}}
                    )
                    break
        
        # Update evaluation status
        update_evaluation(request.evaluation_id, {"status": "updated"})
        
        return {"message": "Results updated"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/evaluation/status/{evaluation_id}")
def check_evaluation(evaluation_id: str, user_id: str = Depends(verify_token)):
    try:
        logger.info(f"Checking status for evaluation_id: {evaluation_id}")
        evaluation = get_evaluation_by_evaluation_id(evaluation_id)
        
        if not evaluation:
            logger.warning(f"Evaluation {evaluation_id} not found in database")
            raise HTTPException(status_code=404, detail=f"Evaluation {evaluation_id} not found")
        
        logger.info(f"Found evaluation {evaluation_id}, checking for evaluation_result...")
        
        # Check if evaluation failed
        if evaluation.get("status") == "failed":
            logger.info(f"Evaluation {evaluation_id} failed")
            return {
                "status": "failed",
                "message": "Evaluation processing failed. Please try again or contact support.",
                "answer_sheet_filenames": evaluation.get("answer_sheet_filenames", []),
                "partial_result": evaluation.get("partial_result")
            }
        
        if "evaluation_result" in evaluation:
            logger.info(f"Evaluation {evaluation_id} has results, returning completed status")
            # Trigger completion email once
            try:
                if not evaluation.get("email_sent"):
                    # send_eval_completion_email(evaluation_id, user_id)
                    update_evaluation(evaluation_id, {"email_sent": True})
            except Exception as e:
                logger.error(f"Failed to send completion email for {evaluation_id}: {str(e)}")
            return {
                "status": "completed",
                "evaluation_result": evaluation["evaluation_result"],
                "answer_sheet_filenames": evaluation.get("answer_sheet_filenames", [])
            }
        else:
            logger.info(f"Evaluation {evaluation_id} exists but no evaluation_result yet, returning processing status")
            return {
                "status": "processing",
                "answer_sheet_filenames": evaluation.get("answer_sheet_filenames", [])
            }
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error checking evaluation status for {evaluation_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error checking evaluation status: {str(e)}")

@router.post("/evaluation/save/{evaluation_id}")
def save_evaluation(evaluation_id: str, asset_name: str = Form(...), user_id: str = Depends(verify_token)):
    try:
        evaluation = get_evaluation_by_evaluation_id(evaluation_id)
        if not evaluation:
            raise HTTPException(status_code=404, detail="Evaluation not found")

        # Get user's display name for the asset
        user_display_name = get_user_display_name(user_id)
        if not user_display_name:
            user_display_name = "Unknown User"

        # Save a lightweight evaluation asset that references the evaluation_id
        # This enables listing a card and opening the live Evaluation UI by ID
        logger.info(f"Saving evaluation reference {evaluation_id}")
        create_asset(
            course_id=evaluation["course_id"],
            asset_name=asset_name,
            asset_category="evaluation",
            asset_type="evaluation",
            asset_content=evaluation_id,
            asset_last_updated_by=user_display_name,
            asset_last_updated_at=datetime.now().strftime("%d %B %Y %H:%M:%S"),
            created_by_user_id=user_id
        )
        
        return {"message": "Evaluation saved successfully", "asset_name": asset_name}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error saving evaluation {evaluation_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error saving evaluation: {str(e)}")

def format_student_report(evaluation, student_index: int):
    """Format evaluation data into a readable report for a single student"""
    result = evaluation["evaluation_result"]
    students = result.get("students", [])
    stored_filenames = evaluation.get("answer_sheet_filenames", [])
    
    if student_index < 0 or student_index >= len(students):
        return None
    
    student = students[student_index]
    
    # Use stored filename if available, otherwise fall back to student_name or file_id
    original_filename = "Unknown"
    if student_index < len(stored_filenames):
        original_filename = stored_filenames[student_index]
    elif student.get('student_name'):
        original_filename = student.get('student_name')
    elif student.get('file_id'):
        original_filename = f"File_{student.get('file_id')}"
    
    report = f"# Student Report\n\n"
    report += f"**Student:** {student_index + 1}\n"
    report += f"**File:** {original_filename}\n"
    report += f"**Total Score:** {student.get('total_score', 0)}/{student.get('max_total_score', 0)}\n"
    report += f"**Status:** {student.get('status', 'completed')}\n"
    report += f"**Evaluation Date:** {datetime.now().strftime('%d %B %Y')}\n\n"
    
    answers = student.get('answers', [])
    for j, answer in enumerate(answers, 1):
        report += f"## Question {j}\n"
        report += f"**Question:** {answer.get('question_text', 'N/A')}\n"
        report += f"**Student Answer:** {answer.get('student_answer', 'N/A')}\n"
        report += f"**Score:** {answer.get('score', 0)}/{answer.get('max_score', 0)}\n"
        report += f"**Feedback:** {answer.get('feedback', 'N/A')}\n\n"
    
    return report

def format_evaluation_csv(evaluation):
    """Format evaluation data into CSV format matching the template structure"""
    result = evaluation["evaluation_result"]
    students = result.get("students", [])
    stored_filenames = evaluation.get("answer_sheet_filenames", [])
    
    # Determine the maximum number of questions across all students
    max_questions = 0
    for student in students:
        answers = student.get('answers', [])
        if len(answers) > max_questions:
            max_questions = len(answers)
    
    # Build CSV header
    header = ["email"]
    for i in range(1, max_questions + 1):
        header.extend([f"Q{i}_score", f"Q{i}_feedback"])
    header.extend(["total_marks", "max_score", "overall_feedback"])
    
    # Build CSV rows
    rows = []
    for idx, student in enumerate(students):
        # Use email from student object if available, otherwise fallback to filename
        email = student.get('email', '')
        if not email:
            if idx < len(stored_filenames):
                filename = stored_filenames[idx]
                # Remove .pdf extension from filename
                email = filename.replace('.pdf', '') if filename.endswith('.pdf') else filename
            elif student.get('student_name'):
                email = student.get('student_name')
            else:
                email = f"student_{idx + 1}"
        
        row = [email]
        
        # Add question scores and feedback
        answers = student.get('answers', [])
        for i in range(max_questions):
            if i < len(answers):
                answer = answers[i]
                score = answer.get('score', '')
                feedback = answer.get('feedback', '')
                # Clean feedback text - remove newlines and quotes
                if feedback:
                    feedback = str(feedback).replace('\n', ' ').replace('\r', ' ').replace('"', '""')
                row.extend([score if score != '' else '', feedback])
            else:
                # Empty cells for questions this student doesn't have
                row.extend(['', ''])
        
        # Add total marks, max score, and overall feedback
        total_score = student.get('total_score', 0)
        max_total_score = student.get('max_total_score', 0)
        row.extend([total_score, max_total_score, ''])
        
        rows.append(row)
    
    # Create CSV in memory
    output = io.StringIO()
    writer = csv.writer(output, quoting=csv.QUOTE_MINIMAL)
    writer.writerow(header)
    writer.writerows(rows)
    
    return output.getvalue()

@router.get("/evaluation/report/{evaluation_id}/student/{student_index}")
def get_student_report(evaluation_id: str, student_index: int, user_id: str = Depends(verify_token)):
    """Get evaluation report for a specific student by index (0-based)"""
    try:
        evaluation = get_evaluation_by_evaluation_id(evaluation_id)
        if not evaluation:
            raise HTTPException(status_code=404, detail="Evaluation not found")
        if not evaluation.get("evaluation_result"):
            raise HTTPException(status_code=400, detail="Evaluation not yet completed")
        
        result = evaluation["evaluation_result"]
        students = result.get("students", [])
        
        if student_index < 0 or student_index >= len(students):
            raise HTTPException(
                status_code=404, 
                detail=f"Student index {student_index} not found. Valid range: 0-{len(students)-1}"
            )
        
        report = format_student_report(evaluation, student_index)
        if report is None:
            raise HTTPException(status_code=404, detail="Student not found")
        
        return {
            "report": report,
            "student_index": student_index,
            "total_students": len(students)
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting student report for {evaluation_id}, student {student_index}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error getting student report: {str(e)}")

@router.get("/evaluation/report/{evaluation_id}/csv")
def download_evaluation_csv(evaluation_id: str, user_id: str = Depends(verify_token)):
    """Download evaluation report as CSV file"""
    try:
        evaluation = get_evaluation_by_evaluation_id(evaluation_id)
        if not evaluation:
            raise HTTPException(status_code=404, detail="Evaluation not found")
        if not evaluation.get("evaluation_result"):
            raise HTTPException(status_code=400, detail="Evaluation not yet completed")
        
        # Generate CSV content
        csv_content = format_evaluation_csv(evaluation)
        
        # Create a streaming response with CSV content
        output = io.BytesIO(csv_content.encode('utf-8'))
        
        # Generate filename with timestamp
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"evaluation_report_{evaluation_id[:8]}_{timestamp}.csv"
        
        return StreamingResponse(
            io.BytesIO(csv_content.encode('utf-8')),
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error downloading CSV report for {evaluation_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error downloading CSV report: {str(e)}")