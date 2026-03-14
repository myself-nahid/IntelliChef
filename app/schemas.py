from pydantic import BaseModel, Field
from typing import List, Optional, Literal, Union
from typing_extensions import Annotated

# RECIPE — Request

class IngredientInput(BaseModel):
    name: str
    stock_status: Optional[str] = "OK"

class RecipeRequest(BaseModel):
    prompt: str
    available_ingredients: List[IngredientInput] = []
    constraints: Optional[str] = None
    language: str = "English"


# RECIPE — Response union  (TYPE 1–4)

class IngredientOutput(BaseModel):
    name: str
    quantity: float
    unit: str
    stock_status: Optional[str] = None

class RecipeResponse(BaseModel):
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
    type: Literal["general"]
    answer: str

class OffTopicResponse(BaseModel):
    type: Literal["off_topic"]
    answer: str
    note: Optional[str] = None

class ErrorResponse(BaseModel):
    type: Literal["error"]
    message: str

# Discriminated union — Pydantic picks the right model via "type"
AIResponse = Annotated[
    Union[RecipeResponse, GeneralResponse, OffTopicResponse, ErrorResponse],
    Field(discriminator="type")
]


# SPECIALS — Request

class SpecialsRequest(BaseModel):
    prompt: Optional[str] = None          # user's free-text message (new)
    expiring_items: List[str] = []
    season: str = "Any"
    cuisine_style: Optional[str] = None
    target_audience: Optional[str] = None
    constraints: Optional[str] = None
    language: str = "English"


# SPECIALS — Response union  (TYPE 1–5)

class SpecialDish(BaseModel):
    dish_name: str
    course: Optional[str] = None
    description: str
    key_ingredients_used: List[str]
    cooking_method: Optional[str] = None
    estimated_prep_time_minutes: Optional[int] = None
    difficulty: Optional[str] = None
    waste_recovery_note: Optional[str] = None
    chef_tip: Optional[str] = None

class SpecialsAIResponse(BaseModel):
    """TYPE 1 — full specials list."""
    type: Literal["specials"]
    season: Optional[str] = None
    total_expiring_items_used: Optional[int] = None
    suggestions: List[SpecialDish]

class SpecialsAdviceResponse(BaseModel):
    """TYPE 2 — menu engineering advice."""
    type: Literal["menu_advice"]
    topic: str
    answer: str
    action_items: Optional[List[str]] = None

class SpecialsGeneralResponse(BaseModel):
    """TYPE 3 — greeting / small talk."""
    type: Literal["general"]
    answer: str

class SpecialsOffTopicResponse(BaseModel):
    """TYPE 4 — off-topic question."""
    type: Literal["off_topic"]
    answer: str
    redirect: Optional[str] = None

class SpecialsErrorResponse(BaseModel):
    """TYPE 5 — error / unsafe request."""
    type: Literal["error"]
    message: str
    suggestion: Optional[str] = None

# Discriminated union for specials endpoint
SpecialsResponse = Annotated[
    Union[
        SpecialsAIResponse,
        SpecialsAdviceResponse,
        SpecialsGeneralResponse,
        SpecialsOffTopicResponse,
        SpecialsErrorResponse,
    ],
    Field(discriminator="type")
]


# CHAT — Request & Response

class ChatRequest(BaseModel):
    question: str
    context_data: str
    language: str = "English"

class ChatResponse(BaseModel):
    answer: str