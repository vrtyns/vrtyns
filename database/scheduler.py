# ============================================================
#  database/scheduler.py
#  ตาราง scheduled_messages — เก็บข้อความอัตโนมัติที่ตั้งเวลา
# ============================================================

from .connection import get_conn
from datetime import datetime, timezone, timedelta
TH_TZ = timezone(timedelta(hours=7))


def create_table():
    with get_conn() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS scheduled_messages (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                channel_id TEXT    NOT NULL,
                message    TEXT    NOT NULL,
                hour       INTEGER NOT NULL,   -- 0-23 (UTC)
                minute     INTEGER DEFAULT 0,  -- 0-59
                enabled    INTEGER DEFAULT 1,  -- 1=เปิด, 0=ปิด
                created_at TEXT    DEFAULT CURRENT_TIMESTAMP
            )
        """)


def add_schedule(channel_id: str, message: str, hour: int, minute: int) -> dict:
    """เพิ่มข้อความอัตโนมัติใหม่"""
    with get_conn() as conn:
        cur = conn.execute(
            "INSERT INTO scheduled_messages (channel_id, message, hour, minute) VALUES (?, ?, ?, ?)",
            (channel_id, message, hour, minute)
        )
        row = conn.execute(
            "SELECT * FROM scheduled_messages WHERE id = ?", (cur.lastrowid,)
        ).fetchone()
    return dict(row)


def get_all_schedules() -> list:
    """ดูรายการข้อความอัตโนมัติทั้งหมด"""
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM scheduled_messages ORDER BY hour, minute"
        ).fetchall()
    return [dict(r) for r in rows]


def remove_schedule(schedule_id: int) -> bool:
    """ลบข้อความอัตโนมัติตาม ID — คืน False ถ้าไม่พบ"""
    with get_conn() as conn:
        result = conn.execute(
            "DELETE FROM scheduled_messages WHERE id = ?", (schedule_id,)
        )
    return result.rowcount > 0


def get_due_messages(hour: int, minute: int) -> list:
    """ดึงข้อความที่ถึงเวลาส่งแล้ว ณ ชั่วโมง:นาที นั้น"""
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM scheduled_messages WHERE hour = ? AND minute = ? AND enabled = 1",
            (hour, minute)
        ).fetchall()
    return [dict(r) for r in rows]
