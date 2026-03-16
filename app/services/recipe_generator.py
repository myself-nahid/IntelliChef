import json
from pydantic import ValidationError
from openai import AsyncOpenAI

from app.schemas import (
    RecipeRequest, APIResponse,
    RecipeData, GeneralData, OffTopicData, ErrorData,
    InventorySummary,
    SpecialsRequest,
    _RecipeAI, _GeneralAI, _OffTopicAI, _ErrorAI,
    _SpecialsAI, _SpecialsAdviceAI, _SpecialsGeneralAI,
    _SpecialsOffTopicAI, _SpecialsErrorAI,
)
from app.prompts import RECIPE_SYSTEM_PROMPT, SPECIALS_SYSTEM_PROMPT


RECIPE_TYPE_MAP = {
    "recipe":    _RecipeAI,
    "general":   _GeneralAI,
    "off_topic": _OffTopicAI,
    "error":     _ErrorAI,
}

SPECIALS_TYPE_MAP = {
    "specials":    _SpecialsAI,
    "menu_advice": _SpecialsAdviceAI,
    "general":     _SpecialsGeneralAI,
    "off_topic":   _SpecialsOffTopicAI,
    "error":       _SpecialsErrorAI,
}

SPECIALS_MESSAGES = {
    "specials":    "Daily specials generated successfully.",
    "menu_advice": "Menu advice generated.",
    "general":     "Chef assistant responded.",
    "off_topic":   "Question answered.",
    "error":       "Could not process request.",
}


# ── Helpers ────────────────────────────────────────────────────────────────────

def _build_ingredient_block(data: RecipeRequest) -> str:
    """Structured per-ingredient context block for the AI prompt."""
    if not data.available_ingredients:
        return "  (none provided)"
    lines = []
    for i in data.available_ingredients:
        parts = [f"  - {i.name} | stock_status: {i.stock_status}"]
        if i.current_stock is not None:
            parts.append(f"current: {i.current_stock} {i.unit or ''}")
        if i.minimum_stock is not None:
            parts.append(f"minimum: {i.minimum_stock} {i.unit or ''}")
        if i.category:
            parts.append(f"category: {i.category}")
        if i.outlet_type:
            parts.append(f"outlet: {i.outlet_type}")
        if i.is_special:
            parts.append("[SPECIAL ITEM]")
        lines.append(" | ".join(parts))
    return "\n".join(lines)


def _build_inventory_summary(data: RecipeRequest, ai: _RecipeAI) -> InventorySummary:
    """Derives inventory usage breakdown — built in Python, never sent to the AI."""
    items_used: list[str] = []
    pantry_used: list[str] = []

    for ing in (ai.ingredients or []):
        if ing.source == "pantry_staple":
            pantry_used.append(ing.name)
        elif ing.source in ("inventory", "substitute"):
            items_used.append(ing.name)

    items_used_lower = {n.lower() for n in items_used}
    items_not_used = [
        i.name for i in data.available_ingredients
        if i.name.lower() not in items_used_lower
    ]

    return InventorySummary(
        total_inventory_items=len(data.available_ingredients),
        items_used_in_recipe=items_used,
        items_not_used=items_not_used,
        pantry_staples_used=pantry_used,
        missing_critical=[m.name for m in (ai.missing_ingredients or []) if m.is_critical],
        missing_optional=[m.name for m in (ai.missing_ingredients or []) if not m.is_critical],
    )


def _to_data(data: RecipeRequest, ai_raw) -> tuple[object, str, bool]:
    """
    Converts an internal AI model into the strongly-typed data payload.
    Returns (data_object, message_string, success_bool).

    Each response_kind maps to its own dedicated model:
      recipe    → RecipeData    (no answer/note/error_message fields)
      general   → GeneralData   (no recipe fields)
      off_topic → OffTopicData  (no recipe fields)
      error     → ErrorData     (no recipe fields)
    """
    kind = ai_raw.type

    if kind == "recipe":
        payload = RecipeData(
            can_be_prepared=ai_raw.can_be_prepared,
            pivoted=ai_raw.pivoted,
            preparation_note=ai_raw.preparation_note,
            original_request=data.prompt,
            constraints=data.constraints,
            inventory_summary=_build_inventory_summary(data, ai_raw),
            title=ai_raw.title,
            description=ai_raw.description,
            prep_time_minutes=ai_raw.prep_time_minutes,
            cook_time_minutes=ai_raw.cook_time_minutes,
            servings=ai_raw.servings,
            difficulty=ai_raw.difficulty,
            ingredients=ai_raw.ingredients,
            substitutions=ai_raw.substitutions or [],
            missing_ingredients=ai_raw.missing_ingredients or [],
            steps=ai_raw.steps,
            tips=ai_raw.tips,
        )
        msg = (
            "Recipe generated successfully."
            if ai_raw.can_be_prepared
            else "Requested dish unavailable with current inventory. Best alternative prepared."
        )
        return payload, msg, True

    if kind == "general":
        return GeneralData(original_request=data.prompt, answer=ai_raw.answer), "Chef assistant responded.", True

    if kind == "off_topic":
        return OffTopicData(original_request=data.prompt, answer=ai_raw.answer, note=ai_raw.note), "Question answered.", True

    # error fallback
    return ErrorData(original_request=data.prompt, error_message=getattr(ai_raw, "message", "Unknown error.")), "Could not process request.", False


