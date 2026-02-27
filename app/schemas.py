from pydantic import BaseModel, Field
from typing import List, Optional

# RECIPE GENERATION 
class IngredientInput(BaseModel):
    name: str
    stock_status: Optional[str] = "OK"

class RecipeRequest(BaseModel):
    prompt: str 
    available_ingredients: List[IngredientInput] 
    constraints: Optional[str] = None
    language: str = "English"  

class IngredientOutput(BaseModel):
    name: str
    quantity: float
    unit: str

class RecipeResponse(BaseModel):
    title: str
    description: str
    steps: List[str]
    ingredients: List[IngredientOutput]

# DAILY SPECIALS 
class SpecialsRequest(BaseModel):
    expiring_items: List[str]
    season: str = "Any"
    language: str = "English" 

class SpecialItem(BaseModel):
    dish_name: str
    description: str
    key_ingredients_used: List[str]

class SpecialsResponse(BaseModel):
    suggestions: List[SpecialItem]

# CHAT / Q&A 
class ChatRequest(BaseModel):
    question: str
    context_data: str 
    language: str = "English" 

class ChatResponse(BaseModel):
    answer: str