"""Tudo que vira saída visual: cartões, barras de stats, tabelas e árvores."""

from __future__ import annotations

from rich import box
from rich.color import Color
from rich.columns import Columns
from rich.console import Group, RenderableType
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich.tree import Tree

from pokedex.models import STAT_NAMES_PT, EvolutionNode, Pokemon, Species, pretty_name
from pokedex.type_chart import (
    TYPE_COLORS,
    TYPES,
    defensive_profile,
    effectiveness,
    group_profile,
    type_name,
)

STAT_MAX = 255
BAR_WIDTH = 24


# ----------------------------------------------------------------- utilidades
def _readable_fg(hex_color: str) -> str:
    r, g, b = Color.parse(hex_color).get_truecolor()
    luminance = 0.299 * r + 0.587 * g + 0.114 * b
    return "black" if luminance > 150 else "white"


def type_badge(t: str) -> Text:
    color = TYPE_COLORS.get(t, "#888888")
    return Text(f" {type_name(t)} ", style=f"bold {_readable_fg(color)} on {color}")


def type_badges(types: list[str] | tuple[str, ...]) -> Text:
    return Text(" ").join(type_badge(t) for t in types)


def badge_columns(types: list[str]) -> Columns:
    """Badges que quebram de linha inteiros, sem cortar um tipo no meio."""
    return Columns([type_badge(t) for t in types], padding=(0, 1))


def stat_color(value: int) -> str:
    if value < 50:
        return "#F34444"
    if value < 80:
        return "#FF7F0F"
    if value < 100:
        return "#FFDD57"
    if value < 120:
        return "#A0E515"
    return "#23CD5E"


def bar(value: int, width: int = BAR_WIDTH, maximum: int = STAT_MAX) -> Text:
    filled = max(1, round(value / maximum * width)) if value else 0
    text = Text("█" * filled, style=stat_color(value))
    text.append("░" * (width - filled), style="grey23")
    return text


def format_multiplier(mult: float) -> str:
    return {0.25: "¼×", 0.5: "½×", 0: "0×"}.get(mult, f"{mult:g}×")


def multiplier_style(mult: float) -> str:
    if mult == 0:
        return "bold grey50"
    if mult >= 4:
        return "bold #FF3B3B"
    if mult >= 2:
        return "#FF8C42"
    if mult <= 0.25:
        return "bold #23CD5E"
    if mult < 1:
        return "#7BD389"
    return "grey35"


# ----------------------------------------------------------------- blocos
def stats_table(pokemon: Pokemon) -> Table:
    table = Table.grid(padding=(0, 1))
    table.add_column(justify="right", style="bold")
    table.add_column(justify="right", width=3)
    table.add_column()
    for stat in pokemon.stats:
        table.add_row(stat.label, str(stat.value), bar(stat.value))
    table.add_row("", "", "")
    table.add_row("Total", Text(str(pokemon.total), style="bold"), "")
    return table


def weakness_block(types: list[str]) -> Table:
    labels = {4: "Muito fraco", 2: "Fraco", 0.5: "Resiste", 0.25: "Resiste muito", 0: "Imune"}
    table = Table.grid(padding=(0, 1))
    table.add_column(justify="right")
    table.add_column()
    for mult, atk_types in group_profile(defensive_profile(types)).items():
        label = Text(
            f"{labels.get(mult, '')} {format_multiplier(mult)}", style=multiplier_style(mult)
        )
        # quebra em linhas de no máximo 4 tipos para caber no cartão
        rows = [atk_types[i : i + 4] for i in range(0, len(atk_types), 4)]
        for i, chunk in enumerate(rows):
            table.add_row(label if i == 0 else "", type_badges(chunk))
    return table


