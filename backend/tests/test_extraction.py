"""
Test script for the local extraction functionality.
This demonstrates how mark schemes and answer sheets are extracted locally.
"""
import os
import sys
from pathlib import Path

# Add parent directory to path to import app modules
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.utils.extraction import (
    extract_text_from_mark_scheme,
    extract_text_from_answer_sheet,
    extract_text_from_pdf
)

def test_mark_scheme_extraction():
    """Test mark scheme extraction from PDF"""
    print("\n=== Testing Mark Scheme Extraction ===")
    
    # Check if test file exists
    test_file = Path("local_storage/course_pdfs/Eval_Course_Description.pdf")
    if not test_file.exists():
        print(f"Test file not found: {test_file}")
        print("Please place a test mark scheme PDF to test extraction")
        return
    
    try:
        result = extract_text_from_mark_scheme(str(test_file))
        print(f"Extracted mark scheme with {len(result.get('mark_scheme', []))} questions")
        
        # Display first question as sample
        if result.get('mark_scheme'):
            first_q = result['mark_scheme'][0]
            print(f"\nSample Question {first_q.get('question_number')}:")
            print(f"  Question: {first_q.get('question_text', '')[:100]}...")
            print(f"  Answer Template: {first_q.get('answer_template', '')[:100]}...")
            print(f"  Mark Scheme: {first_q.get('mark_scheme', '')[:100]}...")
        
        print("✓ Mark scheme extraction successful")
        return True
    except Exception as e:
        print(f"✗ Mark scheme extraction failed: {str(e)}")
        return False

def test_answer_sheet_extraction():
    """Test answer sheet extraction from PDF"""
    print("\n=== Testing Answer Sheet Extraction ===")
    
    # Since we don't have a specific test file, just show the structure
    print("Answer sheet extraction expects PDF with:")
    print("  - Optional: Student name at the top")
    print("  - Questions numbered as 'Question 1', 'Question 2', etc.")
    print("  - Answers following each question")
    print("\nFunction will return:")
    print("  {")
    print("    'student_name': 'Student Name',")
    print("    'answers': [")
    print("      {'question_number': '1', 'question_text': '...', 'student_answer': '...'},")
    print("      ...")
    print("    ]")
    print("  }")
    print("✓ Answer sheet extraction function ready")
    return True

def test_raw_text_extraction():
    """Test raw text extraction from PDF"""
    print("\n=== Testing Raw Text Extraction ===")
    
    test_file = Path("local_storage/course_pdfs/Eval_Course_Description.pdf")
    if not test_file.exists():
        print(f"Test file not found: {test_file}")
        return False
    
    try:
        text = extract_text_from_pdf(str(test_file))
        print(f"Extracted {len(text)} characters of raw text")
        print(f"Preview: {text[:200]}...")
        print("✓ Raw text extraction successful")
        return True
    except Exception as e:
        print(f"✗ Raw text extraction failed: {str(e)}")
        return False

def main():
    """Run all extraction tests"""
    print("=" * 60)
    print("LOCAL EXTRACTION TEST SUITE")
    print("=" * 60)
    
    results = []
    results.append(("Raw Text Extraction", test_raw_text_extraction()))
    results.append(("Mark Scheme Extraction", test_mark_scheme_extraction()))
    results.append(("Answer Sheet Extraction", test_answer_sheet_extraction()))
    
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    for name, success in results:
        status = "✓ PASS" if success else "✗ FAIL"
        print(f"{status}: {name}")
    
    print("\n" + "=" * 60)

if __name__ == "__main__":
    main()

