from fastapi import APIRouter, Request, UploadFile, Depends
from pydantic import BaseModel
from fastapi import Form, File, HTTPException
from typing import List, Optional
import logging
import json
from ..utils.verify_token import verify_token
from app.services.openai_service import upload_evaluation_files
from app.services.mongo import create_evaluation, get_course, get_evaluation_by_evaluation_id, update_evaluation
from app.services.openai_service import extract_mark_scheme, extract_answer_sheets, evaluate_files

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
    vector_store_id = get_course(course_id)["vector_store_id"]
    mark_info = upload_evaluation_files(user_id, course_id, vector_store_id, mark_scheme, answer_sheets)
    evaluation_id = create_evaluation(course_id, mark_info["mark_scheme"], mark_info["answer_sheet"])
    return {"evaluation_id": evaluation_id}

@router.get("/evaluation/extract-files")
def extract_files(evaluation_id: str, user_id: str):
    evaluation = get_evaluation_by_evaluation_id(evaluation_id)
    mark_scheme_file_id = evaluation["mark_scheme_file_id"]
    answer_sheet_file_ids = evaluation["answer_sheet_file_ids"]
    extracted_mark_scheme = extract_mark_scheme(evaluation_id, user_id, mark_scheme_file_id)
    extracted_answer_sheets = extract_answer_sheets(evaluation_id, user_id, answer_sheet_file_ids)
    return {"extracted_mark_scheme": extracted_mark_scheme, "extracted_answer_sheets": extracted_answer_sheets}

@router.get("/evaluation/evaluate-files", response_model=EvaluationResponse)
def evaluate_files_endpoint(evaluation_id: str, user_id: str):
    evaluation_result = evaluate_files(evaluation_id, user_id)
    update_evaluation(evaluation_id, evaluation_result)
    return EvaluationResponse(evaluation_id=evaluation_id, evaluation_result=evaluation_result)
