# ============================================================
#  trade.py — ระบบแลกเปลี่ยนไอเทมและเงินระหว่าง user
#  วางไว้ข้างๆ main.py แล้ว import ใน main.py
# ============================================================

import discord
import database

# เก็บ trade ที่กำลัง active ไว้ใน memory
# (ถ้า bot restart, trade หายหมด — acceptable สำหรับ Discord bot)
active_trades: dict = {}


# ════════════════════════════════════════════════════════════
#  SECTION 1 — Utility Functions
# ════════════════════════════════════════════════════════════

def is_in_trade(user_id: str) -> bool:
    return any(user_id in (t["user_a_id"], t["user_b_id"]) for t in active_trades.values())


def create_trade(user_a: discord.Member, user_b: discord.Member) -> str:
    trade_id = f"{user_a.id}:{user_b.id}"
    active_trades[trade_id] = {
        "user_a_id":   str(user_a.id),
        "user_a_name": user_a.display_name,
        "user_b_id":   str(user_b.id),
        "user_b_name": user_b.display_name,
        "offer_a":     {"items": [], "coin": 0, "sil": 0},
        "offer_b":     {"items": [], "coin": 0, "sil": 0},
        "confirmed_a": False,
        "confirmed_b": False,
        "message":     None,
    }
    return trade_id


def remove_trade(trade_id: str):
    active_trades.pop(trade_id, None)


def get_side(trade_id: str, user_id: str) -> str | None:
    """คืน 'a' หรือ 'b' ตาม user_id, คืน None ถ้าไม่ใช่คนใน trade"""
    t = active_trades.get(trade_id)
    if not t: return None
    if user_id == t["user_a_id"]: return "a"
    if user_id == t["user_b_id"]: return "b"
    return None


def add_item_to_offer(trade_id: str, side: str, item_id: str, qty: int):
    """เพิ่ม/รวมไอเทมในออฟเฟอร์ และ reset confirm"""
    offer = active_trades[trade_id][f"offer_{side}"]
    for item in offer["items"]:
        if item["item_id"] == item_id:
            item["quantity"] += qty
            active_trades[trade_id][f"confirmed_{side}"] = False
            return
    offer["items"].append({"item_id": item_id, "quantity": qty})
    active_trades[trade_id][f"confirmed_{side}"] = False


def add_coins_to_offer(trade_id: str, side: str, coin: int, sil: int):
    offer = active_trades[trade_id][f"offer_{side}"]
    offer["coin"] += coin
    offer["sil"]  += sil
    active_trades[trade_id][f"confirmed_{side}"] = False


def build_trade_embed(trade_id: str) -> discord.Embed:
    t = active_trades[trade_id]
    embed = discord.Embed(
        title="🔄 การแลกเปลี่ยน",
        description=f"**{t['user_a_name']}**  ↔  **{t['user_b_name']}**",
        color=discord.Color.blurple(),
    )
    for side, name, confirmed in [
        ("a", t["user_a_name"], t["confirmed_a"]),
        ("b", t["user_b_name"], t["confirmed_b"]),
    ]:
        offer = t[f"offer_{side}"]
        lines = []
        for item in offer["items"]:
            info = database.ITEMS.get(item["item_id"], {})
            lines.append(f"{info.get('emoji','❓')} **{info.get('name', item['item_id'])}** ×{item['quantity']}")
        if offer["coin"]: lines.append(f"💰 **{offer['coin']:,}** Coin")
        if offer["sil"]:  lines.append(f"💎 **{offer['sil']:,}** Sil")
        status = "✅" if confirmed else "⏳"
        embed.add_field(name=f"{status}  {name}", value="\n".join(lines) or "_ยังว่างอยู่_", inline=True)
    embed.set_footer(text="ทั้งสองฝ่ายต้องกด ✅ ยืนยัน เพื่อ trade สำเร็จ")
    return embed


