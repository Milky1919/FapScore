import aiohttp
import json
import os

class APIError(Exception):
    """FAP Analyzer APIからのエラーレスポンスを表す例外クラス。"""
    def __init__(self, status: int, message: str):
        self.status = status
        self.message = message
        super().__init__(f"API Error {status}: {message}")

class FAPApiClient:
    """FAP Analyzer APIと非同期に通信するためのクライアントクラス。"""

    def __init__(self, base_url: str):
        if not base_url:
            raise ValueError("API_BASE_URL is not set.")
        self.base_url = base_url.rstrip('/')

    async def add_alert(self, guild_id: str, webhook_url: str, conditions: dict) -> dict:
        """
        新しい通知ルールをAPIに登録する。

        :param guild_id: DiscordサーバーのID
        :param webhook_url: 通知先のWebhook URL
        :param conditions: 通知条件の辞書
        :return: 作成されたアラートの情報を含む辞書
        :raises APIError: APIがエラーを返した場合
        """
        url = f"{self.base_url}/api/v1/alerts"
        payload = {
            "guild_id": guild_id,
            "webhook_url": webhook_url,
            "conditions_json": json.dumps(conditions, ensure_ascii=False)
        }
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload) as response:
                if response.status == 200:
                    return await response.json()
                else:
                    error_data = await response.json()
                    raise APIError(response.status, error_data.get("detail", "Unknown error"))

    async def list_alerts(self, guild_id: str) -> list[dict]:
        """
        指定されたDiscordサーバーに登録されている通知ルールの一覧を取得する。

        :param guild_id: DiscordサーバーのID
        :return: アラート情報の辞書のリスト
        :raises APIError: APIがエラーを返した場合
        """
        url = f"{self.base_url}/api/v1/alerts"
        params = {"guild_id": guild_id}
        async with aiohttp.ClientSession() as session:
            async with session.get(url, params=params) as response:
                if response.status == 200:
                    return await response.json()
                else:
                    error_data = await response.json()
                    raise APIError(response.status, error_data.get("detail", "Unknown error"))

    async def remove_alert(self, alert_id: int) -> bool:
        """
        指定されたIDの通知ルールを削除する。

        :param alert_id: 削除するアラートのID
        :return: 削除が成功した場合は True
        :raises APIError: APIがエラーを返した場合 (404 Not Found を含む)
        """
        url = f"{self.base_url}/api/v1/alerts/{alert_id}"
        async with aiohttp.ClientSession() as session:
            async with session.delete(url) as response:
                if response.status == 204:
                    return True
                else:
                    try:
                        error_data = await response.json()
                        message = error_data.get("detail", "Unknown error")
                    except aiohttp.ContentTypeError:
                        message = await response.text()
                    raise APIError(response.status, message)
