# ============================================================
#  database/daily.py
#  ระบบ Daily Reward — เคลมได้วันละครั้ง (รีเซ็ตตี 0:00 UTC)
# ============================================================

from .connection import get_conn
from datetime import datetime, timezone, timedelta

TH_TZ = timezone(timedelta(hours=7))

def _today() -> str:
    return datetime.now(TH_TZ).strftime("%Y-%m-%d")  # เดิมใช้ timezone.utc

def _yesterday() -> str:
    return (datetime.now(TH_TZ) - timedelta(days=1)).strftime("%Y-%m-%d")

def can_claim(user_id: str) -> tuple[bool, int]:
    ...
    # คำนวณเวลาที่เหลือจนถึงเที่ยงคืนเวลาไทย
    now        = datetime.now(TH_TZ)
    midnight   = datetime(now.year, now.month, now.day, tzinfo=TH_TZ)
    next_reset = midnight + timedelta(days=1)
    hours_left = int((next_reset - now).total_seconds() // 3600) + 1
    ...
    
    today = _today()
    with get_conn() as conn:
        row = conn.execute(
            "SELECT last_claimed FROM daily_claims WHERE user_id = ?", (user_id,)
        ).fetchone()

    if not row or row["last_claimed"] != today:
        return True, 0

    # คำนวณเวลาที่เหลือจนถึงตี 0 UTC
    now      = datetime.now(timezone.utc)
    midnight = datetime(now.year, now.month, now.day, tzinfo=timezone.utc)
    from datetime import timedelta
    next_reset   = midnight + timedelta(days=1)
    hours_left   = int((next_reset - now).total_seconds() // 3600) + 1
    return False, hours_left


def do_claim(user_id: str) -> int:
    """
    บันทึกการเคลมวันนี้ และคำนวณ streak
    คืน: streak ปัจจุบัน
    """
    today = _today()
    with get_conn() as conn:
        row = conn.execute(
            "SELECT last_claimed, streak FROM daily_claims WHERE user_id = ?", (user_id,)
        ).fetchone()

        if not row:
            # เคลมครั้งแรก
            conn.execute(
                "INSERT INTO daily_claims (user_id, last_claimed, streak) VALUES (?, ?, 1)",
                (user_id, today)
            )
            return 1

        # เคลมวันก่อนหน้า → streak ต่อเนื่อง, อื่นนั้น → reset
        new_streak = row["streak"] + 1 if row["last_claimed"] == _yesterday() else 1
        conn.execute(
            "UPDATE daily_claims SET last_claimed = ?, streak = ? WHERE user_id = ?",
            (today, new_streak, user_id)
        )
        return new_streak


def get_streak(user_id: str) -> int:
    """ดู streak ปัจจุบันของ user"""
    with get_conn() as conn:
        row = conn.execute(
            "SELECT streak, last_claimed FROM daily_claims WHERE user_id = ?", (user_id,)
        ).fetchone()
    if not row:
        return 0
    # ถ้าไม่ได้เคลมเมื่อวาน streak หายแล้ว
    if row["last_claimed"] not in (_today(), _yesterday()):
        return 0
    return row["streak"]