async def validate_and_execute(trade_id: str) -> tuple[bool, str]:
    """ตรวจสอบของ/เงินทั้งสองฝ่าย แล้ว execute การแลกเปลี่ยน"""
    t = active_trades.get(trade_id)
    if not t: return False, "ไม่พบข้อมูล trade"
    uid_a, uid_b = t["user_a_id"], t["user_b_id"]

    # ── ตรวจ A ───────────────────────────────
    for item in t["offer_a"]["items"]:
        if not database.has_item(uid_a, item["item_id"], item["quantity"]):
            name = database.ITEMS.get(item["item_id"], {}).get("name", item["item_id"])
            return False, f"**{t['user_a_name']}** มี **{name}** ไม่พอแล้ว!"
    ua, _ = database.get_or_create_user(uid_a)
    if ua["coin"] < t["offer_a"]["coin"] or ua["sil"] < t["offer_a"]["sil"]:
        return False, f"**{t['user_a_name']}** มีเงินไม่พอแล้ว!"

    # ── ตรวจ B ───────────────────────────────
    for item in t["offer_b"]["items"]:
        if not database.has_item(uid_b, item["item_id"], item["quantity"]):
            name = database.ITEMS.get(item["item_id"], {}).get("name", item["item_id"])
            return False, f"**{t['user_b_name']}** มี **{name}** ไม่พอแล้ว!"
    ub, _ = database.get_or_create_user(uid_b)
    if ub["coin"] < t["offer_b"]["coin"] or ub["sil"] < t["offer_b"]["sil"]:
        return False, f"**{t['user_b_name']}** มีเงินไม่พอแล้ว!"

    # ── Execute A → B ─────────────────────────
    for item in t["offer_a"]["items"]:
        database.remove_item(uid_a, item["item_id"], item["quantity"])
        database.add_item(uid_b, item["item_id"], item["quantity"])
    if t["offer_a"]["coin"] or t["offer_a"]["sil"]:
        database.update_coins(uid_a, -t["offer_a"]["coin"], -t["offer_a"]["sil"])
        database.update_coins(uid_b,  t["offer_a"]["coin"],  t["offer_a"]["sil"])

    # ── Execute B → A ─────────────────────────
    for item in t["offer_b"]["items"]:
        database.remove_item(uid_b, item["item_id"], item["quantity"])
        database.add_item(uid_a, item["item_id"], item["quantity"])
    if t["offer_b"]["coin"] or t["offer_b"]["sil"]:
        database.update_coins(uid_b, -t["offer_b"]["coin"], -t["offer_b"]["sil"])
        database.update_coins(uid_a,  t["offer_b"]["coin"],  t["offer_b"]["sil"])

    return True, "Trade สำเร็จ!"


# ════════════════════════════════════════════════════════════
#  SECTION 2 — Modals
# ════════════════════════════════════════════════════════════

class TradeItemModal(discord.ui.Modal):
    def __init__(self, trade_id: str, side: str, item_id: str):
        info = database.ITEMS.get(item_id, {})
        super().__init__(title=f"เพิ่ม {info.get('emoji','')} {info.get('name', item_id)}")
        self.trade_id = trade_id
        self.side     = side
        self.item_id  = item_id
        self.qty = discord.ui.TextInput(
            label="จำนวน", placeholder="1", default="1", min_length=1, max_length=4
        )
        self.add_item(self.qty)

    async def on_submit(self, interaction: discord.Interaction):
        try:
            qty = int(self.qty.value)
            if qty <= 0: raise ValueError
        except ValueError:
            await interaction.response.send_message("❌ จำนวนต้องเป็นตัวเลขมากกว่า 0", ephemeral=True)
            return

        uid = str(interaction.user.id)
        if not database.has_item(uid, self.item_id, qty):
            name = database.ITEMS.get(self.item_id, {}).get("name", self.item_id)
            await interaction.response.send_message(f"❌ **{name}** ×{qty} ใน inventory ไม่พอ", ephemeral=True)
            return

        add_item_to_offer(self.trade_id, self.side, self.item_id, qty)

        t = active_trades.get(self.trade_id)
        if t and t.get("message"):
            await t["message"].edit(embed=build_trade_embed(self.trade_id))

        info = database.ITEMS.get(self.item_id, {})
        await interaction.response.send_message(
            f"✅ เพิ่ม {info.get('emoji','')} **{info.get('name', self.item_id)}** ×{qty} สำเร็จ!",
            ephemeral=True,
        )


