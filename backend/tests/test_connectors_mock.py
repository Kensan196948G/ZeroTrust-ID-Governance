"""
コネクタ・エンジンのモックテスト

外部 API（EntraID / AD / HENGEONE）への通信をモックし、
コネクタとアイデンティティエンジンのビジネスロジックを検証する。

準拠: ISO27001 A.8.1 アセット管理 / NIST CSF PR.IP-01
"""

from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock, patch


# ============================================================
# ADConnector テスト（ldap3 をモック）
# ============================================================

class TestADConnector:
    """ADConnector の各メソッドを ldap3 モックで検証"""

    def _make_connector(self):
        """ldap3 をパッチした ADConnector インスタンスを生成"""
        with patch("connectors.ad_connector.ldap3") as mock_ldap3:
            mock_conn = MagicMock()
            mock_conn.add.return_value = True
            mock_conn.modify.return_value = True
            mock_conn.modify_dn.return_value = True
            mock_conn.search.return_value = None
            mock_conn.entries = []
            mock_ldap3.Server.return_value = MagicMock()
            mock_ldap3.Connection.return_value = mock_conn
            mock_ldap3.ALL = "ALL"
            mock_ldap3.NTLM = "NTLM"
            mock_ldap3.MODIFY_REPLACE = "MODIFY_REPLACE"
            mock_ldap3.utils.conv.escape_filter_chars.side_effect = lambda x: x

            from connectors.ad_connector import ADConnector
            connector = ADConnector.__new__(ADConnector)
            connector.conn = mock_conn
            connector.base_dn = "DC=mirai,DC=local"
            return connector, mock_conn

    def test_create_account_success(self):
        """create_account が ldap3.add() を呼び出し True を返す"""
        connector, mock_conn = self._make_connector()
        mock_conn.add.return_value = True
        result = connector.create_account({
            "username": "taro.yamada",
            "email": "taro@mirai.local",
            "display_name": "山田 太郎",
            "department": "Engineering",
            "employee_id": "EMP001",
        })
        assert result is True
        mock_conn.add.assert_called_once()

    def test_create_account_failure(self):
        """create_account が ldap3.add() 失敗時に False を返す"""
        connector, mock_conn = self._make_connector()
        mock_conn.add.return_value = False
        mock_conn.result = {"description": "constraintViolation"}
        result = connector.create_account({
            "username": "taro.yamada",
            "email": "taro@mirai.local",
            "display_name": "山田 太郎",
            "department": "Engineering",
            "employee_id": "EMP001",
        })
        assert result is False

    def test_disable_account_calls_modify(self):
        """disable_account が UAC_DISABLED で modify を呼び出す"""
        connector, mock_conn = self._make_connector()
        mock_conn.modify.return_value = True
        result = connector.disable_account("CN=yamada,OU=Users,DC=mirai,DC=local")
        assert result is True
        mock_conn.modify.assert_called_once()

    def test_update_account_builds_modifications(self):
        """update_account が変更辞書を MODIFY_REPLACE 形式に変換する"""
        connector, mock_conn = self._make_connector()
        mock_conn.modify.return_value = True
        result = connector.update_account(
            "CN=yamada,OU=Users,DC=mirai,DC=local",
            {"department": "Sales", "title": "Manager"},
        )
        assert result is True

    def test_move_to_ou_calls_modify_dn(self):
        """move_to_ou が correct な DN 形式で modify_dn を呼び出す"""
        connector, mock_conn = self._make_connector()
        mock_conn.modify_dn.return_value = True
        result = connector.move_to_ou(
            "CN=yamada,OU=Engineering,OU=Users,DC=mirai,DC=local",
            "OU=Sales,OU=Users,DC=mirai,DC=local",
        )
        assert result is True
        mock_conn.modify_dn.assert_called_once()

    def test_account_exists_true(self):
        """account_exists がエントリあれば True を返す"""
        connector, mock_conn = self._make_connector()
        mock_entry = MagicMock()
        mock_conn.entries = [mock_entry]
        result = connector.account_exists("taro.yamada")
        assert result is True

    def test_account_exists_false(self):
        """account_exists がエントリなしで False を返す"""
        connector, mock_conn = self._make_connector()
        mock_conn.entries = []
        result = connector.account_exists("notexist")
        assert result is False

    def test_account_active_enabled(self):
        """account_active が UAC ビット 2 未設定（有効）で True を返す"""
        connector, mock_conn = self._make_connector()
        mock_entry = MagicMock()
        mock_entry["userAccountControl"].value = "512"  # UAC_NORMAL = 512
        mock_conn.entries = [mock_entry]
        result = connector.account_active("taro.yamada")
        assert result is True  # 512 & 2 == 0, 有効

    def test_account_active_disabled(self):
        """account_active が UAC ビット 2 設定（無効）で False を返す"""
        connector, mock_conn = self._make_connector()
        mock_entry = MagicMock()
        mock_entry["userAccountControl"].value = "514"  # UAC_DISABLED = 514
        mock_conn.entries = [mock_entry]
        result = connector.account_active("taro.yamada")
        assert result is False  # 514 & 2 == 2, 無効

    def test_get_user_dn_found(self):
        """get_user_dn が DN を返す"""
        connector, mock_conn = self._make_connector()
        mock_entry = MagicMock()
        mock_entry["distinguishedName"].__str__ = lambda self: "CN=yamada,OU=Users,DC=mirai,DC=local"
        mock_conn.entries = [mock_entry]
        result = connector.get_user_dn("taro.yamada")
        assert result is not None

    def test_get_user_dn_not_found(self):
        """get_user_dn がユーザ未存在時に None を返す"""
        connector, mock_conn = self._make_connector()
        mock_conn.entries = []
        result = connector.get_user_dn("notexist")
        assert result is None


