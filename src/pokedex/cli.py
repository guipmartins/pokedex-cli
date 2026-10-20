"""Interface de linha de comando."""

from __future__ import annotations

import random as rnd
from contextlib import contextmanager
from typing import Annotated

import typer
from rich.console import Console
from rich.padding import Padding
from rich.panel import Panel
from rich.text import Text

from pokedex import __version__, render, sprite
from pokedex.api import MAX_POKEMON_ID, PokeAPI, PokedexError, PokemonNotFound, normalize_query
from pokedex.cache import DiskCache
from pokedex.models import Pokemon
from pokedex.type_chart import type_name

app = typer.Typer(
    name="pokedex",
    help="Uma Pokédex no seu terminal, com dados da PokeAPI. 🔴⚪",
    no_args_is_help=True,
    rich_markup_mode="rich",
    add_completion=False,
)
cache_app = typer.Typer(help="Gerencia o cache local.", no_args_is_help=True)
app.add_typer(cache_app, name="cache")

console = Console()
state = {"offline": False}

GENERATIONS: dict[int, tuple[int, int]] = {
    1: (1, 151), 2: (152, 251), 3: (252, 386), 4: (387, 493), 5: (494, 649),
    6: (650, 721), 7: (722, 809), 8: (810, 905), 9: (906, 1025),
}  # fmt: skip


def make_api() -> PokeAPI:
    """Ponto único de criação do cliente (os testes substituem esta função)."""
    return PokeAPI(offline=state["offline"])


@contextmanager
def friendly_errors():
    """Mostra erros conhecidos de forma amigável em vez de um traceback."""
    try:
        yield
    except PokemonNotFound as exc:
        msg = Text(f"✗ {exc}", style="bold red")
        if exc.suggestions:
            msg.append("\n  Você quis dizer: ", style="dim")
            msg.append(", ".join(exc.suggestions), style="bold yellow")
            msg.append("?", style="dim")
        console.print(msg)
        raise typer.Exit(1) from None
    except PokedexError as exc:
        console.print(Text(f"✗ {exc}", style="bold red"))
        raise typer.Exit(1) from None


def version_callback(value: bool) -> None:
    if value:
        console.print(f"pokedex-cli {__version__}")
        raise typer.Exit()


@app.callback()
def main(
    offline: Annotated[
        bool, typer.Option("--offline", help="Usa só o que já está no cache, sem internet.")
    ] = False,
    version: Annotated[
        bool,
        typer.Option(
            "--version", "-V", callback=version_callback, is_eager=True, help="Mostra a versão."
        ),
    ] = False,
) -> None:
    state["offline"] = offline


def show_pokemon(
    api: PokeAPI, query: str | int, shiny: bool, size: int, no_sprite: bool
) -> Pokemon:
    with console.status("[bold]Consultando a Pokédex...", spinner="dots"):
        pokemon = api.pokemon(query)
        species = api.species(pokemon)
        evolution = api.evolution_chain(species) if species else None
        art = None if no_sprite else sprite.render(api.sprite(pokemon, shiny=shiny), size)
    console.print(render.pokemon_card(pokemon, species, evolution, art, shiny=shiny))
    return pokemon


@app.command()
def show(
    pokemon: Annotated[str, typer.Argument(help="Nome ou número. Ex.: pikachu, 25, 'mr mime'")],
    shiny: Annotated[bool, typer.Option("--shiny", "-s", help="Mostra a versão shiny ✨")] = False,
    size: Annotated[
        int, typer.Option("--size", min=16, max=96, help="Largura máxima do sprite em colunas.")
    ] = 40,
    no_sprite: Annotated[bool, typer.Option("--no-sprite", help="Não desenha o sprite.")] = False,
) -> None:
    """Mostra o cartão completo de um Pokémon."""
    with friendly_errors(), make_api() as api:
        show_pokemon(api, pokemon, shiny, size, no_sprite)


