# ============================================================
#  main.py — ไฟล์หลักของ bot  |  python main.py
#  โครงสร้างคำสั่งใหม่:
#    /ping /roll /profile /inventory /shop /quest /mine /explore /transfer /trade
#    /farm plant | check | harvest
#    /admin exp | give_coin | take_coin | quest_create | quest_list |
#           quest_give | quest_done | schedule_add | schedule_list | schedule_remove
# ============================================================

import discord
from discord import app_commands
from discord.ext import commands, tasks
from dotenv import load_dotenv
from datetime import datetime, timezone, timedelta
TH_TZ = timezone(timedelta(hours=7))  # ← เพิ่มบรรทัดนี้
import os, random, asyncio
import database
import database.trade as trade_mod
import re

load_dotenv()
intents = discord.Intents.default()
bot     = commands.Bot(command_prefix="v!", intents=intents)
GUILD_IDS = [
    discord.Object(id=int(gid.strip()))
    for gid in os.getenv("GUILD_IDS", "").split(",")
    if gid.strip()
]
intents = discord.Intents.default()
intents.members = True   # ← เพิ่มบรรทัดนี้ (ต้องการสำหรับ add_roles/remove_roles)


# ╔══════════════════════════════════════════════════════════╗
#  SECTION 1 — HELPERS
# ╚══════════════════════════════════════════════════════════╝

# def exp_bar(cur: int, mx: int, length: int = 10) -> str:
#     if mx == 0: return f"[{'░'*length}] 0/0"
#     filled = min(int(cur / mx * length), length)
#     return f"[{'█'*filled}{'░'*(length-filled)}] {cur}/{mx} ({int(cur/mx*100)}%)"

# def level_color(lv: int) -> discord.Color:
#     if lv < 10:  return discord.Color.green()
#     if lv < 20:  return discord.Color.blue()
#     if lv < 30:  return discord.Color.purple()
#     return discord.Color.gold()

def format_time(sec: int) -> str:
    if sec < 60:   return f"{sec} seconds"
    if sec < 3600: m, s = divmod(sec, 60); return f"{m} minutes {s} seconds"
    h, r = divmod(sec, 3600); return f"{h} hours {r//60} minutes"


async def build_inventory_embed(user: discord.Member) -> discord.Embed | None:
    items = database.get_inventory(str(user.id))
    if not items:
        return None

    embed  = discord.Embed(
        title=f"<:inventory:1523010328495915190> {user.display_name}'s inventory",
        color=discord.Color.dark_orange()
    )
    # เพิ่ม "consumable" เข้ามาด้วย — นี่คือสาเหตุที่ potion ไม่แสดง
    groups: dict[str, list[str]] = {
        "seed":       [],
        "crop":       [],
        "ore":        [],
        "consumable": [],
        "misc":       [],
    }
    for row in items:
        item = database.ITEMS.get(row["item_id"])
        if item and item.get("type") in groups:
            groups[item["type"]].append(
                f"{item['emoji']} **{item['name']}** ×{row['quantity']}"
            )
    labels = {
        "seed":       "<:little_bag:1523010357361246419> Seeds",
        "crop":       "<:apple_pixel:1521869087486246962> Crops",
        "ore":        "<:mitthrium:1521877811344707756> Ores",
        "consumable": "<:hp_potion:1523005714904121547> Items",
        "misc":        "<:inventory:1523010328495915190> Items",
    }
    for key, label in labels.items():
        if groups[key]:
            embed.add_field(name=label, value="\n".join(groups[key]), inline=True)

    embed.set_footer(text=f"Total: {sum(r['quantity'] for r in items)} items")
    return embed


async def get_buffs_embed(user: discord.Member) -> discord.Embed:
    buffs   = database.get_active_buffs(str(user.id))
    embed   = discord.Embed(
        title=f"{user.display_name}'s Buffs | Debuffs",
        color=discord.Color.purple()
    )
    if not buffs:
        embed.description = "_No active buffs/debuffs_"
        return embed
 
    buff_lines   = []
    debuff_lines = []
    for b in buffs:
        expire_text = f"(expired <t:{int(b['expires_at'])}:R>)" if b["expires_at"] else "(permanent)"
        line = f"• {b['description']} {expire_text}"
        if b["is_debuff"]:
            debuff_lines.append(line)
        else:
            buff_lines.append(line)
 
    if buff_lines:
        embed.add_field(name="Buff", value="\n".join(buff_lines), inline=False)
    if debuff_lines:
        embed.add_field(name="Debuff", value="\n".join(debuff_lines), inline=False)
    return embed

def _parse_emoji(emoji_str: str):
    """แปลง emoji string เป็น PartialEmoji — ถ้า parse ไม่ได้ return None"""
    if not emoji_str:
        return None
    try:
        m = re.match(r'<(a?):(\w+):(\d+)>', emoji_str)
        if m:
            return discord.PartialEmoji(
                animated=bool(m.group(1)),
                name=m.group(2),
                id=int(m.group(3))
            )
        return emoji_str  # unicode emoji ปกติ
    except Exception:
        return None

def _truncate_field(lines: list[str], max_len: int = 950) -> str:
    """ตัด list ให้ไม่เกิน max_len ตัวอักษร พร้อมแจ้งว่าเหลืออีกกี่รายการ"""
    result, total = [], 0
    for i, line in enumerate(lines):
        if total + len(line) + 1 > max_len:
            result.append(f"_...และอีก {len(lines) - i} รายการ_")
            break
        result.append(line)
        total += len(line) + 1
    return "\n".join(result)

# ╔══════════════════════════════════════════════════════════╗
#  SECTION 2 — BACKGROUND TASK
# ╚══════════════════════════════════════════════════════════╝

@tasks.loop(minutes=1)
async def scheduled_message_task():
    database.remove_expired_buffs()
    
    now = datetime.now(TH_TZ)
    messages = database.get_due_messages(now.hour, now.minute)
    for msg in messages:
        channel = bot.get_channel(int(msg["channel_id"]))
        if channel:
            try:
                await channel.send(msg["message"])
            except Exception as e:
                print(f"Failed to send scheduled message (ch={msg['channel_id']}): {e}")

@scheduled_message_task.before_loop
async def before_scheduled():
    await bot.wait_until_ready()


# ╔══════════════════════════════════════════════════════════╗
#  SECTION 3 — VIEWS & MODALS
# ╚══════════════════════════════════════════════════════════╝

class ProfileView(discord.ui.View):
    def __init__(self, user_id: str):
        super().__init__(timeout=60)
        self.user_id = user_id

    async def _is_owner(self, interaction: discord.Interaction) -> bool:
        if str(interaction.user.id) != self.user_id:
            await interaction.response.send_message("this is not yours!", ephemeral=True)
            return False
        return True

    @discord.ui.button(label="Inventory", style=discord.ButtonStyle.secondary)
    async def inventory_btn(self, interaction: discord.Interaction, _: discord.ui.Button):
        if not await self._is_owner(interaction): return
        embed = await build_inventory_embed(interaction.user)
        if embed:
            await interaction.response.send_message(embed=embed, ephemeral=True)
        else:
            await interaction.response.send_message("Inventory is empty!", ephemeral=True)
            
    @discord.ui.button(label="Buffs", style=discord.ButtonStyle.secondary)
    async def buff_btn(self, interaction: discord.Interaction, _: discord.ui.Button):
        if not await self._is_owner(interaction): return
        embed = await get_buffs_embed(interaction.user)
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @discord.ui.button(label="Skills", style=discord.ButtonStyle.secondary)
    async def skill_btn(self, interaction: discord.Interaction, _: discord.ui.Button):
        if not await self._is_owner(interaction): return

        skills = database.get_skills(self.user_id)

        if not skills:
            await interaction.response.send_message(
                "<:ebook:1521878787871211560> Please wait for updates!", ephemeral=True)
            return

        embed = discord.Embed(
            title="<:sparkling:1523335844029796392> Skills",
            color=discord.Color.yellow()
        )
        for sk in skills:
    
            embed.add_field(
                name=f"{sk['name']}",
                value=sk["description"] or "_No description available_",
                inline=False
            )
        await interaction.response.send_message(embed=embed, ephemeral=True)


class BuyModal(discord.ui.Modal):
    def __init__(self, item_id: str, user_id: str):
        item  = database.ITEMS[item_id]
        price = database.SHOP_ITEMS[item_id]["price_buy"]
        title = f"buy {item['emoji']} {item['name']}"
        super().__init__(title=title[:45])
        self.item_id = item_id
        self.user_id = user_id
        self.qty = discord.ui.TextInput(
            label=f"Quantity (price {price:,} coin/ea)",
            placeholder="1", default="1", min_length=1, max_length=4
        )
        self.add_item(self.qty)

    async def on_submit(self, interaction: discord.Interaction):
        try:
            qty = int(self.qty.value)
            if qty <= 0: raise ValueError
        except ValueError:
            await interaction.response.send_message("Please enter a number greater than 0", ephemeral=True); return
        ok, msg = database.buy_from_shop(self.user_id, self.item_id, qty)
        await interaction.response.send_message(f"{'✅' if ok else '❌'} {msg}", ephemeral=True)


