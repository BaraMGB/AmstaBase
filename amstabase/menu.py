"""Public menu and PDF export routes."""

from __future__ import annotations

from pathlib import Path

from flask import Blueprint, current_app, render_template, send_file
from weasyprint import HTML

from .db import get_categories, get_db
from .permissions import permission_required
from .services import split_large_categories

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


@bp.get("/generate_pdf")
@permission_required("edit")
def generate_pdf():
    categorized = split_large_categories(get_categorized_menu())
    rendered_html = render_template("menu/pdf.html", categorized_recipes=categorized)
    pdf_path = Path(current_app.config["MENU_PDF_PATH"])
    pdf_path.parent.mkdir(parents=True, exist_ok=True)
    HTML(string=rendered_html, base_url=current_app.root_path).write_pdf(pdf_path)
    return send_file(
        pdf_path,
        mimetype="application/pdf",
        as_attachment=True,
        download_name="speisekarte.pdf",
    )
