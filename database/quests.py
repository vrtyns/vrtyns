# ============================================================
#  database/quests.py
#  ระบบ Quest — admin สร้างและมอบ Quest ให้ user
# ============================================================

from .connection import get_conn


def create_tables():
    with get_conn() as conn:
        # ตาราง quest ทั้งหมดที่มีในเกม (admin สร้าง)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS quests (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                name        TEXT    NOT NULL,
                description TEXT    DEFAULT '',
                exp_reward  INTEGER DEFAULT 0,
                coin_reward INTEGER DEFAULT 0,
                created_at  TEXT    DEFAULT CURRENT_TIMESTAMP
            )
        """)
        # ตาราง quest ของ user แต่ละคน
        conn.execute("""
            CREATE TABLE IF NOT EXISTS user_quests (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id      TEXT    NOT NULL,
                quest_id     INTEGER NOT NULL,
                status       TEXT    DEFAULT 'active',   -- active | completed
                assigned_at  TEXT    DEFAULT CURRENT_TIMESTAMP,
                completed_at TEXT,
                FOREIGN KEY (quest_id) REFERENCES quests(id)
            )
        """)


# ── Admin Functions ────────────────────────────────────────

def create_quest(name: str, description: str, exp_reward: int, coin_reward: int) -> dict:
    """สร้าง Quest ใหม่ — คืน dict ของ Quest ที่สร้าง"""
    with get_conn() as conn:
        cur = conn.execute("""
            INSERT INTO quests (name, description, exp_reward, coin_reward)
            VALUES (?, ?, ?, ?)
        """, (name, description, exp_reward, coin_reward))
        row = conn.execute("SELECT * FROM quests WHERE id = ?", (cur.lastrowid,)).fetchone()
    return dict(row)


def get_all_quests() -> list:
    """ดูรายการ Quest ทั้งหมด (สำหรับ admin)"""
    with get_conn() as conn:
        rows = conn.execute("SELECT * FROM quests ORDER BY id DESC").fetchall()
    return [dict(r) for r in rows]


def assign_quest(user_id: str, quest_id: int) -> tuple[bool, str]:
    """มอบ Quest ให้ user"""
    with get_conn() as conn:
        quest = conn.execute("SELECT * FROM quests WHERE id = ?", (quest_id,)).fetchone()
        if not quest:
            return False, f"ไม่พบ Quest ID **{quest_id}**"

        already = conn.execute("""
            SELECT id FROM user_quests
            WHERE user_id = ? AND quest_id = ? AND status = 'active'
        """, (user_id, quest_id)).fetchone()
        if already:
            return False, "ผู้เล่นมี Quest นี้อยู่แล้ว!"

        conn.execute(
            "INSERT INTO user_quests (user_id, quest_id) VALUES (?, ?)",
            (user_id, quest_id)
        )
    return True, f"มอบ Quest **{dict(quest)['name']}** สำเร็จ!"


def complete_quest(user_id: str, quest_id: int) -> tuple[bool, str, dict]:
    """
    Admin ยืนยัน Quest สำเร็จ
    คืน: (success, message, quest_data)
    ถ้าสำเร็จ quest_data จะมี exp_reward และ coin_reward
    """
    with get_conn() as conn:
        row = conn.execute("""
            SELECT uq.id, q.name, q.exp_reward, q.coin_reward
            FROM user_quests uq
            JOIN quests q ON uq.quest_id = q.id
            WHERE uq.user_id = ? AND uq.quest_id = ? AND uq.status = 'active'
        """, (user_id, quest_id)).fetchone()

        if not row:
            return False, f"ไม่พบ Quest ID **{quest_id}** ที่ active ของผู้เล่นนี้", {}

        data = dict(row)
        conn.execute("""
            UPDATE user_quests
            SET status = 'completed', completed_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """, (data["id"],))

    return True, f"Quest **{data['name']}** สำเร็จ!", data


# ── User Functions ─────────────────────────────────────────

def get_user_quests(user_id: str, status: str | None = None) -> list:
    """ดู Quest ของ user — กรองตาม status ได้ (active | completed | None = ทั้งหมด)"""
    with get_conn() as conn:
        if status:
            rows = conn.execute("""
                SELECT uq.quest_id, uq.status, uq.assigned_at, uq.completed_at,
                       q.name, q.description, q.exp_reward, q.coin_reward
                FROM user_quests uq
                JOIN quests q ON uq.quest_id = q.id
                WHERE uq.user_id = ? AND uq.status = ?
                ORDER BY uq.assigned_at DESC
            """, (user_id, status)).fetchall()
        else:
            rows = conn.execute("""
                SELECT uq.quest_id, uq.status, uq.assigned_at, uq.completed_at,
                       q.name, q.description, q.exp_reward, q.coin_reward
                FROM user_quests uq
                JOIN quests q ON uq.quest_id = q.id
                WHERE uq.user_id = ?
                ORDER BY uq.status ASC, uq.assigned_at DESC
            """, (user_id,)).fetchall()
    return [dict(r) for r in rows]
