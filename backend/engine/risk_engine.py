"""
リスクスコアエンジン
ゼロトラスト原則に基づくアクセスリスク評価
設計仕様書 5.1 準拠

スコア範囲: 0-100
  < 30: 通常許可
 30-70: 追加 MFA 要求
  > 70: アクセスブロック
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from ipaddress import IPv4Address, IPv6Address, ip_address

logger = logging.getLogger(__name__)

# リスクスコア閾値
THRESHOLD_BLOCK = 70
THRESHOLD_MFA = 30

# 既知の社内 IP レンジ（設定ファイル移行推奨）
INTERNAL_IP_RANGES = [
    "10.0.0.0/8",
    "172.16.0.0/12",
    "192.168.0.0/16",
]

# 業務時間外リスク加算
OFF_HOURS_SCORE = 15

# 高権限ロールによるリスク加算
HIGH_PRIV_ROLES = {"GlobalAdmin", "PrivilegedRoleAdmin", "SecurityAdmin"}
HIGH_PRIV_SCORE = 20

# MFA 未設定リスク加算
NO_MFA_SCORE = 25

# 連続失敗ログインリスク加算
FAILED_LOGIN_SCORE_PER_ATTEMPT = 10
MAX_FAILED_LOGIN_SCORE = 40


@dataclass
class RiskContext:
    """リスク評価コンテキスト"""

    user_id: str
    source_ip: str | None = None
    user_agent: str | None = None
    requested_role: str | None = None
    mfa_enabled: bool = True
    failed_login_count: int = 0
    access_time: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    # ユーザの既存リスクスコア（DB から取得）
    base_risk_score: int = 0


@dataclass
class RiskEvaluation:
    """リスク評価結果"""

    score: int
    decision: str  # "allow" | "mfa_required" | "block"
    factors: list[str] = field(default_factory=list)

    @property
    def is_blocked(self) -> bool:
        return self.decision == "block"

    @property
    def requires_mfa(self) -> bool:
        return self.decision == "mfa_required"


class RiskEngine:
    """ゼロトラストリスクスコア評価エンジン（設計仕様書 5.1）"""

    def evaluate(self, ctx: RiskContext) -> RiskEvaluation:
        """
        複数のリスク要素を評価しスコアを算出する。

        スコア = base_risk_score + 各リスク加算の合計（0-100 でクランプ）
        """
        score = ctx.base_risk_score
        factors: list[str] = []

        # ① ソース IP 評価
        ip_score, ip_factor = self._evaluate_ip(ctx.source_ip)
        score += ip_score
        if ip_factor:
            factors.append(ip_factor)

        # ② アクセス時間評価（業務時間外）
        if self._is_off_hours(ctx.access_time):
            score += OFF_HOURS_SCORE
            factors.append(f"業務時間外アクセス (+{OFF_HOURS_SCORE})")

        # ③ 高権限ロール要求
        if ctx.requested_role and ctx.requested_role in HIGH_PRIV_ROLES:
            score += HIGH_PRIV_SCORE
            factors.append(f"高権限ロール要求: {ctx.requested_role} (+{HIGH_PRIV_SCORE})")

        # ④ MFA 未設定
        if not ctx.mfa_enabled:
            score += NO_MFA_SCORE
            factors.append(f"MFA 未設定 (+{NO_MFA_SCORE})")

        # ⑤ 連続ログイン失敗
        if ctx.failed_login_count > 0:
            failed_score = min(
                ctx.failed_login_count * FAILED_LOGIN_SCORE_PER_ATTEMPT,
                MAX_FAILED_LOGIN_SCORE,
            )
            score += failed_score
            factors.append(
                f"ログイン失敗 {ctx.failed_login_count}回 (+{failed_score})"
            )

        # スコアを 0-100 にクランプ
        score = max(0, min(100, score))

        # 判定
        if score >= THRESHOLD_BLOCK:
            decision = "block"
        elif score >= THRESHOLD_MFA:
            decision = "mfa_required"
        else:
            decision = "allow"

        result = RiskEvaluation(score=score, decision=decision, factors=factors)
        logger.info(
            "Risk evaluation completed",
            extra={
                "user_id": ctx.user_id,
                "score": score,
                "decision": decision,
                "factors": factors,
            },
        )
        return result

    # ------------------------------------------------------------------
    # プライベートヘルパー
    # ------------------------------------------------------------------

    @staticmethod
    def _evaluate_ip(source_ip: str | None) -> tuple[int, str]:
        """IP アドレスのリスク加算を評価する"""
        if not source_ip:
            return 10, "ソース IP 不明 (+10)"

        try:
            addr: IPv4Address | IPv6Address = ip_address(source_ip)
        except ValueError:
            return 10, f"不正な IP 形式: {source_ip} (+10)"

        import ipaddress

        for cidr in INTERNAL_IP_RANGES:
            if addr in ipaddress.ip_network(cidr, strict=False):
                return 0, ""  # 社内 IP はリスクなし

        # 外部 IP
        return 20, f"外部 IP からのアクセス: {source_ip} (+20)"

    @staticmethod
    def _is_off_hours(access_time: datetime) -> bool:
        """業務時間外（平日 9:00-18:00 JST 以外）かどうかを判定"""
        # UTC → JST (+9h) 変換
        jst_hour = (access_time.hour + 9) % 24
        weekday = access_time.weekday()  # 0=月曜, 6=日曜

        is_weekend = weekday >= 5
        is_night = not (9 <= jst_hour < 18)

        return is_weekend or is_night
