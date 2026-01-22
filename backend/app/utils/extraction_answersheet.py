import sys, importlib, os
import warnings
import pdfplumber
import json
import re
import io
import base64
import logging
from collections import defaultdict
from ..utils.openai_client import client
from ..config.settings import settings


logger = logging.getLogger(__name__)

def _is_footer_text(text, page_height):
    """Detect if text is likely footer content based on patterns and position."""
    if not text or not text.strip():
        return True  # Empty or whitespace-only text should be filtered out
    
    text = text.strip()
    
    # Common footer patterns
    footer_patterns = [
        r'Page\s+\d+\s+of\s+\d+',  # "Page X of Y"
        r'Page\s+\d+',              # "Page X"
        r'Page\s+\d+\s*/\s*\d+',    # "Page X/Y"
    ]
    
    # Check if text matches footer patterns
    for pattern in footer_patterns:
        if re.match(pattern, text, re.IGNORECASE):
            return True
    
    return False

def _filter_footer_lines(lines, page_height):
    """Filter out footer lines from the lines array."""
    filtered_lines = []
    for line in lines:
        # Check if this line is likely footer content
        if not _is_footer_text(line.get("text", ""), page_height):
            filtered_lines.append(line)
    return filtered_lines

def _filter_footer_text(text):
    """Filter out footer content from extracted text."""
    if not text:
        return text
    
    lines = text.split('\n')
    filtered_lines = []
    
    for line in lines:
        line = line.strip()
        if not _is_footer_text(line, None):  # We don't have page height here, so just check patterns
            filtered_lines.append(line)
    
    return '\n'.join(filtered_lines)

def _group_words_by_row(page):
    rows = defaultdict(list)
    for w in page.extract_words():
        rows[round(w["top"], 1)].append(w)
    return rows


def _rows_to_lines(rows):
    lines = []
    for top in sorted(rows):
        words = sorted(rows[top], key=lambda w: w["x0"])
        lines.append({"y": float(top), "text": " ".join(w["text"] for w in words)})
    return lines


def _extract_tables_on_page(page):
    tables = []
    for t in page.find_tables(table_settings={
        "vertical_strategy": "lines",
        "horizontal_strategy": "lines"
    }):
        x0, top, x1, bottom = t.bbox
        # Clip table bbox to page boundaries to avoid errors
        x0 = max(0, min(x0, page.width))
        x1 = max(0, min(x1, page.width))
        top = max(0, min(top, page.height))
        bottom = max(0, min(bottom, page.height))
        
        # Only add valid tables (with non-zero area)
        if x1 > x0 and bottom > top:
            tables.append({"bbox": (x0, top, x1, bottom), "data": t.extract()})
    return tables

def _build_page_entry(page, lines, tables):
    # Extract text excluding table regions to avoid duplication
    text = page.extract_text() or ""
    
    # If there are tables, filter out text from those regions
    if tables:
        # Create a filtered page by excluding table bboxes
        filtered_page = page
        for table in tables:
            try:
                # Crop out the table region
                filtered_page = filtered_page.outside_bbox(table["bbox"])
            except ValueError as e:
                # If bbox is still invalid, skip filtering for this table
                # This shouldn't happen after clipping, but safety first
                warnings.warn(f"Skipping table bbox filtering due to: {e}")
                continue
        text = filtered_page.extract_text() or ""
    
    # Filter out footer content from text
    text = _filter_footer_text(text)
    
    # Filter out footer lines from lines array
    filtered_lines = _filter_footer_lines(lines, page.height)
    
    return {
        "text": text,
        "lines": filtered_lines,
        "height": page.height,
        "tables": tables
    }

def extract_text_tables(pdf_path):
    """Return per-page text, line anchors (y), page height, and tables with bbox."""
    pages = []
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            rows = _group_words_by_row(page)
            lines = _rows_to_lines(rows)
            tables = _extract_tables_on_page(page)
            pages.append(_build_page_entry(page, lines, tables))
    return pages

def _stitch_full_text(pages_content):
    parts, offsets = [], []
    off = 0
    for p in pages_content:
        parts.append(p["text"])
        offsets.append(off)
        off += len(p["text"]) + 1  # newline between pages
    return "\n".join(parts), offsets

def _qa_pattern():
    # Primary pattern: "Question X" followed by optional period, colon, space, or nothing
    # Supports: "Question 1.", "Question 1:", "Question 1 ", "Question 1" (nothing after)
    return re.compile(
        r"(Question\s*\d+[.:\s]?\s*.*?)(?:\n)Answer:\s*(.*?)(?=(?:\n?Question\s*\d+[.:\s]?|$))",
        re.DOTALL | re.IGNORECASE
    )

