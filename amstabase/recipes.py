"""Recipe listing, detail and CRUD routes."""

from __future__ import annotations

import secrets
from pathlib import Path

from flask import (
    Blueprint,
    abort,
    current_app,
    flash,
    redirect,
    render_template,
    request,
    send_from_directory,
    url_for,
)
from flask_login import current_user, login_required

from .db import get_categories, get_db
from .llm import RecipeImportError, fetch_recipe_source, structure_recipe
from .permissions import permission_required
from .services import (
    allowed_image,
    extract_ingredients,
    optional_float,
    sanitize_instructions,
)

bp = Blueprint("recipes", __name__)


def _save_uploaded_photos(recipe_id: int) -> None:
    database = get_db()
    for upload in request.files.getlist("photos"):
        if not upload or not upload.filename:
            continue
        if not allowed_image(upload.filename):
            flash(f"Datei '{upload.filename}' wurde wegen ihres Dateityps übersprungen.", "warning")
            continue
        extension = Path(upload.filename).suffix.lower()
        filename = f"{secrets.token_hex(16)}{extension}"
        upload.save(Path(current_app.config["UPLOAD_FOLDER"]) / filename)
        database.execute(
            "INSERT INTO photos (recipe_id, filename) VALUES (?, ?)",
            (recipe_id, filename),
        )


def _delete_photo_file(filename: str) -> None:
    try:
        (Path(current_app.config["UPLOAD_FOLDER"]) / filename).unlink(missing_ok=True)
    except OSError:
        current_app.logger.exception("Could not delete upload %s", filename)


def _recipe_values() -> tuple[dict, list[dict]]:
    name = request.form.get("name", "").strip()
    if not name:
        raise ValueError("Der Rezeptname ist erforderlich.")

    values = {
        "name": name,
        "menu_description": request.form.get("menu_description", "").strip(),
        "category": request.form.get("category", "").strip(),
        "in_menu": request.form.get("in_menu") == "on",
        "allergens": request.form.get("allergens", "").strip(),
        "approximate_cost": optional_float(request.form.get("approximate_cost")),
        "selling_price": optional_float(request.form.get("selling_price")),
        "instructions": sanitize_instructions(request.form.get("instructions")),
        "notes": request.form.get("notes", "").strip(),
    }
    return values, extract_ingredients(request.form)


def _insert_ingredients(recipe_id: int, ingredients: list[dict]) -> None:
    database = get_db()
    database.executemany(
        """
        INSERT INTO ingredients
            (recipe_id, quantity, unit, ingredient_name, display_order)
        VALUES (?, ?, ?, ?, ?)
        """,
        [
            (
                recipe_id,
                ingredient["quantity"],
                ingredient["unit"],
                ingredient["name"],
                ingredient["display_order"],
            )
            for ingredient in ingredients
        ],
    )


@bp.get("/")
@login_required
def index():
    search_query = request.args.get("search", "").strip()
    categories = get_categories()
    recipes = get_db().execute(
        """
        SELECT r.id, r.name, r.category, r.menu_description,
               COALESCE(CAST(r.selling_price AS REAL), 0) AS selling_price,
               (SELECT filename FROM photos
                WHERE photos.recipe_id = r.id ORDER BY id LIMIT 1) AS photo
        FROM recipes r
        WHERE r.name LIKE ? OR r.category LIKE ?
        """,
        (f"%{search_query}%", f"%{search_query}%"),
    ).fetchall()
    category_order = {category: index for index, category in enumerate(categories)}
    sorted_recipes = sorted(
        recipes,
        key=lambda recipe: (
            category_order.get(recipe["category"], len(categories)),
            recipe["selling_price"],
            recipe["name"].casefold(),
        ),
    )
    return render_template("recipes/index.html", recipes=sorted_recipes, search=search_query)


@bp.get("/uploads/<path:filename>")
def uploaded_file(filename: str):
    return send_from_directory(current_app.config["UPLOAD_FOLDER"], filename)


