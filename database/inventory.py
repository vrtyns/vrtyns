# ============================================================
#  database/inventory.py
#  ตาราง inventory — เก็บไอเทมของ user
#  + รายการไอเทมทั้งหมดในเกม (ITEMS)
#  + ตารางน้ำหนักการขุดแร่ (ORES)
# ============================================================

from .connection import get_conn


# ── รายการไอเทมทั้งหมด ────────────────────────────────────
ITEMS: dict = {
    # เมล็ดพันธุ์ value = ราคาขายต่อเมล็ด
    "seed_tomato":    {"name": "tomatoseed", "emoji": "<:little_bag:1523010357361246419>", "type": "seed", "value": 1},
    "seed_carrot":    {"name": "carrotseed",      "emoji": "<:little_bag:1523010357361246419>", "type": "seed", "value": 2},
    "seed_potato":    {"name": "potatoseed",  "emoji": "<:little_bag:1523010357361246419>", "type": "seed", "value": 4},
    "seed_lemon":      {"name": "lemonseed",      "emoji": "<:little_bag:1523010357361246419>", "type": "seed", "value": 5},
    "seed_cherry":   {"name": "cherryseed",   "emoji": "<:little_bag:1523010357361246419>", "type": "seed", "value": 7},
    "seed_peach":      {"name": "peachseed",      "emoji": "<:little_bag:1523010357361246419>", "type": "seed", "value": 10},
    "seed_pumpkin":    {"name": "pumpkinseed",    "emoji": "<:little_bag:1523010357361246419>", "type": "seed", "value": 15},
    # พืชผล
    "crop_tomato":    {"name": "tomatocrop",        "emoji": "<:tomato_pixel:1521869453728419932>", "type": "crop", "value": 3},
    "crop_blueberry": {"name": "blueberrycrop",  "emoji": "<:blue_berry:1521868955218612334>", "type": "crop", "value": 4},
    "crop_banana":    {"name": "bananacrop",        "emoji": "<:banana_pixel:1521877389444124694>", "type": "crop", "value": 4},
    "crop_apple":     {"name": "applecrop",            "emoji": "<:apple_pixel:1521869087486246962>", "type": "crop", "value": 5},
    "crop_carrot":    {"name": "carrotcrop",            "emoji": "<:carrot_pixel:1521869972081610912>", "type": "crop", "value": 5},
    "crop_lemon":      {"name": "lemoncrop",            "emoji": "<:lemon_pixel:1521877331742949397>", "type": "crop", "value": 5},
    "crop_orange":    {"name": "orangecrop",        "emoji": "<:orange_pixel:1521869897783574629>", "type": "crop", "value": 6},
    "crop_potato":    {"name": "potatocrop",         "emoji": "<:potato_pixel:1521869020230324378>", "type": "crop", "value": 7},
    "crop_cherry":     {"name": "cherrycrop",          "emoji": "<:cherry_pixel:1521877243591135252>", "type": "crop", "value": 9},
    "crop_peach":      {"name": "peachcrop",            "emoji": "<:peachy_pixel:1521877517323993299>", "type": "crop", "value": 11},
    "crop_pumpkin":    {"name": "pumpkincrop",        "emoji": "<:pumkin_pixel:1521869269087027384>", "type": "crop", "value": 30},
   
    # แร่ธาตุ
    "ore_steel":       {"name": "Steel",          "emoji": "<:steel:1521879014128746596>", "type": "ore", "value": 100,   "tier": "Common",    "tier_color": "⚪"},
    "ore_mitthrium":    {"name": "Mitthrium",         "emoji": "<:mitthrium:1521877811344707756>", "type": "ore", "value": 200,  "tier": "Common",    "tier_color": "⚪"},
    "ore_pullux":      {"name": "Pullux",            "emoji": "<:pollux:1521878193751986368>", "type": "ore", "value": 500,  "tier": "Uncommon",      "tier_color": "🟢"},
    "ore_stardust":      {"name": "Stardust",          "emoji": "<:stardust:1521879142360940634>", "type": "ore", "value": 750,  "tier": "Uncommon",      "tier_color": "🟢"},
    "ore_ruby":      {"name": "Ruby",            "emoji": "<:ruby:1521879101718139071>", "type": "ore", "value": 900,  "tier": "Uncommon",      "tier_color": "🟢"},
    "ore_elixis":      {"name": "Elixis",            "emoji": "<:elixis:1521879061444427999>", "type": "ore", "value": 1050,  "tier": "Rare",      "tier_color": "🔵"},
    "ore_rose_crystal": {"name": "Rose Crystal",  "emoji": "<:rose_crystal:1521879180269326567>", "type": "ore", "value": 1100,  "tier": "Rare",      "tier_color": "🔵"},
    "ore_ipsum":    {"name": "Ipsum",       "emoji": "<:ipsum:1521878037115703496>", "type": "ore", "value": 1500,  "tier": "Epic",      "tier_color": "🟣"},
    "ore_ice_crystal": {"name": "Ice Crystal",  "emoji": "<:ice_crystal:1521879224250793984>", "type": "ore", "value": 1700, "tier": "Legendary",      "tier_color": "🟠"},
    "ore_astral_crystal": {"name": "Astral Crystal",  "emoji": "<:astral_crystal:1521879372066197704>", "type": "ore", "value": 5000, "tier": "Mythic", "tier_color": "🟡"},

    # consumable — buff ชั่วคราว
    "potion_hp":         {"name": "โพชั่นรักษา",     "emoji": "<:hp_potion:1523005714904121547>", "type": "consumable", "value": 200,
                          "effect": {"hp": 25}},
    "potion_mana":       {"name": "โพชั่นฟื้นฟู",    "emoji": "<:mana_potion:1523005769400848635>", "type": "consumable", "value": 300,
                          "effect": {"mana": 10}},
    "potion_full":       {"name": "โพชั่นอายุวัฒนะ",        "emoji": "<:all_potion:1523005960686145656>", "type": "consumable", "value": 650,
                          "effect": {"hp": 30, "mana": 15}},
    "potion_dice":       {"name": "โพชั่นเสริมโชค",    "emoji": "<:dice_potion:1523005848668995837>", "type": "consumable", "value": 1500,
                          "effect": {"buff": {"type": "dice_bonus",   "value": 1,  "hours": 3,
                                             "description": "`เต๋า +1 เป็นเวลา 3 ชั่วโมง`"}}},
    "potion_atk":        {"name": "โพชั่นเพิ่มพลัง",    "emoji": "<:status_potion:1523005911684218921>", "type": "consumable", "value": 500,
                          "effect": {"buff": {"type": "atk_bonus",    "value": 2, "hours": 2,
                                             "description": "`พลังโจมตี *2 เป็นเวลา 2 ชั่วโมง`"}}},
    "potion_vit":        {"name": "โพชั่นบำรุง",  "emoji": "<:status_potion:1523005911684218921>", "type": "consumable", "value": 500,
                          "effect": {"buff": {"type": "vit_bonus",    "value": 2, "hours": 2,
                                             "description": "`พลังชีวิต *2 เป็นเวลา 2 ชั่วโมง`"}}},
    "potion_cleanse":    {"name": "โพชั่นล้างพิษ",       "emoji": "<:cleanse_potion:1523006011349143713>", "type": "consumable", "value": 450,
                          "effect": {"cleanse": True}},
    "potion_fire":       {"name": "โพชั่นต้านไฟ",        "emoji": "<:all_potion:1523005960686145656>", "type": "consumable", "value": 250,
                          "effect": {"buff": {"type": "fire_resist",   "value": 1,  "hours": 2,
                                             "description": "`ต้านทานไฟเป็นเวลา 2 ชั่วโมง`"}}},
    "potion_max_hp":     {"name": "โพชั่นเสริมกาย",   "emoji": "<:hp_heart:1521868611524759704>", "type": "consumable", "value": 2000,
                          "effect": {"max_hp": 20}},
    "potion_max_mana":   {"name": "โพชั่นเสริมจิต",    "emoji": "<:mp_heart:1521868748431163492>", "type": "consumable", "value": 2000,
                          "effect": {"max_mana": 15}},
}