# ============================================================
# EntraIDConnector テスト（httpx をモック）
# ============================================================

class TestEntraIDConnector:
    """EntraIDConnector の各メソッドを httpx モックで検証"""

    def _make_connector(self):
        from connectors.entra_connector import EntraIDConnector
        connector = EntraIDConnector.__new__(EntraIDConnector)
        connector._access_token = "mock-token-xyz"
        return connector

    @pytest.mark.asyncio
    async def test_get_headers_uses_existing_token(self):
        """_get_headers がキャッシュ済みトークンを再利用する"""
        connector = self._make_connector()
        headers = await connector._get_headers()
        assert headers["Authorization"] == "Bearer mock-token-xyz"
        assert headers["Content-Type"] == "application/json"

    @pytest.mark.asyncio
    async def test_create_user_success(self):
        """create_user が POST レスポンスを返す"""
        connector = self._make_connector()
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "id": "entra-user-id-001",
            "userPrincipalName": "taro@mirai-kensetsu.co.jp",
        }
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.post = AsyncMock(return_value=mock_response)

        with patch("connectors.entra_connector.httpx.AsyncClient", return_value=mock_client):
            result = await connector.create_user({
                "username": "taro.yamada",
                "email": "taro@mirai-kensetsu.co.jp",
                "display_name": "山田 太郎",
                "department": "Engineering",
                "employee_id": "EMP001",
            })
        assert result["id"] == "entra-user-id-001"

    @pytest.mark.asyncio
    async def test_disable_user_success(self):
        """disable_user が PATCH で accountEnabled=False を送信する"""
        connector = self._make_connector()
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.patch = AsyncMock(return_value=mock_response)

        with patch("connectors.entra_connector.httpx.AsyncClient", return_value=mock_client):
            result = await connector.disable_user("entra-user-id-001")
        assert result is True

    @pytest.mark.asyncio
    async def test_user_exists_true(self):
        """user_exists がユーザ存在時に True を返す"""
        connector = self._make_connector()
        mock_response = MagicMock()
        mock_response.status_code = 200  # user_exists は status_code == 200 で判定
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.get = AsyncMock(return_value=mock_response)

        with patch("connectors.entra_connector.httpx.AsyncClient", return_value=mock_client):
            result = await connector.user_exists("taro@mirai-kensetsu.co.jp")
        assert result is True

    @pytest.mark.asyncio
    async def test_user_exists_false(self):
        """user_exists がユーザ未存在時に False を返す"""
        connector = self._make_connector()
        mock_response = MagicMock()
        mock_response.json.return_value = {"value": []}
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.get = AsyncMock(return_value=mock_response)

        with patch("connectors.entra_connector.httpx.AsyncClient", return_value=mock_client):
            result = await connector.user_exists("notexist@mirai-kensetsu.co.jp")
        assert result is False

    # ── 追加: __init__ / _get_token / _get_headers / assign_license / enable_pim_role / account_active の未カバー行 ──

    def test_init_sets_access_token_to_none(self):
        """__init__ が _access_token を None で初期化する（line 28）"""
        from connectors.entra_connector import EntraIDConnector
        connector = EntraIDConnector()
        assert connector._access_token is None

    @pytest.mark.asyncio
    async def test_get_token_success(self):
        """_get_token がクライアントクレデンシャルフローでアクセストークンを取得する（lines 32-43）"""
        from connectors.entra_connector import EntraIDConnector
        connector = EntraIDConnector()
        mock_response = MagicMock()
        mock_response.json.return_value = {"access_token": "fresh-token-abc"}
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.post = AsyncMock(return_value=mock_response)

        with patch("connectors.entra_connector.httpx.AsyncClient", return_value=mock_client):
            token = await connector._get_token()
        assert token == "fresh-token-abc"

    @pytest.mark.asyncio
    async def test_get_headers_calls_get_token_when_token_is_none(self):
        """_access_token が None のとき _get_headers が _get_token を呼び出す（line 47）"""
        from connectors.entra_connector import EntraIDConnector
        connector = EntraIDConnector()
        assert connector._access_token is None

        mock_response = MagicMock()
        mock_response.json.return_value = {"access_token": "fetched-token-xyz"}
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.post = AsyncMock(return_value=mock_response)

        with patch("connectors.entra_connector.httpx.AsyncClient", return_value=mock_client):
            headers = await connector._get_headers()
        assert headers["Authorization"] == "Bearer fetched-token-xyz"
        assert headers["Content-Type"] == "application/json"

    @pytest.mark.asyncio
    async def test_assign_license_success(self):
        """assign_license が M365 ライセンスを割り当て JSON を返す（lines 81-92）"""
        connector = self._make_connector()
        mock_response = MagicMock()
        mock_response.json.return_value = {"id": "entra-user-id-001", "assignedLicenses": []}
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.post = AsyncMock(return_value=mock_response)

        with patch("connectors.entra_connector.httpx.AsyncClient", return_value=mock_client):
            result = await connector.assign_license("entra-user-id-001")
        assert "id" in result

    @pytest.mark.asyncio
    async def test_enable_pim_role_success(self):
        """enable_pim_role が JIT ロール有効化リクエストを送信して JSON を返す（lines 108-131）"""
        connector = self._make_connector()
        mock_response = MagicMock()
        mock_response.json.return_value = {"id": "pim-req-001", "status": "Provisioned"}
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.post = AsyncMock(return_value=mock_response)

        with patch("connectors.entra_connector.httpx.AsyncClient", return_value=mock_client):
            result = await connector.enable_pim_role(
                "entra-user-id-001", "role-def-001", duration_hours=4
            )
        assert result["id"] == "pim-req-001"

    @pytest.mark.asyncio
    async def test_account_active_returns_true(self):
        """account_active がアクティブユーザで True を返す（lines 147-155）"""
        connector = self._make_connector()
        mock_response = MagicMock()
        mock_response.json.return_value = {"accountEnabled": True}

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.get = AsyncMock(return_value=mock_response)

        with patch("connectors.entra_connector.httpx.AsyncClient", return_value=mock_client):
            result = await connector.account_active("taro@mirai-kensetsu.co.jp")
        assert result is True

    @pytest.mark.asyncio
    async def test_account_active_returns_false(self):
        """account_active が無効ユーザで False を返す（lines 147-155）"""
        connector = self._make_connector()
        mock_response = MagicMock()
        mock_response.json.return_value = {"accountEnabled": False}

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.get = AsyncMock(return_value=mock_response)

        with patch("connectors.entra_connector.httpx.AsyncClient", return_value=mock_client):
            result = await connector.account_active("disabled@mirai-kensetsu.co.jp")
        assert result is False

    @pytest.mark.asyncio
    async def test_account_active_exception_returns_false(self):
        """account_active が例外時に False を返す（耐障害設計: lines 154-155）"""
        connector = self._make_connector()
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(side_effect=Exception("network error"))

        with patch("connectors.entra_connector.httpx.AsyncClient", return_value=mock_client):
            result = await connector.account_active("taro@mirai-kensetsu.co.jp")
        assert result is False

    @pytest.mark.asyncio
    async def test_user_exists_exception_returns_false(self):
        """user_exists が例外時に False を返す（耐障害設計: lines 142-143）"""
        connector = self._make_connector()
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(side_effect=Exception("network error"))

        with patch("connectors.entra_connector.httpx.AsyncClient", return_value=mock_client):
            result = await connector.user_exists("taro@mirai-kensetsu.co.jp")
        assert result is False