def evolution_block(root: EvolutionNode, current: str | None = None) -> RenderableType:
    def label(node: EvolutionNode) -> Text:
        is_current = node.name == current
        return Text(
            f"▶ {node.display_name}" if is_current else node.display_name,
            style="bold reverse" if is_current else "bold",
        )

    nodes = list(root.walk())
    if len(nodes) == 1:
        return Text("Não evolui.", style="dim italic")

    linear = all(len(n.evolves_to) <= 1 for n in nodes)
    if linear:
        line = label(root)
        node = root
        while node.evolves_to:
            node = node.evolves_to[0]
            line.append(f"  ─{node.condition or ''}─▶  ", style="dim")
            line.append_text(label(node))
        return line

    tree = Tree(label(root), guide_style="dim")

    def add(parent: Tree, node: EvolutionNode) -> None:
        for child in node.evolves_to:
            branch_label = label(child)
            branch_label.append(f"  ({child.condition})", style="dim")
            add(parent.add(branch_label), child)

    add(tree, root)
    return tree


def info_table(pokemon: Pokemon, species: Species | None) -> Table:
    table = Table.grid(padding=(0, 2))
    table.add_column(style="dim", justify="right")
    table.add_column()

    if species and species.genus:
        table.add_row("Espécie", species.genus)
    table.add_row("Tipo", type_badges(pokemon.types))
    table.add_row("Altura", f"{pokemon.height_m:.1f} m")
    table.add_row("Peso", f"{pokemon.weight_kg:.1f} kg")

    abilities = Text()
    for i, (name, hidden) in enumerate(pokemon.abilities):
        if i:
            abilities.append(", ")
        abilities.append(pretty_name(name), style="italic dim" if hidden else "")
        if hidden:
            abilities.append(" (oculta)", style="dim")
    table.add_row("Habilidades", abilities)

    if species:
        if species.generation:
            table.add_row("Geração", _roman(species.generation))
        if species.capture_rate is not None:
            table.add_row("Captura", f"{species.capture_rate}/255")
        tags = []
        if species.is_legendary:
            tags.append(Text(" ★ LENDÁRIO ", style="bold black on #FFD700"))
        if species.is_mythical:
            tags.append(Text(" ✦ MÍTICO ", style="bold white on #B455FF"))
        if tags:
            table.add_row("", Text(" ").join(tags))
    return table


def _roman(n: int) -> str:
    numerals = [(10, "X"), (9, "IX"), (5, "V"), (4, "IV"), (1, "I")]
    out = ""
    for value, letter in numerals:
        while n >= value:
            out += letter
            n -= value
    return out


def _section(title: str) -> Text:
    return Text(title.upper(), style="bold dim")


# ----------------------------------------------------------------- telas
def pokemon_card(
    pokemon: Pokemon,
    species: Species | None = None,
    evolution: EvolutionNode | None = None,
    sprite: Text | None = None,
    shiny: bool = False,
) -> Panel:
    header = Table.grid(padding=(0, 3))
    if sprite is not None:
        header.add_column(vertical="middle")
    header.add_column(vertical="middle")
    cells: list[RenderableType] = [sprite] if sprite is not None else []
    header.add_row(*cells, info_table(pokemon, species))

    parts: list[RenderableType] = [header]
    if species and species.flavor_text:
        parts += [Text(""), Text(f"“{species.flavor_text}”", style="italic")]

    lower = Table.grid(padding=(0, 4))
    lower.add_column()
    lower.add_column()
    lower.add_row(_section("Stats base"), _section("Defesa por tipo"))
    lower.add_row(stats_table(pokemon), weakness_block(pokemon.types))
    parts += [Text(""), lower]

    if evolution:
        parts += [Text(""), _section("Evolução"), evolution_block(evolution, pokemon.name)]

    title = Text(f" #{pokemon.id:04d}  {pokemon.display_name} ", style="bold")
    if shiny:
        title.append("✨ ", style="bold #FFD700")
    return Panel(
        Group(*parts),
        title=title,
        title_align="left",
        border_style=TYPE_COLORS.get(pokemon.types[0], "white"),
        box=box.ROUNDED,
        padding=(1, 2),
        expand=False,
    )


