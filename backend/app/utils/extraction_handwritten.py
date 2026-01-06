from mistralai import Mistral
import sys
import os
from dotenv import load_dotenv
import json
import re
import base64
import fitz  # PyMuPDF for PDF image extraction
from typing import Dict, Any
import logging
from pathlib import Path
from app.utils.prompt_parser import PromptParser
from app.services.openai_service import eval_hints
import traceback
load_dotenv()

# Use native Mistral API
api_key = os.getenv("MISTRAL_API_KEY")
if not api_key:
    raise ValueError("Please set the MISTRAL_API_KEY environment variable.")

client = Mistral(api_key=api_key)

def extract_images_from_pdf(pdf_path: str, output_dir: str = "temp_extracted_images", output_file=None):
    """
    Extract all images from a PDF file and save them to a directory.
    Then use the vision model to describe each image.
    
    Args:
        pdf_path: Path to the PDF file
        output_dir: Directory to save extracted images
        output_file: Optional file handle to write output to
    
    Returns:
        List of dictionaries with image descriptions and locations
    """
    try:
        # Create output directory if it doesn't exist
        os.makedirs(output_dir, exist_ok=True)
        
        msg = f"\n{'='*60}\nExtracting images from PDF: {pdf_path}\n{'='*60}"
        print(msg)
        if output_file:
            output_file.write(msg + "\n")
        
        # Open the PDF
        pdf_document = fitz.open(pdf_path)
        image_results = []
        image_count = 0
        
        # Iterate through each page
        for page_num in range(len(pdf_document)):
            page = pdf_document[page_num]
            image_list = page.get_images(full=True)
            
            if image_list:
                msg = f"\nPage {page_num + 1}: Found {len(image_list)} image(s)"
                print(msg)
                if output_file:
                    output_file.write(msg + "\n")
            
            # Extract each image from the page
            for img_index, img in enumerate(image_list):
                try:
                    xref = img[0]
                    base_image = pdf_document.extract_image(xref)
                    image_bytes = base_image["image"]
                    image_ext = base_image["ext"]
                    
                    # Save the image
                    image_count += 1
                    image_filename = f"page_{page_num + 1}_image_{img_index + 1}.{image_ext}"
                    image_path = os.path.join(output_dir, image_filename)
                    
                    with open(image_path, "wb") as img_file:
                        img_file.write(image_bytes)
                    
                    msg = f"  Saved: {image_filename}"
                    print(msg)
                    if output_file:
                        output_file.write(msg + "\n")
                    
                    # Use vision model to describe the image
                    msg = f"  Analyzing with vision model..."
                    print(msg)
                    if output_file:
                        output_file.write(msg + "\n")
                    
                    vision_result = describe_image_with_text(image_path, output_file=output_file)
                    
                    image_results.append({
                        'page_number': page_num + 1,
                        'image_index': img_index + 1,
                        'image_path': image_path,
                        'image_filename': image_filename,
                        'description': vision_result.get('description', ''),
                        'extracted_text': vision_result.get('extracted_text', ''),
                        'visual_elements': vision_result.get('visual_elements', ''),
                        'confidence': vision_result.get('confidence', 'N/A')
                    })
                    
                except Exception as e:
                    error_msg = f"  Error extracting image {img_index + 1} from page {page_num + 1}: {str(e)}"
                    print(error_msg)
                    if output_file:
                        output_file.write(error_msg + "\n")
        
        pdf_document.close()
        
        msg = f"\n{'='*60}\nTotal images extracted and analyzed: {image_count}\n{'='*60}"
        print(msg)
        if output_file:
            output_file.write(msg + "\n")
        
        return image_results
        
    except Exception as e:
        error_msg = f"Error extracting images from PDF: {str(e)}"
        print(error_msg)
        if output_file:
            output_file.write(error_msg + "\n")

        traceback.print_exc()
        return []

