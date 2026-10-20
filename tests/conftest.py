"""Fixtures que simulam a PokeAPI sem acessar a internet.

O cliente real é usado de ponta a ponta; só o transporte HTTP é trocado por um
`httpx.MockTransport` que responde com dados no mesmo formato da API.
"""

from __future__ import annotations

import io

import httpx
import pytest
from PIL import Image

from pokedex.api import BASE_URL, PokeAPI
from pokedex.cache import DiskCache

STAT_KEYS = ["hp", "attack", "defense", "special-attack", "special-defense", "speed"]


def make_pokemon(
    pid: int,
    name: str,
    types: list[str],
    stats: list[int],
    height: int = 7,
    weight: int = 69,
    species: str | None = None,
) -> dict:
    species = species or name
    return {
        "id": pid,
        "name": name,
        "height": height,
        "weight": weight,
        "types": [{"slot": i + 1, "type": {"name": t}} for i, t in enumerate(types)],
        "stats": [
            {"base_stat": v, "stat": {"name": k}} for k, v in zip(STAT_KEYS, stats, strict=True)
        ],
        "abilities": [
            {"ability": {"name": "static"}, "is_hidden": False},
            {"ability": {"name": "lightning-rod"}, "is_hidden": True},
        ],
        "sprites": {
            "front_default": f"https://sprites.test/{pid}.png",
            "front_shiny": f"https://sprites.test/shiny/{pid}.png",
            "other": {
                "official-artwork": {
                    "front_default": f"https://sprites.test/art/{pid}.png",
                    "front_shiny": f"https://sprites.test/art/shiny/{pid}.png",
                }
            },
        },
        "cries": {"latest": f"https://sprites.test/cries/{pid}.ogg"},
        "species": {"url": f"{BASE_URL}/pokemon-species/{species}/"},
    }


def make_species(name: str, chain_id: int, gen: int = 1, legendary: bool = False) -> dict:
    return {
        "name": name,
        "is_legendary": legendary,
        "is_mythical": False,
        "capture_rate": 190,
        "generation": {"url": f"{BASE_URL}/generation/{gen}/"},
        "evolution_chain": {"url": f"{BASE_URL}/evolution-chain/{chain_id}/"},
        "genera": [
            {"genus": "Mouse Pokémon", "language": {"name": "en"}},
            {"genus": "ねずみポケモン", "language": {"name": "ja"}},
        ],
        "flavor_text_entries": [
            {
                "flavor_text": "When several of\nthese POKéMON\x0cgather, their\nelectricity could "
                "build and cause lightning storms.",
                "language": {"name": "en"},
            },
        ],
    }


SPECIES_IDS = {
    "pichu": 172, "pikachu": 25, "raichu": 26, "charmander": 4, "charmeleon": 5,
    "charizard": 6, "squirtle": 7, "gastly": 92, "haunter": 93, "gengar": 94,
    "eevee": 133, "vaporeon": 134, "jolteon": 135, "espeon": 196, "mr-mime": 122,
}  # fmt: skip


def node(name: str, children: list[dict] | None = None, **details) -> dict:
    return {
        "species": {"name": name, "url": f"{BASE_URL}/pokemon-species/{SPECIES_IDS[name]}/"},
        "evolution_details": [details] if details else [],
        "evolves_to": children or [],
    }


