"""OpenAI-compatible recipe extraction and safe URL retrieval."""

from __future__ import annotations

import ipaddress
import json
import os
import socket
from html import escape
from pathlib import Path
from urllib.parse import urljoin, urlparse

import httpx
from bs4 import BeautifulSoup
from flask import current_app

from .db import get_categories, get_setting
from .services import optional_float, sanitize_instructions

DEFAULT_LLM_ENDPOINT = "https://api.openai.com/v1/chat/completions"
DEFAULT_LLM_MODEL = "gpt-4o-mini"


class RecipeImportError(RuntimeError):
    """Raised when recipe source retrieval or LLM extraction fails."""


def is_http_url(value: str) -> bool:
    parsed = urlparse(value)
    try:
        _ = parsed.port
    except ValueError:
        return False
    return (
        parsed.scheme in {"http", "https"}
        and bool(parsed.hostname)
        and parsed.username is None
        and parsed.password is None
    )


def is_https_url(value: str) -> bool:
    return is_http_url(value) and urlparse(value).scheme == "https"


def get_openai_api_key() -> str:
    """Read the admin-managed secret file, falling back to the environment."""

    key_file = Path(current_app.config["OPENAI_API_KEY_FILE"])
    try:
        if key_file.is_file():
            return key_file.read_text(encoding="utf-8").strip()
    except OSError:
        current_app.logger.exception("Could not read the OpenAI API key file")
    return current_app.config.get("OPENAI_API_KEY", "").strip()


def openai_api_key_source() -> str | None:
    key_file = Path(current_app.config["OPENAI_API_KEY_FILE"])
    if key_file.is_file():
        return "admin"
    if current_app.config.get("OPENAI_API_KEY", "").strip():
        return "environment"
    return None


