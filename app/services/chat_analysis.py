from openai import AsyncOpenAI
from app.schemas import ChatRequest, ChatResponse
from app.prompts import CHAT_SYSTEM_PROMPT

class OperationsAI:
    def __init__(self, api_key: str):
        self.client = AsyncOpenAI(api_key=api_key)

    async def analyze_data(self, data: ChatRequest) -> ChatResponse:
        # The backend sends the "Context" (prices, stock) inside data.context_data
        messages = [
            {"role": "system", "content": CHAT_SYSTEM_PROMPT},
            {"role": "user", "content": f"Context Data: {data.context_data}\n\nQuestion: {data.question}"}
        ]

        response = await self.client.chat.completions.create(
            model="gpt-4o",
            messages=messages,
            temperature=0.3 
        )

        return ChatResponse(answer=response.choices[0].message.content)