class KitchenAI:
    def __init__(self, api_key: str):
        self.client = AsyncOpenAI(api_key=api_key)

    # ── /generate-recipe ───────────────────────────────────────────────────────
    async def generate_recipe(self, data: RecipeRequest) -> APIResponse:
        user_content = (
            f"Request: {data.prompt}\n\n"
            f"Available Ingredients (verified inventory):\n{_build_ingredient_block(data)}\n\n"
            f"Constraints: {data.constraints or 'None'}\n\n"
            "IMPORTANT: Only use ingredients listed above plus universal pantry staples "
            "(water, salt, black pepper, generic cooking oil). "
            "Any other ingredient MUST appear in missing_ingredients or substitutions."
        )

        response = await self.client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": RECIPE_SYSTEM_PROMPT.format(language=data.language)},
                {"role": "user",   "content": user_content},
            ],
            response_format={"type": "json_object"},
            temperature=0.7,
        )

        content = response.choices[0].message.content

        # Guard 1 — malformed JSON
        try:
            raw = json.loads(content)
        except json.JSONDecodeError:
            return APIResponse(
                success=False, message="AI returned malformed JSON.",
                data=ErrorData(original_request=data.prompt, error_message="Malformed JSON from AI.").model_dump(),
                error="JSONDecodeError",
            )

        response_type = raw.get("type", "error")

        # Guard 2 — unknown type value
        if response_type not in RECIPE_TYPE_MAP:
            return APIResponse(
                success=False, message="Unexpected AI response type.",
                data=ErrorData(original_request=data.prompt, error_message=f"Unknown type: '{response_type}'").model_dump(),
                error=f"Unknown type: {response_type}",
            )

        # Guard 3 — schema / field-type mismatch
        try:
            ai_model = RECIPE_TYPE_MAP[response_type](**raw)
        except ValidationError as e:
            print(f"\n⚠️ RECIPE SCHEMA MISMATCH\nType: {response_type}\n"
                  f"AI output:\n{json.dumps(raw, indent=2)}\nError:\n{e}")
            return APIResponse(
                success=False, message="AI response schema mismatch.",
                data=ErrorData(original_request=data.prompt, error_message="Schema validation failed.").model_dump(),
                error=str(e),
            )

        payload, message, success = _to_data(data, ai_model)
        return APIResponse(
            success=success,
            message=message,
            data=payload.model_dump(exclude_none=True),
        )

    # ── /suggest-specials ──────────────────────────────────────────────────────
    async def suggest_specials(self, data: SpecialsRequest) -> APIResponse:
        user_content = (
            f"Request: {data.prompt or 'Suggest daily specials for the expiring items.'}\n\n"
            f"Expiring Items: {', '.join(data.expiring_items) or 'None provided'}\n"
            f"Season: {data.season}\n"
            f"Cuisine Style: {data.cuisine_style or 'Any'}\n"
            f"Target Audience: {data.target_audience or 'General'}\n"
            f"Constraints: {data.constraints or 'None'}"
        )

        response = await self.client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": SPECIALS_SYSTEM_PROMPT.format(language=data.language, season=data.season)},
                {"role": "user",   "content": user_content},
            ],
            response_format={"type": "json_object"},
            temperature=0.7,
        )

        content = response.choices[0].message.content

        try:
            raw = json.loads(content)
        except json.JSONDecodeError:
            return APIResponse(success=False, message="AI returned malformed JSON.", error="JSONDecodeError")

        response_type = raw.get("type", "error")

        if response_type not in SPECIALS_TYPE_MAP:
            return APIResponse(success=False, message="Unexpected AI response type.", error=f"Unknown type: {response_type}")

        try:
            ai_model = SPECIALS_TYPE_MAP[response_type](**raw)
        except ValidationError as e:
            print(f"\n⚠️ SPECIALS SCHEMA MISMATCH\nType: {response_type}\n"
                  f"AI output:\n{json.dumps(raw, indent=2)}\nError:\n{e}")
            return APIResponse(success=False, message="AI response schema mismatch.", error=str(e))

        return APIResponse(
            success=response_type != "error",
            message=SPECIALS_MESSAGES.get(response_type, "Response generated."),
            # Strip the internal "type" field — clients don't need it
            data=ai_model.model_dump(exclude={"type"}, exclude_none=True),
        )