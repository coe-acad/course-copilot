from fastapi import APIRouter, Request, UploadFile, Depends
from pydantic import BaseModel
from fastapi import Form, File, HTTPException
from typing import List, Optional
import logging
import json
from uuid import uuid4
import asyncio
from datetime import datetime
from flask import request
from ..utils.verify_token import verify_token
from app.services.mongo import create_evaluation, get_evaluation_by_evaluation_id, update_evaluation_with_result, update_question_score_feedback, update_evaluation, get_evaluations_by_course_id, create_asset, db
from app.services.openai_service import upload_mark_scheme_file, upload_answer_sheet_files, create_evaluation_assistant_and_vector_store, evaluate_files_all_in_one, extract_answer_sheets_batched, extract_mark_scheme, mark_scheme_check
from concurrent.futures import ThreadPoolExecutor

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


def _process_evaluation(evaluation_id, user_id, evaluation):
    """Process evaluation in background"""
    with ThreadPoolExecutor(max_workers=2) as executor:
        fut_ms = executor.submit(extract_mark_scheme, evaluation_id, user_id, evaluation["mark_scheme_file_id"])
        fut_as = executor.submit(extract_answer_sheets_batched, evaluation_id, user_id, evaluation["answer_sheet_file_ids"])
        extracted_mark_scheme = fut_ms.result()
        extracted_answer_sheets = fut_as.result()
    
    evaluation_result = evaluate_files_all_in_one(evaluation_id, user_id, extracted_mark_scheme, extracted_answer_sheets)
    
    # Always verify and potentially recalculate scores for each student
    for student in evaluation_result.get("students", []):
        answers = student.get("answers", [])
        
        # Calculate what the total should be based on individual question scores
        calculated_total = sum((a.get("score") or 0) for a in answers if a.get("score") is not None)
        calculated_max = sum((a.get("max_score") or 0) for a in answers)
        
        # Log the current vs calculated scores
        current_total = student.get("total_score", 0)
        current_max = student.get("max_total_score", 0)
        
        logger.info(f"Student {student.get('file_id', 'unknown')}: AI says {current_total}/{current_max}, calculated {calculated_total}/{calculated_max}")
        
        # Always use the calculated scores to ensure accuracy
        student["total_score"] = calculated_total
        student["max_total_score"] = calculated_max

    # Calculate and save aggregate totals across all students
    overall_total = sum(s.get("total_score", 0) for s in evaluation_result.get("students", []))
    overall_max = sum(s.get("max_total_score", 0) for s in evaluation_result.get("students", []))
    
    # Add overall totals to the evaluation result
    evaluation_result["total_score"] = overall_total
    evaluation_result["max_total_score"] = overall_max
    
    logger.info(f"Evaluation completed - {len(evaluation_result.get('students', []))} students, aggregate: {overall_total}/{overall_max}")
    
    # Store the final evaluation result (now includes overall totals)
    update_evaluation_with_result(evaluation_id, evaluation_result)

