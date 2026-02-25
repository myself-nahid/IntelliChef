import json
from openai import AsyncOpenAI
from app.schemas import RecipeRequest, RecipeResponse, SpecialsRequest, SpecialsResponse
from app.prompts import RECIPE_SYSTEM_PROMPT, SPECIALS_SYSTEM_PROMPT

class KitchenAI:
    def __init__(self, api_key: str):
        self.client = AsyncOpenAI(api_key=api_key)

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
            response_format={"type": "json_object"}, # This forces JSON mode
            temperature=0.7
        )
        
        content = response.choices[0].message.content
        
        # Debugging: Print what AI actually sent if it fails again
        print(f"DEBUG AI RESPONSE: {content}") 

        result = json.loads(content)
        return RecipeResponse(**result)