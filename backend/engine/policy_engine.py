"""
ポリシーエンジン
RBAC/ABAC ポリシー評価および職務分離（SoD）チェック
設計仕様書 5.3 / GOV-002 準拠
"""

import logging
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

# 職務分離（SoD）が禁止されているロールの組み合わせ
# 同一ユーザが同時に保持できないロールペア
SOD_CONFLICT_PAIRS: list[tuple[str, str]] = [
    ("Requester", "Approver"),          # 自己承認防止
    ("Developer", "ProductionDeployer"), # 開発・本番デプロイ分離
    ("FinanceUser", "FinanceAuditor"),   # 財務操作・監査分離
    ("UserAdmin", "AuditAdmin"),         # ユーザ管理・監査管理分離
]

# 条件付きアクセスポリシー
# { role_name: { required_condition: value } }
CONDITIONAL_ACCESS_POLICIES: dict[str, dict] = {
    "GlobalAdmin": {"mfa_required": True, "compliant_device": True},
    "PrivilegedRoleAdmin": {"mfa_required": True, "compliant_device": True},
    "SecurityAdmin": {"mfa_required": True},
    "FinanceAuditor": {"mfa_required": True},
}

# 最大同時保持ロール数
MAX_ROLES_PER_USER = 10


@dataclass
class AccessRequest:
    """アクセス評価リクエスト"""

    user_id: str
    requested_role: str
    current_roles: list[str] = field(default_factory=list)
    mfa_verified: bool = False
    compliant_device: bool = False
    justification: str = ""


@dataclass
class PolicyDecision:
    """ポリシー評価結果"""

    allowed: bool
    reason: str
    required_conditions: list[str] = field(default_factory=list)
    sod_conflicts: list[str] = field(default_factory=list)


class PolicyEngine:
    """
    RBAC + ABAC ポリシー評価エンジン

    評価順:
    1. ロール数上限チェック
    2. 職務分離（SoD）チェック
    3. 条件付きアクセスポリシーチェック
    """

    def evaluate_access(self, request: AccessRequest) -> PolicyDecision:
        """
        ロール付与リクエストを評価する。

        全チェックが通過した場合のみ allowed=True を返す。
        """
        # ① ロール数上限
        if len(request.current_roles) >= MAX_ROLES_PER_USER:
            return PolicyDecision(
                allowed=False,
                reason=f"ロール保持数が上限 ({MAX_ROLES_PER_USER}) に達しています",
            )

        # ② SoD チェック
        sod_conflicts = self._check_sod(
            request.requested_role, request.current_roles
        )
        if sod_conflicts:
            return PolicyDecision(
                allowed=False,
                reason="職務分離ポリシー違反",
                sod_conflicts=sod_conflicts,
            )

        # ③ 条件付きアクセスポリシー
        unmet_conditions = self._check_conditional_access(
            request.requested_role, request.mfa_verified, request.compliant_device
        )
        if unmet_conditions:
            return PolicyDecision(
                allowed=False,
                reason="条件付きアクセスポリシー未充足",
                required_conditions=unmet_conditions,
            )

        logger.info(
            "Access granted by policy engine",
            extra={
                "user_id": request.user_id,
                "role": request.requested_role,
            },
        )
        return PolicyDecision(allowed=True, reason="全ポリシーチェック通過")

    def check_sod_violations(self, roles: list[str]) -> list[tuple[str, str]]:
        """
        ユーザが保持するロールリスト全体の SoD 違反を検出する。
        棚卸処理（ILM-005）から呼び出される。
        """
        violations: list[tuple[str, str]] = []
        role_set = set(roles)

        for role_a, role_b in SOD_CONFLICT_PAIRS:
            if role_a in role_set and role_b in role_set:
                violations.append((role_a, role_b))

        return violations

    # ------------------------------------------------------------------
    # プライベートヘルパー
    # ------------------------------------------------------------------

    @staticmethod
    def _check_sod(requested_role: str, current_roles: list[str]) -> list[str]:
        """要求ロールと既存ロールの SoD 競合を返す"""
        conflicts: list[str] = []
        for role_a, role_b in SOD_CONFLICT_PAIRS:
            if requested_role == role_a and role_b in current_roles:
                conflicts.append(f"{role_a} と {role_b} は同時付与不可")
            elif requested_role == role_b and role_a in current_roles:
                conflicts.append(f"{role_b} と {role_a} は同時付与不可")
        return conflicts

    @staticmethod
    def _check_conditional_access(
        role: str, mfa_verified: bool, compliant_device: bool
    ) -> list[str]:
        """条件付きアクセスポリシーの未充足条件を返す"""
        policy = CONDITIONAL_ACCESS_POLICIES.get(role, {})
        unmet: list[str] = []

        if policy.get("mfa_required") and not mfa_verified:
            unmet.append("MFA 認証が必要です")

        if policy.get("compliant_device") and not compliant_device:
            unmet.append("準拠デバイスからのアクセスが必要です")

        return unmet
