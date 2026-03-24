"""
リスクエンジン単体テスト
"""

import pytest
from datetime import datetime, timezone

from engine.risk_engine import RiskEngine, RiskContext, THRESHOLD_BLOCK, THRESHOLD_MFA


@pytest.fixture
def engine() -> RiskEngine:
    return RiskEngine()


class TestRiskEngineDecisions:
    """リスク判定の境界値テスト"""

    def test_low_risk_allow(self, engine: RiskEngine) -> None:
        """内部 IP + MFA 有効 + 業務時間内 → allow"""
        ctx = RiskContext(
            user_id="user-1",
            source_ip="192.168.1.1",
            mfa_enabled=True,
            failed_login_count=0,
            # 業務時間内（JST 10:00 月曜）
            access_time=datetime(2025, 6, 2, 1, 0, tzinfo=timezone.utc),  # UTC 01:00 = JST 10:00
        )
        result = engine.evaluate(ctx)
        assert result.decision == "allow"
        assert result.score < THRESHOLD_MFA

    def test_medium_risk_mfa_required(self, engine: RiskEngine) -> None:
        """外部 IP + 業務時間外 → mfa_required"""
        ctx = RiskContext(
            user_id="user-2",
            source_ip="203.0.113.10",  # 外部 IP
            mfa_enabled=True,
            failed_login_count=0,
            access_time=datetime(2025, 6, 7, 10, 0, tzinfo=timezone.utc),  # 土曜
        )
        result = engine.evaluate(ctx)
        assert result.decision == "mfa_required"
        assert THRESHOLD_MFA <= result.score < THRESHOLD_BLOCK

    def test_high_risk_block(self, engine: RiskEngine) -> None:
        """外部 IP + MFA 未設定 + 高権限 + ログイン失敗 → block"""
        ctx = RiskContext(
            user_id="user-3",
            source_ip="203.0.113.99",
            mfa_enabled=False,
            requested_role="GlobalAdmin",
            failed_login_count=5,
            access_time=datetime(2025, 6, 7, 10, 0, tzinfo=timezone.utc),  # 土曜
        )
        result = engine.evaluate(ctx)
        assert result.decision == "block"
        assert result.score >= THRESHOLD_BLOCK

    def test_unknown_ip_adds_risk(self, engine: RiskEngine) -> None:
        """IP 不明はリスク加算される"""
        ctx_with_ip = RiskContext(user_id="u", source_ip="192.168.1.1", mfa_enabled=True)
        ctx_no_ip = RiskContext(user_id="u", source_ip=None, mfa_enabled=True)

        assert engine.evaluate(ctx_no_ip).score > engine.evaluate(ctx_with_ip).score

    def test_score_clamped_to_100(self, engine: RiskEngine) -> None:
        """スコアは 100 を超えない"""
        ctx = RiskContext(
            user_id="u",
            source_ip="203.0.113.1",
            mfa_enabled=False,
            requested_role="GlobalAdmin",
            failed_login_count=10,
            base_risk_score=80,
            access_time=datetime(2025, 6, 7, 10, 0, tzinfo=timezone.utc),
        )
        result = engine.evaluate(ctx)
        assert result.score <= 100

    def test_factors_are_populated(self, engine: RiskEngine) -> None:
        """リスク要因リストが適切に記録される"""
        ctx = RiskContext(
            user_id="u",
            source_ip="203.0.113.1",
            mfa_enabled=False,
        )
        result = engine.evaluate(ctx)
        assert len(result.factors) > 0


class TestOffHoursDetection:
    """業務時間外検出テスト"""

    def test_weekday_business_hours_is_not_off_hours(self, engine: RiskEngine) -> None:
        """平日業務時間（JST 10:00）はリスクなし"""
        ctx = RiskContext(
            user_id="u",
            source_ip="192.168.1.1",
            access_time=datetime(2025, 6, 2, 1, 0, tzinfo=timezone.utc),  # JST 10:00 月曜
        )
        result = engine.evaluate(ctx)
        # 業務時間外リスクは加算されない
        assert not any("業務時間外" in f for f in result.factors)

    def test_weekend_is_off_hours(self, engine: RiskEngine) -> None:
        """土曜日はリスク加算される"""
        ctx = RiskContext(
            user_id="u",
            source_ip="192.168.1.1",
            access_time=datetime(2025, 6, 7, 1, 0, tzinfo=timezone.utc),  # 土曜
        )
        result = engine.evaluate(ctx)
        assert any("業務時間外" in f for f in result.factors)
