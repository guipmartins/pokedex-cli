from typer.testing import CliRunner

from pokedex.cli import app

runner = CliRunner()


def run(*args, input=None):
    result = runner.invoke(app, list(args), input=input, env={"COLUMNS": "120"})
    return result


def test_show_card(cli_api):
    result = run("show", "pikachu")
    assert result.exit_code == 0, result.output
    out = result.output
    assert "#0025" in out and "Pikachu" in out
    assert "Elétrico" in out
    assert "Mouse Pokémon" in out
    assert "Pichu" in out and "Raichu" in out  # cadeia evolutiva
    assert "Terrestre" in out  # fraqueza a Terrestre
    assert "▀" in out  # sprite desenhado


def test_show_branching_evolution(cli_api):
    result = run("show", "eevee", "--no-sprite")
    assert result.exit_code == 0, result.output
    for name in ("Vaporeon", "Jolteon", "Espeon"):
        assert name in result.output
    assert "▀" not in result.output


def test_show_unknown_pokemon_suggests(cli_api):
    result = run("show", "charizrd")
    assert result.exit_code == 1
    assert "Você quis dizer" in result.output
    assert "charizard" in result.output


def test_compare(cli_api):
    result = run("compare", "charizard", "blastoise")
    assert result.exit_code == 0, result.output
    assert "Charizard" in result.output and "Blastoise" in result.output
    assert "★" in result.output
    assert "Blastoise → Charizard: 2×" in result.output


def test_compare_needs_two(cli_api):
    assert run("compare", "pikachu").exit_code == 1


def test_team_analysis(cli_api):
    result = run("team", "charizard", "gengar", "pikachu")
    assert result.exit_code == 0, result.output
    assert "Ameaças" in result.output or "Nenhum tipo" in result.output
    assert "STAB" in result.output


def test_types_command_accepts_portuguese(cli_api):
    result = run("types", "fogo", "voador")
    assert result.exit_code == 0, result.output
    assert "4×" in result.output and "Pedra" in result.output


def test_quiz_correct_guess(cli_api, monkeypatch):
    import pokedex.cli as cli

    monkeypatch.setattr(cli.rnd, "sample", lambda pop, k: [25])
    result = run("quiz", "--rounds", "1", input="pikachu\n")
    assert result.exit_code == 0, result.output
    assert "+3 ponto" in result.output
    assert "Pontuação: 3/3" in result.output


def test_quiz_hints_then_skip(cli_api, monkeypatch):
    import pokedex.cli as cli

    monkeypatch.setattr(cli.rnd, "sample", lambda pop, k: [94])
    result = run("quiz", "--rounds", "1", input="mew\npular\n")
    assert result.exit_code == 0, result.output
    assert "Dica" in result.output
    assert "É o Gengar" in result.output
    assert "Pontuação: 0/3" in result.output


def test_version():
    result = run("--version")
    assert result.exit_code == 0
    assert "pokedex-cli" in result.output
