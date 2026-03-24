"""
アイデンティティエンジン
EntraID / AD / HENGEONE の統合プロビジョニング調整
設計仕様書 5.2 準拠（ILM-001, ILM-002, ILM-003）
"""

import logging

from connectors.ad_connector import ADConnector
from connectors.entra_connector import EntraIDConnector
from connectors.hengeone_connector import HengeOneConnector

logger = logging.getLogger(__name__)


class IdentityEngine:
    """
    3システム統合アイデンティティオーケストレーター

    各コネクタを直接呼び出すのではなく、このエンジンを通じて
    プロビジョニング処理を実行することで一貫性を保つ。
    """

    def __init__(self) -> None:
        self.entra = EntraIDConnector()
        self.ad = ADConnector()
        self.hengeone = HengeOneConnector()

    async def provision_user(self, user_data: dict) -> dict:
        """
        新規ユーザを全システムへプロビジョニング（ILM-001）

        実行順:
        1. Entra ID にユーザ作成
        2. Microsoft 365 ライセンス割当
        3. AD アカウント作成
        4. HENGEONE プロビジョニング
        5. HENGEONE MFA 設定

        Returns:
            各システムのプロビジョニング結果
        """
        results: dict = {"entra": None, "ad": None, "hengeone": None, "errors": []}

        # --- Entra ID ---
        try:
            entra_result = await self.entra.create_user(user_data)
            results["entra"] = entra_result
            entra_user_id = entra_result.get("id")

            if entra_user_id:
                await self.entra.assign_license(entra_user_id)
                logger.info("Entra ID provisioned", user_id=entra_user_id)
        except Exception as exc:
            error_msg = f"Entra ID プロビジョニング失敗: {exc}"
            results["errors"].append(error_msg)
            logger.error(error_msg)

        # --- Active Directory ---
        try:
            ad_result = self.ad.create_account(user_data)
            results["ad"] = {"created": ad_result}
            logger.info("AD account provisioned", username=user_data["username"])
        except Exception as exc:
            error_msg = f"AD プロビジョニング失敗: {exc}"
            results["errors"].append(error_msg)
            logger.error(error_msg)

        # --- HENGEONE ---
        try:
            ho_result = await self.hengeone.provision_user(user_data)
            results["hengeone"] = ho_result
            hengeone_id = ho_result.get("id")

            if hengeone_id:
                await self.hengeone.configure_mfa(hengeone_id)
                logger.info("HENGEONE provisioned", hengeone_id=hengeone_id)
        except Exception as exc:
            error_msg = f"HENGEONE プロビジョニング失敗: {exc}"
            results["errors"].append(error_msg)
            logger.error(error_msg)

        return results

    async def deprovision_user(self, user_data: dict) -> dict:
        """
        退職時 3システムのアカウントを無効化（ILM-003）

        user_data には以下が必要:
          - entra_object_id: Entra ID のユーザ ID
          - ad_dn: Active Directory の DN
          - hengeone_id: HENGEONE のユーザ ID
        """
        results: dict = {"entra": None, "ad": None, "hengeone": None, "errors": []}

        if entra_id := user_data.get("entra_object_id"):
            try:
                results["entra"] = await self.entra.disable_user(entra_id)
            except Exception as exc:
                results["errors"].append(f"Entra ID 無効化失敗: {exc}")

        if ad_dn := user_data.get("ad_dn"):
            try:
                results["ad"] = self.ad.disable_account(ad_dn)
            except Exception as exc:
                results["errors"].append(f"AD 無効化失敗: {exc}")

        if hengeone_id := user_data.get("hengeone_id"):
            try:
                results["hengeone"] = await self.hengeone.deprovision_user(hengeone_id)
            except Exception as exc:
                results["errors"].append(f"HENGEONE 無効化失敗: {exc}")

        return results

    async def transfer_user(self, user_data: dict, transfer_info: dict) -> dict:
        """
        異動処理（ILM-002）: 部署・役職の変更を各システムへ反映

        transfer_info には以下を含む:
          - new_department: 新部署名
          - new_job_title: 新役職
          - new_ou: AD の新 OU DN（例: "OU=Engineering,OU=Users,DC=mirai,DC=local"）
        """
        results: dict = {"ad": None, "entra": None, "errors": []}

        new_dept = transfer_info.get("new_department", "")
        new_title = transfer_info.get("new_job_title", "")

        # AD: 属性更新 + OU 移動
        if ad_dn := user_data.get("ad_dn"):
            try:
                changes: dict = {}
                if new_dept:
                    changes["department"] = new_dept
                if new_title:
                    changes["title"] = new_title

                if changes:
                    self.ad.update_account(ad_dn, changes)

                if new_ou := transfer_info.get("new_ou"):
                    self.ad.move_to_ou(ad_dn, new_ou)

                results["ad"] = {"updated": True}
            except Exception as exc:
                results["errors"].append(f"AD 異動処理失敗: {exc}")

        # Entra ID: 属性更新
        if entra_id := user_data.get("entra_object_id"):
            try:
                import httpx

                headers = await self.entra._get_headers()
                payload: dict = {}
                if new_dept:
                    payload["department"] = new_dept
                if new_title:
                    payload["jobTitle"] = new_title

                if payload:
                    async with httpx.AsyncClient() as client:
                        resp = await client.patch(
                            f"{self.entra.BASE_URL}/users/{entra_id}",
                            headers=headers,
                            json=payload,
                        )
                        resp.raise_for_status()
                results["entra"] = {"updated": True}
            except Exception as exc:
                results["errors"].append(f"Entra ID 異動処理失敗: {exc}")

        return results

    async def verify_consistency(self, username: str) -> dict:
        """
        3システム間のアカウント状態整合性確認（ILM-005 棚卸サポート）

        Returns:
            各システムの存在状態と有効状態
        """
        email = f"{username}@mirai-kensetsu.co.jp"
        return {
            "username": username,
            "entra": {
                "exists": await self.entra.user_exists(email),
                "active": await self.entra.account_active(email),
            },
            "ad": {
                "exists": self.ad.account_exists(username),
                "active": self.ad.account_active(username),
            },
            "hengeone": {
                "exists": await self.hengeone.user_exists(username),
                "active": await self.hengeone.account_active(username),
            },
        }
