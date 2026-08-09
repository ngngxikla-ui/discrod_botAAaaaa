import asyncio
from datetime import datetime, timedelta
import json
import os
import random
import re
import sqlite3
import string
import threading
from flask import Flask, jsonify, request
import cloudscraper
import discord
from discord import app_commands
from discord.ext import commands
from myserver import server_on

# ==========================================
# ⚙️ [ตั้งค่าคอนฟิกหลักและการแยก ID แต่ละห้อง]
# ==========================================
GUILD_ID = 1448273040961048618  #

PHONE_NUMBER = "0619612338"  #
PROMPTPAY_NUMBER = "0619612338"  #
TOPUP_DASHBOARD_CHANNEL_ID = 1531619438988890222  #

CONTROL_ROOM_CHANNEL_ID = 1531353093935993001  #
ADMIN_CMD_CHANNEL_ID = 1448273041963618386  #[cite: 10, 11]
RESET_KEY_CHANNEL_ID = 1531390970304663602  #[cite: 10, 11]
LICENSE_LIST_CHANNEL_ID = 1531328817765941460  #[cite: 10, 11]
ACTIVE_HWID_CHANNEL_ID = 1531328835969355878  #[cite: 10, 11]
LOG_CHANNEL_ID = 1531328859763507280  #[cite: 10, 11]
REACTION_LOG_CHANNEL_ID = 1531615505960669235  #[cite: 11]
REACTION_ROLE_CHANNEL_ID = 1531630494259740814  #[cite: 11]

GAME_CHANNEL_ID = 1531651090272227328  #[cite: 11]

ALLOWED_ROLE_IDS = [1448273316610838680, 1531365478109417715]  #[cite: 10, 11]
CUSTOMER_ROLE_ID = 1531392425656848504  #[cite: 10, 11]

GIF_BANNER_URL = "https://cdn.discordapp.com/attachments/1531353093935993001/1531357566385389648/From-Klickpin.com-Sleep-Routine-Tips-73-Ideas-to-Copy-pin-id-1052505375422933587.gif?ex=6a68eb5f&is=6a6799df&hm=013fbaa1f8e97904c5069160e861992c6948b6778068c5c6d0f0f090f17206b3&"  #[cite: 10, 11]

DB_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "bot_licenses.db"
)  #[cite: 10, 11]
TOPUP_DB_FILE = "database.json"  #[cite: 11]
USERDATA_FILE = "userdata.json"  #[cite: 11]

COOLDOWN_TIME = 10  #[cite: 11]
ORES_CONFIG = [
    {
        "name": "💎 Diamond",
        "chance": 0.1,
        "price_per_size": 100,
        "min_size": 1,
        "max_size": 3,
    },
    {
        "name": "💚 Emerald",
        "chance": 0.2,
        "price_per_size": 70,
        "min_size": 1,
        "max_size": 3,
    },
    {
        "name": "🪙 Gold",
        "chance": 0.3,
        "price_per_size": 40,
        "min_size": 1,
        "max_size": 4,
    },
    {
        "name": "⚙️ Iron",
        "chance": 0.4,
        "price_per_size": 20,
        "min_size": 1,
        "max_size": 5,
    },
]  #[cite: 11]

intents = discord.Intents.all()  #[cite: 11]


def is_admin_or_has_role(member: discord.Member) -> bool:
  if not member:
    return False
  if member.guild_permissions.administrator:
    return True
  return any(role.id in ALLOWED_ROLE_IDS for role in member.roles)  #[cite: 11]


class MyBot(commands.Bot):

  def __init__(self):
    super().__init__(command_prefix=["/", "!"], intents=intents)

  async def setup_hook(self):
    try:
      guild = discord.Object(id=GUILD_ID)
      self.tree.copy_global_to(guild=guild)
      await self.tree.sync(guild=guild)
      print("Synced Slash Commands to Guild successfully!")
    except Exception as e:
      print(f"Failed to sync commands: {e}")  #[cite: 11]


bot = MyBot()

license_msg_id = None
hwid_msg_id = None
game_panel_msg_id = None
topup_msg_id = None
pending_commands = {}  #[cite: 10, 11]
recent_logs = []  #[cite: 10, 11]
user_reset_tracker = {}  #[cite: 11]
scraper = cloudscraper.create_scraper()  #[cite: 11]


def init_db():
  conn = sqlite3.connect(DB_PATH, check_same_thread=False)
  cursor = conn.cursor()
  cursor.execute(
      """
        CREATE TABLE IF NOT EXISTS licenses (
            key TEXT PRIMARY KEY,
            duration_days INTEGER,
            expiry_date TEXT,
            hwid TEXT,
            status TEXT,
            paused_days INTEGER DEFAULT 0
        )
    """
  )
  conn.commit()
  conn.close()


init_db()  #[cite: 10, 11]


def load_topup_db():
  if not os.path.exists(TOPUP_DB_FILE):
    return {}
  try:
    with open(TOPUP_DB_FILE, "r", encoding="utf-8") as f:
      return json.load(f)
  except Exception:
    return {}  #[cite: 11]


def save_topup_db(db):
  try:
    with open(TOPUP_DB_FILE, "w", encoding="utf-8") as f:
      json.dump(db, f, indent=4, ensure_ascii=False)
  except Exception as e:
    print(f"Error saving topup db: {e}")  #[cite: 11]


def load_user_data():
  if os.path.exists(USERDATA_FILE):
    try:
      with open(USERDATA_FILE, "r", encoding="utf-8") as f:
        return json.load(f)
    except Exception:
      return {}
  return {}  #[cite: 11]


def save_user_data(data):
  try:
    with open(USERDATA_FILE, "w", encoding="utf-8") as f:
      json.dump(data, f, indent=2, ensure_ascii=False)
  except Exception as e:
    print(f"Error saving user data: {e}")  #[cite: 11]


user_data = load_user_data()  #[cite: 11]


def get_random_ore():
  rand = random.random()
  cumulative = 0
  for ore in ORES_CONFIG:
    cumulative += ore["chance"]
    if rand < cumulative:
      size = random.randint(ore["min_size"], ore["max_size"])
      price = size * ore["price_per_size"]
      return {"name": ore["name"], "size": size, "price": price}
  return None  #[cite: 11]


def send_log(text):
  global recent_logs
  recent_logs.insert(0, f"[{datetime.now().strftime('%H:%M:%S')}] {text}")
  if len(recent_logs) > 20:
    recent_logs.pop()
  if LOG_CHANNEL_ID and bot.is_ready():
    asyncio.run_coroutine_threadsafe(async_send_log(text), bot.loop)  #[cite: 10, 11]


async def async_send_log(text):
  channel = bot.get_channel(LOG_CHANNEL_ID)
  if channel:
    try:
      await channel.send(text)
    except Exception:
      pass  #[cite: 10, 11]


# ==========================================
# 🌐 [FLASK API สำหรับเชื่อมต่อ Client Toolkit]
# ==========================================
app = Flask("Discord Bot")


@app.route("/verify", methods=["POST"])
def verify():
  data = request.json or request.form
  key = data.get("key")
  hwid = data.get("hwid")
  action = data.get("action", "verify")

  if key:
    key = key.replace("\u200b", "").replace("\ufeff", "").strip()
  if hwid:
    hwid = hwid.replace("\u200b", "").replace("\ufeff", "").strip()

  conn = sqlite3.connect(DB_PATH, check_same_thread=False)
  cursor = conn.cursor()

  if action == "close":
    cursor.execute("SELECT duration_days FROM licenses WHERE key = ?", (key,))
    conn.close()
    send_log(
        f"🔴 **[Client Log] ลูกค้าปิดโปรแกรม**\n🔑 คีย์: `{key}`\n💻 HWID:"
        f" `{hwid}`"
    )
    if bot.is_ready():
      asyncio.run_coroutine_threadsafe(update_dashboards(), bot.loop)
    return jsonify({"status": "success", "message": "Closed logged"})

  if action == "poll_command":
    cmd = pending_commands.pop(hwid, "none")
    conn.close()
    return jsonify({"status": "success", "command": cmd})

  if not key:
    conn.close()
    return jsonify({"status": "error", "message": "No key provided!"})

  cursor.execute(
      "SELECT duration_days, expiry_date, hwid, status FROM licenses WHERE key"
      " = ?",
      (key,),
  )
  row = cursor.fetchone()

  if not row:
    conn.close()
    return jsonify({"status": "error", "message": "Invalid Key!"})

  duration_days, expiry_date, reg_hwid, status = row
  now = datetime.now()

  if status == "Paused":
    conn.close()
    return jsonify({"status": "error", "message": "License is Paused!"})

  cursor.execute(
      "SELECT key FROM licenses WHERE hwid = ? AND key != ?", (hwid, key)
  )
  other_bound_key = cursor.fetchone()
  if other_bound_key:
    conn.close()
    send_log(
        f"⚠️ **[Security Alert] HWID พยายามใช้หลายคีย์**\n💻 HWID:"
        f" `{hwid}`\n🔑 คีย์พยายามสลับ: `{key}` (ผูกกับคีย์"
        f" `{other_bound_key[0]}` อยู่แล้ว)"
    )
    return jsonify(
        {
            "status": "error",
            "message": "This PC is already bound to another key!",
        }
    )

  if duration_days == 0:
    if not reg_hwid:
      cursor.execute(
          'UPDATE licenses SET hwid = ?, status = "Active" WHERE key = ?',
          (hwid, key),
      )
      conn.commit()
      conn.close()
      send_log(
          f"🟢 **[Client Log] เปิดใช้งานครั้งแรก (คีย์ถาวร)**\n🔑 คีย์:"
          f" `{key}`\n💻 HWID: `{hwid}`"
      )
      if bot.is_ready():
        asyncio.run_coroutine_threadsafe(update_dashboards(), bot.loop)
      return jsonify({"status": "success", "message": "Activated"})
    elif reg_hwid == hwid:
      conn.close()
      send_log(
          f"💻 **[Client Log] ลูกค้าเปิดโปรแกรม (คีย์ถาวร)**\n🔑 คีย์:"
          f" `{key}`\n💻 HWID: `{hwid}`"
      )
      if bot.is_ready():
        asyncio.run_coroutine_threadsafe(update_dashboards(), bot.loop)
      return jsonify({"status": "success", "message": "Welcome back"})
    else:
      conn.close()
      return jsonify(
          {"status": "error", "message": "Key locked to another PC!"}
      )

  if not reg_hwid or status == "Unused":
    expiry = now + timedelta(days=duration_days)
    expiry_str = expiry.strftime("%Y-%m-%d %H:%M:%S")
    cursor.execute(
        "UPDATE licenses SET hwid = ?, expiry_date = ?, status = 'Active' WHERE"
        " key = ?",
        (hwid, expiry_str, key),
    )
    conn.commit()
    conn.close()
    send_log(
        f"🟢 **[Client Log] เปิดใช้งานครั้งแรก ({duration_days} วัน)**\n🔑 คีย์:"
        f" `{key}`\n💻 HWID: `{hwid}`"
    )
    if bot.is_ready():
      asyncio.run_coroutine_threadsafe(update_dashboards(), bot.loop)
    return jsonify(
        {"status": "success", "message": "Activated", "expiry": expiry_str}
    )

  if reg_hwid != hwid:
    conn.close()
    return jsonify({"status": "error", "message": "HWID Mismatch!"})

  expiry_dt = datetime.strptime(expiry_date, "%Y-%m-%d %H:%M:%S")
  if now > expiry_dt:
    cursor.execute('UPDATE licenses SET status = "Expired" WHERE key = ?', (key,))
    conn.commit()
    conn.close()
    if bot.is_ready():
      asyncio.run_coroutine_threadsafe(update_dashboards(), bot.loop)
    return jsonify({"status": "error", "message": "License Expired"})

  conn.close()
  send_log(
      f"💻 **[Client Log] ลูกค้าเปิดโปรแกรมใช้งาน**\n🔑 คีย์: `{key}`\n💻"
      f" HWID: `{hwid}`"
  )
  if bot.is_ready():
    asyncio.run_coroutine_threadsafe(update_dashboards(), bot.loop)
  return jsonify({"status": "success", "message": "Active"})


