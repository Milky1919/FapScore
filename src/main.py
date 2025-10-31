import os
import logging
import disnake
from disnake.ext import commands
from dotenv import load_dotenv

from bot.api_client import FAPApiClient
from bot.commands import setup as setup_commands

# .envファイルから環境変数を読み込む
load_dotenv()

# ロギング設定
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

# --- 環境変数と設定 ---
DISCORD_BOT_TOKEN = os.getenv("DISCORD_BOT_TOKEN")
FAP_API_BASE_URL = os.getenv("FAP_API_BASE_URL")

if not DISCORD_BOT_TOKEN:
    logger.critical("環境変数 `DISCORD_BOT_TOKEN` が設定されていません。")
    exit(1)
if not FAP_API_BASE_URL:
    logger.critical("環境変数 `FAP_API_BASE_URL` が設定されていません。")
    exit(1)

# --- ボットの初期化 ---
try:
    api_client = FAPApiClient(base_url=FAP_API_BASE_URL)
except ValueError as e:
    logger.critical(f"APIクライアントの初期化に失敗しました: {e}")
    exit(1)

# Botインスタンスを作成 (必要なIntentsを有効化)
intents = disnake.Intents.default()
intents.guilds = True # サーバー情報の取得に必要

bot = commands.Bot(
    command_prefix=commands.when_mentioned_or("!"), # スラッシュコマンドがメインだが念のため設定
    intents=intents,
    activity=disnake.Activity(
        name="/fap_alert_add で通知登録",
        type=disnake.ActivityType.playing
    )
)

# --- イベントリスナー ---
@bot.event
async def on_ready():
    """ボットがDiscordに正常に接続したときに呼び出されるイベント。"""
    logger.info(f"Logged in as {bot.user} (ID: {bot.user.id})")
    logger.info("Bot is ready and online!")
    logger.info("-" * 20)

# --- メイン処理 ---
def main():
    """ボットをセットアップし、実行するメイン関数。"""

    # コマンドCogを読み込む
    setup_commands(bot, api_client)
    logger.info("コマンドCogを正常にロードしました。")

    # ボットを実行
    bot.run(DISCORD_BOT_TOKEN)

if __name__ == "__main__":
    main()
