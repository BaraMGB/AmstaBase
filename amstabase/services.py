"""Framework-light helpers shared by recipe and menu views."""

from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Any

import bleach

ALLOWED_IMAGE_EXTENSIONS = {"png", "jpg", "jpeg", "gif"}
ALLOWED_HTML_TAGS = {
    "a",
    "b",
    "blockquote",
    "br",
    "em",
    "li",
    "ol",
    "p",
    "strong",
    "u",
    "ul",
}
ALLOWED_HTML_ATTRIBUTES = {"a": ["href", "title", "target"]}


def allowed_image(filename: str) -> bool:
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_IMAGE_EXTENSIONS


def sanitize_instructions(value: str | None) -> str:
    """Sanitize rich-text instructions before persistent storage."""

    return bleach.clean(
        value or "",
        tags=ALLOWED_HTML_TAGS,
        attributes=ALLOWED_HTML_ATTRIBUTES,
        protocols={"http", "https", "mailto"},
        strip=True,
    )


def optional_float(value: str | None) -> float | None:
    if value is None or not value.strip():
        return None
    return float(value.replace(",", "."))


def extract_ingredients(form: Mapping[str, Any]) -> list[dict[str, Any]]:
    """Parse dynamically numbered ingredient form fields in display order."""

    indexes = []
    for key in form:
        match = re.fullmatch(r"ingredient_name_(\d+)", key)
        if match:
            indexes.append(int(match.group(1)))

    ingredients = []
    for display_order, index in enumerate(indexes, start=1):
        name = str(form.get(f"ingredient_name_{index}", "")).strip()
        quantity = str(form.get(f"quantity_{index}", "")).strip()
        if not name or not quantity:
            continue
        ingredients.append(
            {
                "name": name,
                "quantity": optional_float(quantity),
                "unit": str(form.get(f"unit_{index}", "")).strip(),
                "display_order": display_order,
            }
        )
    return ingredients
