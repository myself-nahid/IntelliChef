import json
from openai import AsyncOpenAI
from app.schemas import (
    RecipeRequest, AIResponse,
    SpecialsRequest, SpecialsResponse,
    RecipeResponse, GeneralResponse, OffTopicResponse, ErrorResponse,
)
from app.prompts import RECIPE_SYSTEM_PROMPT, SPECIALS_SYSTEM_PROMPT


# Maps the "type" field returned by the AI to the correct Pydantic model
RESPONSE_TYPE_MAP = {
    "recipe":    RecipeResponse,
    "general":   GeneralResponse,
    "off_topic": OffTopicResponse,
    "error":     ErrorResponse,
}


class KitchenAI:
    def __init__(self, api_key: str):
        self.client = AsyncOpenAI(api_key=api_key)

    async def generate_recipe(self, data: RecipeRequest) -> AIResponse:
        ing_list = ", ".join(
            [f"{i.name} ({i.stock_status})" for i in data.available_ingredients]
        )

        user_content = (
            f"Request: {data.prompt}\n"
            f"Available Ingredients: {ing_list or 'None provided'}\n"
            f"Constraints: {data.constraints or 'None'}"
        )

        formatted_system_prompt = RECIPE_SYSTEM_PROMPT.format(language=data.language)

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

        # Route to the correct schema based on the "type" field the AI returned
        response_type = raw.get("type", "error")
        model_class = RESPONSE_TYPE_MAP.get(response_type, ErrorResponse)

        if response_type not in RESPONSE_TYPE_MAP:
            # AI returned an unknown type — wrap it as an error
            return ErrorResponse(
                type="error",
                message=f"Unexpected response type from AI: '{response_type}'"
            )

        return model_class(**raw)

    async def suggest_specials(self, data: SpecialsRequest) -> SpecialsResponse:
        user_content = (
            f"Expiring Items: {', '.join(data.expiring_items)}\n"
            f"Season: {data.season}"
        )

        formatted_system_prompt = SPECIALS_SYSTEM_PROMPT.format(language=data.language)

        response = await self.client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": formatted_system_prompt},
                {"role": "user",   "content": user_content},
            ],
            response_format={"type": "json_object"},
            temperature=0.7,
        )

        result = json.loads(response.choices[0].message.content)
        return SpecialsResponse(**result)