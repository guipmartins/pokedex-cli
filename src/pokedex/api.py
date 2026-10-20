"""Cliente da PokeAPI (https://pokeapi.co) com cache em disco."""

from __future__ import annotations

import difflib
import unicodedata
from typing import Any

import httpx

from pokedex.cache import DiskCache
from pokedex.models import EvolutionNode, Pokemon, Species

BASE_URL = "https://pokeapi.co/api/v2"
MAX_POKEMON_ID = 1025  # até a 9ª geração


class PokedexError(Exception):
    """Erro com mensagem amigável para mostrar ao usuário."""


class PokemonNotFound(PokedexError):
    def __init__(self, query: str, suggestions: list[str]) -> None:
        self.query = query
        self.suggestions = suggestions
        super().__init__(f"Pokémon '{query}' não encontrado.")


def normalize_query(query: str | int) -> str:
    """'Mr. Mime' -> 'mr-mime', ' Pikachu ' -> 'pikachu', '#025' -> '25'."""
    text = str(query).strip().lower().lstrip("#")
    if text.isdigit():
        return str(int(text))
    text = text.replace("♀", "-f").replace("♂", "-m")
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    for ch in (".", "'", ":"):
        text = text.replace(ch, "")
    return "-".join(text.split())


class PokeAPI:
    def __init__(
        self,
        cache: DiskCache | None = None,
        client: httpx.Client | None = None,
        offline: bool = False,
    ) -> None:
        self.cache = cache or DiskCache()
        self.offline = offline
        self._client = client or httpx.Client(
            timeout=15.0,
            follow_redirects=True,
            headers={"User-Agent": "pokedex-cli (github.com)"},
        )

    def __enter__(self) -> PokeAPI:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    def close(self) -> None:
        self._client.close()

    # ---------------------------------------------------------------- baixo nível
    def _url(self, path_or_url: str) -> str:
        if path_or_url.startswith("http"):
            return path_or_url
        path = path_or_url.strip("/")
        return f"{BASE_URL}/{path}" if "?" in path else f"{BASE_URL}/{path}/"

    def get_json(self, path_or_url: str) -> dict[str, Any] | None:
        """Devolve o JSON ou None se o recurso não existir (404)."""
        url = self._url(path_or_url)
        cached = self.cache.get_json(url)
        if cached is not None:
            return cached
        if self.offline:
            raise PokedexError("Modo offline: esse dado ainda não está no cache.")
        try:
            response = self._client.get(url)
        except httpx.HTTPError as exc:
            raise PokedexError(
                "Não consegui falar com a PokeAPI. Verifique sua conexão "
                f"(ou use --offline para ver o que já está no cache).\nDetalhe: {exc}"
            ) from exc
        if response.status_code == 404:
            return None
        if response.status_code >= 400:
            raise PokedexError(f"A PokeAPI respondeu com erro {response.status_code}.")
        data = response.json()
        self.cache.set_json(url, data)
        return data

    def get_bytes(self, url: str) -> bytes | None:
        cached = self.cache.get_bytes(url)
        if cached is not None:
            return cached
        if self.offline:
            return None
        try:
            response = self._client.get(url)
            response.raise_for_status()
        except httpx.HTTPError:
            return None  # sem sprite não é motivo para falhar
        self.cache.set_bytes(url, response.content)
        return response.content

    # --------------------------------------------------------------- alto nível
    def pokemon(self, query: str | int) -> Pokemon:
        key = normalize_query(query)
        data = self.get_json(f"pokemon/{key}") if key else None
        if data is None:
            raise PokemonNotFound(str(query), self.suggest(key))
        return Pokemon.from_api(data)

    def species(self, pokemon: Pokemon) -> Species | None:
        data = self.get_json(pokemon.species_url or f"pokemon-species/{pokemon.id}")
        return Species.from_api(data) if data else None

    def evolution_chain(self, species: Species) -> EvolutionNode | None:
        if not species.evolution_chain_url:
            return None
        data = self.get_json(species.evolution_chain_url)
        return EvolutionNode.from_api(data) if data else None

    def sprite(self, pokemon: Pokemon, shiny: bool = False) -> bytes | None:
        url = pokemon.shiny_sprite_url if shiny else pokemon.sprite_url
        return self.get_bytes(url) if url else None

    def all_names(self) -> list[str]:
        try:
            data = self.get_json(f"pokemon?limit={MAX_POKEMON_ID + 400}")
        except PokedexError:
            return []
        return [r["name"] for r in (data or {}).get("results", [])]

    def suggest(self, query: str, n: int = 3) -> list[str]:
        if not query or query.isdigit():
            return []
        return difflib.get_close_matches(query, self.all_names(), n=n, cutoff=0.6)
