"""
ポリシーエンジン単体テスト
"""

import pytest

from engine.policy_engine import PolicyEngine, AccessRequest


@pytest.fixture
def engine() -> PolicyEngine:
    return PolicyEngine()


class TestSoDViolations:
    """職務分離（SoD）テスト"""

    def test_requester_cannot_be_approver(self, engine: PolicyEngine) -> None:
        """申請者は承認者になれない"""
        request = AccessRequest(
            user_id="u",
            requested_role="Approver",
            current_roles=["Requester"],
        )
        decision = engine.evaluate_access(request)
        assert not decision.allowed
        assert "Approver" in decision.sod_conflicts[0]

    def test_developer_cannot_deploy_to_prod(self, engine: PolicyEngine) -> None:
        """開発者は本番デプロイ権限を取得できない"""
        request = AccessRequest(
            user_id="u",
            requested_role="ProductionDeployer",
            current_roles=["Developer"],
        )
        decision = engine.evaluate_access(request)
        assert not decision.allowed
        assert len(decision.sod_conflicts) > 0

    def test_no_sod_conflict_allowed(self, engine: PolicyEngine) -> None:
        """SoD 競合がないロールは付与可能"""
        request = AccessRequest(
            user_id="u",
            requested_role="ReadOnly",
            current_roles=["Developer"],
            mfa_verified=True,
        )
        decision = engine.evaluate_access(request)
        assert decision.allowed

    def test_check_sod_violations_bulk(self, engine: PolicyEngine) -> None:
        """ロール一覧全体の SoD 違反検出"""
        violations = engine.check_sod_violations(["Requester", "Approver", "Developer"])
        assert len(violations) == 1
        assert violations[0] == ("Requester", "Approver")

    def test_no_violations_on_clean_roles(self, engine: PolicyEngine) -> None:
        """競合のないロールリストは違反なし"""
        violations = engine.check_sod_violations(["Developer", "ReadOnly"])
        assert violations == []


class TestConditionalAccess:
    """条件付きアクセスポリシーテスト"""

    def test_global_admin_requires_mfa(self, engine: PolicyEngine) -> None:
        """GlobalAdmin は MFA 必須"""
        request = AccessRequest(
            user_id="u",
            requested_role="GlobalAdmin",
            current_roles=[],
            mfa_verified=False,
            compliant_device=True,
        )
        decision = engine.evaluate_access(request)
        assert not decision.allowed
        assert any("MFA" in c for c in decision.required_conditions)

    def test_global_admin_requires_compliant_device(self, engine: PolicyEngine) -> None:
        """GlobalAdmin は準拠デバイス必須"""
        request = AccessRequest(
            user_id="u",
            requested_role="GlobalAdmin",
            current_roles=[],
            mfa_verified=True,
            compliant_device=False,
        )
        decision = engine.evaluate_access(request)
        assert not decision.allowed
        assert any("準拠デバイス" in c for c in decision.required_conditions)

    def test_global_admin_allowed_with_all_conditions(self, engine: PolicyEngine) -> None:
        """GlobalAdmin は MFA + 準拠デバイスで付与可能"""
        request = AccessRequest(
            user_id="u",
            requested_role="GlobalAdmin",
            current_roles=[],
            mfa_verified=True,
            compliant_device=True,
        )
        decision = engine.evaluate_access(request)
        assert decision.allowed


class TestRoleLimit:
    """ロール数上限テスト"""

    def test_max_roles_exceeded(self, engine: PolicyEngine) -> None:
        """ロール数上限超過は拒否"""
        request = AccessRequest(
            user_id="u",
            requested_role="NewRole",
            current_roles=[f"Role{i}" for i in range(10)],  # MAX_ROLES = 10
        )
        decision = engine.evaluate_access(request)
        assert not decision.allowed
        assert "上限" in decision.reason