@router.post("/evaluation/upload-mark-scheme")
def upload_mark_scheme(course_id: str = Form(...), user_id: str = Depends(verify_token), mark_scheme: UploadFile = File(...)):
    evaluation_id = str(uuid4())
    eval_info = create_evaluation_assistant_and_vector_store(evaluation_id)
    evaluation_assistant_id = eval_info[0]
    vector_store_id = eval_info[1]

    mark_scheme_file_id = upload_mark_scheme_file(mark_scheme, vector_store_id)

    mark_scheme_check_result = mark_scheme_check(evaluation_assistant_id, user_id, mark_scheme_file_id)
    logger.info(f"Mark scheme check result: {mark_scheme_check_result}")
    
    # Check if mark scheme format is correct
    if "not in the correct format" in mark_scheme_check_result:
        raise HTTPException(status_code=400, detail=mark_scheme_check_result)
    
    create_evaluation(
        evaluation_id=evaluation_id,
        course_id=course_id,
        evaluation_assistant_id=evaluation_assistant_id,
        vector_store_id=vector_store_id,
        mark_scheme_file_id=mark_scheme_file_id,
        answer_sheet_file_ids=[],
        answer_sheet_filenames=[]
    )
    
    # Verify the evaluation was created successfully
    created_evaluation = get_evaluation_by_evaluation_id(evaluation_id)
    if not created_evaluation:
        logger.error(f"Failed to create evaluation {evaluation_id} - not found after creation")
        raise HTTPException(status_code=500, detail="Failed to create evaluation record")
    
    logger.info(f"Successfully created evaluation {evaluation_id} with fields: {list(created_evaluation.keys())}")
    
    return {"evaluation_id": evaluation_id, "mark_scheme_file_id": mark_scheme_file_id, "message": mark_scheme_check_result}

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
        if not evaluation.get("mark_scheme_file_id"):
            raise HTTPException(status_code=400, detail="Mark scheme must be uploaded first")
        
        # Upload answer sheets
        answer_sheet_file_ids, answer_sheet_filenames = upload_answer_sheet_files(answer_sheets)
        
        # Update evaluation record
        update_evaluation(evaluation_id, {
            "answer_sheet_file_ids": answer_sheet_file_ids,
            "answer_sheet_filenames": answer_sheet_filenames
        })
        logger.info(f"Successfully uploaded {len(answer_sheet_file_ids)} answer sheets for evaluation {evaluation_id}")

        return {"evaluation_id": evaluation_id, "answer_sheet_file_ids": answer_sheet_file_ids, "answer_sheet_filenames": answer_sheet_filenames}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error uploading answer sheets for evaluation {evaluation_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error uploading answer sheets: {str(e)}")

@router.get("/evaluation/evaluate-files", response_model=EvaluationResponse)
async def evaluate_files(evaluation_id: str, user_id: str):
    try:
        evaluation = get_evaluation_by_evaluation_id(evaluation_id)
        if not evaluation:
            raise HTTPException(status_code=404, detail=f"Evaluation {evaluation_id} not found")
        
        answer_sheet_file_ids = evaluation["answer_sheet_file_ids"]
        # Multiple files = background processing to avoid Cloudflare timeout
        if len(answer_sheet_file_ids) > 1:
            asyncio.create_task(asyncio.to_thread(_process_evaluation, evaluation_id, user_id, evaluation))
            return {"evaluation_id": evaluation_id, "evaluation_result": {"status": "processing"}}
        
        # Single file = process normally
        with ThreadPoolExecutor(max_workers=2) as executor:
            fut_ms = executor.submit(extract_mark_scheme, evaluation_id, user_id, evaluation["mark_scheme_file_id"])
            fut_as = executor.submit(extract_answer_sheets_batched, evaluation_id, user_id, answer_sheet_file_ids)
            extracted_mark_scheme = fut_ms.result()
            extracted_answer_sheets = fut_as.result()
        
        evaluation_result = evaluate_files_all_in_one(evaluation_id, user_id, extracted_mark_scheme, extracted_answer_sheets)

        # Always verify and potentially recalculate scores for each student
        for student in evaluation_result.get("students", []):
            answers = student.get("answers", [])
            
            # Calculate what the total should be based on individual question scores
            calculated_total = sum((a.get("score") or 0) for a in answers if a.get("score") is not None)
            calculated_max = sum((a.get("max_score") or 0) for a in answers)
            
            # Log the current vs calculated scores
            current_total = student.get("total_score", 0)
            current_max = student.get("max_total_score", 0)
            
            logger.info(f"Student {student.get('file_id', 'unknown')}: AI says {current_total}/{current_max}, calculated {calculated_total}/{calculated_max}")
            
            # Always use the calculated scores to ensure accuracy
            student["total_score"] = calculated_total
            student["max_total_score"] = calculated_max

        # Calculate and save aggregate totals across all students
        overall_total = sum(s.get("total_score", 0) for s in evaluation_result.get("students", []))
        overall_max = sum(s.get("max_total_score", 0) for s in evaluation_result.get("students", []))
        
        # Add overall totals to the evaluation result
        evaluation_result["total_score"] = overall_total
        evaluation_result["max_total_score"] = overall_max
        
        logger.info(f"Evaluation completed - {len(evaluation_result.get('students', []))} students, aggregate: {overall_total}/{overall_max}")
        
        # Store the final evaluation result (now includes overall totals)
        update_evaluation_with_result(evaluation_id, evaluation_result)

        return {"evaluation_id": evaluation_id, "evaluation_result": evaluation_result}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error extracting answer sheets for evaluation {evaluation_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error extracting answer sheets: {str(e)}")

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
        
        if "evaluation_result" in evaluation:
            logger.info(f"Evaluation {evaluation_id} has results, returning completed status")
            return {"status": "completed", "evaluation_result": evaluation["evaluation_result"]}
        else:
            logger.info(f"Evaluation {evaluation_id} exists but no evaluation_result yet, returning processing status")
            return {"status": "processing"}
            
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
        
        if "evaluation_result" not in evaluation:
            raise HTTPException(status_code=400, detail="Cannot save evaluation without results")
        
        # Create formatted evaluation report
        logger.info(f"Saving evaluation {evaluation_id}")
        report = format_evaluation_report(evaluation)
        
        # Save as asset
        create_asset(
            course_id=evaluation["course_id"],
            asset_name=asset_name,
            asset_category="evaluation",
            asset_type="evaluation-report",
            asset_content=report,
            asset_last_updated_by="You",
            asset_last_updated_at=datetime.now().strftime("%d %B %Y %H:%M:%S")
        )
        
        return {"message": "Evaluation saved successfully", "asset_name": asset_name}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error saving evaluation {evaluation_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error saving evaluation: {str(e)}")

def format_evaluation_report(evaluation):
    """Format evaluation data into a readable report"""
    result = evaluation["evaluation_result"]
    students = result.get("students", [])
    stored_filenames = evaluation.get("answer_sheet_filenames", [])
    logger.info(f"Stored filenames: {stored_filenames}")
    report = f"# Evaluation Report\n\n"
    report += f"**Total Students:** {len(students)}\n"
    report += f"**Evaluation Date:** {datetime.now().strftime('%d %B %Y')}\n\n"
    
    for i, student in enumerate(students, 1):
        # Use stored filename if available, otherwise fall back to student_name or file_id
        original_filename = "Unknown"
        if i <= len(stored_filenames):
            original_filename = stored_filenames[i-1]
        elif student.get('student_name'):
            original_filename = student.get('student_name')
        elif student.get('file_id'):
            original_filename = f"File_{student.get('file_id')}"
            
        report += f"## Student {i}\n"
        report += f"**File:** {original_filename}\n"
        report += f"**Total Score:** {student.get('total_score', 0)}/{student.get('max_total_score', 0)}\n"
        report += f"**Status:** {student.get('status', 'completed')}\n\n"
        
        answers = student.get('answers', [])
        for j, answer in enumerate(answers, 1):
            report += f"### Question {j}\n"
            report += f"**Question:** {answer.get('question_text', 'N/A')}\n"
            report += f"**Student Answer:** {answer.get('student_answer', 'N/A')}\n"
            report += f"**Score:** {answer.get('score', 0)}/{answer.get('max_score', 0)}\n"
            report += f"**Feedback:** {answer.get('feedback', 'N/A')}\n\n"
        
        report += "---\n\n"
    
    return report