class TradeMoneyModal(discord.ui.Modal):
    def __init__(self, trade_id: str, side: str):
        super().__init__(title="💰 เพิ่มเงินใน trade")
        self.trade_id = trade_id
        self.side     = side
        self.coin = discord.ui.TextInput(
            label="Coin (ใส่ 0 ถ้าไม่ต้องการ)", placeholder="0", default="0", min_length=1, max_length=10
        )
        self.sil = discord.ui.TextInput(
            label="Sil (ใส่ 0 ถ้าไม่ต้องการ)", placeholder="0", default="0", min_length=1, max_length=10
        )
        self.add_item(self.coin)
        self.add_item(self.sil)

    async def on_submit(self, interaction: discord.Interaction):
        try:
            coin = int(self.coin.value)
            sil  = int(self.sil.value)
            if coin < 0 or sil < 0: raise ValueError
        except ValueError:
            await interaction.response.send_message("❌ กรุณาใส่ตัวเลขที่ถูกต้อง (≥ 0)", ephemeral=True)
            return

        if coin == 0 and sil == 0:
            await interaction.response.send_message("❌ ต้องใส่มากกว่า 0 อย่างน้อย 1 อย่าง", ephemeral=True)
            return

        t = active_trades.get(self.trade_id)
        if not t:
            await interaction.response.send_message("❌ Trade หมดอายุแล้ว", ephemeral=True)
            return

        u, _ = database.get_or_create_user(str(interaction.user.id))
        offer = t[f"offer_{self.side}"]
        if (offer["coin"] + coin) > u["coin"] or (offer["sil"] + sil) > u["sil"]:
            await interaction.response.send_message("❌ เงินที่ใส่รวมกันแล้วเกินกว่าที่มี!", ephemeral=True)
            return

        add_coins_to_offer(self.trade_id, self.side, coin, sil)

        if t.get("message"):
            await t["message"].edit(embed=build_trade_embed(self.trade_id))

        parts = ([f"**{coin:,} Coin**"] if coin else []) + ([f"**{sil:,} Sil**"] if sil else [])
        await interaction.response.send_message(f"✅ เพิ่ม {' และ '.join(parts)} สำเร็จ!", ephemeral=True)


# ════════════════════════════════════════════════════════════
#  SECTION 3 — Select + View สำหรับเลือกไอเทม (ephemeral)
# ════════════════════════════════════════════════════════════

class TradeItemSelect(discord.ui.Select):
    def __init__(self, trade_id: str, side: str, inventory: list):
        self.trade_id = trade_id
        self.side     = side
        options = [
            discord.SelectOption(
                label=f"{database.ITEMS[r['item_id']]['name']} (มี {r['quantity']})",
                value=r["item_id"],
                emoji=database.ITEMS[r["item_id"]]["emoji"],
            )
            for r in inventory[:25]
            if r["item_id"] in database.ITEMS
        ]
        if not options:
            options = [discord.SelectOption(label="ไม่มีไอเทมใน inventory", value="none")]
        super().__init__(
            placeholder="เลือกไอเทมที่ต้องการเสนอใน trade",
            options=options,
            disabled=(not options or options[0].value == "none"),
        )

    async def callback(self, interaction: discord.Interaction):
        if self.values[0] == "none": return
        await interaction.response.send_modal(
            TradeItemModal(self.trade_id, self.side, self.values[0])
        )


class TradeItemView(discord.ui.View):
    def __init__(self, trade_id: str, side: str):
        super().__init__(timeout=60)
        uid = active_trades[trade_id][f"user_{side}_id"]
        inv = database.get_inventory(uid)
        self.add_item(TradeItemSelect(trade_id, side, inv))


# ════════════════════════════════════════════════════════════
#  SECTION 4 — Main Trade Views
# ════════════════════════════════════════════════════════════

