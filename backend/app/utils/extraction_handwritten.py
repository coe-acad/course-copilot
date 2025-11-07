"""
Handwritten answer sheet extraction using Mistral OCR.
Extracts question numbers and student answers from handwritten PDFs/images.
Supports various question numbering formats automatically.
"""

import os
import base64
import re
import logging
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from mistralai import Mistral

from ..config.settings import settings

logger = logging.getLogger(__name__)


class MistralOCRExtractor:
    """Handles OCR extraction using Mistral AI."""
    
    def __init__(self, api_key: Optional[str] = None):
        """Initialize Mistral OCR client."""
        self.api_key = api_key or settings.MISTRAL_API_KEY
        if not self.api_key:
            raise ValueError(
                "MISTRAL_API_KEY is not configured. "
                "Please set it in your environment variables."
            )
        
        self.client = Mistral(api_key=self.api_key)
        logger.info("Mistral OCR client initialized")
    
    def extract_text(self, file_path: str) -> str:
        """
        Extract text from PDF or image using Mistral OCR.
        
        Args:
            file_path: Path to PDF or image file
            
        Returns:
            Extracted text as string
        """
        file_path = Path(file_path)
        if not file_path.is_file():
            raise FileNotFoundError(f"File not found: {file_path}")
        
        logger.info(f"Extracting text from: {file_path}")
        print(f"\n🔍 Processing: {file_path.name}")
        
        try:
            # Read and encode file
            with open(file_path, "rb") as f:
                file_bytes = f.read()
            
            b64_data = base64.b64encode(file_bytes).decode("utf-8")
            
            # Determine document type
            ext = file_path.suffix.lower()
            if ext == '.pdf':
                doc_type = "document_url"
                mime = "application/pdf"
            elif ext in ['.png', '.jpg', '.jpeg', '.gif', '.bmp', '.webp']:
                doc_type = "image_url"
                mime_map = {
                    '.png': 'image/png', '.jpg': 'image/jpeg', 
                    '.jpeg': 'image/jpeg', '.gif': 'image/gif',
                    '.bmp': 'image/bmp', '.webp': 'image/webp'
                }
                mime = mime_map.get(ext, 'image/png')
            else:
                raise ValueError(f"Unsupported file type: {ext}")
            
            data_uri = f"data:{mime};base64,{b64_data}"
            
            # Call Mistral OCR
            response = self.client.ocr.process(
                model="mistral-ocr-latest",
                document={
                    "type": doc_type,
                    doc_type: data_uri
                },
                include_image_base64=False
            )
            
            # Extract text from response
            text = self._extract_text_from_response(response)
            logger.info(f"Extracted {len(text)} characters")
            print(f"✅ Extracted {len(text)} characters\n")
            
            return text
            
        except Exception as e:
            logger.error(f"OCR extraction failed: {e}")
            raise
    
    def _extract_text_from_response(self, response) -> str:
        """Extract text from Mistral OCR response."""
        text_parts = []
        
        if hasattr(response, 'pages'):
            for page in response.pages:
                if hasattr(page, 'markdown') and page.markdown:
                    text_parts.append(page.markdown)
                elif hasattr(page, 'text') and page.text:
                    text_parts.append(page.text)
        elif isinstance(response, dict):
            if "pages" in response:
                for page in response["pages"]:
                    text = page.get("markdown") or page.get("text", "")
                    if text:
                        text_parts.append(text)
            else:
                text = response.get("markdown") or response.get("text", "")
                if text:
                    text_parts.append(text)
        
        return "\n\n".join(text_parts)


