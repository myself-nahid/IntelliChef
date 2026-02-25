from fastapi import FastAPI, HTTPException, Depends
from pydantic_settings import BaseSettings
from app.schemas import RecipeRequest, RecipeResponse, SpecialsRequest, SpecialsResponse, ChatRequest, ChatResponse
from app.services.recipe_generator import KitchenAI
from app.services.chat_analysis import OperationsAI

# 1. Configuration
class Settings(BaseSettings):
    OPENAI_API_KEY: str
    class Config:
        env_file = ".env"

settings = Settings()
app = FastAPI(title="F&B AI Microservice")

# 2. Dependency Injection
def get_kitchen_ai():
    return KitchenAI(api_key=settings.OPENAI_API_KEY)

def get_ops_ai():
    return OperationsAI(api_key=settings.OPENAI_API_KEY)

# 3. Endpoints

@app.post("/api/v1/generate-recipe", response_model=RecipeResponse)
async def generate_recipe(request: RecipeRequest, service: KitchenAI = Depends(get_kitchen_ai)):
    """
    Backend sends ingredient list -> AI returns Recipe JSON.
    """
    try:
        return await service.generate_recipe(request)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/v1/suggest-specials", response_model=SpecialsResponse)
async def suggest_specials(request: SpecialsRequest, service: KitchenAI = Depends(get_kitchen_ai)):
    """
    Backend sends expiring items -> AI returns menu ideas.
    """
    return await service.suggest_specials(request)

@app.post("/api/v1/chat", response_model=ChatResponse)
async def operational_chat(request: ChatRequest, service: OperationsAI = Depends(get_ops_ai)):
    """
    Backend sends query + DB context -> AI returns natural language answer.
    """
    return await service.analyze_data(request)