def save_openai_api_key(api_key: str) -> None:
    """Atomically store an API key in a mode-0600 file outside the database."""

    api_key = api_key.strip()
    if not api_key or "\n" in api_key or "\r" in api_key:
        raise ValueError("Der API-Key ist leer oder ungültig.")
    if len(api_key) > 10_000:
        raise ValueError("Der API-Key ist zu lang.")

    key_file = Path(current_app.config["OPENAI_API_KEY_FILE"])
    key_file.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    key_file.parent.chmod(0o700)
    temporary_file = key_file.with_name(f".{key_file.name}.tmp")
    descriptor = os.open(temporary_file, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as file_handle:
            file_handle.write(api_key)
        os.replace(temporary_file, key_file)
        key_file.chmod(0o600)
    finally:
        temporary_file.unlink(missing_ok=True)


def delete_openai_api_key() -> None:
    Path(current_app.config["OPENAI_API_KEY_FILE"]).unlink(missing_ok=True)


def _validated_public_source_target(url: str) -> tuple[str, str, str]:
    """Resolve once and return an IP-pinned URL, Host header and TLS SNI name."""

    if not is_http_url(url):
        raise RecipeImportError("Die Rezept-URL muss eine gültige HTTP- oder HTTPS-URL sein.")

    parsed = urlparse(url)
    hostname = parsed.hostname
    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    try:
        addresses = socket.getaddrinfo(hostname, port, type=socket.SOCK_STREAM)
    except socket.gaierror as error:
        raise RecipeImportError(
            "Der Hostname der Rezept-URL konnte nicht aufgelöst werden."
        ) from error

    public_addresses: list[ipaddress.IPv4Address | ipaddress.IPv6Address] = []
    for address in addresses:
        ip = ipaddress.ip_address(address[4][0].split("%", 1)[0])
        if not ip.is_global:
            raise RecipeImportError("Lokale oder private Netzwerkadressen sind nicht erlaubt.")
        if ip not in public_addresses:
            public_addresses.append(ip)

    if not public_addresses:
        raise RecipeImportError("Der Hostname der Rezept-URL hat keine erreichbare Adresse.")

    selected_ip = public_addresses[0]
    ip_host = f"[{selected_ip.compressed}]" if selected_ip.version == 6 else selected_ip.compressed
    target_netloc = f"{ip_host}:{parsed.port}" if parsed.port is not None else ip_host
    target_url = parsed._replace(netloc=target_netloc, fragment="").geturl()

    try:
        original_ip = ipaddress.ip_address(hostname)
    except ValueError:
        sni_hostname = hostname.encode("idna").decode("ascii")
        host_name = sni_hostname
    else:
        sni_hostname = original_ip.compressed
        host_name = f"[{sni_hostname}]" if original_ip.version == 6 else sni_hostname
    host_header = f"{host_name}:{parsed.port}" if parsed.port is not None else host_name
    return target_url, host_header, sni_hostname


def fetch_recipe_source(url: str) -> str:
    """Fetch public HTML/text while limiting redirects, size and SSRF exposure."""

    max_bytes = current_app.config["RECIPE_URL_MAX_BYTES"]
    timeout = current_app.config["LLM_REQUEST_TIMEOUT_SECONDS"]
    current_url = url.strip()

    try:
        with httpx.Client(
            timeout=timeout,
            follow_redirects=False,
            trust_env=False,
            headers={"User-Agent": "AmstaBase recipe importer/1.0"},
        ) as client:
            for _redirect in range(4):
                target_url, host_header, sni_hostname = _validated_public_source_target(
                    current_url
                )
                with client.stream(
                    "GET",
                    target_url,
                    headers={"Host": host_header},
                    extensions={"sni_hostname": sni_hostname},
                ) as response:
                    if response.is_redirect:
                        location = response.headers.get("location")
                        if not location:
                            raise RecipeImportError(
                                "Die Rezept-URL enthält eine ungültige Weiterleitung."
                            )
                        current_url = urljoin(current_url, location)
                        continue

                    response.raise_for_status()
                    content_type = response.headers.get("content-type", "").lower()
                    if not any(kind in content_type for kind in ("text/html", "text/plain")):
                        raise RecipeImportError("Die URL liefert weder HTML noch Text.")

                    content = bytearray()
                    for chunk in response.iter_bytes():
                        content.extend(chunk)
                        if len(content) > max_bytes:
                            raise RecipeImportError("Die geladene Rezeptseite ist zu groß.")
                    encoding = response.charset_encoding or "utf-8"
                    try:
                        text = bytes(content).decode(encoding, errors="replace")
                    except LookupError:
                        text = bytes(content).decode("utf-8", errors="replace")
                    break
            else:
                raise RecipeImportError("Die Rezept-URL enthält zu viele Weiterleitungen.")
    except RecipeImportError:
        raise
    except httpx.HTTPError as error:
        raise RecipeImportError(f"Die Rezept-URL konnte nicht geladen werden: {error}") from error

    if "text/html" in content_type:
        soup = BeautifulSoup(text, "html.parser")
        for element in soup(["script", "style", "noscript", "svg"]):
            element.decompose()
        text = soup.get_text("\n", strip=True)

    return _limit_source_text(text)


def _limit_source_text(text: str) -> str:
    normalized = "\n".join(line.strip() for line in text.splitlines() if line.strip())
    max_chars = current_app.config["RECIPE_SOURCE_MAX_CHARS"]
    if not normalized:
        raise RecipeImportError("Die Rezeptquelle enthält keinen auswertbaren Text.")
    if len(normalized) > max_chars:
        normalized = normalized[:max_chars]
    return normalized


def _json_from_content(content: str) -> dict:
    cleaned = content.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.removeprefix("```json").removeprefix("```")
        cleaned = cleaned.removesuffix("```").strip()
    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start == -1 or end == -1:
        raise RecipeImportError("Das LLM hat kein gültiges JSON geliefert.")
    try:
        data = json.loads(cleaned[start : end + 1])
    except json.JSONDecodeError as error:
        raise RecipeImportError("Das LLM-Ergebnis konnte nicht als JSON gelesen werden.") from error
    if not isinstance(data, dict):
        raise RecipeImportError("Das LLM-Ergebnis hat ein unerwartetes Format.")
    return data


def _as_text(value) -> str:
    if value is None:
        return ""
    if isinstance(value, list):
        return ", ".join(str(item) for item in value)
    return str(value).strip()


def _as_number(value) -> float | str | None:
    if value is None or value == "":
        return ""
    try:
        return optional_float(str(value))
    except ValueError:
        return ""


def _normalize_recipe(data: dict) -> tuple[dict, list[dict]]:
    name = _as_text(data.get("name"))
    if not name:
        raise RecipeImportError("Das LLM-Ergebnis enthält keinen Rezeptnamen.")

    categories = get_categories()
    category_lookup = {category.casefold(): category for category in categories}
    suggested_category = _as_text(data.get("category"))
    category = category_lookup.get(
        suggested_category.casefold(), categories[0] if categories else ""
    )

    instructions = data.get("instructions")
    if isinstance(instructions, list):
        items = "".join(f"<li>{escape(_as_text(item))}</li>" for item in instructions)
        instructions = f"<ol>{items}</ol>"

    recipe = {
        "name": name,
        "category": category,
        "in_menu": False,
        "menu_description": _as_text(data.get("menu_description")),
        "allergens": _as_text(data.get("allergens")),
        "approximate_cost": _as_number(data.get("approximate_cost")),
        "selling_price": _as_number(data.get("selling_price")),
        "instructions": sanitize_instructions(_as_text(instructions)),
        "notes": _as_text(data.get("notes")),
    }

    ingredients = []
    raw_ingredients = data.get("ingredients", [])
    if isinstance(raw_ingredients, list):
        for item in raw_ingredients:
            if not isinstance(item, dict):
                continue
            ingredient_name = _as_text(item.get("ingredient_name") or item.get("name"))
            if not ingredient_name:
                continue
            ingredients.append(
                {
                    "quantity": _as_number(item.get("quantity")),
                    "unit": _as_text(item.get("unit")),
                    "ingredient_name": ingredient_name,
                }
            )
    return recipe, ingredients


def structure_recipe(source_text: str) -> tuple[dict, list[dict]]:
    """Send source text to an OpenAI-compatible chat completions endpoint."""

    source_text = _limit_source_text(source_text)
    endpoint = get_setting("llm_endpoint", DEFAULT_LLM_ENDPOINT) or DEFAULT_LLM_ENDPOINT
    model = get_setting("llm_model", DEFAULT_LLM_MODEL) or DEFAULT_LLM_MODEL
    if not is_http_url(endpoint):
        raise RecipeImportError("Der konfigurierte LLM-Endpunkt ist ungültig.")

    categories = ", ".join(get_categories())
    system_prompt = f"""
Du extrahierst Rezepte für eine Rezeptdatenbank. Antworte ausschließlich mit einem JSON-Objekt.
Verwende dieses Schema:
{{
  "name": "string",
  "category": "eine der Kategorien: {categories}",
  "menu_description": "kurze Beschreibung",
  "allergens": "kommagetrennte Allergene",
  "approximate_cost": null,
  "selling_price": null,
  "instructions": "einfaches HTML mit p, ol, ul und li",
  "notes": "string",
  "ingredients": [
    {{
      "quantity": 1.0,
      "unit": "g/ml/kg/l/TL/EL/Stück/Prise/nach Geschmack",
      "ingredient_name": "string"
    }}
  ]
}}
Erfinde keine Preise. Fehlende Werte bleiben leer oder null. Mengen müssen numerisch sein;
bei 'nach Geschmack' verwende 0. Bewahre alle fachlich relevanten Zubereitungsschritte.
""".strip()
    headers = {"Content-Type": "application/json"}
    api_key = get_openai_api_key()
    if api_key:
        if not is_https_url(endpoint):
            raise RecipeImportError(
                "Ein API-Key darf nur an einen HTTPS-Endpunkt übertragen werden."
            )
        headers["Authorization"] = f"Bearer {api_key}"

    try:
        response = httpx.post(
            endpoint,
            headers=headers,
            json={
                "model": model,
                "temperature": 0,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": source_text},
                ],
            },
            timeout=current_app.config["LLM_REQUEST_TIMEOUT_SECONDS"],
        )
        response.raise_for_status()
        payload = response.json()
        content = payload["choices"][0]["message"]["content"]
        if not isinstance(content, str):
            raise TypeError("message.content is not a string")
    except (httpx.HTTPError, KeyError, IndexError, TypeError, ValueError) as error:
        raise RecipeImportError(
            f"Der LLM-Endpunkt konnte nicht verarbeitet werden: {error}"
        ) from error

    return _normalize_recipe(_json_from_content(content))
