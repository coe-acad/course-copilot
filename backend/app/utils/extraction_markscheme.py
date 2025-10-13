"""
Mark Scheme Extraction Module
Extracts structured mark scheme data from PDF files with fields:
- questionnumber
- question-text
- answertemplate
- markingscheme (array)
- deductions (array)
- notes
"""

import pdfplumber
import re
import json
import logging
from typing import List, Dict, Any, Optional
from collections import defaultdict

logger = logging.getLogger(__name__)


def extract_mark_scheme_from_pdf(pdf_path: str) -> List[Dict[str, Any]]:
    """
    Extract mark scheme data from a PDF file.
    
    Args:
        pdf_path: Path to the PDF file
        
    Returns:
        List of dictionaries, each containing mark scheme data for one question
    """
    try:
        # Extract full text from PDF
        full_text = _extract_full_text_from_pdf(pdf_path)
        
        # Try JSON format first (if the PDF contains JSON structure)
        json_questions = _try_extract_json_format(full_text)
        if json_questions:
            logger.info(f"Extracted {len(json_questions)} questions using JSON format")
            return json_questions
        
        # Try structured text format
        text_questions = _extract_structured_text_format(full_text)
        if text_questions:
            logger.info(f"Extracted {len(text_questions)} questions using structured text format")
            return text_questions
        
        # Fallback: Try to parse as basic question format
        basic_questions = _extract_basic_question_format(full_text)
        logger.info(f"Extracted {len(basic_questions)} questions using basic format")
        return basic_questions
        
    except Exception as e:
        logger.error(f"Error extracting mark scheme from {pdf_path}: {str(e)}")
        raise


def _extract_full_text_from_pdf(pdf_path: str) -> str:
    """Extract all text from PDF using pdfplumber"""
    text_parts = []
    
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            page_text = page.extract_text()
            if page_text:
                text_parts.append(page_text)
    
    return "\n".join(text_parts)


def _try_extract_json_format(text: str) -> Optional[List[Dict[str, Any]]]:
    """
    Try to extract JSON format from text.
    Handles cases where PDF contains JSON structure (with or without markdown code blocks)
    """
    try:
        # Remove markdown code blocks if present
        cleaned_text = re.sub(r'```json\s*', '', text)
        cleaned_text = re.sub(r'```\s*', '', cleaned_text)
        
        # Try to find JSON array pattern
        json_match = re.search(r'\[\s*\{.*?\}\s*\]', cleaned_text, re.DOTALL)
        if json_match:
            json_str = json_match.group(0)
            questions_data = json.loads(json_str)
            
            # Normalize the format
            normalized_questions = []
            for item in questions_data:
                normalized_questions.append(_normalize_question_format(item))
            
            return normalized_questions
    except (json.JSONDecodeError, AttributeError) as e:
        logger.debug(f"JSON extraction failed: {str(e)}")
        return None


def _extract_structured_text_format(text: str) -> List[Dict[str, Any]]:
    """
    Extract mark scheme from structured text format.
    Expected format:
    questionnumber: 1
    question-text: "..."
    answertemplate: "..."
    markingscheme: [
        "(X marks) bullet point 1",
        "(Y marks) bullet point 2"
    ]
    deductions: [
        "(X mark) deduction 1"
    ]
    notes: "..."
    """
    questions = []
    
    # Split by question blocks - look for questionnumber pattern
    question_blocks = re.split(r'\n(?=(?:questionnumber|"questionnumber")\s*:\s*\d+)', text, flags=re.IGNORECASE)
    
    for block in question_blocks:
        if not block.strip():
            continue
        
        question_data = _parse_question_block(block)
        if question_data and question_data.get('questionnumber'):
            questions.append(question_data)
    
    return questions


def _parse_question_block(block: str) -> Dict[str, Any]:
    """Parse a single question block into structured data"""
    question_data = {
        "questionnumber": None,
        "question-text": "",
        "answertemplate": "",
        "markingscheme": [],
        "deductions": [],
        "notes": ""
    }
    
    # Extract question number
    qnum_match = re.search(r'(?:questionnumber|"questionnumber")\s*:\s*(\d+)', block, re.IGNORECASE)
    if qnum_match:
        question_data["questionnumber"] = int(qnum_match.group(1))
    
    # Extract question-text
    qtext_match = re.search(
        r'(?:question-text|"question-text")\s*:\s*["\']?(.*?)(?=["\']?\s*(?:answertemplate|"answertemplate"|$))',
        block,
        re.DOTALL | re.IGNORECASE
    )
    if qtext_match:
        question_data["question-text"] = _clean_text(qtext_match.group(1))
    
    # Extract answertemplate
    answer_match = re.search(
        r'(?:answertemplate|"answertemplate")\s*:\s*["\']?(.*?)(?=["\']?\s*(?:markingscheme|"markingscheme"|$))',
        block,
        re.DOTALL | re.IGNORECASE
    )
    if answer_match:
        question_data["answertemplate"] = _clean_text(answer_match.group(1))
    
    # Extract markingscheme array
    marking_match = re.search(
        r'(?:markingscheme|"markingscheme")\s*:\s*\[(.*?)\]',
        block,
        re.DOTALL | re.IGNORECASE
    )
    if marking_match:
        question_data["markingscheme"] = _extract_array_items(marking_match.group(1))
    
    # Extract deductions array
    deductions_match = re.search(
        r'(?:deductions|"deductions")\s*:\s*\[(.*?)\]',
        block,
        re.DOTALL | re.IGNORECASE
    )
    if deductions_match:
        question_data["deductions"] = _extract_array_items(deductions_match.group(1))
    
    # Extract notes
    notes_match = re.search(
        r'(?:notes|"notes")\s*:\s*["\']?(.*?)(?=["\']?\s*(?:\}|questionnumber|$))',
        block,
        re.DOTALL | re.IGNORECASE
    )
    if notes_match:
        question_data["notes"] = _clean_text(notes_match.group(1))
    
    return question_data