class SellModal(discord.ui.Modal):
    def __init__(self, item_id: str, user_id: str):
        item = database.ITEMS[item_id]
        title = f"sell {item['emoji']} {item['name']}"
        super().__init__(title=title[:45])
        self.item_id = item_id
        self.user_id = user_id
        self.qty = discord.ui.TextInput(
            label=f"Quantity (sell for {item['value']:,} coin/ea)",
            placeholder="1", default="1", min_length=1, max_length=4
        )
        self.add_item(self.qty)

    async def on_submit(self, interaction: discord.Interaction):
        try:
            qty = int(self.qty.value)
            if qty <= 0: raise ValueError
        except ValueError:
            await interaction.response.send_message("Please enter a number greater than 0", ephemeral=True); return
        ok, msg = database.sell_to_shop(self.user_id, self.item_id, qty)
        await interaction.response.send_message(f"{'✅' if ok else '❌'} {msg}", ephemeral=True)


class CategoryBuySelect(discord.ui.Select):
    """Dropdown ซื้อของ — กรองเฉพาะ type ที่ระบุ"""

    def __init__(self, user_id: str, item_type: str):
        self.user_id = user_id
        options = [
            discord.SelectOption(
                label=database.ITEMS[iid]["name"],
                value=iid,
                description=f"price {data['price_buy']:,} Coin",
                emoji=database.ITEMS[iid]["emoji"],
            )
            for iid, data in database.SHOP_ITEMS.items()
            if database.ITEMS.get(iid, {}).get("type") == item_type
        ]
        if not options:
            options = [discord.SelectOption(label="No items for sale", value="none")]
        super().__init__(
            placeholder="Select item to buy",
            options=options,
            disabled=(options[0].value == "none"),
        )

    async def callback(self, interaction: discord.Interaction):
        if str(interaction.user.id) != self.user_id:
            await interaction.response.send_message("This is not your shop!", ephemeral=True)
            return
        if self.values[0] == "none": return
        await interaction.response.send_modal(BuyModal(self.values[0], self.user_id))


# ── Category Sell Select ──────────────────────────────────
class CategorySellSelect(discord.ui.Select):
    """Dropdown ขายของ — กรองเฉพาะ type ที่ระบุ"""

    def __init__(self, user_id: str, item_types: list[str]):
        self.user_id = user_id
        inv      = database.get_inventory(user_id)
        sellable = [
            r for r in inv
            if database.ITEMS.get(r["item_id"], {}).get("type") in item_types
            and database.ITEMS[r["item_id"]].get("value", 0) > 0
        ]
        if sellable:
            options = [
                discord.SelectOption(
                    label=f"{database.ITEMS[r['item_id']]['name']} ({r['quantity']})",
                    value=r["item_id"],
                    description=f"sell for {database.ITEMS[r['item_id']]['value']:,} Coin",
                    emoji=database.ITEMS[r["item_id"]]["emoji"],
                )
                for r in sellable[:25]
            ]
            disabled = False
        else:
            options  = [discord.SelectOption(label="Nothing to sell", value="none")]
            disabled = True
        super().__init__(
            placeholder="Select item to sell",
            options=options,
            disabled=disabled,
        )

    async def callback(self, interaction: discord.Interaction):
        if str(interaction.user.id) != self.user_id:
            await interaction.response.send_message("This is not your shop!", ephemeral=True)
            return
        if self.values[0] == "none": return
        await interaction.response.send_modal(SellModal(self.values[0], self.user_id))


# ── Category Shop View ────────────────────────────────────
class CategoryShopView(discord.ui.View):
    """View ภายในแต่ละหมวด — มี dropdown ซื้อและขาย"""

    def __init__(self, user_id: str, item_type: str):
        super().__init__(timeout=120)
        # เพิ่ม buy dropdown ถ้ามีสินค้าในหมวดนี้
        has_buy = any(
            database.ITEMS.get(iid, {}).get("type") == item_type
            for iid in database.SHOP_ITEMS
        )
        if has_buy:
            self.add_item(CategoryBuySelect(user_id, item_type))

        # crop shop ขาย crop + ore รวมกัน
        sell_types = ["crop", "ore"] if item_type == "crop" else [item_type]
        self.add_item(CategorySellSelect(user_id, sell_types))


# ── Shop Category View (หน้าหลัก) ────────────────────────
class ShopCategoryView(discord.ui.View):
    """View หลักของร้านค้า — 3 ปุ่มเลือกหมวด"""

    def __init__(self, user_id: str):
        super().__init__(timeout=120)
        self.user_id = user_id

    async def _check(self, interaction: discord.Interaction) -> bool:
        if str(interaction.user.id) != self.user_id:
            await interaction.response.send_message(
                "This is not your shop!", ephemeral=True)
            return False
        return True

    async def _open(
        self,
        interaction: discord.Interaction,
        item_type: str,
        title: str,
        color: discord.Color,
    ):
        uid    = str(interaction.user.id)
        u, _   = database.get_or_create_user(uid)
        inv    = database.get_inventory(uid)

        embed  = discord.Embed(title=title, color=color)
        embed.set_footer(
            text=f"your money: {u['coin']:,} coins  |  {u['sil']:,} sil"
        )

        # ── ของที่ร้านขาย ──────────────────────
        buy_items = [
            (iid, data)
            for iid, data in database.SHOP_ITEMS.items()
            if database.ITEMS.get(iid, {}).get("type") == item_type
        ]
        if buy_items:
            lines = [
                f"{database.ITEMS[iid]['emoji']} **{database.ITEMS[iid]['name']}**"
                f"   {data['price_buy']:,} Coin"
                for iid, data in buy_items
            ]
            embed.add_field(name="<:sparkling:1523335844029796392> Buy", value="\n".join(lines), inline=False)

        # ── ของที่ user ขายได้ ──────────────────
        # crop shop รวม ore ด้วย เพราะทั้งคู่เป็นของที่ "หามาได้"
        sell_types = ["crop"] if item_type == "crop" else [item_type]
        sellable   = [
            r for r in inv
            if database.ITEMS.get(r["item_id"], {}).get("type") in sell_types
            and database.ITEMS[r["item_id"]].get("value", 0) > 0
        ]
        if sellable:
            lines = [
                f"{database.ITEMS[r['item_id']]['emoji']} **{database.ITEMS[r['item_id']]['name']}**"
                f" ({r['quantity']})   {database.ITEMS[r['item_id']]['value']:,} Coin"
                for r in sellable
            ]
            embed.add_field(name="<:mn_bag:1523012990306226236> Sell", value="\n".join(lines), inline=False)

        if not buy_items and not sellable:
            embed.description = "_Nothing available in this category yet._"

        await interaction.response.send_message(
            embed=embed,
            view=CategoryShopView(uid, item_type),
            ephemeral=True,
        )

    @discord.ui.button(label="🌱 Seed Shop", style=discord.ButtonStyle.secondary, row=0)
    async def seed_shop(self, interaction: discord.Interaction, _: discord.ui.Button):
        if not await self._check(interaction): return
        await self._open(interaction, "seed", "🌱 Seed Shop", discord.Color.green())
        
    @discord.ui.button(label="🍎 Fruits shop", style=discord.ButtonStyle.secondary, row=0)
    async def crop_shop(self, interaction: discord.Interaction, _: discord.ui.Button):
        if not await self._check(interaction): return
        await self._open(interaction, "crop", ":apple_pixel:1521869087486246962> Fruits Shop", discord.Color.dark_orange())
        
    @discord.ui.button(label="⛏️ Ore Market", style=discord.ButtonStyle.secondary, row=0)
    async def ore_shop(self, interaction: discord.Interaction, _: discord.ui.Button):
        if not await self._check(interaction): return
        await self._open(interaction, "ore", "<:ingotgold:1523335798978777110> Ore Shop", discord.Color.dark_blue())
        
    
    @discord.ui.button(label="⚗️ Item Shop", style=discord.ButtonStyle.secondary, row=0)
    async def item_shop(self, interaction: discord.Interaction, _: discord.ui.Button):
        if not await self._check(interaction): return
        await self._open(interaction, "consumable", "⚗️ Item Shop", discord.Color.purple())



class TransferConfirmView(discord.ui.View):
    def __init__(self, sender_id: str, receiver_id: str, coin: int, sil: int):
        super().__init__(timeout=60)
        self.sender_id   = sender_id
        self.receiver_id = receiver_id
        self.coin        = coin
        self.sil         = sil
        self.done        = False

    @discord.ui.button(label="Accept", style=discord.ButtonStyle.success)
    async def accept_btn(self, interaction: discord.Interaction, _: discord.ui.Button):
        if str(interaction.user.id) != self.receiver_id:
            await interaction.response.send_message("This is not your transfer!", ephemeral=True); return
        if self.done:
            await interaction.response.send_message("Action already completed", ephemeral=True); return
        self.done = True
        self.stop()
        ok = database.update_coins(self.sender_id, coin_delta=-self.coin, sil_delta=-self.sil)
        if not ok:
            await interaction.response.edit_message(content="Sender has insufficient funds. Transfer cancelled.", view=None); return
        database.update_coins(self.receiver_id, coin_delta=self.coin, sil_delta=self.sil)
        parts = ([f"**{self.coin:,} Coin**"] if self.coin else []) + \
                ([f"**{self.sil:,} Sil**"]   if self.sil  else [])
        await interaction.response.edit_message(content=f"Transfer of {' and '.join(parts)} completed successfully!", view=None)

    @discord.ui.button(label="Decline", style=discord.ButtonStyle.danger)
    async def decline_btn(self, interaction: discord.Interaction, _: discord.ui.Button):
        if str(interaction.user.id) != self.receiver_id:
            await interaction.response.send_message("This is not your transfer!", ephemeral=True); return
        if self.done: return
        self.done = True
        self.stop()
        await interaction.response.edit_message(content="Declined transfer", view=None)