# ── ตารางน้ำหนักการขุดแร่ ─────────────────────────────────
ORES: list = [
    # Common (68.0%)
    {"id": "ore_steel",         "weight": 34.0,    "qty_min": 1, "qty_max": 3},
    {"id": "ore_mitthrium",         "weight": 34.0,    "qty_min": 1, "qty_max": 3},

    # Uncommon (20.0%)
    {"id": "ore_pullux",     "weight": 8.0,     "qty_min": 1, "qty_max": 2},
    {"id": "ore_stardust",          "weight": 7.0,     "qty_min": 1, "qty_max": 2},
    {"id": "ore_ruby",   "weight": 5.0,     "qty_min": 1, "qty_max": 1},

    # Rare (8.0%)
    {"id": "ore_elixis",        "weight": 5.0,     "qty_min": 1, "qty_max": 1},
    {"id": "ore_rose_crystal",  "weight": 3.0,     "qty_min": 1, "qty_max": 1},

    # Epic (3.992%)
    {"id": "ore_ipsum",      "weight": 3.992,   "qty_min": 1, "qty_max": 1},

    # Legendary (0.008%)
    {"id": "ore_ice_crystal",        "weight": 0.008,   "qty_min": 1, "qty_max": 1},

    # Mythic (0.0001%)
    {"id": "ore_astral_crystal","weight": 0.0001,  "qty_min": 1, "qty_max": 1},
]

