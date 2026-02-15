import logging
from typing import Optional
from aiogram import Bot
from aiogram.types import Sticker, InputSticker
from aiogram.exceptions import TelegramBadRequest

from core import ChatRepository


logger = logging.getLogger(__name__)


class EmojiPackService:
    """
    Сервіс для автоматичного керування емодзі-паками бота.
    v2.10.0: Створює та наповнює власні набори (Bot-Owned Packs)
    """

    def __init__(self, bot: Bot, chat_repo: ChatRepository):
        self.bot = bot
        self.chat_repo = chat_repo
        self.me = None  # Буде завантажено в ensure_init

    async def ensure_init(self):
        """Гарантує, що дані бота завантажені"""
        if not self.me:
            self.me = await self.bot.get_me()

    async def get_or_create_active_pack(self) -> dict:
        """Знаходить або створює активний емодзі-пак"""
        await self.ensure_init()

        pack = self.chat_repo.emoji_packs.get_active_pack()
        if pack:
            # v2.10.9: Перевіряємо, чи пак належить поточному боту
            if pack["name"].lower().endswith(f"_by_{self.me.username}".lower()):
                return pack
            logger.warning(
                f"Active pack {pack['name']} doesn't match bot {self.me.username}. Ignoring."
            )

        # Створюємо новий пак
        packs = self.chat_repo.emoji_packs.get_packs()
        version = len(packs) + 1

        # Назва паку: pack_v1_by_botusername (вимога Telegram)
        pack_name = f"pack_v{version}_by_{self.me.username}"
        # Заголовок: Bot Emoji Pack v1 @ping_super_bot (вимога користувача)
        pack_title = f"Emoji Pack v{version} @{self.me.username}"

        # Реєструємо в базі (спочатку порожній)
        self.chat_repo.emoji_packs.register_pack(pack_name, pack_title, 0)
        return {"name": pack_name, "title": pack_title, "count": 0}

    async def clone_emoji(self, custom_emoji_id: str, owner_id: int) -> Optional[str]:
        """
        Копіює емодзі з чужого паку в наш власний.

        Returns:
            Новий custom_emoji_id з нашого паку або None
        """
        print(
            f"[CLONE_EMOJI] Starting clone for emoji_id={custom_emoji_id}, owner_id={owner_id}"
        )
        await self.ensure_init()

        # 1. Перевіряємо, чи ми вже копіювали цей емодзі
        existing_copy = self.chat_repo.emoji_packs.get_registered_emoji(custom_emoji_id)
        print(f"[CLONE_EMOJI] Existing copy check: {existing_copy}")
        if existing_copy:
            print(f"[CLONE_EMOJI] Returning existing: {existing_copy}")
            return existing_copy

        print(f"[CLONE_EMOJI] No existing copy, proceeding...")
        try:
            # 2. Отримуємо файл емодзі
            print(f"[CLONE_EMOJI] Fetching sticker data...")
            stickers = await self.bot.get_custom_emoji_stickers([custom_emoji_id])
            print(f"[CLONE_EMOJI] Got {len(stickers) if stickers else 0} stickers")
            if not stickers:
                logger.error(f"Emoji {custom_emoji_id} not found")
                print(f"[CLONE_EMOJI] ERROR: No stickers found!")
                return None

            sticker: Sticker = stickers[0]
            print(
                f"[CLONE_EMOJI] Sticker: emoji={sticker.emoji}, file_id={sticker.file_id[:20]}..."
            )

            # 3. Визначаємо формат (статичний, анімований, відео)
            sticker_format = "static"
            if sticker.is_animated:
                sticker_format = "animated"
            elif sticker.is_video:
                sticker_format = "video"

            # 4. Отримуємо активний пак
            pack = await self.get_or_create_active_pack()
            pack_name = pack["name"]

            # 5. Готуємо InputSticker (використовуємо file_id без завантаження)
            sticker_item = InputSticker(
                sticker=sticker.file_id,
                emoji_list=[sticker.emoji or "✨"],
                format=sticker_format,
            )

            try:
                # Спроба додати в існуючий
                logger.info(
                    f"Cloning emoji: Attempting to add sticker to set {pack_name} for owner ID {owner_id}"
                )
                await self.bot.add_sticker_to_set(
                    user_id=owner_id,  # Власник - людина (той хто викликав команду)
                    name=pack_name,
                    sticker=sticker_item,
                )
            except TelegramBadRequest as e:
                logger.warning(f"Failed to add sticker to set: {e}")
                if "STICKERSET_INVALID" in str(e):
                    # Пак ще не існує фізично в Telegram - створюємо
                    logger.info(
                        f"Creating new sticker set {pack_name} for owner ID {owner_id}"
                    )
                    await self.bot.create_new_sticker_set(
                        user_id=owner_id,
                        name=pack_name,
                        title=pack["title"],
                        stickers=[sticker_item],
                        sticker_type="custom_emoji",
                    )
                else:
                    raise e

            # 7. Отримуємо новий custom_emoji_id нашої копії
            # Це трохи складно, бо API не повертає новий ID одразу.
            # Нам треба ще раз отримати стікери набору.
            new_pack_data = await self.bot.get_sticker_set(pack_name)
            new_sticker = new_pack_data.stickers[-1]
            new_custom_id = getattr(new_sticker, "custom_emoji_id", None)

            print(f"[CLONE_EMOJI] New custom_emoji_id from pack: {new_custom_id}")
            if new_custom_id:
                logger.info(
                    f"Successfully cloned emoji! New custom_emoji_id: {new_custom_id} in pack {pack_name}"
                )
                print(f"[CLONE_EMOJI] SUCCESS! Saving mapping...")
                # 8. Зберігаємо мапінг та оновлюємо лічильник
                self.chat_repo.emoji_packs.save_emoji_mapping(
                    custom_emoji_id, new_custom_id, sticker.emoji or "✨"
                )
                self.chat_repo.emoji_packs.increment_pack_count(pack_name)
                print(f"[CLONE_EMOJI] Returning new ID: {new_custom_id}")
                return new_custom_id

            print(f"[CLONE_EMOJI] ERROR: new_custom_id is None!")
            return None

        except Exception as e:
            logger.error(f"Error cloning emoji {custom_emoji_id}: {e}")
            print(f"[CLONE_EMOJI] EXCEPTION: {e}")
            import traceback

            traceback.print_exc()
            return None