@bp.get("/recipe/<int:recipe_id>")
@login_required
def show_recipe(recipe_id: int):
    database = get_db()
    row = database.execute("SELECT * FROM recipes WHERE id = ?", (recipe_id,)).fetchone()
    if row is None:
        abort(404, description="Rezept nicht gefunden")

    ingredients = database.execute(
        """
        SELECT * FROM ingredients
        WHERE recipe_id = ?
        ORDER BY display_order, id
        """,
        (recipe_id,),
    ).fetchall()
    photos = database.execute(
        "SELECT * FROM photos WHERE recipe_id = ? ORDER BY id", (recipe_id,)
    ).fetchall()
    recipe = dict(row)
    recipe["selling_price"] = float(recipe["selling_price"] or 0)
    recipe["approximate_cost"] = float(recipe["approximate_cost"] or 0)

    if current_user.role == "Service":
        return render_template(
            "recipes/detail_service.html",
            recipe=recipe,
            ingredients=ingredients,
            photos=photos,
        )

    linked_ingredients = []
    for ingredient in ingredients:
        linked_recipe = database.execute(
            "SELECT id FROM recipes WHERE name = ?", (ingredient["ingredient_name"],)
        ).fetchone()
        linked_ingredients.append(
            {
                "name": ingredient["ingredient_name"],
                "quantity": ingredient["quantity"],
                "unit": ingredient["unit"],
                "linked_recipe_id": linked_recipe["id"] if linked_recipe else None,
            }
        )
    return render_template(
        "recipes/detail.html",
        recipe=recipe,
        ingredients=linked_ingredients,
        photos=photos,
    )


