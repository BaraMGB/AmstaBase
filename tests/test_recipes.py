from io import BytesIO
from pathlib import Path

from amstabase.db import get_db


def recipe_data(name="Kartoffelsuppe"):
    return {
        "name": name,
        "category": "Suppen",
        "in_menu": "on",
        "menu_description": "Cremige Suppe",
        "allergens": "Milch",
        "approximate_cost": "2.50",
        "selling_price": "8.90",
        "instructions": "<p><strong>Kochen</strong></p><script>bad()</script>",
        "notes": "Warm servieren",
        "quantity_1": "200",
        "unit_1": "g",
        "ingredient_name_1": "Kartoffeln",
    }


def test_admin_can_create_view_edit_and_delete_recipe(app, client, auth):
    auth.register()
    auth.login()

    response = client.post("/new_recipe", data=recipe_data())
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/recipe/1")

    with app.app_context():
        recipe = get_db().execute("SELECT * FROM recipes WHERE id = 1").fetchone()
        ingredient = get_db().execute(
            "SELECT * FROM ingredients WHERE recipe_id = 1"
        ).fetchone()
        assert recipe["created_by"] == "admin"
        assert "<script" not in recipe["instructions"]
        assert ingredient["ingredient_name"] == "Kartoffeln"
        assert ingredient["display_order"] == 1

    detail = client.get("/recipe/1")
    assert detail.status_code == 200
    assert "Kartoffelsuppe" in detail.get_data(as_text=True)

    updated = recipe_data("Kürbissuppe")
    updated["ingredient_name_1"] = "Kürbis"
    response = client.post("/edit_recipe/1", data=updated)
    assert response.status_code == 302

    with app.app_context():
        database = get_db()
        stored_name = database.execute(
            "SELECT name FROM recipes WHERE id = 1"
        ).fetchone()[0]
        assert stored_name == "Kürbissuppe"
        assert database.execute(
            "SELECT ingredient_name FROM ingredients WHERE recipe_id = 1"
        ).fetchone()[0] == "Kürbis"

    response = client.post("/delete_recipe/1")
    assert response.status_code == 302
    with app.app_context():
        assert get_db().execute("SELECT COUNT(*) FROM recipes").fetchone()[0] == 0


def test_photo_upload_uses_random_safe_filename(app, client, auth):
    auth.register()
    auth.login()
    data = recipe_data()
    data["photos"] = (BytesIO(b"fake image"), "../../meal.JPG")

    response = client.post("/new_recipe", data=data, content_type="multipart/form-data")
    assert response.status_code == 302

    with app.app_context():
        filename = get_db().execute("SELECT filename FROM photos").fetchone()[0]
    assert filename.endswith(".jpg")
    assert "meal" not in filename
    assert (Path(app.config["UPLOAD_FOLDER"]) / filename).exists()


def test_service_gets_reduced_detail_view(client, auth):
    auth.register("admin")
    auth.login("admin")
    client.post("/new_recipe", data=recipe_data())
    auth.logout()
    auth.register("service")
    auth.login("service")

    text = client.get("/recipe/1").get_data(as_text=True)
    assert "Kartoffelsuppe" in text
    assert "Einkaufspreis" not in text
    assert "Zubereitung" not in text


def test_missing_recipe_returns_404(client, auth):
    auth.register()
    auth.login()
    assert client.get("/recipe/999").status_code == 404
