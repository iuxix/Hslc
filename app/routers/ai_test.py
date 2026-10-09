from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import google.generativeai as genai
from app.config import settings

router = APIRouter(prefix="/api/ai", tags=["AI Test"])


class GenerateRequest(BaseModel):
    prompt: str


@router.get("/test")
def test_gemini():
    """Simple test — Gemini API connected hai ya nahi"""
    try:
        genai.configure(api_key=settings.GEMINI_API_KEY)
        model = genai.GenerativeModel("gemini-1.5-flash")
        response = model.generate_content("Say 'Hello from Gemini' in exactly 5 words.")
        return {
            "status": "success",
            "response": response.text,
            "message": "Gemini API is working! ✅"
        }
    except Exception as e:
        return {
            "status": "error",
            "error": str(e),
            "message": "Gemini API failed ❌"
        }


@router.post("/generate-mcq")
def generate_mcq(req: GenerateRequest):
    """Ek sample MCQ generate karo"""
    try:
        genai.configure(api_key=settings.GEMINI_API_KEY)
        model = genai.GenerativeModel("gemini-1.5-flash")
        
        prompt = f"""Generate exactly 1 MCQ question from this topic: {req.prompt}

Return ONLY valid JSON in this exact format (no extra text, no markdown):
{{
  "question": "Question text here?",
  "options": ["A text", "B text", "C text", "D text"],
  "correct": "A",
  "explanation": "Explanation here"
}}"""
        
        response = model.generate_content(prompt)
        text = response.text.strip()
        
        # Clean markdown if present
        if text.startswith("```"):
            text = text.split("```")[1]
            if text.startswith("json"):
                text = text[4:]
        text = text.strip()
        
        import json
        data = json.loads(text)
        
        return {
            "status": "success",
            "data": data,
            "message": "MCQ generated successfully! ✅"
        }
    except Exception as e:
        return {
            "status": "error",
            "error": str(e),
            "message": "Generation failed ❌"
      }
