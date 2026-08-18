import logging
import time
from fastapi import HTTPException
from ..utils.prompt_parser import PromptParser
from ..utils.openai_client import client
from ..config.settings import settings
import json
from app.services.mongo import get_evaluation_by_evaluation_id


logger = logging.getLogger(__name__)


def _validate_question_numbers(mark_scheme: dict, answer_sheets: list) -> None:
    """
    Validate that student answer question numbers match the mark scheme.
    Warns if there are discrepancies.

    Args:
        mark_scheme: Dict with 'mark_scheme' key containing list of question dicts
        answer_sheets: List of student answer sheet dicts
    """
    mark_scheme_list = mark_scheme.get("mark_scheme", [])
    if not mark_scheme_list:
        logger.warning("No mark scheme questions found for validation")
        return

    # Extract expected question numbers from mark scheme
    expected_questions = set()
    for question in mark_scheme_list:
        q_num = question.get("questionnumber")
        if q_num is not None:
            expected_questions.add(str(q_num))

    if not expected_questions:
        logger.warning("Could not extract question numbers from mark scheme")
        return

    # Check each student's answers
    for sheet in answer_sheets:
        student_answers = sheet.get("answers", [])
        student_questions = set()
        for answer in student_answers:
            q_num = answer.get("question_number")
            if q_num:
                student_questions.add(str(q_num))

        # Compare
        missing_questions = expected_questions - student_questions
        extra_questions = student_questions - expected_questions

        if missing_questions:
            logger.warning(
                f"Student {sheet.get('email', sheet.get('file_id'))} missing answers for questions: {missing_questions}"
            )
        if extra_questions:
            logger.warning(
                f"Student {sheet.get('email', sheet.get('file_id'))} has answers for unexpected questions: {extra_questions}"
            )


