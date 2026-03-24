"""
Active Directory コネクタ
ldap3 ライブラリを用いた AD 連携
設計仕様書 4.2 準拠
"""

import logging

import ldap3
from tenacity import retry, stop_after_attempt, wait_exponential

from core.config import settings

logger = logging.getLogger(__name__)

# userAccountControl 定数
UAC_NORMAL = "512"        # 有効
UAC_DISABLED = "514"      # 無効


class ADConnector:
    """ldap3 ライブラリを用いた Active Directory 連携"""

    def __init__(self) -> None:
        server = ldap3.Server(settings.AD_SERVER, use_ssl=True, get_info=ldap3.ALL)
        self.conn = ldap3.Connection(
            server,
            settings.AD_BIND_DN,
            settings.AD_BIND_PASSWORD,
            authentication=ldap3.NTLM,
            auto_bind=True,
        )
        self.base_dn = settings.AD_BASE_DN

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    def create_account(self, user_data: dict) -> bool:
        """AD アカウント作成（ILM-001）"""
        department = user_data.get("department", "General")
        dn = f"CN={user_data['display_name']},OU={department},OU=Users,{self.base_dn}"
        attributes = {
            "sAMAccountName": user_data["username"],
            "mail": user_data["email"],
            "department": department,
            "title": user_data.get("job_title", ""),
            "displayName": user_data["display_name"],
            "userPrincipalName": f"{user_data['username']}@mirai.local",
            "userAccountControl": UAC_NORMAL,
        }
        result = self.conn.add(dn, ["user", "organizationalPerson", "person"], attributes)
        if result:
            logger.info("AD account created", username=user_data["username"], dn=dn)
        else:
            logger.error("AD account creation failed", error=self.conn.result)
        return result

    def disable_account(self, dn: str) -> bool:
        """退職時アカウント無効化（ILM-003）"""
        result = self.conn.modify(dn, {
            "userAccountControl": [(ldap3.MODIFY_REPLACE, [UAC_DISABLED])]
        })
        if result:
            logger.info("AD account disabled", dn=dn)
        return result

    def update_account(self, dn: str, changes: dict) -> bool:
        """アカウント情報更新（異動処理 ILM-002）"""
        modifications = {
            key: [(ldap3.MODIFY_REPLACE, [value])]
            for key, value in changes.items()
        }
        return self.conn.modify(dn, modifications)

    def move_to_ou(self, dn: str, new_ou: str) -> bool:
        """OU 移動（異動時 ILM-002）"""
        cn = dn.split(",")[0]
        return self.conn.modify_dn(dn, cn, new_superior=new_ou)

    def account_exists(self, username: str) -> bool:
        """アカウント存在確認"""
        self.conn.search(
            self.base_dn,
            f"(sAMAccountName={ldap3.utils.conv.escape_filter_chars(username)})",
            attributes=["sAMAccountName"],
        )
        return len(self.conn.entries) > 0

    def account_active(self, username: str) -> bool:
        """アカウント有効状態確認"""
        self.conn.search(
            self.base_dn,
            f"(sAMAccountName={ldap3.utils.conv.escape_filter_chars(username)})",
            attributes=["userAccountControl"],
        )
        if not self.conn.entries:
            return False
        uac = int(self.conn.entries[0]["userAccountControl"].value)
        return not bool(uac & 2)  # ビット 2 が有効 = 無効フラグ

    def get_user_dn(self, username: str) -> str | None:
        """ユーザの DN を取得"""
        self.conn.search(
            self.base_dn,
            f"(sAMAccountName={ldap3.utils.conv.escape_filter_chars(username)})",
            attributes=["distinguishedName"],
        )
        if self.conn.entries:
            return str(self.conn.entries[0]["distinguishedName"])
        return None

    def __del__(self) -> None:
        try:
            self.conn.unbind()
        except Exception:
            pass