def run_flask():
  app.run(host="0.0.0.0", port=5000, debug=False, use_reloader=False)


# ==========================================
# 💰 [ระบบเติมเงิน TrueMoney ซองอั่งเปา]
# ==========================================
def create_topup_dashboard_embed(db):
  embed = discord.Embed(
      title="📊 ตารางสถานะและยอดเงินกระเป๋า (Real-time)",
      description="ระบบเติมเงินผ่านซองอั่งเปา TrueMoney และพร้อมเพย์อัตโนมัติ",
      color=0x00FF00,
  )
  if not db:
    embed.add_field(name="สถานะ", value="ยังไม่มีข้อมูลผู้ใช้งานในระบบ", inline=False)
  else:
    user_list = []
    for u_id, data in db.items():
      points = data.get("point", 0)
      user_list.append(f"<@{u_id}> ➔ **{points:,.2f} ฿**")
    chunks = [user_list[i : i + 10] for i in range(0, len(user_list), 10)]
    for i, chunk in enumerate(chunks):
      embed.add_field(
          name=f"รายชื่อสมาชิก (ชุดที่ {i+1})",
          value="\n".join(chunk),
          inline=False,
      )
  embed.set_footer(
      text=f"อัปเดตล่าสุดอัตโนมัติ | เบอร์รับซอง: {PHONE_NUMBER}"
  )
  return embed


class TopupModal(discord.ui.Modal):

  def __init__(self, bot_instance):
    super().__init__(title="『 เติมเงิน TrueMoney ซองอั่งเปา 』")
    self.bot_instance = bot_instance
    self.link = discord.ui.TextInput(
        label="ลิงก์ซองอั่งเปา",
        placeholder="https://gift.truemoney.com/campaign/?v=...",
        required=True,
    )
    self.add_item(self.link)

  async def callback(self, interaction: discord.Interaction):
    link = str(self.link.value).replace(" ", "")
    if re.match(
        r"https:\/\/gift\.truemoney\.com\/campaign\/\?v=[a-zA-Z0-9]{18}", link
    ):
      hash_v = link.split("?v=")[1]
      try:
        res = scraper.post(
            f"https://gift.truemoney.com/campaign/vouchers/{hash_v}/redeem",
            json={"mobile": PHONE_NUMBER, "voucher_hash": hash_v},
            timeout=15,
        )
        data = res.json()
        if (
            res.status_code == 200
            and data.get("status", {}).get("code") == "SUCCESS"
        ):
          amount = float(data["data"]["my_ticket"]["amount_baht"])
          db = load_topup_db()
          u_id = str(interaction.user.id)
          if u_id not in db:
            db[u_id] = {"point": 0, "expire_date": "ไม่มี", "role_id": None}
          db[u_id]["point"] += amount
          save_topup_db(db)
          await self.bot_instance.update_topup_dashboard_panel()

          embed = discord.Embed(
              title="✅ เติมเงินสำเร็จ!",
              description=(
                  f"ได้รับยอดเงินเข้ากระเป๋า: `{amount:,.2f}` ฿\nยอดสะสมรวม:"
                  f" `{db[u_id]['point']:,.2f}` ฿"
              ),
              color=discord.Color.green(),
          )
          await interaction.response.send_message(embed=embed, ephemeral=True)
        else:
          await interaction.response.send_message(
              "❌ ซองอั่งเปานี้ถูกใช้ไปแล้ว หรือลิงก์ไม่ถูกต้อง", ephemeral=True
          )
      except Exception:
        await interaction.response.send_message(
            "⚠️ ไม่สามารถติดต่อระบบ TrueMoney ได้ในขณะนี้", ephemeral=True
        )
    else:
      await interaction.response.send_message(
          "⚠️ รูปแบบลิงก์ซองอั่งเปาไม่ถูกต้อง", ephemeral=True
      )


class TopupView(discord.ui.View):

  def __init__(self, bot_instance):
    super().__init__(timeout=None)
    self.bot_instance = bot_instance

  @discord.ui.button(
      label="เติมเงิน (TrueMoney)",
      style=discord.ButtonStyle.green,
      custom_id="topup_receive_btn",
      emoji="💳",
  )
  async def topup_button(
      self, interaction: discord.Interaction, button: discord.ui.Button
  ):
    await interaction.response.send_modal(TopupModal(self.bot_instance))

  @discord.ui.button(
      label="เช็คยอดเงิน (Admin)",
      style=discord.ButtonStyle.blurple,
      custom_id="check_balance_btn",
      emoji="🏦",
  )
  async def check_balance_button(
      self, interaction: discord.Interaction, button: discord.ui.Button
  ):
    if not is_admin_or_has_role(interaction.user):
      await interaction.response.send_message(
          "❌ ปุ่มนี้สำหรับแอดมินเท่านั้น", ephemeral=True
      )
      return
    db = load_topup_db()
    embed = discord.Embed(
        title="🏦 สรุปยอดเงินสมาชิกทั้งหมดในระบบ", color=discord.Color.gold()
    )
    if not db:
      embed.description = "ยังไม่มีข้อมูลผู้ใช้งานในระบบ"
    else:
      desc = ""
      for u_id, data in db.items():
        desc += f"<@{u_id}> ➔ `{data.get('point', 0):,.2f}` ฿\n"
      embed.description = desc
    await interaction.response.send_message(embed=embed, ephemeral=True)


# ==========================================
# 🎮 [ระบบมินิเกมขุดแร่ & แลกคีย์]
# ==========================================
def check_game_channel(interaction: discord.Interaction) -> bool:
  if GAME_CHANNEL_ID != 0 and interaction.channel.id != GAME_CHANNEL_ID:
    return False
  return True


