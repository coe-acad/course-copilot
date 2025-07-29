import sys
import os
import time
from pathlib import Path

# Add the app directory to the Python path
sys.path.append(os.path.join(os.path.dirname(__file__), 'app'))

from app.services.openai_service import create_assistant, create_vector_store, connect_file_to_vector_store, create_file
from app.services.mongo import create_course, get_course
from app.routes.resources import create_course_description_file
from app.utils.course_pdf_utils import generate_course_pdf
from app.utils.openai_client import client

def test_create_course_and_vector_store():
    print("=== Test: Create Course, Vector Store, and Link ===\n")
    output = create_course_description_file("f91e3c94-7bc3-4677-abba-c66d3f409e63", "test_user_001")
    print(output)
    # # Step 1: Create an assistant
    # assistant_id = create_assistant()
    # print(f"✅ Assistant created: {assistant_id}")

    # # Step 2: Create a vector store and link to assistant
    # vector_store_id = create_vector_store(assistant_id)
    # print(f"✅ Vector store created: {vector_store_id}")
    # client.beta.assistants.update(
    #     assistant_id,
    #     tool_resources={
    #         "file_search": {
    #             "vector_store_ids": [vector_store_id]
    #         }
    #     }
    # )
    # print(f"✅ Linked vector store to assistant")

    # # Step 3: Create a course in MongoDB with vector store ID
    # course_data = {
    #     "name": "Test Course for Vector Store Integration",
    #     "description": "dummy course description",
    #     "user_id": "test_user_001",
    #     "assistant_id": assistant_id,
    #     "vector_store_id": vector_store_id
    # }
    # course_id = create_course(course_data)
    # print(f"✅ Course created: {course_id}")

    # # Step 4: Generate course description PDF
    # pdf_path = generate_course_pdf(course_id, "test_user_001")
    # if pdf_path and os.path.exists(pdf_path):
    #     print(f"✅ Course description PDF generated: {pdf_path}")
    # else:
    #     print("❌ Failed to generate course description PDF")
    #     return

    # # Get relative path starting from 'local_storage'
    # pdf_relative_path = Path(pdf_path).as_posix().split("local_storage", 1)[-1]
    # pdf_relative_path = "local_storage" + pdf_relative_path

    # # Step 5: Upload the PDF to OpenAI for vector store and connect to vector store
    # openai_file_id = create_file(pdf_relative_path)
    # print(f"✅ PDF uploaded to OpenAI for vector store: {openai_file_id}")
    # batch_id = connect_file_to_vector_store(vector_store_id, openai_file_id)
    # print(f"✅ File connected to vector store, batch ID: {batch_id}")

    print("\n=== Test Complete ===")

if __name__ == "__main__":
    test_create_course_and_vector_store() 