def _qa_pattern_alt():
    # Alternative patterns for different formats
    patterns = [
        # "Q1. ... Answer: ..." or "Q1: ... Answer: ..." or "Q1 ..." or "Q1" (nothing after)
        re.compile(r"(Q\s*\d+[.:\s]?\s*.*?)(?:\n| )Answer:\s*(.*?)(?=(?:\n?Q\s*\d+[.:\s]?|$))", re.DOTALL | re.IGNORECASE),
        # "1. ... Answer: ..." (numbered questions)
        re.compile(r"(\d+\.\s+.*?)(?:\n| )Answer:\s*(.*?)(?=(?:\n?\d+\.\s+|$))", re.DOTALL),
    ]
    return patterns

def _qa_matches_to_results(matches):
    return [{
        "question": m.group(1).strip(),
        "answer": [{"type": "text", "content": m.group(2).strip()}]
    } for m in matches]

def _is_question_line(ln):
    text = ln["text"] or ""
    # Match various question formats with optional period, colon, space, or nothing after number
    # Supports: "Question 1.", "Question 1:", "Question 1 ", "Question 1", "Q1.", "Q1:", "Q1", "1."
    patterns = [
        r"\s*Question\s*\d+[.:\s]?",  # "Question 1." or "Question 1:" or "Question 1 " or "Question 1"
        r"\s*Q\s*\d+[.:\s]?",         # "Q1." or "Q1:" or "Q1 " or "Q1"
        r"^\s*\d+\.\s+",              # "1. " at start of line
    ]
    for pattern in patterns:
        if re.match(pattern, text, re.IGNORECASE):
            return True
    return False

def _is_answer_line(ln):
    text = ln["text"] or ""
    # Match various answer formats: "Answer:", "Ans:", "A:"
    patterns = [
        r"\s*Answer:\s*",
        r"\s*Ans:\s*",
        r"\s*A:\s*",
    ]
    for pattern in patterns:
        if re.match(pattern, text, re.IGNORECASE):
            return True
    return False

def _collect_line_anchors(pages_content):
    q_anchors, a_anchors = [], []  # tuples of (page_idx, y)
    for pi, page in enumerate(pages_content):
        for ln in page["lines"]:
            if _is_question_line(ln):
                q_anchors.append((pi, ln["y"]))
            if _is_answer_line(ln):
                a_anchors.append((pi, ln["y"]))
    q_anchors.sort(key=lambda t: (t[0], t[1]))
    a_anchors.sort(key=lambda t: (t[0], t[1]))
    return q_anchors, a_anchors


def _compute_answer_spans(a_anchors, q_anchors, pages_content, results_len):
    """Return list of (start_page, start_y, end_page, end_y) aligned to results."""
    n = min(len(a_anchors), results_len)
    spans = []
    qj = 0
    last_end = (len(pages_content) - 1, pages_content[-1]["height"] + 5.0)

    for i in range(n):
        ap, ay = a_anchors[i]
        # advance to first question strictly below (ap, ay)
        while qj < len(q_anchors) and (
            q_anchors[qj][0] < ap or (q_anchors[qj][0] == ap and q_anchors[qj][1] <= ay + 0.1)
        ):
            qj += 1
        ep, ey = q_anchors[qj] if qj < len(q_anchors) else last_end
        spans.append((ap, ay, ep, ey))
    return spans

def _pos_le(p1, y1, p2, y2):
    return (p1 < p2) or (p1 == p2 and y1 <= y2)

def _pos_ge(p1, y1, p2, y2):
    return (p1 > p2) or (p1 == p2 and y1 >= y2)

def _attach_tables_to_spans(results, pages_content, spans):
    if not spans:
        return
    n = min(len(spans), len(results))
    for pi, page in enumerate(pages_content):
        for t in page["tables"]:
            _, top, _, bottom = t["bbox"]
            yc = 0.5 * (top + bottom)
            target = None
            # primary: containing span
            for idx in range(n):
                sp, sy, ep, ey = spans[idx]
                if _pos_ge(pi, yc, sp, sy) and _pos_le(pi, yc, ep, ey):
                    target = idx
                    break
            # fallback: last span that started before this table
            if target is None and n > 0:
                latest = None
                for idx in range(n):
                    sp, sy, _, _ = spans[idx]
                    if _pos_le(sp, sy, pi, yc):
                        latest = idx
                target = latest
            if target is not None:
                results[target]["answer"].append({"type": "table", "content": t["data"]})

