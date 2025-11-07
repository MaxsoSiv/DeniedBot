from __future__ import annotations

import discord
from discord.ext import commands
import json
import os
from typing import TYPE_CHECKING, Self
from pathlib import Path
from dotenv import load_dotenv
import datetime
import threading
from flask import Flask, jsonify

if TYPE_CHECKING:
    from collections.abc import Iterable

# Загружаем переменные из .env файла
load_dotenv()

# Инициализация Flask приложения
app = Flask(__name__)

@app.route('/')
def home():
    return jsonify({
        "status": "online",
        "bot": "DeniedBot",
        "description": "Discord bot for moderating emojis"
    })

@app.route('/health')
def health():
    return jsonify({"status": "healthy"})

def run_flask():
    """Запускает Flask сервер в отдельном потоке"""
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port, debug=False)

# Настройки бота
intents = discord.Intents.all()
bot = commands.Bot(command_prefix='!', intents=intents)

# Файл для хранения запрещенных эмодзи
BANNED_EMOJIS_FILE = Path('banned_emojis.json')
BACKUP_FOLDER = Path('backups')

# Создаем папку для бэкапов если ее нет
BACKUP_FOLDER.mkdir(exist_ok=True)

# Список эмодзи флагов стран
DEFAULT_COUNTRY_FLAGS = [
    '🇷🇺', '🇺🇦', '🇺🇸', '🇬🇧', '🇩🇪', '🇫🇷', '🇨🇳', '🇯🇵', '🇰🇷',
    '🇮🇹', '🇪🇸', '🇨🇦', '🇦🇺', '🇧🇷', '🇮🇳', '🇵🇱', '🇹🇷', '🇸🇦'
]

