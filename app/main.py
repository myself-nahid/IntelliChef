from fastapi import FastAPI, HTTPException, Depends
from pydantic_settings import BaseSettings

from app.schemas import (
    RecipeRequest, AIResponse,
    SpecialsRequest, SpecialsResponse,
    ChatRequest, ChatResponse,
)
from app.services.recipe_generator import KitchenAI
from app.services.chat_analysis import OperationsAI


# Configuration 

class Settings(BaseSettings):
    OPENAI_API_KEY: str
    class Config:
        env_file = ".env"

settings = Settings()
app = FastAPI(title="F&B AI Microservice")


# Dependency Injection 

def get_kitchen_ai() -> KitchenAI:
    return KitchenAI(api_key=settings.OPENAI_API_KEY)

def get_ops_ai() -> OperationsAI:
    return OperationsAI(api_key=settings.OPENAI_API_KEY)


# Endpoints 
@app.post("/api/v1/generate-recipe", response_model=AIResponse)
async def generate_recipe(
    request: RecipeRequest,
    service: KitchenAI = Depends(get_kitchen_ai),
):
    """
    Accepts a user prompt + ingredient list.
    Returns one of: recipe | general | off_topic | error
    depending on what the user actually asked.
    """
    try:
        return await service.generate_recipe(request)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/v1/suggest-specials", response_model=SpecialsResponse)
async def suggest_specials(
    request: SpecialsRequest,
    service: KitchenAI = Depends(get_kitchen_ai),
):
    """
    Accepts expiring items -> returns 3 daily special suggestions.
    """
    try:
        return await service.suggest_specials(request)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/v1/chat", response_model=ChatResponse)
async def operational_chat(
    request: ChatRequest,
    service: OperationsAI = Depends(get_ops_ai),
):
    """
    Accepts a query + DB context -> returns answer or TOOL_CALL instruction.
    """
    try:
        return await service.analyze_data(request)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))