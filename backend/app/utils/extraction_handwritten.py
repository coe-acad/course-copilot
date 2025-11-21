"""
Handwritten answer sheet extraction using Mistral OCR.
Extracts question numbers and student answers from handwritten PDFs/images.
Based on the working Mistral API approach.
"""

import os
import re
import json
import logging
import time
from pathlib import Path
from typing import List, Dict, Optional
from mistralai import Mistral
from dotenv import load_dotenv

from prompt_parser import PromptParser

# Load environment variables
load_dotenv()

logger = logging.getLogger(__name__)


def parse_questions_and_answers(markdown_text: str) -> List[Dict[str, Optional[str]]]:
    """
    Parse questions and answers from markdown text.
    
    Supports multiple question formats:
    - "Question 1:", "Question 2:", etc.
    - "1.", "2.", "3.", etc.
    - "Q1:", "Q2:", etc.
    
    The text between two questions is the answer for the question above.
    
    Handles duplicate question numbers by keeping the first substantial occurrence.
    
    Args:
        markdown_text: The markdown text extracted from OCR response
    
    Returns:
        List of dictionaries with question_number and student_answer
    """
    # Enhanced patterns to match various question formats
    # Pattern 1: "Question 1:", "Question 2:", etc. (case insensitive)
    question_pattern_1 = r'(?i)^Question\s+(\d+)\s*:'
    
    # Pattern 2: "1.", "2.", "10.", etc. at start of line
    question_pattern_2 = r'^(\d+)\.\s'
    
    # Pattern 3: "Q1:", "Q2:", etc. (case insensitive)
    question_pattern_3 = r'(?i)^Q(\d+)\s*:'
    
    # Pattern 4: "(1)", "(2)", etc. at start of line
    question_pattern_4 = r'^\((\d+)\)\s'
    
    # Combine all patterns
    question_pattern = rf'({question_pattern_1}|{question_pattern_2}|{question_pattern_3}|{question_pattern_4})'
    
    # Find all question numbers and their positions
    all_matches = []
    
    # Try each pattern and collect matches
    for pattern in [question_pattern_1, question_pattern_2, question_pattern_3, question_pattern_4]:
        matches = list(re.finditer(pattern, markdown_text, re.MULTILINE))
        for match in matches:
            # Extract question number from the appropriate group
            if pattern == question_pattern_1:
                qnum = match.group(1)
            elif pattern == question_pattern_2:
                qnum = match.group(1)
            elif pattern == question_pattern_3:
                qnum = match.group(1)
            elif pattern == question_pattern_4:
                qnum = match.group(1)
            else:
                qnum = match.group(1) if match.lastindex else None
            
            if qnum:
                all_matches.append({
                    'question_num': qnum,
                    'start': match.start(),
                    'end': match.end()
                })
    
    # Sort by position and remove duplicates (keep first occurrence)
    all_matches.sort(key=lambda x: x['start'])
    unique_matches = []
    seen_positions = set()
    for match in all_matches:
        # Avoid duplicates within 50 characters (same question detected multiple times)
        if not any(abs(match['start'] - pos) < 50 for pos in seen_positions):
            unique_matches.append(match)
            seen_positions.add(match['start'])
    
    matches = unique_matches
    
    logger.info(f"Found {len(matches)} unique question markers")
    print(f"\n📋 Found {len(matches)} question markers")
    
    for match in matches:
        print(f"  - Question {match['question_num']} at position {match['start']}")
    
    if not matches:
        logger.warning("No questions found in the text")
        print("⚠️  No questions found in the text")
        # Try to extract any numbered content as fallback
        return _fallback_extraction(markdown_text)
    
    # Extract questions and answers with positions
    raw_results = []
    for i, match in enumerate(matches):
        question_num = match['question_num']
        match_start = match['start']
        match_end = match['end']
        
        # The answer starts right after the match
        answer_start = match_end
        
        # Find the end of this question's answer
        # It's either the start of the next question or the end of the text
        if i + 1 < len(matches):
            answer_end = matches[i + 1]['start']
        else:
            # Last question - answer goes to the end of the text
            answer_end = len(markdown_text)
        
        # Extract the answer text (everything between this question number and the next)
        answer_text = markdown_text[answer_start:answer_end].strip()
        
        # Clean up common prefixes that might appear
        # Remove "Answer:" prefix if present
        answer_text = re.sub(r'^(?i)Answer\s*:\s*', '', answer_text)
        # Remove leading/trailing dashes or separators
        answer_text = re.sub(r'^[-=\s]+|[-=\s]+$', '', answer_text)
        
        raw_results.append({
            'question_number': question_num,
            'student_answer': answer_text,
            'position': match_start
        })
    
    # Handle duplicate question numbers by keeping only the first substantial occurrence
    print(f"\n🔄 Processing question numbers and removing duplicates...")
    seen_questions = {}
    result = []
    
    for item in raw_results:
        qnum = item['question_number']
        answer = item['student_answer']
        
        # Keep the first occurrence encountered
        if qnum not in seen_questions:
            # This is the first time we see this question number
            if answer:
                seen_questions[qnum] = True
                result.append({
                    'question_number': qnum,
                    'student_answer': answer
                })
                
                answer_length = len(answer)
                answer_preview = answer[:100] if len(answer) > 100 else answer
                
                logger.info(f"Question {qnum}: {answer_length} characters")
                print(f"  Q{qnum}: {answer_length} characters")
                if answer_preview:
                    print(f"    Preview: {answer_preview}...")
            else:
                # Mark as seen but don't add yet (might be a header/empty)
                logger.debug(f"Skipping empty/short Q{qnum} at position {item['position']}")
        else:
            # We've seen this question before - skip duplicate
            logger.debug(f"Skipping duplicate Q{qnum} at position {item['position']}")
            print(f"  ⚠️  Skipping duplicate Q{qnum} (already processed)")
    
    # Sort by question number
    result.sort(key=lambda x: int(x['question_number']))
    
    print()
    
    # Validate results
    if not result:
        logger.warning("No valid questions extracted, attempting fallback")
        return _fallback_extraction(markdown_text)
    
    # Log validation summary
    logger.info(f"Successfully extracted {len(result)} questions")
    for item in result:
        if not item.get('student_answer') or len(item['student_answer'].strip()) < 3:
            logger.warning(f"Question {item['question_number']} has very short or empty answer")
    
    return result