def best_attack_multiplier(attacker: Pokemon, defender: Pokemon) -> tuple[float, str]:
    """Melhor multiplicador que os tipos do atacante (STAB) causam no defensor."""
    best = (-1.0, attacker.types[0])
    for atk in attacker.types:
        mult = 1.0
        for d in defender.types:
            mult *= effectiveness(atk, d)
        if mult > best[0]:
            best = (mult, atk)
    return best


def compare_table(pokemons: list[Pokemon]) -> Table:
    table = Table(box=box.SIMPLE_HEAVY, show_lines=False, header_style="bold", pad_edge=False)
    table.add_column("", style="bold", justify="right")
    for p in pokemons:
        table.add_column(
            f"#{p.id:04d} {p.display_name}",
            justify="left",
            header_style=f"bold {TYPE_COLORS.get(p.types[0], 'white')}",
        )

    table.add_row("Tipo", *[type_badges(p.types) for p in pokemons])
    table.add_row("", *["" for _ in pokemons])

    for key, label in STAT_NAMES_PT.items():
        values = [p.stat(key) for p in pokemons]
        top = max(values)
        cells = []
        for v in values:
            winner = v == top and values.count(top) < len(values)
            cell = Text(f"{v:>3} ", style="bold" if winner else "")
            cell.append_text(bar(v, width=16))
            if winner:
                cell.append(" ★", style="bold #FFD700")
            cells.append(cell)
        table.add_row(label, *cells)

    totals = [p.total for p in pokemons]
    table.add_row(
        "Total",
        *[
            Text(
                f"{t:>3}" + (" ★" if t == max(totals) and totals.count(t) < len(totals) else ""),
                style="bold #FFD700" if t == max(totals) else "bold",
            )
            for t in totals
        ],
        end_section=True,
    )
    table.add_row("Altura", *[f"{p.height_m:.1f} m" for p in pokemons])
    table.add_row("Peso", *[f"{p.weight_kg:.1f} kg" for p in pokemons])
    return table


def matchup_lines(pokemons: list[Pokemon]) -> Group:
    lines: list[Text] = []
    for a in pokemons:
        for b in pokemons:
            if a is b:
                continue
            mult, atk = best_attack_multiplier(a, b)
            line = Text(f"{a.display_name} → {b.display_name}: ")
            line.append(format_multiplier(mult), style=multiplier_style(mult))
            line.append("  com golpes ")
            line.append_text(type_badge(atk))
            lines.append(line)
    return Group(*lines)


def team_table(team: list[Pokemon]) -> tuple[Table, list[str], list[str]]:
    """Tabela de fraquezas do time + lista de ameaças + buracos na cobertura ofensiva."""
    table = Table(box=box.SIMPLE_HEAD, header_style="bold", pad_edge=False)
    table.add_column("Ataque", justify="left")
    for p in team:
        table.add_column(p.display_name[:10], justify="center")
    table.add_column("Fracos", justify="center", style="#FF8C42")
    table.add_column("Resistem", justify="center", style="#7BD389")

    profiles = [defensive_profile(p.types) for p in team]
    threats: list[str] = []
    for atk in TYPES:
        mults = [prof[atk] for prof in profiles]
        weak = sum(m > 1 for m in mults)
        resist = sum(m < 1 for m in mults)
        cells = [
            Text(format_multiplier(m) if m != 1 else "·", style=multiplier_style(m)) for m in mults
        ]
        danger = weak >= max(2, len(team) // 2) and resist == 0
        if danger:
            threats.append(atk)
        name = type_badge(atk)
        if danger:
            name.append(" ⚠", style="bold #FF3B3B")
        table.add_row(
            name,
            *cells,
            str(weak) if weak else "",
            str(resist) if resist else "",
            style="on #3a1414" if danger else "",
        )

    stab_types = {t for p in team for t in p.types}
    uncovered = [d for d in TYPES if not any(effectiveness(a, d) > 1 for a in stab_types)]
    return table, threats, uncovered
