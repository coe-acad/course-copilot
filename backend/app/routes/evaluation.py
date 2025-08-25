from fastapi import APIRouter, Request, UploadFile, Depends
from pydantic import BaseModel
from fastapi import Form, File, HTTPException
from typing import List, Optional
import logging
import json
from uuid import uuid4
from ..utils.verify_token import verify_token
from app.services.openai_service import upload_evaluation_files
from app.services.mongo import create_evaluation, get_evaluation_by_evaluation_id, update_evaluation, get_evaluation_schemes_by_course_id, create_evaluation_scheme
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

class EvaluationSchemeResponse(BaseModel):
    scheme_id: str
    scheme_name: str
    scheme_description: str
    created_at: str
    file_id: str

@router.get("/evaluation/schemes/{course_id}")
def get_evaluation_schemes(course_id: str, user_id: str = Depends(verify_token)):
    """Get all evaluation schemes (mark schemes) for a course"""
    try:
        schemes = get_evaluation_schemes_by_course_id(course_id)
        return {"schemes": schemes}
    except Exception as e:
        logger.error(f"Error getting evaluation schemes for course {course_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to get evaluation schemes: {str(e)}")

@router.post("/evaluation/upload-scheme")
def upload_evaluation_scheme_endpoint(
    course_id: str = Form(...), 
    scheme_name: str = Form(...),
    scheme_description: str = Form(...),
    mark_scheme: UploadFile = File(...),
    user_id: str = Depends(verify_token)
):
    """Upload a new evaluation scheme (mark scheme) for a course"""
    try:
        logger.info(f"Uploading evaluation scheme '{scheme_name}' for course {course_id}")
        
        # Create evaluation assistant and vector store for this scheme
        evaluation_id = str(uuid4())
        eval_info = create_evaluation_assistant_and_vector_store(evaluation_id)
        evaluation_assistant_id = eval_info[0]
        vector_store_id = eval_info[1]
        
        # Upload the mark scheme file
        mark_info = upload_evaluation_files(user_id, course_id, vector_store_id, mark_scheme, [])
        
        # Create evaluation scheme record
        scheme_id = create_evaluation_scheme(
            course_id=course_id,
            scheme_name=scheme_name,
            scheme_description=scheme_description,
            evaluation_assistant_id=evaluation_assistant_id,
            vector_store_id=vector_store_id,
            mark_scheme_file_id=mark_info["mark_scheme"]
        )
        
        logger.info(f"Created evaluation scheme {scheme_id} for course {course_id}")
        return {"scheme_id": scheme_id, "message": "Evaluation scheme created successfully"}
        
    except Exception as e:
        logger.error(f"Error creating evaluation scheme: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to create evaluation scheme: {str(e)}")

@router.post("/evaluation/upload-files")
def upload_files(courseId: str = Form(...), user_id: str = Depends(verify_token), mark_scheme: UploadFile = File(None), answer_sheets: List[UploadFile] = File(None), scheme_id: str = Form(None)):
    try:
        logger.info(f"Starting file upload for course {courseId} by user {user_id}")
        
        if scheme_id:
            # Use existing evaluation scheme
            logger.info(f"Using existing evaluation scheme: {scheme_id}")
            # TODO: Get scheme details and use existing assistant/vector store
            # For now, create new evaluation
            evaluation_id = str(uuid4())
            eval_info = create_evaluation_assistant_and_vector_store(evaluation_id)
            evaluation_assistant_id = eval_info[0]
            vector_store_id = eval_info[1]
            mark_scheme_file_id = None  # Using existing scheme
        else:
            # Create new evaluation scheme
            if not mark_scheme:
                raise HTTPException(status_code=400, detail="Mark scheme is required when not using existing scheme")
            
            evaluation_id = str(uuid4())
            eval_info = create_evaluation_assistant_and_vector_store(evaluation_id)
            evaluation_assistant_id = eval_info[0]
            vector_store_id = eval_info[1]
            
            # Upload mark scheme
            mark_info = upload_evaluation_files(user_id, courseId, vector_store_id, mark_scheme, [])
            mark_scheme_file_id = mark_info["mark_scheme"]
        
        # Upload answer sheets
        if not answer_sheets or len(answer_sheets) == 0:
            raise HTTPException(status_code=400, detail="At least one answer sheet is required")
        
        answer_sheet_info = upload_evaluation_files(user_id, courseId, vector_store_id, None, answer_sheets)
        
        # Create evaluation record in MongoDB
        create_evaluation(
            evaluation_id=evaluation_id,
            course_id=courseId, 
            evaluation_assistant_id=evaluation_assistant_id, 
            vector_store_id=vector_store_id,
            mark_scheme_file_id=mark_scheme_file_id if not scheme_id else None, 
            answer_sheet_file_ids=answer_sheet_info["answer_sheet"]
        )
        logger.info(f"Evaluation record created in MongoDB: {evaluation_id}")
        
        return {"evaluation_id": evaluation_id}
        
    except Exception as e:
        logger.error(f"Error in upload_files: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")

@router.get("/evaluation/evaluate-files", response_model=EvaluationResponse)
def evaluate_files_endpoint(evaluation_id: str, user_id: str):
    try:
        logger.info(f"Starting evaluation for {evaluation_id} by user {user_id}")
        
        # Get evaluation record
        evaluation = get_evaluation_by_evaluation_id(evaluation_id)
        if not evaluation:
            logger.error(f"Evaluation {evaluation_id} not found")
            raise HTTPException(status_code=404, detail=f"Evaluation {evaluation_id} not found")
        
        answer_sheet_file_ids = evaluation["answer_sheet_file_ids"]
        logger.info(f"Found {len(answer_sheet_file_ids)} answer sheets for evaluation {evaluation_id}")
        
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