def enhance_text_with_image_descriptions(extracted_text: str, image_descriptions: list, output_file=None):
    """
    Enhance the extracted text by inserting detailed image descriptions where [IMAGE:...] markers appear.
    
    Args:
        extracted_text: The text extracted from PDF
        image_descriptions: List of image description dictionaries from extract_images_from_pdf
        output_file: Optional file handle to write output to
    
    Returns:
        Enhanced text with detailed image descriptions
    """
    if not image_descriptions:
        return extracted_text
    
    msg = f"\n{'='*60}\nEnhancing text with detailed image descriptions\n{'='*60}"
    print(msg)
    if output_file:
        output_file.write(msg + "\n")
    
    enhanced_text = extracted_text
    
    # For each image, try to find and enhance its description in the text
    for img_desc in image_descriptions:
        page_num = img_desc['page_number']
        
        # Create a detailed replacement description
        detailed_desc = f"""[IMAGE on Page {page_num}]
Description: {img_desc.get('description', 'N/A')}
Extracted Text from Image: {img_desc.get('extracted_text', 'None')}
Visual Elements: {img_desc.get('visual_elements', 'N/A')}
[END IMAGE]"""
        
        # Look for generic [IMAGE:...] markers and try to match by page
        # This is a simple approach - you might need to adjust based on how the model marks images
        pattern = rf'\[IMAGE:([^\]]*)\]'
        
        # Find all image markers
        matches = list(re.finditer(pattern, enhanced_text))
        
        if matches and img_desc['image_index'] <= len(matches):
            # Replace the generic marker with detailed description
            match_to_replace = matches[img_desc['image_index'] - 1]
            enhanced_text = (
                enhanced_text[:match_to_replace.start()] + 
                detailed_desc + 
                enhanced_text[match_to_replace.end():]
            )
    
    # If no [IMAGE:] markers were found, append all image descriptions at the end
    if '[IMAGE' not in extracted_text and image_descriptions:
        msg = "\nNo image markers found in extracted text. Appending image descriptions at the end."
        print(msg)
        if output_file:
            output_file.write(msg + "\n")
        
        enhanced_text += "\n\n" + "="*60 + "\n"
        enhanced_text += "EXTRACTED IMAGES WITH DETAILED DESCRIPTIONS\n"
        enhanced_text += "="*60 + "\n\n"
        
        for img_desc in image_descriptions:
            enhanced_text += f"""
Page {img_desc['page_number']}, Image {img_desc['image_index']}:
{'-'*40}
Description: {img_desc.get('description', 'N/A')}

Extracted Text: {img_desc.get('extracted_text', 'None')}

Visual Elements: {img_desc.get('visual_elements', 'N/A')}

Confidence: {img_desc.get('confidence', 'N/A')}
{'='*60}
"""
    
    return enhanced_text

def format_mark_scheme_context(mark_scheme: Dict[str, Any]) -> str:
    """
    Format mark scheme as readable text context for the extraction prompt.
    
    Args:
        mark_scheme: Dictionary with 'mark_scheme' key containing list of questions
        
    Returns:
        Formatted string representation of the mark scheme
    """
    if not mark_scheme or not mark_scheme.get('mark_scheme'):
        return ""
    
    questions = mark_scheme.get('mark_scheme', [])
    if not questions:
        return ""
    
    formatted_lines = []
    formatted_lines.append("=" * 60)
    formatted_lines.append("MARK SCHEME CONTEXT")
    formatted_lines.append("=" * 60)
    formatted_lines.append("\nUse this mark scheme as context to better understand what questions and answers to expect in the answer sheet.\n")
    formatted_lines.append("This will help you identify questions correctly and extract answers more accurately.\n")
    formatted_lines.append("=" * 60)
    formatted_lines.append("")
    
    for question in questions:
        qnum = question.get('questionnumber') or question.get('question_number') or 'N/A'
        qtext = question.get('question-text') or question.get('question_text') or question.get('question', '')
        answer_template = question.get('answertemplate') or question.get('answer_template') or question.get('answer', '')
        marking_scheme = question.get('markingscheme') or question.get('marking_scheme') or []
        
        formatted_lines.append(f"Question {qnum}:")
        formatted_lines.append("-" * 40)
        
        if qtext:
            formatted_lines.append(f"Question Text: {qtext}")
        
        if answer_template:
            formatted_lines.append(f"Answer Template: {answer_template}")
        
        if marking_scheme:
            formatted_lines.append("Marking Scheme:")
            if isinstance(marking_scheme, list):
                for item in marking_scheme:
                    formatted_lines.append(f"  - {item}")
            else:
                formatted_lines.append(f"  - {marking_scheme}")
        
        formatted_lines.append("")
    
    formatted_lines.append("=" * 60)
    formatted_lines.append("END OF MARK SCHEME CONTEXT")
    formatted_lines.append("=" * 60)
    
    return "\n".join(formatted_lines)


