# ============================================================
#  database/connection.py
#  connection กลาง และ setup ตารางทั้งหมด
# ============================================================

import sqlite3
import os

DB_PATH = os.environ.get("DB_PATH", "rpg.db")


def get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def setup():
    """once call when bot starts — create tables if not exist"""
    from .users      import create_table  as users_table
    from .inventory  import create_table  as inventory_table
    from .farming    import create_table  as farming_table
    from .quests     import create_tables as quest_tables
    from .scheduler  import create_table  as scheduler_table
    # from .daily      import create_table  as daily_table
    from .buffs import create_table as buffs_table  
    from .skills import create_table as skills_table
    from .reaction_roles import create_table as rr_table    # ← เพิ่ม

    users_table()
    inventory_table()
    farming_table()
    quest_tables()
    scheduler_table()
    # daily_table()                                            
    skills_table()                       
    buffs_table()                     
    rr_table()                                                 # ← เพิ่ม
    print("Database initialized (rpg.db)")
