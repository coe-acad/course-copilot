from mistralai import Mistral
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
        import traceback
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

    # 2) Format mark scheme context if provided
    mark_scheme_formatted = ""
    if mark_scheme_context:
        mark_scheme_text = format_mark_scheme_context(mark_scheme_context)
        logging.info(f"Mark scheme context provided: {len(mark_scheme_text)} characters")
        # Format with header for prompt inclusion
        mark_scheme_formatted = (
            "---\n\n"
            "## MARK SCHEME CONTEXT\n\n"
            "IMPORTANT: The following mark scheme is provided as context to help you better understand the questions and expected answer format. "
            "Use this information to:\n"
            "- Identify questions correctly by matching question numbers and text\n"
            "- Understand the expected answer format and structure\n"
            "- Better interpret handwritten answers in context\n"
            "- Ensure you extract all questions that are present in the mark scheme\n\n"
            f"{mark_scheme_text}\n\n"
        )
    
    # 3) Load prompt from JSON file using PromptParser
    # Use PromptParser's path resolution which works in both development and production
    # It uses __file__ to resolve paths relative to backend/app, regardless of working directory
    prompt_parser = PromptParser()
    input_variables = {}
    if mark_scheme_formatted:
        input_variables["mark_scheme_context"] = mark_scheme_formatted
    
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
    if mark_scheme_formatted:
        logging.info("Mark scheme context included in prompt")
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
        import traceback
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

