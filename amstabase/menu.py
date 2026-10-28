"""Public menu routes."""

from __future__ import annotations

from flask import Blueprint, render_template

from .db import get_categories, get_db

bp = Blueprint("menu", __name__)


def get_categorized_menu() -> dict[str, list]:
    categories = get_categories()
    rows = get_db().execute(
        """
        SELECT r.name, r.category, r.menu_description,
               COALESCE(CAST(r.selling_price AS REAL), 0) AS selling_price,
               r.id,
               (SELECT filename FROM photos
                WHERE photos.recipe_id = r.id ORDER BY id LIMIT 1) AS photo
        FROM recipes r
        WHERE r.in_menu = 1
        ORDER BY r.selling_price, r.name
        """
    ).fetchall()
    categorized = {category: [] for category in categories}
    for row in rows:
        if row["category"] in categorized:
            categorized[row["category"]].append(row)
    return {category: recipes for category, recipes in categorized.items() if recipes}


@bp.get("/menu")
def public_menu():
    return render_template("menu/public.html", categorized_recipes=get_categorized_menu())
