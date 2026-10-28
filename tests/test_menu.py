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