if __name__ == "__main__":
    # PDF Processing Mode
    pdf_path = "handwritten answersheet.pdf"  # Updated to the latest file
    output_file = "output.txt"
    
    # Open output file for writing
    with open(output_file, 'w', encoding='utf-8') as f:
        try:
            print("=" * 80)
            print("STEP 0: Processing PDF with Mistral API")
            print("=" * 80)
            f.write("=" * 80 + "\n")
            f.write("STEP 0: Processing PDF with Mistral API\n")
            f.write("=" * 80 + "\n\n")
            
            # Convert PDF to images (Mistral doesn't support document_url directly)
            print("\nConverting PDF pages to images...")
            f.write("\nConverting PDF pages to images...\n")
            
            pdf_document = fitz.open(pdf_path)
            pdf_images = []
            
            for page_num in range(len(pdf_document)):
                page = pdf_document[page_num]
                # Render at high resolution (300 DPI)
                mat = fitz.Matrix(3, 3)
                pix = page.get_pixmap(matrix=mat)
                
                # Convert to base64
                img_bytes = pix.tobytes("png")
                img_base64 = base64.b64encode(img_bytes).decode('utf-8')
                pdf_images.append(img_base64)
                
                print(f"  Converted page {page_num + 1}/{len(pdf_document)}")
                f.write(f"  Converted page {page_num + 1}/{len(pdf_document)}\n")
            
            pdf_document.close()
            print(f"✓ Converted {len(pdf_images)} pages to images\n")
            f.write(f"✓ Converted {len(pdf_images)} pages to images\n\n")
            
            # Choose model
            model = "mistral-large-latest"  # Mistral's multimodal model for PDF processing
            
            print(f"\nUsing model: {model}")
            f.write(f"\nUsing model: {model}\n")
            
            # Build content with all PDF pages as images
            content_items = [
                {
                    "type": "text",
                    "text": "You are a specialized OCR system designed for extracting content from handwritten academic answer sheets with maximum accuracy. Your task is to extract ALL visible content EXACTLY as it appears, maintaining the original layout, structure, and sequential order.\n\n---\n\n## CORE PRINCIPLES\n\nCRITICAL: Extract content in the EXACT sequence it appears in the document:\n- Top to bottom, left to right progression\n- Page by page in order\n- NO rearranging, regrouping, or summarizing\n- ALL elements (text, images, tables, diagrams) must appear inline at their exact position\n\n---\n\n## TEXT EXTRACTION RULES\n\n### Character-Level Accuracy\n- Extract every character, word, and symbol exactly as written\n- DO NOT correct spelling, grammar, or formatting errors\n- DO NOT standardize or clean up the text\n- Preserve original writing style and quirks\n\n### Preserve All Formatting\n- Original line breaks, spacing, and indentation\n- Headers, footers, watermarks, page numbers\n- Question numbers, bullet points, subpoints, section markers\n- Heading hierarchy (main headings → subheadings → sub-subheadings)\n- Natural reading flow and document structure\n\n### Handwriting-Specific Guidelines\n- When text is ambiguous or unclear, make your best interpretation\n- For illegible or highly uncertain text, use: [UNCERTAIN: possible_text]\n- Preserve strikethroughs, corrections, and insertions (use ^word^ for insertions, word for strikethroughs)\n- Maintain spacing between words as perceived\n- Note significant pressure variations or emphasis if visible\n\n---\n\n## INLINE IMAGE AND DIAGRAM HANDLING\n\n### Critical Rule: Inline Placement\nWhen you encounter ANY visual element, insert its description at that EXACT position in the document flow. Never move visuals to the end.\n\n### Image vs. Table Distinction\nTreat as IMAGE if:\n- Flowcharts with arrows and decision points\n- Diagrams with labels and relationships\n- Charts/graphs (bar charts, pie charts, line graphs, scatter plots)\n- Illustrations, drawings, or sketches\n- Photos or complex visual layouts\n- Any visual without clear row-column grid structure\n\nTreat as TABLE only if:\n- Clear rectangular grid with visible or implied borders\n- Defined rows and columns with consistent structure\n- Data organized in cells with clear alignment\n- Header row typically present\n\n### Image Description Format\n[IMAGE DESCRIPTION: Provide detailed structural description focusing on layout, relationships, and visual elements. Describe shapes, arrows, connections, spatial arrangement, and overall organization.\n\nTEXT IN IMAGE: Extract all visible text, labels, numbers, and annotations exactly as they appear. Use bullet points for multiple labels.\n\nIMAGE TYPE: Specify one - diagram | flowchart | bar_chart | line_graph | pie_chart | scatter_plot | illustration | sketch | photo | complex_visual\n\nIMAGE CONTEXT: Identify which question number, section, or concept this visual relates to]\n\nThen immediately continue with the text that follows.\n\n---\n\n## INLINE TABLE HANDLING\n\n### Table Detection Criteria\nOnly mark as a table if there is:\n- Clear grid structure with rows and columns\n- Consistent cell boundaries (visible or strongly implied)\n- Tabular data organization\n- Header row typically present\n\n### Table Description Format\nWhen you encounter a table, provide ONLY a detailed description at the exact position where it appears. Do NOT rewrite the full table text and do NOT recreate it in markdown.\n\n[TABLE DESCRIPTION: Provide comprehensive structural description focusing on layout, organization, and data relationships. Describe:\n- Number of rows and columns\n- Header structure and column purposes\n- Data organization pattern (e.g., comparison table, data table, calculation table)\n- Any special formatting, merged cells, or visual emphasis\n- Overall purpose and context of the table\n\nTABLE TYPE: Specify one - data_table | comparison_table | calculation_table | reference_table | summary_table | other\n\nTABLE CONTEXT: Identify which question number, section, or concept this table relates to]\n\nThen immediately continue with the next handwritten content in order.\n\n---\n\n## MATHEMATICAL CONTENT EXTRACTION\n\n### Equations and Formulas\n- Use Unicode for special characters: ×, ÷, ±, ≤, ≥, ≠, √, ∞, ∫, ∑, π, θ\n- Superscripts: x², a³, e^(2x)\n- Subscripts: H₂O, x₁, aₙ\n- Fractions: Use (numerator)/(denominator) or proper notation based on clarity\n- Maintain alignment for multi-line equations\n\n### Mathematical Expressions in Handwriting\n- If notation is ambiguous, provide best interpretation\n- Use [UNCERTAIN: x² or x³] for unclear exponents\n- Preserve work shown, including crossed-out attempts\n\n---\n\n## STRUCTURAL ELEMENT PRESERVATION\n\nMaintain all structural elements exactly:\n- Numbering systems: 1., 2., (a), (b), i., ii., etc.\n- Bullet types: •, ○, ■, -, →, *, etc.\n- Question-answer layouts and spacing\n- Bold emphasis (use text if detectable)\n- Underlines and emphasis markers\n- Visual separators: dashes, lines, brackets\n- Margins and indentation levels\n\n---\n\n## ERROR HANDLING AND UNCERTAINTY MARKING\n\n### Uncertainty Markers\nUse these markers to flag extraction issues:\n\n- [UNCERTAIN: possible_text] - Text is unclear but this is the best interpretation\n- [ILLEGIBLE] - Text cannot be reliably read\n- [UNCLEAR_WORD] - Single word is unreadable\n- [SMUDGED] - Content is smudged or damaged\n- [FADED] - Content is too faint to read confidently\n- [PARTIAL: visible_portion...] - Only part of the content is readable\n\n### Impact on Confidence Score\n- Each uncertainty marker reduces text accuracy component\n- Multiple uncertainties in critical areas (question answers) have higher impact\n- Document overall legibility affects handwriting confidence score\n\n---\n\n## CONFIDENCE SCORING SYSTEM\n\nAt the end of your extraction, provide a detailed confidence assessment:\n\n### Scoring Components\n\n| Component | Weight | Evaluation Criteria |\n|-----------|--------|---------------------|\n| Text Accuracy | 40% | Character recognition precision, proper handling of handwriting variations, minimal [UNCERTAIN] markers, correct preservation of formatting and alignment |\n| Visual Element Handling | 25% | Correct identification of images vs. tables, accurate inline placement, comprehensive structural descriptions, complete text extraction from visuals |\n| Table Structure Accuracy | 20% | Accurate detection of true tables (no false positives from charts), complete row-column preservation, proper markdown formatting, data integrity |\n| Handwriting Legibility | 15% | Overall clarity of handwriting, confidence in character interpretation, frequency of uncertain extractions, writing consistency |\n\n### Per-Question Confidence Scores\n\nCRITICAL FORMATTING REQUIREMENT: For EACH question extracted, you MUST provide an individual confidence score using the EXACT format specified below. This exact format is required for automated parsing and must be followed precisely.\n\nREQUIRED FORMAT (use this EXACT format for each question - this is mandatory):\n\nQUESTION [N] CONFIDENCE: [X] / 100\n\nWhere:\n- [N] is the question number as an integer (1, 2, 3, 4, etc.)\n- [X] is the confidence score as a number (0-100, can include decimals like 85.5)\n- The format must be: \"QUESTION\" (all caps) followed by a space, then the question number, then a space, then \"CONFIDENCE:\" (all caps), then a space, then the score, optionally followed by \" / 100\"\n\nValid format examples (any of these will work):\n- QUESTION 1 CONFIDENCE: 85 / 100\n- QUESTION 2 CONFIDENCE: 92/100\n- QUESTION 3 CONFIDENCE: 87.5 / 100\n- QUESTION 4 CONFIDENCE: 90\n\nIMPORTANT PLACEMENT: Place all per-question confidence scores in a dedicated section at the END of your response, after all question content but BEFORE the overall/total confidence score section. This ensures proper parsing.\n\nBREAKDOWN FOR QUESTION [N]:\n- Text Accuracy: [X]/40 - [Brief note on text quality for this question]\n- Visual Elements: [X]/25 - [Note on any images/diagrams in this question]\n- Table Structure: [X]/20 - [Note on any tables in this question]\n- Handwriting Legibility: [X]/15 - [Note on handwriting clarity for this question]\n\nISSUES FOR QUESTION [N]:\n- [List any specific difficulties, uncertainties, or challenges for this question]\n\nMANDATORY: Repeat this format for ALL questions found in the document (Question 1, Question 2, Question 3, etc.). You MUST provide a confidence score for EVERY SINGLE question you extract.\n\nCRITICAL REQUIREMENT: If you extract 5 questions, you MUST provide exactly 5 confidence scores (one for Question 1, one for Question 2, one for Question 3, one for Question 4, and one for Question 5). If you extract 10 questions, you MUST provide exactly 10 confidence scores. There is NO exception to this rule - every question MUST have its own confidence score.\n\nMissing confidence scores will result in \"N/A\" being assigned to those questions, which indicates incomplete extraction. Your response is incomplete and unacceptable if you do not provide confidence scores for ALL questions..\n\n### Overall Confidence Score Format\n\nTOTAL CONFIDENCE SCORE: [X] / 100\n\nOVERALL BREAKDOWN:\n- Text Accuracy: [X]/40 - [Brief note on overall text quality and any issues]\n- Visual Elements: [X]/25 - [Note on overall image/diagram handling accuracy]\n- Table Structure: [X]/20 - [Note on overall table detection and extraction]\n- Handwriting Legibility: [X]/15 - [Note on overall handwriting clarity and challenges]\n\nKEY CHALLENGES:\n- [List any specific difficulties encountered across the document]\n- [Note any sections with multiple uncertainties]\n- [Summary of per-question confidence variations]\n\nRELIABILITY NOTES:\n- [Any warnings about specific sections or content types]\n- [Overall assessment of extraction quality]\n\n---\n\n## CORRECT OUTPUT EXAMPLE\n\nStudent Name: John Smith     Roll No: 2024-0156     Date: 15/03/2024\n\nPHYSICS EXAMINATION - ANSWER SHEET\n\nQuestion 1: Explain Newton's Second Law of Motion with an example.\n\nAnswer: Newton's Second Law states that Force = mass × acceleration or F = ma. This means that the acceleration of an object depends on the net force acting upon it and the mass of the object.\n\n[IMAGE DESCRIPTION: A hand-drawn diagram showing a rectangular block on a horizontal surface with two arrows. One arrow points right labeled 'Applied Force' and another points left labeled 'Friction'. The block has 'm = 5kg' written inside it.\n\nTEXT IN IMAGE: \n- Applied Force (right arrow)\n- Friction (left arrow)  \n- m = 5kg\n- F = 20N\n\nIMAGE TYPE: diagram\n\nIMAGE CONTEXT: Illustrates force application for Question 1 example]\n\nExample: When we push a box of mass 5kg with a force of 20N, the [UNCERTAIN: acceleration] can be calculated using a = F/m = 20/5 = 4 m/s²\n\nQuestion 2: Calculate the velocity using the data below:\n\n[TABLE DESCRIPTION: A data table with 3 columns and 4 rows (including header). The table presents physical parameters for velocity calculation with parameter names, numerical values, and units.\n\nTEXT IN TABLE:\n- Header row: Parameter, Value, Unit\n- Row 1: Initial Velocity, 0, m/s\n- Row 2: Acceleration, 9.8, m/s²\n- Row 3: Time, 5, s\n\nTABLE TYPE: data_table\n\nTABLE CONTEXT: Provides input data for Question 2 velocity calculation]\n\n| Parameter | Value | Unit |\n|-----------|-------|------|\n| Initial Velocity | 0 | m/s |\n| Acceleration | 9.8 | m/s² |\n| Time | 5 | s |\n\nSolution: Using v = u + at\nv = 0 + (9.8)(5)\nv = 49 m/s 50 m/s\n\n[Note: Student corrected their answer]\n\n---\n\n## CONFIDENCE SCORES EXAMPLE\n\nQUESTION 1 CONFIDENCE: 85 / 100\n\nBREAKDOWN FOR QUESTION 1:\n- Text Accuracy: 35/40 - Clear handwriting, minor uncertainty in one word\n- Visual Elements: 22/25 - Diagram well-described with all labels extracted\n- Table Structure: 20/20 - No tables in this question\n- Handwriting Legibility: 8/15 - Generally clear but some pressure variations\n\nISSUES FOR QUESTION 1:\n- One uncertain word marked: [UNCERTAIN: acceleration]\n- Diagram extraction complete and accurate\n\nQUESTION 2 CONFIDENCE: 92 / 100\n\nBREAKDOWN FOR QUESTION 2:\n- Text Accuracy: 38/40 - Very clear text extraction\n- Visual Elements: 25/25 - No images in this question\n- Table Structure: 19/20 - Table well-extracted with complete data\n- Handwriting Legibility: 10/15 - Clear and consistent handwriting\n\nISSUES FOR QUESTION 2:\n- Student correction noted (49 m/s corrected to 50 m/s)\n- Table description and markdown format both provided accurately\n\nTOTAL CONFIDENCE SCORE: 88 / 100\n\nOVERALL BREAKDOWN:\n- Text Accuracy: 36/40 - High accuracy with minimal uncertainties\n- Visual Elements: 23/25 - Images and tables properly identified and described\n- Table Structure: 19/20 - Accurate table detection and extraction\n- Handwriting Legibility: 9/15 - Generally legible with minor variations\n\nKEY CHALLENGES:\n- One uncertain word in Question 1\n- Student correction in Question 2 properly preserved\n- Overall extraction quality is high\n\nRELIABILITY NOTES:\n- All questions successfully extracted with high confidence\n- Visual elements (diagram and table) comprehensively described\n- Extraction suitable for automated grading with minimal review\n\n---\n\n## WRONG OUTPUT EXAMPLES - DO NOT DO THIS\n\nWRONG: Moving all images to end of document\nWRONG: Reordering content by type (all questions, then all images)\nWRONG: Auto-correcting student spelling or grammar\nWRONG: Summarizing or paraphrasing answers\nWRONG: Treating bar charts or line graphs as tables\nWRONG: Skipping headers, footers, or student information\nWRONG: Ignoring crossed-out work or corrections\nWRONG: Failing to mark uncertain text with [UNCERTAIN] tags\nWRONG: Providing only total confidence score without per-question scores\nWRONG: Providing table markdown without table description\n\n---\n\n## FINAL EXECUTION CHECKLIST\n\nBefore submitting extraction, verify:\n- Content extracted in exact sequential order\n- All visuals described and placed inline at correct positions\n- Images vs. tables correctly distinguished (graphs are NOT tables)\n- Tables have BOTH description AND markdown format\n- All uncertain text marked with appropriate tags\n- Mathematical notation properly formatted\n- Student corrections and edits preserved\n- Per-question confidence scores provided for ALL questions\n- Total confidence score provided with detailed breakdown\n- No content rearranged or moved from original position\n\n---\n\n## GOAL\n\nProduce a flawless, character-perfect sequential reproduction of the handwritten answer sheet where:\n1. Every element appears in its original position\n2. Handwriting is interpreted with maximum accuracy\n3. Uncertainties are clearly flagged\n4. Visual elements (images AND tables) are comprehensively described\n5. Per-question confidence scores reflect extraction quality for each question\n6. Overall confidence assessment reflects total extraction quality\n\nThis extraction should be usable for automated grading, archival, or digitization purposes with minimal manual review required."
                }
            ]
            
            # Add all PDF pages as images
            for page_num, img_base64 in enumerate(pdf_images, 1):
                content_items.append({
                    "type": "image_url",
                    "image_url": f"data:image/png;base64,{img_base64}"
                })
            
            messages = [
                {
                    "role": "user",
                    "content": content_items
                }
            ]
            
            print("\nSending request to Mistral API...")
            f.write("\nSending request to Mistral API...\n")
            
            chat_response = client.chat.complete(
                model=model,
                messages=messages
            )
            
            print("\nChat Response:")
            print("=" * 50)
            f.write("\nChat Response:\n")
            f.write("=" * 50 + "\n")
            
            # Extract the text from the response
            extracted_text = ""
            if hasattr(chat_response, 'choices') and chat_response.choices:
                for choice in chat_response.choices:
                    if hasattr(choice, 'message') and hasattr(choice.message, 'content'):
                        extracted_text += choice.message.content + "\n"
            
            print(extracted_text)
            f.write(extracted_text + "\n")
            
            # Extract per-question confidence scores BEFORE removing confidence section
            print("\n" + "=" * 80)
            print("Extracting Per-Question Confidence Scores")
            print("=" * 80)
            f.write("\n" + "=" * 80 + "\n")
            f.write("Extracting Per-Question Confidence Scores\n")
            f.write("=" * 80 + "\n\n")
            
            per_question_confidence = parse_per_question_confidence(extracted_text, output_file=f)
            
            # Extract overall confidence score separately and remove it (and everything after) from text
            confidence_score = "N/A"
            confidence_details = ""
            
            # First, look for the confidence section header to remove the entire section
            # This prevents confidence scores from appearing in question answers
            confidence_section_start = None
            
            # Pattern 0: Look for "CONFIDENCE SCORES:" or "**CONFIDENCE SCORES:**" section header
            # This is the most reliable way to find where the confidence section starts
            confidence_header_patterns = [
                r'\*\*CONFIDENCE\s+SCORES?\*\*:',
                r'CONFIDENCE\s+SCORES?:',
                r'---\s*CONFIDENCE\s+SCORES\s*---',
                r'---\s*\n\s*\*\*CONFIDENCE',
                r'---\s*\n\s*CONFIDENCE',
                r'CONFIDENCE SCORES',
            ]
            
            for pattern in confidence_header_patterns:
                match = re.search(pattern, extracted_text, re.IGNORECASE | re.MULTILINE)
                if match:
                    confidence_section_start = match.start()
                    msg = f"  Found confidence section header at position {confidence_section_start}"
                    print(msg)
                    f.write(msg + "\n")
                    break
            
            # If we found the confidence section header, extract details and remove it
            if confidence_section_start is not None:
                confidence_details = extracted_text[confidence_section_start:].strip()
                # Extract overall confidence score from the details
                # Look for "TOTAL CONFIDENCE SCORE: 85" or similar in the details
                total_match = re.search(r'TOTAL\s+CONFIDENCE\s+SCORE[:\s]+(\d+(?:\.\d+)?)', confidence_details, re.IGNORECASE)
                if total_match:
                    confidence_score = total_match.group(1)
                else:
                    # Try to find any overall confidence score pattern
                    overall_patterns = [
                        r'(?:TOTAL\s+)?confidence\s*(?:score)?[:\s]*(\d+(?:\.\d+)?)\s*(?:/|\s*out\s*of\s*)?\s*(?:100)?',
                        r'(\d+(?:\.\d+)?)\s*(?:/|\s*out\s*of\s*)\s*100\s*(?:confidence|confidence\s*score)',
                    ]
                    for pattern in overall_patterns:
                        match = re.search(pattern, confidence_details, re.IGNORECASE)
                        if match:
                            confidence_score = match.group(1)
                            break
                
                # Remove the confidence section from extracted_text
                extracted_text = extracted_text[:confidence_section_start].rstrip()
                msg = f"  Removed confidence section (length: {len(confidence_details)} chars)"
                print(msg)
                f.write(msg + "\n")
            else:
                # Fallback: Look for confidence score patterns (usually at the end of the text)
                # Check the last 800 characters for confidence mentions
                end_section = extracted_text[-800:] if len(extracted_text) > 800 else extracted_text
                
                # Pattern 1: "TOTAL CONFIDENCE SCORE: 85" or "Confidence Score: 85" or "Confidence: 90"
                confidence_match = re.search(r'(?:TOTAL\s+)?confidence\s*(?:score)?[:\s]*(\d+(?:\.\d+)?)\s*(?:/|\s*out\s*of\s*)?\s*(?:100)?', end_section, re.IGNORECASE)
                if confidence_match:
                    confidence_score = confidence_match.group(1)
                    confidence_section_start = len(extracted_text) - len(end_section) + confidence_match.start()
                    confidence_details = extracted_text[confidence_section_start:].strip()
                
                # Pattern 2: "85/100" or "90 out of 100" near "confidence"
                if confidence_score == "N/A":
                    confidence_match = re.search(r'(\d+(?:\.\d+)?)\s*(?:/|\s*out\s*of\s*)\s*100\s*(?:confidence|confidence\s*score)', end_section, re.IGNORECASE)
                    if confidence_match:
                        confidence_score = confidence_match.group(1)
                        confidence_section_start = len(extracted_text) - len(end_section) + confidence_match.start()
                        confidence_details = extracted_text[confidence_section_start:].strip()
                
                # Pattern 3: Just a number followed by "confidence" or "confidence score"
                if confidence_score == "N/A":
                    confidence_match = re.search(r'(\d+(?:\.\d+)?)\s*(?:%|percent)?\s*(?:confidence|confidence\s*score)', end_section, re.IGNORECASE)
                    if confidence_match:
                        confidence_score = confidence_match.group(1)
                        confidence_section_start = len(extracted_text) - len(end_section) + confidence_match.start()
                        confidence_details = extracted_text[confidence_section_start:].strip()
                
                # If we found a confidence section, remove everything from that point onward
                if confidence_section_start is not None:
                    extracted_text = extracted_text[:confidence_section_start].rstrip()
            
            # Note: Confidence score will be included in final JSON output
            # Don't display it here, it will be shown at the end
            
            # Safety: If any remaining "CONFIDENCE SCORES" text slipped through, trim it here as well
            fallback_conf_idx = extracted_text.upper().find("CONFIDENCE SCORES")
            if fallback_conf_idx != -1:
                msg = f"  Fallback removal: trimming text at position {fallback_conf_idx} due to 'CONFIDENCE SCORES' keyword"
                print(msg)
                f.write(msg + "\n")
                confidence_details = extracted_text[fallback_conf_idx:].strip()
                extracted_text = extracted_text[:fallback_conf_idx].rstrip()

            # Optional: Extract images separately for extra-detailed vision model analysis
            # Set to False to rely on inline document processing (recommended for maintaining layout)
            use_separate_vision_analysis = False
            
            if use_separate_vision_analysis:
                # Extract images from PDF and get detailed descriptions
                print("\n" + "=" * 80)
                print("STEP 1: Extracting and Analyzing Images from PDF with Vision Model")
                print("=" * 80)
                f.write("\n" + "=" * 80 + "\n")
                f.write("STEP 1: Extracting and Analyzing Images from PDF with Vision Model\n")
                f.write("=" * 80 + "\n\n")
                
                image_descriptions = extract_images_from_pdf(pdf_path, output_file=f)
                
                # Enhance the extracted text with detailed image descriptions
                if image_descriptions:
                    print("\n" + "=" * 80)
                    print("STEP 2: Enhancing Text with Detailed Image Descriptions")
                    print("=" * 80)
                    f.write("\n" + "=" * 80 + "\n")
                    f.write("STEP 2: Enhancing Text with Detailed Image Descriptions\n")
                    f.write("=" * 80 + "\n\n")
                    
                    extracted_text = enhance_text_with_image_descriptions(
                        extracted_text, 
                        image_descriptions, 
                        output_file=f
                    )
                    
                    print("\nEnhanced text with image descriptions:")
                    print("-" * 60)
                    print(extracted_text)
                    f.write("\nEnhanced text with image descriptions:\n")
                    f.write("-" * 60 + "\n")
                    f.write(extracted_text + "\n")
            
            # Parse questions and answers
            print("\n" + "=" * 80)
            print("STEP 1: Parsing Questions and Answers (Sequential Order Only)")
            print("=" * 80)
            f.write("\n" + "=" * 80 + "\n")
            f.write("STEP 1: Parsing Questions and Answers (Sequential Order Only)\n")
            f.write("=" * 80 + "\n\n")
            
            questions_answers = parse_questions_and_answers(extracted_text, output_file=f)
            
            # Add confidence scores to each question
            print("\n" + "=" * 80)
            print("Adding Confidence Scores to Questions")
            print("=" * 80)
            f.write("\n" + "=" * 80 + "\n")
            f.write("Adding Confidence Scores to Questions\n")
            f.write("=" * 80 + "\n\n")
            
            print(f"  Found {len(per_question_confidence)} confidence score(s) in extracted data")
            print(f"  Processing {len(questions_answers)} question(s)")
            f.write(f"  Found {len(per_question_confidence)} confidence score(s) in extracted data\n")
            f.write(f"  Processing {len(questions_answers)} question(s)\n")
            
            if per_question_confidence:
                print(f"  Confidence scores found for questions: {', '.join(per_question_confidence.keys())}")
                f.write(f"  Confidence scores found for questions: {', '.join(per_question_confidence.keys())}\n")
            
            for qa in questions_answers:
                question_num = qa['question_number']
                # Get confidence score for this question, default to "N/A" if not found
                confidence = per_question_confidence.get(question_num, "N/A")
                qa['confidence_score'] = confidence
                
                msg = f"  Question {question_num}: confidence_score = {confidence}"
                print(msg)
                f.write(msg + "\n")
            
            # Create final output structure with questions and confidence score
            final_output = {
                'questions': questions_answers,
                'confidence': {
                    'score': confidence_score,
                    'details': confidence_details
                }
            }
            
            # Print parsed results
            print("\n" + "=" * 80)
            print("STEP 2: Final JSON Output")
            print("=" * 80)
            f.write("\n" + "=" * 80 + "\n")
            f.write("STEP 2: Final JSON Output\n")
            f.write("=" * 80 + "\n\n")
            
            json_output = json.dumps(final_output, indent=2, ensure_ascii=False)
            print("\nParsed Questions and Answers with Confidence Score (JSON):")
            print("-" * 50)
            print(json_output)
            f.write("\nParsed Questions and Answers with Confidence Score (JSON):\n")
            f.write("-" * 50 + "\n")
            f.write(json_output + "\n")
            
            print(f"\n\nTotal sequential questions found: {len(questions_answers)}")
            print(f"Confidence Score: {confidence_score}")
            print(f"Output saved to: {output_file}")
            f.write(f"\n\nTotal sequential questions found: {len(questions_answers)}\n")
            f.write(f"Confidence Score: {confidence_score}\n")
            f.write(f"Output saved to: {output_file}\n")
        
        except Exception as e:
            error_msg = f"Error: {e}"
            print(error_msg)
            f.write(error_msg + "\n")
            import traceback
            traceback.print_exc()
            f.write(traceback.format_exc() + "\n")




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