class AnswerSheetParser:
    """
    Intelligent parser that automatically detects question numbering patterns.
    Works with: Q1, Q1), Q1:, Q1., 1), 1., ✓1, ✓ 1, etc.
    """
    
    def __init__(self):
        """Initialize parser."""
        self.debug_mode = True
        logger.info("Answer sheet parser initialized")
    
    def parse(self, text: str) -> List[Dict[str, Optional[str]]]:
        """
        Parse text to extract question-answer pairs.
        
        Args:
            text: Extracted text from OCR
            
        Returns:
            List of {"question_number": str, "student_answer": str}
        """
        logger.info("Starting Q&A parsing")
        
        # Save complete text for debugging
        self._save_debug_text(text)
        
        # Clean text first
        cleaned_text = self._preprocess_text(text)
        
        # Find all question markers
        questions = self._find_all_questions(cleaned_text)
        
        if not questions:
            logger.warning("No questions found")
            print("⚠️  No question markers detected\n")
            return []
        
        # Extract answers
        results = self._extract_answers(cleaned_text, questions)
        
        logger.info(f"Parsed {len(results)} Q&A pairs")
        return results
    
    def _save_debug_text(self, text: str):
        """Save complete extracted text for debugging."""
        if self.debug_mode:
            try:
                with open("extracted_text_complete.txt", "w", encoding="utf-8") as f:
                    f.write(text)
                print("💾 Complete text saved to: extracted_text_complete.txt")
            except Exception as e:
                logger.warning(f"Could not save debug text: {e}")
            
            # Print preview
            print("\n" + "="*80)
            print("EXTRACTED TEXT PREVIEW (first 1500 characters):")
            print("="*80)
            print(text[:1500])
            if len(text) > 1500:
                print("\n... (see extracted_text_complete.txt for full text)")
            print("="*80 + "\n")
    
    def _preprocess_text(self, text: str) -> str:
        """
        Clean and normalize text before parsing.
        Removes common OCR artifacts but preserves structure.
        """
        # Remove scanner artifacts
        text = re.sub(r'(?:PAGE|PDF)\s+(?:ACE\s+)?Scanner', '', text, flags=re.IGNORECASE)
        
        # Remove standalone image references
        text = re.sub(r'!\[img-\d+\.\w+\]\(img-\d+\.\w+\)\s*', '', text)
        
        # Normalize whitespace (but preserve structure)
        text = re.sub(r'\n\s*\n\s*\n+', '\n\n', text)
        
        return text.strip()
    
    def _find_all_questions(self, text: str) -> List[Tuple[int, int, str]]:
        """
        Find ALL question markers using multiple detection strategies.
        Returns list of (position, question_number, marker_text).
        """
        questions = []
        
        # Strategy 1: Common patterns with numbers
        patterns = [
            # Checkmark/tick patterns
            (r'[✓✔√]\s*(\d+)', 'checkmark'),
            # Q patterns
            (r'\b[Qq]\.?\s*(\d+)\s*[:\)\.]', 'q_with_punct'),
            (r'\b[Qq]\s*(\d+)\b', 'q_simple'),
            # Number patterns at start of line
            (r'^\s*(\d+)\s*[:\)\.]', 'num_with_punct'),
            # Question word
            (r'\bQuestion\s+(\d+)', 'question_word'),
        ]
        
        for pattern, pattern_type in patterns:
            regex = re.compile(pattern, re.MULTILINE | re.IGNORECASE)
            for match in regex.finditer(text):
                try:
                    num = match.group(1)
                    pos = match.start()
                    marker = match.group(0).strip()
                    questions.append((pos, num, marker, pattern_type))
                except (IndexError, AttributeError):
                    continue
        
        # Sort by position and remove duplicates
        questions.sort(key=lambda x: x[0])
        
        # Remove duplicates (same position within 10 chars)
        unique_questions = []
        for q in questions:
            if not unique_questions or q[0] > unique_questions[-1][0] + 10:
                unique_questions.append(q)
        
        # Display found questions
        if unique_questions:
            nums = [q[1] for q in unique_questions]
            print(f"✅ Found {len(unique_questions)} questions: {nums}\n")
            
            # Show where each was found (with context)
            for pos, num, marker, ptype in unique_questions:
                start = max(0, pos - 15)
                end = min(len(text), pos + 60)
                context = text[start:end].replace('\n', ' ')
                context = ' '.join(context.split())  # Normalize spaces
                print(f"   Q{num}: ...{context}...")
            print()
        
        return [(pos, num, marker) for pos, num, marker, _ in unique_questions]
    
    def _extract_answers(
        self, 
        text: str, 
        questions: List[Tuple[int, str, str]]
    ) -> List[Dict[str, Optional[str]]]:
        """
        Extract answer text between consecutive question markers.
        
        Args:
            text: Cleaned text
            questions: List of (position, number, marker)
            
        Returns:
            List of Q&A pairs
        """
        results = []
        
        for i, (pos, num, marker) in enumerate(questions):
            # Find marker end position
            marker_end = pos + len(marker)
            
            # Determine answer region
            if i + 1 < len(questions):
                next_pos = questions[i + 1][0]
                answer_text = text[marker_end:next_pos]
            else:
                answer_text = text[marker_end:]
            
            # Clean the answer
            answer_text = self._clean_answer(answer_text)
            
            results.append({
                "question_number": num,
                "student_answer": answer_text if answer_text else None
            })
            
            char_count = len(answer_text) if answer_text else 0
            logger.debug(f"Q{num}: {char_count} characters")
            print(f"  Q{num}: {char_count} characters")
        
        print()
        return results
    
    def _clean_answer(self, text: str) -> str:
        """
        Clean answer text by removing artifacts and normalizing.
        """
        if not text:
            return text
        
        text = text.strip()
        
        # Remove "Answer:", "Ans:", "Solution:" at start
        text = re.sub(
            r'^(?:Answer|Ans?|Solution)\s*[:\-\s]+', 
            '', 
            text, 
            flags=re.IGNORECASE
        ).strip()
        
        # Remove any remaining image references
        text = re.sub(r'!\[img-\d+\.\w+\]\(img-\d+\.\w+\)', '', text)
        
        # Remove extra blank lines (max 2 newlines)
        text = re.sub(r'\n\s*\n\s*\n+', '\n\n', text)
        
        # Remove leading/trailing whitespace from each line
        lines = [line.rstrip() for line in text.split('\n')]
        text = '\n'.join(lines)
        
        return text.strip()