def clean_text(text: str):
    try:
        response = client.responses.create(
            model=settings.OPENAI_MODEL,
            input=[
                {
                    "role": "system",
                    "content": "You are a helpful assistant that cleans AI-generated messages. Your job is to remove any irrelevant or excessive introductory or concluding text — such as apologies, disclaimers, or requests for confirmation — that do not contribute to the core output.\n\nFocus on keeping only the core meaningful content such as course outcomes, summaries, tables, or actual suggestions.\n\nIf there is any core component or content to be saved, preserve that fully.\n\nIf no meaningful content is found (e.g., just a warning or error message), return it as-is without adding any explanation or comment."
                },
                {"role": "user", "content": text}
            ]
        )

        return response.output_text.strip()
    except Exception as e:
        logger.error(f"Error cleaning text: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

def course_description(description: str, course_name: str) -> str:
    try:
        # Clean and improve the course description using the Responses API
        response = client.responses.create(
            model=settings.OPENAI_MODEL,
            input=f"""You are a helpful assistant that rewrites rough course descriptions into clear,
realistic, and professional course descriptions written in the style a teacher would use
when describing a course.

Use the course name and provided description as context.
Focus only on what the course covers and what students will learn.
Do not use marketing language, exaggeration, or phrases like "join us" or "your journey".

Only return the improved description as plain text, with no labels or extra commentary.

Course name: {course_name}
Course description: {description}
"""
        )

        if not response.output_text:
            raise ValueError("Empty response from OpenAI")

        return response.output_text.strip()
        
    except Exception as e:
        logger.error(f"Error generating course description: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to generate course description")

    
def _collect_image_refs(answer_sheets_list: list) -> list:
    """
    Collect (sheet_file_id, question_number, openai_file_id) for every image
    referenced in student answers, in the order they appear in the payload.

    Structured answers (images/tables/mixed) are stored as a JSON array string
    in 'student_answer'; plain text answers are stored as a plain string.
    """
    refs = []
    for sheet in answer_sheets_list:
        sheet_id = sheet.get("file_id", "unknown")
        for answer in sheet.get("answers", []) or []:
            raw = answer.get("student_answer")
            if not isinstance(raw, str) or not raw.lstrip().startswith("["):
                continue
            try:
                items = json.loads(raw)
            except (json.JSONDecodeError, ValueError):
                continue
            if not isinstance(items, list):
                continue
            for item in items:
                if isinstance(item, dict) and item.get("type") == "image" and item.get("file_id"):
                    refs.append((sheet_id, str(answer.get("question_number", "?")), item["file_id"]))
    return refs


def evaluate_files_all_in_one(evaluation_id: str, user_id: str, extracted_mark_scheme: dict, extracted_answer_sheets: dict):
    """
    Evaluate a batch of answer sheets using OpenAI API.

    This function evaluates the answer sheets it receives without internal batching.
    Batching logic should be handled by the caller (routes layer).

    Args:
        evaluation_id: Unique identifier for the evaluation
        user_id: User performing the evaluation
        extracted_mark_scheme: Dict containing mark scheme with 'mark_scheme' key
        extracted_answer_sheets: Dict with "answer_sheets" key containing list of sheets to evaluate

    Returns:
        Dict with structure: { "evaluation_id": str, "students": [...] }
    """
    # Get list of answer sheets
    answer_sheets_list = extracted_answer_sheets.get("answer_sheets", [])
    if not answer_sheets_list:
        raise HTTPException(status_code=400, detail="No answer sheets found in extracted data")

    # Store email mapping (file_id -> email) for restoration after evaluation
    email_mapping = {}
    for sheet in answer_sheets_list:
        file_id = sheet.get('file_id')
        email = sheet.get('email')
        if file_id and email:
            email_mapping[file_id] = email

    # Get evaluation
    evaluation = get_evaluation_by_evaluation_id(evaluation_id)
    if not evaluation:
        raise HTTPException(status_code=404, detail=f"Evaluation {evaluation_id} not found")

    # Validate question numbers consistency
    _validate_question_numbers(extracted_mark_scheme, answer_sheets_list)
    # Prepare evaluation payload
    payload = {
        "mark_scheme": json.dumps(extracted_mark_scheme),
        "answer_sheets": json.dumps({"answer_sheets": answer_sheets_list}),
        "evaluation_id": evaluation_id
    }
    
    evaluation_prompt = PromptParser().get_evaluation_prompt(evaluation_id, payload)

    # Attach student answer images as vision inputs. A file_id mentioned inside
    # prompt text is inert — the model only sees images passed as input_image
    # content parts. Each image is preceded by a text label (file_id, sheet,
    # question) so the model can match it to the reference in the answer JSON.
    image_refs = _collect_image_refs(answer_sheets_list)
    content = [{"type": "input_text", "text": evaluation_prompt}]
    for sheet_id, question_number, image_file_id in image_refs:
        content.append({
            "type": "input_text",
            "text": f"Attached image {image_file_id} — {sheet_id}, question {question_number}:"
        })
        content.append({"type": "input_image", "file_id": image_file_id, "detail": "auto"})
    if image_refs:
        logger.info(f"Attaching {len(image_refs)} answer image(s) to evaluation request")

    # Create thread and run evaluation
    run = client.responses.create(
        model=settings.OPENAI_MODEL,
        input=[{"role": "user", "content": content}],
        temperature=0.3,
        text={
            "format": {
                "type": "json_schema",
                "name": "evaluation_schema",
                "strict": True,
                "schema": {
                    "type": "object",
                    "properties": {
                        "evaluation_id": {"type": "string"},
                        "students": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "file_id": {"type": "string"},
                                    "answers": {
                                        "type": "array",
                                        "items": {
                                            "type": "object",
                                            "properties": {
                                                "question_number": {"type": "string"},
                                                "question_text": {"type": "string"},
                                                "student_answer": {"type": ["string", "null"]},
                                                "correct_answer": {"type": ["string", "null"]},
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
                                            ],
                                            "additionalProperties": False
                                        }
                                    },
                                    "total_score": {"type": "number"},
                                    "max_total_score": {"type": "number"}
                                },
                                "required": ["file_id", "answers", "total_score", "max_total_score"],
                                "additionalProperties": False
                            }
                        }
                    },
                    "required": ["evaluation_id", "students"],
                    "additionalProperties": False
                }
            }
        }
    )

    # Poll until run completes
    while run.status in ("queued", "in_progress"):
        time.sleep(1) # Add a small sleep to avoid tight loop
        run = client.responses.retrieve(run.id)

    if run.status == "failed":
        logger.error(f"OpenAI evaluation failed: {run.last_error}")
        raise HTTPException(status_code=500, detail=f"Evaluation failed: {run.last_error}")

    # Extract structured output from response
    structured_output = run.output_text.strip() if run.output_text else None

    if not structured_output:
        raise HTTPException(
            status_code=500,
            detail="No structured output returned from OpenAI evaluation"
        )

    # Parse JSON response
    try:
        evaluation_result = json.loads(structured_output)
        
        # Validate response structure
        if "properties" in evaluation_result and "type" in evaluation_result:
            raise HTTPException(
                status_code=500,
                detail="OpenAI returned schema definition instead of evaluation results. Please try again."
            )
        
        if "evaluation_id" not in evaluation_result:
            evaluation_result["evaluation_id"] = evaluation_id
            
        if "students" not in evaluation_result:
            raise HTTPException(
                status_code=500,
                detail="Invalid evaluation result: missing 'students' field"
            )
            
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse OpenAI JSON response: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Invalid JSON response from OpenAI: {str(e)}"
        )

    # Restore emails to students from mapping
    students = evaluation_result.get("students", [])
    for student in students:
        file_id = student.get('file_id')
        if file_id and file_id in email_mapping:
            student['email'] = email_mapping[file_id]

    return {
        "evaluation_id": evaluation_id,
        "students": students
    }

