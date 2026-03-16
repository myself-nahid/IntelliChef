from openai import AsyncOpenAI
from app.schemas import ChatRequest, APIResponse
from app.prompts import CHAT_SYSTEM_PROMPT


class OperationsAI:
    def __init__(self, api_key: str):
        self.client = AsyncOpenAI(api_key=api_key)

    async def analyze_data(self, data: ChatRequest) -> APIResponse:
        response = await self.client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {
                    "role": "system",
                    "content": CHAT_SYSTEM_PROMPT.format(language=data.language),
                },
                {
                    "role": "user",
                    "content": f"Context: {data.context_data}\n\nQuestion: {data.question}",
                },
            ],
            temperature=0.3,
        )

        answer = response.choices[0].message.content

        return APIResponse(
            success=True,
            message="Query processed successfully.",
            data={"answer": answer},
        )