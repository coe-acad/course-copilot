from fastapi import APIRouter, Request, UploadFile, Depends
from pydantic import BaseModel
from fastapi import Form, File, HTTPException
from typing import List, Optional
import logging
import json
from uuid import uuid4
from ..utils.verify_token import verify_token
from app.services.mongo import create_evaluation, get_evaluation_by_evaluation_id, update_evaluation, update_evaluation_with_result, update_student_result, update_student_status, update_question_score_feedback
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

class UpdateStudentResultRequest(BaseModel):
    question_scores: List[int]
    feedback: str

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
def extracting_answersheets_and_mark_scheme(evaluation_id: str, user_id: str):
    try:
        evaluation = get_evaluation_by_evaluation_id(evaluation_id)
        if not evaluation:
            raise HTTPException(status_code=404, detail=f"Evaluation {evaluation_id} not found")
        
        answer_sheet_file_ids = evaluation["answer_sheet_file_ids"]
        logger.info(f"Found {len(answer_sheet_file_ids)} answer sheets for evaluation {evaluation_id}")
        
        logger.info(f"Starting individual evaluation for {evaluation_id} with {len(answer_sheet_file_ids)} answer sheets")
        
        # Perform individual evaluation (processes each file separately)
        extracted_mark_scheme = extract_mark_scheme(evaluation_id, user_id, evaluation["mark_scheme_file_id"])
        extracted_answer_sheets = extract_answer_sheets_batched(evaluation_id, user_id, answer_sheet_file_ids)
        
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

@router.put("/evaluation/update-student-result")
def update_student_result_endpoint(
    evaluation_id: str = Form(...),
    student_index: int = Form(...),
    question_scores: str = Form(...),  # Will be JSON string
    feedback: str = Form(...),
    user_id: str = Depends(verify_token)
):
    """Update individual student result with manual marks and feedback"""
    try:
        # Parse question_scores from JSON string
        import json
        try:
            question_scores_list = json.loads(question_scores)
            if not isinstance(question_scores_list, list):
                raise ValueError("question_scores must be a list")
        except (json.JSONDecodeError, ValueError) as e:
            raise HTTPException(status_code=400, detail=f"Invalid question_scores format: {str(e)}")
        
        # Validate inputs
        if not question_scores_list or len(question_scores_list) == 0:
            raise HTTPException(status_code=400, detail="Question scores are required")
        
        # Validate that all scores are integers
        for i, score in enumerate(question_scores_list):
            if not isinstance(score, int) or score < 0:
                raise HTTPException(status_code=400, detail=f"Question score at index {i} must be a non-negative integer")
        
        # Calculate total score
        total_score = sum(question_scores_list)
        
        # Update the student result with status "modified"
        success = update_student_result(evaluation_id, student_index, question_scores_list, feedback, total_score, "modified")
        
        if success:
            logger.info(f"Successfully updated student {student_index} result for evaluation {evaluation_id}")
            return {"message": "Student result updated successfully", "total_score": total_score, "status": "modified"}
        else:
            raise HTTPException(status_code=404, detail="Student result not found or could not be updated")
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating student result for evaluation {evaluation_id}, student {student_index}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error updating student result: {str(e)}")

@router.put("/evaluation/update-student-status")
def update_student_status_endpoint(
    evaluation_id: str = Form(...),
    student_index: int = Form(...),
    status: str = Form(...),
    user_id: str = Depends(verify_token)
):
    """Update student status (e.g., from 'unopened' to 'opened')"""
    try:
        # Validate status
        valid_statuses = ["unopened", "opened", "modified"]
        if status not in valid_statuses:
            raise HTTPException(status_code=400, detail=f"Invalid status. Must be one of: {', '.join(valid_statuses)}")
        
        # Update the student status
        success = update_student_status(evaluation_id, student_index, status)
        
        if success:
            logger.info(f"Successfully updated student {student_index} status to '{status}' for evaluation {evaluation_id}")
            return {"message": "Student status updated successfully", "status": status}
        else:
            raise HTTPException(status_code=404, detail="Student result not found or could not be updated")
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating student status for evaluation {evaluation_id}, student {student_index}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error updating student status: {str(e)}")