#extract email from the answer sheet
def extract_email_from_answer_sheet(answer_sheet):
    """Extract email from the answer sheet.

    """
    try:
        with pdfplumber.open(answer_sheet) as pdf:
            # Check first page only (email is typically at the top)
            for page in pdf.pages[:1]:
                text = page.extract_text()
                if not text:
                    continue
                
                # Search for "Email:" followed by the email address
                # Match pattern: Email: something@atriauniversity.edu.in
                match = re.search(r'Email:\s*([a-zA-Z0-9._%+-]+@atriauniversity\.edu\.in)', text, re.IGNORECASE)
                if match:
                    email = match.group(1).strip()
                    logger.info(f"Extracted email from answer sheet: {email}")
                    return email
                
                # Alternative: try to find any @atriauniversity.edu.in email
                match = re.search(r'([a-zA-Z0-9._%+-]+@atriauniversity\.edu\.in)', text, re.IGNORECASE)
                if match:
                    email = match.group(1).strip()
                    logger.info(f"Extracted email from answer sheet (fallback): {email}")
                    return email
        
        logger.warning(f"No email found in answer sheet: {answer_sheet}")
        return None
    except Exception as e:
        logger.error(f"Error extracting email from answer sheet: {str(e)}")
        return None

# ---------- NEW IMAGE + OPENAI INTEGRATION HELPERS ----------

def extract_images_from_pdf(pdf_path):
    """Extract images with their bounding boxes from each page."""
    images = []
    
    try:
        with pdfplumber.open(pdf_path) as pdf:
            logger.info(f"Extracting images from PDF: {pdf_path}")
            for page_index, page in enumerate(pdf.pages):
                page_images = page.images
                logger.debug(f"Page {page_index + 1}: Found {len(page_images)} images")
                
                for img_index, img_obj in enumerate(page_images):
                    try:
                        x0, top, x1, bottom = img_obj["x0"], img_obj["top"], img_obj["x1"], img_obj["bottom"]
                        logger.debug(f"Processing image {img_index + 1} on page {page_index + 1}: bbox=({x0}, {top}, {x1}, {bottom})")
                        
                        image = page.within_bbox((x0, top, x1, bottom)).to_image(resolution=150)
                        img_bytes = io.BytesIO()
                        image.original.save(img_bytes, format="PNG")
                        img_bytes.seek(0)
                        
                        images.append({
                            "page": page_index,
                            "bbox": (x0, top, x1, bottom),
                            "data": img_bytes.getvalue()
                        })
                        logger.debug(f"Successfully extracted image {img_index + 1} on page {page_index + 1}")
                        
                    except Exception as e:
                        logger.warning(f"Error extracting image {img_index + 1} on page {page_index + 1}: {e}")
                        continue
                        
        logger.info(f"Successfully extracted {len(images)} images from PDF")
        return images
        
    except Exception as e:
        logger.error(f"Error opening PDF {pdf_path}: {e}")
        return []


def upload_image_to_openai(image_data, filename_prefix="image"):
    """Upload image to OpenAI files API and return file_id."""
    try:
        # Create a BytesIO object from image data
        image_file = io.BytesIO(image_data)
        image_file.name = f"{filename_prefix}.png"
        
        # Upload to OpenAI files API
        response = client.files.create(
            file=image_file,
            purpose="vision"
        )
        
        logger.info(f"Successfully uploaded image to OpenAI: {response.id}")
        return response.id
        
    except Exception as e:
        logger.error(f"Error uploading image to OpenAI: {e}")
        return None


