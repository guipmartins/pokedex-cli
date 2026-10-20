"""Servidor FastAPI: entrega a página do aparelho e uma API JSON para ela."""

from __future__ import annotations

import base64
import binascii
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from pokedex import __version__
from pokedex.ai import AIError, Message, PokedexAI
from pokedex.api import MAX_POKEMON_ID, PokeAPI, PokedexError, PokemonNotFound
from pokedex.models import Pokemon, Species
from pokedex.type_chart import TYPE_COLORS, defensive_profile, group_profile, type_name

STATIC_DIR = Path(__file__).parent / "static"
MAX_UPLOAD_BYTES = 8 * 1024 * 1024
DEFENSE_LABELS = {
    4: "Muito fraco",
    2: "Fraco",
    0.5: "Resiste",
    0.25: "Resiste muito",
    0: "Imune",
}


class AskBody(BaseModel):
    pokemon: str
    question: str = Field(min_length=1, max_length=500)
    history: list[dict[str, str]] = Field(default_factory=list)


class IdentifyBody(BaseModel):
    image: str  # data URL (data:image/png;base64,...) ou base64 puro


def _type(t: str) -> dict[str, str]:
    return {"key": t, "name": type_name(t), "color": TYPE_COLORS.get(t, "#888888")}


def serialize(api: PokeAPI, pokemon: Pokemon) -> dict[str, Any]:
    species = api.species(pokemon)
    evolution = api.evolution_chain(species) if species else None
    groups = group_profile(defensive_profile(pokemon.types))
    return {
        "id": pokemon.id,
        "name": pokemon.name,
        "display_name": pokemon.display_name,
        "types": [_type(t) for t in pokemon.types],
        "height_m": pokemon.height_m,
        "weight_kg": pokemon.weight_kg,
        "stats": [{"key": s.name, "label": s.label, "value": s.value} for s in pokemon.stats],
        "total": pokemon.total,
        "abilities": [
            {"name": n.replace("-", " ").title(), "hidden": h} for n, h in pokemon.abilities
        ],
        "artwork": pokemon.artwork_url,
        "shiny_artwork": pokemon.shiny_artwork_url,
        "sprite": pokemon.sprite_url,
        "cry": pokemon.cry_url,
        "species": _species(species),
        "defense": [
            {
                "multiplier": m,
                "label": DEFENSE_LABELS.get(m, f"{m:g}×"),
                "types": [_type(t) for t in ts],
            }
            for m, ts in groups.items()
        ],
        "evolution": evolution.to_dict() if evolution else None,
        "prev_id": pokemon.id - 1 if pokemon.id > 1 else None,
        "next_id": pokemon.id + 1 if pokemon.id < MAX_POKEMON_ID else None,
    }


def _species(species: Species | None) -> dict[str, Any] | None:
    if not species:
        return None
    return {
        "name": species.name,
        "genus": species.genus,
        "flavor_text": species.flavor_text,
        "generation": species.generation,
        "legendary": species.is_legendary,
        "mythical": species.is_mythical,
        "capture_rate": species.capture_rate,
    }


def create_app(api: PokeAPI | None = None, ai: PokedexAI | None = None) -> FastAPI:
    api = api or PokeAPI()
    app = FastAPI(title="Pokédex", version=__version__, docs_url="/api/docs")

    def fetch(query: str | int) -> Pokemon:
        try:
            return api.pokemon(query)
        except PokemonNotFound as exc:
            raise HTTPException(
                404, detail={"message": str(exc), "suggestions": exc.suggestions}
            ) from exc
        except PokedexError as exc:
            raise HTTPException(502, detail={"message": str(exc)}) from exc

    def require_ai() -> PokedexAI:
        if ai is None:
            raise HTTPException(
                503,
                detail={
                    "message": "IA desligada. Coloque ANTHROPIC_API_KEY ou OPENAI_API_KEY "
                    "no arquivo .env e reinicie."
                },
            )
        return ai

    def ai_call(fn, *args):
        try:
            return fn(*args)
        except AIError as exc:
            raise HTTPException(502, detail={"message": str(exc)}) from exc

    @app.get("/api/status")
    def status() -> dict[str, Any]:
        return {
            "version": __version__,
            "ai": {"enabled": ai is not None, "label": ai.label if ai else None},
            "max_id": MAX_POKEMON_ID,
        }

    @app.get("/api/pokemon/{query}")
    def pokemon(query: str) -> dict[str, Any]:
        p = fetch(query)
        try:
            return serialize(api, p)
        except PokedexError as exc:
            raise HTTPException(502, detail={"message": str(exc)}) from exc

    @app.get("/api/names")
    def names() -> list[str]:
        return api.all_names()

    @app.post("/api/ai/entry/{query}")
    def ai_entry(query: str) -> dict[str, str]:
        engine = require_ai()
        p = fetch(query)
        return {"text": ai_call(engine.entry, p, api.species(p))}

    @app.post("/api/ai/ask")
    def ai_ask(body: AskBody) -> dict[str, str]:
        engine = require_ai()
        p = fetch(body.pokemon)
        history = [
            Message(m.get("role", ""), m.get("content", ""))
            for m in body.history
            if m.get("role") in ("user", "assistant") and m.get("content")
        ]
        return {"text": ai_call(engine.ask, p, api.species(p), body.question, history)}

    @app.post("/api/ai/identify")
    def ai_identify(body: IdentifyBody) -> dict[str, Any]:
        engine = require_ai()
        raw = body.image.split(",", 1)[1] if body.image.startswith("data:") else body.image
        try:
            data = base64.b64decode(raw, validate=True)
        except (binascii.Error, ValueError) as exc:
            raise HTTPException(400, detail={"message": "Imagem inválida."}) from exc
        if len(data) > MAX_UPLOAD_BYTES:
            raise HTTPException(413, detail={"message": "Imagem muito grande (máx. 8 MB)."})

        result = ai_call(engine.identify, data)
        if not result["pokemon"]:
            return {"result": result, "pokemon": None, "suggestions": []}
        try:
            found = api.pokemon(result["pokemon"])
        except PokemonNotFound as exc:
            return {"result": result, "pokemon": None, "suggestions": exc.suggestions}
        except PokedexError as exc:
            raise HTTPException(502, detail={"message": str(exc)}) from exc
        return {"result": result, "pokemon": found.name, "suggestions": []}

    @app.get("/")
    def index() -> FileResponse:
        return FileResponse(STATIC_DIR / "index.html")

    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
    return app
