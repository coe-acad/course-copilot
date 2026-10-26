from fastapi import APIRouter, Request, UploadFile, Depends
from pydantic import BaseModel
from fastapi import Form, File, HTTPException
from fastapi.responses import StreamingResponse
from typing import List, Optional
import logging
from uuid import uuid4
import shutil
import asyncio
import threading
import time
from datetime import datetime
from flask import request
import os
from pathlib import Path
import csv
import re
import io
from collections import Counter
from ..utils.verify_token import verify_token
from app.services.mongo import (
    create_evaluation,
    get_evaluation_by_evaluation_id,
    update_evaluation_with_result,
    update_question_score_feedback,
    update_evaluation,
    get_evaluations_by_course_id,
    create_asset,
    db,
    get_email_by_user_id,
    create_ai_feedback,
    get_ai_feedback_by_evaluation_id,
    update_ai_feedback,
    get_user_display_name,
    get_asset_by_course_id_and_asset_name,
    get_asset_by_evaluation_id,
    get_course,
)
from app.services.openai_service import evaluate_files_all_in_one
from concurrent.futures import ThreadPoolExecutor, as_completed
from app.utils.eval_mail import send_eval_completion_email, send_eval_error_email
from app.utils.extraction_answersheet import extract_text_tables, split_into_qas
from app.utils.extraction_answersheet_mettl import (
    attach_mark_scheme_numbers, to_mark_scheme_numbering, restore_answer_sheet_order
)
from app.utils.extraction_markscheme import extract_text_from_mark_scheme
logger = logging.getLogger(__name__)
router = APIRouter()

# Grading batches: how many OpenAI calls run at once, and how often a failed batch is retried
MAX_PARALLEL_BATCHES = 5
BATCH_MAX_ATTEMPTS = 2           # first try + one retry
BATCH_RETRY_DELAYS = [15]        # seconds to wait before the retry

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


def _paper_total(mark_scheme_questions):
    """Maximum marks for a paper with "answer any N of ..." choice groups: the compulsory questions
    plus the N highest totals of each group. None when the paper has no choice groups or a question
    has no stated total."""
    if not any(q.get("choice") for q in mark_scheme_questions):
        return None
    total, groups = 0, {}
    for q in mark_scheme_questions:
        if q.get("max_score") is None:
            return None
        if q.get("choice"):
            groups.setdefault(q["choice"]["group"], (q["choice"]["pick"], []))[1].append(q["max_score"])
        else:
            total += q["max_score"]
    return total + sum(sum(sorted(maxes, reverse=True)[:pick]) for pick, maxes in groups.values())


def _add_skipped_questions(student, mark_scheme_questions):
    """List every mark scheme question for a sheet matched to the mark scheme: questions the student
    skipped are added as not attempted (0 marks), in paper order. Mettl sheets list unattempted
    questions themselves and are left as they are."""
    answers = student.get("answers", [])
    if not answers or any(a.get("section_question_number") is not None or not a.get("mark_scheme_question_number") for a in answers):
        return
    by_number = {str(a["mark_scheme_question_number"]): a for a in answers}
    ms_numbers = [str(q.get("questionnumber")) for q in mark_scheme_questions]
    if len(by_number) != len(answers) or not set(by_number) < set(ms_numbers):
        return  # nothing skipped, or answers that aren't one-to-one with mark scheme questions
    complete = [
        by_number.get(number) or {
            "mark_scheme_question_number": number,
            "question_text": None,
            "student_answer": None,
            "score": 0,
            "max_score": q.get("max_score"),
            "feedback": "Not attempted",
        }
        for number, q in zip(ms_numbers, mark_scheme_questions)
    ]
    # Positions are how answers are addressed when a teacher edits a score
    for position, a in enumerate(complete, 1):
        a["question_number"] = str(position)
    student["answers"] = complete


