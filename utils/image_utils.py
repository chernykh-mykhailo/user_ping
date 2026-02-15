import logging
import os
from PIL import Image, ImageDraw, ImageFont
from pilmoji import Pilmoji
from pilmoji.source import TwitterEmojiSource
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

            width, height = img.size

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
                raise FileNotFoundError(f"No fonts available from list: {paths}")

            # Збільшуємо базовий розмір для кращої читабельності
            font_size = int(height / 15)  # Було /18, тепер /15 (більше)

            # Завантажуємо шрифт для тексту (pilmoji використає його для тексту, а емодзі візьме з Twemoji)
            text_font_paths = [
                # Linux fonts (Docker/Ubuntu priority)
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
            # ---------------------

            # Create overlay
            overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
            overlay_draw = ImageDraw.Draw(overlay)

            # Використовуємо Pilmoji для вимірювання тексту з емодзі
            with Pilmoji(img, source=TwitterEmojiSource) as pilmoji:
                # Calculate dimensions
                total_text_height = 0
                line_spacing = int(font_size * 0.2)
                processed_lines = []

                for line in text_lines:
                    # Вимірюємо текст з емодзі за допомогою pilmoji
                    bbox = pilmoji.getsize(line, text_font)
                    line_width = bbox[0]
                    line_height = bbox[1]

                    processed_lines.append(
                        {
                            "text": line,
                            "w": line_width,
                            "h": line_height,
                        }
                    )

                    total_text_height += line_height + line_spacing

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

                # Створюємо новий Pilmoji для фінального рендерингу
                with Pilmoji(img, source=TwitterEmojiSource) as pilmoji_final:
                    # Draw lines з емодзі
                    for line_data in processed_lines:
                        x = (width - line_data["w"]) / 2

                        # Рендеримо текст з емодзі (pilmoji автоматично додає тінь)
                        # Спочатку тінь
                        pilmoji_final.text(
                            (x + 1, current_y + 1),
                            line_data["text"],
                            font=text_font,
                            fill=(0, 0, 0, 128),
                            emoji_scale_factor=1.2,  # Емодзі трохи більші
                        )
                        # Потім основний текст
                        pilmoji_final.text(
                            (x, current_y),
                            line_data["text"],
                            font=text_font,
                            fill=(255, 255, 255, 255),
                            emoji_scale_factor=1.2,
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
