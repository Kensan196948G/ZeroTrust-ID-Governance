"""
Microsoft Entra ID コネクタ
Microsoft Graph API を通じた Entra ID 連携
設計仕様書 4.1 準拠
"""

import logging
import secrets
import string

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from core.config import settings

logger = logging.getLogger(__name__)

M365_E3_SKU = "05e9a617-0261-4cee-bb44-138d3ef5d965"  # Microsoft 365 E3


class EntraIDConnector:
    """Microsoft Graph API を通じた Entra ID 連携"""

    BASE_URL = "https://graph.microsoft.com/v1.0"
    TOKEN_URL = f"https://login.microsoftonline.com/{settings.AZURE_TENANT_ID}/oauth2/v2.0/token"

    def __init__(self) -> None:
        self._access_token: str | None = None

    async def _get_token(self) -> str:
        """クライアントクレデンシャルフローでアクセストークン取得"""
        async with httpx.AsyncClient() as client:
            response = await client.post(
                self.TOKEN_URL,
                data={
                    "grant_type": "client_credentials",
                    "client_id": settings.AZURE_CLIENT_ID,
                    "client_secret": settings.AZURE_CLIENT_SECRET,
                    "scope": "https://graph.microsoft.com/.default",
                },
            )
            response.raise_for_status()
            return response.json()["access_token"]

    async def _get_headers(self) -> dict[str, str]:
        if not self._access_token:
            self._access_token = await self._get_token()
        return {
            "Authorization": f"Bearer {self._access_token}",
            "Content-Type": "application/json",
        }

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    async def create_user(self, user_data: dict) -> dict:
        """Entra ID ユーザ作成（ILM-001）"""
        payload = {
            "accountEnabled": True,
            "displayName": user_data["display_name"],
            "mailNickname": user_data["username"],
            "userPrincipalName": f"{user_data['username']}@mirai-kensetsu.co.jp",
            "jobTitle": user_data.get("job_title", ""),
            "department": user_data.get("department", ""),
            "passwordProfile": {
                "forceChangePasswordNextSignIn": True,
                "password": self._generate_temp_password(),
            },
        }
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.BASE_URL}/users",
                headers=await self._get_headers(),
                json=payload,
            )
            response.raise_for_status()
            result = response.json()
            logger.info("Entra ID user created", user_id=result.get("id"), upn=result.get("userPrincipalName"))
            return result

    async def assign_license(self, user_id: str, sku_id: str = M365_E3_SKU) -> dict:
        """Microsoft 365 ライセンス割当"""
        payload = {
            "addLicenses": [{"skuId": sku_id, "disabledPlans": []}],
            "removeLicenses": [],
        }
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.BASE_URL}/users/{user_id}/assignLicense",
                headers=await self._get_headers(),
                json=payload,
            )
            response.raise_for_status()
            return response.json()

    async def disable_user(self, user_id: str) -> bool:
        """退職時アカウント無効化（ILM-003）"""
        async with httpx.AsyncClient() as client:
            response = await client.patch(
                f"{self.BASE_URL}/users/{user_id}",
                headers=await self._get_headers(),
                json={"accountEnabled": False},
            )
            response.raise_for_status()
            logger.info("Entra ID user disabled", user_id=user_id)
            return True

    async def enable_pim_role(self, user_id: str, role_id: str, duration_hours: int = 8) -> dict:
        """PIM 特権ロールの時限付き有効化（MFA-004）"""
        from datetime import datetime, timedelta, timezone

        payload = {
            "principalId": user_id,
            "roleDefinitionId": role_id,
            "directoryScopeId": "/",
            "action": "selfActivate",
            "justification": "JIT access via ZeroTrust-ID-Governance",
            "scheduleInfo": {
                "startDateTime": datetime.now(timezone.utc).isoformat(),
                "expiration": {
                    "type": "AfterDuration",
                    "duration": f"PT{duration_hours}H",
                },
            },
        }
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.BASE_URL}/roleManagement/directory/roleEligibilityScheduleRequests",
                headers=await self._get_headers(),
                json=payload,
            )
            response.raise_for_status()
            return response.json()

    async def user_exists(self, email: str) -> bool:
        """ユーザ存在確認"""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.BASE_URL}/users/{email}",
                    headers=await self._get_headers(),
                )
                return response.status_code == 200
        except Exception:
            return False

    async def account_active(self, email: str) -> bool:
        """アカウント有効状態確認"""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.BASE_URL}/users/{email}?$select=accountEnabled",
                    headers=await self._get_headers(),
                )
                return response.json().get("accountEnabled", False)
        except Exception:
            return False

    @staticmethod
    def _generate_temp_password() -> str:
        """一時パスワード生成（大文字・小文字・数字・記号を含む12文字以上）"""
        chars = string.ascii_uppercase + string.ascii_lowercase + string.digits + "!@#$%"
        return "".join(secrets.choice(chars) for _ in range(16))
