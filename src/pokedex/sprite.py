"""Renderiza sprites PNG direto no terminal usando meios-blocos coloridos.

Cada caractere '▀' mostra dois pixels: a cor do texto pinta o pixel de cima e a
cor de fundo pinta o de baixo. Assim um sprite 96x96 vira algo em torno de 48
colunas x 24 linhas, sem precisar de nenhum protocolo de imagem especial.
"""

from __future__ import annotations

import io

from PIL import Image
from rich.color import Color
from rich.style import Style
from rich.text import Text

UPPER_HALF = "▀"
LOWER_HALF = "▄"
ALPHA_THRESHOLD = 128


def load_sprite(data: bytes, max_width: int = 48) -> Image.Image:
    """Abre o PNG, corta as bordas transparentes e reduz se for muito largo."""
    img = Image.open(io.BytesIO(data)).convert("RGBA")
    alpha = img.getchannel("A").point(lambda a: 255 if a >= ALPHA_THRESHOLD else 0)
    bbox = alpha.getbbox()
    if bbox:
        img = img.crop(bbox)
    if img.width > max_width:
        ratio = max_width / img.width
        size = (max_width, max(1, round(img.height * ratio)))
        # NEAREST preserva a cara de pixel art; LANCZOS borra os contornos.
        img = img.resize(size, Image.Resampling.NEAREST)
    return img


def silhouette(img: Image.Image, color: tuple[int, int, int] = (30, 30, 46)) -> Image.Image:
    """Versão 'Quem é esse Pokémon?': todo pixel visível vira uma cor só."""
    out = Image.new("RGBA", img.size, (0, 0, 0, 0))
    solid = Image.new("RGBA", img.size, (*color, 255))
    mask = img.getchannel("A").point(lambda a: 255 if a >= ALPHA_THRESHOLD else 0)
    out.paste(solid, mask=mask)
    return out


def _color(pixel: tuple[int, int, int, int]) -> Color | None:
    r, g, b, a = pixel
    return Color.from_rgb(r, g, b) if a >= ALPHA_THRESHOLD else None


def to_text(img: Image.Image) -> Text:
    """Converte a imagem em um `rich.Text` pronto para imprimir."""
    img = img.convert("RGBA")
    width, height = img.size
    px = img.load()
    text = Text(no_wrap=True, overflow="crop")

    for y in range(0, height, 2):
        for x in range(width):
            top = _color(px[x, y])
            bottom = _color(px[x, y + 1]) if y + 1 < height else None
            if top and bottom:
                text.append(UPPER_HALF, Style(color=top, bgcolor=bottom))
            elif top:
                text.append(UPPER_HALF, Style(color=top))
            elif bottom:
                text.append(LOWER_HALF, Style(color=bottom))
            else:
                text.append(" ")
        if y + 2 < height:
            text.append("\n")
    return text


def render(data: bytes | None, max_width: int = 48, hidden: bool = False) -> Text | None:
    if not data:
        return None
    try:
        img = load_sprite(data, max_width=max_width)
    except Exception:  # imagem corrompida no cache, formato estranho etc.
        return None
    if hidden:
        img = on_background(silhouette(img), QUIZ_BACKGROUND)
    return to_text(img)


QUIZ_BACKGROUND = (82, 160, 230)  # o azul clássico do "Quem é esse Pokémon?"


def on_background(img: Image.Image, color: tuple[int, int, int], margin: int = 2) -> Image.Image:
    """Coloca a imagem sobre um fundo sólido (com uma margem), como um cartão."""
    w, h = img.width + margin * 4, img.height + margin * 2
    canvas = Image.new("RGBA", (w, h + h % 2), (*color, 255))
    canvas.alpha_composite(img, (margin * 2, margin))
    return canvas
