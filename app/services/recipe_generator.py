import json
from openai import AsyncOpenAI
from app.schemas import (
    RecipeRequest, AIResponse,
    SpecialsRequest, SpecialsResponse,
    RecipeResponse, GeneralResponse, OffTopicResponse, ErrorResponse,
    SpecialsAIResponse, SpecialsAdviceResponse,
    SpecialsGeneralResponse, SpecialsOffTopicResponse, SpecialsErrorResponse,
)
from app.prompts import RECIPE_SYSTEM_PROMPT, SPECIALS_SYSTEM_PROMPT


# Recipe: maps AI "type" → Pydantic model 
RECIPE_TYPE_MAP = {
    "recipe":    RecipeResponse,
    "general":   GeneralResponse,
    "off_topic": OffTopicResponse,
    "error":     ErrorResponse,
}

# Specials: maps AI "type" → Pydantic model 
SPECIALS_TYPE_MAP = {
    "specials":    SpecialsAIResponse,
    "menu_advice": SpecialsAdviceResponse,
    "general":     SpecialsGeneralResponse,
    "off_topic":   SpecialsOffTopicResponse,
    "error":       SpecialsErrorResponse,
}


class KitchenAI:
    def __init__(self, api_key: str):
        self.client = AsyncOpenAI(api_key=api_key)

    # generate-recipe 
    async def generate_recipe(self, data: RecipeRequest) -> AIResponse:
        ing_list = ", ".join(
            [f"{i.name} ({i.stock_status})" for i in data.available_ingredients]
        ) or "None provided"

        user_content = (
            f"Request: {data.prompt}\n"
            f"Available Ingredients: {ing_list}\n"
            f"Constraints: {data.constraints or 'None'}"
        )

        formatted_system_prompt = RECIPE_SYSTEM_PROMPT.format(
            language=data.language
        )

        response = await self.client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": formatted_system_prompt},
                {"role": "user",   "content": user_content},
            ],
            response_format={"type": "json_object"},
            temperature=0.7,
        )

        raw = json.loads(response.choices[0].message.content)
        response_type = raw.get("type", "error")
        model_class = RECIPE_TYPE_MAP.get(response_type, ErrorResponse)

        if response_type not in RECIPE_TYPE_MAP:
            return ErrorResponse(
                type="error",
                message=f"Unexpected response type from AI: '{response_type}'"
            )

        return model_class(**raw)

    # suggest-specials 
    async def suggest_specials(self, data: SpecialsRequest) -> SpecialsResponse:
        user_content = (
            f"Expiring Items: {', '.join(data.expiring_items) or 'None provided'}\n"
            f"Season: {data.season}\n"
            f"Cuisine Style: {getattr(data, 'cuisine_style', 'Any')}\n"
            f"Target Audience: {getattr(data, 'target_audience', 'General')}\n"
            f"Constraints: {getattr(data, 'constraints', 'None')}"
        )

        # FIX: pass ALL placeholders used in SPECIALS_SYSTEM_PROMPT
        formatted_system_prompt = SPECIALS_SYSTEM_PROMPT.format(
            language=data.language,
            season=data.season,     # ← root cause of 500: was missing
        )

        response = await self.client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": formatted_system_prompt},
                {"role": "user",   "content": user_content},
            ],
            response_format={"type": "json_object"},
            temperature=0.7,
        )

        raw = json.loads(response.choices[0].message.content)
        response_type = raw.get("type", "error")
        model_class = SPECIALS_TYPE_MAP.get(response_type, SpecialsErrorResponse)

        if response_type not in SPECIALS_TYPE_MAP:
            return SpecialsErrorResponse(
                type="error",
                message=f"Unexpected response type from AI: '{response_type}'"
            )

        return model_class(**raw)