def _try_extract_json(text: str) -> Optional[Dict]:
    """
    Try to extract JSON from the response text.
    Looks for JSON objects in the text.
    """
    # Try to find JSON object in the text
    json_pattern = r'\{[^{}]*"answers"[^{}]*\[[^\]]*\][^{}]*\}'
    match = re.search(json_pattern, text, re.DOTALL)
    
    if match:
        try:
            json_str = match.group(0)
            return json.loads(json_str)
        except json.JSONDecodeError:
            pass
    
    # Try to find JSON array
    array_pattern = r'\[[^\]]*\{[^}]+\}[^\]]*\]'
    match = re.search(array_pattern, text, re.DOTALL)
    if match:
        try:
            json_str = match.group(0)
            return {"answers": json.loads(json_str)}
        except json.JSONDecodeError:
            pass
    
    # Try parsing the entire text as JSON
    try:
        return json.loads(text.strip())
    except json.JSONDecodeError:
        pass
    
    return None


def _parse_json_response(json_data: Dict) -> List[Dict[str, Optional[str]]]:
    """
    Parse questions and answers from JSON response.
    """
    result = []
    
    # Handle different JSON structures
    if "answers" in json_data:
        answers = json_data["answers"]
    elif isinstance(json_data, list):
        answers = json_data
    else:
        return []
    
    for item in answers:
        if isinstance(item, dict):
            qnum = str(item.get("question_number") or item.get("questionNumber") or item.get("q") or "")
            answer = item.get("student_answer") or item.get("studentAnswer") or item.get("answer") or ""
            
            if qnum and answer:
                result.append({
                    "question_number": qnum,
                    "student_answer": str(answer)
                })
    
    # Sort by question number
    result.sort(key=lambda x: int(x['question_number']) if x['question_number'].isdigit() else 999)
    
    return result


