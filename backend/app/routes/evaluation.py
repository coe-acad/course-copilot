from fastapi import APIRouter, Request, UploadFile, Depends
from pydantic import BaseModel
from fastapi import Form, File, HTTPException
from typing import List, Optional
import logging
import json
from uuid import uuid4
from flask import request
from ..utils.verify_token import verify_token
from app.services.mongo import create_evaluation, get_evaluation_by_evaluation_id, update_evaluation_with_result, update_question_score_feedback, update_evaluation, db
from app.services.openai_service import upload_mark_scheme_file, upload_answer_sheet_files, create_evaluation_assistant_and_vector_store, evaluate_files_all_in_one, extract_answer_sheets_batched, extract_mark_scheme, mark_scheme_check
from concurrent.futures import ThreadPoolExecutor

logger = logging.getLogger(__name__)
router = APIRouter()

# Endpoints will be implemented here later. 
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
    evaluation_id = str(uuid4())
    eval_info = create_evaluation_assistant_and_vector_store(evaluation_id)
    evaluation_assistant_id = eval_info[0]
    vector_store_id = eval_info[1]

    mark_scheme_file_id = upload_mark_scheme_file(mark_scheme, vector_store_id)

    mark_scheme_check_result = mark_scheme_check(evaluation_assistant_id, user_id, mark_scheme_file_id)
    logger.info(f"Mark scheme check result: {mark_scheme_check_result}")
    
    create_evaluation(
        evaluation_id=evaluation_id,
        course_id=course_id,
        evaluation_assistant_id=evaluation_assistant_id,
        vector_store_id=vector_store_id,
        mark_scheme_file_id=mark_scheme_file_id,
        answer_sheet_file_ids=[]
    )
    
    return {"evaluation_id": evaluation_id, "mark_scheme_file_id": mark_scheme_file_id}

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
        
        vector_store_id = evaluation["vector_store_id"]
        
        # Upload answer sheets
        answer_sheet_file_ids = upload_answer_sheet_files(answer_sheets, vector_store_id)
        
        # Update evaluation record
        update_evaluation(evaluation_id, {"answer_sheet_file_ids": answer_sheet_file_ids})
        logger.info(f"Successfully uploaded {len(answer_sheet_file_ids)} answer sheets for evaluation {evaluation_id}")

        return {"evaluation_id": evaluation_id, "answer_sheet_file_ids": answer_sheet_file_ids}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error uploading answer sheets for evaluation {evaluation_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error uploading answer sheets: {str(e)}")

@router.get("/evaluation/evaluate-files", response_model=EvaluationResponse)
def evaluate_files(evaluation_id: str, user_id: str):
    try:
        evaluation = get_evaluation_by_evaluation_id(evaluation_id)
        if not evaluation:
            raise HTTPException(status_code=404, detail=f"Evaluation {evaluation_id} not found")
        
        answer_sheet_file_ids = evaluation["answer_sheet_file_ids"]
        logger.info(f"Found {len(answer_sheet_file_ids)} answer sheets for evaluation {evaluation_id}")
        
        logger.info(f"Starting individual evaluation for {evaluation_id} with {len(answer_sheet_file_ids)} answer sheets")
        
        # Perform individual evaluation (processes each file separately)
        with ThreadPoolExecutor(max_workers=2) as executor:
            fut_ms = executor.submit(extract_mark_scheme, evaluation_id, user_id, evaluation["mark_scheme_file_id"])
            fut_as = executor.submit(extract_answer_sheets_batched, evaluation_id, user_id, answer_sheet_file_ids)
            extracted_mark_scheme = fut_ms.result()
            extracted_answer_sheets = fut_as.result()
        
        evaluation_result = evaluate_files_all_in_one(evaluation_id, user_id, extracted_mark_scheme, extracted_answer_sheets)
        
        # Transform the evaluation result to match frontend expectations
        transformed_result = transform_evaluation_result_for_frontend(evaluation_result)
        
        update_evaluation_with_result(evaluation_id, transformed_result) 

        logger.info(f"Successfully completed and saved evaluation {evaluation_id}")
        return {"evaluation_id": evaluation_id, "evaluation_result": transformed_result}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error extracting answer sheets for evaluation {evaluation_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error extracting answer sheets: {str(e)}")


@router.put("/evaluation/edit-results")
def edit_results(request: EditresultRequest, user_id: str):
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

