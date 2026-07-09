# ============================================================
#  database/skills.py
#  ตาราง skills — เก็บรายการสกิลของ user แต่ละคน
#  admin เป็นคนเพิ่ม/ลบเท่านั้น user ดูได้อย่างเดียว
# ============================================================

from .connection import get_conn


def create_table():
    with get_conn() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS skills (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id     TEXT    NOT NULL,
                name        TEXT    NOT NULL,   -- ชื่อสกิล
                description TEXT    DEFAULT '',  -- คำอธิบายสกิล
                added_at    TEXT    DEFAULT CURRENT_TIMESTAMP
            )
        """)


def add_skill(user_id: str, name: str, description: str = "") -> dict:
    """เพิ่มสกิลให้ user — คืน dict ของสกิลที่เพิ่ม"""
    with get_conn() as conn:
        cur = conn.execute(
            "INSERT INTO skills (user_id, name, description) VALUES (?, ?, ?)",
            (user_id, name, description)
        )
        row = conn.execute(
            "SELECT * FROM skills WHERE id = ?", (cur.lastrowid,)
        ).fetchone()
    return dict(row)


def remove_skill(skill_id: int, user_id: str) -> bool:
    """ลบสกิลตาม ID — ต้องระบุ user_id ด้วยเพื่อป้องกันลบข้ามคน"""
    with get_conn() as conn:
        result = conn.execute(
            "DELETE FROM skills WHERE id = ? AND user_id = ?",
            (skill_id, user_id)
        )
    return result.rowcount > 0


def get_skills(user_id: str) -> list:
    """ดูสกิลทั้งหมดของ user"""
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM skills WHERE user_id = ? ORDER BY added_at ASC",
            (user_id,)
        ).fetchall()
    return [dict(r) for r in rows]
