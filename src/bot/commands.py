import disnake
from disnake.ext import commands
import json
import logging

from .api_client import FAPApiClient, APIError

# ロガーの設定
logger = logging.getLogger(__name__)

# API仕様書に記載されている配列型のパラメータ
# これらはユーザーがカンマ区切りで入力することを想定
ARRAY_TYPE_PARAMETERS = [
    "include_wish_real_ages", "include_wish_jobs", "include_playstyle_tags",
    "include_activity_times", "include_wish_races", "include_wish_char_genders",
    "include_wish_real_genders", "include_external_tools"
]

class FapAlertCommands(commands.Cog):
    """FAPアラートボットのスラッシュコマンドを管理するCog。"""

    def __init__(self, bot: commands.Bot, api_client: FAPApiClient):
        self.bot = bot
        self.api_client = api_client

    # --- Utility Methods ---

    def _parse_array_param(self, value: str | None) -> list[str] | None:
        """カンマ区切りの文字列をリストに変換する。"""
        if value is None:
            return None
        return [item.strip() for item in value.split(',') if item.strip()]

    async def _get_or_create_webhook(self, channel: disnake.TextChannel) -> disnake.Webhook | None:
        """指定されたチャンネルでボットが管理するWebhookを取得または作成する。"""
        try:
            webhooks = await channel.webhooks()
            bot_webhook = disnake.utils.find(lambda w: w.user == self.bot.user, webhooks)
            if bot_webhook:
                return bot_webhook
            # Webhookが存在しない場合は作成
            return await channel.create_webhook(name=f"{self.bot.user.name} Alerts")
        except disnake.Forbidden:
            logger.error(f"Webhookの管理権限がありません: channel_id={channel.id}")
            return None
        except disnake.HTTPException as e:
            logger.error(f"Webhookの取得/作成中にエラーが発生しました: {e}")
            return None

    # --- Slash Commands ---

    @commands.slash_command(
        name="fap_alert_list",
        description="このサーバーに登録されている通知ルールを一覧表示します。"
    )
    async def fap_alert_list(self, inter: disnake.ApplicationCommandInteraction):
        await inter.response.defer()

        try:
            alerts = await self.api_client.list_alerts(str(inter.guild.id))

            if not alerts:
                await inter.followup.send("このサーバーには登録済みの通知ルールがありません。")
                return

            embed = disnake.Embed(
                title="登録済み通知ルール一覧",
                color=disnake.Color.blue()
            )

            for alert in alerts:
                try:
                    conditions = json.loads(alert['conditions_json'])
                    # 条件を見やすく整形
                    conditions_str = "\n".join(f"- `{key}`: `{value}`" for key, value in conditions.items())
                    if not conditions_str:
                        conditions_str = "条件なし (すべての新規投稿)"
                except json.JSONDecodeError:
                    conditions_str = alert['conditions_json']

                # Webhook URLからチャンネルIDを抽出し、チャンネル名に変換を試みる
                webhook_id = alert['webhook_url'].split('/')[-2]
                channel_info = f"Webhook ID: `{webhook_id}`"
                try:
                    webhook = await self.bot.fetch_webhook(int(webhook_id))
                    if webhook and webhook.channel:
                        channel_info = f"通知先: <#{webhook.channel.id}>"
                except (disnake.NotFound, disnake.Forbidden, ValueError):
                     pass # チャンネルが特定できなくても続行

                embed.add_field(
                    name=f"アラートID: `{alert['alert_id']}`",
                    value=f"{channel_info}\n**通知条件:**\n{conditions_str}",
                    inline=False
                )

            await inter.followup.send(embed=embed)

        except APIError as e:
            logger.error(f"APIエラー (list): {e}")
            await inter.followup.send(f"❌ ルール一覧の取得に失敗しました (APIエラー: {e.status})。")
        except Exception as e:
            logger.exception("予期せぬエラー (list):")
            await inter.followup.send("❌ 不明なエラーが発生しました。")


    @commands.slash_command(
        name="fap_alert_remove",
        description="指定したIDの通知ルールを削除します。"
    )
    async def fap_alert_remove(
        self,
        inter: disnake.ApplicationCommandInteraction,
        alert_id: int = commands.Param(description="削除する通知ルールのID。")
    ):
        # サーバー管理者権限をチェック
        if not inter.author.guild_permissions.manage_guild:
            await inter.response.send_message("❌ このコマンドを実行するにはサーバーの管理権限が必要です。", ephemeral=True)
            return

        await inter.response.defer()

        try:
            success = await self.api_client.remove_alert(alert_id)
            if success:
                await inter.followup.send(f"✅ アラートID `{alert_id}` の通知ルールを削除しました。")

        except APIError as e:
            logger.warning(f"APIエラー (remove): {e}")
            if e.status == 404:
                await inter.followup.send(f"❌ 指定されたアラートID `{alert_id}` は存在しません。")
            else:
                await inter.followup.send(f"❌ ルールの削除に失敗しました (APIエラー: {e.status})。")
        except Exception as e:
            logger.exception("予期せぬエラー (remove):")
            await inter.followup.send("❌ 不明なエラーが発生しました。")

    @fap_alert_remove.autocomplete("alert_id")
    async def fap_alert_remove_autocomplete(
        self, inter: disnake.ApplicationCommandInteraction, user_input: str
    ):
        """削除コマンドのalert_id入力中に、サーバーのIDをサジェストする。"""
        if not inter.guild:
            return {}

        try:
            alerts = await self.api_client.list_alerts(str(inter.guild.id))
            # 文字列に変換して前方一致でフィルタリング
            return {
                str(alert['alert_id']): alert['alert_id']
                for alert in alerts if str(alert['alert_id']).startswith(user_input)
            }
        except APIError: # APIエラー時はサジェストしない
            return {}
        except Exception:
            return {}

    @commands.slash_command(
        name="fap_alert_add",
        description="新しい通知ルールを登録します。"
    )
    async def fap_alert_add(
        self,
        inter: disnake.ApplicationCommandInteraction,
        channel: disnake.TextChannel = commands.Param(description="通知を投稿させたいチャンネル。"),
        min_score: float = commands.Param(description="最低ユニークスコア (0-100)。", default=None),
        purpose: str = commands.Param(description="募集目的 (例: フレンド, 相方)。", default=None),
        author_real_gender: str = commands.Param(description="投稿者のリアル性別 (例: 男性, 女性)。", default=None),
        server: str = commands.Param(description="活動サーバー名 (例: Mana)。", default=None),
        voice_chat: str = commands.Param(description="VC状況 (例: ◯, △, ✕)。", default=None),
        include_playstyle_tags: str = commands.Param(description="プレイスタイルタグ (カンマ区切り)。", default=None),
        include_activity_times: str = commands.Param(description="活動時間タグ (カンマ区切り)。", default=None),
        include_wish_jobs: str = commands.Param(description="希望ジョブタグ (カンマ区切り)。", default=None)
        # ... 他のパラメータも同様に追加可能
    ):
        await inter.response.defer()

        # Webhookの取得/作成
        webhook = await self._get_or_create_webhook(channel)
        if not webhook:
            await inter.followup.send(f"❌ <#{channel.id}> のWebhookを管理できませんでした。ボットに「ウェブフックの管理」権限があるか確認してください。")
            return

        # conditions_jsonの構築
        conditions = {}
        # locals()を使ってコマンドの引数を一括処理
        args = locals()
        for key, value in args.items():
            if key in ["self", "inter", "channel"] or value is None:
                continue

            if key in ARRAY_TYPE_PARAMETERS:
                parsed_list = self._parse_array_param(value)
                if parsed_list: # 空リストは条件に含めない
                    conditions[key] = parsed_list
            else:
                conditions[key] = value

        try:
            created_alert = await self.api_client.add_alert(
                guild_id=str(inter.guild.id),
                webhook_url=webhook.url,
                conditions=conditions
            )
            alert_id = created_alert.get('alert_id')
            await inter.followup.send(f"✅ 通知ルールを登録しました！ (アラートID: `{alert_id}`)\n- 通知先: <#{channel.id}>")

        except APIError as e:
            logger.error(f"APIエラー (add): {e}")
            await inter.followup.send(f"❌ ルールの登録に失敗しました (APIエラー: {e.status})。")
        except Exception as e:
            logger.exception("予期せぬエラー (add):")
            await inter.followup.send("❌ 不明なエラーが発生しました。")


def setup(bot: commands.Bot, api_client: FAPApiClient):
    """Cogをボットに登録するためのセットアップ関数。"""
    bot.add_cog(FapAlertCommands(bot, api_client))