def _assign_images_to_questions(images, q_anchors, results, pages_content, a_anchors=None):
    """Attach images to the correct question based on position.
    
    Only includes images that appear AFTER the "Answer:" line for each question,
    to avoid including question diagrams as part of the student's answer.
    """
    if not images or not q_anchors:
        logger.debug("No images or question anchors available for assignment")
        return results

    logger.info(f"Assigning {len(images)} images to {len(q_anchors)} questions")
    
    assigned_count = 0
    skipped_question_images = 0
    
    for img_index, img in enumerate(images):
        try:
            page, (x0, top, x1, bottom) = img["page"], img["bbox"]
            yc = 0.5 * (top + bottom)
            target = None
            
            logger.debug(f"Processing image {img_index + 1}: page={page}, bbox=({x0:.1f}, {top:.1f}, {x1:.1f}, {bottom:.1f}), center_y={yc:.1f}")

            for idx, (qp, qy) in enumerate(q_anchors):
                # Check if this is the last question
                is_last_question = (idx == len(q_anchors) - 1)
                
                if is_last_question:
                    # For the last question, just check if image is below it (on same page or later page)
                    if page > qp or (page == qp and yc >= qy):
                        target = idx
                        logger.debug(f"Image {img_index + 1} matches LAST question {idx + 1}: page {qp} y={qy:.1f} (last question)")
                        break
                else:
                    # For non-last questions, check if image is between current and next question
                    next_q = q_anchors[idx + 1]
                    next_p, next_y = next_q
                    if (page > qp or (page == qp and yc >= qy)) and (page < next_p or (page == next_p and yc < next_y)):
                        target = idx
                        logger.debug(f"Image {img_index + 1} matches question {idx + 1}: page {qp} y={qy:.1f} -> next page {next_p} y={next_y:.1f}")
                        break

            # Check if image is in the ANSWER area (after "Answer:" line), not the question area
            if target is not None and a_anchors and target < len(a_anchors):
                answer_page, answer_y = a_anchors[target]
                # Image must be at or below the "Answer:" line to be part of the student's answer
                if page < answer_page or (page == answer_page and yc < answer_y):
                    logger.debug(f"Skipping image {img_index + 1} - appears in question area (above Answer: line) for question {target + 1}")
                    skipped_question_images += 1
                    continue  # Skip this image - it's part of the question, not the answer

            if target is not None:
                question_text = results[target].get("question", "Unknown question")[:100]
                logger.info(f"Image {img_index + 1} assigned to question {target + 1}: {question_text}...")
                
                # Upload image to OpenAI files API
                filename_prefix = f"answer_sheet_q{target + 1}_img{img_index + 1}"
                file_id = upload_image_to_openai(img["data"], filename_prefix)
                
                if file_id:
                    results[target]["answer"].append({
                        "type": "image",
                        "file_id": file_id,
                    })
                else:
                    # Fallback to base64 if upload fails
                    logger.warning(f"Failed to upload image {img_index + 1}, falling back to base64")
                    b64_image = base64.b64encode(img["data"]).decode("utf-8")
                    results[target]["answer"].append({
                        "type": "image",
                        "image_data": b64_image,
                    })
                assigned_count += 1
                if file_id:
                    logger.info(f"✅ Uploaded and assigned image {img_index + 1} to question {target + 1} (file_id: {file_id})")
                else:
                    logger.info(f"✅ Assigned image {img_index + 1} to question {target + 1} (fallback to base64)")
            else:
                logger.warning(f"❌ Could not assign image {img_index + 1} to any question - no suitable position found")
                
        except Exception as e:
            logger.error(f"Error processing image {img_index + 1}: {e}")
            continue

    if skipped_question_images > 0:
        logger.info(f"Skipped {skipped_question_images} images that were in question areas (not student answers)")
    logger.info(f"Successfully assigned {assigned_count}/{len(images)} images to questions")
    return results


