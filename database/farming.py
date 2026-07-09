# ============================================================
#  database/farming.py
#  ตาราง farming — เก็บข้อมูลการปลูกพืชและเวลาเก็บเกี่ยว
# ============================================================

from .connection import get_conn
from datetime import datetime


# ── ข้อมูลพืชแต่ละชนิด ───────────────────────────────────
PLANTS: dict = {
    "tomato": {
        "name":         "มะเขือเทศ",
        "emoji":        "🍅",
        "seed_id":      "seed_tomato",
        "crop_id":      "crop_tomato",
        "grow_minutes": 5,
        "yield_min":    1,
        "yield_max":    3,
    },
    "carrot": {
        "name":         "แครอท",
        "emoji":        "🥕",
        "seed_id":      "seed_carrot",
        "crop_id":      "crop_carrot",
        "grow_minutes": 8,
        "yield_min":    1,
        "yield_max":    4,
    },
    "potato": {
        "name":         "มันฝรั่ง",
        "emoji":        "🥔",
        "seed_id":      "seed_potato",
        "crop_id":      "crop_potato",
        "grow_minutes": 12,
        "yield_min":    2,
        "yield_max":    5,
    },
    "lemon": {
        "name":         "มะนาว",
        "emoji":        "🍋",
        "seed_id":      "seed_lemon",
        "crop_id":      "crop_lemon",
        "grow_minutes": 15,
        "yield_min":    1,
        "yield_max":    3,
    },
    "eggplant": {
        "name":         "มะเขือม่วง",
        "emoji":        "🍆",
        "seed_id":      "seed_eggplant",
        "crop_id":      "crop_eggplant",
        "grow_minutes": 20,
        "yield_min":    1,
        "yield_max":    4,
    },
    "peach": {
        "name":         "พีช",
        "emoji":        "🍑",
        "seed_id":      "seed_peach",
        "crop_id":      "crop_peach",
        "grow_minutes": 25,
        "yield_min":    1,
        "yield_max":    3,
    },
    "pumpkin": {
        "name":         "ฟักทอง",
        "emoji":        "🎃",
        "seed_id":      "pumpkin_seed",
        "crop_id":      "crop_pumpkin",
        "grow_minutes": 30,
        "yield_min":    1,
        "yield_max":    2,
    },
    "watermelon": {
        "name":         "แตงโม",
        "emoji":        "🍉",
        "seed_id":      "seed_watermelon",
        "crop_id":      "crop_watermelon",
        "grow_minutes": 40,
        "yield_min":    1,
        "yield_max":    2,
    },
}


def create_table():
    with get_conn() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS farming (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id     TEXT    NOT NULL,
                plant_type  TEXT    NOT NULL,
                planted_at  REAL    NOT NULL,  -- Unix timestamp
                harvest_at  REAL    NOT NULL,  -- Unix timestamp
                harvested   INTEGER DEFAULT 0  -- 0 = ยังไม่เก็บ, 1 = เก็บแล้ว
            )
        """)


def plant_crop(user_id: str, plant_type: str):
    """บันทึกการปลูกพืชใหม่ พร้อมคำนวณเวลาเก็บเกี่ยว"""
    plant = PLANTS[plant_type]
    now = datetime.utcnow().timestamp()
    harvest_at = now + plant["grow_minutes"] * 60  # แปลงนาที → วินาที

    with get_conn() as conn:
        conn.execute("""
            INSERT INTO farming (user_id, plant_type, planted_at, harvest_at)
            VALUES (?, ?, ?, ?)
        """, (user_id, plant_type, now, harvest_at))


def get_farms(user_id: str) -> list:
    """ดูแปลงปลูกทั้งหมดที่ยังไม่ได้เก็บ พร้อมสถานะว่าพร้อมหรือยัง"""
    now = datetime.utcnow().timestamp()
    with get_conn() as conn:
        rows = conn.execute("""
            SELECT * FROM farming
            WHERE user_id = ? AND harvested = 0
            ORDER BY harvest_at ASC
        """, (user_id,)).fetchall()

    result = []
    for row in rows:
        r = dict(row)
        r["is_ready"]     = r["harvest_at"] <= now
        r["seconds_left"] = max(0, int(r["harvest_at"] - now))
        result.append(r)
    return result


def harvest_ready(user_id: str) -> list:
    """
    เก็บเกี่ยวทุกต้นที่พร้อมแล้ว
    คืนรายการต้นที่เก็บได้ (เพื่อให้ main.py สุ่มจำนวนและเพิ่มใน inventory)
    """
    now = datetime.utcnow().timestamp()
    with get_conn() as conn:
        rows = conn.execute("""
            SELECT * FROM farming
            WHERE user_id = ? AND harvested = 0 AND harvest_at <= ?
        """, (user_id, now)).fetchall()

        if rows:
            ids = [row["id"] for row in rows]
            placeholders = ",".join("?" * len(ids))
            conn.execute(
                f"UPDATE farming SET harvested = 1 WHERE id IN ({placeholders})",
                ids
            )

    return [dict(r) for r in rows]