# ╔══════════════════════════════════════════════════════════╗
#  SECTION 4 — /farm — TOP-LEVEL GROUP
# ╚══════════════════════════════════════════════════════════╝

class FarmCommands(app_commands.Group, name="farm", description="Plant and harvest crops <:greensapling:1521901310742495332>"):

    @app_commands.command(name="plant", description="Plant crops using seeds from your inventory")
    @app_commands.describe(plant_type="Crop type to plant")
    @app_commands.choices(plant_type=[
        app_commands.Choice(name="🍅 Tomato  (5 mins)",  value="tomato"),
        app_commands.Choice(name="🥕 Carrot      (8 mins)",  value="carrot"),
        app_commands.Choice(name="🥔 Potato  (12 mins)", value="potato"),
        app_commands.Choice(name="🍋 Lemon      (15 mins)", value="lemon"),
        app_commands.Choice(name="🍆 Eggplant  (20 mins)", value="eggplant"),
        app_commands.Choice(name="🍑 Peach      (25 mins)", value="peach"),
        app_commands.Choice(name="🎃 Pumpkin  (30 mins)", value="pumpkin"),
        app_commands.Choice(name="🍉 Watermelon  (40 mins)", value="watermelon"),
    
    ])
    async def plant(self, interaction: discord.Interaction, plant_type: str):
        uid  = str(interaction.user.id)
        info = database.PLANTS[plant_type]
        if not database.has_item(uid, info["seed_id"]):
            await interaction.response.send_message(
                f"*คุณไม่มีเมล็ด **{info['name']}** ในกระเป๋านะ? ลองไปหาซื้อสักหน่อยดูไหม?*", ephemeral=True); return
        database.remove_item(uid, info["seed_id"], 1)
        database.plant_crop(uid, plant_type)
        await interaction.response.send_message(
            f"*ปลูก {info['emoji']} สำเร็จ!*\n"
            f"-# *สามารถเก็บเกี่ยวได้ใน **{info['grow_minutes']} นาที** — ตรวจสอบได้ด้วย `/farm check`*")

    @app_commands.command(name="check", description="Check the status of your farm")
    async def check(self, interaction: discord.Interaction):
        farms = database.get_farms(str(interaction.user.id))
        if not farms:
            await interaction.response.send_message(
                "*คุณไม่มีพืชใดในแปลงของคุณ ลอง `/farm plant` ดูสิ?*", ephemeral=True); return
        embed = discord.Embed(title="<:greensapling:1521901310742495332> **__แปลงของคุณ__**", color=discord.Color.green())
        for f in farms:
            info   = database.PLANTS[f["plant_type"]]
            status = "***เก็บเกี่ยวได้แล้ว!***" if f["is_ready"] else f"*น้องกำลังโต **{format_time(f['seconds_left'])}***"
            embed.add_field(name=f"{info['emoji']} {info['name']}", value=status, inline=True)
        embed.set_footer(text="ใช้ `/farm harvest` เพื่อเช็ค")
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="harvest", description="Harvest ready crops and collect yields")
    async def harvest(self, interaction: discord.Interaction):
        uid  = str(interaction.user.id)
        done = database.harvest_ready(uid)
        if not done:
            await interaction.response.send_message(
                "*ไม่มีพืชใดพร้อมให้เก็บเกี่ยว ลองใช้ `/farm check` เพื่อตรวจสอบสถานะ*", ephemeral=True); return
        summary: dict[str, int] = {}
        for f in done:
            info = database.PLANTS[f["plant_type"]]
            qty  = random.randint(info["yield_min"], info["yield_max"])
            database.add_item(uid, info["crop_id"], qty)
            summary[info["crop_id"]] = summary.get(info["crop_id"], 0) + qty
        lines = [f"{database.ITEMS[k]['emoji']} **{database.ITEMS[k]['name']}** ×{v}"
                 for k, v in summary.items()]
        embed = discord.Embed(title="**เก็บเกี่ยวสำเร็จ!**", description="\n".join(lines), color=discord.Color.yellow())
        embed.set_footer(text=f"เก็บเกี่ยว {len(done)} • สามารถขายได้ที่ /shop")
        await interaction.response.send_message(embed=embed)


# ╔══════════════════════════════════════════════════════════╗
#  SECTION 5 — /admin — TOP-LEVEL GROUP 🔒
#  ตอนนี้เป็น top-level group แล้ว default_permissions ใช้ได้ผลจริง
#  (ต่างจากตอนซ้อนใต้ /v ที่ Discord ไม่ enforce ให้)
# ╚══════════════════════════════════════════════════════════╝

