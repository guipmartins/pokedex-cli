import pytest

from pokedex.type_chart import _CHART, TYPES, defensive_profile, effectiveness, group_profile


def test_chart_only_uses_known_types():
    assert set(_CHART) == set(TYPES)
    for row in _CHART.values():
        assert set(row) <= set(TYPES)
        assert set(row.values()) <= {0, 0.5, 2}


@pytest.mark.parametrize(
    ("atk", "dfn", "expected"),
    [
        ("water", "fire", 2),
        ("fire", "water", 0.5),
        ("electric", "ground", 0),
        ("normal", "ghost", 0),
        ("dragon", "fairy", 0),
        ("fairy", "dragon", 2),
        ("psychic", "dark", 0),
        ("grass", "grass", 0.5),
        ("normal", "normal", 1),
    ],
)
def test_single_type_effectiveness(atk, dfn, expected):
    assert effectiveness(atk, dfn) == expected


def test_dual_type_stacks_multipliers():
    charizard = defensive_profile(["fire", "flying"])
    assert charizard["rock"] == 4
    assert charizard["ground"] == 0
    assert charizard["grass"] == 0.25
    assert charizard["water"] == 2


def test_gengar_immunities():
    gengar = defensive_profile(["ghost", "poison"])
    assert gengar["normal"] == 0
    assert gengar["fighting"] == 0
    assert gengar["psychic"] == 2


def test_group_profile_hides_neutral_and_sorts_desc():
    groups = group_profile(defensive_profile(["fire", "flying"]))
    assert list(groups) == sorted(groups, reverse=True)
    assert 1.0 not in groups
    assert groups[4] == ["rock"]