def _extract_basic_question_format(text: str) -> List[Dict[str, Any]]:
    """
    Fallback: Extract questions in basic format.
    Looks for patterns like:
    Question 1: ... Answer: ... Mark Scheme: ... Deductions: ... Notes: ...
    """
    questions = []
    
    # Pattern to match Question X blocks
    question_pattern = re.compile(
        r'(?:Question\s+(\d+)|questionnumber\s*[:=]?\s*(\d+))(.*?)(?=(?:Question\s+\d+|questionnumber\s*[:=]?\s*\d+|$))',
        re.DOTALL | re.IGNORECASE
    )
    
    for match in question_pattern.finditer(text):
        qnum = match.group(1) or match.group(2)
        content = match.group(3)
        
        if not qnum:
            continue
        
        question_data = {
            "questionnumber": int(qnum),
            "question-text": "",
            "answertemplate": "",
            "markingscheme": [],
            "deductions": [],
            "notes": ""
        }
        
        # Extract question text (before answer/template)
        qtext_match = re.search(
            r'^(.*?)(?=(?:answer|answertemplate|marking|mark\s+scheme))',
            content,
            re.DOTALL | re.IGNORECASE
        )
        if qtext_match:
            question_data["question-text"] = _clean_text(qtext_match.group(1))
        
        # Extract answer template
        answer_match = re.search(
            r'(?:answer\s*template|correct\s*answer|answer)\s*[:=]?\s*(.*?)(?=(?:marking|mark\s+scheme|deductions|notes|$))',
            content,
            re.DOTALL | re.IGNORECASE
        )
        if answer_match:
            question_data["answertemplate"] = _clean_text(answer_match.group(1))
        
        # Extract marking scheme
        marking_match = re.search(
            r'(?:marking\s*scheme|mark\s*scheme)\s*[:=]?\s*(.*?)(?=(?:deductions|notes|$))',
            content,
            re.DOTALL | re.IGNORECASE
        )
        if marking_match:
            marking_text = marking_match.group(1)
            question_data["markingscheme"] = _extract_bullet_points(marking_text)
        
        # Extract deductions
        deductions_match = re.search(
            r'deductions\s*[:=]?\s*(.*?)(?=(?:notes|$))',
            content,
            re.DOTALL | re.IGNORECASE
        )
        if deductions_match:
            deductions_text = deductions_match.group(1)
            question_data["deductions"] = _extract_bullet_points(deductions_text)
        
        # Extract notes
        notes_match = re.search(
            r'notes\s*[:=]?\s*(.*?)$',
            content,
            re.DOTALL | re.IGNORECASE
        )
        if notes_match:
            question_data["notes"] = _clean_text(notes_match.group(1))
        
        questions.append(question_data)
    
    return questions


def _extract_array_items(array_text: str) -> List[str]:
    """
    Extract items from array text.
    Handles quoted strings separated by commas.
    """
    items = []
    
    # Match quoted strings
    quoted_pattern = re.compile(r'["\']([^"\']*)["\']')
    matches = quoted_pattern.findall(array_text)
    
    if matches:
        items = [_clean_text(m) for m in matches if m.strip()]
    else:
        # Fallback: split by commas if not quoted
        parts = array_text.split(',')
        items = [_clean_text(p) for p in parts if p.strip()]
    
    return items


def _extract_bullet_points(text: str) -> List[str]:
    """
    Extract bullet points from text.
    Handles various bullet point formats: -, *, •, numbers, etc.
    """
    bullets = []
    
    # Split by common bullet point patterns
    lines = text.split('\n')
    
    current_bullet = ""
    for line in lines:
        line = line.strip()
        
        # Check if line starts with bullet pattern
        if re.match(r'^[-*•▪►]\s+', line) or re.match(r'^\(\d+\s*marks?\)', line, re.IGNORECASE):
            # Save previous bullet if exists
            if current_bullet:
                bullets.append(_clean_text(current_bullet))
            current_bullet = line
        elif line and current_bullet:
            # Continuation of current bullet
            current_bullet += " " + line
        elif line and not current_bullet:
            # First line without bullet marker
            current_bullet = line
    
    # Add last bullet
    if current_bullet:
        bullets.append(_clean_text(current_bullet))
    
    # If no bullets found, return the whole text as single item
    if not bullets:
        cleaned = _clean_text(text)
        if cleaned:
            bullets = [cleaned]
    
    return bullets