class AdminCommands(
    app_commands.Group,
    name="admin",
    description="คำสั่งสำหรับ Admin เท่านั้น 🔒",
    default_permissions=discord.Permissions(administrator=True),  # ชื่อ parameter ถูกต้อง
):
    # เก็บ _require_admin ไว้เป็นชั้นป้องกันที่ 2 (defense in depth)
    # เผื่อ admin เปลี่ยนสิทธิ์คำสั่งใน server settings ภายหลัง
    @staticmethod
    async def _require_admin(interaction: discord.Interaction) -> bool:
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("🔒 คำสั่งนี้สำหรับ Admin เท่านั้น!", ephemeral=True)
            return False
        return True

    # # ── EXP ──────────────────────────────
    # @app_commands.command(name="exp", description="มอบ EXP ให้ผู้เล่น")
    # @app_commands.describe(user="ผู้เล่น", amount="จำนวน EXP")
    # async def give_exp(
    #     self, interaction: discord.Interaction,
    #     user: discord.Member,
    #     amount: app_commands.Range[int, 1, 999_999],
    # ):
    #     if not await self._require_admin(interaction): return
    #     uid    = str(user.id)
    #     result = database.add_exp(uid, amount)
    #     if result["leveled_up"]:
    #         old = result["new_level"] - result["levels_gained"]
    #         msg = (f"✨ มอบ **{amount:,} EXP** ให้ **{user.display_name}** สำเร็จ!\n"
    #                f"🎉 **Level Up!** Lv.{old} → Lv.**{result['new_level']}**")
    #         try: await user.send(f"🎉 คุณ Level Up! ถึง Lv.**{result['new_level']}** แล้ว!\nดู stats ที่ `/profile`")
    #         except Exception: pass
    #     else:
    #         msg = f"✅ มอบ **{amount:,} EXP** ให้ **{user.display_name}** สำเร็จ!"
    #     await interaction.response.send_message(msg)

    # ── Coins ─────────────────────────────
    @app_commands.command(name="give_coin", description="เสกเงินให้ผู้เล่น (Admin เท่านั้น)")
    @app_commands.describe(user="ผู้เล่น", coin="จำนวน Coin", sil="จำนวน Sil")
    async def give_coin(
        self, interaction: discord.Interaction,
        user: discord.Member, coin: int = 0, sil: int = 0,
    ):
        if not await self._require_admin(interaction): return
        if coin == 0 and sil == 0:
            await interaction.response.send_message("❌ ระบุจำนวน Coin หรือ Sil อย่างน้อย 1 อย่าง", ephemeral=True); return
        database.get_or_create_user(str(user.id))
        database.update_coins(str(user.id), coin_delta=coin, sil_delta=sil)
        parts = ([f"**{coin:,} Coin**"] if coin else []) + ([f"**{sil:,} Sil**"] if sil else [])
        await interaction.response.send_message(f"💰 มอบ {' และ '.join(parts)} ให้ **{user.display_name}** สำเร็จ!")

    @app_commands.command(name="take_coin", description="ลบเงินจากผู้เล่น (Admin เท่านั้น)")
    @app_commands.describe(user="ผู้เล่น", coin="จำนวน Coin ที่จะลบ", sil="จำนวน Sil ที่จะลบ")
    async def take_coin(
        self, interaction: discord.Interaction,
        user: discord.Member, coin: int = 0, sil: int = 0,
    ):
        if not await self._require_admin(interaction): return
        ok = database.update_coins(str(user.id), coin_delta=-coin, sil_delta=-sil)
        if not ok:
            await interaction.response.send_message(f"❌ **{user.display_name}** มีเงินไม่พอ!", ephemeral=True); return
        parts = ([f"**{coin:,} Coin**"] if coin else []) + ([f"**{sil:,} Sil**"] if sil else [])
        await interaction.response.send_message(f"✂️ ลบ {' และ '.join(parts)} จาก **{user.display_name}** สำเร็จ!")
        
    # ── HP & MANA ────────────────────────
    @app_commands.command(name="set_hp", description="เพิ่ม/หัก HP ผู้เล่น (ใส่เลขลบเพื่อหัก)")
    @app_commands.describe(user="ผู้เล่น", amount="จำนวน HP (ใส่ลบเพื่อหัก เช่น -20)")
    async def set_hp(
        self, interaction: discord.Interaction,
        user: discord.Member,
        amount: int,
    ):
        if not await self._require_admin(interaction): return
        u, _ = database.get_or_create_user(str(user.id))

        new_hp = max(0, min(u["hp"] + amount, u["hp_max"]))  # จำกัดไม่ให้ต่ำกว่า 0 หรือเกิน hp_max
        with database.get_conn() as conn:
            conn.execute("UPDATE users SET hp = ? WHERE user_id = ?", (new_hp, str(user.id)))

        action = f"+{amount}" if amount >= 0 else str(amount)
        await interaction.response.send_message(
            f"<:hp_heart:1521868611524759704> HP ของ **{user.display_name}** คงเหลือ..\n"
            f"`{u['hp']} → {new_hp} / {u['hp_max']}` ({action})"
        )

    @app_commands.command(name="set_mana", description="เพิ่ม/หัก MANA ผู้เล่น (ใส่เลขลบเพื่อหัก)")
    @app_commands.describe(user="ผู้เล่น", amount="จำนวน MANA (ใส่ลบเพื่อหัก เช่น -10)")
    async def set_mana(
        self, interaction: discord.Interaction,
        user: discord.Member,
        amount: int,
    ):
        if not await self._require_admin(interaction): return
        u, _ = database.get_or_create_user(str(user.id))

        new_mana = max(0, min(u["mana"] + amount, u["mana_max"]))  # จำกัดไม่ให้ต่ำกว่า 0 หรือเกิน mana_max
        with database.get_conn() as conn:
            conn.execute("UPDATE users SET mana = ? WHERE user_id = ?", (new_mana, str(user.id)))

        action = f"+{amount}" if amount >= 0 else str(amount)
        await interaction.response.send_message(
            f"<:mp_heart:1521868748431163492> MANA ของ **{user.display_name}** คงเหลือ..\n"
            f"`{u['mana']} → {new_mana} / {u['mana_max']}` ({action})"
        )
    
    @app_commands.command(name="edit_status", description="แก้ไขค่าสเตตัสของผู้เล่น")
    @app_commands.describe(user="ผู้เล่น", stat="ค่าที่ต้องการแก้", value="ค่าใหม่")
    @app_commands.choices(stat=[
        app_commands.Choice(name="⚔️ STR", value="str"),
        app_commands.Choice(name="🧠 INT", value="int_stat"),
        app_commands.Choice(name="✨ DEX", value="dex"),
        app_commands.Choice(name="🛡️ VIT", value="vit"),
        app_commands.Choice(name="🏃 AGI", value="agi"),
    ])
    async def edit_status(
        self, interaction: discord.Interaction,
        user: discord.Member,
        stat: str,
        value: app_commands.Range[int, 1, 9999],
    ):
        if not await self._require_admin(interaction): return
        database.get_or_create_user(str(user.id))
        with database.get_conn() as conn:
            conn.execute(
                f"UPDATE users SET {stat} = ? WHERE user_id = ?",
                (value, str(user.id))
            )
        stat_display = {"str": "STR", "int_stat": "INT", "dex": "DEX",
                        "vit": "VIT", "agi": "AGI"}
        await interaction.response.send_message(
            f"✅ แก้ไข **{stat_display[stat]}** ของ **{user.display_name}** "
            f"เป็น **{value}** สำเร็จ!"
        )
        
    @app_commands.command(name="set_sanity", description="เพิ่ม/หัก SANITY ผู้เล่น (ใส่เลขลบเพื่อหัก)")
    @app_commands.describe(user="ผู้เล่น", amount="จำนวน SANITY (ใส่ลบเพื่อหัก เช่น -10)")
    async def set_sanity(
        self, interaction: discord.Interaction,
        user: discord.Member,
        amount: int,
    ):
        if not await self._require_admin(interaction): return
        u, _ = database.get_or_create_user(str(user.id))

        new_sanity = max(0, min(u["san"] + amount, u["san_max"]))  # จำกัดไม่ให้ต่ำกว่า 0 หรือเกิน san_max
        with database.get_conn() as conn:
            conn.execute("UPDATE users SET san = ? WHERE user_id = ?", (new_sanity, str(user.id)))

        action = f"+{amount}" if amount >= 0 else str(amount)
        await interaction.response.send_message(
            f"🎭 SANITY ของ **{user.display_name}** คงเหลือ..\n"
            f"`{u['san']} → {new_sanity} / {u['san_max']}` ({action})"
        )

    # ── Quests ────────────────────────────
    @app_commands.command(name="quest_create", description="สร้าง Quest ใหม่")
    @app_commands.describe(
        name="ชื่อ Quest",
        description="คำอธิบาย",
        # exp_reward="EXP ที่ได้รับ",
        coin_reward="Coin ที่ได้รับ",
    )
    async def quest_create(
        self,
        interaction: discord.Interaction,
        name: str,
        description: str,
        exp_reward: app_commands.Range[int, 0, 999_999] = 0,
        coin_reward: app_commands.Range[int, 0, 999_999] = 0,
    ):
        if not await self._require_admin(interaction): return

        new_quest = database.create_quest(name, description, exp_reward, coin_reward)

        embed = discord.Embed(title="📋 สร้าง Quest สำเร็จ!", color=discord.Color.teal())
        embed.add_field(name="ID",       value=f"`{new_quest['id']}`",  inline=True)
        embed.add_field(name="ชื่อ",      value=new_quest["name"],       inline=True)
        embed.add_field(name="รางวัล",    value=f"**{coin_reward:,}** Coin", inline=False)
        embed.add_field(name="คำอธิบาย", value=description or "-",      inline=False)
        embed.set_footer(text=f"ใช้ /admin quest_give @user {new_quest['id']} เพื่อมอบให้ผู้เล่น")
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="quest_list", description="Check all quests")
    async def quest_list(self, interaction: discord.Interaction):
        if not await self._require_admin(interaction): return
        quests = database.get_all_quests()
        if not quests:
            await interaction.response.send_message("<:quest_pixel:1521869362129142000> No quest now", ephemeral=True); return
        embed = discord.Embed(title="<:quest_pixel:1521869362129142000> All quest list", color=discord.Color.teal())
        for q in quests[:15]:
            embed.add_field(
                name=f"{q['name']}",
                value=f"<:giftcute:1521902746998013982> {q['coin_reward']:,} Coin\n_{q['description'] or 'ไม่มีคำอธิบาย'}_",
                inline=False)
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="quest_give", description="มอบ Quest ให้ผู้เล่น")
    @app_commands.describe(user="Player", quest_id="Quest ID")
    async def quest_give(
        self, interaction: discord.Interaction,
        user: discord.Member, quest_id: int,
    ):
        if not await self._require_admin(interaction): return
        database.get_or_create_user(str(user.id))
        ok, msg = database.assign_quest(str(user.id), quest_id)
        await interaction.response.send_message(f"{'✅' if ok else '❌'} {msg}")
        # if ok:
            # try: await user.send("📋 คุณได้รับ Quest ใหม่! ดูได้ที่ `/quest`")
            # except Exception: pass

    @app_commands.command(name="quest_done", description="Complete Quest for player (Admin only)")
    @app_commands.describe(user="Player", quest_id="Quest ID")
    async def quest_done(
        self, interaction: discord.Interaction,
        user: discord.Member, quest_id: int,
    ):
        if not await self._require_admin(interaction): return
        uid            = str(user.id)
        ok, msg, data  = database.complete_quest(uid, quest_id)
        if not ok:
            await interaction.response.send_message(f"❌ {msg}", ephemeral=True); return
        # lv_result = database.add_exp(uid, data["exp_reward"])
        database.update_coins(uid, coin_delta=data["coin_reward"])
        embed = discord.Embed(title="<:quest_pixel:1521869362129142000> Quest done!", color=discord.Color.gold())
        embed.add_field(name="Player", value=user.display_name, inline=True)
        embed.add_field(name="Quest",   value=data["name"],       inline=True)
        embed.add_field(name="Reward",  value=f"\n<:manycoins:1521902681642500287> **{data['coin_reward']:,}** Coin", inline=False)
        # if lv_result["leveled_up"]:
        #     old = lv_result["new_level"] - lv_result["levels_gained"]
        #     embed.add_field(name="🎉 Level Up!", value=f"Lv.{old} → Lv.**{lv_result['new_level']}**", inline=False)
        await interaction.response.send_message(embed=embed)
        # try: await user.send(f"🏆 Quest **{data['name']}** สำเร็จ!\nได้รับ {data['coin_reward']:,} Coin")
        # except Exception: pass

    # ── Scheduled Messages ─────────────────
    @app_commands.command(name="schedule_add", description="Add automatic message schedule")
    @app_commands.describe(channel="Channel to send message", message="Message to send",
                           hour="Hour 0-23 (UTC)", minute="Minute 0-59 (Default: 0)")
    async def schedule_add(
        self, interaction: discord.Interaction,
        channel: discord.TextChannel, message: str,
        hour:   app_commands.Range[int, 0, 23],
        minute: app_commands.Range[int, 0, 59] = 0,
    ):
        if not await self._require_admin(interaction): return
        sched   = database.add_schedule(str(channel.id), message, hour, minute)
        preview = message[:80] + ("..." if len(message) > 80 else "")
        await interaction.response.send_message(
            f"Added schedule successfully! (ID: `{sched['id']}`)\n"
            f"Channel: {channel.mention}\n"
            f"Time: **{hour:02d}:{minute:02d} น.** (Daily)\n"
            f"Message: {preview}")

    @app_commands.command(name="schedule_list", description="Check all scheduled messages (Admin only)")
    async def schedule_list(self, interaction: discord.Interaction):
        if not await self._require_admin(interaction): return
        schedules = database.get_all_schedules()
        if not schedules:
            await interaction.response.send_message("No scheduled messages found", ephemeral=True); return
        embed = discord.Embed(title="Scheduled Messages", color=discord.Color.blue())
        for s in schedules[:10]:
            channel = interaction.guild.get_channel(int(s["channel_id"]))
            ch_name = channel.mention if channel else f"<#{s['channel_id']}>"
            preview = s["message"][:60] + ("..." if len(s["message"]) > 60 else "")
            embed.add_field(name=f"[ID: {s['id']}] {s['hour']:02d}:{s['minute']:02d} UTC",
                            value=f"{ch_name}\n {preview}", inline=False)
        embed.set_footer(text="Remove by /admin schedule_remove <id>")
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="schedule_remove", description="Delete message schedule (Admin only)")
    @app_commands.describe(schedule_id="ID of schedule (see from /admin schedule_list)")
    async def schedule_remove(
        self, interaction: discord.Interaction, schedule_id: int,
    ):
        if not await self._require_admin(interaction): return
        ok = database.remove_schedule(schedule_id)
        if ok:
            await interaction.response.send_message(f"✅ Deleted schedule ID `{schedule_id}` successfully!")
        else:
            await interaction.response.send_message(f"❌ Schedule not found!", ephemeral=True)