def parse_per_question_confidence(text: str, output_file=None):
    """
    Parse per-question confidence scores from the text.
    
    Looks for patterns like:
    - "QUESTION 1 CONFIDENCE: 85 / 100"
    - "QUESTION 1 CONFIDENCE: 85/100"
    - "QUESTION 1 CONFIDENCE: 85"
    
    Args:
        text: The text containing confidence scores
        output_file: Optional file handle to write output to
    
    Returns:
        Dictionary mapping question numbers (as strings) to confidence scores (as strings)
    """
    confidence_dict = {}
    
    msg = f"\nSearching for per-question confidence scores in text (length: {len(text)} characters)"
    print(msg)
    if output_file:
        output_file.write(msg + "\n")
    
    # Pattern to match: QUESTION N CONFIDENCE: X / 100 or QUESTION N CONFIDENCE: X/100 or QUESTION N CONFIDENCE: X
    # More flexible patterns to catch variations
    patterns = [
        r'QUESTION\s+(\d+)\s+CONFIDENCE[:\s]+(\d+(?:\.\d+)?)\s*(?:/|\s*out\s*of\s*)?\s*(?:100)?',
        r'QUESTION\s+(\d+)\s+CONFIDENCE[:\s]+(\d+(?:\.\d+)?)',
        r'Question\s+(\d+)\s+Confidence[:\s]+(\d+(?:\.\d+)?)\s*(?:/|\s*out\s*of\s*)?\s*(?:100)?',
        r'Question\s+(\d+)\s+Confidence[:\s]+(\d+(?:\.\d+)?)',
    ]
    
    # Search the ENTIRE text, not just a section
    for pattern in patterns:
        matches = re.finditer(pattern, text, re.IGNORECASE | re.MULTILINE)
        for match in matches:
            question_num = match.group(1)
            confidence_score = match.group(2)
            # Only add if not already found (avoid duplicates)
            if question_num not in confidence_dict:
                confidence_dict[question_num] = confidence_score
                
                msg = f"  ✓ Found confidence for Question {question_num}: {confidence_score}"
                print(msg)
                if output_file:
                    output_file.write(msg + "\n")
    
    if not confidence_dict:
        msg = "  ⚠ No per-question confidence scores found in the text"
        print(msg)
        if output_file:
            output_file.write(msg + "\n")
        # Debug: show a sample of the text where we'd expect to find confidence scores
        if "CONFIDENCE" in text.upper():
            # Find where confidence appears
            idx = text.upper().rfind("CONFIDENCE")
            sample = text[max(0, idx-100):min(len(text), idx+500)]
            msg = f"  Debug: Found 'CONFIDENCE' in text. Sample around it:\n{sample[:300]}..."
            print(msg)
            if output_file:
                output_file.write(msg + "\n")
    else:
        msg = f"  ✓ Successfully extracted {len(confidence_dict)} per-question confidence score(s)"
        print(msg)
        if output_file:
            output_file.write(msg + "\n")
    
    return confidence_dict