@bp.route("/new_recipe", methods=("GET", "POST"))
@permission_required("add")
def new_recipe():
    if request.method == "POST":
        try:
            values, ingredients = _recipe_values()
        except ValueError as error:
            flash(str(error), "danger")
        else:
            database = get_db()
            cursor = database.execute(
                """
                INSERT INTO recipes
                    (name, menu_description, category, in_menu, approximate_cost,
                     selling_price, allergens, instructions, notes, created_by)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    values["name"],
                    values["menu_description"],
                    values["category"],
                    values["in_menu"],
                    values["approximate_cost"],
                    values["selling_price"],
                    values["allergens"],
                    values["instructions"],
                    values["notes"],
                    current_user.username,
                ),
            )
            recipe_id = cursor.lastrowid
            _insert_ingredients(recipe_id, ingredients)
            _save_uploaded_photos(recipe_id)
            database.commit()
            flash("Rezept wurde angelegt.", "success")
            return redirect(url_for("recipes.show_recipe", recipe_id=recipe_id))

    return render_template(
        "recipes/new.html",
        categories=get_categories(),
        recipe=None,
        ingredients=[],
        photos=[],
        form_mode="new",
    )


@bp.route("/import_recipe", methods=("GET", "POST"))
@permission_required("add")
def import_recipe():
    source_url = request.form.get("source_url", "").strip()
    source_text = request.form.get("source_text", "").strip()

    if request.method == "POST":
        if bool(source_url) == bool(source_text):
            flash("Bitte entweder eine URL oder einen Textblock angeben.", "danger")
        else:
            try:
                source = fetch_recipe_source(source_url) if source_url else source_text
                recipe, ingredients = structure_recipe(source)
            except RecipeImportError as error:
                current_app.logger.warning("Recipe import failed: %s", error)
                flash(str(error), "danger")
            else:
                flash(
                    "Rezept wurde strukturiert. Bitte alle Angaben vor dem Speichern prüfen.",
                    "success",
                )
                return render_template(
                    "recipes/new.html",
                    categories=get_categories(),
                    recipe=recipe,
                    ingredients=ingredients,
                    photos=[],
                    form_mode="import",
                )

    return render_template(
        "recipes/import.html", source_url=source_url, source_text=source_text
    )


@bp.route("/edit_recipe/<int:recipe_id>", methods=("GET", "POST"))
@permission_required("edit")
def edit_recipe(recipe_id: int):
    database = get_db()
    recipe = database.execute("SELECT * FROM recipes WHERE id = ?", (recipe_id,)).fetchone()
    if recipe is None:
        abort(404, description="Rezept nicht gefunden")

    if request.method == "POST":
        try:
            values, ingredients = _recipe_values()
        except ValueError as error:
            flash(str(error), "danger")
        else:
            database.execute(
                """
                UPDATE recipes
                SET name = ?, menu_description = ?, category = ?, in_menu = ?,
                    approximate_cost = ?, selling_price = ?, allergens = ?,
                    instructions = ?, notes = ?, edited_by = ?,
                    edited_time = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (
                    values["name"],
                    values["menu_description"],
                    values["category"],
                    values["in_menu"],
                    values["approximate_cost"],
                    values["selling_price"],
                    values["allergens"],
                    values["instructions"],
                    values["notes"],
                    current_user.username,
                    recipe_id,
                ),
            )
            database.execute("DELETE FROM ingredients WHERE recipe_id = ?", (recipe_id,))
            _insert_ingredients(recipe_id, ingredients)
            _save_uploaded_photos(recipe_id)

            photo_ids = [
                int(key.rsplit("_", 1)[1])
                for key, value in request.form.items()
                if key.startswith("delete_photo_") and value == "1"
            ]
            for photo_id in photo_ids:
                photo = database.execute(
                    "SELECT filename FROM photos WHERE id = ? AND recipe_id = ?",
                    (photo_id, recipe_id),
                ).fetchone()
                if photo:
                    _delete_photo_file(photo["filename"])
                    database.execute("DELETE FROM photos WHERE id = ?", (photo_id,))

            database.commit()
            flash("Rezept wurde aktualisiert.", "success")
            return redirect(url_for("recipes.show_recipe", recipe_id=recipe_id))

    ingredients = database.execute(
        "SELECT * FROM ingredients WHERE recipe_id = ? ORDER BY display_order, id",
        (recipe_id,),
    ).fetchall()
    photos = database.execute(
        "SELECT id, filename FROM photos WHERE recipe_id = ? ORDER BY id", (recipe_id,)
    ).fetchall()
    return render_template(
        "recipes/edit.html",
        categories=get_categories(),
        recipe=recipe,
        ingredients=ingredients,
        photos=photos,
        form_mode="edit",
    )


@bp.post("/delete_recipe/<int:recipe_id>")
@permission_required("delete")
def delete_recipe(recipe_id: int):
    database = get_db()
    photos = database.execute(
        "SELECT filename FROM photos WHERE recipe_id = ?", (recipe_id,)
    ).fetchall()
    for photo in photos:
        _delete_photo_file(photo["filename"])
    database.execute("DELETE FROM ingredients WHERE recipe_id = ?", (recipe_id,))
    database.execute("DELETE FROM photos WHERE recipe_id = ?", (recipe_id,))
    database.execute("DELETE FROM recipes WHERE id = ?", (recipe_id,))
    database.commit()
    flash("Rezept wurde gelöscht.", "success")
    return redirect(url_for("recipes.index"))


@bp.post("/delete_photo/<int:photo_id>")
@permission_required("edit")
def delete_photo(photo_id: int):
    database = get_db()
    photo = database.execute(
        "SELECT filename, recipe_id FROM photos WHERE id = ?", (photo_id,)
    ).fetchone()
    if photo is None:
        abort(404)
    _delete_photo_file(photo["filename"])
    database.execute("DELETE FROM photos WHERE id = ?", (photo_id,))
    database.commit()
    return redirect(url_for("recipes.edit_recipe", recipe_id=photo["recipe_id"]))
