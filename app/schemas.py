from pydantic import BaseModel, Field
from typing import List, Optional, Literal, Union
from typing_extensions import Annotated


# RECIPE GENERATION — REQUEST 

class IngredientInput(BaseModel):
    name: str
    stock_status: Optional[str] = "OK"

class RecipeRequest(BaseModel):
    prompt: str
    available_ingredients: List[IngredientInput] = []
    constraints: Optional[str] = None
    language: str = "English"


# RECIPE GENERATION — RESPONSE (union of all AI response types) 

class IngredientOutput(BaseModel):
    name: str
    quantity: float
    unit: str
    stock_status: Optional[str] = None   # echoed back from input


class RecipeResponse(BaseModel):
    """TYPE 1 — AI returned a full recipe."""
    type: Literal["recipe"]
    title: str
    description: str
    prep_time_minutes: Optional[int] = None
    cook_time_minutes: Optional[int] = None
    servings: Optional[int] = None
    difficulty: Optional[str] = None
    steps: List[str]
    ingredients: List[IngredientOutput]
    tips: Optional[str] = None


class GeneralResponse(BaseModel):
    """TYPE 2 — greeting, small talk, cooking Q&A (no recipe needed)."""
    type: Literal["general"]
    answer: str


class OffTopicResponse(BaseModel):
    """TYPE 3 — question unrelated to food/cooking."""
    type: Literal["off_topic"]
    answer: str
    note: Optional[str] = None


class ErrorResponse(BaseModel):
    """TYPE 4 — harmful, impossible, or unintelligible request."""
    type: Literal["error"]
    message: str


# Discriminated union — FastAPI/Pydantic picks the right model via "type" field
AIResponse = Annotated[
    Union[RecipeResponse, GeneralResponse, OffTopicResponse, ErrorResponse],
    Field(discriminator="type")
]


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