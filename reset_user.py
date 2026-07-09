# ============================================================
#  reset_user.py — ลบข้อมูลของ user คนเดียวออกจาก database
#  วางไฟล์นี้ไว้ข้างๆ main.py แล้วรัน: python reset_user.py
# ============================================================

import sqlite3

DB_PATH = "rpg.db"


def reset_user(user_id: str):
    conn = sqlite3.connect(DB_PATH)

    # ลบข้อมูลจากทุกตารางที่เกี่ยวกับ user คนนี้
    conn.execute("DELETE FROM users           WHERE user_id = ?", (user_id,))
    conn.execute("DELETE FROM inventory       WHERE user_id = ?", (user_id,))
    conn.execute("DELETE FROM farming         WHERE user_id = ?", (user_id,))
    conn.execute("DELETE FROM user_quests     WHERE user_id = ?", (user_id,))

    conn.commit()
    conn.close()
    print(f"delete all data of user_id={user_id} successfully")
    print("   (if user use /profile again, new data will be created automatically)")


if __name__ == "__main__":
    print("=" * 50)
    print("  Reset User Data Tool")
    print("=" * 50)
    print("how to find user_id: right click on user > Copy ID")
    print("(have to turn on Developer Mode first: Settings > Advanced)")
    print()

    uid = input("Discord User ID: ").strip()

    if not uid.isdigit():
        print("user ID have to be a number. exit.")
    else:
        confirm = input(f"confirm deletion of user_id={uid}? type 'y' to confirm: ").strip().lower()
        if confirm == "y":
            reset_user(uid)
        else:
            print("ยกเลิกการลบ")
