import pytest

from amstabase.db import set_setting
from amstabase.llm import RecipeImportError, fetch_recipe_source, structure_recipe


def test_structure_recipe_calls_openai_compatible_endpoint(app, monkeypatch):
    captured = {}

    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {
                "choices": [
                    {
                        "message": {
                            "content": """```json
                            {
                              "name": "Tomatensuppe",
                              "category": "Suppen",
                              "menu_description": "Fruchtige Suppe",
                              "allergens": [],
                              "approximate_cost": null,
                              "selling_price": null,
                              "instructions": ["Tomaten kochen", "Pürieren"],
                              "notes": "",
                              "ingredients": [
                                {"quantity": 500, "unit": "g", "ingredient_name": "Tomaten"}
                              ]
                            }
                            ```"""
                        }
                    }
                ]
            }

    def fake_post(url, **kwargs):
        captured["url"] = url
        captured.update(kwargs)
        return FakeResponse()

    monkeypatch.setattr("amstabase.llm.httpx.post", fake_post)
    with app.app_context():
        app.config["OPENAI_API_KEY"] = "secret"
        recipe, ingredients = structure_recipe("Tomatensuppe mit 500 g Tomaten")

    assert captured["url"] == "https://api.openai.com/v1/chat/completions"
    assert captured["headers"]["Authorization"] == "Bearer secret"
    assert captured["json"]["model"] == "gpt-4o-mini"
    assert recipe["name"] == "Tomatensuppe"
    assert recipe["category"] == "Suppen"
    assert "<ol>" in recipe["instructions"]
    assert ingredients == [
        {"quantity": 500.0, "unit": "g", "ingredient_name": "Tomaten"}
    ]


def test_fetch_recipe_source_extracts_visible_html_text(app, monkeypatch):
    captured = {}

    class FakeResponse:
        is_redirect = False
        headers = {"content-type": "text/html; charset=utf-8"}
        charset_encoding = "utf-8"

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

        def raise_for_status(self):
            return None

        def iter_bytes(self):
            yield b"<html><script>ignore()</script><body><h1>Soup</h1><p>Cook it</p></body></html>"

    class FakeClient:
        def __init__(self, **kwargs):
            captured["client"] = kwargs

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

        def stream(self, method, url, **kwargs):
            captured.update({"method": method, "url": url, **kwargs})
            return FakeResponse()

    monkeypatch.setattr(
        "amstabase.llm.socket.getaddrinfo",
        lambda *_args, **_kwargs: [(2, 1, 6, "", ("93.184.216.34", 0))],
    )
    monkeypatch.setattr("amstabase.llm.httpx.Client", FakeClient)
    with app.app_context():
        result = fetch_recipe_source("https://example.com/recipe")

    assert result == "Soup\nCook it"
    assert "ignore" not in result
    assert captured["client"]["trust_env"] is False
    assert captured["url"] == "https://93.184.216.34/recipe"
    assert captured["headers"]["Host"] == "example.com"
    assert captured["extensions"]["sni_hostname"] == "example.com"


def test_fetch_recipe_source_falls_back_for_unknown_charset(app, monkeypatch):
    class FakeResponse:
        is_redirect = False
        headers = {"content-type": "text/plain; charset=unknown-encoding"}
        charset_encoding = "unknown-encoding"

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

        def raise_for_status(self):
            return None

        def iter_bytes(self):
            yield "Käsekuchen".encode()

    class FakeClient:
        def __init__(self, **_kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

        def stream(self, _method, _url, **_kwargs):
            return FakeResponse()

    monkeypatch.setattr(
        "amstabase.llm.socket.getaddrinfo",
        lambda *_args, **_kwargs: [(2, 1, 6, "", ("93.184.216.34", 0))],
    )
    monkeypatch.setattr("amstabase.llm.httpx.Client", FakeClient)
    with app.app_context():
        result = fetch_recipe_source("https://example.com/recipe")

    assert result == "Käsekuchen"


def test_fetch_recipe_source_rejects_private_network(app, monkeypatch):
    monkeypatch.setattr(
        "amstabase.llm.socket.getaddrinfo",
        lambda *_args, **_kwargs: [(2, 1, 6, "", ("127.0.0.1", 0))],
    )
    with app.app_context(), pytest.raises(RecipeImportError, match="private"):
        fetch_recipe_source("http://localhost/recipe")


def test_structure_recipe_rejects_api_key_over_http(app):
    with app.app_context():
        app.config["OPENAI_API_KEY"] = "secret"
        set_setting("llm_endpoint", "http://llm.example/v1/chat/completions")
        with pytest.raises(RecipeImportError, match="nur an einen HTTPS-Endpunkt"):
            structure_recipe("Ein gültiger Rezepttext")


def test_structure_recipe_rejects_invalid_llm_response(app, monkeypatch):
    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {"choices": [{"message": {"content": "kein json"}}]}

    monkeypatch.setattr("amstabase.llm.httpx.post", lambda *_args, **_kwargs: FakeResponse())
    with app.app_context(), pytest.raises(RecipeImportError, match="kein gültiges JSON"):
        structure_recipe("Ein gültiger Rezepttext")
