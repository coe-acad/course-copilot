#!/usr/bin/env python3
"""
Test script for the course PDF utility using MongoDB
"""

import sys
import os

# Add the app directory to the Python path
sys.path.append(os.path.join(os.path.dirname(__file__), 'app'))

from app.utils.course_pdf_utils import generate_course_pdf, course_pdf_utils

def test_mongo_pdf():
    """
    Test the PDF generation with MongoDB
    """
    print("=== Course PDF Generator with MongoDB ===\n")
    
    # Get course ID from user
    course_id = input("Enter the course ID: ").strip()
    
    if not course_id:
        print("Error: Course ID is required")
        return
    
    print(f"\nTesting PDF generation for course ID: {course_id}")
    
    try:
        # First, let's test getting course info from MongoDB
        print("\n1. Testing course info retrieval from MongoDB...")
        course_info = course_pdf_utils.get_course_info(course_id)
        
        if course_info:
            print(f"✅ Course found in MongoDB!")
            print(f"   Course Name: {course_info.get('name', 'Unknown')}")
            print(f"   Description: {course_info.get('description', 'No description')[:100]}...")
            print(f"   User ID: {course_info.get('user_id', 'Unknown')}")
            
            # Now generate the PDF
            print("\n2. Generating PDF...")
            pdf_path = generate_course_pdf(course_id)
            
            if pdf_path:
                print(f"✅ PDF created successfully!")
                print(f"📁 File location: {os.path.abspath(pdf_path)}")
                print(f"📄 File size: {os.path.getsize(pdf_path)} bytes")
            else:
                print("❌ Failed to generate PDF")
        else:
            print("❌ Course not found in MongoDB")
            
    except Exception as e:
        print(f"\n❌ Error: {str(e)}")
        import traceback
        traceback.print_exc()

def list_available_courses():
    """
    List available courses from MongoDB (if you want to see what courses exist)
    """
    try:
        from app.services.mongo import get_many_from_collection
        
        print("\n=== Available Courses in MongoDB ===")
        courses = get_many_from_collection("courses", {})
        
        if courses:
            print(f"Found {len(courses)} courses:")
            for i, course in enumerate(courses[:10], 1):  # Show first 10 courses
                print(f"{i}. ID: {course.get('_id', 'Unknown')}")
                print(f"   Name: {course.get('name', 'Unknown')}")
                print(f"   User: {course.get('user_id', 'Unknown')}")
                print()
        else:
            print("No courses found in MongoDB")
            
    except Exception as e:
        print(f"Error listing courses: {str(e)}")

if __name__ == "__main__":
    print("Choose an option:")
    print("1. Generate PDF for a course")
    print("2. List available courses")
    
    choice = input("\nEnter your choice (1 or 2): ").strip()
    
    if choice == "1":
        test_mongo_pdf()
    elif choice == "2":
        list_available_courses()
    else:
        print("Invalid choice. Running PDF generation test...")
        test_mongo_pdf() 