@app.command()
def random(
    generation: Annotated[
        int | None, typer.Option("--gen", "-g", min=1, max=9, help="Sorteia só desta geração.")
    ] = None,
    shiny: Annotated[bool, typer.Option("--shiny", "-s")] = False,
) -> None:
    """Sorteia um Pokémon aleatório."""
    low, high = GENERATIONS[generation] if generation else (1, MAX_POKEMON_ID)
    with friendly_errors(), make_api() as api:
        show_pokemon(api, rnd.randint(low, high), shiny, 40, False)


@app.command()
def compare(
    pokemons: Annotated[list[str], typer.Argument(help="De 2 a 4 Pokémon.")],
) -> None:
    """Compara stats lado a lado e mostra quem leva vantagem de tipo."""
    if not 2 <= len(pokemons) <= 4:
        console.print("[bold red]✗ Informe de 2 a 4 Pokémon para comparar.")
        raise typer.Exit(1)
    with friendly_errors(), make_api() as api:
        with console.status("[bold]Carregando..."):
            team = [api.pokemon(p) for p in pokemons]
        console.print(render.compare_table(team))
        console.print(
            Panel(
                render.matchup_lines(team),
                title="Vantagem de tipo (STAB)",
                title_align="left",
                border_style="dim",
                expand=False,
            )
        )


@app.command()
def team(
    pokemons: Annotated[list[str], typer.Argument(help="De 1 a 6 Pokémon.")],
) -> None:
    """Analisa as fraquezas de um time e os buracos de cobertura ofensiva."""
    if not 1 <= len(pokemons) <= 6:
        console.print("[bold red]✗ Um time tem de 1 a 6 Pokémon.")
        raise typer.Exit(1)
    with friendly_errors(), make_api() as api, console.status("[bold]Montando o time..."):
        members = [api.pokemon(p) for p in pokemons]

    names = Text(" · ").join(
        Text(p.display_name, style="bold").append(" ").append_text(render.type_badges(p.types))
        for p in members
    )
    console.print(names, "\n")
    table, threats, uncovered = render.team_table(members)
    console.print(table)

    if threats:
        console.print("⚠  Ameaças ao time:", style="bold #FF3B3B")
        console.print(Padding(render.badge_columns(threats), (0, 0, 0, 3)))
        console.print("   Vários membros são fracos e ninguém resiste a esses tipos.", style="dim")
    else:
        console.print("✓  Nenhum tipo pega o time desprevenido. Boa defesa!", style="bold green")

    console.print()
    if uncovered:
        console.print("◎  Sem golpe super efetivo (STAB) contra:", style="bold #FFDD57")
        console.print(Padding(render.badge_columns(uncovered), (0, 0, 0, 3)))
    else:
        console.print(
            "◎  O STAB do time acerta todos os 18 tipos super efetivamente!", style="bold green"
        )


