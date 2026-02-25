from pydantic import BaseModel, Field
from typing import List, Optional, Dict

# RECIPE GENERATION
class IngredientInput(BaseModel):
    name: str
    stock_status: Optional[str] = "OK"  # e.g., "OK", "Low", "Waste Risk"

class RecipeRequest(BaseModel):
    prompt: str  # User's request, e.g. "Spicy pasta"
    available_ingredients: List[IngredientInput] # Backend sends this list
    constraints: Optional[str] = None # e.g. "No gluten"

class IngredientOutput(BaseModel):
    name: str
    quantity: float
    unit: str

class RecipeResponse(BaseModel):
    title: str
    description: str
    steps: List[str]
    ingredients: List[IngredientOutput]
    # Note: return quantities. The backend calculates cost.

# DAILY SPECIALS
class SpecialsRequest(BaseModel):
    expiring_items: List[str] # Backend sends ["Tomato", "Milk"]
    season: str = "Summer"

class SpecialItem(BaseModel):
    dish_name: str
    description: str
    key_ingredients_used: List[str]

class SpecialsResponse(BaseModel):
    suggestions: List[SpecialItem]

# CHAT / Q&A 
class ChatRequest(BaseModel):
    question: str
    # The Backend Developer must perform the DB search FIRST and send the context
    context_data: str 
    # Example context_data: "Salmon Price: $20/kg, Supplier: FishCo. Stock: 5kg."

class ChatResponse(BaseModel):
    answer: str