def split_into_qas(pages_content, pdf_path=None, answers_only=True):
    """
    Global Q&A parse (handles page spill) + attach tables and images
    to the correct answer via (page,y) spans.
    
    Args:
        pages_content: List of page dictionaries with text, lines, and tables
        pdf_path: Optional path to PDF for image extraction and email extraction
        answers_only: If True, returns only question numbers and answers (no question text)
    
    Returns:
        If answers_only=True: Dict with {"email": str or None, "answers": List of {"question_number": str, "student_answer": str}}
        If answers_only=False: List of {"question": str, "answer": [{"type": ..., "content": ...}]}
    """
    # 0) Extract email from PDF if path is provided
    extracted_email = None
    if pdf_path:
        try:
            extracted_email = extract_email_from_answer_sheet(pdf_path)
            logger.info(f"Extracted email: {extracted_email}")
        except Exception as e:
            logger.warning(f"Failed to extract email: {e}")
    
    # 1) Global Q&A from stitched text - try primary pattern first
    full_text, page_offsets = _stitch_full_text(pages_content)
    qa_pat = _qa_pattern()
    qa_matches = list(qa_pat.finditer(full_text))
    results = _qa_matches_to_results(qa_matches)
    
    # 1b) If primary pattern fails, try alternative patterns
    if not results:
        logger.info("Primary Q&A pattern found no matches, trying alternative patterns...")
        for alt_pattern in _qa_pattern_alt():
            qa_matches = list(alt_pattern.finditer(full_text))
            if qa_matches:
                results = _qa_matches_to_results(qa_matches)
                logger.info(f"Alternative pattern found {len(results)} Q&A pairs")
                break

    # 2) Build ordered anchors from page lines
    q_anchors, a_anchors = _collect_line_anchors(pages_content)

    # 3) Compute cross-page answer spans
    spans = _compute_answer_spans(a_anchors, q_anchors, pages_content, len(results))

    # 4) Attach tables by locating table center inside spans
    _attach_tables_to_spans(results, pages_content, spans)

    # 5) Extract images from PDF if path is provided
    images = []
    if pdf_path:
        try:
            logger.info(f"Starting image extraction from PDF: {pdf_path}")
            images = extract_images_from_pdf(pdf_path)
            if images:
                logger.info(f"Found {len(images)} images in PDF")
            else:
                logger.info("No images found in PDF")
        except Exception as e:
            logger.error(f"Image extraction failed: {e}")
            logger.warning("Continuing without image extraction due to error")

    # 5b) Fallback for image-only answer sheets: if no Q&A pairs found but we have images
    if not results and images:
        logger.warning("No text-based Q&A found but images exist - creating image-only entries")
        # Create one entry per image, assuming each image is a separate answer
        for img_idx, img in enumerate(images):
            # Upload image to OpenAI
            file_id = upload_image_to_openai(img["data"], f"answer_img_{img_idx + 1}")
            if file_id:
                results.append({
                    "question": f"Question {img_idx + 1}",
                    "answer": [{"type": "image", "file_id": file_id}]
                })
                logger.info(f"Created image-only entry for question {img_idx + 1} (file_id: {file_id})")
            else:
                # Fallback to base64
                b64_image = base64.b64encode(img["data"]).decode("utf-8")
                results.append({
                    "question": f"Question {img_idx + 1}",
                    "answer": [{"type": "image", "image_data": b64_image}]
                })
                logger.info(f"Created image-only entry for question {img_idx + 1} (base64 fallback)")
        # Update q_anchors for image assignment consistency
        q_anchors = [(img["page"], img["bbox"][1]) for img in images]
        logger.info(f"Created {len(results)} image-only Q&A entries")
    elif results and images and q_anchors:
        # Normal case: assign images to existing questions
        # Pass a_anchors to filter out images that are part of the question (not the answer)
        results = _assign_images_to_questions(images, q_anchors, results, pages_content, a_anchors)
        logger.info(f"Image extraction completed successfully")

    # 6) ERROR CHECK: If still no Q&A pairs found after all attempts, raise an error
    if not results:
        error_msg = (
            "Failed to extract any Q&A pairs from the answer sheet. "
            "The document format may not be supported. "
            "Expected formats: 'Question 1. ... Answer: ...' or 'Question 1: ... Answer: ...' or similar patterns."
        )
        logger.error(error_msg)
        raise ValueError(error_msg)

    # 7) If answers_only mode, convert to simplified format
    if answers_only:
        logger.info(f"Converting {len(results)} Q&A pairs to answers-only format")
        answers_only_results = []
        for idx, qa in enumerate(results):
            # Extract answer content from the answer array
            answer_content = ""
            if qa.get("answer") and isinstance(qa["answer"], list):
                for ans_item in qa["answer"]:
                    if isinstance(ans_item, dict) and ans_item.get("type") == "text":
                        answer_content += ans_item.get("content", "")
                    elif isinstance(ans_item, dict) and ans_item.get("type") == "table":
                        # Format table data as readable text
                        table_data = ans_item.get("content", [])
                        if table_data and isinstance(table_data, list):
                            answer_content += "\n[Table]:\n"
                            for row in table_data:
                                if row:  # Skip empty rows
                                    # Join cells with | separator
                                    row_text = " | ".join(str(cell) if cell else "" for cell in row)
                                    answer_content += row_text + "\n"
                            answer_content += "[End Table]\n"
                    elif isinstance(ans_item, dict) and ans_item.get("type") == "image":
                        # Include image reference in answer content
                        file_id = ans_item.get("file_id", "")
                        if file_id:
                            answer_content += f"\n[Image: {file_id}]\n"
            
            # Store only answer with question number (NO question text)
            answer_only = {
                "question_number": str(idx + 1),
                "student_answer": answer_content if answer_content else None
            }
            answers_only_results.append(answer_only)
        
        logger.info(f"Converted to {len(answers_only_results)} answers-only entries")
        return {
            "email": extracted_email,
            "answers": answers_only_results
        }

    return results