def _fallback_extraction(markdown_text: str) -> List[Dict[str, Optional[str]]]:
    """
    Fallback extraction method when primary patterns fail.
    Tries to extract any numbered content as potential questions.
    """
    logger.info("Attempting fallback extraction method")
    print("🔄 Attempting fallback extraction...")
    
    # Look for any numbered patterns that might be questions
    # Pattern: number followed by colon or period, possibly with "Question" prefix
    fallback_pattern = r'(?i)(?:Question\s+)?(\d+)[:.]\s*(.+?)(?=(?:Question\s+)?\d+[:.]|$)'
    
    matches = list(re.finditer(fallback_pattern, markdown_text, re.DOTALL | re.MULTILINE))
    
    result = []
    for match in matches:
        qnum = match.group(1)
        answer = match.group(2).strip() if match.group(2) else ""
        
        # Clean up answer
        answer = re.sub(r'^(?i)Answer\s*:\s*', '', answer)
        answer = answer.strip()
        
        if answer and len(answer) > 2:  # Only add if answer has meaningful content
            result.append({
                'question_number': qnum,
                'student_answer': answer
            })
    
    if result:
        logger.info(f"Fallback extraction found {len(result)} potential questions")
        print(f"✅ Fallback extraction found {len(result)} potential questions")
    else:
        logger.warning("Fallback extraction also failed - no questions found")
        print("⚠️  Fallback extraction also failed")
    
    return result


