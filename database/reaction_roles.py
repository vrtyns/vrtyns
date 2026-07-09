# ============================================================
#  database/reaction_roles.py
#  ตาราง reaction_roles — เก็บการตั้งค่า reaction role
# ============================================================

from .connection import get_conn


def create_table():
    with get_conn() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS reaction_roles (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                channel_id TEXT    NOT NULL,  -- channel ที่ message อยู่
                message_id TEXT    NOT NULL,  -- message ที่ให้ react
                emoji      TEXT    NOT NULL,  -- emoji ที่ใช้ (unicode หรือ custom id)
                role_id    TEXT    NOT NULL,  -- role ที่จะให้/ลบ
                UNIQUE(message_id, emoji)     -- message เดียวกัน emoji ซ้ำไม่ได้
            )
        """)


def add_reaction_role(channel_id: str, message_id: str, emoji: str, role_id: str) -> tuple[bool, str]:
    """เพิ่ม reaction role — คืน (success, message)"""
    try:
        with get_conn() as conn:
            cur = conn.execute("""
                INSERT INTO reaction_roles (channel_id, message_id, emoji, role_id)
                VALUES (?, ?, ?, ?)
            """, (channel_id, message_id, emoji, role_id))
        return True, str(cur.lastrowid)
    except Exception:
        return False, "emoji นี้ถูกตั้งค่าไว้กับ message นี้แล้ว"


def remove_reaction_role(rr_id: int) -> bool:
    """ลบ reaction role ตาม ID — คืน False ถ้าไม่พบ"""
    with get_conn() as conn:
        result = conn.execute(
            "DELETE FROM reaction_roles WHERE id = ?", (rr_id,)
        )
    return result.rowcount > 0


def get_all_reaction_roles() -> list:
    """ดูรายการทั้งหมด (สำหรับ admin)"""
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM reaction_roles ORDER BY message_id"
        ).fetchall()
    return [dict(r) for r in rows]


def get_role_for_reaction(message_id: str, emoji: str) -> str | None:
    """
    หา role_id จาก message_id + emoji
    ใช้ตอน on_raw_reaction_add/remove
    คืน role_id หรือ None ถ้าไม่พบ
    """
    with get_conn() as conn:
        row = conn.execute("""
            SELECT role_id FROM reaction_roles
            WHERE message_id = ? AND emoji = ?
        """, (message_id, emoji)).fetchone()
    return row["role_id"] if row else None