def extract_handwritten_answers(pdf_path: str, answers_only: bool = True, mark_scheme_context: Dict[str, Any] = None) -> Dict[str, Any]:
    """
    High-level API used by the evaluation pipeline.
    
    - Runs the Mistral multimodal model over the handwritten PDF
    - Parses question/answer pairs in sequential order (1., 2., 3., ...)
    - Extracts per-question and overall confidence scores
    - Uses mark scheme context to improve extraction accuracy
    - Returns a structure compatible with the evaluation flow:
      {
        "email": None,
        "answers": [
          {"question_number": "1", "student_answer": "...", "confidence_score": "85"},
          ...
        ],
        "confidence": {"score": "88", "details": "...raw confidence section..."}
      }
    
    Args:
        pdf_path: Path to the handwritten answer sheet PDF
        answers_only: If True, returns simplified format with only answers
        mark_scheme_context: Optional mark scheme dictionary with 'mark_scheme' key for context
    """
    # 1) Render PDF pages to high-res images and encode as base64
    pdf_document = fitz.open(pdf_path)
    pdf_images = []
    for page_num in range(len(pdf_document)):
        page = pdf_document[page_num]
        mat = fitz.Matrix(3, 3)  # 300 DPI-ish
        pix = page.get_pixmap(matrix=mat)
        img_bytes = pix.tobytes("png")
        img_base64 = base64.b64encode(img_bytes).decode("utf-8")
        pdf_images.append(img_base64)
    pdf_document.close()

    # 2) Get eval hints context if mark scheme is provided
    extracted_questions = ""
    eval_hints_formatted = ""
    if mark_scheme_context:
        # Extract questions from mark_scheme_context
        questions = mark_scheme_context.get('mark_scheme', [])
        logging.info(f"Mark scheme context: {questions}")
        if questions:
            # Format questions as simple text for eval_hints
            question_lines = []
            for question in questions:
                qnum = question.get('questionnumber') or question.get('question_number') or 'N/A'
                qtext = question.get('question-text') or question.get('question_text') or question.get('question', '')
                if qtext:
                    question_lines.append(f"Question {qnum}: {qtext}")
            extracted_questions = "\n".join(question_lines)
            logging.info(f"Extracted {len(questions)} questions from mark scheme: {(extracted_questions)} characters")
    
    if extracted_questions:
        # Get eval hints using the eval_hints function
        try:
            eval_hints_output = eval_hints(extracted_questions)
            logging.info(f"Eval hints generated: {(eval_hints_output)} characters")
            # Format with header for prompt inclusion
            eval_hints_formatted = (
                "---\n\n"
                "## EVAL HINTS CONTEXT\n\n"
                "IMPORTANT: The following evaluation hints are provided as context to help you better understand the questions and expected answer format. "
                "Use this information to:\n"
                "- Identify questions correctly by matching question numbers and text\n"
                "- Understand the expected answer format and structure\n"
                "- Better interpret handwritten answers in context\n"
                "- Ensure you extract all questions that are present in the hints\n\n"
                f"{eval_hints_output}\n\n"
            )
        except Exception as e:
            logging.error(f"Error generating eval hints: {str(e)}")
            # If eval_hints fails, leave eval_hints_formatted as empty string
            eval_hints_formatted = ""
    
    # 3) Load prompt from JSON file using PromptParser
    # Use PromptParser's path resolution which works in both development and production
    # It uses __file__ to resolve paths relative to backend/app, regardless of working directory
    prompt_parser = PromptParser()
    input_variables = {}
    if eval_hints_formatted:
        input_variables["eval_hints_context"] = eval_hints_formatted
    
    # Resolve path using PromptParser's _get_prompt_path which handles production paths correctly
    # This uses os.path.abspath(__file__) internally, so it works regardless of where the script is run from
    prompt_path = prompt_parser._get_prompt_path("prompts/evaluation/handwritten-answer-sheet-extraction.json")
    
    # Verify the path exists before attempting to load (better error message)
    if not os.path.exists(prompt_path):
        error_msg = (
            f"Prompt template file not found: {prompt_path}\n"
            f"Base directory: {prompt_parser.base_dir}\n"
            f"Current working directory: {os.getcwd()}\n"
            f"Expected location: {os.path.join(prompt_parser.base_dir, 'prompts/evaluation/handwritten-answer-sheet-extraction.json')}"
        )
        logging.error(error_msg)
        raise FileNotFoundError(error_msg)
    
    system_prompt = prompt_parser.render_prompt(prompt_path, input_variables)
    
    # Log the final prompt for debugging
    logging.info(f"Final prompt length: {len(system_prompt)} characters")
    if eval_hints_formatted:
        logging.info("Eval hints context included in prompt")
    print("\n" + "="*80)
    print("FINAL HANDWRITTEN EXTRACTION PROMPT (with mark scheme context)")
    print("="*80)
    print(system_prompt)
    print("="*80 + "\n")

    content_items = [
        {
            "type": "text",
            "text": system_prompt,
        }
    ]

    # Attach each rendered page as an image
    for img_base64 in pdf_images:
        content_items.append(
            {
                "type": "image_url",
                "image_url": f"data:image/png;base64,{img_base64}",
            }
        )

    messages = [
        {
            "role": "user",
            "content": content_items,
        }
    ]

    # 4) Call Mistral multimodal chat API
    chat_response = client.chat.complete(model="mistral-large-latest", messages=messages)

    extracted_text = ""
    if hasattr(chat_response, "choices") and chat_response.choices:
        for choice in chat_response.choices:
            if hasattr(choice, "message") and hasattr(choice.message, "content"):
                extracted_text += choice.message.content + "\n"

    # Preserve the full raw chat response before trimming confidence sections
    raw_chat_response = extracted_text

    # 5) Parse per-question confidence BEFORE trimming confidence section
    per_question_confidence = parse_per_question_confidence(extracted_text)

    # 6) Extract overall confidence section and trim it from main text
    confidence_score = "N/A"
    confidence_details = ""
    confidence_section_start = None

    confidence_header_patterns = [
        r"\*\*CONFIDENCE\s+SCORES?\*\*:",
        r"CONFIDENCE\s+SCORES?:",
        r"---\s*CONFIDENCE\s+SCORES\s*---",
        r"CONFIDENCE SCORES",
    ]

    for pattern in confidence_header_patterns:
        match = re.search(pattern, extracted_text, re.IGNORECASE | re.MULTILINE)
        if match:
            confidence_section_start = match.start()
            break

    if confidence_section_start is not None:
        confidence_details = extracted_text[confidence_section_start:].strip()
        total_match = re.search(
            r"TOTAL\s+CONFIDENCE\s+SCORE[:\s]+(\d+(?:\.\d+)?)",
            confidence_details,
            re.IGNORECASE,
        )
        if total_match:
            confidence_score = total_match.group(1)
        else:
            overall_patterns = [
                r"(?:TOTAL\s+)?confidence\s*(?:score)?[:\s]*(\d+(?:\.\d+)?)\s*(?:/|\s*out\s*of\s*)?\s*(?:100)?",
                r"(\d+(?:\.\d+)?)\s*(?:/|\s*out\s*of\s*)\s*100\s*(?:confidence|confidence\s*score)",
            ]
            for pattern in overall_patterns:
                match = re.search(pattern, confidence_details, re.IGNORECASE)
                if match:
                    confidence_score = match.group(1)
                    break

        extracted_text = extracted_text[:confidence_section_start].rstrip()
    else:
        # Fallback: look near the end for an overall confidence score
        end_section = extracted_text[-800:] if len(extracted_text) > 800 else extracted_text
        confidence_match = re.search(
            r"(?:TOTAL\s+)?confidence\s*(?:score)?[:\s]*(\d+(?:\.\d+)?)\s*(?:/|\s*out\s*of\s*)?\s*(?:100)?",
            end_section,
            re.IGNORECASE,
        )
        if confidence_match:
            confidence_score = confidence_match.group(1)
            confidence_section_start = len(extracted_text) - len(end_section) + confidence_match.start()
            confidence_details = extracted_text[confidence_section_start:].strip()
            extracted_text = extracted_text[:confidence_section_start].rstrip()

    # Extra safety: if any "CONFIDENCE SCORES" text slipped through, cut it
    fallback_conf_idx = extracted_text.upper().find("CONFIDENCE SCORES")
    if fallback_conf_idx != -1:
        confidence_details = extracted_text[fallback_conf_idx:].strip()
        extracted_text = extracted_text[:fallback_conf_idx].rstrip()

    # 7) Parse questions/answers from the remaining text
    questions_answers = parse_questions_and_answers(extracted_text)

    # Attach per-question confidence where available
    for qa in questions_answers:
        qnum = qa.get("question_number")
        qa["confidence_score"] = per_question_confidence.get(qnum, "N/A") if qnum else "N/A"

    # 8) Build evaluation-friendly structure
    if answers_only:
        answers = [
            {
                "question_number": qa.get("question_number"),
                "student_answer": qa.get("student_answer"),
                "confidence_score": qa.get("confidence_score"),
            }
            for qa in questions_answers
            if qa.get("question_number") is not None
        ]
        return {
            "email": None,
            "answers": answers,
            "confidence": {
                "score": confidence_score,
                "details": confidence_details,
            },
            # Expose raw chat response so CLI/debug tooling can print it,
            # but callers can ignore it if they don't need it.
            "raw_chat_response": raw_chat_response,
        }

    # Non-answers_only mode: return richer raw structure (not currently used in evaluation)
    return {
        "email": None,
        "questions": questions_answers,
        "confidence": {
            "score": confidence_score,
            "details": confidence_details,
        },
        "raw_chat_response": raw_chat_response,
    }

