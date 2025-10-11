import re
import PyPDF2

def extract_text_from_mark_scheme(file_path):
    mark_scheme_text = ""
    with open(file_path, "rb") as f:
        reader = PyPDF2.PdfReader(f)
        for page in reader.pages:
            mark_scheme_text += page.extract_text() + "\n"
    return mark_scheme_text

def extract_text_from_answer_sheet(file_path):
    answer_sheet_text = ""
    with open(file_path, "rb") as f:
        reader = PyPDF2.PdfReader(f)
        for page in reader.pages:
            answer_sheet_text += page.extract_text() + "\n"
    return answer_sheet_text

def parse_answer_paper(text):
    # Split into Q&A
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
