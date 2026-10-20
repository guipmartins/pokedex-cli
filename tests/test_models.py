from conftest import CHAINS, POKEMON, SPECIES

from pokedex.models import EvolutionNode, Pokemon, Species, describe_evolution, pretty_name


def test_pokemon_from_api_converts_units():
    p = Pokemon.from_api(POKEMON["charizard"])
    assert p.id == 6
    assert p.types == ["fire", "flying"]
    assert p.height_m == 1.7
    assert p.weight_kg == 90.5
    assert p.total == 534
    assert p.stat("special-attack") == 109
    assert ("lightning-rod", True) in p.abilities


def test_species_cleans_flavor_text_and_reads_generation():
    s = Species.from_api(SPECIES["pikachu"])
    assert s.generation == 1
    assert s.genus == "Mouse Pokémon"
    assert "\n" not in s.flavor_text and "\x0c" not in s.flavor_text
    assert "  " not in s.flavor_text


def test_linear_evolution_chain():
    root = EvolutionNode.from_api(CHAINS[2])
    names = [n.name for n in root.walk()]
    assert names == ["charmander", "charmeleon", "charizard"]
    assert root.evolves_to[0].condition == "Nv. 16"


def test_branching_evolution_chain():
    root = EvolutionNode.from_api(CHAINS[67])
    assert len(root.evolves_to) == 3
    conditions = {c.name: c.condition for c in root.evolves_to}
    assert conditions["vaporeon"] == "Usar Water Stone"
    assert conditions["espeon"] == "com amizade alta de dia"


def test_describe_trade():
    assert describe_evolution({"trigger": {"name": "trade"}}) == "Troca"


def test_pretty_name():
    assert pretty_name("mr-mime") == "Mr Mime"