class GameControlView(discord.ui.View):

  def __init__(self):
    super().__init__(timeout=None)

  @discord.ui.button(
      label="⛏️ ขุดเหมือง",
      style=discord.ButtonStyle.success,
      custom_id="game_mine_btn",
  )
  async def mine_button(
      self, interaction: discord.Interaction, button: discord.ui.Button
  ):
    if not check_game_channel(interaction):
      await interaction.response.send_message(
          f"❌ กรุณาเล่นเกมในห้อง <#{GAME_CHANNEL_ID}> เท่านั้น!", ephemeral=True
      )
      return

    user_id = str(interaction.user.id)
    now = __import__("time").time()
    user_data.setdefault(
        user_id, {"ores": [], "points": 0, "last_mine": 0}
    )
    last_time = user_data[user_id]["last_mine"]

    if now - last_time < COOLDOWN_TIME:
      remaining = int(COOLDOWN_TIME - (now - last_time))
      await interaction.response.send_message(
          f"⏳ กำลังเหนื่อยพักหายใจ... กรุณารออีก `{remaining}` วินาที",
          ephemeral=True,
      )
      return

    ore = get_random_ore()
    if not ore:
      await interaction.response.send_message(
          "❌ ขุดไม่เจออะไรเลย ลองใหม่อีกครั้ง!", ephemeral=True
      )
      return

    user_data[user_id]["ores"].append(ore)
    user_data[user_id]["last_mine"] = now
    save_user_data(user_data)

    embed = discord.Embed(
        title="⛏️ ผลการขุดเหมืองสำเร็จ!",
        description=(
            f"👤 นักขุด: {interaction.user.mention}\n✨ ขุดพบแร่:"
            f" **{ore['name']}**\n📦 ขนาด: `{ore['size']}` หน่วย\n💰 มูลค่า:"
            f" `{ore['price']}` พ้อยต์"
        ),
        color=discord.Color.from_rgb(255, 215, 0),
    )
    await interaction.response.send_message(embed=embed, ephemeral=True)

  @discord.ui.button(
      label="📦 เช็คกระเป๋าแร่",
      style=discord.ButtonStyle.primary,
      custom_id="game_check_btn",
  )
  async def check_button(
      self, interaction: discord.Interaction, button: discord.ui.Button
  ):
    if not check_game_channel(interaction):
      await interaction.response.send_message(
          f"❌ กรุณาใช้ปุ่มนี้ในห้อง <#{GAME_CHANNEL_ID}> เท่านั้น!",
          ephemeral=True,
      )
      return

    user_id = str(interaction.user.id)
    data = user_data.get(user_id, {"ores": [], "points": 0})
    ore_lines = "\n".join([
        f"• {o['name']} (ขนาด {o['size']}) ➔ `{o['price']}` พ้อยต์"
        for o in data["ores"]
    ])
    ore_display = (
        ore_lines
        if ore_lines
        else "📭 กระเป๋าว่างเปล่า (ยังไม่ได้ขุดแร่สะสม)"
    )

    embed = discord.Embed(
        title=f"🎒 กระเป๋าแร่ของ {interaction.user.name}",
        description=f"{ore_display}\n\n💰 **พ้อยต์สะสมทั้งหมด:** `{data['points']}`"
        " พ้อยต์",
        color=discord.Color.from_rgb(0, 191, 255),
    )
    await interaction.response.send_message(embed=embed, ephemeral=True)

  @discord.ui.button(
      label="💸 ขายแร่ทั้งหมด",
      style=discord.ButtonStyle.danger,
      custom_id="game_sell_btn",
  )
  async def sell_button(
      self, interaction: discord.Interaction, button: discord.ui.Button
  ):
    if not check_game_channel(interaction):
      await interaction.response.send_message(
          f"❌ กรุณาใช้ปุ่มนี้ในห้อง <#{GAME_CHANNEL_ID}> เท่านั้น!",
          ephemeral=True,
      )
      return

    user_id = str(interaction.user.id)
    data = user_data.get(user_id, {"ores": [], "points": 0})
    if not data["ores"]:
      await interaction.response.send_message(
          "❌ คุณไม่มีแร่ในกระเป๋าให้ขาย", ephemeral=True
      )
      return

    total = sum(o["price"] for o in data["ores"])
    data["points"] += total
    data["ores"] = []
    save_user_data(user_data)

    embed = discord.Embed(
        title="💸 ขายแร่สำเร็จ!",
        description=(
            f"คุณได้รับพ้อยต์จากการขายแร่รวมทั้งสิ้น: `+{total}`"
            f" พ้อยต์\n💰 ยอดพ้อยต์คงเหลือ: `{data['points']}` พ้อยต์"
        ),
        color=discord.Color.green(),
    )
    await interaction.response.send_message(embed=embed, ephemeral=True)

  @discord.ui.button(
      label="🎁 แลกคีย์ 1 วัน (300 🪙)",
      style=discord.ButtonStyle.secondary,
      custom_id="game_redeem_key_btn",
  )
  async def redeem_btn(
      self, interaction: discord.Interaction, button: discord.ui.Button
  ):
    if not check_game_channel(interaction):
      await interaction.response.send_message(
          f"❌ กรุณาใช้ปุ่มนี้ในห้อง <#{GAME_CHANNEL_ID}> เท่านั้น!",
          ephemeral=True,
      )
      return

    user_id = str(interaction.user.id)
    data = user_data.get(user_id, {"ores": [], "points": 0})
    cost = 300

    if data["points"] < cost:
      await interaction.response.send_message(
          f"❌ พ้อยต์ไม่พอ! (ต้องการ `{cost}` พ้อยต์ แต่คุณมี `{data['points']}`"
          " พ้อยต์)",
          ephemeral=True,
      )
      return

    data["points"] -= cost
    save_user_data(user_data)

    key = "".join(random.choices(string.ascii_uppercase + string.digits, k=16))
    key_formatted = f"{key[0:4]}-{key[4:8]}-{key[8:12]}-{key[12:16]}"

    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO licenses (key, duration_days, expiry_date, hwid, status,"
        " paused_days) VALUES (?, ?, ?, ?, ?, ?)",
        (key_formatted, 1, None, None, "Unused", 0),
    )
    conn.commit()
    conn.close()

    embed = discord.Embed(
        title="🎉 แลกคีย์ใช้งานสำเร็จ!",
        description=(
            f"🔑 คีย์ของคุณ: `{key_formatted}`\n⏳ ระยะเวลา: `1 วัน`\n💰"
            f" พ้อยต์คงเหลือ: `{data['points']}` พ้อยต์"
        ),
        color=discord.Color.from_rgb(138, 43, 226),
    )
    await interaction.response.send_message(embed=embed, ephemeral=True)

    send_log(
        f"🎁 **[Game Redeem Log]**\n👤 ผู้ใช้: `{interaction.user.name}`"
        f" ({interaction.user.mention})\n🔑 แลกคีย์สำเร็จ: `{key_formatted}`"
    )
    await update_dashboards()


# ==========================================
# 🎛️ [MODALS & SELECT MENUS สำหรับแอดมิน]
# ==========================================
class ResetUserQuotaModal(discord.ui.Modal):

  def __init__(self):
    super().__init__(title="🔄 รีเซ็ตโควตารายคน")
    self.user_id_input = discord.ui.TextInput(
        label="กรอก User ID ของสมาชิกที่ต้องการรีเซ็ต",
        placeholder="เช่น 123456789012345678",
        required=True,
    )
    self.add_item(self.user_id_input)

  async def callback(self, interaction: discord.Interaction):
    if not is_admin_or_has_role(interaction.user):
      await interaction.response.send_message(
          "❌ เฉพาะแอดมินเท่านั้น", ephemeral=True
      )
      return
    try:
      target_id = int(self.user_id_input.value.strip())
      if target_id in user_reset_tracker:
        user_reset_tracker[target_id] = {
            "count": 0,
            "reset_time": datetime.now(),
        }
        await interaction.response.send_message(
            f"✅ **รีเซ็ตโควตาของ <@{target_id}> สำเร็จแล้ว!**", ephemeral=True
        )
        send_log(
            f"👑 **[Admin Log]** แอดมิน `{interaction.user.name}` ได้ทำการรีเซ็ตโควตาการใช้งานของ"
            f" <@{target_id}>"
        )
      else:
        await interaction.response.send_message(
            "❌ สมาชิกคนนี้ยังไม่มีประวัติการใช้งานโควตาในวันนี้",
            ephemeral=True,
        )
    except ValueError:
      await interaction.response.send_message(
          "❌ กรุณากรอก ID เป็นตัวเลขเท่านั้น", ephemeral=True
      )


class QuotaManageView(discord.ui.View):

  def __init__(self):
    super().__init__(timeout=60)

  @discord.ui.button(
      label="🔄 รีเซ็ตโควตารายคน",
      style=discord.ButtonStyle.danger,
      custom_id="reset_single_quota",
  )
  async def reset_single_quota_btn(
      self, interaction: discord.Interaction, button: discord.ui.Button
  ):
    await interaction.response.send_modal(ResetUserQuotaModal())

  @discord.ui.button(
      label="💥 รีเซ็ตโควตาทั้งหมด",
      style=discord.ButtonStyle.secondary,
      custom_id="reset_all_quota",
  )
  async def reset_all_quota_btn(
      self, interaction: discord.Interaction, button: discord.ui.Button
  ):
    if not is_admin_or_has_role(interaction.user):
      await interaction.response.send_message(
          "❌ เฉพาะแอดมินเท่านั้น", ephemeral=True
      )
      return
    user_reset_tracker.clear()
    await interaction.response.send_message(
        "✅ **ล้างและรีเซ็ตโควตาสมาชิกทั้งหมดเรียบร้อยแล้ว!**", ephemeral=True
    )
    send_log(
        f"👑 **[Admin Log]** แอดมิน `{interaction.user.name}`"
        " ได้ทำการล้างโควตารีเซ็ต HWID ทั้งหมดในระบบ"
    )


class ControlRoomResetKeyModal(discord.ui.Modal):

  def __init__(self):
    super().__init__(title="🔄 รีเซ็ต HWID คีย์ (Control Room)")

  key_input = discord.ui.TextInput(
      label="พิมพ์ License Key ที่ต้องการรีเซ็ต",
      placeholder="XXXX-XXXX-XXXX-XXXX",
      required=True,
  )

  async def on_submit(self, interaction: discord.Interaction):
    if not is_admin_or_has_role(interaction.user):
      await interaction.response.send_message(
          "❌ เฉพาะแอดมินเท่านั้น", ephemeral=True
      )
      return
    await interaction.response.defer(ephemeral=True)
    clean_key = self.key_input.value.strip()
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT key, status, hwid FROM licenses WHERE key = ?", (clean_key,)
    )
    row = cursor.fetchone()

    if not row:
      conn.close()
      await interaction.followup.send(
          "❌ **ไม่พบคีย์นี้ในระบบ!**", ephemeral=True
      )
      return

    db_key, status, current_hwid = row
    if not current_hwid:
      conn.close()
      await interaction.followup.send(
          "⚠️ **คีย์นี้ยังไม่เคยถูกใช้งานบนเครื่องใดเลย**", ephemeral=True
      )
      return

    cursor.execute(
        "UPDATE licenses SET hwid = NULL, status = 'Unused', expiry_date = NULL,"
        " paused_days = 0 WHERE key = ?",
        (clean_key,),
    )
    conn.commit()
    conn.close()

    await interaction.followup.send(
        f"✅ **รีเซ็ต HWID สำเร็จ!**\n🔑 คีย์: `{clean_key}`", ephemeral=True
    )
    send_log(
        f"🔄 **[Control Room] แอดมิน `{interaction.user.name}` รีเซ็ตคีย์:**"
        f" `{clean_key}`"
    )
    await update_dashboards()