@app.command()
def quiz(
    rounds: Annotated[
        int, typer.Option("--rounds", "-r", min=1, max=50, help="Número de rodadas.")
    ] = 5,
    generation: Annotated[
        int, typer.Option("--gen", "-g", min=0, max=9, help="Geração (1-9), ou 0 para todas.")
    ] = 1,
) -> None:
    """Quem é esse Pokémon? Adivinhe pela silhueta."""
    low, high = GENERATIONS[generation] if generation else (1, MAX_POKEMON_ID)
    if high - low + 1 < rounds:
        rounds = high - low + 1
    ids = rnd.sample(range(low, high + 1), rounds)
    score = 0
    max_score = rounds * 3

    console.print(
        Panel.fit(
            "[bold]QUEM É ESSE POKÉMON?[/]\n[dim]3 tentativas por rodada · "
            "3/2/1 pontos · digite [bold]pular[/bold] para desistir[/]",
            border_style="#FFCB05",
        )
    )

    with friendly_errors(), make_api() as api:
        for n, pid in enumerate(ids, 1):
            with console.status("[bold]Escondendo o Pokémon..."):
                pokemon = api.pokemon(pid)
                species = api.species(pokemon)
                data = api.sprite(pokemon)
            answers = {pokemon.name, species.name if species else pokemon.name}

            console.rule(f"[bold]Rodada {n}/{rounds}")
            art = sprite.render(data, 40, hidden=True)
            console.print(art if art else Text("(sem sprite — só nas dicas!)", style="dim"))

            for attempt in range(1, 4):
                if attempt == 2:
                    hint = Text("💡 Dica: é do tipo ")
                    hint.append_text(render.type_badges(pokemon.types))
                    console.print(hint)
                elif attempt == 3:
                    first = pokemon.display_name[0]
                    size = len(species.name if species else pokemon.name)
                    console.print(f"💡 Dica: começa com [bold]{first}[/] e tem {size} letras.")

                guess = console.input(f"[bold cyan]Tentativa {attempt}/3 ›[/] ").strip()
                if normalize_query(guess) in {"pular", "skip"}:
                    break
                if normalize_query(guess) in answers or guess.strip("#") == str(pokemon.id):
                    points = 4 - attempt
                    score += points
                    console.print(f"[bold green]✓ Isso! +{points} ponto(s)[/]")
                    break
                console.print("[red]✗ Não é esse...[/]")

            console.print(
                Text(f"\nÉ o {pokemon.display_name}!", style="bold"),
                render.type_badges(pokemon.types),
            )
            revealed = sprite.render(data, 40)
            if revealed:
                console.print(revealed)

    pct = score / max_score
    verdict = (
        "Mestre Pokémon! 🏆"
        if pct >= 0.9
        else "Treinador de elite!"
        if pct >= 0.6
        else "Bom começo, continue treinando!"
        if pct >= 0.3
        else "O Professor Carvalho tem uma Pokédex nova pra você..."
    )
    console.print(
        Panel.fit(f"[bold]Pontuação: {score}/{max_score}[/]\n{verdict}", border_style="#FFCB05")
    )


@app.command(name="types")
def types_cmd(
    types: Annotated[list[str], typer.Argument(help="1 ou 2 tipos, em inglês ou português.")],
) -> None:
    """Mostra fraquezas e resistências de uma combinação de tipos."""
    from pokedex.type_chart import TYPE_NAMES_PT, TYPES

    lookup = {t: t for t in TYPES}
    lookup.update({normalize_query(pt): en for en, pt in TYPE_NAMES_PT.items()})
    resolved = []
    for t in types:
        key = normalize_query(t)
        if key not in lookup:
            valid = ", ".join(type_name(x) for x in TYPES)
            console.print(f"[bold red]✗ Tipo desconhecido: {t}[/]\n[dim]Válidos: {valid}")
            raise typer.Exit(1)
        resolved.append(lookup[key])
    if not 1 <= len(resolved) <= 2:
        console.print("[bold red]✗ Informe 1 ou 2 tipos.")
        raise typer.Exit(1)
    console.print(
        Panel(
            render.weakness_block(resolved),
            title=render.type_badges(resolved),
            title_align="left",
            border_style="dim",
            expand=False,
            padding=(1, 2),
        )
    )


@cache_app.command("info")
def cache_info() -> None:
    """Mostra onde fica o cache e quanto espaço ocupa."""
    files, size = DiskCache().stats()
    console.print(f"📁 {DiskCache().root}\n   {files} arquivos · {size / 1024:.1f} KB")


@cache_app.command("clear")
def cache_clear(
    yes: Annotated[bool, typer.Option("--yes", "-y", help="Não pede confirmação.")] = False,
) -> None:
    """Apaga todo o cache local."""
    if not yes and not typer.confirm("Apagar todo o cache?"):
        raise typer.Exit()
    DiskCache().clear()
    console.print("[green]✓ Cache apagado.")


if __name__ == "__main__":
    app()
