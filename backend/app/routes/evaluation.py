from fastapi import APIRouter, Request, UploadFile, Depends
from pydantic import BaseModel
from fastapi import Form, File, HTTPException
from typing import List, Optional
import logging
import json
from uuid import uuid4
from ..utils.verify_token import verify_token
from app.services.openai_service import upload_evaluation_files
from app.services.mongo import create_evaluation, get_evaluation_by_evaluation_id, update_evaluation
from app.services.openai_service import evaluate_files_individually, create_evaluation_assistant_and_vector_store

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

@router.post("/evaluation/upload-files")
def upload_files(course_id: str = Form(...), user_id: str = Depends(verify_token), mark_scheme: UploadFile = File(...), answer_sheets: List[UploadFile] = File(None)):
    evaluation_id = str(uuid4())
    eval_info= create_evaluation_assistant_and_vector_store(evaluation_id)
    evaluation_assistant_id = eval_info[0]
    vector_store_id = eval_info[1]
    mark_info = upload_evaluation_files(user_id, course_id, vector_store_id, mark_scheme, answer_sheets)
    # Create evaluation record in MongoDB
    create_evaluation(
        evaluation_id=evaluation_id,
        course_id=course_id, 
        evaluation_assistant_id=evaluation_assistant_id, 
        vector_store_id=vector_store_id,
        mark_scheme_file_id=mark_info["mark_scheme"], 
        answer_sheet_file_ids=mark_info["answer_sheet"]
    )
    print(evaluation_id)
    return {"evaluation_id": evaluation_id}

@router.get("/evaluation/evaluate-files", response_model=EvaluationResponse)
def evaluate_files_endpoint(evaluation_id: str, user_id: str):
    try:
        # Get evaluation record
        evaluation = get_evaluation_by_evaluation_id(evaluation_id)
        if not evaluation:
            raise HTTPException(status_code=404, detail=f"Evaluation {evaluation_id} not found")
        
        answer_sheet_file_ids = evaluation["answer_sheet_file_ids"]
        
        logger.info(f"Starting individual evaluation for {evaluation_id} with {len(answer_sheet_file_ids)} answer sheets")
        
        # Perform individual evaluation (processes each file separately)
        evaluation_result = evaluate_files_individually(evaluation_id, user_id, answer_sheet_file_ids)
        
        # Save to MongoDB
        update_evaluation(evaluation_id, evaluation_result)
        
        logger.info(f"Successfully completed and saved evaluation {evaluation_id}")
        return EvaluationResponse(evaluation_id=evaluation_id, evaluation_result=evaluation_result)
        
    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        logger.error(f"Error processing evaluation {evaluation_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error processing evaluation: {str(e)}")


