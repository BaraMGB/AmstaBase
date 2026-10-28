from pathlib import Path


def recipe_data(name: str, in_menu: bool = True):
    data = {
        "name": name,
        "category": "Dessert",
        "menu_description": f"Beschreibung {name}",
        "selling_price": "9.50",
        "instructions": "<p>Zubereitung</p>",
    }
    if in_menu:
        data["in_menu"] = "on"
    return data


def test_public_menu_only_shows_published_recipes(client, auth):
    auth.register()
    auth.login()
    client.post("/new_recipe", data=recipe_data("Tiramisu"))
    client.post("/new_recipe", data=recipe_data("Intern", in_menu=False))
    auth.logout()

    response = client.get("/menu")
    text = response.get_data(as_text=True)
    assert response.status_code == 200
    assert "Tiramisu" in text
    assert "Intern" not in text


def test_pdf_export_requires_edit_permission(client, auth, user_factory):
    response = client.get("/generate_pdf")
    assert response.status_code == 302

    user_factory("viewer", "Viewer")
    auth.login("viewer")
    assert client.get("/generate_pdf").status_code == 403


def test_editor_can_generate_pdf(app, client, auth, user_factory, monkeypatch):
    class FakeHTML:
        def __init__(self, string, base_url):
            assert "Speisekarte" in string
            self.base_url = base_url

        def write_pdf(self, target):
            Path(target).write_bytes(b"%PDF-test")

    monkeypatch.setattr("amstabase.menu.HTML", FakeHTML)
    user_factory("editor", "Editor")
    auth.login("editor")

    response = client.get("/generate_pdf")
    assert response.status_code == 200
    assert response.mimetype == "application/pdf"
    assert response.data == b"%PDF-test"
    assert Path(app.config["MENU_PDF_PATH"]).exists()