# ── Skills ───────────────────────────
    @app_commands.command(name="skill_add", description="Add skill to player (Admin only)")
    @app_commands.describe(
        user="Player",
        name="Skill Name",
        description="Skill Description (e.g., Effect, Condition)"
    )
    async def skill_add(
        self, interaction: discord.Interaction,
        user: discord.Member,
        name: str,
        description: str = "",
    ):
        if not await self._require_admin(interaction): return

        database.get_or_create_user(str(user.id))
        skill = database.add_skill(str(user.id), name, description)

        embed = discord.Embed(title="<:sparkling:1523335844029796392> Skill added!", color=discord.Color.purple())
        embed.add_field(name="Player",      value=user.display_name,      inline=True)
        embed.add_field(name="Skill Name",     value=name,                   inline=False)
        embed.add_field(name="Description",     value=description or "-",     inline=False)
        embed.set_footer(text=f"Remove by /admin skill_remove @user {skill['id']}")
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="skill_remove", description="Remove a player's skill (Admin only)")
    @app_commands.describe(
        user="Player",
        skill_id="ID of skill (see from Skills button in profile)"
    )
    async def skill_remove(
        self, interaction: discord.Interaction,
        user: discord.Member,
        skill_id: int,
    ):
        if not await self._require_admin(interaction): return

        ok = database.remove_skill(skill_id, str(user.id))
        if ok:
            await interaction.response.send_message(
                f"✅ Delete **{user.display_name}**'s skill successfully!")
        else:
            await interaction.response.send_message(
                f"❌ Skill not found!", ephemeral=True)

    @app_commands.command(name="skill_list", description="Check all player's skills")
    @app_commands.describe(user="Player")
    async def skill_list(
        self, interaction: discord.Interaction,
        user: discord.Member,
    ):
        if not await self._require_admin(interaction): return

        skills = database.get_skills(str(user.id))
        if not skills:
            await interaction.response.send_message(
                f"<:quest_pixel:1521869362129142000> You have no skills!", ephemeral=True)
            return

        embed = discord.Embed(
            title=f"<:lg:1523335760818868396> **__{user.display_name}'s skill__**",
            color=discord.Color.purple()
        )
        for sk in skills:
            embed.add_field(
                name=f"__{sk['name']}__",
                value=sk["-# description"] or "_no description_",
                inline=False
            )
        await interaction.response.send_message(embed=embed, ephemeral=True)
        
# ── Give Item ─────────────────────────
    @app_commands.command(name="give_item", description="give item to player (Admin only)")
    @app_commands.describe(
        user="user to give item to",
        item_id="ID of item (e.g. potion_hp, potion_mana, potion_full)",
        quantity="amount (start: 1)",
    )
    @app_commands.choices(item_id=[
    app_commands.Choice(name="hp_potion    (HP +100)",           value="potion_hp"),
    app_commands.Choice(name="mp_potion   (MANA +50)",          value="potion_mana"),
    app_commands.Choice(name="full_potion       (HP+MANA full)",      value="potion_full"),
    app_commands.Choice(name="dice_potion   (dice +1 / 3 hrs.)",   value="potion_dice"),
    app_commands.Choice(name="str_potion   (STR *2 / 2 hrs.)",  value="potion_str"),
    app_commands.Choice(name="vit_potion   (VIT *2 / 2 hrs.)",  value="potion_vit"),
    app_commands.Choice(name="cleanse_potion     (cleanse 1 of debuff)", value="potion_cleanse"),
    app_commands.Choice(name="fire_potion      (fire resistance / 2 hrs.)",    value="potion_fire"),
    app_commands.Choice(name="life_potion  (Max HP +50 / 2 hrs.)", value="potion_max_hp"),
    app_commands.Choice(name="soul_potion   (Max MANA +30 / 2 hrs.)", value="potion_max_mana"),
    ])
    async def give_item(
        self, interaction: discord.Interaction,
        user: discord.Member,
        item_id: str,
        quantity: app_commands.Range[int, 1, 99] = 1,
    ):
        if not await self._require_admin(interaction): return

        item = database.ITEMS.get(item_id)
        if not item:
            await interaction.response.send_message(
                f"Item `{item_id}` not found", ephemeral=True)
            return

        database.get_or_create_user(str(user.id))
        database.add_item(str(user.id), item_id, quantity)

        # แจ้ง admin
        await interaction.response.send_message(
            f"**{user.display_name}** ได้รับ __{item['name']}, {item['emoji']}__ ×{quantity}"
            f" คุณสามารถตรวจสอบใน inventory ได้ด้วยคำสั่ง `/inventory`"
        )
        
    @app_commands.command(name="give_misc", description="give item (no effect) to player (Admin only)")
    @app_commands.describe(user="player", item_id="ID of item", quantity="quantity")
    @app_commands.choices(item_id=[
    app_commands.Choice(name="🗝️ Key",        value="item_key"),
    app_commands.Choice(name="📜 Old Scroll",  value="item_scroll"),
    # app_commands.Choice(name="💠 Gem",         value="item_gem"),
    ])
    async def give_misc(
        self, interaction: discord.Interaction,
        user: discord.Member,
        item_id: str,
        quantity: app_commands.Range[int, 1, 99] = 1,
    ):
        if not await self._require_admin(interaction): return
        item = database.ITEMS.get(item_id)
        if not item:
            await interaction.response.send_message(f"*ไม่เจอไอเทมนะ!*", ephemeral=True)
            return
        database.get_or_create_user(str(user.id))
        database.add_item(str(user.id), item_id, quantity)
        await interaction.response.send_message(
            f"**{user.display_name}** ได้รับ __{item['name']}, {item['emoji']}__ ×{quantity}"
            f" คุณสามารถตรวจสอบใน inventory ได้ด้วยคำสั่ง `/inventory`"
        )

    @app_commands.command(name="take_item", description="remove item from player (Admin only)")
    @app_commands.describe(user="player", item_name="name of the item", quantity="quantity to remove")
    async def take_item(
        self, interaction: discord.Interaction,
        user: discord.Member,
        item_name: str,
        quantity: app_commands.Range[int, 1, 99] = 1,
    ):
        if not await self._require_admin(interaction): return
        found_id = next((
            iid for iid, data in database.ITEMS.items()
            if data["name"] == item_name
        ), None)
        if not found_id:
            await interaction.response.send_message(
                f"*ไม่เจอไอเทมนะ!*", ephemeral=True)
            return
        ok = database.remove_item(str(user.id), found_id, quantity)
        if ok:
            item = database.ITEMS[found_id]
            await interaction.response.send_message(
                f"**{user.display_name}** ได้สูญเสีย __{item['name']}, {item['emoji']}__ ×{quantity}"
            )
        else:
            await interaction.response.send_message(
                f"*{user.display_name} ไม่มี {item_name}*", ephemeral=True)

        # # DM แจ้ง user
        # effect = item.get("effect", {})
        # effect_lines = []
        # if "hp"   in effect: effect_lines.append(f"❤️ HP +{effect['hp']}")
        # if "mana" in effect: effect_lines.append(f"💙 MANA +{effect['mana']}")
        # effect_text = "\n".join(effect_lines) if effect_lines else "_ไม่มีข้อมูล_"

        # try:
        #     await user.send(
        #         f"🎁 คุณได้รับไอเทม **{item['emoji']} {item['name']}** ×{quantity}!\n\n"
        #         f"**สรรพคุณของไอเทม:**\n{effect_text}\n\n"
        #         f"ใช้ได้ด้วยคำสั่ง `/use {item['name']}`"
        #     )
        # except Exception:
        #     pass  # ถ้า user ปิด DM ก็ข้ามไป
        
