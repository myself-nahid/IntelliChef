import json
from openai import AsyncOpenAI
from app.schemas import ChatRequest, ChatResponse
from app.prompts import CHAT_SYSTEM_PROMPT

class OperationsAI:
    def __init__(self, api_key: str):
        self.client = AsyncOpenAI(api_key=api_key)

    async def analyze_data(self, data: ChatRequest) -> ChatResponse:
        formatted_system_prompt = CHAT_SYSTEM_PROMPT.format(language=data.language)

        messages = [
            {"role": "system", "content": formatted_system_prompt},
            {"role": "user", "content": f"Context Data: {data.context_data}\n\nQuestion: {data.question}"}
        ]

        response = await self.client.chat.completions.create(
            model="gpt-4o",
            messages=messages,
            response_format={"type": "json_object"},
            temperature=0.3
        )

        content = response.choices[0].message.content

        try:
            result = json.loads(content)
            final_answer = result.get("answer", content)
            return ChatResponse(answer=final_answer)
        except json.JSONDecodeError:
            return ChatResponse(answer=content)