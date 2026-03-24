"""
HENGEONE コネクタ
SCIM 2.0 プロトコルによる連携
設計仕様書 4.3 準拠
"""

import structlog

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from core.config import settings

logger = structlog.get_logger(__name__)


class HengeOneConnector:
    """HENGEONE SCIM 2.0 プロトコルによる連携"""

    SCIM_BASE = settings.HENGEONE_SCIM_BASE_URL

    def _get_headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {settings.HENGEONE_API_TOKEN}",
            "Content-Type": "application/scim+json",
            "Accept": "application/scim+json",
        }

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    async def provision_user(self, user_data: dict) -> dict:
        """HENGEONE へのユーザプロビジョニング（ILM-001）"""
        scim_payload = {
            "schemas": ["urn:ietf:params:scim:schemas:core:2.0:User"],
            "userName": user_data["username"],
            "name": {
                "formatted": user_data["display_name"],
                "displayName": user_data["display_name"],
            },
            "emails": [{"value": user_data["email"], "primary": True, "type": "work"}],
            "active": True,
            "externalId": user_data["employee_id"],
            "title": user_data.get("job_title", ""),
            "urn:ietf:params:scim:schemas:extension:enterprise:2.0:User": {
                "department": user_data.get("department", ""),
                "employeeNumber": user_data["employee_id"],
            },
        }
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.SCIM_BASE}/Users",
                headers=self._get_headers(),
                json=scim_payload,
            )
            response.raise_for_status()
            result = response.json()
            logger.info("HENGEONE user provisioned", hengeone_id=result.get("id"))
            return result

    async def deprovision_user(self, hengeone_id: str) -> bool:
        """退職時 HENGEONE アカウント無効化（ILM-003）"""
        async with httpx.AsyncClient() as client:
            response = await client.patch(
                f"{self.SCIM_BASE}/Users/{hengeone_id}",
                headers=self._get_headers(),
                json={
                    "schemas": ["urn:ietf:params:scim:api:messages:2.0:PatchOp"],
                    "Operations": [{"op": "replace", "path": "active", "value": False}],
                },
            )
            response.raise_for_status()
            logger.info("HENGEONE user deprovisioned", hengeone_id=hengeone_id)
            return True

    async def configure_mfa(self, hengeone_id: str, mfa_type: str = "totp") -> dict:
        """MFA 設定の適用（MFA-001）"""
        async with httpx.AsyncClient() as client:
            response = await client.patch(
                f"{self.SCIM_BASE}/Users/{hengeone_id}",
                headers=self._get_headers(),
                json={
                    "schemas": ["urn:ietf:params:scim:api:messages:2.0:PatchOp"],
                    "Operations": [
                        {
                            "op": "replace",
                            "path": "urn:hengeone:params:scim:schemas:extension:mfa",
                            "value": {"enabled": True, "type": mfa_type},
                        }
                    ],
                },
            )
            response.raise_for_status()
            return response.json()

    async def user_exists(self, username: str) -> bool:
        """ユーザ存在確認"""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.SCIM_BASE}/Users",
                    headers=self._get_headers(),
                    params={"filter": f'userName eq "{username}"'},
                )
                data = response.json()
                return data.get("totalResults", 0) > 0
        except Exception:
            return False

    async def account_active(self, username: str) -> bool:
        """アカウント有効状態確認"""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.SCIM_BASE}/Users",
                    headers=self._get_headers(),
                    params={"filter": f'userName eq "{username}"'},
                )
                data = response.json()
                if data.get("totalResults", 0) > 0:
                    return data["Resources"][0].get("active", False)
            return False
        except Exception:
            return False