# ── Give Buff / Debuff ────────────────
    @app_commands.command(name="give_buff", description="give buff to player (Admin only)")
    @app_commands.describe(
        user="player",
        buff_type="buff type",
        value="value of the buff (e.g., 1 for dice, 20 for str%, 50 for HP)",
        hours="duration (hours) — enter 0 for no expiration",
        description="description of the buff to display in the profile",
    )
    @app_commands.choices(buff_type=[
        app_commands.Choice(name="Dice +N",          value="dice_bonus"),
        app_commands.Choice(name="STR% +N",    value="str_bonus"),
        app_commands.Choice(name="VIT% +N",    value="vit_bonus"),
        app_commands.Choice(name="Fire Resistance",        value="fire_resist"),
        app_commands.Choice(name="Max HP +N",         value="max_hp_bonus"),
        app_commands.Choice(name="Max MP +N",       value="max_mana_bonus"),
    ])
    async def give_buff(
        self, interaction: discord.Interaction,
        user: discord.Member,
        buff_type: str,
        value: int,
        hours: int,
        description: str,
    ):
        if not await self._require_admin(interaction): return

        database.get_or_create_user(str(user.id))
        expires_at = int((datetime.now(TH_TZ) + timedelta(hours=hours)).timestamp()) if hours > 0 else None

        database.add_buff(str(user.id), buff_type, value, description, expires_at)

        expire_text = f"expire in <t:{expires_at}:R>" if expires_at else "no expiration"
        await interaction.response.send_message(
            f"**{user.display_name}** ได้รับ buff!\n"
            f"-# buff *{description}* `({expire_text})`"
        )
        # try:
        #     await user.send(
        #         f"✨ คุณได้รับ buff **{description}**!\n"
        #         f"ดูได้ที่ปุ่ม 🔮 บัฟ ในโปรไฟล์"
        # #     )
        # except Exception:
        #     pass

    @app_commands.command(name="give_debuff", description="give debuff to player (Admin only)")
    @app_commands.describe(
        user="player",
        buff_type="debuff type",
        description="name/description of the debuff to display in the profile",
        value="value to reduce (e.g., enter 5 = reduce dice by 5) — if general is selected, enter 0",
        hours="duration (hours) — enter 0 for no expiration",
    )
    @app_commands.choices(buff_type=[
        app_commands.Choice(name="reduce dice -N",        value="dice_bonus"),
        app_commands.Choice(name="general (no effect)", value="debuff"),
    ])
    async def give_debuff(
        self, interaction: discord.Interaction,
        user: discord.Member,
        buff_type: str,
        description: str,
        value: int = 0,
        hours: int = 0,
    ):
        if not await self._require_admin(interaction): return

        database.get_or_create_user(str(user.id))
        expires_at = int(
            (datetime.now(TH_TZ) + timedelta(hours=hours)).timestamp()
        ) if hours > 0 else None

        database.add_buff(
            str(user.id),
            buff_type=buff_type,
            value=value,
            description=description,
            expires_at=expires_at,
            is_debuff=True,
        )

        expire_text = f"expire in <t:{expires_at}:R>" if expires_at else "no expiration"
        effect_text = f" (reduce by {value})" if buff_type == "dice_bonus" else ""
        await interaction.response.send_message(
            f"**{user.display_name}** ถูก debuff เล่นงาน!\n"
            f"-# Debuff **__{description}__**{effect_text} ({expire_text})\n")
        # try:
        #     await user.send(
        #         f"⚠️ คุณได้รับ debuff **{description}**!\n"
        #         f"ใช้ `/use ยาล้างพิษ` เพื่อล้างออก"
        #     )
        # except Exception:
        #     pass
        

bot.tree.add_command(FarmCommands(),  guild=GUILD)
bot.tree.add_command(AdminCommands(), guild=GUILD)


# ╔══════════════════════════════════════════════════════════╗
#  SECTION 6 — STANDALONE TOP-LEVEL COMMANDS
# ╚══════════════════════════════════════════════════════════╝

@bot.tree.command(name="ping", description="test bot", guild=GUILD)
async def ping(interaction: discord.Interaction):
    await interaction.response.send_message(f"**Pong!** {round(bot.latency*1000)}ms")


@bot.tree.command(name="roll", description="roll d20", guild=GUILD)
async def roll(interaction: discord.Interaction):
    uid = str(interaction.user.id)
    database.remove_expired_buffs(uid)

    base = random.randint(1, 20)
    bonus = database.get_dice_modifier(uid)   # รวม buff+debuff อัตโนมัติ
    if bonus > 0:
        bonus_text = f" `(+{bonus} from buff)`"
    elif bonus < 0:
        bonus_text = f" `({bonus} from debuff)`"
    else:
        bonus_text = ""
    result = min(20, base + bonus)  # cap ที่ 20

    # ดึง admin คนแรกมาแท็ก
    admin_mention = ""
    for member in interaction.guild.members:
        if member.guild_permissions.administrator and not member.bot:
            admin_mention = member.mention
            break

    if result in (1, 20):
        label = "<:dice_pixel:1523010248590364905>" if result == 20 else "**CRITICAL FAIL!**"
        msg   = (f"{label} {interaction.user.mention} rolled **{result}**{bonus_text}!\n"
                 f"-# โปรดแท็กสต๊าฟเพื่อรัน**อีเว้นท์พิเศษ**..")
    elif 2 <= result <= 7:
        msg = (f"<:dice_pixel:1523010248590364905> {interaction.user.mention} rolled **{result}**{bonus_text}\n"
               f"-# ออกแอคชั่นไม่สำเร็จ! สามารถลองใหม่และทอยอีกครั้งได้ เมื่อผ่าน สามารถรีแอคแล้วแท็กสต๊าฟได้")
    elif 8 <= result <= 15:
        msg = (f"<:dice_pixel:1523010248590364905> {interaction.user.mention} rolled **{result}**{bonus_text}\n"
               f"-# แอคชั่นสำเร็จ! รีแอคแล้วแท็กสต๊าฟเพื่อรันต่อ")
    elif 16 <= result <= 19:  # 16-19
        msg = (f"<:dice_pixel:1523010248590364905> {interaction.user.mention} rolled **{result}**{bonus_text}\n"
               f"-# เริ่ด! แอคชั่นสำเร็จอย่างดี! รีแอคแล้วแท็กสต๊าฟเพื่อรันต่อ")
    else:
        msg = (f"<:dice_pixel:1523010248590364905> {interaction.user.mention} rolled **{result}**{bonus_text}\n"
               f"-# เหลือจะเชื่อ.. แท็กสต๊าฟเพื่อรันผลลัพธ์เอานะ..")
    await interaction.response.send_message(msg)
    
@bot.tree.command(name="choose", description="Let the fate decide", guild=GUILD)
@app_commands.describe(choices="Options separated by | e.g., A | B | C | D")
async def choose(interaction: discord.Interaction, choices: str):
    options = [c.strip() for c in choices.split("|") if c.strip()]

    if len(options) < 2:
        await interaction.response.send_message(
            "You must provide at least 2 options separated by `|`\n"
            "Example: `/choose A | B | C`",
            ephemeral=True
        )
        return

    picked = random.choice(options)

    await interaction.response.send_message(
        f"<:lg:1523335760818868396> ***{interaction.user.display_name}** ปล่อยให้ชะตาตัดสิน...\n*"
        f"*โชคชะตาได้เลือก ... **{picked}**!*"
    )


@bot.tree.command(name="profile", description="check your profile", guild=GUILD)
async def profile(interaction: discord.Interaction):
    uid       = str(interaction.user.id)
    u, _ = database.get_or_create_user(uid)
    
    # if is_new:
    #     for seed in ("seed_tomato", "seed_carrot", "seed_potato"):
    #         database.add_item(uid, seed, 5)
    embed = discord.Embed(title=f"profile of {interaction.user.display_name}", color=discord.Color.dark_red())
    embed.set_thumbnail(url=interaction.user.display_avatar.url)
    # embed.add_field(name="📊 เลเวล / EXP",    value=f"Lv. **{u['level']}**\n{exp_bar(u['exp'], u['exp_max'])}", inline=True)
    embed.add_field(name="<:hp_heart:1521868611524759704> **HP**  <:mp_heart:1521868748431163492> **MP**", value=f"`{u['hp']}/{u['hp_max']}` | `{u['mana']}/{u['mana_max']}`", inline=True)
    embed.add_field(name="**SAN**", value=f"`{u['san']}/{u['san_max']}`", inline=True)
    # embed.add_field(name="\u200b", value="\u200b", inline=False)
    # embed.add_field(name="status",
    #                 value=(f"**ATK** {u['atk']}   **INT** {u['int_stat']}\n"
    #                        f"**AGI** {u['agi']}   **VIT** {u['vit']}\n"
    #                        f"**DEX** {u['dex']}"), inline=True)
    embed.add_field(name="**STR**  **VIT**  **AGI**", value=f"`{u['str']}` | `{u['vit']}` | `{u['agi']}`", inline=False)
    embed.add_field(name="<:acoin:1521901067602759882> **Coin** <:banknote_pixel:1521902802975068432> **Sil**", value=f"**{u['coin']:,}** | **{u['sil']:,}** ", inline=True)
    # if is_new:
    #     embed.set_footer(text="🎁 ยินดีต้อนรับ! ได้รับเมล็ดพันธุ์เริ่มต้น 5 เมล็ดทุกชนิด")
    await interaction.response.send_message(embed=embed, view=ProfileView(uid))


@bot.tree.command(name="inventory", description="check your inventory", guild=GUILD)
async def inventory(interaction: discord.Interaction):
    embed = await build_inventory_embed(interaction.user)
    if embed:
        await interaction.response.send_message(embed=embed)
    else:
        await interaction.response.send_message(
            "กระเป๋าของคุณว่างเปล่า\nลองไปเดินเล่นดูสักหน่อยดีไหม?", ephemeral=True)


