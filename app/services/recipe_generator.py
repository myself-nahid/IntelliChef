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

MAX_HISTORY_TURNS = 10

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

DIFFICULTY_EMOJI = {"easy": "🟢", "medium": "🟡", "hard": "🔴"}
SOURCE_LABEL     = {"inventory": "✅", "substitute": "🔄", "pantry_staple": "🧂"}

# UTILITIES
def _build_history_messages(history) -> list[dict]:
    trimmed = history[-(MAX_HISTORY_TURNS * 2):]
    return [{"role": msg.role, "content": msg.content} for msg in trimmed]


def _safe_get(d, key, default=""):
    return d.get(key) or default


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
    items_used, pantry_used = [], []
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


def _recipe_to_markdown(payload: RecipeData) -> str:
    """
    Converts a validated RecipeData object into a clean Markdown string.
    Only includes sections that have meaningful content.
    Non-recipe responses (general / off_topic / error) return their answer directly.
    """
    lines: list[str] = []

    if payload.pivoted and payload.preparation_note:
        lines.append(f"> ⚠️ {payload.preparation_note}")
        lines.append("")

    lines.append(f"# {payload.title}")
    lines.append("")
    lines.append(payload.description)
    lines.append("")

    meta = []
    if payload.prep_time_minutes is not None:
        meta.append(f"⏱ Prep **{payload.prep_time_minutes} min**")
    if payload.cook_time_minutes is not None:
        meta.append(f"🍳 Cook **{payload.cook_time_minutes} min**")
    if payload.servings is not None:
        meta.append(f"🍽 Serves **{payload.servings}**")
    if payload.difficulty:
        emoji = DIFFICULTY_EMOJI.get(payload.difficulty.lower(), "")
        meta.append(f"{emoji} **{payload.difficulty.capitalize()}**")
    if meta:
        lines.append("  ".join(meta))
        lines.append("")

    inv = payload.inventory_summary
    if inv.missing_critical or inv.missing_optional or payload.substitutions:
        lines.append("## 🗂 Inventory Snapshot")
        lines.append("")
        if inv.missing_critical:
            lines.append(f"**Missing (critical):** {', '.join(inv.missing_critical)}")
        if inv.missing_optional:
            lines.append(f"**Missing (optional):** {', '.join(inv.missing_optional)}")
        if payload.substitutions:
            for s in payload.substitutions:
                lines.append(f"**Substituted:** {s.original} → {s.used_instead} *({s.reason})*")
        lines.append("")

    if payload.ingredients:
        lines.append("## 🧾 Ingredients")
        lines.append("")
        for ing in payload.ingredients:
            icon  = SOURCE_LABEL.get(ing.source or "", "")
            qty   = "" if ing.quantity is None else str(ing.quantity).rstrip("0").rstrip(".")
            unit  = ing.unit or ""
            amount = f"{qty} {unit}".strip() if qty else unit
            line   = f"- {icon} **{ing.name}**"
            if amount:
                line += f" — {amount}"
            lines.append(line)
        lines.append("")

    if payload.steps:
        lines.append("## 👨‍🍳 Instructions")
        lines.append("")
        for idx, step in enumerate(payload.steps, 1):
            clean = step.strip()
            import re
            clean = re.sub(r"^Step\s+\d+\s*[—–-]\s*", "", clean)
            lines.append(f"{idx}. {clean}")
        lines.append("")

    critical = [m for m in (payload.missing_ingredients or []) if m.is_critical]
    if critical:
        lines.append("## 🛒 Shopping List")
        lines.append("")
        for m in critical:
            sub = f" *(substitute: {m.suggested_substitute})*" if m.suggested_substitute else ""
            lines.append(f"- **{m.name}**{sub}")
        lines.append("")

    if payload.tips:
        lines.append("## 💡 Chef's Tip")
        lines.append("")
        lines.append(payload.tips)
        lines.append("")

    return "\n".join(lines).strip()


