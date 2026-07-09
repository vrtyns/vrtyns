# ============================================================
#  database/buffs.py
#  ระบบ Buff / Debuff — เก็บ effect ที่มีระยะเวลาของ user
# ============================================================

from .connection import get_conn
from datetime import datetime, timezone, timedelta

TH_TZ = timezone(timedelta(hours=7))


def create_table():
    with get_conn() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS user_buffs (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id     TEXT    NOT NULL,
                buff_type   TEXT    NOT NULL,   -- dice_bonus, atk_bonus, vit_bonus, fire_resist, max_hp_bonus, max_mana_bonus
                value       REAL    DEFAULT 0,  -- ค่าของ buff เช่น +1, +20, +50
                description TEXT    DEFAULT '',  -- ข้อความแสดงผล
                expires_at  REAL,               -- Unix timestamp, NULL = ไม่มีกำหนดหมดอายุ
                is_debuff   INTEGER DEFAULT 0   -- 0=buff, 1=debuff
            )
        """)


def _now_ts() -> float:
    return datetime.now(TH_TZ).timestamp()


def add_buff(
    user_id: str,
    buff_type: str,
    value: float,
    description: str,
    expires_at: float | None,
    is_debuff: bool = False,
) -> dict:
    """
    เพิ่ม buff ให้ user
    ถ้ามี buff ชนิดเดิมอยู่แล้ว → refresh (อัปเดตแทนเพิ่มใหม่)
    buff ที่เพิ่ม max_hp / max_mana จะอัปเดต stats ใน users ทันที
    """
    with get_conn() as conn:
        # ตรวจว่ามีอยู่แล้วไหม
        existing = conn.execute("""
            SELECT id FROM user_buffs
            WHERE user_id = ? AND buff_type = ? AND is_debuff = ?
            AND (expires_at IS NULL OR expires_at > ?)
        """, (user_id, buff_type, int(is_debuff), _now_ts())).fetchone()

        if existing:
            # refresh — อัปเดต value และ expires_at
            conn.execute("""
                UPDATE user_buffs SET value = ?, description = ?, expires_at = ?
                WHERE id = ?
            """, (value, description, expires_at, existing["id"]))
            row = conn.execute(
                "SELECT * FROM user_buffs WHERE id = ?", (existing["id"],)
            ).fetchone()
        else:
            # buff ใหม่ — อัปเดต stat ถ้าจำเป็น
            if buff_type == "max_hp_bonus":
                conn.execute(
                    "UPDATE users SET hp_max = hp_max + ? WHERE user_id = ?",
                    (int(value), user_id)
                )
            elif buff_type == "max_mana_bonus":
                conn.execute(
                    "UPDATE users SET mana_max = mana_max + ? WHERE user_id = ?",
                    (int(value), user_id)
                )

            cur = conn.execute("""
                INSERT INTO user_buffs
                    (user_id, buff_type, value, description, expires_at, is_debuff)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (user_id, buff_type, value, description, expires_at, int(is_debuff)))
            row = conn.execute(
                "SELECT * FROM user_buffs WHERE id = ?", (cur.lastrowid,)
            ).fetchone()

    return dict(row)


def get_active_buffs(user_id: str) -> list:
    """ดึง buff/debuff ที่ยังไม่หมดอายุทั้งหมดของ user"""
    now = _now_ts()
    with get_conn() as conn:
        rows = conn.execute("""
            SELECT * FROM user_buffs
            WHERE user_id = ?
            AND (expires_at IS NULL OR expires_at > ?)
            ORDER BY is_debuff ASC, expires_at ASC
        """, (user_id, now)).fetchall()
    return [dict(r) for r in rows]


def has_buff(user_id: str, buff_type: str) -> bool:
    """ตรวจว่า user มี buff ชนิดนี้อยู่หรือเปล่า"""
    now = _now_ts()
    with get_conn() as conn:
        row = conn.execute("""
            SELECT id FROM user_buffs
            WHERE user_id = ? AND buff_type = ? AND is_debuff = 0
            AND (expires_at IS NULL OR expires_at > ?)
        """, (user_id, buff_type, now)).fetchone()
    return row is not None


def get_buff_value(user_id: str, buff_type: str) -> float:
    """ดึงค่าของ buff ที่ active อยู่"""
    now = _now_ts()
    with get_conn() as conn:
        row = conn.execute("""
            SELECT value FROM user_buffs
            WHERE user_id = ? AND buff_type = ? AND is_debuff = 0
            AND (expires_at IS NULL OR expires_at > ?)
        """, (user_id, buff_type, now)).fetchone()
    return row["value"] if row else 0.0

def get_dice_modifier(user_id: str) -> int:
    """รวมค่าเต๋าทั้งหมด — บวก buff, ลบ debuff"""
    now = _now_ts()
    with get_conn() as conn:
        rows = conn.execute("""
            SELECT value, is_debuff FROM user_buffs
            WHERE user_id = ? AND buff_type = 'dice_bonus'
            AND (expires_at IS NULL OR expires_at > ?)
        """, (user_id, now)).fetchall()
    total = 0
    for r in rows:
        total += -int(r["value"]) if r["is_debuff"] else int(r["value"])
    return total


def clear_debuff(user_id: str) -> str | None:
    """ล้าง debuff เก่าที่สุด 1 ตัว — คืนชื่อที่ล้าง หรือ None ถ้าไม่มี"""
    now = _now_ts()
    with get_conn() as conn:
        row = conn.execute("""
            SELECT id, description FROM user_buffs
            WHERE user_id = ? AND is_debuff = 1
            AND (expires_at IS NULL OR expires_at > ?)
            ORDER BY id ASC LIMIT 1
        """, (user_id, now)).fetchone()
        if not row:
            return None
        conn.execute("DELETE FROM user_buffs WHERE id = ?", (row["id"],))
    return row["description"] or "ดีบัฟ"


def remove_expired_buffs(user_id: str | None = None):
    """
    ลบ buff ที่หมดอายุแล้ว + คืนค่า max_hp / max_mana ถ้าจำเป็น
    user_id = None → ทำทุก user (เรียกจาก background task ทุก 1 นาที)
    """
    now = _now_ts()
    with get_conn() as conn:
        query = "SELECT * FROM user_buffs WHERE expires_at IS NOT NULL AND expires_at <= ?"
        params = [now]
        if user_id:
            query += " AND user_id = ?"
            params.append(user_id)
        expired = conn.execute(query, params).fetchall()

        for row in expired:
            # คืน max_hp เมื่อ buff หมด
            if row["buff_type"] == "max_hp_bonus":
                conn.execute("""
                    UPDATE users SET
                        hp_max = MAX(100, hp_max - ?),
                        hp     = MIN(hp, MAX(100, hp_max - ?))
                    WHERE user_id = ?
                """, (int(row["value"]), int(row["value"]), row["user_id"]))

            # คืน max_mana เมื่อ buff หมด
            elif row["buff_type"] == "max_mana_bonus":
                conn.execute("""
                    UPDATE users SET
                        mana_max = MAX(80, mana_max - ?),
                        mana     = MIN(mana, MAX(80, mana_max - ?))
                    WHERE user_id = ?
                """, (int(row["value"]), int(row["value"]), row["user_id"]))

        # ลบทั้งหมดในครั้งเดียว
        delete_query = "DELETE FROM user_buffs WHERE expires_at IS NOT NULL AND expires_at <= ?"
        delete_params = [now]
        if user_id:
            delete_query += " AND user_id = ?"
            delete_params.append(user_id)
        conn.execute(delete_query, delete_params)
