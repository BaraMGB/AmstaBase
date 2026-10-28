from amstabase.services import (
    allowed_image,
    extract_ingredients,
    optional_float,
    sanitize_instructions,
)


def test_allowed_image_is_case_insensitive():
    assert allowed_image("food.JPG")
    assert not allowed_image("food.svg")
    assert not allowed_image("README")


def test_optional_float_supports_comma_and_empty_values():
    assert optional_float("12,50") == 12.5
    assert optional_float("") is None


def test_extract_ingredients_preserves_form_order():
    form = {
        "ingredient_name_2": "Salz",
        "quantity_2": "0",
        "unit_2": "nach Geschmack",
        "ingredient_name_1": "Mehl",
        "quantity_1": "100",
        "unit_1": "g",
    }
    ingredients = extract_ingredients(form)
    assert [item["name"] for item in ingredients] == ["Salz", "Mehl"]
    assert [item["display_order"] for item in ingredients] == [1, 2]


def test_sanitize_instructions_removes_dangerous_markup():
    result = sanitize_instructions(
        '<p>Text</p><script>alert(1)</script><a href="javascript:x">x</a>'
    )
    assert "<p>Text</p>" in result
    assert "<script" not in result
    assert "javascript:" not in result