@bot.tree.command(name="shop", description="check the shop", guild=GUILD)
async def shop(interaction: discord.Interaction):
    uid   = str(interaction.user.id)
    u, _  = database.get_or_create_user(uid)

    embed = discord.Embed(title="**__Local shop__**", color=discord.Color.orange())
    embed.add_field(
        name="Categories",
        value=(
            "<:little_bag:1523010357361246419>**Seed Shop**"
            "  <:watermelon_pixel:1521877458704400504>**Fruit Shop**"
            "  <:ice_crystal:1521879224250793984>**Ore Market**"
            "  <:lg:1523335760818868396>**Item Shop**"
        ),
        inline=False,
    )
    embed.set_footer(text=f"your money: {u['coin']:,} coins  |  {u['sil']:,} sil")
    await interaction.response.send_message(embed=embed, view=ShopCategoryView(uid))


@bot.tree.command(name="quest", description="check your quests", guild=GUILD)
async def quest(interaction: discord.Interaction):
    uid    = str(interaction.user.id)
    quests = database.get_user_quests(uid)
    if not quests:
        await interaction.response.send_message(
            "<:quest_pixel:1521869362129142000> You have no quests — Maybe talk to someone..?", ephemeral=True); return
    embed     = discord.Embed(title=f"<:quest_pixel:1521869362129142000> {interaction.user.display_name}'s Quests", color=discord.Color.teal())
    active    = [q for q in quests if q["status"] == "active"]
    completed = [q for q in quests if q["status"] == "completed"]
    if active:
        lines = [f"**[ID:{q['quest_id']}] {q['name']}**\n_{q['description'] or 'No description'}_\n"
                 f"<:manycoins:1521902681642500287> {q['coin_reward']:,} Coin" for q in active]
        embed.add_field(name=f"In progress", value="\n\n".join(lines), inline=False)
    if completed:
        embed.add_field(name=f"Completed ({len(completed)})",
                        value="\n".join(f"✅ ~~{q['name']}~~" for q in completed[:5]), inline=False)
    await interaction.response.send_message(embed=embed)


@bot.tree.command(name="mine", description="dig for ore", guild=GUILD)
@app_commands.checks.cooldown(1, 30.0, key=lambda i: i.user.id)
async def mine(interaction: discord.Interaction):
    await interaction.response.defer()
    await asyncio.sleep(1.5)
    uid      = str(interaction.user.id)
    database.get_or_create_user(uid)
    ore_data = random.choices(database.ORES, weights=[o["weight"] for o in database.ORES], k=1)[0]
    qty      = random.randint(ore_data["qty_min"], ore_data["qty_max"])
    item     = database.ITEMS[ore_data["id"]]
    database.add_item(uid, ore_data["id"], qty)
    tier_colors = {
        "Common": discord.Color.light_grey(), "Uncommon": discord.Color.green(),
        "Rare": discord.Color.blue(), "Epic": discord.Color.purple(), "Legendary": discord.Color.orange(), "Mythic": discord.Color.gold(),
    }
    embed = discord.Embed(
        title="Mining Results",
        description=(f"**{interaction.user.display_name}** mined ore!\n\n"
                     f"{item['emoji']} **{item['name']}** ×{qty}\n"
                    #  f"{item['tier_color']} Tier: **{item['tier']}**\n"
                     f"<:mn_bag:1523012990306226236> Value: {item['value']*qty:,} Coin"),
        color=tier_colors.get(item["tier"], discord.Color.default())
    )
    embed.set_footer(text="คุณสามารถขุดแร่ได้อีกครั้งใน 30 วินาที")
    await interaction.followup.send(embed=embed)

@mine.error
async def mine_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
    if isinstance(error, app_commands.CommandOnCooldown):
        await interaction.response.send_message(
            f"คุณสามารถขุดแร่ได้อีกครั้งใน **{error.retry_after:.0f} วินาที**", ephemeral=True)


# @bot.tree.command(name="explore", description="สำรวจป่าเก็บผลไม้ 🌿", guild=GUILD)
# @app_commands.checks.cooldown(1, 60.0, key=lambda i: i.user.id)
# async def explore(interaction: discord.Interaction):
#     await interaction.response.defer()
#     await asyncio.sleep(2)
#     uid        = str(interaction.user.id)
#     database.get_or_create_user(uid)
#     fruit_data = random.choices(database.FRUITS, weights=[f["weight"] for f in database.FRUITS], k=1)[0]
#     qty        = random.randint(fruit_data["qty_min"], fruit_data["qty_max"])
#     item       = database.ITEMS[fruit_data["id"]]
#     database.add_item(uid, fruit_data["id"], qty)
#     tier_colors = {
#         "Common": discord.Color.light_grey(), "Uncommon": discord.Color.green(),
#         "Rare": discord.Color.blue(), "Epic": discord.Color.purple(), "Legendary": discord.Color.gold(),
#     }
#     flavor = {
#         "Common":    "เจอผลไม้ธรรมดาข้างทาง",
#         "Uncommon":  "เจอผลไม้ดีๆ ซ่อนอยู่ในพุ่มไม้",
#         "Rare":      "🍀 โชคดี! เจอผลไม้หายากในส่วนลึกของป่า",
#         "Epic":      "✨ ว้าว! เจอผลไม้พิเศษที่แทบไม่มีใครเจอ",
#         "Legendary": "🌟 ปาฏิหาริย์! เจอผลไม้ในตำนาน!",
#     }
#     embed = discord.Embed(
#         title="🌿 ผลการสำรวจ",
#         description=(f"**{interaction.user.display_name}** {flavor.get(item['tier'], 'เจอผลไม้')}\n\n"
#                      f"{item['emoji']} **{item['name']}** ×{qty}\n"
#                      f"{item['tier_color']} Tier: **{item['tier']}**\n"
#                      f"💰 มูลค่า: {item['value']*qty:,} Coin"),
#         color=tier_colors.get(item["tier"], discord.Color.default())
#     )
#     embed.set_footer(text="สำรวจได้อีกใน 60 วินาที • ขายได้ที่ /shop")
#     await interaction.followup.send(embed=embed)

# @explore.error
# async def explore_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
#     if isinstance(error, app_commands.CommandOnCooldown):
#         await interaction.response.send_message(
#             f"⏳ รออีก **{error.retry_after:.0f} วินาที** ก่อนสำรวจได้อีกครั้ง", ephemeral=True)
        
# ============================================================
#  คัดลอกโค้ดด้านล่างนี้ไปวางใน main.py
#  วางต่อจาก @explore.error ได้เลย (ก่อน @transfer และ @trade)
# ============================================================

# @bot.tree.command(name="daily", description="รับรางวัลประจำวัน 🎁", guild=GUILD)
# async def daily(interaction: discord.Interaction):
#     uid = str(interaction.user.id)
#     database.get_or_create_user(uid)

#     ok, hours_left = database.can_claim(uid)

#     # ── ยังไม่ถึงเวลา ─────────────────────────
#     if not ok:
#         await interaction.response.send_message(
#             f"⏳ คุณเคลมรางวัลวันนี้ไปแล้ว!\n"
#             f"รีเซ็ตอีกประมาณ **{hours_left} ชั่วโมง** (ตี 0:00 UTC)",
#             ephemeral=True
#         )
#         return

#     # ── เคลมและคำนวณรางวัล ───────────────────
#     streak = database.do_claim(uid)

#     # รางวัลหลัก — สุ่ม coin
#     base_coin = random.randint(50, 150)

#     # bonus ตาม streak (ทุก 7 วัน ได้โบนัสพิเศษ)
#     bonus_coin = 0
#     bonus_text = ""
#     if streak % 7 == 0:
#         bonus_coin = 500
#         bonus_text = f"\n🌟 **streak {streak} วัน!** โบนัสพิเศษ **+{bonus_coin:,} Coin**"
#     elif streak >= 3:
#         bonus_coin = streak * 10
#         bonus_text = f"\n🔥 streak **{streak} วัน** โบนัส **+{bonus_coin:,} Coin**"

#     total_coin = base_coin + bonus_coin
#     database.update_coins(uid, coin_delta=total_coin)

#     # สุ่มของแถม (โอกาส 30%)
#     bonus_item_text = ""
#     if random.random() < 0.3:
#         bonus_items = [
#             ("seed_tomato", 3),
#             ("seed_carrot", 2),
#             ("seed_potato", 2),
#         ]
#         item_id, qty = random.choice(bonus_items)
#         database.add_item(uid, item_id, qty)
#         item_info     = database.ITEMS[item_id]
#         bonus_item_text = f"\n{item_info['emoji']} แถม **{item_info['name']}** ×{qty}"

#     # สร้าง embed
#     streak_bar = "🟨" * min(streak % 7 or 7, 7)   # แสดง progress ใน week
#     embed = discord.Embed(
#         title="🎁 รางวัลประจำวัน",
#         description=(
#             f"**{interaction.user.display_name}** เช็คอินสำเร็จ!\n\n"
#             f"💰 **+{base_coin:,} Coin**"
#             f"{bonus_text}"
#             f"{bonus_item_text}"
#         ),
#         color=discord.Color.gold()
#     )
#     embed.add_field(
#         name="📅 streak",
#         value=f"{streak_bar}\n**{streak}** วันติดต่อกัน",
#         inline=True
#     )
#     embed.set_footer(text="กลับมาเช็คอินพรุ่งนี้เพื่อรักษา streak!")