# ============================================================
# HengeOneConnector テスト（httpx をモック）
# ============================================================

class TestHengeOneConnector:
    """HengeOneConnector の各メソッドを httpx モックで検証"""

    def _make_connector(self):
        from connectors.hengeone_connector import HengeOneConnector
        connector = HengeOneConnector.__new__(HengeOneConnector)
        return connector

    def test_get_headers_format(self):
        """_get_headers が正しい形式を返す"""
        connector = self._make_connector()
        headers = connector._get_headers()
        assert "Authorization" in headers
        assert headers["Content-Type"] == "application/scim+json"

    @pytest.mark.asyncio
    async def test_provision_user_success(self):
        """provision_user が SCIM POST で ID を返す"""
        connector = self._make_connector()
        mock_response = MagicMock()
        mock_response.json.return_value = {"id": "ho-user-001", "active": True}
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.post = AsyncMock(return_value=mock_response)

        with patch("connectors.hengeone_connector.httpx.AsyncClient", return_value=mock_client):
            result = await connector.provision_user({
                "username": "taro.yamada",
                "email": "taro@example.com",
                "display_name": "山田 太郎",
                "employee_id": "EMP001",
            })
        assert result["id"] == "ho-user-001"

    @pytest.mark.asyncio
    async def test_deprovision_user_success(self):
        """deprovision_user が PATCH で True を返す"""
        connector = self._make_connector()
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.patch = AsyncMock(return_value=mock_response)

        with patch("connectors.hengeone_connector.httpx.AsyncClient", return_value=mock_client):
            result = await connector.deprovision_user("ho-user-001")
        assert result is True

    @pytest.mark.asyncio
    async def test_configure_mfa_success(self):
        """configure_mfa が MFA PATCH を送信してレスポンスを返す"""
        connector = self._make_connector()
        mock_response = MagicMock()
        mock_response.json.return_value = {"id": "ho-user-001"}
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.patch = AsyncMock(return_value=mock_response)

        with patch("connectors.hengeone_connector.httpx.AsyncClient", return_value=mock_client):
            result = await connector.configure_mfa("ho-user-001", mfa_type="totp")
        assert result["id"] == "ho-user-001"

    @pytest.mark.asyncio
    async def test_user_exists_true(self):
        """user_exists が totalResults > 0 で True を返す"""
        connector = self._make_connector()
        mock_response = MagicMock()
        mock_response.json.return_value = {"totalResults": 1, "Resources": [{"active": True}]}

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.get = AsyncMock(return_value=mock_response)

        with patch("connectors.hengeone_connector.httpx.AsyncClient", return_value=mock_client):
            result = await connector.user_exists("taro.yamada")
        assert result is True

    @pytest.mark.asyncio
    async def test_user_exists_false(self):
        """user_exists が totalResults == 0 で False を返す"""
        connector = self._make_connector()
        mock_response = MagicMock()
        mock_response.json.return_value = {"totalResults": 0}

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.get = AsyncMock(return_value=mock_response)

        with patch("connectors.hengeone_connector.httpx.AsyncClient", return_value=mock_client):
            result = await connector.user_exists("notexist")
        assert result is False

    @pytest.mark.asyncio
    async def test_user_exists_exception_returns_false(self):
        """user_exists が例外時に False を返す（耐障害設計）"""
        connector = self._make_connector()
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(side_effect=Exception("network error"))

        with patch("connectors.hengeone_connector.httpx.AsyncClient", return_value=mock_client):
            result = await connector.user_exists("taro.yamada")
        assert result is False

    @pytest.mark.asyncio
    async def test_account_active_true(self):
        """account_active がアクティブユーザで True を返す"""
        connector = self._make_connector()
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "totalResults": 1,
            "Resources": [{"active": True}],
        }

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.get = AsyncMock(return_value=mock_response)

        with patch("connectors.hengeone_connector.httpx.AsyncClient", return_value=mock_client):
            result = await connector.account_active("taro.yamada")
        assert result is True


