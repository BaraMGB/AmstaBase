def test_viewer_cannot_create_or_admin(client, auth, user_factory):
    user_factory("viewer", "Viewer")
    auth.login("viewer")
    assert client.get("/new_recipe").status_code == 403
    assert client.get("/admin/").status_code == 403


def test_editor_can_open_recipe_form(client, auth, user_factory):
    user_factory("editor", "Editor")
    auth.login("editor")
    response = client.get("/new_recipe")
    assert response.status_code == 200
    assert "Neues Rezept anlegen" in response.get_data(as_text=True)


def test_anonymous_write_routes_redirect_to_login(client):
    for method, path in (
        ("get", "/new_recipe"),
        ("get", "/edit_recipe/1"),
        ("post", "/delete_recipe/1"),
        ("post", "/delete_photo/1"),
    ):
        response = getattr(client, method)(path)
        assert response.status_code == 302
        assert "/login" in response.headers["Location"]