def _apply_totals(student, paper_total=None):
    """Set the student's total and max total. For an "answer any N of ..." choice group only the
    N best-scored answers count; the others are kept but marked counted=False. When given,
    paper_total is the max total, so every student of a choice paper is marked out of the same."""
    answers = student.get("answers", [])
    groups = {}
    for a in answers:
        a.pop("counted", None)
        if a.get("choice"):
            groups.setdefault(a["choice"]["group"], []).append(a)
    for group in groups.values():
        best_first = sorted(group, key=lambda a: a.get("score") or 0, reverse=True)
        for a in best_first[group[0]["choice"]["pick"]:]:
            a["counted"] = False
    counted = [a for a in answers if a.get("counted", True)]
    student["total_score"] = sum((a.get("score") or 0) for a in counted)
    student["max_total_score"] = (
        paper_total if paper_total is not None else sum((a.get("max_score") or 0) for a in counted)
    )


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
        
        # Create evaluation record
        create_evaluation(
            evaluation_id=evaluation_id,
            course_id=course_id,
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

async def _process_evaluation(evaluation_id: str, user_id: str):
    """Process evaluation in background using local file extraction with parallel workers"""
    try:
        # Check if evaluation is already completed
        evaluation = await asyncio.to_thread(get_evaluation_by_evaluation_id, evaluation_id)
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
        extracted_mark_scheme = await asyncio.to_thread(extract_text_from_mark_scheme, mark_scheme_path)
        question_count = len(extracted_mark_scheme.get('mark_scheme', []))
        logger.info(f"Mark scheme extracted: {extracted_mark_scheme}")
        
        # ERROR CHECK: Stop if mark scheme extraction failed
        if question_count == 0:
            error_msg = (
                "Failed to extract any questions from the mark scheme. "
                "Please ensure the mark scheme follows a supported format "
                "(e.g., 'Question number: 1', 'Question 1:', with 'Marking scheme' sections)."
            )
            logger.error(error_msg)
            raise Exception(error_msg)
        
        # Extract answer sheets
        logger.info(f"Extracting {len(answer_sheet_paths)} answer sheets")
        extracted_answer_sheets = []
        skipped_sheets = []  # sheets that could not be read, reported with the result
        for i, answer_sheet_path in enumerate(answer_sheet_paths):
            try:
                pages = await asyncio.to_thread(extract_text_tables, answer_sheet_path)

                # [EXTRACTION CHECK] Log the raw extracted text per page. Uses the uncropped line text:
                # page 'text' has table regions cut out, and Mettl reports draw every card as a table.
                raw_text_parts = []
                for p_idx, p in enumerate(pages):
                    page_text = "\n".join(ln.get("text", "") for ln in p.get("lines", []))
                    raw_text_parts.append(f"--- Page {p_idx + 1} ---\n{page_text}")
                logger.info(
                    f"\n{'=' * 60}\n[EXTRACTION CHECK] Answer sheet {i+1} RAW TEXT ({answer_sheet_path}):\n"
                    + "\n".join(raw_text_parts)
                    + f"\n{'=' * 60}"
                )

                extraction_result = await asyncio.to_thread(split_into_qas, pages, pdf_path=answer_sheet_path)
                
                extracted_email = extraction_result.get("email", None)
                qas_list = extraction_result.get("answers", [])
                # Find each question's mark scheme number by question text (question order can differ
                # from the mark scheme); falls back to sheet numbering when the match isn't confident.
                if any("question_text" in a for a in qas_list):
                    qas_list = attach_mark_scheme_numbers(qas_list, extracted_mark_scheme.get("mark_scheme", []))
                
                answer_sheet_data = {
                    "file_id": f"answer_sheet_{i+1}",
                    "filename": answer_sheet_filenames[i] if i < len(answer_sheet_filenames) else f"answer_sheet_{i+1}.pdf",
                    "student_name": extraction_result.get("student_name") or (answer_sheet_filenames[i].replace('.pdf', '').replace('_', ' ') if i < len(answer_sheet_filenames) else f"Student {i+1}"),
                    "email": extracted_email,
                    "answers": qas_list
                }
                extracted_answer_sheets.append(answer_sheet_data)
                logger.info(f"Answer sheet {i+1} extracted: {answer_sheet_data}")
            except Exception as extraction_error:
                logger.error(f"Failed to extract answer sheet {i+1}: {str(extraction_error)}")
                skipped_sheets.append({
                    "file_id": f"answer_sheet_{i+1}",
                    "filename": answer_sheet_filenames[i] if i < len(answer_sheet_filenames) else f"answer_sheet_{i+1}.pdf",
                    "error": str(extraction_error),
                })
                continue
        
        logger.info(f"Successfully extracted {len(extracted_answer_sheets)}/{len(answer_sheet_paths)} answer sheets")

        # A question the extractor missed is never sent for grading, so flag sheets whose question
        # count differs from the mark scheme (kept apart from the sheet data sent to the model)
        sheet_warnings = {}
        for sheet in extracted_answer_sheets:
            found = len(sheet.get("answers", []))
            if found == question_count:
                continue
            if found < question_count:
                matched = {str(a.get("mark_scheme_question_number")) for a in sheet["answers"] if a.get("mark_scheme_question_number")}
                if len(matched) == found:
                    # Matched to the mark scheme: name the mark scheme questions the sheet doesn't have,
                    # except choice questions left out of a group the student answered enough of
                    ms_questions = extracted_mark_scheme.get("mark_scheme", [])
                    answered_in_group = Counter(
                        q["choice"]["group"] for q in ms_questions if q.get("choice") and str(q.get("questionnumber")) in matched
                    )
                    gaps = [
                        q.get("questionnumber") for q in ms_questions
                        if str(q.get("questionnumber")) not in matched
                        and not (q.get("choice") and answered_in_group[q["choice"]["group"]] >= q["choice"]["pick"])
                    ]
                    if not gaps:
                        continue
                else:
                    numbers = {int(a["question_number"]) for a in sheet["answers"] if str(a.get("question_number")).isdigit()}
                    gaps = [n for n in range(1, max(numbers, default=0) + 1) if n not in numbers]
                missing = f" (Q{', Q'.join(map(str, gaps))} missing)" if gaps else ""
                message = f"{found} of {question_count} questions found{missing}; please verify"
            else:
                message = f"{found} questions found but the mark scheme has {question_count}; please verify"
            logger.warning(f"{sheet.get('filename')}: {message}")
            sheet_warnings.setdefault(sheet["file_id"], []).append(message)

        # ERROR CHECK: Stop if no answer sheets were successfully extracted
        if not extracted_answer_sheets:
            error_msg = (
                f"Failed to extract Q&A from any of the {len(answer_sheet_paths)} answer sheet(s). "
                "Please ensure answer sheets follow the expected format: 'Question 1. ... Answer: ...' or similar patterns."
            )
            logger.error(error_msg)
            raise Exception(error_msg)

        # Evaluation request uses mark scheme numbering so each answer is graded against the right
        # question; results are put back into answer sheet order afterwards.
        eval_answer_sheets = [to_mark_scheme_numbering(sheet) for sheet in extracted_answer_sheets]

        # Determine batch size based on question count
        total_sheets = len(extracted_answer_sheets)
        BATCH_SIZE = 5 if question_count < 15 else 3
        total_batches = (total_sheets + BATCH_SIZE - 1) // BATCH_SIZE
        
        logger.info(f"Starting evaluation: {total_sheets} answer sheets, {total_batches} batches (size: {BATCH_SIZE})")
        
        # Limit simultaneous OpenAI calls so large uploads don't hit rate limits all at once
        batch_slots = threading.BoundedSemaphore(MAX_PARALLEL_BATCHES)

        # Helper function to process a single batch
        def process_batch(batch_num: int, batch_sheets: list):
            """Process a single batch and return results, retrying failed or incomplete responses"""
            filenames = [sheet.get('filename', 'Unknown') for sheet in batch_sheets]
            expected_ids = sorted(sheet.get("file_id") for sheet in batch_sheets)
            # Every question sent for a sheet must come back graded exactly once, otherwise a dropped
            # question would quietly shrink both the score and the maximum
            expected_questions = {
                sheet.get("file_id"): sorted(str(a.get("question_number")).strip() for a in sheet.get("answers", []))
                for sheet in batch_sheets
            }
            batch_data = {"answer_sheets": batch_sheets}

            with batch_slots:
                for attempt in range(1, BATCH_MAX_ATTEMPTS + 1):
                    logger.info(f"→ Batch {batch_num} of {total_batches} started (attempt {attempt}): {filenames}")
                    try:
                        # Note: evaluate_files_all_in_one is synchronous, so it fits in this threaded function
                        batch_result = evaluate_files_all_in_one(evaluation_id, user_id, extracted_mark_scheme, batch_data)
                        students = batch_result.get("students", [])
                        returned_ids = sorted(s.get("file_id") for s in students)
                        if returned_ids != expected_ids:
                            raise ValueError(f"expected students {expected_ids}, got {returned_ids}")
                        for s in students:
                            expected = expected_questions[s.get("file_id")]
                            # A grade for a question that isn't on the sheet (e.g. one the student skipped) is dropped
                            extra = [a for a in s.get("answers", []) if str(a.get("question_number")).strip() not in expected]
                            if extra:
                                logger.warning(
                                    f"{s.get('file_id')}: dropped grades for questions not on the sheet: "
                                    f"{[a.get('question_number') for a in extra]}"
                                )
                                s["answers"] = [a for a in s["answers"] if a not in extra]
                            returned_questions = sorted(str(a.get("question_number")).strip() for a in s.get("answers", []))
                            if returned_questions != expected:
                                missing = sorted(set(expected) - set(returned_questions))
                                extra = sorted(set(returned_questions) - set(expected))
                                raise ValueError(
                                    f"{s.get('file_id')}: graded questions don't match the answer sheet "
                                    f"(missing {missing}, unexpected {extra}, got {len(returned_questions)} of {len(expected)})"
                                )
                        logger.info(f"✓ Batch {batch_num} of {total_batches} completed")
                        return batch_num, students
                    except Exception as batch_error:
                        detail = getattr(batch_error, "detail", None) or str(batch_error)
                        if attempt == BATCH_MAX_ATTEMPTS:
                            logger.error(f"✗ Batch {batch_num} failed after {attempt} attempts: {detail}")
                            raise
                        wait = BATCH_RETRY_DELAYS[attempt - 1]
                        logger.warning(f"Batch {batch_num} attempt {attempt} failed ({detail}); retrying in {wait}s")
                        time.sleep(wait)
        
        # Process batches asynchronously using asyncio.gather + to_thread
        # This replaces the ThreadPoolExecutor while still running purely synchronous separate tasks in threads
        batch_tasks = []
        
        # Log batch assignment
        logger.info("=" * 60)
        logger.info("BATCH ASSIGNMENT:")
        for batch_start in range(0, total_sheets, BATCH_SIZE):
            batch_end = min(batch_start + BATCH_SIZE, total_sheets)
            batch_sheets = eval_answer_sheets[batch_start:batch_end]
            batch_num = (batch_start // BATCH_SIZE) + 1
            
            filenames = [sheet.get('filename', 'Unknown') for sheet in batch_sheets]
            logger.info(f"  Batch {batch_num}: {filenames}")
            
            # Create a task for this batch
            # We use asyncio.to_thread to run the synchronous process_batch in a separate thread
            # This is non-blocking to the event loop
            task = asyncio.to_thread(process_batch, batch_num, batch_sheets)
            batch_tasks.append(task)
            
        logger.info("=" * 60)
        logger.info(f"Launching {len(batch_tasks)} batch tasks ({MAX_PARALLEL_BATCHES} at a time)")

        # Wait for all batches to complete
        batch_results_list = await asyncio.gather(*batch_tasks, return_exceptions=True)

        # Process results. A batch that still fails after its retries doesn't throw away the other
        # batches: its students are reported as skipped and the rest are saved.
        batch_results = {}
        for b_idx, result in enumerate(batch_results_list):
            if isinstance(result, Exception):
                error_text = getattr(result, "detail", None) or str(result)
                logger.error(f"Batch {b_idx + 1} execution failed with error: {error_text}")
                for sheet in eval_answer_sheets[b_idx * BATCH_SIZE:(b_idx + 1) * BATCH_SIZE]:
                    skipped_sheets.append({
                        "file_id": sheet.get("file_id"),
                        "filename": sheet.get("filename"),
                        "error": f"Grading failed: {error_text}",
                    })
            else:
                b_num, b_students = result
                batch_results[b_num] = b_students

        if not batch_results:
            raise Exception(f"All {len(batch_tasks)} grading batches failed. Last error: {skipped_sheets[-1]['error']}")
        
        # Reconstruct students in correct order by batch number
        all_students = []
        for batch_num in sorted(batch_results.keys()):
            all_students.extend(batch_results[batch_num])
        
        logger.info("=" * 60)
        logger.info(f"ALL BATCHES COMPLETED: {sorted(batch_results.keys())} | Total students: {len(all_students)}")
        logger.info("=" * 60)
        
        if skipped_sheets:
            logger.warning(
                f"{len(all_students)} students evaluated, {len(skipped_sheets)} answer sheet(s) skipped: "
                + ", ".join(s.get("filename") or s.get("file_id") for s in skipped_sheets)
            )
        else:
            logger.info(f"All batches completed: {len(all_students)} students evaluated successfully")

        # Put each student's results back into their answer sheet's numbering and order, whatever order
        # the mark scheme uses, with the sheet's section labels, question text and question images.
        sheets_by_file_id = {sheet.get("file_id"): sheet for sheet in extracted_answer_sheets}
        for idx, student in enumerate(all_students):
            sheet = sheets_by_file_id.get(student.get("file_id"))
            if sheet:
                all_students[idx] = restore_answer_sheet_order(student, sheet)
                all_students[idx]["filename"] = sheet.get("filename")
                unmapped = all_students[idx].pop("unmapped_answers", 0)
                if unmapped:
                    sheet_warnings.setdefault(student.get("file_id"), []).append(
                        f"{unmapped} graded answer(s) could not be matched to a question on the sheet; please verify"
                    )
            _add_skipped_questions(all_students[idx], extracted_mark_scheme.get("mark_scheme", []))

        # The model no longer echoes question text: answers whose sheet had none (image-only sheets, or an
        # answer that couldn't be mapped back to its sheet question) get the mark scheme's question text
        ms_question_text = {
            str(q.get("questionnumber")): re.sub(r"^\s*Q\s*\d+\s*[.:)]\s*", "", q.get("question-text") or "").strip()
            for q in extracted_mark_scheme.get("mark_scheme", [])
        }
        # "Answer any N of ..." groups from the mark scheme, applied to the totals below
        ms_choice = {
            str(q.get("questionnumber")): q["choice"]
            for q in extracted_mark_scheme.get("mark_scheme", []) if q.get("choice")
        }
        # A question's maximum is the total stated in the mark scheme, not the model's own figure,
        # so every student is marked out of the same maximum
        ms_max = {
            str(q.get("questionnumber")): q["max_score"]
            for q in extracted_mark_scheme.get("mark_scheme", []) if q.get("max_score") is not None
        }
        for student in all_students:
            for answer in student.get("answers", []):
                ms_number = answer.get("mark_scheme_question_number") or answer.get("question_number")
                if not answer.get("question_text"):
                    answer["question_text"] = ms_question_text.get(str(ms_number)) or None
                answer.setdefault("student_answer", None)
                if str(ms_number) in ms_choice:
                    answer["choice"] = ms_choice[str(ms_number)]
                max_score = ms_max.get(str(ms_number))
                model_max = answer.get("max_score")
                if max_score is not None and model_max != max_score:
                    # The model marked out of the wrong maximum: keep its score (capped at the maximum)
                    # and flag the answer for the teacher to review
                    answer["max_score"] = max_score
                    if (answer.get("score") or 0) > max_score:
                        answer["score"] = max_score
                    message = (
                        f"Question {answer.get('question_number')} was marked out of {model_max} instead of "
                        f"{max_score} (score {answer.get('score') or 0}/{max_score}); please verify this answer"
                    )
                    logger.warning(f"{student.get('file_id')}: {message}")
                    sheet_warnings.setdefault(student.get("file_id"), []).append(message)

        # One entry per uploaded sheet, in upload order: the UI, reports and CSV pair students with
        # answer_sheet_filenames by position, so a skipped sheet keeps its slot as a placeholder.
        students_by_file_id = {s.get("file_id"): s for s in all_students}
        skipped_by_file_id = {s["file_id"]: s for s in skipped_sheets}
        ordered_students = []
        for i in range(len(answer_sheet_paths)):
            file_id = f"answer_sheet_{i+1}"
            if file_id in students_by_file_id:
                ordered_students.append(students_by_file_id[file_id])
                continue
            skipped = skipped_by_file_id.get(file_id, {})
            ordered_students.append({
                "file_id": file_id,
                "filename": skipped.get("filename") or (answer_sheet_filenames[i] if i < len(answer_sheet_filenames) else f"answer_sheet_{i+1}.pdf"),
                "skipped": True,
                "error": skipped.get("error", "Answer sheet was not evaluated"),
                "answers": [],
                "total_score": 0,
                "max_total_score": 0,
            })
        all_students = ordered_students

        # Graded sheets that may be incomplete: shown in the UI banner and on the student's row
        warnings = []
        for student in all_students:
            messages = sheet_warnings.get(student["file_id"])
            if messages:
                student["warnings"] = messages
                warnings.extend({"file_id": student["file_id"], "filename": student.get("filename"), "message": m} for m in messages)

        # Create final evaluation result
        evaluation_result = {
            "evaluation_id": evaluation_id,
            "students": all_students,
            "skipped_sheets": skipped_sheets,
            "warnings": warnings
        }
        # Same max total for every student of a choice paper; kept for recalculating after edits
        paper_total = _paper_total(extracted_mark_scheme.get("mark_scheme", []))
        if paper_total is not None:
            evaluation_result["paper_total"] = paper_total
        # Verify and recalculate scores for each student (skipped sheets have no answers and stay 0/0)
        for student in evaluation_result.get("students", []):
            _apply_totals(student, None if student.get("skipped") else paper_total)

        # Calculate aggregate totals
        overall_total = sum(s.get("total_score", 0) for s in evaluation_result.get("students", []))
        overall_max = sum(s.get("max_total_score", 0) for s in evaluation_result.get("students", []))
        evaluation_result["total_score"] = overall_total
        evaluation_result["max_total_score"] = overall_max
        
        # Save evaluation result to MongoDB
        try:
            await asyncio.to_thread(update_evaluation_with_result, evaluation_id, evaluation_result)
            logger.info(f"Evaluation result saved to database")
        except Exception as save_error:
            logger.error(f"Failed to save evaluation result: {str(save_error)}")
            raise save_error
        
        # Extract all feedback from students' answers
        all_feedback = []
        
        # Get answer sheet filenames from evaluation record
        # Note: 'evaluation' variable from earlier might be stale if updated elsewhere, but filenames shouldn't change
        
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
            await asyncio.to_thread(create_ai_feedback, evaluation_id, {"feedback": all_feedback})
            
        # Send completion email
        try:
            await asyncio.to_thread(send_eval_completion_email, evaluation_id, user_id)
            await asyncio.to_thread(update_evaluation, evaluation_id, {"email_sent": True})
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
            await asyncio.to_thread(send_eval_error_email, evaluation_id, user_id)
        except Exception as email_error:
            logger.error(f"Failed to send error email: {str(email_error)}")

        # Update evaluation status to failed, keeping the error so the frontend
        # can tell the user why the process stopped.
        try:
            await asyncio.to_thread(update_evaluation, evaluation_id, {"status": "failed", "error_message": str(e)})
        except Exception as status_error:
            logger.error(f"Failed to update evaluation status: {str(status_error)}")

        # Clean up temporary files
        try:
            eval_dir = Path(f"local_storage/temp_evaluations/{evaluation_id}")
            if eval_dir.exists():
                shutil.rmtree(eval_dir)
        except Exception as cleanup_error:
            logger.error(f"Failed to cleanup temporary files: {str(cleanup_error)}")
        
        return {
            "error": str(e)
        }

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
        
        # Start the async background task
        asyncio.create_task(_process_evaluation(evaluation_id, user_id))
        
        return {
            "evaluation_id": evaluation_id,
            "message": "Evaluation started in background"
        }
        
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error starting evaluation {evaluation_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error starting evaluation: {str(e)}")

@router.put("/evaluation/edit-results")
def edit_results(request: EditresultRequest, user_id: str = Depends(verify_token)):
    try:
        # Update the question score and feedback
        update_question_score_feedback(request.evaluation_id, request.file_id, request.question_number, request.score, request.feedback)

        # Get current evaluation to calculate new total score
        updated_student = None
        evaluation = get_evaluation_by_evaluation_id(request.evaluation_id)
        if evaluation and "evaluation_result" in evaluation:
            for student in evaluation["evaluation_result"].get("students", []):
                if student.get("file_id") == request.file_id:
                    # A new score can change which answers of a choice group count
                    _apply_totals(student, evaluation["evaluation_result"].get("paper_total"))

                    # Update the totals and mark this student as modified
                    # using MongoDB directly with proper positional operator
                    db["evaluations"].update_one(
                        {"evaluation_id": request.evaluation_id, "evaluation_result.students.file_id": request.file_id},
                        {
                            "$set": {
                                "evaluation_result.students.$.answers": student.get("answers", []),
                                "evaluation_result.students.$.total_score": student["total_score"],
                                "evaluation_result.students.$.max_total_score": student["max_total_score"],
                                "evaluation_result.students.$.status": "modified",
                            }
                        },
                    )
                    updated_student = {
                        "total_score": student["total_score"],
                        "max_total_score": student["max_total_score"],
                        "not_counted": [a.get("question_number") for a in student.get("answers", []) if a.get("counted") is False],
                    }
                    break
        
        # Update evaluation status
        update_evaluation(request.evaluation_id, {"status": "updated"})
        
        return {"message": "Results updated", "student": updated_student}
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
                "error": evaluation.get("error_message") or "",
                "answer_sheet_filenames": evaluation.get("answer_sheet_filenames", [])
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

        # Ensure asset_name is unique per course by appending (n) if needed
        base_name = asset_name.strip()
        course_id = evaluation["course_id"]
        unique_name = base_name
        suffix = 1
        # Loop until we find a name that does not exist yet
        while get_asset_by_course_id_and_asset_name(course_id, unique_name):
            unique_name = f"{base_name} ({suffix})"
            suffix += 1

        # Get user's display name for the asset
        user_display_name = get_user_display_name(user_id)
        if not user_display_name:
            user_display_name = "Unknown User"

        # Save a lightweight evaluation asset that references the evaluation_id
        # This enables listing a card and opening the live Evaluation UI by ID
        logger.info(f"Saving evaluation reference {evaluation_id}")
        create_asset(
            course_id=course_id,
            asset_name=unique_name,
            asset_category="evaluation",
            asset_type="evaluation",
            asset_content=evaluation_id,
            asset_last_updated_by=user_display_name,
            asset_last_updated_at=datetime.now().strftime("%d %B %Y %H:%M:%S"),
            created_by_user_id=user_id
        )
        
        return {"message": "Evaluation saved successfully", "asset_name": unique_name}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error saving evaluation {evaluation_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error saving evaluation: {str(e)}")

def _has_section(answer):
    return answer.get("section") is not None and answer.get("section_question_number") is not None

def _question_label(answer, position):
    """Question number to show: the section's number on Mettl sheets; on other sheets the mark scheme
    question the answer was matched to (a student may skip questions), else its position."""
    if _has_section(answer):
        return answer["section_question_number"]
    if answer.get("section_question_number") is None and answer.get("mark_scheme_question_number"):
        return answer["mark_scheme_question_number"]
    return position

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
    current_section = None
    for j, answer in enumerate(answers, 1):
        if _has_section(answer) and answer["section"] != current_section:
            current_section = answer["section"]
            report += f"# Section {current_section}\n\n"
        report += f"## Question {_question_label(answer, j)}\n"
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
    
    # One column pair per question across all students, by question label (section-wise like "S2_Q1"
    # for Mettl sheets), so a student who skipped a question leaves that column empty
    def column(answer, position):
        number = _question_label(answer, position)
        if _has_section(answer):
            return f"S{answer['section']}_Q{number}", (answer["section"], int(number))
        return f"Q{number}", (0, int(number))

    columns = {}
    for student in students:
        for position, answer in enumerate(student.get('answers', []), 1):
            label, order = column(answer, position)
            columns.setdefault(label, order)
    labels = sorted(columns, key=columns.get)

    header = ["email"]
    for label in labels:
        header.extend([f"{label}_score", f"{label}_feedback"])
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
        by_label = {column(answer, position)[0]: answer for position, answer in enumerate(student.get('answers', []), 1)}
        for label in labels:
            answer = by_label.get(label)
            if answer:
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

def _filename_part(value) -> str:
    """Make a name safe for a download filename: letters, digits, '-' kept; everything else becomes '_'."""
    return re.sub(r"[^A-Za-z0-9-]+", "_", str(value or "")).strip("_")

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
        
        # Filename: evaluation_results_<course name>_<evaluation card name>.csv
        course = get_course(evaluation.get("course_id")) or {}
        asset = get_asset_by_evaluation_id(evaluation_id) or {}
        course_part = _filename_part(course.get("name")) or "course"
        card_part = _filename_part(asset.get("asset_name")) or evaluation_id[:8]
        filename = f"evaluation_results_{course_part}_{card_part}.csv"

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