class CustomGenModal(discord.ui.Modal):

  def __init__(self):
    super().__init__(title="🛠️ สร้าง License Key แบบกำหนดเอง")

  days_input = discord.ui.TextInput(
      label="ระบุจำนวนวัน (ตัวเลข หรือ perm ถาวร)",
      placeholder="เช่น 5, 15, 60 หรือ perm",
      required=True,
  )

  async def on_submit(self, interaction: discord.Interaction):
    if not is_admin_or_has_role(interaction.user):
      await interaction.response.send_message(
          "❌ เฉพาะแอดมินเท่านั้น", ephemeral=True
      )
      return
    await interaction.response.defer(ephemeral=True)
    days_str = self.days_input.value.strip()
    try:
      d_days = 0 if days_str.lower() == "perm" else int(days_str)
    except ValueError:
      await interaction.followup.send(
          "❌ กรุณากรอกตัวเลขจำนวนวันให้ถูกต้อง หรือพิมพ์ว่า perm เท่านั้น",
          ephemeral=True,
      )
      return

    key = "".join(random.choices(string.ascii_uppercase + string.digits, k=16))
    key_formatted = f"{key[0:4]}-{key[4:8]}-{key[8:12]}-{key[12:16]}"

    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO licenses (key, duration_days, expiry_date, hwid, status,"
        " paused_days) VALUES (?, ?, ?, ?, ?, ?)",
        (key_formatted, d_days, None, None, "Unused", 0),
    )
    conn.commit()
    conn.close()

    await interaction.followup.send(
        f"✅ สร้างคีย์สำเร็จ: `{key_formatted}` ({days_str} วัน)", ephemeral=True
    )
    send_log(
        f"🎛️ แอดมิน `{interaction.user.name}` สร้างคีย์: `{key_formatted}`"
        f" ({days_str})"
    )
    await update_dashboards()


class GenSelectDropdown(discord.ui.Select):

  def __init__(self):
    options = [
        discord.SelectOption(
            label="📅 1 วัน",
            description="สร้างคีย์ใช้งานระยะเวลา 1 วัน",
            value="1",
        ),
        discord.SelectOption(
            label="📅 3 วัน",
            description="สร้างคีย์ใช้งานระยะเวลา 3 วัน",
            value="3",
        ),
        discord.SelectOption(
            label="📅 7 วัน",
            description="สร้างคีย์ใช้งานระยะเวลา 7 วัน",
            value="7",
        ),
        discord.SelectOption(
            label="📅 30 วัน",
            description="สร้างคีย์ใช้งานระยะเวลา 30 วัน",
            value="30",
        ),
        discord.SelectOption(
            label="♾️ ถาวร (Permanent)",
            description="สร้างคีย์ใช้งานแบบถาวรไม่มีวันหมดอายุ",
            value="perm",
        ),
        discord.SelectOption(
            label="⌨️ [พิมพ์ระบุจำนวนวันเอง]",
            description="คลิกเพื่อกรอกตัวเลขวันตามต้องการ",
            value="CUSTOM_INPUT",
        ),
    ]
    super().__init__(
        placeholder="👉 เลือกจำนวนวันที่ต้องการสร้างคีย์...",
        min_values=1,
        max_values=1,
        options=options,
    )

  async def callback(self, interaction: discord.Interaction):
    if not is_admin_or_has_role(interaction.user):
      await interaction.response.send_message(
          "❌ เฉพาะแอดมินเท่านั้น", ephemeral=True
      )
      return
    val = self.values[0]
    if val == "CUSTOM_INPUT":
      await interaction.response.send_modal(CustomGenModal())
      return

    await interaction.response.defer(ephemeral=True)
    d_days = 0 if val == "perm" else int(val)
    key = "".join(random.choices(string.ascii_uppercase + string.digits, k=16))
    key_formatted = f"{key[0:4]}-{key[4:8]}-{key[8:12]}-{key[12:16]}"

    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO licenses (key, duration_days, expiry_date, hwid, status,"
        " paused_days) VALUES (?, ?, ?, ?, ?, ?)",
        (key_formatted, d_days, None, None, "Unused", 0),
    )
    conn.commit()
    conn.close()

    label_text = "ถาวร" if val == "perm" else f"{val} วัน"
    await interaction.followup.send(
        f"✅ สร้างคีย์สำเร็จ: `{key_formatted}` ({label_text})", ephemeral=True
    )
    send_log(
        f"🎛️ แอดมิน `{interaction.user.name}` สร้างคีย์: `{key_formatted}`"
        f" ({label_text})"
    )
    await update_dashboards()


class GenSelectView(discord.ui.View):

  def __init__(self):
    super().__init__(timeout=60)
    self.add_item(GenSelectDropdown())


class CheckKeyModal(discord.ui.Modal):

  def __init__(self):
    super().__init__(title="🔍 เช็คข้อมูลคีย์รายตัว")

  key_input = discord.ui.TextInput(
      label="พิมพ์ License Key ที่ต้องการตรวจสอบ",
      placeholder="เช่น XXXX-XXXX-XXXX-XXXX",
      required=True,
  )

  async def on_submit(self, interaction: discord.Interaction):
    if not is_admin_or_has_role(interaction.user):
      await interaction.response.send_message(
          "❌ เฉพาะแอดมินเท่านั้น", ephemeral=True
      )
      return
    await interaction.response.defer(ephemeral=True)
    target = self.key_input.value.strip()
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT key, duration_days, expiry_date, hwid, status, paused_days FROM"
        " licenses WHERE key = ?",
        (target,),
    )
    row = cursor.fetchone()
    conn.close()

    if not row:
      await interaction.followup.send(
          f"❌ ไม่พบคีย์ `{target}` ในระบบ", ephemeral=True
      )
      return

    k, days, exp, hwid, status, paused = row
    text = (
        f"🔑 **รายละเอียดคีย์:** `{k}`\n• สถานะ: `{status}`\n• ระยะเวลา: `{days}`"
        f" วัน\n• วันหมดอายุ: `{exp or 'ยังไม่เปิดใช้งาน'}`\n• HWID ผูกเครื่อง:"
        f" `{hwid or 'ยังไม่ผูก'}`"
    )
    await interaction.followup.send(text, ephemeral=True)


class CheckHWIDModal(discord.ui.Modal):

  def __init__(self):
    super().__init__(title="💻 เช็คข้อมูล HWID")

  hwid_input = discord.ui.TextInput(
      label="พิมพ์ HWID ที่ต้องการตรวจสอบ",
      placeholder="เช่น DESKTOP-XXXXXX",
      required=True,
  )

  async def on_submit(self, interaction: discord.Interaction):
    if not is_admin_or_has_role(interaction.user):
      await interaction.response.send_message(
          "❌ เฉพาะแอดมินเท่านั้น", ephemeral=True
      )
      return
    await interaction.response.defer(ephemeral=True)
    target = self.hwid_input.value.strip()
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT key, status, expiry_date FROM licenses WHERE hwid = ?",
        (target,),
    )
    rows = cursor.fetchall()
    conn.close()

    if not rows:
      await interaction.followup.send(
          f"❌ ไม่พบข้อมูลที่ผูกกับ HWID: `{target}`", ephemeral=True
      )
      return

    msg = f"💻 **HWID:** `{target}`\nผูกอยู่กับคีย์:\n"
    for r in rows:
      msg += f"• คีย์: `{r[0]}` (สถานะ: `{r[1]}`)\n"
    await interaction.followup.send(msg, ephemeral=True)


class SearchInputModal(discord.ui.Modal):

  def __init__(self, action_type: str):
    self.action_type = action_type
    super().__init__(title="🔍 ค้นหาคีย์ด้วยชื่อหรือตัวอักษร")
    self.search_text = discord.ui.TextInput(
        label="พิมพ์คำที่ต้องการค้นหา",
        placeholder="เช่น LUCA หรือเว้นว่างเพื่อดูทั้งหมด",
        required=False,
    )
    self.add_item(self.search_text)

  async def on_submit(self, interaction: discord.Interaction):
    if not is_admin_or_has_role(interaction.user):
      await interaction.response.send_message(
          "❌ เฉพาะแอดมินเท่านั้น", ephemeral=True
      )
      return
    keyword = self.search_text.value.strip()
    view = SelectActionView(self.action_type, search_keyword=keyword)
    await interaction.response.send_message(
        "🔽 ผลการค้นหา เลือกรายการด้านล่าง:", view=view, ephemeral=True
    )


