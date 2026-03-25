"""
アイデンティティエンジン統合テスト（Phase 9）

3システム（EntraID / AD / HENGEONE）統合プロビジョニングの
モックベース単体テスト。

準拠: ISO27001 A.5.15 / ILM-001 / ILM-002 / ILM-003 / ILM-005
"""

from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from engine.identity_engine import IdentityEngine


# ============================================================
# フィクスチャ
# ============================================================

@pytest.fixture
def mock_entra() -> AsyncMock:
    m = AsyncMock()
    m.create_user.return_value = {"id": "entra-uid-123", "displayName": "Test User"}
    m.assign_license.return_value = True
    m.disable_user.return_value = {"status": "disabled"}
    m.user_exists.return_value = True
    m.account_active.return_value = True
    m._get_headers.return_value = {"Authorization": "Bearer token"}
    return m


@pytest.fixture
def mock_ad() -> MagicMock:
    m = MagicMock()
    m.create_account.return_value = True
    m.disable_account.return_value = True
    m.update_account.return_value = True
    m.move_to_ou.return_value = True
    m.account_exists.return_value = True
    m.account_active.return_value = True
    return m


@pytest.fixture
def mock_hengeone() -> AsyncMock:
    m = AsyncMock()
    m.provision_user.return_value = {"id": "ho-uid-456", "status": "active"}
    m.configure_mfa.return_value = True
    m.deprovision_user.return_value = {"status": "suspended"}
    m.user_exists.return_value = True
    m.account_active.return_value = True
    return m


@pytest.fixture
def engine(mock_entra, mock_ad, mock_hengeone) -> IdentityEngine:
    """モックコネクタを注入した IdentityEngine"""
    eng = IdentityEngine.__new__(IdentityEngine)
    eng.entra = mock_entra
    eng.ad = mock_ad
    eng.hengeone = mock_hengeone
    return eng


USER_DATA = {
    "username": "testuser",
    "display_name": "Test User",
    "email": "testuser@mirai-kensetsu.co.jp",
    "employee_id": "EMP001",
    "department": "Engineering",
}


# ============================================================
# provision_user テスト（ILM-001）
# ============================================================

class TestProvisionUser:
    """provision_user: 全システム正常プロビジョニング"""

    @pytest.mark.asyncio
    async def test_provision_success_all_systems(self, engine: IdentityEngine) -> None:
        """全3システムへのプロビジョニングが成功する"""
        result = await engine.provision_user(USER_DATA)

        assert result["entra"] is not None
        assert result["ad"] is not None
        assert result["hengeone"] is not None
        assert result["errors"] == []

    @pytest.mark.asyncio
    async def test_entra_user_created_with_license(
        self, engine: IdentityEngine, mock_entra: AsyncMock
    ) -> None:
        """EntraID ユーザ作成後にライセンス割当が呼ばれる"""
        await engine.provision_user(USER_DATA)

        mock_entra.create_user.assert_awaited_once_with(USER_DATA)
        mock_entra.assign_license.assert_awaited_once_with("entra-uid-123")

    @pytest.mark.asyncio
    async def test_hengeone_mfa_configured_after_provision(
        self, engine: IdentityEngine, mock_hengeone: AsyncMock
    ) -> None:
        """HENGEONE プロビジョニング後に MFA 設定が呼ばれる"""
        await engine.provision_user(USER_DATA)

        mock_hengeone.provision_user.assert_awaited_once_with(USER_DATA)
        mock_hengeone.configure_mfa.assert_awaited_once_with("ho-uid-456")

    @pytest.mark.asyncio
    async def test_entra_failure_continues_other_systems(
        self, engine: IdentityEngine, mock_entra: AsyncMock
    ) -> None:
        """EntraID 失敗でも AD / HENGEONE のプロビジョニングは継続される"""
        mock_entra.create_user.side_effect = Exception("Entra API error")

        result = await engine.provision_user(USER_DATA)

        assert len(result["errors"]) == 1
        assert "Entra ID" in result["errors"][0]
        assert result["ad"] is not None
        assert result["hengeone"] is not None

    @pytest.mark.asyncio
    async def test_ad_failure_continues_other_systems(
        self, engine: IdentityEngine, mock_ad: MagicMock
    ) -> None:
        """AD 失敗でも他システムのプロビジョニングは継続される"""
        mock_ad.create_account.side_effect = Exception("AD connection failed")

        result = await engine.provision_user(USER_DATA)

        assert len(result["errors"]) == 1
        assert "AD" in result["errors"][0]
        assert result["entra"] is not None
        assert result["hengeone"] is not None

    @pytest.mark.asyncio
    async def test_all_systems_fail_collects_all_errors(
        self,
        engine: IdentityEngine,
        mock_entra: AsyncMock,
        mock_ad: MagicMock,
        mock_hengeone: AsyncMock,
    ) -> None:
        """全システム失敗時は全エラーが収集される"""
        mock_entra.create_user.side_effect = Exception("Entra error")
        mock_ad.create_account.side_effect = Exception("AD error")
        mock_hengeone.provision_user.side_effect = Exception("HO error")

        result = await engine.provision_user(USER_DATA)

        assert len(result["errors"]) == 3

    @pytest.mark.asyncio
    async def test_entra_no_id_skips_license_assignment(
        self, engine: IdentityEngine, mock_entra: AsyncMock
    ) -> None:
        """EntraID がユーザ ID なし応答の場合ライセンス割当をスキップ"""
        mock_entra.create_user.return_value = {}  # id なし

        result = await engine.provision_user(USER_DATA)

        mock_entra.assign_license.assert_not_awaited()
        assert result["errors"] == []

    @pytest.mark.asyncio
    async def test_hengeone_no_id_skips_mfa_config(
        self, engine: IdentityEngine, mock_hengeone: AsyncMock
    ) -> None:
        """HENGEONE が ID なし応答の場合 MFA 設定をスキップ"""
        mock_hengeone.provision_user.return_value = {}  # id なし

        result = await engine.provision_user(USER_DATA)

        mock_hengeone.configure_mfa.assert_not_awaited()
        assert result["errors"] == []