def parse_questions_and_answers(markdown_text: str, output_file=None):
    """
    Parse questions and answers from markdown text with SEQUENTIAL ORDERING.
    
    Questions must be in sequential order (1, 2, 3, 4...). If a question number
    appears out of sequence (e.g., 5 appears before 2), it will be skipped until
    the proper sequence is established.
    
    Questions are identified by numbers followed by a period (e.g., "1.", "2.", "3.")
    The text between two questions is the answer for the question above.
    
    Args:
        markdown_text: The markdown text extracted from OCR response
        output_file: Optional file handle to write output to
    
    Returns:
        List of dictionaries with question_number and student_answer (in sequential order)
    """
    # Pattern to match question numbers at start of line: "1.", "2.", "10.", etc.
    # ^(\d+)\. matches number + period at start of line with MULTILINE flag
    question_pattern = r'^(\d+)\.\s'
    
    # Find all question numbers and their positions
    matches = list(re.finditer(question_pattern, markdown_text, re.MULTILINE))
    
    msg = f"\nStep 1: Found {len(matches)} question number matches"
    print(msg)
    if output_file:
        output_file.write(msg + "\n")
    
    for match in matches:
        msg = f"  - Question {match.group(1)} at position {match.start()}"
        print(msg)
        if output_file:
            output_file.write(msg + "\n")
    
    if not matches:
        msg = "  No questions found in the text"
        print(msg)
        if output_file:
            output_file.write(msg + "\n")
        return []
    
    # First pass: Identify sequential questions and their positions
    sequential_questions = []  # List of (question_num, match_object) tuples
    expected_question_num = 1  # Start expecting question 1
    skipped_questions = []
    
    msg = f"\nStep 2: Filtering for sequential questions (starting from {expected_question_num})"
    print(msg)
    if output_file:
        output_file.write(msg + "\n")
    
    for match in matches:
        question_num_str = match.group(1)
        question_num = int(question_num_str)
        
        if question_num == expected_question_num:
            # This is the expected question - add it to sequential list
            sequential_questions.append((question_num, match))
            msg = f"  ✓ Found sequential Question {question_num_str} at position {match.start()}"
            print(msg)
            if output_file:
                output_file.write(msg + "\n")
            # Move to next expected question
            expected_question_num += 1
        elif question_num > expected_question_num:
            # This question is ahead of expected sequence - skip it
            skipped_questions.append(question_num_str)
            msg = f"  ✗ Skipping Question {question_num_str} (expected {expected_question_num}, will process when sequence is correct)"
            print(msg)
            if output_file:
                output_file.write(msg + "\n")
        else:
            # This question is behind expected sequence (duplicate or already processed)
            msg = f"  ✗ Skipping Question {question_num_str} (already processed or duplicate, expected {expected_question_num})"
            print(msg)
            if output_file:
                output_file.write(msg + "\n")
    
    # Second pass: Extract answers for sequential questions
    # For each sequential question, the answer goes from after the question number
    # until the next sequential question appears (or end of text)
    result = []
    
    msg = f"\nStep 3: Extracting answers for {len(sequential_questions)} sequential question(s)"
    print(msg)
    if output_file:
        output_file.write(msg + "\n")
    
    for i, (question_num, match) in enumerate(sequential_questions):
        question_num_str = str(question_num)
        
        # The answer starts right after the match (which includes "N. ")
        answer_start = match.end()
        
        # Find the end of this question's answer
        # Look for the NEXT sequential question in the text
        if i + 1 < len(sequential_questions):
            # Next sequential question exists - answer ends at its start
            next_question_match = sequential_questions[i + 1][1]
            answer_end = next_question_match.start()
        else:
            # Last sequential question - answer goes to the end of the text
            answer_end = len(markdown_text)
        
        # Extract the answer text (everything between this question number and the next sequential question)
        answer_text = markdown_text[answer_start:answer_end].strip()

        # NEW: Treat a line containing only '---' as an explicit question breaker.
        # If present, everything after the first such line belongs to the next question
        # (or is ignored for this question).
        lines = answer_text.splitlines()
        trimmed_lines = []
        for line in lines:
            if line.strip() == "---":
                break
            trimmed_lines.append(line)
        answer_text = "\n".join(trimmed_lines).strip()
        
        result.append({
            'question_number': question_num_str,
            'student_answer': answer_text
        })
        
        msg1 = f"\n  ✓ Processing Question {question_num_str}"
        msg2 = f"    Answer start: {answer_start}, Answer end: {answer_end}"
        msg3 = f"    Answer length: {len(answer_text)} characters"
        msg4 = f"    Answer preview: {answer_text[:150]}..." if len(answer_text) > 150 else f"    Answer: {answer_text}"
        
        print(msg1)
        print(msg2)
        print(msg3)
        print(msg4)
        
        if output_file:
            output_file.write(msg1 + "\n")
            output_file.write(msg2 + "\n")
            output_file.write(msg3 + "\n")
            output_file.write(msg4 + "\n")
    
    if skipped_questions:
        msg = f"\nStep 4: Summary - Skipped {len(skipped_questions)} out-of-sequence question(s): {', '.join(skipped_questions)}"
        print(msg)
        if output_file:
            output_file.write(msg + "\n")
    
    msg = f"\nStep 5: Final result - {len(result)} sequential question(s) processed"
    print(msg)
    if output_file:
        output_file.write(msg + "\n")
    
    return result