def extract_handwritten_answers(
    file_path: str,
    answers_only: bool = True
) -> Dict[str, any]:
    """
    Extract question-answer pairs from handwritten answer sheets using Mistral API.
    
    Args:
        file_path: Path to PDF or image file
        answers_only: If True, returns simplified format (default)
        
    Returns:
        Dict with format:
        {
            "email": None,
            "answers": [{"question_number": str, "student_answer": str}, ...]
        }
        
    Raises:
        FileNotFoundError: If file doesn't exist
        ValueError: If API key not configured
        Exception: For OCR or parsing errors
    """
    logger.info(f"Extracting from: {file_path}")
    
    # Get API key from environment
    api_key = os.getenv("MISTRAL_API_KEY")
    if not api_key:
        raise ValueError(
            "MISTRAL_API_KEY is not configured. "
            "Please set it in your environment variables."
        )
    
    # Initialize Mistral client
    client = Mistral(api_key=api_key)
    
    file_path = Path(file_path)
    if not file_path.is_file():
        raise FileNotFoundError(f"File not found: {file_path}")
    
    try:
        
        # Upload PDF
        logger.info("Uploading PDF file...")
        print("\n📤 Uploading PDF file...")
        
        with open(file_path, "rb") as f:
            uploaded_pdf = client.files.upload(
                file={
                    "file_name": file_path.name,
                    "content": f,
                },
                purpose="ocr"
            )
        
        logger.info(f"File uploaded with ID: {uploaded_pdf.id}")
        print(f"✅ File uploaded with ID: {uploaded_pdf.id}")
        
        # Get signed URL
        signed_url = client.files.get_signed_url(file_id=uploaded_pdf.id)
        logger.info("Signed URL obtained")
        print(f"✅ Signed URL obtained")
        
        # Use mistral-large-latest model for better instruction following
        model = "mistral-large-latest"
        
        print(f"\n🤖 Using model: {model}")
        logger.info(f"Using model: {model}")
        
        prompt_parser = PromptParser()
        prompt_template_path = os.path.join(
            prompt_parser.base_dir,
            "prompts/evaluation/handwritten-answer-sheet-extraction.json"
        )
        print(f"📝 Using prompt template: {prompt_template_path}")
        base_prompt = prompt_parser.render_prompt(
            prompt_template_path,
            {"file_id": uploaded_pdf.id}
        )
        
        # Enhanced prompt with explicit JSON output request and few-shot example
        enhanced_prompt = f"""{base_prompt}

---

## CRITICAL OUTPUT FORMAT REQUIREMENT

You MUST output the extracted content in the following EXACT format:

1. Start with any header/metadata (student name, roll number, date, etc.)
2. For each question, use this EXACT format:
   Question [NUMBER]: [Question text if visible]
   
   Answer: [Student's answer text]
   
3. If a question number appears multiple times, extract each occurrence separately
4. Preserve ALL text exactly as written - do not summarize or paraphrase
5. Mark uncertain text with [UNCERTAIN: text] tags
6. For images/diagrams, use the [IMAGE DESCRIPTION: ...] format inline
7. For tables, use markdown table format inline

EXAMPLE OUTPUT FORMAT:
---
Student Name: [Name]     Roll No: [Number]     Date: [Date]

Question 1: [Question text]

Answer: [Student's complete answer text here, preserving all formatting, line breaks, and structure]

Question 2: [Question text]

Answer: [Student's complete answer text here]

[IMAGE DESCRIPTION: ...]

Question 3: [Question text]

Answer: [Student's complete answer text here]
---

IMPORTANT: 
- Each question MUST start with "Question [NUMBER]:" on a new line
- Each answer MUST start with "Answer:" on a new line immediately after the question
- Do NOT combine multiple questions into one
- Do NOT skip question numbers
- Extract answers in the exact order they appear in the document
"""
        
        logger.info(f"Enhanced prompt length: {len(enhanced_prompt)} characters")
        
        # Prepare messages with structured prompt
        messages = [
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": enhanced_prompt
                    },
                    {
                        "type": "document_url",
                        "document_url": signed_url.url
                    }
                ]
            }
        ]
        
        print("\n📡 Sending request to Mistral API...")
        logger.info("Sending request to Mistral API...")
        
        # Call the Mistral API with optimized parameters and retry logic
        # Lower temperature for more consistent, structured output
        max_retries = 3
        retry_delay = 2  # seconds
        
        for attempt in range(max_retries):
            try:
                chat_response = client.chat.complete(
                    model=model,
                    messages=messages,
                    temperature=0.1,  # Lower temperature for more deterministic, structured output
                    top_p=0.9,  # Nucleus sampling for better quality
                    max_tokens=16000  # Ensure enough tokens for complete extraction
                )
                break  # Success, exit retry loop
            except Exception as e:
                if attempt < max_retries - 1:
                    wait_time = retry_delay * (2 ** attempt)  # Exponential backoff
                    logger.warning(f"API call failed (attempt {attempt + 1}/{max_retries}): {e}. Retrying in {wait_time}s...")
                    print(f"⚠️  API call failed, retrying in {wait_time}s...")
                    time.sleep(wait_time)
                else:
                    logger.error(f"API call failed after {max_retries} attempts: {e}")
                    raise
        
        print("✅ Received response from Mistral API\n")
        logger.info("Received response from Mistral API")
        
        # Extract the text from the response
        extracted_text = ""
        if hasattr(chat_response, 'choices') and chat_response.choices:
            for choice in chat_response.choices:
                if hasattr(choice, 'message') and hasattr(choice.message, 'content'):
                    extracted_text += choice.message.content + "\n"
        
        logger.info(f"Extracted {len(extracted_text)} characters")
        print(f"✅ Extracted {len(extracted_text)} characters\n")
        
        # Try to extract JSON if model output JSON format
        json_data = _try_extract_json(extracted_text)
        if json_data:
            logger.info("Found JSON structure in response, using JSON parser")
            print("📋 Detected JSON format, parsing...")
            questions_answers = _parse_json_response(json_data)
            if questions_answers:
                result = {
                    "email": json_data.get("email"),
                    "answers": questions_answers
                }
                print(f"✅ Extracted {len(questions_answers)} questions from JSON\n")
                return result
            else:
                logger.warning("JSON parsing failed, falling back to text parsing")
                print("⚠️  JSON parsing failed, using text parser\n")
        
        # Parse questions and answers
        print("=" * 80)
        print("STEP 2: Parsing Questions and Answers")
        print("=" * 80)
        
        questions_answers = parse_questions_and_answers(extracted_text)
        
        print("\n" + "=" * 80)
        print("STEP 3: Final Results")
        print("=" * 80)
        print(f"\n✅ Total questions found: {len(questions_answers)}\n")
        
        # Return format matching extraction_answersheet.py
        result = {
            "email": None,  # Email extraction not yet implemented for handwritten
            "answers": questions_answers
        }
        
        return result
        
    except Exception as e:
        logger.error(f"Extraction failed: {e}")
        print(f"\n❌ Error: {e}\n")
        import traceback
        traceback.print_exc()
        raise