def _to_markdown_response(data: RecipeRequest, ai_raw) -> tuple[str, str, bool]:
    """
    Converts any AI response kind into (markdown_string, message, success).
    recipe    → full recipe Markdown
    general   → plain answer string (already Markdown from prompt)
    off_topic → plain answer string
    error     → error message string
    """
    kind = ai_raw.type

    if kind == "recipe":
        inv_summary = _build_inventory_summary(data, ai_raw)
        payload = RecipeData(
            can_be_prepared=ai_raw.can_be_prepared,
            pivoted=ai_raw.pivoted,
            preparation_note=ai_raw.preparation_note,
            original_request=data.prompt,
            constraints=data.constraints,
            inventory_summary=inv_summary,
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
        return _recipe_to_markdown(payload), msg, True

    if kind == "general":
        return ai_raw.answer, "Chef assistant responded.", True

    if kind == "off_topic":
        md = ai_raw.answer
        if getattr(ai_raw, "note", None):
            md += f"\n\n*{ai_raw.note}*"
        return md, "Question answered.", True

    return f"> {getattr(ai_raw, 'message', 'Unknown error.')}", "Could not process request.", False


# Specials Helpers 
def _specials_to_markdown(data: dict) -> str:
    lines = []

    lines.append(f"# 🍽️ Daily Specials ({data.get('season', '')})")
    lines.append("")
    lines.append(f"**Total Expiring Items Used:** {data.get('total_expiring_items_used', 0)}")
    lines.append("")

    for i, dish in enumerate(data.get("suggestions", []), 1):
        lines.append(f"## {i}. {_safe_get(dish, 'dish_name')}")
        lines.append("")

        lines.append(f"- **Course:** {_safe_get(dish, 'course')}")
        lines.append(f"- **Cooking Method:** {_safe_get(dish, 'cooking_method')}")
        lines.append(f"- **Prep Time:** {_safe_get(dish, 'estimated_prep_time_minutes')} min")
        lines.append(f"- **Difficulty:** {_safe_get(dish, 'difficulty')}")
        lines.append("")

        lines.append("### 📖 Description")
        lines.append(_safe_get(dish, "description"))
        lines.append("")

        lines.append("### 🧾 Ingredients")
        for ing in dish.get("key_ingredients_used", []):
            lines.append(f"- {ing}")
        lines.append("")

        lines.append("### ♻️ Waste Recovery")
        lines.append(_safe_get(dish, "waste_recovery_note"))
        lines.append("")

        if dish.get("chef_tip"):
            lines.append("### 👨‍🍳 Chef Tip")
            lines.append(dish["chef_tip"])
            lines.append("")

        lines.append("---")
        lines.append("")

    return "\n".join(lines).strip()

# MAIN CLASS
class KitchenAI:
    def __init__(self, api_key: str):
        self.client = AsyncOpenAI(api_key=api_key)

    # RECIPE
    async def generate_recipe(self, data: RecipeRequest) -> APIResponse:

        messages = [
            {
                "role": "system",
                "content": RECIPE_SYSTEM_PROMPT.format(language=data.language),
            }
        ]
        messages.extend(_build_history_messages(data.history))
        messages.append({
            "role": "user",
            "content": (
                f"Request: {data.prompt}\n\n"
                f"Available Ingredients (verified inventory):\n{_build_ingredient_block(data)}\n\n"
                f"Constraints: {data.constraints or 'None'}\n\n"
                "IMPORTANT: Only use ingredients listed above plus universal pantry staples "
                "(water, salt, black pepper, generic cooking oil). "
                "Any other ingredient MUST appear in missing_ingredients or substitutions."
            ),
        })

        response = await self.client.chat.completions.create(
            model="gpt-4o",
            messages=messages,
            response_format={"type": "json_object"},
            temperature=0.7,
        )

        content = response.choices[0].message.content

        try:
            raw = json.loads(content)
        except json.JSONDecodeError:
            return APIResponse(
                success=False,
                message="AI returned malformed JSON.",
                data={"markdown": ">  AI returned malformed JSON. Please try again."},
                error="JSONDecodeError",
            )

        response_type = raw.get("type", "error")

        # Guard 2 — unknown type
        if response_type not in RECIPE_TYPE_MAP:
            return APIResponse(
                success=False,
                message="Unexpected AI response type.",
                data={"markdown": f"> Unexpected response type: `{response_type}`"},
                error=f"Unknown type: {response_type}",
            )

        # Guard 3 — schema mismatch
        try:
            ai_model = RECIPE_TYPE_MAP[response_type](**raw)
        except ValidationError as e:
            print(f"\n RECIPE SCHEMA MISMATCH\nType: {response_type}\n"
                  f"AI output:\n{json.dumps(raw, indent=2)}\nError:\n{e}")
            return APIResponse(
                success=False,
                message="AI response schema mismatch.",
                data={"markdown": ">  Schema validation failed. Please try again."},
                error=str(e),
            )

        markdown, message, success = _to_markdown_response(data, ai_model)
        return APIResponse(
            success=success,
            message=message,
            data={"markdown": markdown},
        )

    # SPECIALS
    async def suggest_specials(self, data: SpecialsRequest) -> APIResponse:

        messages = [
            {
                "role": "system",
                "content": SPECIALS_SYSTEM_PROMPT.format(
                    language=data.language,
                    season=data.season,
                ),
            }
        ]
        messages.extend(_build_history_messages(data.history))

        messages.append({
            "role": "user",
            "content": (
                f"User Message: {data.prompt or '(no message — generate specials from expiring items)'}\n\n"
                f"Expiring Items: {', '.join(data.expiring_items) if data.expiring_items else 'None'}\n"
                f"Cuisine Style: {data.cuisine_style or 'Any'}\n"
                f"Target Audience: {data.target_audience or 'General'}\n"
                f"Constraints: {data.constraints or 'None'}\n"
            ),
        })

        response = await self.client.chat.completions.create(
            model="gpt-4o",
            messages=messages,
            response_format={"type": "json_object"},
        )

        raw = json.loads(response.choices[0].message.content)
        response_type = raw.get("type", "error")

        try:
            ai_model = SPECIALS_TYPE_MAP[response_type](**raw)
        except ValidationError:
            return APIResponse(success=False, message="Schema error")

        structured = ai_model.model_dump(exclude={"type"}, exclude_none=True)

        if response_type == "specials":
            markdown = _specials_to_markdown(structured)
        elif response_type in ["menu_advice", "general", "off_topic"]:
            markdown = getattr(ai_model, "answer", "> Error")
        else:
            markdown = f"> {getattr(ai_model, 'message', 'Unknown error')}"

        return APIResponse(
            success=response_type != "error",
            message=SPECIALS_MESSAGES.get(response_type),
            data={"markdown": markdown}
        )