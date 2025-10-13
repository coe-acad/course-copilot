import re
import PyPDF2
import logging

logger = logging.getLogger(__name__)

def extract_text_from_pdf(file_path):
    """Extract raw text from PDF file"""
    text = ""
    with open(file_path, "rb") as f:
        reader = PyPDF2.PdfReader(f)
        for page in reader.pages:
            text += page.extract_text() + "\n"
    return text

def extract_text_from_mark_scheme(file_path):
    """Extract and parse mark scheme from PDF"""
    text = extract_text_from_pdf(file_path)
    
    # Parse mark scheme - looking for Question, Answer/Answer Template, Mark Scheme patterns
    mark_scheme = []
    
    # Pattern to match: Question X ... Answer: ... Mark Scheme: ...
    # This is flexible to handle different formats
    question_pattern = re.compile(
        r'Question\s+(\d+)[:\.]?\s*(.*?)(?=Question\s+\d+|$)', 
        re.DOTALL | re.IGNORECASE
    )
    
    for match in question_pattern.finditer(text):
        question_num = match.group(1).strip()
        content = match.group(2).strip()
        
        # Extract question text, answer template, and mark scheme from content
        question_text = ""
        answer_template = ""
        marking_scheme = ""
        deductions = ""
        notes = ""
        
        # Try to split by Answer/Correct Answer/Answer Template
        answer_match = re.search(
            r'(Answer\s*Template|Correct\s*Answer|Answer)[:\.]?\s*(.*?)(?=Mark(?:ing)?\s*Scheme|Deductions|Notes|$)',
            content,
            re.DOTALL | re.IGNORECASE
        )
        
        if answer_match:
            question_text = content[:answer_match.start()].strip()
            answer_template = answer_match.group(2).strip()
            
            # Extract marking scheme
            scheme_match = re.search(
                r'Mark(?:ing)?\s*Scheme[:\.]?\s*(.*?)(?=Deductions|Notes|$)',
                content,
                re.DOTALL | re.IGNORECASE
            )
            if scheme_match:
                marking_scheme = scheme_match.group(1).strip()
            
            # Extract deductions if present
            deductions_match = re.search(
                r'Deductions[:\.]?\s*(.*?)(?=Notes|$)',
                content,
                re.DOTALL | re.IGNORECASE
            )
            if deductions_match:
                deductions = deductions_match.group(1).strip()
            
            # Extract notes if present
            notes_match = re.search(
                r'Notes[:\.]?\s*(.*?)$',
                content,
                re.DOTALL | re.IGNORECASE
            )
            if notes_match:
                notes = notes_match.group(1).strip()
        else:
            # If no answer section found, treat all as question text
            question_text = content
        
        mark_scheme.append({
            "question_number": question_num,
            "question_text": question_text,
            "answer_template": answer_template,
            "mark_scheme": marking_scheme,
            "deductions": deductions,
            "notes": notes
        })
    
    logger.info(f"Extracted {len(mark_scheme)} questions from mark scheme")
    return {"mark_scheme": mark_scheme}

def extract_text_from_answer_sheet(file_path):
    """Extract and parse answer sheet from PDF"""
    text = extract_text_from_pdf(file_path)
    
    # Try to extract student name if present
    student_name = "Unknown Student"
    name_match = re.search(r'(?:Name|Student)[:\.]?\s*([^\n]+)', text, re.IGNORECASE)
    if name_match:
        student_name = name_match.group(1).strip()
    
    # Parse answers - looking for Question X ... Answer: ... patterns
    answers = []
    
    question_pattern = re.compile(
        r'Question\s+(\d+)[:\.]?\s*(.*?)(?:Answer[:\.]?\s*(.*?))?(?=Question\s+\d+|$)',
        re.DOTALL | re.IGNORECASE
    )
    
    for match in question_pattern.finditer(text):
        question_num = match.group(1).strip()
        question_text = match.group(2).strip() if match.group(2) else ""
        student_answer = match.group(3).strip() if match.group(3) else None
        
        # If answer is empty or marked as N/A, set to None
        if student_answer and (not student_answer.strip() or student_answer.strip().upper() == 'N/A'):
            student_answer = None
        
        answers.append({
            "question_number": question_num,
            "question_text": question_text,
            "student_answer": student_answer
        })
    
    logger.info(f"Extracted {len(answers)} answers from answer sheet for {student_name}")
    
    return {
        "student_name": student_name,
        "answers": answers
    }

def parse_answer_paper(text):
    """Legacy function for backward compatibility - parses answer paper text"""
    qa_pattern = re.compile(r"Question\s*\d+\.(.*?)Answer:(.*?)(?=Question\s*\d+\.|$)", re.S)
    responses = []
    for match in qa_pattern.finditer(text):
        question = match.group(1).strip()
        answer = match.group(2).strip()
        responses.append({
            "question": question,
            "answer": answer,
        })

    return {
        "responses": responses
    }
