# ============================================================
#  database/shop.py
#  รายการสินค้าร้านค้า และ logic การซื้อ/ขาย
# ============================================================

from .connection import get_conn
from .inventory  import ITEMS, add_item, remove_item

# ── รายการสินค้าที่ร้านขาย (ราคาซื้อจากร้าน) ─────────────
SHOP_ITEMS: dict = {
    "seed_tomato": {"price_buy": 1},
    "seed_carrot":  {"price_buy": 2},
    "seed_potato":  {"price_buy": 4},
    "seed_lemon":   {"price_buy": 6},
    "seed_peach":   {"price_buy": 10},
    "seed_pumpkin": {"price_buy": 15},
    
    "crop_tomato": {"price_buy": 3},
    "crop_blueberry": {"price_buy": 4},
    "crop_banana": {"price_buy": 4},
    "crop_apple": {"price_buy": 5},
    "crop_carrot": {"price_buy": 5},
    "crop_lemon": {"price_buy": 5},
    "crop_orange": {"price_buy": 6},
    "crop_potato": {"price_buy": 7},
    "crop_corn": {"price_buy": 8},
    "crop_strawberry": {"price_buy": 8},
    "crop_cherry": {"price_buy": 9},
    "crop_eggplant": {"price_buy": 10},
    "crop_peach": {"price_buy": 11},
    "crop_coconut": {"price_buy": 12},
    "crop_mango": {"price_buy": 15},
    "crop_pumpkin": {"price_buy": 30},
    "crop_watermelon": {"price_buy": 40},
    
    "potion_hp": {"price_buy": 200},
    "potion_mana": {"price_buy": 300},
    "potion_full": {"price_buy": 650},
    "potion_dice": {"price_buy": 1500},
    "potion_atk": {"price_buy": 500},
    "potion_vit": {"price_buy": 500},
    "potion_cleanse": {"price_buy": 450},
    "potion_fire": {"price_buy": 250},
    "potion_max_hp": {"price_buy": 2000},
    "potion_max_mana": {"price_buy": 2000},
    # เพิ่มสินค้าใหม่ที่นี่ในอนาคต เช่น ยา, อุปกรณ์
}
# ราคาขาย (user ขายให้ร้าน) ใช้ค่า "value" ใน ITEMS แทน


def buy_from_shop(user_id: str, item_id: str, quantity: int = 1) -> tuple[bool, str]:
    """user ซื้อของจากร้าน — ตรวจเงิน, ตัดเงิน, เพิ่มของใน inventory"""
    if item_id not in SHOP_ITEMS:
        return False, "Item not found in shop"

    item       = ITEMS[item_id]
    total_cost = SHOP_ITEMS[item_id]["price_buy"] * quantity

    with get_conn() as conn:
        row = conn.execute("SELECT coin FROM users WHERE user_id = ?", (user_id,)).fetchone()
        have = row["coin"] if row else 0
        if have < total_cost:
            return False, f"Insufficient funds! Need **{total_cost:,}** Coin (Have **{have:,}** Coin)"
        conn.execute("UPDATE users SET coin = coin - ? WHERE user_id = ?", (total_cost, user_id))

    add_item(user_id, item_id, quantity)
    return True, f"Purchased {item['emoji']} **{item['name']}** ×{quantity} successfully! Paid **{total_cost:,}** Coin"


def sell_to_shop(user_id: str, item_id: str, quantity: int = 1) -> tuple[bool, str]:
    """user ขายของให้ร้าน — ลบของออก, เพิ่มเงิน"""
    if item_id not in ITEMS:
        return False, "Item not found"

    item       = ITEMS[item_id]
    sell_price = item.get("value", 0)

    if sell_price == 0:
        return False, f"**{item['name']}** cannot be sold to the shop"

    if not remove_item(user_id, item_id, quantity):
        return False, f"Item not found in inventory"
    total_earn = sell_price * quantity
    with get_conn() as conn:
        conn.execute("UPDATE users SET coin = coin + ? WHERE user_id = ?", (total_earn, user_id))

    return True, f"Sold {item['emoji']} **{item['name']}** ×{quantity} for **{total_earn:,}** Coin"
