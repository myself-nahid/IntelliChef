import json
from openai import AsyncOpenAI
from app.schemas import ChatRequest, ChatResponse
from app.prompts import CHAT_SYSTEM_PROMPT

# DEFINE THE TOOLS (The Capabilities)
# This tells the AI what data it can ask for.
TOOLS_SCHEMA = [
    {
        "type": "function",
        "function": {
            "name": "get_stock_status",
            "description": "Get a list of ingredients filtered by their stock level (Low, None, OK).",
            "parameters": {
                "type": "object",
                "properties": {
                    "status": {"type": "string", "enum": ["Low", "None", "All"]}
                },
                "required": ["status"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_supplier_price_history",
            "description": "Get price history and cheapest supplier for a specific ingredient.",
            "parameters": {
                "type": "object",
                "properties": {
                    "ingredient_name": {"type": "string"},
                    "period": {"type": "string", "enum": ["current", "last_30_days"]}
                },
                "required": ["ingredient_name"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_recipe_financials",
            "description": "Get cost, margin, and profit data for a specific recipe.",
            "parameters": {
                "type": "object",
                "properties": {
                    "recipe_name": {"type": "string"}
                },
                "required": ["recipe_name"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "check_critical_alerts",
            "description": "Check for system alerts like waste spikes, abnormal price hikes, or stockouts.",
            "parameters": {"type": "object", "properties": {}}
        }
    }
]

class OperationsAI:
    def __init__(self, api_key: str):
        self.client = AsyncOpenAI(api_key=api_key)

    async def analyze_data(self, data: ChatRequest) -> ChatResponse:
        messages = [
            {"role": "system", "content": CHAT_SYSTEM_PROMPT.format(language=data.language)},
            # The backend puts any PREVIOUSLY retrieved data here
            {"role": "user", "content": f"Context: {data.context_data}\n\nQuestion: {data.question}"}
        ]

        # 1. Ask AI: "Do you need a tool to answer this?"
        response = await self.client.chat.completions.create(
            model="gpt-4o",
            messages=messages,
            tools=TOOLS_SCHEMA,
            tool_choice="auto", 
            temperature=0.3
        )

        msg = response.choices[0].message

        # 2. Logic: Did the AI ask for a tool?
        if msg.tool_calls:
            # If AI says "Call function get_stock_status", we return that instruction
            tool_call = msg.tool_calls[0]
            function_name = tool_call.function.name
            arguments = json.loads(tool_call.function.arguments)
            
            # We return a SPECIAL response telling the Backend: "Run this SQL query!"
            return ChatResponse(
                answer=f"TOOL_CALL:{function_name}:{json.dumps(arguments)}"
            )
        
        # 3. If no tool needed, just answer normally
        content = msg.content
        return ChatResponse(answer=content)