# ============================================================
# deprovision_user テスト（ILM-003）
# ============================================================

class TestDeprovisionUser:
    """deprovision_user: 退職時 3システムアカウント無効化"""

    @pytest.mark.asyncio
    async def test_deprovision_all_systems(
        self,
        engine: IdentityEngine,
        mock_entra: AsyncMock,
        mock_ad: MagicMock,
        mock_hengeone: AsyncMock,
    ) -> None:
        """全3システムの無効化が実行される"""
        user_data = {
            "entra_object_id": "entra-123",
            "ad_dn": "CN=testuser,OU=Users,DC=mirai,DC=local",
            "hengeone_id": "ho-456",
        }
        result = await engine.deprovision_user(user_data)

        mock_entra.disable_user.assert_awaited_once_with("entra-123")
        mock_ad.disable_account.assert_called_once()
        mock_hengeone.deprovision_user.assert_awaited_once_with("ho-456")
        assert result["errors"] == []

    @pytest.mark.asyncio
    async def test_deprovision_skips_missing_ids(
        self,
        engine: IdentityEngine,
        mock_entra: AsyncMock,
        mock_ad: MagicMock,
        mock_hengeone: AsyncMock,
    ) -> None:
        """ID が指定されていないシステムはスキップされる"""
        user_data = {"entra_object_id": "entra-123"}  # ad_dn / hengeone_id なし

        await engine.deprovision_user(user_data)

        mock_entra.disable_user.assert_awaited_once()
        mock_ad.disable_account.assert_not_called()
        mock_hengeone.deprovision_user.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_deprovision_failure_collects_errors(
        self, engine: IdentityEngine, mock_entra: AsyncMock
    ) -> None:
        """無効化失敗はエラーとして収集される"""
        mock_entra.disable_user.side_effect = Exception("Entra disable error")

        result = await engine.deprovision_user({"entra_object_id": "entra-123"})

        assert len(result["errors"]) == 1
        assert "Entra ID 無効化失敗" in result["errors"][0]


# ============================================================
# transfer_user テスト（ILM-002）
# ============================================================

