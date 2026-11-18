from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from genai.assistant import run_assistant

router = APIRouter(
    prefix="/ai",
    tags=["AI Assistant"]
)

class ChatRequest(BaseModel):
    question: str

class ChatResponse(BaseModel):
    response: str

@router.post("/chat", response_model=ChatResponse)
def chat_with_ai(request: ChatRequest):

    try:
        response = run_assistant(request.question)
        return {
            "response": str(response)
        }
    except Exception as error:

        raise HTTPException(
            status_code=500,
            detail=f"AI assistant error: {str(error)}"
        )