class KeyPickerModal(discord.ui.Modal):

  def __init__(self, action_type: str):
    self.action_type = action_type
    super().__init__(title="🎯 เลือกคีย์รายตัว")
    self.key_text = discord.ui.TextInput(
        label="พิมพ์ชื่อคีย์ที่ต้องการจัดการ",
        placeholder="เช่น LUCA-XXXX-XXXX-XXXX",
        required=True,
    )
    self.add_item(self.key_text)

  async def on_submit(self, interaction: discord.Interaction):
    if not is_admin_or_has_role(interaction.user):
      await interaction.response.send_message(
          "❌ เฉพาะแอดมินเท่านั้น", ephemeral=True
      )
      return
    await interaction.response.defer(ephemeral=True)
    target_key = self.key_text.value.strip()
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute("SELECT key FROM licenses WHERE key = ?", (target_key,))
    row = cursor.fetchone()

    if not row:
      conn.close()
      await interaction.followup.send(
          f"❌ ไม่พบคีย์ `{target_key}` ในระบบ", ephemeral=True
      )
      return
    conn.close()

    if self.action_type in ["add", "sub"]:
      await interaction.followup.send(
          "🔽 กรุณาใช้คำสั่งผ่านเมนูปุ่มกดปกติสำหรับเพิ่ม/ลดวัน", ephemeral=True
      )
      return

    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    cursor = conn.cursor()
    if self.action_type == "reset":
      cursor.execute(
          "UPDATE licenses SET hwid = NULL, status = 'Unused', expiry_date ="
          " NULL, paused_days = 0 WHERE key = ?",
          (target_key,),
      )
      msg = f"🔄 รีเซ็ตคีย์ `{target_key}` สำเร็จ!"
    elif self.action_type == "delete":
      cursor.execute("DELETE FROM licenses WHERE key = ?", (target_key,))
      msg = f"🗑️ ลบคีย์ `{target_key}` สำเร็จ!"
    elif self.action_type == "pause":
      cursor.execute(
          "SELECT expiry_date, status FROM licenses WHERE key = ?",
          (target_key,),
      )
      r = cursor.fetchone()
      if r and r[1] == "Active" and r[0]:
        rem_days = (
            datetime.strptime(r[0], "%Y-%m-%d %H:%M:%S") - datetime.now()
        ).total_seconds() / 86400
        cursor.execute(
            "UPDATE licenses SET status = 'Paused', paused_days = ? WHERE key ="
            " ?",
            (rem_days, target_key),
        )
        msg = f"⏸️ หยุดเวลาคีย์ `{target_key}` สำเร็จ!"
      else:
        msg = "❌ คีย์ไม่ได้ใช้งานอยู่"
    elif self.action_type == "resume":
      cursor.execute(
          "SELECT paused_days, status FROM licenses WHERE key = ?", (target_key,)
      )
      r = cursor.fetchone()
      if r and r[1] == "Paused":
        new_exp = datetime.now() + timedelta(days=r[0])
        cursor.execute(
            "UPDATE licenses SET status = 'Active', expiry_date = ?, paused_days"
            " = 0 WHERE key = ?",
            (new_exp.strftime("%Y-%m-%d %H:%M:%S"), target_key),
        )
        msg = f"▶️ เดินเวลาคีย์ `{target_key}` สำเร็จ!"
      else:
        msg = "❌ คีย์ไม่ได้ถูกหยุดเวลาไว้"
    elif self.action_type == "remote_kill":
      cursor.execute("SELECT hwid FROM licenses WHERE key = ?", (target_key,))
      r = cursor.fetchone()
      if r and r[0]:
        pending_commands[r[0]] = "kill_program"
        msg = f"⚡ ส่งคำสั่งปิดโปรแกรมไปยังคีย์ `{target_key}` เรียบร้อย!"
      else:
        msg = "❌ ไม่พบ HWID ผูกกับคีย์นี้"

    conn.commit()
    conn.close()
    await interaction.followup.send(msg, ephemeral=True)
    send_log(
        f"🎛️ แอดมิน `{interaction.user.name}` จัดการ `{self.action_type}`"
        f" เป้าหมาย: `{target_key}`"
    )
    await update_dashboards()


class KeySelectDropdown(discord.ui.Select):

  def __init__(self, action_type: str, search_keyword: str = ""):
    self.action_type = action_type
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    cursor = conn.cursor()

    if action_type == "remote_kill":
      cursor.execute("SELECT key, hwid FROM licenses WHERE hwid IS NOT NULL")
    else:
      cursor.execute("SELECT key, status FROM licenses")
    rows = cursor.fetchall()
    conn.close()

    if search_keyword:
      rows = [
          r
          for r in rows
          if search_keyword.lower() in r[0].lower()
          or (len(r) > 1 and r[1] and search_keyword.lower() in str(r[1]).lower())
      ]

    options = [
        discord.SelectOption(
            label="🔍 [พิมพ์ค้นหาชื่อหรือคีย์...]",
            description="คลิกเพื่อพิมพ์กรองข้อมูล",
            value="TRIGGER_SEARCH",
        ),
        discord.SelectOption(
            label="🎯 [เลือกคีย์รายตัว]",
            description="คลิกเพื่อพิมพ์ระบุคีย์ที่ต้องการเลือก",
            value="TRIGGER_PICK_KEY",
        ),
    ]

    if rows:
      for r in rows:
        k = r[0]
        extra = (
            f" (HWID: {r[1][:10]}...)"
            if action_type == "remote_kill" and r[1]
            else f" [{r[1]}]"
        )
        options.append(
            discord.SelectOption(
                label=f"{k}"[:100],
                description=f"สถานะ: {extra}"[:100],
                value=k,
            )
        )
        if len(options) >= 23:
          break

    options.append(
        discord.SelectOption(
            label="⚡ [ALL - เลือกทั้งหมดทุกคีย์]",
            description="จัดการทุกรายการในระบบพร้อมกัน",
            value="ALL_ITEMS",
        )
    )
    super().__init__(
        placeholder="👉 คลิกเลือกรายการ หรือค้นหา...",
        min_values=1,
        max_values=1,
        options=options,
    )

  async def callback(self, interaction: discord.Interaction):
    if not is_admin_or_has_role(interaction.user):
      await interaction.response.send_message(
          "❌ เฉพาะแอดมินเท่านั้น", ephemeral=True
      )
      return
    selected_val = self.values[0]
    if selected_val == "TRIGGER_SEARCH":
      await interaction.response.send_modal(SearchInputModal(self.action_type))
      return
    if selected_val == "TRIGGER_PICK_KEY":
      await interaction.response.send_modal(KeyPickerModal(self.action_type))
      return

    await interaction.response.defer(ephemeral=True)
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    cursor = conn.cursor()

    if selected_val == "ALL_ITEMS":
      if self.action_type == "delete":
        cursor.execute("DELETE FROM licenses")
        msg = "🗑️ ลบข้อมูลคีย์ทั้งหมดในระบบเรียบร้อยแล้ว!"
      elif self.action_type == "reset":
        cursor.execute(
            "UPDATE licenses SET hwid = NULL, status = 'Unused', expiry_date ="
            " NULL, paused_days = 0"
        )
        msg = "🔄 รีเซ็ต HWID และสถานะคีย์ทั้งหมดเรียบร้อยแล้ว!"
      elif self.action_type == "pause":
        cursor.execute(
            "UPDATE licenses SET status = 'Paused' WHERE status = 'Active'"
        )
        msg = "⏸️ หยุดเวลาคีย์ทั้งหมดเรียบร้อยแล้ว!"
      elif self.action_type == "resume":
        cursor.execute(
            "UPDATE licenses SET status = 'Active' WHERE status = 'Paused'"
        )
        msg = "▶️ เดินเวลาคีย์ทั้งหมดเรียบร้อยแล้ว!"
      elif self.action_type == "remote_kill":
        cursor.execute("SELECT hwid FROM licenses WHERE hwid IS NOT NULL")
        for r in cursor.fetchall():
          if r[0]:
            pending_commands[r[0]] = "kill_program"
        msg = "⚡ ส่งคำสั่งปิดโปรแกรมไปยังทุกเครื่องเรียบร้อย!"
      else:
        msg = "⚠️ คำสั่งนี้ไม่รองรับการใช้งานแบบ ALL"

      conn.commit()
      conn.close()
      await interaction.followup.send(msg, ephemeral=True)
      send_log(
          f"🎛️ แอดมิน `{interaction.user.name}` สั่งจัดการทั้งหมด"
          f" (`{self.action_type} - ALL`)"
      )
      await update_dashboards()
      return

    if self.action_type in ["add", "sub"]:
      conn.close()
      await interaction.followup.send(
          "🔽 กรุณาใช้ปุ่มเมนูจัดการรายตัวผ่านหน้าแดชบอร์ดหลัก", ephemeral=True
      )
      return

    if self.action_type == "reset":
      cursor.execute(
          "UPDATE licenses SET hwid = NULL, status = 'Unused', expiry_date ="
          " NULL, paused_days = 0 WHERE key = ?",
          (selected_val,),
      )
      msg = f"🔄 รีเซ็ตคีย์ `{selected_val}` สำเร็จ!"
    elif self.action_type == "delete":
      cursor.execute("DELETE FROM licenses WHERE key = ?", (selected_val,))
      msg = f"🗑️ ลบคีย์ `{selected_val}` สำเร็จ!"
    elif self.action_type == "pause":
      cursor.execute(
          "SELECT expiry_date, status FROM licenses WHERE key = ?",
          (selected_val,),
      )
      row = cursor.fetchone()
      if row and row[1] == "Active" and row[0]:
        rem_days = (
            datetime.strptime(row[0], "%Y-%m-%d %H:%M:%S") - datetime.now()
        ).total_seconds() / 86400
        cursor.execute(
            "UPDATE licenses SET status = 'Paused', paused_days = ? WHERE key ="
            " ?",
            (rem_days, selected_val),
        )
        msg = f"⏸️ หยุดเวลาคีย์ `{selected_val}` สำเร็จ!"
      else:
        msg = "❌ คีย์ไม่ได้ใช้งานอยู่"
    elif self.action_type == "resume":
      cursor.execute(
          "SELECT paused_days, status FROM licenses WHERE key = ?",
          (selected_val,),
      )
      row = cursor.fetchone()
      if row and row[1] == "Paused":
        new_exp = datetime.now() + timedelta(days=row[0])
        cursor.execute(
            "UPDATE licenses SET status = 'Active', expiry_date = ?, paused_days"
            " = 0 WHERE key = ?",
            (new_exp.strftime("%Y-%m-%d %H:%M:%S"), selected_val),
        )
        msg = f"▶️ เดินเวลาคีย์ `{selected_val}` สำเร็จ!"
      else:
        msg = "❌ คีย์ไม่ได้ถูกหยุดเวลาไว้"
    elif self.action_type == "remote_kill":
      cursor.execute("SELECT hwid FROM licenses WHERE key = ?", (selected_val,))
      r = cursor.fetchone()
      if r and r[0]:
        pending_commands[r[0]] = "kill_program"
        msg = f"⚡ ส่งคำสั่งปิดโปรแกรมไปยังคีย์ `{selected_val}` เรียบร้อย!"
      else:
        msg = "❌ ไม่พบ HWID ผูกกับคีย์นี้"

    conn.commit()
    conn.close()
    await interaction.followup.send(msg, ephemeral=True)
    send_log(
        f"🎛️ แอดมิน `{interaction.user.name}` จัดการ `{self.action_type}`"
        f" เป้าหมาย: `{selected_val}`"
    )
    await update_dashboards()


