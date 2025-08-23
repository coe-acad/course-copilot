from re import L
from fastapi import APIRouter, Request, UploadFile, Depends
from pydantic import BaseModel
from fastapi import Form, File, HTTPException
from typing import List, Optional
import logging
import json
from uuid import uuid4
from ..utils.verify_token import verify_token
from app.services.mongo import create_evaluation, get_evaluation_by_evaluation_id, update_evaluation, update_evaluation_with_result
from app.services.openai_service import upload_mark_scheme_file, upload_answer_sheet_files, create_evaluation_assistant_and_vector_store, evaluate_files_all_in_one, extract_answer_sheets_batched, extract_mark_scheme, mark_scheme_check

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
def extracting_answersheets_and_mark_scheme(evaluation_id: str, user_id: str):
    try:
        evaluation = get_evaluation_by_evaluation_id(evaluation_id)
        if not evaluation:
            raise HTTPException(status_code=404, detail=f"Evaluation {evaluation_id} not found")
        
        answer_sheet_file_ids = evaluation["answer_sheet_file_ids"]
        
        logger.info(f"Starting individual evaluation for {evaluation_id} with {len(answer_sheet_file_ids)} answer sheets")
        
        # Perform individual evaluation (processes each file separately)
        extracted_mark_scheme = extract_mark_scheme(evaluation_id, user_id, evaluation["mark_scheme_file_id"])
        extracted_answer_sheets = extract_answer_sheets_batched(evaluation_id, user_id, answer_sheet_file_ids)
        
        evaluation_result = evaluate_files_all_in_one(evaluation_id, user_id, extracted_mark_scheme, extracted_answer_sheets)
        update_evaluation_with_result(evaluation_id, evaluation_result) 

        logger.info(f"Successfully completed and saved evaluation {evaluation_id}")
        return {"evaluation_id": evaluation_id, "evaluation_result": evaluation_result}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error extracting answer sheets for evaluation {evaluation_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error extracting answer sheets: {str(e)}")