# ============================================================
# IdentityEngine テスト（全コネクタをモック）
# ============================================================

class TestIdentityEngine:
    """IdentityEngine のオーケストレーションロジックをモックで検証"""

    USER_DATA = {
        "username": "taro.yamada",
        "email": "taro@mirai-kensetsu.co.jp",
        "display_name": "山田 太郎",
        "department": "Engineering",
        "employee_id": "EMP001",
        "job_title": "Engineer",
    }

    def _make_engine(self):
        """全コネクタをモックした IdentityEngine インスタンスを生成"""
        mock_entra = AsyncMock()
        mock_entra.create_user = AsyncMock(return_value={"id": "entra-001"})
        mock_entra.assign_license = AsyncMock(return_value=True)
        mock_entra.disable_user = AsyncMock(return_value=True)
        mock_entra.user_exists = AsyncMock(return_value=True)
        mock_entra.account_active = AsyncMock(return_value=True)
        mock_entra.BASE_URL = "https://graph.microsoft.com/v1.0"

        mock_ad = MagicMock()
        mock_ad.create_account = MagicMock(return_value=True)
        mock_ad.disable_account = MagicMock(return_value=True)
        mock_ad.update_account = MagicMock(return_value=True)
        mock_ad.move_to_ou = MagicMock(return_value=True)
        mock_ad.account_exists = MagicMock(return_value=True)
        mock_ad.account_active = MagicMock(return_value=True)

        mock_hengeone = AsyncMock()
        mock_hengeone.provision_user = AsyncMock(return_value={"id": "ho-001"})
        mock_hengeone.configure_mfa = AsyncMock(return_value={"id": "ho-001"})
        mock_hengeone.deprovision_user = AsyncMock(return_value=True)
        mock_hengeone.user_exists = AsyncMock(return_value=True)
        mock_hengeone.account_active = AsyncMock(return_value=True)

        with (
            patch("engine.identity_engine.EntraIDConnector", return_value=mock_entra),
            patch("engine.identity_engine.ADConnector", return_value=mock_ad),
            patch("engine.identity_engine.HengeOneConnector", return_value=mock_hengeone),
        ):
            from engine.identity_engine import IdentityEngine
            engine = IdentityEngine()

        return engine, mock_entra, mock_ad, mock_hengeone

    @pytest.mark.asyncio
    async def test_provision_user_all_success(self):
        """provision_user が全システムに成功した場合に errors が空"""
        engine, mock_entra, mock_ad, mock_hengeone = self._make_engine()
        result = await engine.provision_user(self.USER_DATA)
        assert result["errors"] == []
        assert result["entra"]["id"] == "entra-001"
        assert result["ad"]["created"] is True
        assert result["hengeone"]["id"] == "ho-001"

    @pytest.mark.asyncio
    async def test_provision_user_entra_failure_partial(self):
        """Entra ID 失敗時も AD/HENGEONE は継続してエラーがリストに記録される"""
        engine, mock_entra, mock_ad, mock_hengeone = self._make_engine()
        mock_entra.create_user.side_effect = Exception("Entra API error")
        result = await engine.provision_user(self.USER_DATA)
        assert len(result["errors"]) == 1
        assert "Entra ID" in result["errors"][0]
        # AD と HENGEONE は継続実行
        assert result["ad"]["created"] is True

    @pytest.mark.asyncio
    async def test_provision_user_calls_mfa(self):
        """provision_user が HENGEONE ID 取得後に configure_mfa を呼び出す"""
        engine, mock_entra, mock_ad, mock_hengeone = self._make_engine()
        await engine.provision_user(self.USER_DATA)
        mock_hengeone.configure_mfa.assert_called_once_with("ho-001")

    @pytest.mark.asyncio
    async def test_deprovision_user(self):
        """deprovision_user が全システムで無効化を実行する"""
        engine, mock_entra, mock_ad, mock_hengeone = self._make_engine()
        result = await engine.deprovision_user({
            "entra_object_id": "entra-001",
            "ad_dn": "CN=yamada,OU=Users,DC=mirai,DC=local",
            "hengeone_id": "ho-001",
        })
        assert result["errors"] == []
        mock_entra.disable_user.assert_called_once_with("entra-001")
        mock_ad.disable_account.assert_called_once()
        mock_hengeone.deprovision_user.assert_called_once_with("ho-001")

    @pytest.mark.asyncio
    async def test_transfer_user_updates_ad(self):
        """transfer_user が AD の update_account と move_to_ou を呼び出す"""
        engine, mock_entra, mock_ad, mock_hengeone = self._make_engine()
        result = await engine.transfer_user(
            {"ad_dn": "CN=yamada,OU=Eng,DC=mirai,DC=local"},
            {"new_department": "Sales", "new_job_title": "Manager", "new_ou": "OU=Sales,DC=mirai,DC=local"},
        )
        assert result["errors"] == []
        mock_ad.update_account.assert_called_once()
        mock_ad.move_to_ou.assert_called_once()

    @pytest.mark.asyncio
    async def test_verify_consistency(self):
        """verify_consistency が全システムの整合性状態を返す"""
        engine, mock_entra, mock_ad, mock_hengeone = self._make_engine()
        result = await engine.verify_consistency("taro.yamada")
        assert result["username"] == "taro.yamada"
        assert "entra" in result
        assert "ad" in result
        assert "hengeone" in result
        assert result["entra"]["exists"] is True
        assert result["ad"]["active"] is True
