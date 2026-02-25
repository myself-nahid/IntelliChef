import json
from openai import AsyncOpenAI
from app.schemas import RecipeRequest, RecipeResponse, SpecialsRequest, SpecialsResponse
from app.prompts import RECIPE_SYSTEM_PROMPT, SPECIALS_SYSTEM_PROMPT

class KitchenAI:
    def __init__(self, api_key: str):
        self.client = AsyncOpenAI(api_key=api_key)

    # --- METHOD 1: RECIPES ---
    async def generate_recipe(self, data: RecipeRequest) -> RecipeResponse:
        # Format the ingredient list for the AI
        ing_list = ", ".join([f"{i.name} ({i.stock_status})" for i in data.available_ingredients])
        
        user_content = f"Request: {data.prompt}\nAvailable Ingredients: {ing_list}\nConstraints: {data.constraints}"

        response = await self.client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": RECIPE_SYSTEM_PROMPT},
                {"role": "user", "content": user_content}
            ],
            response_format={"type": "json_object"},
            temperature=0.7
        )
        
        # Parse JSON
        result = json.loads(response.choices[0].message.content)
        return RecipeResponse(**result)

    # --- METHOD 2: SPECIALS (This was missing) ---
    async def suggest_specials(self, data: SpecialsRequest) -> SpecialsResponse:
        user_content = f"Expiring Items: {', '.join(data.expiring_items)}\nSeason: {data.season}"

        response = await self.client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": SPECIALS_SYSTEM_PROMPT},
                {"role": "user", "content": user_content}
            ],
            response_format={"type": "json_object"},
            temperature=0.7
        )

        # Parse JSON
        result = json.loads(response.choices[0].message.content)
        return SpecialsResponse(**result)