class SelectActionView(discord.ui.View):

  def __init__(self, action_type: str, search_keyword: str = ""):
    super().__init__(timeout=60)
    self.add_item(KeySelectDropdown(action_type, search_keyword))


class ControlPanelView(discord.ui.View):

  def __init__(self):
    super().__init__(timeout=None)

  @discord.ui.button(
      label="🔄 รีเฟรช",
      style=discord.ButtonStyle.blurple,
      custom_id="ctrl_refresh",
      row=0,
  )
  async def refresh_btn(
      self, interaction: discord.Interaction, button: discord.ui.Button
  ):
    if not is_admin_or_has_role(interaction.user):
      await interaction.response.send_message(
          "❌ เฉพาะแอดมินเท่านั้น", ephemeral=True
      )
      return
    await interaction.response.defer(ephemeral=True)
    await update_dashboards()
    await interaction.followup.send("✅ รีเฟรชข้อมูลสำเร็จ!", ephemeral=True)

  @discord.ui.button(
      label="➕ สร้างคีย์",
      style=discord.ButtonStyle.green,
      custom_id="ctrl_gen",
      row=0,
  )
  async def gen_btn(
      self, interaction: discord.Interaction, button: discord.ui.Button
  ):
    if not is_admin_or_has_role(interaction.user):
      await interaction.response.send_message(
          "❌ เฉพาะแอดมินเท่านั้น", ephemeral=True
      )
      return
    await interaction.response.send_message(
        "🔽 เลือกจำนวนวันหรือระบุเองด้านล่าง:",
        view=GenSelectView(),
        ephemeral=True,
    )

  @discord.ui.button(
      label="🔍 เช็คคีย์",
      style=discord.ButtonStyle.primary,
      custom_id="ctrl_check_key",
      row=0,
  )
  async def check_key_btn(
      self, interaction: discord.Interaction, button: discord.ui.Button
  ):
    if not is_admin_or_has_role(interaction.user):
      await interaction.response.send_message(
          "❌ เฉพาะแอดมินเท่านั้น", ephemeral=True
      )
      return
    await interaction.response.send_modal(CheckKeyModal())

  @discord.ui.button(
      label="💻 เช็ค HWID",
      style=discord.ButtonStyle.primary,
      custom_id="ctrl_check_hwid",
      row=0,
  )
  async def check_hwid_btn(
      self, interaction: discord.Interaction, button: discord.ui.Button
  ):
    if not is_admin_or_has_role(interaction.user):
      await interaction.response.send_message(
          "❌ เฉพาะแอดมินเท่านั้น", ephemeral=True
      )
      return
    await interaction.response.send_modal(CheckHWIDModal())

  @discord.ui.button(
      label="📋 คีย์ทั้งหมด",
      style=discord.ButtonStyle.secondary,
      custom_id="ctrl_check_all_key",
      row=1,
  )
  async def check_all_key_btn(
      self, interaction: discord.Interaction, button: discord.ui.Button
  ):
    if not is_admin_or_has_role(interaction.user):
      await interaction.response.send_message(
          "❌ เฉพาะแอดมินเท่านั้น", ephemeral=True
      )
      return
    await interaction.response.defer(ephemeral=True)
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute("SELECT key, status FROM licenses")
    rows = cursor.fetchall()
    conn.close()
    text = "📋 **รายชื่อคีย์ทั้งหมดในระบบ:**\n"
    for r in rows[:30]:
      text += f"• `{r[0]}` [{r[1]}]\n"
    if len(rows) > 30:
      text += f"...และอีก {len(rows)-30} รายการ"
    await interaction.followup.send(text, ephemeral=True)

  @discord.ui.button(
      label="🖥️ HWID ทั้งหมด",
      style=discord.ButtonStyle.secondary,
      custom_id="ctrl_check_all_hwid",
      row=1,
  )
  async def check_all_hwid_btn(
      self, interaction: discord.Interaction, button: discord.ui.Button
  ):
    if not is_admin_or_has_role(interaction.user):
      await interaction.response.send_message(
          "❌ เฉพาะแอดมินเท่านั้น", ephemeral=True
      )
      return
    await interaction.response.defer(ephemeral=True)
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute("SELECT key, hwid FROM licenses WHERE hwid IS NOT NULL")
    rows = cursor.fetchall()
    conn.close()
    text = "🖥️ **HWID ที่เชื่อมต่ออยู่ทั้งหมด:**\n"
    for r in rows[:30]:
      text += f"• คีย์ `{r[0]}` ➔ `{r[1]}`\n"
    if not rows:
      text += "📭 ยังไม่มี HWID เชื่อมต่อ"
    await interaction.followup.send(text, ephemeral=True)

  @discord.ui.button(
      label="📜 เช็ค Log สำคัญ",
      style=discord.ButtonStyle.danger,
      custom_id="ctrl_check_log",
      row=1,
  )
  async def check_log_btn(
      self, interaction: discord.Interaction, button: discord.ui.Button
  ):
    if not is_admin_or_has_role(interaction.user):
      await interaction.response.send_message(
          "❌ เฉพาะแอดมินเท่านั้น", ephemeral=True
      )
      return
    log_text = "📜 **Log สำคัญล่าสุด (20 รายการ):**\n"
    if recent_logs:
      log_text += "\n".join(recent_logs[:15])
    else:
      log_text += "📭 ยังไม่มีบันทึก Log ในหน่วยความจำ"
    await interaction.response.send_message(log_text, ephemeral=True)

  @discord.ui.button(
      label="📊 โควตา HWID",
      style=discord.ButtonStyle.blurple,
      custom_id="ctrl_quota_status",
      row=2,
  )
  async def quota_status_btn(
      self, interaction: discord.Interaction, button: discord.ui.Button
  ):
    if not is_admin_or_has_role(interaction.user):
      await interaction.response.send_message(
          "❌ เฉพาะแอดมินเท่านั้น", ephemeral=True
      )
      return
    now = datetime.now()
    embed = discord.Embed(
        title="📊 **รายงานการใช้โควตารีเซ็ต HWID ประจำวัน**",
        color=discord.Color.blue(),
    )
    if not user_reset_tracker:
      embed.description = "📭 **ยังไม่มีผู้ใช้วันนี้ที่มีการใช้โควตา**"
    else:
      desc = ""
      for uid, data in user_reset_tracker.items():
        if now - data["reset_time"] >= timedelta(days=1):
          cnt = 0
        else:
          cnt = data["count"]
        left = max(0, 2 - cnt)
        desc += (
            f"• <@{uid}> (`{uid}`)\n  └ 🔄 ใช้ไปแล้ว: `{cnt}/2` รอบ | ⏳"
            f" เหลือ: `{left}` รอบ\n"
        )
      embed.description = desc
    await interaction.response.send_message(
        embed=embed, view=QuotaManageView(), ephemeral=True
    )

  @discord.ui.button(
      label="🔄 รีเซ็ต HWID",
      style=discord.ButtonStyle.danger,
      custom_id="ctrl_reset",
      row=2,
  )
  async def reset_btn(
      self, interaction: discord.Interaction, button: discord.ui.Button
  ):
    if not is_admin_or_has_role(interaction.user):
      await interaction.response.send_message(
          "❌ เฉพาะแอดมินเท่านั้น", ephemeral=True
      )
      return
    await interaction.response.send_message(
        "🔽 เลือกเมนูด้านล่าง (Search / เลือกคีย์ / All):",
        view=SelectActionView("reset"),
        ephemeral=True,
    )

  @discord.ui.button(
      label="🔄 รีเซ็ตคีย์ (Control Room)",
      style=discord.ButtonStyle.danger,
      custom_id="ctrl_resetkey_btn",
      row=2,
  )
  async def ctrl_resetkey_btn(
      self, interaction: discord.Interaction, button: discord.ui.Button
  ):
    if not is_admin_or_has_role(interaction.user):
      await interaction.response.send_message(
          "❌ เฉพาะแอดมินเท่านั้น", ephemeral=True
      )
      return
    await interaction.response.send_modal(ControlRoomResetKeyModal())

  @discord.ui.button(
      label="⏸️ หยุดเวลา",
      style=discord.ButtonStyle.secondary,
      custom_id="ctrl_pause",
      row=3,
  )
  async def pause_btn(
      self, interaction: discord.Interaction, button: discord.ui.Button
  ):
    if not is_admin_or_has_role(interaction.user):
      await interaction.response.send_message(
          "❌ เฉพาะแอดมินเท่านั้น", ephemeral=True
      )
      return
    await interaction.response.send_message(
        "🔽 เลือกเมนูด้านล่าง (Search / เลือกคีย์ / All):",
        view=SelectActionView("pause"),
        ephemeral=True,
    )

  @discord.ui.button(
      label="▶️ เดินต่อ",
      style=discord.ButtonStyle.success,
      custom_id="ctrl_resume",
      row=3,
  )
  async def resume_btn(
      self, interaction: discord.Interaction, button: discord.ui.Button
  ):
    if not is_admin_or_has_role(interaction.user):
      await interaction.response.send_message(
          "❌ เฉพาะแอดมินเท่านั้น", ephemeral=True
      )
      return
    await interaction.response.send_message(
        "🔽 เลือกเมนูด้านล่าง (Search / เลือกคีย์ / All):",
        view=SelectActionView("resume"),
        ephemeral=True,
    )

  @discord.ui.button(
      label="⚡ ปิดโปรแกรม",
      style=discord.ButtonStyle.danger,
      custom_id="ctrl_kill",
      row=3,
  )
  async def kill_btn(
      self, interaction: discord.Interaction, button: discord.ui.Button
  ):
    if not is_admin_or_has_role(interaction.user):
      await interaction.response.send_message(
          "❌ เฉพาะแอดมินเท่านั้น", ephemeral=True
      )
      return
    await interaction.response.send_message(
        "🔽 เลือกเมนูด้านล่าง (Search / เลือกคีย์ / All):",
        view=SelectActionView("remote_kill"),
        ephemeral=True,
    )

  @discord.ui.button(
      label="🗑️ ลบคีย์",
      style=discord.ButtonStyle.danger,
      custom_id="ctrl_delete",
      row=4,
  )
  async def delete_btn(
      self, interaction: discord.Interaction, button: discord.ui.Button
  ):
    if not is_admin_or_has_role(interaction.user):
      await interaction.response.send_message(
          "❌ เฉพาะแอดมินเท่านั้น", ephemeral=True
      )
      return
    await interaction.response.send_message(
        "🔽 เลือกเมนูด้านล่าง (Search / เลือกคีย์ / All):",
        view=SelectActionView("delete"),
        ephemeral=True,
    )


