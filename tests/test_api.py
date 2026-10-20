import pytest

from pokedex.api import PokedexError, PokemonNotFound, normalize_query


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("Pikachu", "pikachu"),
        ("  Mr. Mime ", "mr-mime"),
        ("#025", "25"),
        ("Nidoran♀", "nidoran-f"),
        ("Farfetch'd", "farfetchd"),
        ("Flabébé", "flabebe"),
    ],
)
def test_normalize_query(raw, expected):
    assert normalize_query(raw) == expected


def test_fetch_by_name_and_number(api):
    assert api.pokemon("Pikachu").id == 25
    assert api.pokemon("#25").name == "pikachu"
    assert api.pokemon("mr mime").types == ["psychic", "fairy"]


def test_second_request_comes_from_cache(api, server):
    api.pokemon("pikachu")
    n = len(server.calls)
    api.pokemon("pikachu")
    assert len(server.calls) == n


def test_not_found_suggests_similar_names(api):
    with pytest.raises(PokemonNotFound) as exc:
        api.pokemon("pikachuu")
    assert "pikachu" in exc.value.suggestions


def test_species_and_evolution(api):
    p = api.pokemon("gengar")
    chain = api.evolution_chain(api.species(p))
    assert [n.name for n in chain.walk()] == ["gastly", "haunter", "gengar"]


def test_sprite_is_downloaded_and_cached(api, server):
    p = api.pokemon("pikachu")
    data = api.sprite(p)
    assert data.startswith(b"\x89PNG")
    n = len(server.calls)
    assert api.sprite(p) == data
    assert len(server.calls) == n


def test_offline_mode_uses_only_cache(api):
    api.pokemon("pikachu")
    api.offline = True
    assert api.pokemon("pikachu").id == 25
    with pytest.raises(PokedexError):
        api.pokemon("charizard")