#     await interaction.response.send_message(embed=embed)
    
@bot.tree.command(name="use", description="use item from inventory", guild=GUILD)
@app_commands.describe(item_name="name of the item to use")
async def use_item(interaction: discord.Interaction, item_name: str):
    uid = str(interaction.user.id)
    database.remove_expired_buffs(uid)  # เคลียร์ buff หมดอายุก่อน
 
    found_id = next((
        iid for iid, data in database.ITEMS.items()
        if data["name"] == item_name and data.get("type") == "consumable"
    ), None)
 
    if not found_id:
        await interaction.response.send_message(
            f"Item **{item_name}** not found or cannot be used", ephemeral=True)
        return
 
    if not database.has_item(uid, found_id):
        await interaction.response.send_message(
            f" You don't have **{item_name}** in your inventory", ephemeral=True)
        return
 
    item   = database.ITEMS[found_id]
    effect = item.get("effect", {})
    u, _   = database.get_or_create_user(uid)
    lines  = []
 
    # ── HP ──────────────────────────────────
    if "hp" in effect:
        new_hp = min(u["hp"] + effect["hp"], u["hp_max"])
        gain   = new_hp - u["hp"]
        with database.get_conn() as conn:
            conn.execute("UPDATE users SET hp = ? WHERE user_id = ?", (new_hp, uid))
        lines.append(f"<:hp_heart:1521868611524759704> HP +{gain} (`{u['hp']} → {new_hp}/{u['hp_max']}`)")
 
    # ── MANA ────────────────────────────────
    if "mana" in effect:
        new_mana = min(u["mana"] + effect["mana"], u["mana_max"])
        gain     = new_mana - u["mana"]
        with database.get_conn() as conn:
            conn.execute("UPDATE users SET mana = ? WHERE user_id = ?", (new_mana, uid))
        lines.append(f"<:mp_heart:1521868748431163492> MANA +{gain} (`{u['mana']} → {new_mana}/{u['mana_max']}`)")
        
    if "san" in effect:
        new_san = min(u["san"] + effect["san"], u["san_max"])
        gain     = new_san - u["san"]
        with database.get_conn() as conn:
            conn.execute("UPDATE users SET san = ? WHERE user_id = ?", (new_san, uid))
        lines.append(f"🎭 SAN +{gain} (`{u['san']} → {new_san}/{u['san_max']}`)")
 
    # ── Buff ชั่วคราว ────────────────────────
    if "buff" in effect:
        b          = effect["buff"]
        expires_at = int((datetime.now(TH_TZ) + timedelta(hours=b["hours"])).timestamp())
        database.add_buff(uid, b["type"], b["value"], b["description"], expires_at)
        lines.append(f"<:sparkling:1523335844029796392> **{b['description']}** (expire in <t:{expires_at}:R>)")
 
    # ── Max HP buff ─────────────────────────
    if "max_hp" in effect:
        val        = effect["max_hp"]
        expires_at = int((datetime.now(TH_TZ) + timedelta(hours=2)).timestamp())
        database.add_buff(uid, "max_hp_bonus", val, f"Max HP +{val}", expires_at)
        lines.append(f"<:heart:1521868611524759704> **Max HP +{val}** (expire in <t:{expires_at}:R>)")
 
    # ── Max MANA buff ───────────────────────
    if "max_mana" in effect:
        val        = effect["max_mana"]
        expires_at = int((datetime.now(TH_TZ) + timedelta(hours=2)).timestamp())
        database.add_buff(uid, "max_mana_bonus", val, f"Max MANA +{val}", expires_at)
        lines.append(f"<:mp_heart:1521868748431163492> **Max MANA +{val}** (expire in <t:{expires_at}:R>)")
    
    if "max_san" in effect:
        val        = effect["max_san"]
        expires_at = int((datetime.now(TH_TZ) + timedelta(hours=2)).timestamp())
        database.add_buff(uid, "max_san_bonus", val, f"Max SAN +{val}", expires_at)
        lines.append(f"🎭 **Max SAN +{val}** (expire in <t:{expires_at}:R>)")
 
    # ── Cleanse debuff ──────────────────────
    if "cleanse" in effect:
        removed = database.clear_debuff(uid)
        if removed:
            lines.append(f"<:sparkling:1523335844029796392> *Removed **{removed}** !*")
        else:
            lines.append("<:cleanse_potion:1523006011349143713> *No debuff to cleanse*")
 
    database.remove_item(uid, found_id, 1)
 
    embed = discord.Embed(
        title=f"{item['emoji']} use {item['name']}",
        description="\n".join(lines) if lines else "nothing happen..",
        color=discord.Color.green()
    )
    await interaction.response.send_message(embed=embed)


@bot.tree.command(name="transfer", description="Transfer coins and sil to another user", guild=GUILD)
@app_commands.describe(user="The user to transfer to", coin="Amount of Coin to transfer", sil="Amount of Sil to transfer")
async def transfer_cmd(
    interaction: discord.Interaction,
    user: discord.Member, coin: int = 0, sil: int = 0,
):
    if user.id == interaction.user.id:
        await interaction.response.send_message("*You cannot transfer to yourself!*", ephemeral=True); return
    if user.bot:
        await interaction.response.send_message("*You cannot transfer to a bot!*", ephemeral=True); return
    if coin == 0 and sil == 0:
        await interaction.response.send_message("*You must specify at least one currency to transfer!*", ephemeral=True); return
    if coin < 0 or sil < 0:
        await interaction.response.send_message("*Amount must be a positive number!*", ephemeral=True); return
    sender_data, _ = database.get_or_create_user(str(interaction.user.id))
    if sender_data["coin"] < coin or sender_data["sil"] < sil:
        await interaction.response.send_message("*Insufficient funds for the transfer!*", ephemeral=True); return
    database.get_or_create_user(str(user.id))
    parts = ([f"**{coin:,} Coin**"] if coin else []) + ([f"**{sil:,} Sil**"] if sil else [])
    view  = TransferConfirmView(str(interaction.user.id), str(user.id), coin, sil)
    await interaction.response.send_message(
        f"<:mn_bag:1523012990306226236> **__{interaction.user.display_name}__** wants to transfer {' and '.join(parts)} to __{user.mention}\n__"
        f"-# click ✅ to accept or ❌ to decline `(expires in 60 seconds)`",
        view=view)

@bot.tree.command(name="countdown", description="Countdown timer ⏱", guild=GUILD)
@app_commands.describe(seconds="Number of seconds (max 3600 = 1 hour)")
async def countdown(
    interaction: discord.Interaction,
    seconds: app_commands.Range[int, 1, 3600],
):
    end_time = int((datetime.now(TH_TZ) + timedelta(seconds=seconds)).timestamp()
    )

    await interaction.response.send_message(
        f"# Start a countdown!\n"
        f" Time's up <t:{end_time}:R>"
    )

    # รันใน background — ไม่บล็อกคำสั่งอื่น
    async def notify():
        await asyncio.sleep(seconds)
        await interaction.channel.send(
            f"# Time's Up!"
            f" โปรดรอการสรุปผล.."
        )

    asyncio.create_task(notify())


@bot.tree.command(name="trade", description="Offer to trade items and coins with another user 🔄", guild=GUILD)
@app_commands.describe(user="The user you want to trade with")
async def trade_cmd(interaction: discord.Interaction, user: discord.Member):
    if user.id == interaction.user.id:
        await interaction.response.send_message("*You cannot trade with yourself!*", ephemeral=True); return
    if user.bot:
        await interaction.response.send_message("*You cannot trade with a bot!*", ephemeral=True); return

    uid_a = str(interaction.user.id)
    uid_b = str(user.id)

    if trade_mod.is_in_trade(uid_a):
        await interaction.response.send_message("*You are already in a trade!*", ephemeral=True); return
    if trade_mod.is_in_trade(uid_b):
        await interaction.response.send_message(f"***{user.display_name}** is already in a trade!*", ephemeral=True); return

    database.get_or_create_user(uid_a)
    database.get_or_create_user(uid_b)

    trade_id = trade_mod.create_trade(interaction.user, user)
    embed    = discord.Embed(
        title="🔄 Trade Request",
        description=(f"**{interaction.user.display_name}** wants to trade with **{user.display_name}**\n\n"
                     f"You can offer **items** and **coins** to each other"),
        color=discord.Color.blurple()
    )
    embed.set_footer(text=f"{user.display_name}: Click ✅ to accept or ❌ to decline (expires in 60 seconds)")

    view = trade_mod.TradeRequestView(trade_id, uid_b)
    await interaction.response.send_message(embed=embed, view=view)

    msg = await interaction.original_response()
    trade_mod.active_trades[trade_id]["message"] = msg


# ╔══════════════════════════════════════════════════════════╗
#  SECTION 7 — EVENTS & RUN
# ╚══════════════════════════════════════════════════════════╝

@bot.event
async def on_ready():
    database.setup()
    await bot.tree.sync(guild=GUILD)
    if not scheduled_message_task.is_running():
        scheduled_message_task.start()
    print("=" * 40)
    print(f"✅ Bot ออนไลน์: {bot.user}")
    print("=" * 40)

bot.run(os.getenv("DISCORD_TOKEN"))
