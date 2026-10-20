# 🔴⚪ pokedex-cli

Uma Pokédex completa direto no terminal, escrita em Python. Mostra o **sprite colorido** do Pokémon
desenhado com caracteres Unicode, stats, fraquezas, cadeia evolutiva, compara Pokémon, analisa
seu time e ainda tem o clássico **"Quem é esse Pokémon?"**.

Os dados vêm da [PokeAPI](https://pokeapi.co) e ficam em cache local, então a segunda consulta é
instantânea e funciona até offline.

<!-- Dica: grave um GIF com https://github.com/charmbracelet/vhs ou tire um print e coloque aqui -->
<!-- ![demo](docs/demo.gif) -->

## Funcionalidades

| Comando | O que faz |
|---|---|
| `pokedex show pikachu` | Cartão completo: sprite, tipos, espécie, altura/peso, habilidades, stats com barras, fraquezas e evolução |
| `pokedex show charizard --shiny` | Mesma coisa com o sprite shiny ✨ |
| `pokedex random --gen 3` | Sorteia um Pokémon (opcionalmente de uma geração) |
| `pokedex compare charizard blastoise venusaur` | Stats lado a lado (2 a 4), destaca o vencedor de cada stat e mostra a vantagem de tipo entre eles |
| `pokedex team garchomp gengar ...` | Analisa um time de até 6: tabela de fraquezas, tipos que ameaçam o time e buracos na cobertura ofensiva |
| `pokedex types fogo voador` | Fraquezas e resistências de qualquer combinação de tipos (aceita nomes em português ou inglês) |
| `pokedex quiz --rounds 10` | **Quem é esse Pokémon?** Silhueta no fundo azul, 3 tentativas com dicas, pontuação no final |
| `pokedex cache info` / `cache clear` | Mostra ou limpa o cache local |

Opções globais: `--offline` (usa só o cache) e `--version`.

A busca é tolerante: `Mr. Mime`, `mr mime`, `#122` e `122` funcionam igual, e se você errar o nome
ela sugere o mais parecido:

```
$ pokedex show charizrd
✗ Pokémon 'charizrd' não encontrado.
  Você quis dizer: charizard?
```

## Instalação

Requer Python 3.10+.

```bash
git clone https://github.com/<seu-usuario>/pokedex-cli.git
cd pokedex-cli
python -m venv .venv
# Windows: .venv\Scripts\activate   |   Linux/macOS: source .venv/bin/activate
pip install -e .
pokedex show pikachu
```

> **Windows:** use o [Windows Terminal](https://aka.ms/terminal) para ter cores 24-bit nos sprites.
> O `cmd.exe` antigo funciona, mas com menos cores.

## Como funciona

```
src/pokedex/
├── cli.py         # comandos (Typer) e fluxo do quiz
├── api.py         # cliente HTTP da PokeAPI, normalização de nomes e sugestões
├── cache.py       # cache em disco com escrita atômica
├── models.py      # dataclasses + parsing do JSON da API
├── type_chart.py  # tabela de efetividade dos 18 tipos (offline)
├── sprite.py      # PNG -> texto colorido no terminal
└── render.py      # cartões, tabelas e barras com Rich
```

**Sprites no terminal.** Cada caractere `▀` representa *dois* pixels: a cor do texto pinta o de cima
e a cor de fundo pinta o de baixo. O PNG é recortado nas bordas transparentes, reduzido com
`NEAREST` (para manter a cara de pixel art) e convertido linha a linha. A silhueta do quiz é o mesmo
sprite com todos os pixels visíveis pintados de uma cor só sobre o fundo azul.

**Fraquezas sem chamadas extras.** A tabela de tipos da geração 6+ está no código, então o cálculo
de multiplicadores (inclusive 4× e ¼× em tipos duplos) é local e testado.

**Cache.** Cada URL vira um arquivo (hash SHA-1) em `~/.cache/pokedex-cli` (ou
`%LOCALAPPDATA%\pokedex-cli` no Windows; dá para mudar com `POKEDEX_CACHE_DIR`). A escrita é feita
num arquivo temporário e renomeada, para nunca deixar JSON pela metade.

## Testes

```bash
pip install -e ".[dev]"
pytest
ruff check .
```

Os testes **não acessam a internet**: o cliente real roda de ponta a ponta, mas com um
`httpx.MockTransport` que responde no formato da PokeAPI. O GitHub Actions roda tudo em Linux e
Windows com Python 3.10 a 3.13.

## Créditos

Dados e sprites: [PokeAPI](https://pokeapi.co). Pokémon e nomes relacionados são marcas da
Nintendo/Game Freak/The Pokémon Company; este é um projeto de fã, sem fins comerciais.

Licença MIT.