# ==========================================
# DISCORD SLASH COMMANDS & EVENTS
# ==========================================
@bot.tree.command(name="gen", description="🛠️ สร้าง License Key ใหม่")
@app_commands.describe(days="ระยะเวลา (เช่น 1, 3, 7, 30 หรือ perm)")
@app_commands.default_permissions(administrator=True)
async def slash_gen(interaction: discord.Interaction, days: str):
  if not is_admin_or_has_role(interaction.user):
    await interaction.response.send_message(
        "❌ คุณไม่มีสิทธิ์ใช้งาน", ephemeral=True
    )
    return

  await interaction.response.defer(ephemeral=True)
  key = "".join(random.choices(string.ascii_uppercase + string.digits, k=16))
  key_formatted = f"{key[0:4]}-{key[4:8]}-{key[8:12]}-{key[12:16]}"
  d_days = 0 if days.lower() == "perm" else int(days)

  conn = sqlite3.connect(DB_PATH, check_same_thread=False)
  cursor = conn.cursor()
  cursor.execute(
      "INSERT INTO licenses (key, duration_days, expiry_date, hwid, status,"
      " paused_days) VALUES (?, ?, ?, ?, ?, ?)",
      (key_formatted, d_days, None, None, "Unused", 0),
  )
  conn.commit()
  conn.close()

  await interaction.followup.send(
      f"✅ สร้างคีย์สำเร็จ: `{key_formatted}` ({days})", ephemeral=True
  )
  send_log(
      f"⌨️ แอดมิน `{interaction.user.name}` ใช้คำสั่ง `/gen` สร้างคีย์:"
      f" `{key_formatted}`"
  )
  await update_dashboards()


@bot.tree.command(name="reset", description="🔄 รีเซ็ต HWID คีย์ (เลือกจากเมนู)")
@app_commands.default_permissions(administrator=True)
async def slash_reset(interaction: discord.Interaction):
  if not is_admin_or_has_role(interaction.user):
    await interaction.response.send_message(
        "❌ คุณไม่มีสิทธิ์ใช้งาน", ephemeral=True
    )
    return
  await interaction.response.send_message(
      "🔽 เลือกเมนูด้านล่าง:", view=SelectActionView("reset"), ephemeral=True
  )


@bot.tree.command(
    name="add", description="⏰ เพิ่มวันใช้งานให้ License Key (เลือกจากเมนู)"
)
@app_commands.default_permissions(administrator=True)
async def slash_add(interaction: discord.Interaction):
  if not is_admin_or_has_role(interaction.user):
    await interaction.response.send_message(
        "❌ คุณไม่มีสิทธิ์ใช้งาน", ephemeral=True
    )
    return
  await interaction.response.send_message(
      "🔽 เลือกเมนูด้านล่าง:", view=SelectActionView("add"), ephemeral=True
  )


@bot.tree.command(
    name="sub", description="⏳ ลดวันใช้งาน License Key (เลือกจากเมนู)"
)
@app_commands.default_permissions(administrator=True)
async def slash_sub(interaction: discord.Interaction):
  if not is_admin_or_has_role(interaction.user):
    await interaction.response.send_message(
        "❌ คุณไม่มีสิทธิ์ใช้งาน", ephemeral=True
    )
    return
  await interaction.response.send_message(
      "🔽 เลือกเมนูด้านล่าง:", view=SelectActionView("sub"), ephemeral=True
  )


@bot.tree.command(name="pause", description="⏸️ หยุดเวลาคีย์ (เลือกจากเมนู)")
@app_commands.default_permissions(administrator=True)
async def slash_pause(interaction: discord.Interaction):
  if not is_admin_or_has_role(interaction.user):
    await interaction.response.send_message(
        "❌ คุณไม่มีสิทธิ์ใช้งาน", ephemeral=True
    )
    return
  await interaction.response.send_message(
      "🔽 เลือกเมนูด้านล่าง:", view=SelectActionView("pause"), ephemeral=True
  )


@bot.tree.command(
    name="resume", description="▶️ เดินเวลาคีย์ต่อ (เลือกจากเมนู)"
)
@app_commands.default_permissions(administrator=True)
async def slash_resume(interaction: discord.Interaction):
  if not is_admin_or_has_role(interaction.user):
    await interaction.response.send_message(
        "❌ คุณไม่มีสิทธิ์ใช้งาน", ephemeral=True
    )
    return
  await interaction.response.send_message(
      "🔽 เลือกเมนูด้านล่าง:", view=SelectActionView("resume"), ephemeral=True
  )


@bot.tree.command(
    name="kill", description="⚡ สั่งปิดโปรแกรมลูกค้าทันที (เลือกจากเมนู)"
)
@app_commands.default_permissions(administrator=True)
async def slash_kill(interaction: discord.Interaction):
  if not is_admin_or_has_role(interaction.user):
    await interaction.response.send_message(
        "❌ คุณไม่มีสิทธิ์ใช้งาน", ephemeral=True
    )
    return
  await interaction.response.send_message(
      "🔽 เลือกเมนูด้านล่าง:", view=SelectActionView("remote_kill"), ephemeral=True
  )


@bot.tree.command(name="del", description="🗑️ ลบคีย์ออกจากระบบ (เลือกจากเมนู)")
@app_commands.default_permissions(administrator=True)
async def slash_del(interaction: discord.Interaction):
  if not is_admin_or_has_role(interaction.user):
    await interaction.response.send_message(
        "❌ คุณไม่มีสิทธิ์ใช้งาน", ephemeral=True
    )
    return
  await interaction.response.send_message(
      "🔽 เลือกเมนูด้านล่าง:", view=SelectActionView("delete"), ephemeral=True
  )


@bot.tree.command(
    name="resetkey",
    description="🔄 รีเซ็ต HWID คีย์ (Admin ใช้ได้ทุกห้อง / ลูกค้าใช้ได้เฉพาะห้องที่กำหนด)",
)
@app_commands.describe(key="กรอก License Key ที่ต้องการรีเซ็ต")
async def slash_resetkey(interaction: discord.Interaction, key: str):
  is_admin_user = is_admin_or_has_role(interaction.user)
  has_customer_role = (
      any(role.id == CUSTOMER_ROLE_ID for role in interaction.user.roles)
      if CUSTOMER_ROLE_ID != 0
      else True
  )

  if not is_admin_user:
    if (
        RESET_KEY_CHANNEL_ID != 0
        and interaction.channel_id != RESET_KEY_CHANNEL_ID
    ):
      await interaction.response.send_message(
          f"❌ ลูกค้าสามารถใช้งานคำสั่งนี้ได้เฉพาะในห้อง <#{RESET_KEY_CHANNEL_ID}>"
          " เท่านั้นครับ!",
          ephemeral=True,
      )
      return

    if CUSTOMER_ROLE_ID != 0 and not has_customer_role:
      await interaction.response.send_message(
          "❌ คุณไม่มีสิทธิ์ใช้งานคำสั่งนี้"
          " (สำหรับยศลูกค้าหรือแอดมินเท่านั้น)",
          ephemeral=True,
      )
      return

  await interaction.response.defer(ephemeral=True)
  clean_key = key.replace("\u200b", "").replace("\ufeff", "").strip()

  conn = sqlite3.connect(DB_PATH, check_same_thread=False)
  cursor = conn.cursor()
  cursor.execute(
      "SELECT key, status, hwid FROM licenses WHERE key = ?", (clean_key,)
  )
  row = cursor.fetchone()

  if not row:
    conn.close()
    await interaction.followup.send(
        "❌ **ไม่พบคีย์นี้ในระบบ!** กรุณาตรวจสอบความถูกต้องของ License Key"
        " อีกครั้ง",
        ephemeral=True,
    )
    return

  db_key, status, current_hwid = row

  if not current_hwid:
    conn.close()
    await interaction.followup.send(
        "⚠️ **คีย์นี้ยังไม่เคยถูกใช้งานบนเครื่องใดเลย**", ephemeral=True
    )
    return

  # ระบบจำกัดโควตาสำหรับลูกค้า
  if not is_admin_user:
    user_id = interaction.user.id
    now = datetime.now()
    if user_id not in user_reset_tracker:
      user_reset_tracker[user_id] = {"count": 0, "reset_time": now}

    tracker = user_reset_tracker[user_id]
    if now - tracker["reset_time"] >= timedelta(days=1):
      tracker["count"] = 0
      tracker["reset_time"] = now

    if tracker["count"] >= 2:
      conn.close()
      await interaction.followup.send(
          "❌ **คุณใช้งานโควตารีเซ็ต HWID ครบ 2 ครั้งสำหรับวันนี้แล้ว!**"
          " กรุณาติดต่อแอดมิน",
          ephemeral=True,
      )
      return
    tracker["count"] += 1

  cursor.execute(
      "UPDATE licenses SET hwid = NULL, status = 'Unused', expiry_date = NULL,"
      " paused_days = 0 WHERE key = ?",
      (clean_key,),
  )
  conn.commit()
  conn.close()

  await interaction.followup.send(
      f"✅ **รีเซ็ต HWID สำเร็จ!**\n🔑 คีย์: `{clean_key}`\n💻"
      " ปลดล็อกฮาร์ดแวร์เรียบร้อยแล้ว"
      " คุณสามารถนำคีย์นี้ไปใช้งานบนเครื่องใหม่ได้เลยครับ",
      ephemeral=True,
  )

  send_log(
      f"🔄 **[Reset Key] {'แอดมิน' if is_admin_user else 'ลูกค้า'}ทำการรีเซ็ตคีย์**\n👤"
      f" ผู้ใช้งาน: `{interaction.user.name}`\n🔑 คีย์: `{clean_key}`"
  )
  await update_dashboards()


