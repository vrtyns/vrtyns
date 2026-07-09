# ============================================================
#  database/__init__.py — export ทุกอย่างออกมา
# ============================================================

from .connection import setup
from .users      import get_or_create_user, add_exp, update_coins
from .inventory  import ITEMS, ORES, add_item, remove_item, has_item, get_inventory
from .farming    import PLANTS, plant_crop, get_farms, harvest_ready
from .shop       import SHOP_ITEMS, buy_from_shop, sell_to_shop
from .quests     import (create_quest, get_all_quests,
                          assign_quest, complete_quest, get_user_quests)
from .scheduler  import (add_schedule, get_all_schedules,
                          remove_schedule, get_due_messages)
# from .daily      import can_claim, do_claim, get_streak              # ← เพิ่มใหม่
from .connection import get_conn
from .reaction_roles import (add_reaction_role, remove_reaction_role,
                              get_all_reaction_roles, get_role_for_reaction)
from .skills import add_skill, remove_skill, get_skills
from .buffs import (add_buff, get_active_buffs, has_buff,
                    get_buff_value, clear_debuff, remove_expired_buffs,
                    get_dice_modifier)   # ← เพิ่ม