def _clean_text(text: str) -> str:
    """Clean and normalize text"""
    if not text:
        return ""
    
    # Remove quotes at start/end
    text = text.strip()
    text = re.sub(r'^["\']|["\']$', '', text)
    
    # Remove excessive whitespace
    text = re.sub(r'\s+', ' ', text)
    
    # Remove trailing commas and semicolons
    text = re.sub(r'[,;]\s*$', '', text)
    
    return text.strip()


def _normalize_question_format(item: Dict[str, Any]) -> Dict[str, Any]:
    """
    Normalize question format to ensure consistent structure.
    Handles variations in field names.
    """
    normalized = {
        "questionnumber": None,
        "question-text": "",
        "answertemplate": "",
        "markingscheme": [],
        "deductions": [],
        "notes": ""
    }
    
    # Question number
    qnum = item.get('questionnumber') or item.get('question_number') or item.get('questionNumber')
    if qnum:
        normalized["questionnumber"] = int(qnum) if not isinstance(qnum, int) else qnum
    
    # Question text
    qtext = (item.get('question-text') or item.get('question_text') or 
             item.get('questionText') or item.get('question') or "")
    normalized["question-text"] = str(qtext).strip()
    
    # Answer template
    answer = (item.get('answertemplate') or item.get('answer_template') or 
              item.get('answerTemplate') or item.get('answer') or "")
    normalized["answertemplate"] = str(answer).strip()
    
    # Marking scheme
    marking = (item.get('markingscheme') or item.get('marking_scheme') or 
               item.get('markingScheme') or item.get('mark_scheme') or [])
    if isinstance(marking, list):
        normalized["markingscheme"] = [str(m).strip() for m in marking if m]
    elif isinstance(marking, str):
        normalized["markingscheme"] = [marking.strip()] if marking.strip() else []
    
    # Deductions
    deductions = item.get('deductions') or []
    if isinstance(deductions, list):
        normalized["deductions"] = [str(d).strip() for d in deductions if d]
    elif isinstance(deductions, str):
        normalized["deductions"] = [deductions.strip()] if deductions.strip() else []
    
    # Notes
    notes = item.get('notes') or ""
    normalized["notes"] = str(notes).strip()
    
    return normalized


def validate_mark_scheme(questions: List[Dict[str, Any]]) -> bool:
    """
    Validate that extracted mark scheme has required fields.
    
    Args:
        questions: List of question dictionaries
        
    Returns:
        True if valid, False otherwise
    """
    if not questions:
        return False
    
    required_fields = ["questionnumber", "question-text", "answertemplate", 
                      "markingscheme", "deductions", "notes"]
    
    for question in questions:
        # Check all required fields exist
        if not all(field in question for field in required_fields):
            return False
        
        # Check question number is valid
        if not isinstance(question["questionnumber"], int) or question["questionnumber"] <= 0:
            return False
    
    return True


def extract_mark_scheme_to_json(pdf_path: str, output_path: str = None) -> str:
    """
    Extract mark scheme and save as JSON file.
    
    Args:
        pdf_path: Path to PDF file
        output_path: Optional path to save JSON output
        
    Returns:
        JSON string of extracted mark scheme
    """
    questions = extract_mark_scheme_from_pdf(pdf_path)
    json_output = json.dumps(questions, indent=2, ensure_ascii=False)
    
    if output_path:
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(json_output)
        logger.info(f"Saved mark scheme to {output_path}")
    
    return json_output


# Convenience function to match existing API
def extract_text_from_mark_scheme(pdf_path: str) -> Dict[str, Any]:
    """
    Extract mark scheme from PDF file.
    Returns format compatible with existing evaluation system.
    
    Args:
        pdf_path: Path to PDF file
        
    Returns:
        Dictionary with 'mark_scheme' key containing list of questions
    """
    questions = extract_mark_scheme_from_pdf(pdf_path)
    return {"mark_scheme": questions}


if __name__ == "__main__":
    # Test with example file
    import sys
    
    if len(sys.argv) > 1:
        pdf_path = sys.argv[1]
        print(f"Extracting mark scheme from: {pdf_path}")
        
        try:
            questions = extract_mark_scheme_from_pdf(pdf_path)
            print(f"\n✓ Extracted {len(questions)} questions\n")
            print(json.dumps(questions, indent=2))
            
            # Validate
            if validate_mark_scheme(questions):
                print("\n✓ Mark scheme is valid!")
            else:
                print("\n⚠ Mark scheme validation failed")
        except Exception as e:
            print(f"\n✗ Error: {str(e)}")
    else:
        print("Usage: python extraction_markscheme.py <pdf_path>")


