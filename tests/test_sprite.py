from conftest import sprite_png
from PIL import Image

from pokedex import sprite


def test_load_crops_transparent_border():
    img = sprite.load_sprite(sprite_png())
    assert img.size == (36, 42)


def test_load_downscales_wide_sprites():
    img = sprite.load_sprite(sprite_png(), max_width=18)
    assert img.width == 18
    assert img.height == 21


def test_to_text_uses_half_blocks_two_pixels_per_row():
    img = sprite.load_sprite(sprite_png())
    text = sprite.to_text(img)
    lines = text.plain.split("\n")
    assert len(lines) == 21  # 42 px de altura / 2
    assert all(len(line) == 36 for line in lines)
    assert set(text.plain) <= {"▀", "▄", " ", "\n"}


def test_silhouette_paints_every_visible_pixel_the_same_color():
    img = sprite.silhouette(sprite.load_sprite(sprite_png()))
    colors = {img.getpixel((x, y)) for x in range(img.width) for y in range(img.height)} - {
        (0, 0, 0, 0)
    }
    assert len(colors) == 1


def test_odd_height_does_not_crash():
    img = Image.new("RGBA", (3, 3), (255, 0, 0, 255))
    assert sprite.to_text(img).plain.count("\n") == 1


def test_render_handles_missing_or_invalid_data():
    assert sprite.render(None) is None
    assert sprite.render(b"isso nao e um png") is None