class TradeView(discord.ui.View):
    """View หลักของ trade — แสดงหลัง UserB ตอบรับ"""

    def __init__(self, trade_id: str):
        super().__init__(timeout=300)
        self.trade_id = trade_id

    async def on_timeout(self):
        t = active_trades.get(self.trade_id)
        if t and t.get("message"):
            try:
                embed = discord.Embed(
                    title="⏰ Trade หมดเวลา",
                    description="การแลกเปลี่ยนถูกยกเลิกอัตโนมัติเพราะไม่มีการตอบสนองใน 5 นาที",
                    color=discord.Color.greyple(),
                )
                await t["message"].edit(embed=embed, view=None)
            except Exception:
                pass
        remove_trade(self.trade_id)

    async def _check(self, interaction: discord.Interaction) -> str | None:
        """ตรวจสอบว่าคนกดปุ่มคือผู้เล่นใน trade นี้ — คืน side หรือ None"""
        side = get_side(self.trade_id, str(interaction.user.id))
        if not side:
            await interaction.response.send_message(
                "❌ คุณไม่ได้อยู่ใน trade นี้!", ephemeral=True
            )
        return side

    @discord.ui.button(label="➕ เพิ่มไอเทม", style=discord.ButtonStyle.secondary, row=0)
    async def add_item_btn(self, interaction: discord.Interaction, _: discord.ui.Button):
        side = await self._check(interaction)
        if not side: return
        await interaction.response.send_message(
            "เลือกไอเทมที่ต้องการเสนอ:",
            view=TradeItemView(self.trade_id, side),
            ephemeral=True,
        )

    @discord.ui.button(label="💰 เพิ่มเงิน", style=discord.ButtonStyle.secondary, row=0)
    async def add_money_btn(self, interaction: discord.Interaction, _: discord.ui.Button):
        side = await self._check(interaction)
        if not side: return
        await interaction.response.send_modal(TradeMoneyModal(self.trade_id, side))

    @discord.ui.button(label="✅ ยืนยัน", style=discord.ButtonStyle.success, row=1)
    async def confirm_btn(self, interaction: discord.Interaction, _: discord.ui.Button):
        side = await self._check(interaction)
        if not side: return

        t = active_trades.get(self.trade_id)
        if not t:
            await interaction.response.send_message("❌ ไม่พบข้อมูล trade", ephemeral=True)
            return

        t[f"confirmed_{side}"] = True

        if t["confirmed_a"] and t["confirmed_b"]:
            success, err = await validate_and_execute(self.trade_id)
            if success:
                self.stop()
                ua_name, ub_name = t["user_a_name"], t["user_b_name"]
                remove_trade(self.trade_id)
                embed = discord.Embed(
                    title="✅ Trade สำเร็จ!",
                    description=f"**{ua_name}** และ **{ub_name}** แลกเปลี่ยนกันเรียบร้อยแล้ว!",
                    color=discord.Color.green(),
                )
                await interaction.response.edit_message(embed=embed, view=None)
            else:
                # ล้าง confirm ทั้งคู่ ให้ user แก้ไขก่อนยืนยันใหม่
                t["confirmed_a"] = False
                t["confirmed_b"] = False
                embed = build_trade_embed(self.trade_id)
                embed.color = discord.Color.red()
                embed.set_footer(text=f"❌ {err} — กรุณาตรวจสอบแล้วยืนยันใหม่")
                await interaction.response.edit_message(embed=embed)
        else:
            await interaction.response.edit_message(embed=build_trade_embed(self.trade_id))

    @discord.ui.button(label="❌ ยกเลิก", style=discord.ButtonStyle.danger, row=1)
    async def cancel_btn(self, interaction: discord.Interaction, _: discord.ui.Button):
        side = await self._check(interaction)
        if not side: return
        self.stop()
        remove_trade(self.trade_id)
        embed = discord.Embed(
            title="❌ Trade ถูกยกเลิก",
            description=f"**{interaction.user.display_name}** ยกเลิกการแลกเปลี่ยน",
            color=discord.Color.red(),
        )
        await interaction.response.edit_message(embed=embed, view=None)


class TradeRequestView(discord.ui.View):
    """View ขั้นแรก — รอ UserB ตอบรับหรือปฏิเสธ"""

    def __init__(self, trade_id: str, user_b_id: str):
        super().__init__(timeout=60)
        self.trade_id  = trade_id
        self.user_b_id = user_b_id

    async def on_timeout(self):
        t = active_trades.get(self.trade_id)
        if t and t.get("message"):
            try:
                embed = discord.Embed(
                    title="⏰ คำเชิญหมดเวลา",
                    description="ไม่มีการตอบรับภายใน 60 วินาที",
                    color=discord.Color.greyple(),
                )
                await t["message"].edit(embed=embed, view=None)
            except Exception:
                pass
        remove_trade(self.trade_id)

    @discord.ui.button(label="✅ ตอบรับ", style=discord.ButtonStyle.success)
    async def accept_btn(self, interaction: discord.Interaction, _: discord.ui.Button):
        if str(interaction.user.id) != self.user_b_id:
            await interaction.response.send_message("❌ ไม่ใช่การ trade ของคุณ!", ephemeral=True)
            return
        self.stop()
        trade_view = TradeView(self.trade_id)
        await interaction.response.edit_message(embed=build_trade_embed(self.trade_id), view=trade_view)
        active_trades[self.trade_id]["message"] = interaction.message

    @discord.ui.button(label="❌ ปฏิเสธ", style=discord.ButtonStyle.danger)
    async def decline_btn(self, interaction: discord.Interaction, _: discord.ui.Button):
        if str(interaction.user.id) != self.user_b_id:
            await interaction.response.send_message("❌ ไม่ใช่การ trade ของคุณ!", ephemeral=True)
            return
        t = active_trades.get(self.trade_id) or {}
        self.stop()
        remove_trade(self.trade_id)
        embed = discord.Embed(
            title="❌ ปฏิเสธการแลกเปลี่ยน",
            description=f"**{interaction.user.display_name}** ปฏิเสธคำเชิญ trade จาก **{t.get('user_a_name','?')}**",
            color=discord.Color.red(),
        )
        await interaction.response.edit_message(embed=embed, view=None)
