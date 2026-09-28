from fastapi import APIRouter, Depends
from pydantic import BaseModel
from openai import OpenAI
from dotenv import load_dotenv

from backend.auth import get_current_user
from backend.models import UserDB

import os

load_dotenv()

router = APIRouter()

client = OpenAI(
    api_key=os.getenv("OPENAI_API_KEY")
)

class ChatRequest(BaseModel):
    message: str

@router.post("/ai/chat")
async def ai_chat(req: ChatRequest, current_user: UserDB = Depends(get_current_user)):

    response = client.responses.create(
        model="gpt-5.5",
        input=req.message
    )

    return {
        "reply": response.output_text
    }