class EmojiModerator(commands.Cog):
    def __init__(self: Self, bot: commands.Bot) -> None:
        self.bot = bot
        self.banned_emojis = self.load_banned_emojis()
        self.all_banned_emojis = set(DEFAULT_COUNTRY_FLAGS + self.banned_emojis)

    def load_banned_emojis(self: Self) -> list[str]:
        """Загружаем запрещенные эмодзи из файла"""
        if BANNED_EMOJIS_FILE.exists():
            try:
                with BANNED_EMOJIS_FILE.open('r', encoding='utf-8') as f:
                    return json.load(f)
            except json.JSONDecodeError:
                print("Ошибка: Файл banned_emojis.json поврежден!")
                return []
        return []

    def save_banned_emojis(self: Self, emojis: Iterable[str]) -> None:
        """Сохраняем запрещенные эмодзи в файл"""
        with BANNED_EMOJIS_FILE.open('w', encoding='utf-8') as f:
            json.dump(list(emojis), f, ensure_ascii=False, indent=2)

    def contains_banned_emoji(self: Self, text: str) -> bool:
        """Проверяет, содержит ли текст запрещенный эмодзи"""
        return any(emoji in text for emoji in self.all_banned_emojis)

    @commands.Cog.listener()
    async def on_message(self: Self, message: discord.Message) -> None:
        if message.author.bot:
            return

        if self.contains_banned_emoji(message.content):
            try:
                await message.delete()
                warning_embed = discord.Embed(
                    title="⚠️ Предупреждение",
                    description=f"{message.author.mention}, использование флагов стран запрещено!",
                    color=discord.Color.orange()
                )
                await message.channel.send(embed=warning_embed, delete_after=10)
            except Exception as e:
                print(f"Ошибка: {e}")

    @commands.Cog.listener()
    async def on_reaction_add(self: Self, reaction: discord.Reaction, user: discord.User | discord.Member) -> None:
        if user.bot:
            return

        emoji_str = str(reaction.emoji)
        if emoji_str in self.all_banned_emojis:
            try:
                await reaction.message.remove_reaction(reaction.emoji, user)
                try:
                    warning_dm = discord.Embed(
                        title="⚠️ Предупреждение",
                        description="Использование реакций с флагами стран запрещено!",
                        color=discord.Color.orange()
                    )
                    await user.send(embed=warning_dm)
                except:
                    warning_chat = f"{user.mention}, использование реакций с флагами стран запрещено!"
                    await reaction.message.channel.send(warning_chat, delete_after=10)
            except Exception as e:
                print(f"Ошибка при обработке реакции: {e}")

    @commands.command(name='add-emoji')
    @commands.has_permissions(administrator=True)
    async def add_emoji(self: Self, ctx: commands.Context, emoji: str) -> None:
        """Добавляет эмодзи в список запрещенных"""
        if emoji in self.banned_emojis:
            await ctx.send(f"Эмодзи {emoji} уже в списке!")
            return

        self.banned_emojis.append(emoji)
        self.all_banned_emojis.add(emoji)
        self.save_banned_emojis(self.banned_emojis)
        
        embed = discord.Embed(
            title="✅ Эмодзи добавлен",
            description=f"Эмодзи {emoji} добавлен в список запрещенных",
            color=discord.Color.green()
        )
        await ctx.send(embed=embed)

    @commands.command(name='remove-emoji')
    @commands.has_permissions(administrator=True)
    async def remove_emoji(self: Self, ctx: commands.Context, emoji: str) -> None:
        """Удаляет эмодзи из списка запрещенных"""
        if emoji not in self.banned_emojis:
            await ctx.send(f"Эмодзи {emoji} не найден!")
            return

        self.banned_emojis.remove(emoji)
        self.all_banned_emojis.discard(emoji)
        self.save_banned_emojis(self.banned_emojis)
        
        embed = discord.Embed(
            title="✅ Эмодзи удален",
            description=f"Эмодзи {emoji} удален из запрещенных",
            color=discord.Color.green()
        )
        await ctx.send(embed=embed)

    @commands.command(name='list-banned')
    @commands.has_permissions(administrator=True)
    async def list_banned(self: Self, ctx: commands.Context) -> None:
        """Показывает список всех запрещенных эмодзи"""
        if not self.all_banned_emojis:
            await ctx.send("Список пуст!")
            return
            
        banned_list = "\n".join(self.all_banned_emojis)
        embed = discord.Embed(
            title="📋 Запрещенные эмодзи", 
            description=banned_list,
            color=discord.Color.blue()
        )
        await ctx.send(embed=embed)

    @commands.command(name='backup')
    @commands.has_permissions(administrator=True)
    async def backup(self: Self, ctx: commands.Context) -> None:
        """Создает резервную копию файла с запрещенными эмодзи"""
        try:
            if not BANNED_EMOJIS_FILE.exists():
                await ctx.send("❌ Файл с запрещенными эмодзи не существует!")
                return

            # Создаем имя файла с timestamp
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_filename = f"banned_emojis_backup_{timestamp}.json"
            backup_path = BACKUP_FOLDER / backup_filename

            # Копируем файл
            import shutil
            shutil.copy2(BANNED_EMOJIS_FILE, backup_path)

            # Отправляем файл в чат
            await ctx.send(
                content="✅ Резервная копия создана!",
                file=discord.File(backup_path)
            )

        except Exception as e:
            await ctx.send(f"❌ Ошибка при создании резервной копии: {e}")

    @commands.command(name='restore')
    @commands.has_permissions(administrator=True)
    async def restore(self: Self, ctx: commands.Context) -> None:
        """Восстанавливает запрещенные эмодзи из файла"""
        try:
            if not ctx.message.attachments:
                await ctx.send("❌ Пожалуйста, прикрепите .json файл для восстановления!")
                return

            attachment = ctx.message.attachments[0]
            if not attachment.filename.endswith('.json'):
                await ctx.send("❌ Файл должен быть в формате .json!")
                return

            # Скачиваем файл
            await attachment.save(BANNED_EMOJIS_FILE)

            # Перезагружаем данные
            self.banned_emojis = self.load_banned_emojis()
            self.all_banned_emojis = set(DEFAULT_COUNTRY_FLAGS + self.banned_emojis)

            embed = discord.Embed(
                title="✅ Восстановление завершено",
                description="Список запрещенных эмодзи успешно восстановлен из файла!",
                color=discord.Color.green()
            )
            await ctx.send(embed=embed)

        except Exception as e:
            await ctx.send(f"❌ Ошибка при восстановлении: {e}")

app = Flask('')

@app.route('/')
def home():
    return "🤖 Discord Bot is Online! | Status: ✅ Running"

@app.route('/health')
def health():
    return "OK", 200

def run_flask():
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port, debug=False)

def keep_alive():
    flask_thread = threading.Thread(target=run_flask)
    flask_thread.daemon = True
    flask_thread.start()
    print(f"🌐 Flask server started for Render compatibility")

# Запускаем Flask сервер
keep_alive()
# ==================== END RENDER FIX ====================

# Запуск бота
if __name__ == "__main__":
    bot.run(DISCORD_TOKEN)

    
    token = os.getenv('DISCORD_TOKEN')
    if token is None:
        print("Ошибка: DISCORD_TOKEN не найден в переменных окружения!")
        print("Убедитесь, что файл .env существует и содержит DISCORD_TOKEN")
    else:
        bot.run(token)

