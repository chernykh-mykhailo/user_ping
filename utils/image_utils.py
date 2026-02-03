import logging
import os
from PIL import Image, ImageDraw, ImageFont
from typing import List

logger = logging.getLogger(__name__)


def create_summary_image(
    sticker_path: str, text_lines: List[str], output_path: str
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
                for path in paths:
                    try:
                        if os.path.exists(path):
                            return ImageFont.truetype(path, size)
                        elif path == "arial.ttf":
                            return ImageFont.truetype(path, size)
                    except IOError:
                        continue
                return ImageFont.load_default()

            # 1. Text Font (Prioritize reliable Cyrillic)
            text_font_paths = [
                "C:/Windows/Fonts/arial.ttf",
                "C:/Windows/Fonts/segoeui.ttf",
                "C:/Windows/Fonts/calibri.ttf",
                "arial.ttf",
                "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            ]
            text_font = load_font(text_font_paths, font_size)

            # 2. Emoji Font (Prioritize Symbols)
            emoji_font_paths = [
                "C:/Windows/Fonts/seguisym.ttf",  # Segoe UI Symbol
                "C:/Windows/Fonts/seguiemj.ttf",  # Segoe UI Emoji
                "C:/Windows/Fonts/segoeui.ttf",
            ]
            emoji_font = load_font(emoji_font_paths, font_size)
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
            current_y = (height - total_text_height) / 2
            padding = 20
            max_width = max([l["w"] for l in processed_lines]) if processed_lines else 0

            bg_left = (width - max_width) / 2 - padding
            bg_top = current_y - padding
            bg_right = (width + max_width) / 2 + padding
            bg_bottom = current_y + total_text_height + padding

            overlay_draw.rectangle(
                [bg_left, bg_top, bg_right, bg_bottom], fill=(0, 0, 0, 160)
            )

            # Composite
            img = Image.alpha_composite(img, overlay)
            draw = ImageDraw.Draw(img)

            # Draw lines
            for line_data in processed_lines:
                x = (width - line_data["w"]) / 2

                if line_data["type"] == "dual":
                    # Draw Emoji with Emoji Font
                    draw.text(
                        (x, current_y),
                        line_data["emoji"],
                        font=emoji_font,
                        fill=(255, 255, 255, 255),
                    )
                    # Draw Text with Text Font
                    text_x = x + line_data["ew"] + line_data["spacing"]
                    draw.text(
                        (text_x, current_y),
                        line_data["text"],
                        font=text_font,
                        fill=(255, 255, 255, 255),
                    )
                else:
                    draw.text(
                        (x, current_y),
                        line_data["text"],
                        font=text_font,
                        fill=(255, 255, 255, 255),
                    )

                current_y += line_data["h"] + line_spacing

            img.save(output_path, "PNG")
            return output_path

    except Exception as e:
        logger.error(f"Error creating summary image: {e}")
        return None