#use the web search to discover resources for the input typed on the UI
def discover_resources(query):
    system_prompt = """You are a resource discovery assistant specialized in finding high-quality, authoritative, and up-to-date web resources.

Your task:
1. Search the web to find the most relevant and trustworthy resources for the user's query
2. Prioritize sources in this order:
   - Official documentation or official websites
   - Reputable organizations, standards bodies, or well-known platforms
   - High-quality educational resources from established publishers
3. Avoid low-quality blogs, SEO-driven content, forums, or opinion pieces unless no authoritative source exists
4. Only include sources that are currently accessible and actively maintained
5. Always include working, direct URLs

CRITICAL: You must respond with ONLY a valid JSON array. No preamble, no markdown code blocks, no explanation text.

Response format (JSON only):
[
  {
    "title": "Resource title",
    "url": "https://example.com",
    "description": "Brief 1-2 sentence description of what this resource provides and why it's authoritative"
  }
]

Additional guidelines:
- Return 5-10 resources maximum
- Prefer primary sources over summaries or secondary explanations
- Do not repeat the same platform or website excessively unless clearly justified
- Each resource must have all three fields: title, url, and description
- Ensure all URLs are complete and valid (starting with https://)

Focus on accuracy, credibility, and usefulness over quantity."""

    run = client.responses.create(
        model=settings.OPENAI_MODEL,
        input=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": query}
        ],
        tools=[{"type": "web_search"}],
        temperature=0.2
    )

    # Get the output
    output = run.output_text.strip()
    
    # Parse JSON (with error handling)
    try:
        # Remove markdown code blocks if present
        if output.startswith("```json"):
            output = output.replace("```json", "").replace("```", "").strip()
        elif output.startswith("```"):
            output = output.replace("```", "").strip()
        
        resources_json = json.loads(output)
        return resources_json
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse JSON response: {output}")
        # Fallback: return empty list or raise exception
        raise ValueError(f"Invalid JSON response from API: {str(e)}")