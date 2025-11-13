"""
Handwritten answer sheet extraction using Mistral OCR.
Extracts question numbers and student answers from handwritten PDFs/images.
Based on the working Mistral API approach.
"""

import os
import re
import json
import logging
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
    
    Questions are identified by numbers followed by a period (e.g., "1.", "2.", "3.")
    The text between two questions is the answer for the question above.
    
    Handles duplicate question numbers by merging answers for the same question.
    
    Args:
        markdown_text: The markdown text extracted from OCR response
    
    Returns:
        List of dictionaries with question_number and student_answer
    """
    # Pattern to match question numbers at start of line: "1.", "2.", "10.", etc.
    question_pattern = r'^(\d+)\.\s'
    
    # Find all question numbers and their positions
    matches = list(re.finditer(question_pattern, markdown_text, re.MULTILINE))
    
    logger.info(f"Found {len(matches)} question markers")
    print(f"\n📋 Found {len(matches)} question markers")
    
    for match in matches:
        print(f"  - Question {match.group(1)} at position {match.start()}")
    
    if not matches:
        logger.warning("No questions found in the text")
        print("⚠️  No questions found in the text")
        return []
    
    # Extract questions and answers with positions
    raw_results = []
    for i, match in enumerate(matches):
        question_num = match.group(1)
        
        # The answer starts right after the match (which includes "N. ")
        answer_start = match.end()
        
        # Find the end of this question's answer
        # It's either the start of the next question or the end of the text
        if i + 1 < len(matches):
            answer_end = matches[i + 1].start()
        else:
            # Last question - answer goes to the end of the text
            answer_end = len(markdown_text)
        
        # Extract the answer text (everything between this question number and the next)
        answer_text = markdown_text[answer_start:answer_end].strip()
        
        raw_results.append({
            'question_number': question_num,
            'student_answer': answer_text,
            'position': match.start()
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
        
        # Use mistral-small-latest model
        model = "mistral-small-latest"
        
        print(f"\n🤖 Using model: {model}")
        logger.info(f"Using model: {model}")
        
        prompt_parser = PromptParser()
        prompt_template_path = os.path.join(
            prompt_parser.base_dir,
            "prompts/evaluation/handwritten-answer-sheet-extraction.json"
        )
        print(f"📝 Using prompt template: {prompt_template_path}")
        prompt_text = prompt_parser.render_prompt(
            prompt_template_path,
            {"file_id": uploaded_pdf.id}
        )
        logger.info(f"Prompt text: {prompt_text}")
        # Prepare messages with structured prompt
        messages = [
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": prompt_text
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
        
        # Call the Mistral API
        chat_response = client.chat.complete(
            model=model,
            messages=messages
        )
        
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