def describe_image_with_text(image_path: str, output_file=None):
    """
    Convert an image into a detailed, accurate text description.
    Focuses on extracting and representing all text content in the image.
    
    Args:
        image_path: Path to the image file (JPEG, PNG, etc.)
        output_file: Optional file handle to write output to
    
    Returns:
        Dictionary with:
        - 'image_path': Original image path
        - 'description': Detailed description of the image
        - 'extracted_text': Text content extracted from the image
        - 'confidence': Confidence level of the extraction
    """
    try:
        msg = f"\n{'='*60}\nProcessing Image: {image_path}\n{'='*60}"
        print(msg)
        if output_file:
            output_file.write(msg + "\n")
        
        # Read and encode the image in base64
        with open(image_path, "rb") as img_file:
            image_data = base64.b64encode(img_file.read()).decode('utf-8')
        
        # Determine image format from file extension
        file_extension = os.path.splitext(image_path)[1].lower()
        mime_type_map = {
            '.jpg': 'image/jpeg',
            '.jpeg': 'image/jpeg',
            '.png': 'image/png',
            '.gif': 'image/gif',
            '.webp': 'image/webp'
        }
        mime_type = mime_type_map.get(file_extension, 'image/jpeg')
        
        # Create the image URL for Mistral API
        image_url = f"data:{mime_type};base64,{image_data}"
        
        # Use Mistral vision model to analyze the image
        model = "mistral-large-latest"  # Mistral's multimodal model
        
        messages = [
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": """Analyze this image carefully and provide:

1. A detailed, accurate description of what you see in the image
2. Extract ALL text content visible in the image with perfect accuracy
3. Describe the layout, formatting, and structure of the text
4. Include any mathematical symbols, diagrams, charts, or special characters exactly as they appear
5. Note the context and purpose of the image (e.g., is it a worksheet, diagram, form, etc.)

Your response should be a perfect representation of all text and visual content in the image. Do not miss any text, numbers, symbols, or important visual elements.

Format your response as:

**IMAGE DESCRIPTION:**
[Provide a comprehensive description of the image]

**EXTRACTED TEXT:**
[Provide all text content exactly as it appears, maintaining formatting and structure]

**VISUAL ELEMENTS:**
[Describe any diagrams, charts, drawings, or non-text elements]

**CONFIDENCE SCORE:**
[Provide a confidence score from 0-100 for the accuracy of your extraction]"""
                    },
                    {
                        "type": "image_url",
                        "image_url": image_url  # Already in format: data:image/jpeg;base64,...
                    }
                ]
            }
        ]
        
        print("\nSending image to Mistral Vision API...")
        if output_file:
            output_file.write("\nSending image to Mistral Vision API...\n")
        
        # Call the Mistral API
        chat_response = client.chat.complete(
            model=model,
            messages=messages
        )
        
        # Extract the response
        response_text = ""
        if hasattr(chat_response, 'choices') and chat_response.choices:
            for choice in chat_response.choices:
                if hasattr(choice, 'message') and hasattr(choice.message, 'content'):
                    response_text += choice.message.content
        
        print("\nImage Analysis Complete!")
        print("-" * 60)
        print(response_text)
        print("-" * 60)
        
        if output_file:
            output_file.write("\nImage Analysis Complete!\n")
            output_file.write("-" * 60 + "\n")
            output_file.write(response_text + "\n")
            output_file.write("-" * 60 + "\n")
        
        # Parse the response to extract components
        extracted_text = ""
        description = ""
        visual_elements = ""
        confidence = "N/A"
        
        # Simple parsing of the structured response
        if "**EXTRACTED TEXT:**" in response_text:
            parts = response_text.split("**EXTRACTED TEXT:**")
            if len(parts) > 1:
                text_part = parts[1].split("**VISUAL ELEMENTS:**")[0] if "**VISUAL ELEMENTS:**" in parts[1] else parts[1]
                extracted_text = text_part.strip()
        
        if "**IMAGE DESCRIPTION:**" in response_text:
            parts = response_text.split("**IMAGE DESCRIPTION:**")
            if len(parts) > 1:
                desc_part = parts[1].split("**EXTRACTED TEXT:**")[0] if "**EXTRACTED TEXT:**" in parts[1] else parts[1]
                description = desc_part.strip()
        
        if "**VISUAL ELEMENTS:**" in response_text:
            parts = response_text.split("**VISUAL ELEMENTS:**")
            if len(parts) > 1:
                visual_part = parts[1].split("**CONFIDENCE SCORE:**")[0] if "**CONFIDENCE SCORE:**" in parts[1] else parts[1]
                visual_elements = visual_part.strip()
        
        if "**CONFIDENCE SCORE:**" in response_text:
            parts = response_text.split("**CONFIDENCE SCORE:**")
            if len(parts) > 1:
                confidence = parts[1].strip()
        
        result = {
            'image_path': image_path,
            'full_response': response_text,
            'description': description,
            'extracted_text': extracted_text,
            'visual_elements': visual_elements,
            'confidence': confidence
        }
        
        return result
        
    except Exception as e:
        error_msg = f"Error processing image {image_path}: {str(e)}"
        print(error_msg)
        if output_file:
            output_file.write(error_msg + "\n")
        traceback.print_exc()
        if output_file:
            output_file.write(traceback.format_exc() + "\n")
        return {
            'image_path': image_path,
            'error': str(e),
            'full_response': '',
            'description': '',
            'extracted_text': '',
            'visual_elements': '',
            'confidence': 'N/A'
        }

def split_into_qas_mistral(
    pdf_path: str,
    answers_only: bool = True,
    mark_scheme_context: Dict[str, Any] = None
) -> Dict[str, any]:
    """
    Alternative interface matching extraction_answersheet.py.
    
    Args:
        pdf_path: Path to PDF file
        answers_only: Returns simplified format
        mark_scheme_context: Optional mark scheme dictionary with 'mark_scheme' key for context
        
    Returns:
        Dict with format: {"email": str or None, "answers": [{"question_number": str, "student_answer": str}, ...]}
    """
    return extract_handwritten_answers(pdf_path, answers_only=answers_only, mark_scheme_context=mark_scheme_context)
