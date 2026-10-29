def imported_recipe():
    return (
        {
            "name": "Tomatensuppe",
            "category": "Suppen",
            "in_menu": False,
            "menu_description": "Fruchtig",
            "allergens": "",
            "approximate_cost": "",
            "selling_price": "",
            "instructions": "<p>Kochen</p>",
            "notes": "Prüfen",
        },
        [{"quantity": 500, "unit": "g", "ingredient_name": "Tomaten"}],
    )


def test_text_import_prefills_review_form(client, auth, monkeypatch):
    auth.register()
    auth.login()
    monkeypatch.setattr("amstabase.recipes.structure_recipe", lambda text: imported_recipe())

    response = client.post("/import_recipe", data={"source_text": "Mein Rezept"})
    text = response.get_data(as_text=True)
    assert response.status_code == 200
    assert "Importiertes Rezept prüfen" in text
    assert 'value="Tomatensuppe"' in text
    assert 'value="Tomaten"' in text
    assert 'action="/new_recipe"' in text


def test_url_import_fetches_source_before_structuring(client, auth, monkeypatch):
    auth.register()
    auth.login()
    captured = {}
    monkeypatch.setattr(
        "amstabase.recipes.fetch_recipe_source", lambda url: "Geladener Rezepttext"
    )

    def fake_structure(text):
        captured["text"] = text
        return imported_recipe()

    monkeypatch.setattr("amstabase.recipes.structure_recipe", fake_structure)
    response = client.post(
        "/import_recipe", data={"source_url": "https://example.com/recipe"}
    )
    assert response.status_code == 200
    assert captured["text"] == "Geladener Rezepttext"


def test_import_requires_exactly_one_source(client, auth, monkeypatch):
    auth.register()
    auth.login()
    response = client.post(
        "/import_recipe",
        data={"source_url": "https://example.com", "source_text": "Text"},
    )
    assert "entweder eine URL oder einen Textblock" in response.get_data(as_text=True)
