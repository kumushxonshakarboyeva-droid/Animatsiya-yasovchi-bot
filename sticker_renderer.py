"""
Sticker Renderer & Image Processor Module (SVG-free for Render)
"""
from __future__ import annotations

import math
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

# ─────────────────────────────────────────────────────────────────────────────
# Presets & Options
# ─────────────────────────────────────────────────────────────────────────────
FONTS = {
    "fredoka": {"label": "🎈 Fredoka (Bubble)", "path": "fonts/Fredoka-Bold.ttf"},
    "impact": {"label": "💥 Impact (Meme)", "path": "fonts/Impact.ttf"},
    "bangers": {"label": "🦸 Bangers (Comic)", "path": "fonts/Bangers-Regular.ttf"},
    "caveat": {"label": "✍️ Caveat (Hand)", "path": "fonts/Caveat-Bold.ttf"},
}

COLORS = {
    "purple": {"label": "🟣 Electric Purple", "fill": "#8A2BE2"},
    "red": {"label": "🔴 Vibrant Red", "fill": "#FF2A55"},
    "yellow": {"label": "🟡 Cyber Yellow", "fill": "#FFD700"},
    "cyan": {"label": "🌐 Neon Cyan", "fill": "#00F5FF"},
    "mint": {"label": "🌿 Mint Green", "fill": "#98FF98"},
    "white": {"label": "⚪ Clean White", "fill": "#FFFFFF"},
}

# ─────────────────────────────────────────────────────────────────────────────
# 360 Spin & Image Processing Functions
# ─────────────────────────────────────────────────────────────────────────────
def crop_to_circle(image: Image.Image) -> Image.Image:
    """Rasmni mukammal yumaloq (circle) shaklda qirqib beradi."""
    image = image.convert("RGBA")
    size = min(image.size)
    
    left = (image.width - size) // 2
    top = (image.height - size) // 2
    image = image.crop((left, top, left + size, top + size))
    
    mask = Image.new("L", (size, size), 0)
    draw = ImageDraw.Draw(mask)
    draw.ellipse((0, 0, size, size), fill=255)
    
    result = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    result.paste(image, (0, 0), mask=mask)
    return result

def render_360_spin_sticker(image_path: Path, output_dir: Path, frames_count: int = 30) -> Path:
    """Yumaloq rasmni 360° 3D Spin qilib WebP animatsion stiker ko'rinishida saqlaydi."""
    orig_img = Image.open(image_path)
    circle_img = crop_to_circle(orig_img)
    
    target_size = (512, 512)
    circle_img = circle_img.resize(target_size, Image.Resampling.LANCZOS)
    
    frames = []
    for i in range(frames_count):
        angle = (360 / frames_count) * i
        scale_x = abs(math.cos(math.radians(angle)))
        new_width = max(1, int(target_size[0] * scale_x))
        
        resized_frame = circle_img.resize((new_width, target_size[1]), Image.Resampling.LANCZOS)
        
        frame = Image.new("RGBA", target_size, (0, 0, 0, 0))
        offset_x = (target_size[0] - new_width) // 2
        frame.paste(resized_frame, (offset_x, 0), mask=resized_frame)
        frames.append(frame)

    output_path = output_dir / "spin_sticker.webp"
    frames[0].save(
        output_path,
        save_all=True,
        append_images=frames[1:],
        duration=40,
        loop=0,
        transparency=0,
        disposal=2
    )
    return output_path

# ─────────────────────────────────────────────────────────────────────────────
# Text & Custom Emoji Renderers
# ─────────────────────────────────────────────────────────────────────────────
def render_sticker(
    text: str,
    output_dir: Path,
    font_key: str,
    color_val: str,
    animation: str = "bounce"
) -> Path:
    """Matnli 512x512 stiker yaratadi."""
    img = Image.new("RGBA", (512, 512), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    
    fill = COLORS.get(color_val, {}).get("fill", color_val)
    font_path = FONTS.get(font_key, {}).get("path", "arial.ttf")
    
    try:
        font = ImageFont.truetype(font_path, 60)
    except IOError:
        font = ImageFont.load_default()

    draw.text((256, 256), text, fill=fill, anchor="mm", font=font)
    
    output_path = output_dir / "text_sticker.webp"
    img.save(output_path, "WEBP")
    return output_path

def render_custom_emoji(
    content: str,
    output_dir: Path,
    font_key: str,
    color_val: str,
    animation: str = "bounce"
) -> Path:
    """100x100 o'lchamdagi Custom Emoji yaratadi."""
    img = Image.new("RGBA", (100, 100), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    
    fill = COLORS.get(color_val, {}).get("fill", color_val)
    font_path = FONTS.get(font_key, {}).get("path", "arial.ttf")
    
    try:
        font = ImageFont.truetype(font_path, 40)
    except IOError:
        font = ImageFont.load_default()

    draw.text((50, 50), content, fill=fill, anchor="mm", font=font)
    
    output_path = output_dir / "custom_emoji.webp"
    img.save(output_path, "WEBP")
    return output_path
