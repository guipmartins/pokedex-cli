# pokedex-cli

Uma Pokédex feita em Python, em duas versões:

- **No navegador:** um aparelho de Pokédex com a arte oficial em HD, o grito de cada Pokémon e uma
  **IA** que narra a entrada em português, responde perguntas e **identifica Pokémon por foto**.
- **No terminal:** sprites coloridos desenhados com caracteres Unicode, comparação de stats,
  análise de time e o quiz **"Quem é esse Pokémon?"**.

Os dados vêm da [PokeAPI](https://pokeapi.co) e ficam em cache local, então a segunda consulta é
instantânea e funciona até offline.

<!-- Coloque aqui um print da versão web: ![Pokédex no navegador](docs/web.png) -->

## Começando

Requer Python 3.10+.

```bash
git clone https://github.com/<seu-usuario>/pokedex-cli.git
cd pokedex-cli
python -m venv .venv
# Windows: .venv\Scripts\activate   |   Linux/macOS: source .venv/bin/activate
pip install -e .
pokedex web
```

O navegador abre sozinho em `http://localhost:8000`.

### Ligando a IA (opcional)

Sem chave, tudo funciona, menos a aba **IA** e a identificação por foto. Para ligar, copie
`.env.example` para `.env` e preencha **uma** das chaves:

```env
ANTHROPIC_API_KEY=sk-ant-...
# ou
OPENAI_API_KEY=sk-...
```

Reinicie o `pokedex web`. O `.env` está no `.gitignore`, então a chave não vai para o GitHub.
Para trocar o modelo, use `AI_MODEL` (padrão: `claude-haiku-5-5` ou `gpt-6-luna`).

## Versão web

| Recurso | Como usar |
|---|---|
| Arte oficial em HD | Aparece na tela da esquerda, com uma varredura de leitura a cada Pokémon |
| Navegação | Botões ◀ ▶ ou as setas do teclado; busca com autocompletar; dado para sortear |
| Shiny | Botão de estrela alterna a arte shiny |
| Grito | Botão de som toca o grito oficial |
| Dados, Status, Defesa, Evolução | Abas da tela da direita; clique numa evolução para ir até ela |
| Narrar entrada (IA) | A IA escreve a entrada da Pokédex em português e o navegador lê em voz alta |
| Pergunte à Pokédex (IA) | Chat sobre o Pokémon na tela: estratégia, curiosidades, matchups |
| Identificar por foto (IA) | Botão da câmera ou arraste uma imagem para a tela: foto, print, desenho ou pelúcia |

Cada Pokémon tem link próprio (`http://localhost:8000/#gengar`). A API JSON fica documentada em
`/api/docs`.

## Versão de terminal

| Comando | O que faz |
|---|---|
| `pokedex show pikachu` | Cartão completo com sprite, stats, fraquezas e evolução |
| `pokedex show charizard --shiny` | Mesma coisa com o sprite shiny |
| `pokedex random --gen 3` | Sorteia um Pokémon (opcionalmente de uma geração) |
| `pokedex compare charizard blastoise` | Stats lado a lado (2 a 4) e vantagem de tipo entre eles |
| `pokedex team garchomp gengar ...` | Fraquezas de um time de até 6 e buracos na cobertura ofensiva |
| `pokedex types fogo voador` | Fraquezas de uma combinação de tipos (português ou inglês) |
| `pokedex quiz --rounds 10` | Quem é esse Pokémon? Silhueta, 3 tentativas com dicas e pontuação |
| `pokedex cache info` / `cache clear` | Mostra ou limpa o cache local |

A busca é tolerante: `Mr. Mime`, `mr mime`, `#122` e `122` funcionam igual, e um nome errado
recebe sugestão ("Você quis dizer: charizard?").

## Como funciona

```
src/pokedex/
├── api.py         # cliente da PokeAPI, normalização de nomes e sugestões
├── cache.py       # cache em disco com escrita atômica
├── models.py      # dataclasses + parsing do JSON da API
├── type_chart.py  # tabela de efetividade dos 18 tipos (offline)
├── ai.py          # Claude ou OpenAI via HTTP: narração, perguntas e visão
├── web/
│   ├── server.py  # FastAPI: API JSON + página
│   └── static/    # HTML, CSS e JS do aparelho (sem framework)
├── cli.py         # comandos de terminal (Typer)
├── sprite.py      # PNG -> texto colorido no terminal
└── render.py      # cartões e tabelas do terminal (Rich)
```

**IA com dados reais.** A IA não "lembra" stats de cabeça: o servidor manda junto os fatos da PokeAPI
(tipos, fraquezas calculadas, stats, habilidades) e o prompt pede para narrar a partir deles. As
narrações ficam em cache, então cada Pokémon custa uma chamada só. As duas APIs são chamadas direto
com `httpx`, sem SDK, e o provedor é escolhido pela chave presente no `.env`.

**Identificação por foto.** A imagem é reduzida para no máximo 1024 px e convertida para JPEG antes
de ir para o modelo de visão (menos custo). A resposta vem em JSON e o nome passa pela PokeAPI; se
não bater exatamente, a página sugere os nomes parecidos.

**Sprites no terminal.** Cada caractere `▀` representa dois pixels: a cor do texto pinta o de cima e
a cor de fundo o de baixo.

## Testes

```bash
pip install -e ".[dev]"
pytest
ruff check .
```

Os testes **não acessam a internet nem gastam créditos de IA**: os clientes reais rodam de ponta a
ponta com um `httpx.MockTransport` que responde no formato da PokeAPI, da Anthropic e da OpenAI. O
GitHub Actions roda tudo em Linux e Windows com Python 3.10 a 3.13.

## Créditos

Dados e imagens: [PokeAPI](https://pokeapi.co). Pokémon e nomes relacionados são marcas da
Nintendo, Game Freak e The Pokémon Company; este é um projeto de fã, sem fins comerciais. O visual do
aparelho é original.

Licença MIT.