class TestTransferUser:
    """transfer_user: 異動処理（部署・役職変更）"""

    @pytest.mark.asyncio
    async def test_transfer_updates_ad_and_entra(
        self,
        engine: IdentityEngine,
        mock_ad: MagicMock,
    ) -> None:
        """AD の属性更新と Entra ID の更新が実行される"""
        user_data = {
            "ad_dn": "CN=testuser,OU=Users,DC=mirai,DC=local",
            "entra_object_id": "entra-123",
        }
        transfer_info = {
            "new_department": "Security",
            "new_job_title": "Security Engineer",
        }

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_resp = MagicMock()
            mock_resp.raise_for_status.return_value = None
            mock_client = AsyncMock()
            mock_client.patch.return_value = mock_resp
            mock_client_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=None)

            result = await engine.transfer_user(user_data, transfer_info)

        mock_ad.update_account.assert_called_once()
        assert result["ad"] == {"updated": True}
        assert result["entra"] == {"updated": True}
        assert result["errors"] == []

    @pytest.mark.asyncio
    async def test_transfer_moves_ou_when_specified(
        self, engine: IdentityEngine, mock_ad: MagicMock
    ) -> None:
        """new_ou が指定された場合 OU 移動が実行される"""
        user_data = {"ad_dn": "CN=testuser,OU=OldDept,DC=mirai,DC=local"}
        transfer_info = {
            "new_department": "Security",
            "new_ou": "OU=Security,OU=Users,DC=mirai,DC=local",
        }

        result = await engine.transfer_user(user_data, transfer_info)

        mock_ad.move_to_ou.assert_called_once()
        assert result["errors"] == []

    @pytest.mark.asyncio
    async def test_transfer_ad_failure_collects_error(
        self, engine: IdentityEngine, mock_ad: MagicMock
    ) -> None:
        """AD 異動処理失敗はエラーとして収集される"""
        mock_ad.update_account.side_effect = Exception("LDAP error")

        user_data = {"ad_dn": "CN=testuser,OU=Users,DC=mirai,DC=local"}
        transfer_info = {"new_department": "Finance"}

        result = await engine.transfer_user(user_data, transfer_info)

        assert len(result["errors"]) == 1
        assert "AD 異動処理失敗" in result["errors"][0]

    @pytest.mark.asyncio
    async def test_transfer_skips_ad_without_dn(
        self, engine: IdentityEngine, mock_ad: MagicMock
    ) -> None:
        """ad_dn がなければ AD 更新をスキップ"""
        user_data: dict = {}
        transfer_info = {"new_department": "Finance"}

        await engine.transfer_user(user_data, transfer_info)

        mock_ad.update_account.assert_not_called()


# ============================================================
# verify_consistency テスト（ILM-005）
# ============================================================

class TestVerifyConsistency:
    """verify_consistency: 3システム間の整合性確認"""

    @pytest.mark.asyncio
    async def test_consistency_check_all_systems(
        self,
        engine: IdentityEngine,
        mock_entra: AsyncMock,
        mock_ad: MagicMock,
        mock_hengeone: AsyncMock,
    ) -> None:
        """3システム全ての存在状態が返される"""
        result = await engine.verify_consistency("testuser")

        assert result["username"] == "testuser"
        assert "entra" in result
        assert "ad" in result
        assert "hengeone" in result

    @pytest.mark.asyncio
    async def test_consistency_active_user(
        self,
        engine: IdentityEngine,
        mock_entra: AsyncMock,
        mock_ad: MagicMock,
        mock_hengeone: AsyncMock,
    ) -> None:
        """全システムでアクティブなユーザの整合性確認"""
        result = await engine.verify_consistency("testuser")

        assert result["entra"]["exists"] is True
        assert result["entra"]["active"] is True
        assert result["ad"]["exists"] is True
        assert result["hengeone"]["exists"] is True

    @pytest.mark.asyncio
    async def test_consistency_email_format(
        self, engine: IdentityEngine, mock_entra: AsyncMock
    ) -> None:
        """Entra ID に対して正しいメールアドレス形式で問い合わせる"""
        await engine.verify_consistency("kensan")

        expected_email = "kensan@mirai-kensetsu.co.jp"
        mock_entra.user_exists.assert_awaited_once_with(expected_email)
        mock_entra.account_active.assert_awaited_once_with(expected_email)

    @pytest.mark.asyncio
    async def test_consistency_inactive_user_detected(
        self,
        engine: IdentityEngine,
        mock_entra: AsyncMock,
        mock_ad: MagicMock,
        mock_hengeone: AsyncMock,
    ) -> None:
        """一部システムで無効なユーザを正確に検出"""
        mock_entra.account_active.return_value = False
        mock_ad.account_active.return_value = True

        result = await engine.verify_consistency("inactiveuser")

        assert result["entra"]["active"] is False
        assert result["ad"]["active"] is True