POKEMON = {
    "pikachu": make_pokemon(25, "pikachu", ["electric"], [35, 55, 40, 50, 50, 90]),
    "charizard": make_pokemon(
        6, "charizard", ["fire", "flying"], [78, 84, 78, 109, 85, 100], height=17, weight=905
    ),
    "blastoise": make_pokemon(9, "blastoise", ["water"], [79, 83, 100, 85, 105, 78]),
    "gengar": make_pokemon(94, "gengar", ["ghost", "poison"], [60, 65, 60, 130, 75, 110]),
    "eevee": make_pokemon(133, "eevee", ["normal"], [55, 55, 50, 45, 65, 55]),
    "mr-mime": make_pokemon(122, "mr-mime", ["psychic", "fairy"], [40, 45, 65, 100, 120, 90]),
}
SPECIES = {
    "pikachu": make_species("pikachu", 10),
    "charizard": make_species("charizard", 2),
    "blastoise": make_species("blastoise", 3),
    "gengar": make_species("gengar", 40),
    "eevee": make_species("eevee", 67),
    "mr-mime": make_species("mr-mime", 99),
}
CHAINS = {
    10: {
        "chain": node(
            "pichu",
            [
                node(
                    "pikachu",
                    [
                        node(
                            "raichu", trigger={"name": "use-item"}, item={"name": "thunder-stone"}
                        ),
                    ],
                    trigger={"name": "level-up"},
                    min_happiness=220,
                )
            ],
        )
    },
    2: {
        "chain": node(
            "charmander",
            [
                node(
                    "charmeleon",
                    [
                        node("charizard", trigger={"name": "level-up"}, min_level=36),
                    ],
                    trigger={"name": "level-up"},
                    min_level=16,
                )
            ],
        )
    },
    3: {"chain": node("squirtle")},
    40: {
        "chain": node(
            "gastly",
            [
                node(
                    "haunter",
                    [
                        node("gengar", trigger={"name": "trade"}),
                    ],
                    trigger={"name": "level-up"},
                    min_level=25,
                )
            ],
        )
    },
    67: {
        "chain": node(
            "eevee",
            [
                node("vaporeon", trigger={"name": "use-item"}, item={"name": "water-stone"}),
                node("jolteon", trigger={"name": "use-item"}, item={"name": "thunder-stone"}),
                node("espeon", trigger={"name": "level-up"}, min_happiness=160, time_of_day="day"),
            ],
        )
    },
    99: {"chain": node("mr-mime")},
}
ALIASES = {str(p["id"]): name for name, p in POKEMON.items()}


def sprite_png(seed: int = 0) -> bytes:
    """Um 'sprite' 96x96 com área transparente em volta, como os reais."""
    img = Image.new("RGBA", (96, 96), (0, 0, 0, 0))
    for x in range(30, 66):
        for y in range(28, 70):
            img.putpixel((x, y), ((x * 7 + seed) % 256, (y * 5) % 256, 120, 255))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


class FakeServer:
    def __init__(self) -> None:
        self.calls: list[str] = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        self.calls.append(url)
        if request.url.host == "sprites.test":
            return httpx.Response(200, content=sprite_png(len(url)))

        parts = request.url.path.strip("/").split("/")  # api, v2, recurso, chave
        resource, key = parts[2], parts[3] if len(parts) > 3 else None
        if resource == "pokemon" and key is None:
            names = list(POKEMON) + ["raichu", "pichu", "charmander"]
            return httpx.Response(200, json={"results": [{"name": n} for n in names]})
        if resource == "pokemon":
            data = POKEMON.get(ALIASES.get(key, key))
        elif resource == "pokemon-species":
            data = SPECIES.get(key)
        elif resource == "evolution-chain":
            data = CHAINS.get(int(key))
        else:
            data = None
        return httpx.Response(200, json=data) if data else httpx.Response(404)


@pytest.fixture
def server() -> FakeServer:
    return FakeServer()


@pytest.fixture
def api(tmp_path, server) -> PokeAPI:
    client = httpx.Client(transport=httpx.MockTransport(server))
    return PokeAPI(cache=DiskCache(tmp_path / "cache"), client=client)


@pytest.fixture
def cli_api(monkeypatch, tmp_path, server):
    """Faz a CLI usar a API falsa e um cache temporário."""
    from pokedex import cli

    monkeypatch.setenv("POKEDEX_CACHE_DIR", str(tmp_path / "cache"))

    def factory():
        client = httpx.Client(transport=httpx.MockTransport(server))
        return PokeAPI(
            cache=DiskCache(tmp_path / "cache"), client=client, offline=cli.state["offline"]
        )

    monkeypatch.setattr(cli, "make_api", factory)
    return server


class FakeAIServer:
    """Responde como a API da Anthropic ou da OpenAI, guardando o que recebeu."""

    def __init__(self) -> None:
        self.requests: list[dict] = []
        self.reply = "Pikachu, o Pokémon Rato. Guarda eletricidade nas bochechas."
        self.status = 200

    def __call__(self, request: httpx.Request) -> httpx.Response:
        import json

        body = json.loads(request.content)
        self.requests.append({"url": str(request.url), "headers": request.headers, "body": body})
        if self.status != 200:
            return httpx.Response(self.status, json={"error": "x"})
        if request.url.host == "api.anthropic.com":
            return httpx.Response(200, json={"content": [{"type": "text", "text": self.reply}]})
        return httpx.Response(200, json={"choices": [{"message": {"content": self.reply}}]})


@pytest.fixture
def ai_server() -> FakeAIServer:
    return FakeAIServer()


@pytest.fixture
def ai_client(ai_server) -> httpx.Client:
    return httpx.Client(transport=httpx.MockTransport(ai_server))
