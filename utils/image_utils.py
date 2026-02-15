import logging
import os
from PIL import Image, ImageDraw, ImageFont
from typing import List

logger = logging.getLogger(__name__)


def create_summary_image(
    sticker_path: str, text_lines: List[str], output_path: str, watermark: str = None
) -> str:
    """
    Overlays text on a sticker image.

    Args:
        sticker_path: Path to the input sticker image
        text_lines: List of strings to draw
        output_path: Path to save the result

    Returns:
        Path to the saved image or None if failed
    """
    try:
        # Open image
        with Image.open(sticker_path) as img:
            if img.mode != "RGBA":
                img = img.convert("RGBA")

            draw = ImageDraw.Draw(img)
            width, height = img.size
            font_size = int(height / 18)

            # --- Font Loading Helper ---
            def load_font(paths, size):
                """Завантажує шрифт з першого доступного шляху"""
                for path in paths:
                    try:
                        if os.path.exists(path):
                            logger.info(f"[FONT] Loading font: {path} (size={size})")
                            return ImageFont.truetype(path, size)
                    except Exception as e:
                        logger.warning(f"[FONT] Failed to load {path}: {e}")
                        continue

                # Якщо нічого не знайдено - критична помилка
                logger.error("[FONT] No fonts found! Image will have broken text.")
                # Повертаємо None замість load_default(), щоб побачити проблему
                raise FileNotFoundError(f"No fonts available from list: {paths}")

            # Збільшуємо базовий розмір для кращої читабельності
            font_size = int(height / 15)  # Було /18, тепер /15 (більше)

            # 1. Text Font (Prioritize reliable Cyrillic)
            text_font_paths = [
                # Linux fonts (Docker/Ubuntu priority) - БІЛЬШЕ ВАРІАНТІВ
                "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
                "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
                "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
                "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
                "/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf",
                "/usr/share/fonts/truetype/noto/NotoSans-Regular.ttf",
                "/usr/share/fonts/truetype/freefont/FreeSans.ttf",
                # Windows fonts
                "C:/Windows/Fonts/arial.ttf",
                "C:/Windows/Fonts/arialbd.ttf",
                "C:/Windows/Fonts/segoeui.ttf",
                "C:/Windows/Fonts/calibri.ttf",
            ]
            text_font = load_font(text_font_paths, font_size)

            # 2. Emoji Font (використовуємо той самий шрифт, але більший розмір)
            emoji_font_size = int(font_size * 1.4)  # Було 1.3, тепер 1.4 (ще більше)
            emoji_font = load_font(text_font_paths, emoji_font_size)
            # ---------------------

            # Create overlay
            overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
            overlay_draw = ImageDraw.Draw(overlay)

            # Calculate dimensions using dual-font logic
            total_text_height = 0
            line_spacing = int(font_size * 0.2)
            processed_lines = []  # Store (emoji_part, text_part, width, height, emoji_width)

            for line in text_lines:
                parts = line.split(" ", 1)
                emoji_part = None
                text_part = line

                # Heuristic: if first part is short (likely emoji) and we have space
                # Check known emojis or length
                if len(parts) == 2 and len(parts[0]) <= 2:
                    emoji_part = parts[0]
                    text_part = parts[1]

                if emoji_part:
                    # Measure separately
                    ebbox = draw.textbbox((0, 0), emoji_part, font=emoji_font)
                    tbbox = draw.textbbox((0, 0), text_part, font=text_font)

                    ewidth = ebbox[2] - ebbox[0]
                    eheight = ebbox[3] - ebbox[1]
                    twidth = tbbox[2] - tbbox[0]
                    theight = tbbox[3] - tbbox[1]

                    # Add extra spacing after emoji
                    spacing = int(font_size * 0.4)
                    line_width = ewidth + spacing + twidth
                    line_height = max(eheight, theight) if eheight > 0 else theight

                    processed_lines.append(
                        {
                            "type": "dual",
                            "emoji": emoji_part,
                            "text": text_part,
                            "w": line_width,
                            "h": line_height,
                            "ew": ewidth,
                            "spacing": spacing,
                        }
                    )
                else:
                    # Standard text
                    bbox = draw.textbbox((0, 0), line, font=text_font)
                    width_line = bbox[2] - bbox[0]
                    height_line = bbox[3] - bbox[1]
                    processed_lines.append(
                        {
                            "type": "single",
                            "text": line,
                            "w": width_line,
                            "h": height_line,
                        }
                    )

                total_text_height += processed_lines[-1]["h"] + line_spacing

            total_text_height -= line_spacing

            # Draw background
            # v3.0.0: Move text block lower (75% height instead of 50%)
            current_y = (height * 0.75) - (total_text_height / 2)
            padding = 20
            max_width = (
                max([line_data["w"] for line_data in processed_lines])
                if processed_lines
                else 0
            )

            bg_left = (width - max_width) / 2 - padding
            bg_top = current_y - padding
            bg_right = (width + max_width) / 2 + padding
            bg_bottom = current_y + total_text_height + padding

            overlay_draw.rectangle(
                [bg_left, bg_top, bg_right, bg_bottom], fill=(0, 0, 0, 180)
            )

            # Composite
            img = Image.alpha_composite(img, overlay)
            draw = ImageDraw.Draw(img)

            # Draw lines
            for line_data in processed_lines:
                x = (width - line_data["w"]) / 2

                # Helper to draw text with shadow
                def draw_text_with_shadow(draw_obj, pos, text, font, fill):
                    # Subtle shadow
                    shadow_pos = (pos[0] + 1, pos[1] + 1)
                    draw_obj.text(shadow_pos, text, font=font, fill=(0, 0, 0, 128))
                    draw_obj.text(pos, text, font=font, fill=fill)

                if line_data["type"] == "dual":
                    # Draw Emoji
                    draw_text_with_shadow(
                        draw,
                        (x, current_y),
                        line_data["emoji"],
                        font=emoji_font,
                        fill=(255, 255, 255, 255),
                    )
                    # Draw Text
                    text_x = x + line_data["ew"] + line_data["spacing"]
                    draw_text_with_shadow(
                        draw,
                        (text_x, current_y),
                        line_data["text"],
                        font=text_font,
                        fill=(255, 255, 255, 255),
                    )
                else:
                    draw_text_with_shadow(
                        draw,
                        (x, current_y),
                        line_data["text"],
                        font=text_font,
                        fill=(255, 255, 255, 255),
                    )

                current_y += line_data["h"] + line_spacing

            # Draw Watermark (Bottom-Right, subtle)
            if watermark:
                wm_font_size = max(12, int(font_size * 0.5))
                wm_font = load_font(text_font_paths, wm_font_size)

                # Create a fresh overlay for the watermark to ensure alpha works
                wm_overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
                wm_draw = ImageDraw.Draw(wm_overlay)

                wm_bbox = wm_draw.textbbox((0, 0), watermark, font=wm_font)
                wm_w = wm_bbox[2] - wm_bbox[0]
                wm_h = wm_bbox[3] - wm_bbox[1]

                # Position: bottom-right with 15px padding
                padding_cm = 15
                wm_x = width - wm_w - padding_cm
                wm_y = height - wm_h - padding_cm

                # Subtle dark background for the watermark itself to improve visibility
                wm_bg_padding = 4
                wm_draw.rectangle(
                    [
                        wm_x - wm_bg_padding,
                        wm_y - wm_bg_padding,
                        wm_x + wm_w + wm_bg_padding,
                        wm_y + wm_h + wm_bg_padding,
                    ],
                    fill=(0, 0, 0, 60),  # Very light dark tint
                )

                # Draw text with higher opacity on the overlay
                wm_draw.text(
                    (wm_x, wm_y), watermark, font=wm_font, fill=(255, 255, 255, 180)
                )

                # Merge the watermark overlay
                img = Image.alpha_composite(img, wm_overlay)

            img.save(output_path, "WEBP")
            return output_path

    except Exception as e:
        logger.error(f"Error creating summary image: {e}")
        return None
