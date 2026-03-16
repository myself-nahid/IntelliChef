from pydantic import BaseModel, field_validator, model_serializer
from typing import List, Optional, Literal, Union, Any
from typing_extensions import Annotated
from pydantic import Field


# ══════════════════════════════════════════════════════════════════════════════
# SHARED — uniform API envelope for every endpoint
# ══════════════════════════════════════════════════════════════════════════════

class APIResponse(BaseModel):
    """
    Every endpoint returns this wrapper.
    {
        "success": true,
        "message": "...",
        "data":    { ... },   # payload specific to each endpoint
        "error":   null       # populated only on failure
    }
    """
    success: bool
    message: str
    data: Optional[Any] = None
    error: Optional[str] = None


# ══════════════════════════════════════════════════════════════════════════════
# RECIPE — Request
# ══════════════════════════════════════════════════════════════════════════════

class IngredientInput(BaseModel):
    name: str
    stock_status: Optional[str] = "OK"
    current_stock: Optional[float] = None
    minimum_stock: Optional[float] = None
    unit: Optional[str] = None
    category: Optional[str] = None
    outlet_type: Optional[str] = None
    is_special: Optional[bool] = None
    status: Optional[str] = None


class RecipeRequest(BaseModel):
    prompt: str
    available_ingredients: List[IngredientInput] = []
    constraints: Optional[str] = None
    language: str = "English"


# ══════════════════════════════════════════════════════════════════════════════
# RECIPE — Ingredient output
# ══════════════════════════════════════════════════════════════════════════════

class IngredientOutput(BaseModel):
    name: str

    # float for normal quantities; str preserved for "to taste" / "as needed"
    quantity: Union[float, str]

    # None / omitted when quantity is a qualifier like "to taste"
    unit: Optional[str] = None

    # "available" | "substitute" | "pantry_staple"
    stock_status: Optional[str] = None

    # "inventory" | "substitute" | "pantry_staple"
    source: Optional[str] = None

    @field_validator("quantity", mode="before")
    @classmethod
    def coerce_quantity(cls, v):
        if isinstance(v, (int, float)):
            return float(v)
        if isinstance(v, str):
            try:
                return float(v)
            except ValueError:
                return v.strip()   # keep "to taste", "as needed", etc.
        return v

    def model_dump(self, **kwargs):
        """
        Custom serialisation:
        - Omit quantity (and unit) when the value is 0.0 — pantry staples that
          the AI encoded as quantity:0 / unit:"to taste".  Replace with
          quantity: null, unit: "to taste" so the frontend can render cleanly.
        - Strip any field whose value is None (exclude_none behaviour per field).
        """
        d = super().model_dump(**kwargs)
        if d.get("quantity") == 0.0:
            d["quantity"] = None
            d.setdefault("unit", "to taste")
        return {k: v for k, v in d.items() if v is not None or k in ("quantity",)}


class SubstitutionNote(BaseModel):
    original: str
    used_instead: str
    reason: str


class MissingIngredient(BaseModel):
    name: str
    is_critical: bool
    impact: Optional[str] = None
    suggested_substitute: Optional[str] = None
    shopping_note: Optional[str] = None


# ══════════════════════════════════════════════════════════════════════════════
# RECIPE — Inventory summary (built in service layer, never sent to AI)
# ══════════════════════════════════════════════════════════════════════════════

class InventorySummary(BaseModel):
    total_inventory_items: int
    items_used_in_recipe: List[str]
    items_not_used: List[str]
    pantry_staples_used: List[str]
    missing_critical: List[str]
    missing_optional: List[str]


# ══════════════════════════════════════════════════════════════════════════════
# RECIPE — Strongly-typed per-kind payloads  (what goes inside data{})
# Using separate models per kind eliminates null pollution entirely.
# ══════════════════════════════════════════════════════════════════════════════