def create_table():
    with get_conn() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS inventory (
                id        INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id   TEXT    NOT NULL,
                item_id   TEXT    NOT NULL,
                quantity  INTEGER DEFAULT 1,
                UNIQUE(user_id, item_id)
            )
        """)


def add_item(user_id: str, item_id: str, quantity: int = 1):
    """add item — ถ้ามีอยู่แล้วให้บวกเพิ่ม"""
    with get_conn() as conn:
        conn.execute("""
            INSERT INTO inventory (user_id, item_id, quantity) VALUES (?, ?, ?)
            ON CONFLICT(user_id, item_id)
            DO UPDATE SET quantity = quantity + excluded.quantity
        """, (user_id, item_id, quantity))


def remove_item(user_id: str, item_id: str, quantity: int = 1) -> bool:
    """remove item — คืน False ถ้าของไม่พอหรือไม่มี"""
    with get_conn() as conn:
        row = conn.execute(
            "SELECT quantity FROM inventory WHERE user_id = ? AND item_id = ?",
            (user_id, item_id)
        ).fetchone()
        if not row or row["quantity"] < quantity:
            return False
        if row["quantity"] == quantity:
            conn.execute(
                "DELETE FROM inventory WHERE user_id = ? AND item_id = ?",
                (user_id, item_id)
            )
        else:
            conn.execute(
                "UPDATE inventory SET quantity = quantity - ? WHERE user_id = ? AND item_id = ?",
                (quantity, user_id, item_id)
            )
    return True


def has_item(user_id: str, item_id: str, quantity: int = 1) -> bool:
    """ตรวจว่า user มีไอเทมนี้ครบจำนวนไหม"""
    with get_conn() as conn:
        row = conn.execute(
            "SELECT quantity FROM inventory WHERE user_id = ? AND item_id = ?",
            (user_id, item_id)
        ).fetchone()
    return row is not None and row["quantity"] >= quantity


def get_inventory(user_id: str) -> list:
    """ดึงไอเทมทั้งหมดของ user"""
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT item_id, quantity FROM inventory WHERE user_id = ? ORDER BY item_id",
            (user_id,)
        ).fetchall()
    return [dict(r) for r in rows]