# ==========================================
# DISCORD BOT EVENTS & DASHBOARDS
# ==========================================
@bot.event
async def on_ready():
  print(f"Logged in as {bot.user.name}!")
  bot.add_view(ControlPanelView())
  bot.add_view(TopupView(bot))
  bot.add_view(GameControlView())

  await setup_control_panel()
  await setup_admin_panel()
  await setup_topup_dashboard_panel()
  await setup_game_panel()
  await update_dashboards()


async def setup_control_panel():
  if CONTROL_ROOM_CHANNEL_ID == 0:
    return
  channel = bot.get_channel(CONTROL_ROOM_CHANNEL_ID)
  if not channel:
    return

  embed = discord.Embed(
      title="🎛️ CONTROL ROOM (แผงควบคุมระบบคีย์)",
      description=(
          "ห้องสำหรับกดปุ่มควบคุมระบบต่างๆ\n• ตรวจสอบข้อมูลคีย์, เช็ค HWID, ดู Log"
          " และจัดการสถานะคีย์แบบจัดเต็มสำหรับ Admin"
      ),
      color=discord.Color.from_rgb(138, 43, 226),
  )
  embed.set_image(url=GIF_BANNER_URL)

  try:
    async for m in channel.history(limit=5):
      if m.author == bot.user:
        await m.edit(embed=embed, view=ControlPanelView())
        return
    await channel.send(embed=embed, view=ControlPanelView())
  except Exception:
    pass


async def setup_admin_panel():
  if ADMIN_CMD_CHANNEL_ID == 0:
    return
  channel = bot.get_channel(ADMIN_CMD_CHANNEL_ID)
  if not channel:
    return

  embed = discord.Embed(
      title="⌨️ ADMIN SLASH COMMAND ROOM",
      description=(
          "ห้องสำหรับพิมพ์แอดมินคอมมานด์\n*หมายเหตุ: คำสั่งทั้งหมดจะซ่อนจากบุคคลทั่วไปโดยอัตโนมัติ*"
      ),
      color=discord.Color.from_rgb(255, 215, 0),
  )
  embed.set_image(url=GIF_BANNER_URL)

  try:
    async for m in channel.history(limit=5):
      if m.author == bot.user:
        await m.edit(embed=embed)
        return
    await channel.send(embed=embed)
  except Exception:
    pass


async def setup_topup_dashboard_panel():
  if TOPUP_DASHBOARD_CHANNEL_ID == 0:
    return
  channel = bot.get_channel(TOPUP_DASHBOARD_CHANNEL_ID)
  if not channel:
    try:
      channel = await bot.fetch_channel(TOPUP_DASHBOARD_CHANNEL_ID)
    except Exception:
      return

  db = load_topup_db()
  embed = create_topup_dashboard_embed(db)
  embed.set_image(url=GIF_BANNER_URL)
  view = TopupView(bot)

  global topup_msg_id
  try:
    async for m in channel.history(limit=5):
      if m.author == bot.user and m.embeds:
        if "ตารางสถานะและยอดเงินกระเป๋า" in m.embeds[0].title:
          topup_msg_id = m.id
          await m.edit(embed=embed, view=view)
          return
    msg = await channel.send(embed=embed, view=view)
    topup_msg_id = msg.id
  except Exception as e:
    print(f"Error setup topup dashboard: {e}")


async def update_topup_dashboard_panel():
  if TOPUP_DASHBOARD_CHANNEL_ID == 0 or not topup_msg_id:
    return
  channel = bot.get_channel(TOPUP_DASHBOARD_CHANNEL_ID)
  if not channel:
    return
  try:
    msg = await channel.fetch_message(topup_msg_id)
    db = load_topup_db()
    embed = create_topup_dashboard_embed(db)
    embed.set_image(url=GIF_BANNER_URL)
    await msg.edit(embed=embed, view=TopupView(bot))
  except Exception as e:
    print(f"Error updating topup dashboard: {e}")


async def update_dashboards():
  conn = sqlite3.connect(DB_PATH, check_same_thread=False)
  cursor = conn.cursor()
  cursor.execute(
      "SELECT key, duration_days, expiry_date, status, hwid FROM licenses"
  )
  rows = cursor.fetchall()
  conn.close()

  now = datetime.now()
  current_time_str = now.strftime("%Y-%m-%d %H:%M:%S")

  # 1. อัปเดตห้องแสดงรายการคีย์ (LICENSE_LIST_CHANNEL_ID)
  if LICENSE_LIST_CHANNEL_ID != 0:
    l_channel = bot.get_channel(LICENSE_LIST_CHANNEL_ID)
    if l_channel:
      embed_l = discord.Embed(
          title="📊 LICENSE KEY STATUS TABLE",
          description=f"🔄 **อัปเดตล่าสุดแบบเรียลไทม์เมื่อ:** `{current_time_str}`",
          color=discord.Color.from_rgb(0, 255, 200),
      )
      if not rows:
        embed_l.add_field(name="สถานะ", value="📭 ยังไม่มีข้อมูลคีย์", inline=False)
      else:
        for r in rows:
          key, days, expiry_str, status, hwid = r
          if status == "Paused":
            t_left = "⏸️ Paused"
          elif days == 0:
            t_left = "♾️ Permanent"
          elif not expiry_str or status == "Unused":
            t_left = f"⏳ Unused ({days} วัน)"
          else:
            expiry_dt = datetime.strptime(expiry_str, "%Y-%m-%d %H:%M:%S")
            rem = expiry_dt - now
            if rem.total_seconds() <= 0:
              t_left = "❌ Expired"
            else:
              t_left = f"⏱️ เหลือ {rem.days} วัน {rem.seconds // 3600} ชม."

          embed_l.add_field(
              name=f"🔑 {key}",
              value=(
                  f"• สถานะ: `{status}` | {t_left}\n• HWID:"
                  f" `{hwid or 'ยังไม่ผูก'}`"
              ),
              inline=False,
          )

      embed_l.set_image(url=GIF_BANNER_URL)
      global license_msg_id
      try:
        if license_msg_id:
          msg = await l_channel.fetch_message(license_msg_id)
          await msg.edit(embed=embed_l)
        else:
          async for m in l_channel.history(limit=5):
            if m.author == bot.user:
              license_msg_id = m.id
              await m.edit(embed=embed_l)
              break
          else:
            msg = await l_channel.send(embed=embed_l)
            license_msg_id = msg.id
      except Exception:
        try:
          msg = await l_channel.send(embed=embed_l)
          license_msg_id = msg.id
        except Exception:
          pass

  # 2. อัปเดตห้องแสดงรายการ HWID ที่กำลังเชื่อมต่อ (ACTIVE_HWID_CHANNEL_ID)
  if ACTIVE_HWID_CHANNEL_ID != 0:
    h_channel = bot.get_channel(ACTIVE_HWID_CHANNEL_ID)
    if h_channel:
      embed_h = discord.Embed(
          title="💻 ACTIVE HWID BINDING TABLE",
          description=f"🔄 **อัปเดตล่าสุดแบบเรียลไทม์เมื่อ:** `{current_time_str}`",
          color=discord.Color.from_rgb(255, 100, 0),
      )
      active_rows = [r for r in rows if r[4] and r[3] == "Active"]
      if not active_rows:
        embed_h.add_field(
            name="สถานะ", value="📭 ยังไม่มี HWID เชื่อมต่อ", inline=False
        )
      else:
        for r in active_rows:
          key, days, expiry_str, status, hwid = r
          embed_h.add_field(
              name=f"💻 HWID: {hwid}", value=f"• คีย์ที่ใช้ผูก: `{key}`", inline=False
          )

      embed_h.set_image(url=GIF_BANNER_URL)
      global hwid_msg_id
      try:
        if hwid_msg_id:
          msg = await h_channel.fetch_message(hwid_msg_id)
          await msg.edit(embed=embed_h)
        else:
          async for m in h_channel.history(limit=5):
            if m.author == bot.user:
              hwid_msg_id = m.id
              await m.edit(embed=embed_h)
              break
          else:
            msg = await h_channel.send(embed=embed_h)
            hwid_msg_id = msg.id
      except Exception:
        try:
          msg = await h_channel.send(embed=embed_h)
          hwid_msg_id = msg.id
        except Exception:
          pass


if __name__ == "__main__":
  threading.Thread(target=run_flask, daemon=True).start()
  server_on()
  bot.run("YOUR_DISCORD_BOT_TOKEN_HERE")