@router.get("/evaluation/student-details")
def get_student_evaluation_details_endpoint(
    evaluation_id: str,
    student_index: int,
    user_id: str = Depends(verify_token)
):
    """Get detailed evaluation data for a specific student"""
    try:
        # Validate inputs
        if student_index < 0:
            raise HTTPException(status_code=400, detail="Student index must be non-negative")
        
        # Get the student evaluation details
        student_data = get_student_evaluation_details(evaluation_id, student_index)
        
        if not student_data:
            raise HTTPException(status_code=404, detail="Student evaluation details not found")
        
        logger.info(f"Successfully retrieved student {student_index} details for evaluation {evaluation_id}")
        return student_data
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting student details for evaluation {evaluation_id}, student {student_index}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error getting student details: {str(e)}")

def transform_evaluation_result_for_frontend(evaluation_result: dict) -> dict:
    """
    Transform the backend evaluation result structure to match frontend expectations.
    
    Backend format:
    {
        "students": [
            {
                "file_id": "uuid",
                "answers": [
                    {
                        "question_number": "1",
                        "question_text": "What is Python?",
                        "student_answer": "A programming language",
                        "correct_answer": "A high-level programming language",
                        "score": 2,
                        "max_score": 4,
                        "feedback": "Good but incomplete"
                    }
                ],
                "total_score": 15,
                "max_total_score": 20
            }
        ]
    }
    
    Frontend format:
    {
        "students": [
            {
                "question_scores": [2, 3, 0, 4, 1],
                "max_scores": [4, 4, 4, 5, 5],
                "questions": ["Question 1", "Question 2", ...],
                "answers": ["Answer 1", "Answer 2", ...],
                "ai_feedback": ["Feedback 1", "Feedback 2", ...],
                "total_score": 15,
                "max_total_score": 20,
                "status": "unopened"
            }
        ]
    }
    """
    if "students" not in evaluation_result:
        return evaluation_result
    
    transformed_students = []
    
    for student in evaluation_result["students"]:
        if "answers" not in student:
            continue
            
        # Extract data from answers array
        question_scores = []
        max_scores = []
        questions = []
        answers = []
        ai_feedback = []
        
        for answer in student["answers"]:
            question_scores.append(answer.get("score", 0))
            max_scores.append(answer.get("max_score", 0))
            questions.append(answer.get("question_text", ""))
            answers.append(answer.get("student_answer", ""))
            ai_feedback.append(answer.get("feedback", ""))
        
        # Create transformed student object with default status
        transformed_student = {
            "question_scores": question_scores,
            "max_scores": max_scores,
            "questions": questions,
            "answers": answers,
            "ai_feedback": ai_feedback,
            "total_score": student.get("total_score", sum(question_scores)),
            "max_total_score": student.get("max_total_score", sum(max_scores)),
            "status": student.get("status", "unopened")  # Default status
        }
        
        transformed_students.append(transformed_student)
    
    return {
        "evaluation_id": evaluation_result.get("evaluation_id", ""),
        "students": transformed_students
    }

@router.put("/evaluation/edit-results")
def edit_results(request: EditresultRequest, user_id: str = Depends(verify_token)):
    """Edit specific question score and feedback for a student"""
    try:
        # Validate inputs
        if request.score < 0:
            raise HTTPException(status_code=400, detail="Score cannot be negative")
        
        if not request.feedback or request.feedback.strip() == "":
            raise HTTPException(status_code=400, detail="Feedback cannot be empty")
        
        # Update the question score and feedback
        success = update_question_score_feedback(
            request.evaluation_id, 
            request.file_id, 
            request.question_number, 
            request.score, 
            request.feedback.strip()
        )
        
        if success:
            # Update evaluation status to indicate it has been modified
            update_evaluation(request.evaluation_id, {"status": "updated"})
            logger.info(f"Successfully updated question {request.question_number} for file {request.file_id} in evaluation {request.evaluation_id}")
            return {"message": "Results updated successfully"}
        else:
            raise HTTPException(status_code=404, detail="Question or student not found")
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating results for evaluation {request.evaluation_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error updating results: {str(e)}")