# ==================== TESTING / CLI ENTRYPOINT ====================

if __name__ == "__main__":
    """
    CLI usage (testing only, not used in the API):
    
    - Single PDF mode (backwards compatible):
        python extraction_handwritten.py input.pdf [output.txt]
    
    - Folder mode (requested):
        python extraction_handwritten.py input_folder [output_folder]
    
      For each *.pdf in input_folder, writes:
        output_folder/<pdf_stem>_output.txt
    """
    import sys

    # Configure logging for testing
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s",
    )

    script_dir = Path(__file__).parent

    # No args → fall back to single default PDF for convenience
    if len(sys.argv) == 1:
        pdf_path = script_dir / "handwritten answersheet.pdf"
        output_file = script_dir / "output.txt"

        print("\n" + "=" * 80)
        print("HANDWRITTEN ANSWER SHEET EXTRACTION (single PDF default)")
        print("=" * 80)
        print(f"Input PDF: {pdf_path}")
        print(f"Output File: {output_file}")
        print("=" * 80 + "\n")

        try:
            result = extract_handwritten_answers(str(pdf_path))

            with open(output_file, "w", encoding="utf-8") as f:
                f.write("=" * 80 + "\n")
                f.write("EXTRACTION RESULTS\n")
                f.write("=" * 80 + "\n\n")

                f.write(f"Email: {result.get('email', 'None')}\n")
                f.write(f"Total Questions Extracted: {len(result['answers'])}\n\n")
                f.write("=" * 80 + "\n\n")

                for qa in result["answers"]:
                    f.write(f"Question {qa['question_number']}:\n")
                    f.write("-" * 40 + "\n")
                    f.write(f"{qa['student_answer']}\n")
                    f.write("\n" + "=" * 80 + "\n\n")

                # Also write raw chat response so you can inspect the full model output
                raw_chat = result.get("raw_chat_response", "")
                if raw_chat:
                    f.write("\n\n" + "=" * 80 + "\n")
                    f.write("RAW CHAT RESPONSE\n")
                    f.write("=" * 80 + "\n\n")
                    f.write(raw_chat)

                # Finally, write JSON without the raw_chat_response field
                result_for_json = dict(result)
                result_for_json.pop("raw_chat_response", None)
                f.write("\n\n" + "=" * 80 + "\n")
                f.write("JSON FORMAT\n")
                f.write("=" * 80 + "\n")
                f.write(json.dumps(result_for_json, indent=2, ensure_ascii=False))

            print(f"\n✅ Results written to: {output_file}")
            print(f"✅ Total questions extracted: {len(result['answers'])}")

        except FileNotFoundError:
            print(f"\n❌ Error: File '{pdf_path}' not found!")
            print("Please make sure the PDF file exists in the current directory.\n")
        except Exception as e:
            print(f"\n❌ Error during extraction: {e}\n")
            import traceback

            traceback.print_exc()

        sys.exit(0)

    # If first arg is a directory → folder mode
    input_path = Path(sys.argv[1])

    if input_path.is_dir():
        input_folder = input_path
        # Optional second arg = output folder; default: <input_folder>/handwritten_outputs
        if len(sys.argv) > 2:
            output_folder = Path(sys.argv[2])
        else:
            output_folder = input_folder / "handwritten_outputs"

        output_folder.mkdir(parents=True, exist_ok=True)

        print("\n" + "=" * 80)
        print("HANDWRITTEN ANSWER SHEET EXTRACTION (folder mode)")
        print("=" * 80)
        print(f"Input folder:  {input_folder}")
        print(f"Output folder: {output_folder}")
        print("=" * 80 + "\n")

        pdf_files = sorted(input_folder.glob("*.pdf"))
        if not pdf_files:
            print(f"❌ No PDF files found in folder: {input_folder}")
            sys.exit(1)

        for pdf_file in pdf_files:
            try:
                print("\n" + "-" * 80)
                print(f"Processing PDF: {pdf_file.name}")
                print("-" * 80)

                result = extract_handwritten_answers(str(pdf_file))

                out_path = output_folder / f"{pdf_file.stem}_output.txt"
                with open(out_path, "w", encoding="utf-8") as f:
                    f.write("=" * 80 + "\n")
                    f.write("EXTRACTION RESULTS\n")
                    f.write("=" * 80 + "\n\n")

                    f.write(f"Email: {result.get('email', 'None')}\n")
                    f.write(
                        f"Total Questions Extracted: {len(result.get('answers', []))}\n\n"
                    )
                    f.write("=" * 80 + "\n\n")

                    for qa in result.get("answers", []):
                        f.write(f"Question {qa['question_number']}:\n")
                        f.write("-" * 40 + "\n")
                        f.write(f"{qa['student_answer']}\n")
                        f.write("\n" + "=" * 80 + "\n\n")

                    # Also write raw chat response so you can inspect the full model output
                    raw_chat = result.get("raw_chat_response", "")
                    if raw_chat:
                        f.write("\n\n" + "=" * 80 + "\n")
                        f.write("RAW CHAT RESPONSE\n")
                        f.write("=" * 80 + "\n\n")
                        f.write(raw_chat)

                    # Finally, write JSON without the raw_chat_response field
                    result_for_json = dict(result)
                    result_for_json.pop("raw_chat_response", None)
                    f.write("\n\n" + "=" * 80 + "\n")
                    f.write("JSON FORMAT\n")
                    f.write("=" * 80 + "\n")
                    f.write(json.dumps(result_for_json, indent=2, ensure_ascii=False))

                print(f"✅ Wrote output to: {out_path}")

            except Exception as e:
                print(f"\n❌ Error during extraction for '{pdf_file}': {e}\n")
                import traceback

                traceback.print_exc()

        print("\n" + "=" * 80)
        print("FOLDER PROCESSING COMPLETE")
        print("=" * 80 + "\n")

    else:
        # Backwards compatible single-file mode when a file path is provided
        pdf_path = input_path
        output_file = Path(sys.argv[2]) if len(sys.argv) > 2 else Path("output.txt")

        print("\n" + "=" * 80)
        print("HANDWRITTEN ANSWER SHEET EXTRACTION (single PDF)")
        print("=" * 80)
        print(f"Input PDF: {pdf_path}")
        print(f"Output File: {output_file}")
        print("=" * 80 + "\n")

        try:
            result = extract_handwritten_answers(str(pdf_path))

            with open(output_file, "w", encoding="utf-8") as f:
                f.write("=" * 80 + "\n")
                f.write("EXTRACTION RESULTS\n")
                f.write("=" * 80 + "\n\n")

                f.write(f"Email: {result.get('email', 'None')}\n")
                f.write(f"Total Questions Extracted: {len(result['answers'])}\n\n")
                f.write("=" * 80 + "\n\n")

                for qa in result["answers"]:
                    f.write(f"Question {qa['question_number']}:\n")
                    f.write("-" * 40 + "\n")
                    f.write(f"{qa['student_answer']}\n")
                    f.write("\n" + "=" * 80 + "\n\n")

                # Also write raw chat response so you can inspect the full model output
                raw_chat = result.get("raw_chat_response", "")
                if raw_chat:
                    f.write("\n\n" + "=" * 80 + "\n")
                    f.write("RAW CHAT RESPONSE\n")
                    f.write("=" * 80 + "\n\n")
                    f.write(raw_chat)

                # Finally, write JSON without the raw_chat_response field
                result_for_json = dict(result)
                result_for_json.pop("raw_chat_response", None)
                f.write("\n\n" + "=" * 80 + "\n")
                f.write("JSON FORMAT\n")
                f.write("=" * 80 + "\n")
                f.write(json.dumps(result_for_json, indent=2, ensure_ascii=False))

            print(f"\n✅ Results written to: {output_file}")
            print(f"✅ Total questions extracted: {len(result['answers'])}")

        except FileNotFoundError:
            print(f"\n❌ Error: File '{pdf_path}' not found!")
            print("Please make sure the PDF file exists in the current directory.\n")
        except Exception as e:
            print(f"\n❌ Error during extraction: {e}\n")
            import traceback

            traceback.print_exc()