def extract_handwritten_answers(
    file_path: str,
    answers_only: bool = True
) -> List[Dict[str, Optional[str]]]:
    """
    Extract question-answer pairs from handwritten answer sheets.
    
    Uses Mistral OCR for text extraction and intelligent parsing
    to automatically detect various question numbering formats.
    
    Args:
        file_path: Path to PDF or image file
        answers_only: If True, returns simplified format (default)
        
    Returns:
        List of {"question_number": str, "student_answer": str}
        
    Raises:
        FileNotFoundError: If file doesn't exist
        ValueError: If API key not configured or unsupported format
        Exception: For OCR or parsing errors
        
    Example:
        >>> results = extract_handwritten_answers("answers.pdf")
        >>> print(results[0])
        {'question_number': '1', 'student_answer': 'The answer is...'}
    """
    logger.info(f"Extracting from: {file_path}")
    
    print("\n" + "="*80)
    print("HANDWRITTEN ANSWER EXTRACTION")
    print("="*80)
    
    try:
        # Extract text using Mistral OCR
        extractor = MistralOCRExtractor()
        text = extractor.extract_text(file_path)
        
        # Parse Q&A pairs
        parser = AnswerSheetParser()
        results = parser.parse(text)
        
        # Save results
        if results:
            import json
            with open("extraction_results.json", "w", encoding="utf-8") as f:
                json.dump(results, f, indent=2, ensure_ascii=False)
            print(f"💾 Results saved to: extraction_results.json\n")
        
        print("="*80)
        print(f"✅ COMPLETE: Extracted {len(results)} questions")
        print("="*80 + "\n")
        
        return results
        
    except Exception as e:
        logger.error(f"Extraction failed: {e}")
        print(f"\n❌ Error: {e}\n")
        raise


def split_into_qas_mistral(
    pdf_path: str,
    answers_only: bool = True
) -> List[Dict[str, Optional[str]]]:
    """
    Alternative interface matching extraction_answersheet.py.
    
    Args:
        pdf_path: Path to PDF file
        answers_only: Returns simplified format
        
    Returns:
        List of Q&A pairs
    """
    return extract_handwritten_answers(pdf_path, answers_only=answers_only)