def split_into_qas_mistral(
    pdf_path: str,
    answers_only: bool = True
) -> Dict[str, any]:
    """
    Alternative interface matching extraction_answersheet.py.
    
    Args:
        pdf_path: Path to PDF file
        answers_only: Returns simplified format
        
    Returns:
        Dict with format: {"email": str or None, "answers": [{"question_number": str, "student_answer": str}, ...]}
    """
    return extract_handwritten_answers(pdf_path, answers_only=answers_only)


# ==================== TESTING ====================

if __name__ == "__main__":
    import sys
    
    # Configure logging for testing
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
    
    # PDF Processing Mode
    if len(sys.argv) > 1:
        pdf_path = sys.argv[1]
        output_file = sys.argv[2] if len(sys.argv) > 2 else "output.txt"
    else:
        # Default: look for PDF in the same directory as this script
        script_dir = Path(__file__).parent
        pdf_path = str(script_dir / "handwritten answersheet.pdf")
        output_file = str(script_dir / "output.txt")
    
    print("\n" + "=" * 80)
    print("HANDWRITTEN ANSWER SHEET EXTRACTION")
    print("=" * 80)
    print(f"Input PDF: {pdf_path}")
    print(f"Output File: {output_file}")
    print("=" * 80 + "\n")
    
    try:
        # Extract answers from the PDF
        result = extract_handwritten_answers(pdf_path)
        
        # Write results to output file
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write("=" * 80 + "\n")
            f.write("EXTRACTION RESULTS\n")
            f.write("=" * 80 + "\n\n")
            
            f.write(f"Email: {result.get('email', 'None')}\n")
            f.write(f"Total Questions Extracted: {len(result['answers'])}\n\n")
            f.write("=" * 80 + "\n\n")
            
            # Write each question-answer pair
            for qa in result['answers']:
                f.write(f"Question {qa['question_number']}:\n")
                f.write("-" * 40 + "\n")
                f.write(f"{qa['student_answer']}\n")
                f.write("\n" + "=" * 80 + "\n\n")
            
            # Also write JSON format at the end
            f.write("\n\n" + "=" * 80 + "\n")
            f.write("JSON FORMAT\n")
            f.write("=" * 80 + "\n")
            f.write(json.dumps(result, indent=2, ensure_ascii=False))
        
        print(f"\n✅ Results written to: {output_file}")
        print(f"✅ Total questions extracted: {len(result['answers'])}")
        
        # Print summary to console
        print("\n" + "=" * 80)
        print("EXTRACTION SUMMARY")
        print("=" * 80)
        for qa in result['answers']:
            answer_preview = qa['student_answer'][:100] if qa['student_answer'] else "No answer"
            print(f"Q{qa['question_number']}: {answer_preview}...")
        print("=" * 80 + "\n")
        
    except FileNotFoundError:
        print(f"\n❌ Error: File '{pdf_path}' not found!")
        print("Please make sure the PDF file exists in the current directory.\n")
    except Exception as e:
        print(f"\n❌ Error during extraction: {e}\n")
        import traceback
        traceback.print_exc()
