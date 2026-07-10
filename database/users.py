# ============================================================
#  database/users.py
#  ตาราง users — stats, เงิน, EXP, level
# ============================================================

from .connection import get_conn


def create_table():
    with get_conn() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id   TEXT    PRIMARY KEY,
                level     INTEGER DEFAULT 1,
                exp       INTEGER DEFAULT 0,
                exp_max   INTEGER DEFAULT 100,
                hp        INTEGER DEFAULT 100,
                hp_max    INTEGER DEFAULT 100,
                mana      INTEGER DEFAULT 100,
                mana_max  INTEGER DEFAULT 100,
                san       INTEGER DEFAULT 100,
                san_max   INTEGER DEFAULT 100,
                str       INTEGER DEFAULT 10,
                int       INTEGER DEFAULT 10,
                dex       INTEGER DEFAULT 10,
                vit       INTEGER DEFAULT 10,
                agi       INTEGER DEFAULT 10,
                coin      INTEGER DEFAULT 0,
                sil       INTEGER DEFAULT 0
            )
        """)


def get_or_create_user(user_id: str) -> tuple[dict, bool]:
    """คืน (ข้อมูล user, is_new) — สร้างใหม่อัตโนมัติถ้ายังไม่มี"""
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM users WHERE user_id = ?", (user_id,)).fetchone()
        if row:
            return dict(row), False
        conn.execute("INSERT INTO users (user_id) VALUES (?)", (user_id,))
        row = conn.execute("SELECT * FROM users WHERE user_id = ?", (user_id,)).fetchone()
        return dict(row), True


def add_exp(user_id: str, amount: int) -> dict:
    """
    เพิ่ม EXP ให้ user และจัดการ Level Up อัตโนมัติ
    คืน: {"leveled_up": bool, "levels_gained": int, "new_level": int}
    """
    user, _ = get_or_create_user(user_id)

    new_exp      = user["exp"] + amount
    new_level    = user["level"]
    new_exp_max  = user["exp_max"]
    levels_gained = 0

    # วนตรวจ level up (อาจ level up หลายครั้งถ้า EXP เยอะมาก)
    while new_exp >= new_exp_max:
        new_exp      -= new_exp_max
        new_level    += 1
        new_exp_max   = new_level * 100   # EXP ที่ต้องการ = level ใหม่ × 100
        levels_gained += 1

    with get_conn() as conn:
        if levels_gained > 0:
            # คำนวณ stat ใหม่ในฝั่ง Python เพื่อป้องกัน SQLite ใช้ค่าเก่า
            new_hp_max   = user["hp_max"]   + levels_gained * 10
            new_mana_max = user["mana_max"] + levels_gained * 5
            conn.execute("""
                UPDATE users SET
                    exp = ?, exp_max = ?, level = ?,
                    hp_max = ?, hp = ?,
                    mana_max = ?, mana = ?,
                    str = str + ?,
                    vit = vit + ?,
                    int_stat = int_stat + ?,
                    san = san + ?,
                    san_max = san_max + ?
                WHERE user_id = ?
            """, (
                new_exp, new_exp_max, new_level,
                new_hp_max, new_hp_max,       # HP เต็มตอน level up
                new_mana_max, new_mana_max,   # MANA เต็มตอน level up
                levels_gained,                # +1 ATK ต่อ level
                levels_gained,                # +1 VIT ต่อ level
                levels_gained,                # +1 INT ต่อ level
                user_id,
            ))
        else:
            conn.execute("UPDATE users SET exp = ? WHERE user_id = ?", (new_exp, user_id))

    return {
        "leveled_up":    levels_gained > 0,
        "levels_gained": levels_gained,
        "new_level":     new_level,
    }


def update_coins(user_id: str, coin_delta: int = 0, sil_delta: int = 0) -> bool:
    """
    เพิ่ม/ลดเงิน (ใส่เลขลบเพื่อลด)
    คืน False ถ้าเงินไม่พอ
    """
    user, _ = get_or_create_user(user_id)
    new_coin = user["coin"] + coin_delta
    new_sil  = user["sil"]  + sil_delta

    if new_coin < 0 or new_sil < 0:
        return False

    with get_conn() as conn:
        conn.execute(
            "UPDATE users SET coin = ?, sil = ? WHERE user_id = ?",
            (new_coin, new_sil, user_id)
        )
    return True