class RecipeData(BaseModel):
    """
    Returned when the AI produced a recipe (can_be_prepared true or false).
    No answer/note/error_message fields — those belong to other kinds.
    """
    can_be_prepared: bool
    pivoted: bool = False
    preparation_note: Optional[str] = None
    original_request: str
    constraints: Optional[str] = None
    inventory_summary: InventorySummary
    title: str
    description: str
    prep_time_minutes: Optional[int] = None
    cook_time_minutes: Optional[int] = None
    servings: Optional[int] = None
    difficulty: Optional[str] = None
    ingredients: List[IngredientOutput]
    substitutions: List[SubstitutionNote] = []
    missing_ingredients: List[MissingIngredient] = []
    steps: List[str]
    tips: Optional[str] = None


class GeneralData(BaseModel):
    """Returned for greetings, small talk, or cooking Q&A (no recipe)."""
    original_request: str
    answer: str


class OffTopicData(BaseModel):
    """Returned when the question is unrelated to food/cooking."""
    original_request: str
    answer: str
    note: Optional[str] = None


class ErrorData(BaseModel):
    """Returned when the request cannot be fulfilled."""
    original_request: str
    error_message: str


# ══════════════════════════════════════════════════════════════════════════════
# INTERNAL AI response models  (used only inside recipe_generator.py)
# Prefixed with _ to signal: never expose these to the client.
# ══════════════════════════════════════════════════════════════════════════════

class _RecipeAI(BaseModel):
    type: Literal["recipe"]
    title: str
    description: str
    prep_time_minutes: Optional[int] = None
    cook_time_minutes: Optional[int] = None
    servings: Optional[int] = None
    difficulty: Optional[str] = None
    can_be_prepared: bool = True
    pivoted: bool = False
    preparation_note: Optional[str] = None
    ingredients: List[IngredientOutput]
    substitutions: Optional[List[SubstitutionNote]] = []
    missing_ingredients: Optional[List[MissingIngredient]] = []
    steps: List[str]
    tips: Optional[str] = None


class _GeneralAI(BaseModel):
    type: Literal["general"]
    answer: str


class _OffTopicAI(BaseModel):
    type: Literal["off_topic"]
    answer: str
    note: Optional[str] = None


class _ErrorAI(BaseModel):
    type: Literal["error"]
    message: str


_AIResponse = Annotated[
    Union[_RecipeAI, _GeneralAI, _OffTopicAI, _ErrorAI],
    Field(discriminator="type")
]


# ══════════════════════════════════════════════════════════════════════════════
# SPECIALS — Request
# ══════════════════════════════════════════════════════════════════════════════

class SpecialsRequest(BaseModel):
    prompt: Optional[str] = None
    expiring_items: List[str] = []
    season: str = "Any"
    cuisine_style: Optional[str] = None
    target_audience: Optional[str] = None
    constraints: Optional[str] = None
    language: str = "English"


# ══════════════════════════════════════════════════════════════════════════════
# SPECIALS — Internal AI response models
# ══════════════════════════════════════════════════════════════════════════════

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


class _SpecialsAI(BaseModel):
    type: Literal["specials"]
    season: Optional[str] = None
    total_expiring_items_used: Optional[int] = None
    suggestions: List[SpecialDish]


class _SpecialsAdviceAI(BaseModel):
    type: Literal["menu_advice"]
    topic: str
    answer: str
    action_items: Optional[List[str]] = None


class _SpecialsGeneralAI(BaseModel):
    type: Literal["general"]
    answer: str


class _SpecialsOffTopicAI(BaseModel):
    type: Literal["off_topic"]
    answer: str
    redirect: Optional[str] = None


class _SpecialsErrorAI(BaseModel):
    type: Literal["error"]
    message: str
    suggestion: Optional[str] = None


_SpecialsAIResponse = Annotated[
    Union[
        _SpecialsAI, _SpecialsAdviceAI, _SpecialsGeneralAI,
        _SpecialsOffTopicAI, _SpecialsErrorAI,
    ],
    Field(discriminator="type")
]


# ══════════════════════════════════════════════════════════════════════════════
# CHAT — Request & Response
# ══════════════════════════════════════════════════════════════════════════════

class ChatRequest(BaseModel):
    question: str
    context_data: str
    language: str = "English"


class ChatResponse(BaseModel):
    answer: str