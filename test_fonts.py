#!/usr/bin/env python3
"""
Тестовий скрипт для перевірки доступності шрифтів
Запустіть у Docker контейнері: docker exec -it ping_bot python test_fonts.py
"""

import os
from PIL import ImageFont

# Список шрифтів для перевірки
font_paths = [
    # Linux fonts
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    "/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf",
    "/usr/share/fonts/truetype/noto/NotoSans-Regular.ttf",
    "/usr/share/fonts/truetype/freefont/FreeSans.ttf",
    "/usr/share/fonts/truetype/ubuntu/Ubuntu-R.ttf",
    # Windows fonts
    "C:/Windows/Fonts/arial.ttf",
    "C:/Windows/Fonts/arialbd.ttf",
    "C:/Windows/Fonts/segoeui.ttf",
    "C:/Windows/Fonts/calibri.ttf",
]

print("=" * 60)
print("ПЕРЕВІРКА ДОСТУПНОСТІ ШРИФТІВ")
print("=" * 60)

found_fonts = []
missing_fonts = []

for path in font_paths:
    exists = os.path.exists(path)
    status = "✅ ЗНАЙДЕНО" if exists else "❌ ВІДСУТНІЙ"
    print(f"{status}: {path}")

    if exists:
        # Спробуємо завантажити
        try:
            font = ImageFont.truetype(path, 20)
            print(f"   └─ Завантажено успішно (розмір 20)")
            found_fonts.append(path)
        except Exception as e:
            print(f"   └─ ПОМИЛКА завантаження: {e}")
            missing_fonts.append(path)
    else:
        missing_fonts.append(path)

print("\n" + "=" * 60)
print(f"ПІДСУМОК: {len(found_fonts)} знайдено, {len(missing_fonts)} відсутні")
print("=" * 60)

if found_fonts:
    print("\n✅ РОБОЧІ ШРИФТИ:")
    for font in found_fonts:
        print(f"  - {font}")
else:
    print("\n❌ ЖОДНОГО РОБОЧОГО ШРИФТУ НЕ ЗНАЙДЕНО!")
    print("   Встановіть шрифти командою:")
    print("   apt-get update && apt-get install -y fonts-dejavu fonts-liberation")

# Тест кирилиці
if found_fonts:
    print("\n" + "=" * 60)
    print("ТЕСТ КИРИЛИЦІ")
    print("=" * 60)

    test_text = "Привіт! 👋 Виклик завершено!"
    font_path = found_fonts[0]

    try:
        from PIL import Image, ImageDraw

        img = Image.new("RGB", (400, 100), color=(255, 255, 255))
        draw = ImageDraw.Draw(img)
        font = ImageFont.truetype(font_path, 24)

        draw.text((10, 10), test_text, font=font, fill=(0, 0, 0))

        output_path = "/tmp/test_cyrillic.png"
        img.save(output_path)

        print(f"✅ Тест пройдено! Зображення збережено: {output_path}")
        print(f"   Використаний шрифт: {font_path}")
        print(f"   Текст: {test_text}")

    except Exception as e:
        print(f"❌ Помилка при тесті кирилиці: {e}")
