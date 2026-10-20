"""Modelos de dados e conversão a partir das respostas JSON da PokeAPI."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from pokedex.type_chart import type_name

STAT_NAMES_PT: dict[str, str] = {
    "hp": "HP",
    "attack": "Ataque",
    "defense": "Defesa",
    "special-attack": "Atq. Esp.",
    "special-defense": "Def. Esp.",
    "speed": "Velocidade",
}

PREFERRED_LANGS = ("pt-br", "pt", "en")


def pretty_name(slug: str) -> str:
    """'mr-mime' -> 'Mr Mime', 'charizard' -> 'Charizard'."""
    return " ".join(part.capitalize() for part in slug.split("-"))


def _pick_lang(entries: list[dict[str, Any]], key: str) -> str | None:
    by_lang: dict[str, str] = {}
    for entry in entries:
        lang = entry.get("language", {}).get("name")
        if lang and lang not in by_lang:
            by_lang[lang] = entry.get(key, "")
    for lang in PREFERRED_LANGS:
        if by_lang.get(lang):
            return by_lang[lang]
    return None


def _clean_text(text: str) -> str:
    # O texto da Pokédex vem com quebras de página (\x0c) e quebras de linha soltas.
    return re.sub(r"\s+", " ", text.replace("\x0c", " ").replace("­", "")).strip()


@dataclass(frozen=True)
class Stat:
    name: str
    value: int

    @property
    def label(self) -> str:
        return STAT_NAMES_PT.get(self.name, pretty_name(self.name))


@dataclass
class Pokemon:
    id: int
    name: str
    types: list[str]
    height_m: float
    weight_kg: float
    stats: list[Stat]
    abilities: list[tuple[str, bool]]  # (nome, é_oculta)
    sprite_url: str | None = None
    shiny_sprite_url: str | None = None
    species_url: str | None = None

    @property
    def display_name(self) -> str:
        return pretty_name(self.name)

    @property
    def total(self) -> int:
        return sum(s.value for s in self.stats)

    def stat(self, name: str) -> int:
        return next((s.value for s in self.stats if s.name == name), 0)

    @classmethod
    def from_api(cls, data: dict[str, Any]) -> Pokemon:
        sprites = data.get("sprites") or {}
        artwork = (sprites.get("other") or {}).get("official-artwork") or {}
        return cls(
            id=data["id"],
            name=data["name"],
            types=[t["type"]["name"] for t in sorted(data["types"], key=lambda t: t["slot"])],
            height_m=data["height"] / 10,
            weight_kg=data["weight"] / 10,
            stats=[Stat(s["stat"]["name"], s["base_stat"]) for s in data["stats"]],
            abilities=[(a["ability"]["name"], a["is_hidden"]) for a in data["abilities"]],
            sprite_url=sprites.get("front_default") or artwork.get("front_default"),
            shiny_sprite_url=sprites.get("front_shiny") or artwork.get("front_shiny"),
            species_url=(data.get("species") or {}).get("url"),
        )


@dataclass
class Species:
    name: str
    genus: str | None
    flavor_text: str | None
    generation: int | None
    is_legendary: bool
    is_mythical: bool
    capture_rate: int | None
    evolution_chain_url: str | None

    @classmethod
    def from_api(cls, data: dict[str, Any]) -> Species:
        generation = None
        gen_url = (data.get("generation") or {}).get("url", "")
        match = re.search(r"/generation/(\d+)/?$", gen_url)
        if match:
            generation = int(match.group(1))

        flavor = _pick_lang(data.get("flavor_text_entries", []), "flavor_text")
        return cls(
            name=data["name"],
            genus=_pick_lang(data.get("genera", []), "genus"),
            flavor_text=_clean_text(flavor) if flavor else None,
            generation=generation,
            is_legendary=bool(data.get("is_legendary")),
            is_mythical=bool(data.get("is_mythical")),
            capture_rate=data.get("capture_rate"),
            evolution_chain_url=(data.get("evolution_chain") or {}).get("url"),
        )


@dataclass
class EvolutionNode:
    name: str
    condition: str | None = None
    evolves_to: list[EvolutionNode] = field(default_factory=list)

    @property
    def display_name(self) -> str:
        return pretty_name(self.name)

    @classmethod
    def from_api(cls, data: dict[str, Any]) -> EvolutionNode:
        """Aceita tanto a resposta inteira (/evolution-chain/N) quanto um nó `chain`."""
        node = data.get("chain", data)
        details = node.get("evolution_details") or []
        return cls(
            name=node["species"]["name"],
            condition=describe_evolution(details[0]) if details else None,
            evolves_to=[cls.from_api(child) for child in node.get("evolves_to", [])],
        )

    def walk(self):
        yield self
        for child in self.evolves_to:
            yield from child.walk()


_TIME_PT = {"day": "de dia", "night": "à noite", "dusk": "ao entardecer"}


def describe_evolution(d: dict[str, Any]) -> str:
    """Transforma um `evolution_details` da PokeAPI numa frase curta em português."""
    trigger = (d.get("trigger") or {}).get("name")
    parts: list[str] = []

    if trigger == "trade":
        parts.append("Troca")
    elif trigger == "use-item" and d.get("item"):
        parts.append(f"Usar {pretty_name(d['item']['name'])}")
    elif trigger == "shed":
        parts.append("Espaço livre na equipe")
    elif trigger and trigger != "level-up":
        parts.append(pretty_name(trigger))

    if d.get("min_level"):
        parts.append(f"Nv. {d['min_level']}")
    elif trigger == "level-up" and not any(
        d.get(k)
        for k in (
            "min_happiness",
            "min_affection",
            "known_move",
            "known_move_type",
            "location",
            "min_beauty",
        )
    ):
        parts.append("Subir de nível")

    if d.get("held_item"):
        parts.append(f"segurando {pretty_name(d['held_item']['name'])}")
    if d.get("min_happiness"):
        parts.append("com amizade alta")
    if d.get("min_affection"):
        parts.append("com afeição alta")
    if d.get("min_beauty"):
        parts.append("com beleza alta")
    if d.get("known_move"):
        parts.append(f"sabendo {pretty_name(d['known_move']['name'])}")
    if d.get("known_move_type"):
        parts.append(f"sabendo golpe {type_name(d['known_move_type']['name'])}")
    if d.get("location"):
        parts.append(f"em {pretty_name(d['location']['name'])}")
    if d.get("time_of_day") in _TIME_PT:
        parts.append(_TIME_PT[d["time_of_day"]])
    if d.get("gender") == 1:
        parts.append("(fêmea)")
    elif d.get("gender") == 2:
        parts.append("(macho)")

    return " ".join(parts) if parts else "?"
