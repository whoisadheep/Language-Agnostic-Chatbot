import io
import re
import json
from typing import Dict, Any, List, Optional
from pypdf import PdfReader
from docx import Document
from router import ai_router

def extract_text_from_file(file_bytes: bytes, filename: str) -> str:
    """Extract plain text from PDF, DOCX, or plain text file."""
    fname_lower = filename.lower()
    text = ""
    try:
        if fname_lower.endswith(".pdf"):
            reader = PdfReader(io.BytesIO(file_bytes))
            for page in reader.pages:
                extracted = page.extract_text()
                if extracted:
                    text += extracted + "\n"
        elif fname_lower.endswith(".docx"):
            doc = Document(io.BytesIO(file_bytes))
            for para in doc.paragraphs:
                if para.text:
                    text += para.text + "\n"
        else: # assume text/plain or markdown
            text = file_bytes.decode("utf-8", errors="ignore")
    except Exception as e:
        print(f"Error parsing file {filename}: {e}")
        text = file_bytes.decode("utf-8", errors="ignore")
    return text.strip()

def parse_resume_to_vault(resume_text: str) -> Dict[str, Any]:
    """
    Parses resume text into structured profile slots and memory snippets using AI Router.
    """
    system_prompt = (
        "You are an expert ATS document and profile parser. "
        "Extract the applicant's profile and return ONLY a valid JSON object with NO extra markdown or formatting.\n"
        "Schema:\n"
        "{\n"
        '  "full_name": string,\n'
        '  "email": string,\n'
        '  "phone": string,\n'
        '  "linkedin": string,\n'
        '  "github": string,\n'
        '  "portfolio": string,\n'
        '  "university": string,\n'
        '  "degree": string,\n'
        '  "gpa": string,\n'
        '  "graduation_year": string,\n'
        '  "skills": [string],\n'
        '  "experiences": [{"role": string, "company": string, "summary": string}],\n'
        '  "projects": [{"title": string, "tech": [string], "summary": string}]\n'
        "}"
    )

    prompt = f"Extract structured profile information from this resume:\n\n{resume_text[:4000]}"
    res = ai_router.complete(prompt, system_prompt=system_prompt)
    raw = res.get("text", "{}")

    # Clean markdown json fencing if present
    clean_json = re.sub(r"^```(?:json)?\s*", "", raw.strip())
    clean_json = re.sub(r"\s*```$", "", clean_json.strip())

    try:
        parsed = json.loads(clean_json)
    except Exception as e:
        print(f"Failed to parse LLM JSON: {e}, raw: {raw[:200]}")
        parsed = {
            "full_name": "",
            "email": "",
            "phone": "",
            "university": "",
            "degree": "",
            "skills": [],
            "experiences": [],
            "projects": []
        }
    return parsed

def evaluate_trick_question(question: str) -> bool:
    """Detect trick or negative questions that require careful user review."""
    trick_patterns = [
        r"\bNOT\b", r"\bEXCEPT\b", r"\bLEAST\b", r"\bNEVER\b",
        r"\bnone of the above\b", r"\bwhich of the following is false\b"
    ]
    for pattern in trick_patterns:
        if re.search(pattern, question, re.IGNORECASE):
            return True
    return False

def solve_form_fields(fields: List[Dict[str, Any]], profile_data: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Given a list of form questions and applicant's profile/memory vault,
    generates grounded answers with confidence scores and trick question flags.
    """
    results = []
    profile_summary = json.dumps(profile_data, indent=2)

    for field in fields:
        field_id = field.get("id") or field.get("name") or "field"
        question = field.get("label") or field.get("question") or "Question"
        field_type = field.get("type", "text")
        options = field.get("options", [])

        is_trick = evaluate_trick_question(question)

        system_prompt = (
            "You are an intelligent form autofill agent. Given the user's profile and memory, "
            "provide the best, most accurate answer for the requested form field.\n"
            "Return JSON ONLY with schema:\n"
            '{"answer": string, "confidence": number (0-100), "reason": string}'
        )

        prompt = (
            f"User Profile:\n{profile_summary}\n\n"
            f"Field Label: {question}\n"
            f"Field Type: {field_type}\n"
            f"Available Options: {options if options else 'Free text'}\n"
            "Respond with the best answer matching the profile."
        )

        try:
            res = ai_router.complete(prompt, system_prompt=system_prompt)
            raw = res.get("text", "{}")
            clean_json = re.sub(r"^```(?:json)?\s*", "", raw.strip())
            clean_json = re.sub(r"\s*```$", "", clean_json.strip())
            answer_data = json.loads(clean_json)
            ans = str(answer_data.get("answer", ""))
            confidence = int(answer_data.get("confidence", 85))
            reason = str(answer_data.get("reason", "Matched profile data"))
        except Exception:
            ans = ""
            confidence = 50
            reason = "Direct heuristic fallback"

        review_needed = is_trick or confidence < 80

        results.append({
            "id": field_id,
            "question": question,
            "answer": ans,
            "confidence": confidence,
            "review_recommended": review_needed,
            "reason": "⚠️ Negative / Trick phrasing detected" if is_trick else reason,
            "type": field_type,
            "options": options
        })

    return results
