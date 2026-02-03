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
            # Convert to RGBA if not already
            if img.mode != "RGBA":
                img = img.convert("RGBA")

            # Create a drawing context
            draw = ImageDraw.Draw(img)

            # Determine font size based on image size
            width, height = img.size
            font_size = int(height / 10)  # Larger font (was /15)

            # Try to load a font with Cyrillic support
            font_paths = [
                "C:/Windows/Fonts/arial.ttf",
                "C:/Windows/Fonts/segoeui.ttf",
                "C:/Windows/Fonts/calibri.ttf",
                "arial.ttf",
            ]

            font = None
            for path in font_paths:
                try:
                    if os.path.exists(path):
                        font = ImageFont.truetype(path, font_size)
                        break
                    elif path == "arial.ttf":  # Try system lookup for simple name
                        font = ImageFont.truetype(path, font_size)
                        break
                except IOError:
                    continue

            if font is None:
                # Fallback to default (likely won't support Cyrillic)
                font = ImageFont.load_default()
                logger.warning("No suitable font found, using default.")

            # Create overlay for better text visibility
            overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
            overlay_draw = ImageDraw.Draw(overlay)

            # Calculate total text height
            total_text_height = 0
            line_spacing = int(font_size * 0.2)

            # Get text bounding boxes
            text_dims = []
            for line in text_lines:
                bbox = draw.textbbox((0, 0), line, font=font)
                text_width = bbox[2] - bbox[0]
                text_height = bbox[3] - bbox[1]
                text_dims.append((text_width, text_height))
                total_text_height += text_height + line_spacing

            total_text_height -= line_spacing  # Remove last spacing

            # Center the text block vertically and horizontally
            current_y = (height - total_text_height) / 2

            # Draw distinct background rectangle for text
            padding = 20
            max_width = max([d[0] for d in text_dims]) if text_dims else 0
            bg_left = (width - max_width) / 2 - padding
            bg_top = current_y - padding
            bg_right = (width + max_width) / 2 + padding
            bg_bottom = current_y + total_text_height + padding

            overlay_draw.rectangle(
                [bg_left, bg_top, bg_right, bg_bottom], fill=(0, 0, 0, 160)
            )

            # Composite overlay
            img = Image.alpha_composite(img, overlay)
            draw = ImageDraw.Draw(img)  # Re-create draw for final image

            # Draw text
            for i, line in enumerate(text_lines):
                if i < len(text_dims):
                    text_width, text_height = text_dims[i]
                    x = (width - text_width) / 2
                    draw.text(
                        (x, current_y), line, font=font, fill=(255, 255, 255, 255)
                    )
                    current_y += text_height + line_spacing

            # Save result
            img.save(output_path, "PNG")
            return output_path

    except Exception as e:
        logger.error(f"Error creating summary image: {e}")
        return None
