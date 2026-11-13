import os, sqlite3, logging
from datetime import datetime
import telebot
from telebot import types

TOKEN = os.getenv("BOT_TOKEN", "").strip()
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))
DB = os.getenv("DB_PATH", "data/shop.db")
if not TOKEN:
    raise RuntimeError("Set BOT_TOKEN in environment variables")

os.makedirs(os.path.dirname(DB) or ".", exist_ok=True)
bot = telebot.TeleBot(TOKEN, parse_mode="HTML")
logging.basicConfig(level=logging.INFO)

def db():
    c = sqlite3.connect(DB)
    c.row_factory = sqlite3.Row
    return c

def init():
    with db() as c:
        c.executescript("""
        CREATE TABLE IF NOT EXISTS users(id INTEGER PRIMARY KEY, balance INTEGER NOT NULL DEFAULT 0);
        CREATE TABLE IF NOT EXISTS products(id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, price INTEGER NOT NULL, active INTEGER NOT NULL DEFAULT 1);
        CREATE TABLE IF NOT EXISTS keys(id INTEGER PRIMARY KEY AUTOINCREMENT, product_id INTEGER NOT NULL, secret TEXT NOT NULL, sold_to INTEGER, sold_at TEXT);
        CREATE TABLE IF NOT EXISTS orders(id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL, product_id INTEGER NOT NULL, price INTEGER NOT NULL, key_id INTEGER, status TEXT NOT NULL, created_at TEXT NOT NULL);
        """)

def ensure_user(uid):
    with db() as c:
        c.execute("INSERT OR IGNORE INTO users(id) VALUES(?)", (uid,))

def is_admin(uid):
    return ADMIN_ID != 0 and uid == ADMIN_ID

def main_menu(uid):
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.row("🛒 Cửa hàng", "👛 Ví của tôi")
    kb.row("📦 Đơn hàng", "🆔 ID của tôi")
    if is_admin(uid):
        kb.row("🛠 Quản trị")
    return kb

@bot.message_handler(commands=["start"])
def start(m):
    ensure_user(m.from_user.id)
    bot.send_message(m.chat.id, "🏪 <b>SOP TBANG STORE</b>\\nChào mừng mày đến cửa hàng!", reply_markup=main_menu(m.from_user.id))

@bot.message_handler(commands=["myid"])
def myid(m):
    bot.reply_to(m, f"Telegram ID của mày: <code>{m.from_user.id}</code>")

@bot.message_handler(func=lambda m: m.text == "🆔 ID của tôi")
def showid(m):
    myid(m)

@bot.message_handler(func=lambda m: m.text == "🛒 Cửa hàng")
def shop(m):
    with db() as c:
        products = c.execute("SELECT p.*, (SELECT COUNT(*) FROM keys k WHERE k.product_id=p.id AND k.sold_to IS NULL) stock FROM products p WHERE active=1 ORDER BY id").fetchall()
    if not products:
        return bot.send_message(m.chat.id, "Cửa hàng hiện chưa có sản phẩm.")
    kb = types.InlineKeyboardMarkup()
    for p in products:
        kb.add(types.InlineKeyboardButton(f"{p['name']} — {p['price']:,}đ (còn {p['stock']})", callback_data=f"buy:{p['id']}"))
    bot.send_message(m.chat.id, "Chọn sản phẩm muốn mua:", reply_markup=kb)

@bot.callback_query_handler(func=lambda q: q.data.startswith("buy:"))
def buy(q):
    uid = q.from_user.id
    pid = int(q.data.split(":")[1])
    ensure_user(uid)
    with db() as c:
        c.execute("BEGIN IMMEDIATE")
        p = c.execute("SELECT * FROM products WHERE id=? AND active=1", (pid,)).fetchone()
        u = c.execute("SELECT balance FROM users WHERE id=?", (uid,)).fetchone()
        k = c.execute("SELECT * FROM keys WHERE product_id=? AND sold_to IS NULL ORDER BY id LIMIT 1", (pid,)).fetchone()
        if not p:
            c.rollback()
            return bot.answer_callback_query(q.id, "Sản phẩm không tồn tại.")
        if not k:
            c.rollback()
            return bot.answer_callback_query(q.id, "Sản phẩm đã hết hàng.", show_alert=True)
        if not u or u["balance"] < p["price"]:
            c.rollback()
            return bot.answer_callback_query(q.id, "Số dư không đủ. Hãy nạp tiền hoặc liên hệ admin.", show_alert=True)
        now = datetime.utcnow().isoformat()
        c.execute("UPDATE users SET balance=balance-? WHERE id=?", (p["price"], uid))
        c.execute("UPDATE keys SET sold_to=?, sold_at=? WHERE id=? AND sold_to IS NULL", (uid, now, k["id"]))
        c.execute("INSERT INTO orders(user_id,product_id,price,key_id,status,created_at) VALUES(?,?,?,?,?,?)",
                  (uid, pid, p["price"], k["id"], "delivered", now))
        c.commit()
    bot.answer_callback_query(q.id, "Mua hàng thành công!")
    bot.send_message(uid, f"✅ <b>Đơn hàng đã giao</b>\\nSản phẩm: {p['name']}\\nMã đơn: #{c.execute if False else 'đã lưu'}\\n\\n🔑 Key của mày:\\n<code>{k['secret']}</code>")
    bot.send_message(q.message.chat.id, "Đã gửi key riêng cho mày.")

@bot.message_handler(func=lambda m: m.text == "👛 Ví của tôi")
def wallet(m):
    ensure_user(m.from_user.id)
    with db() as c:
        u = c.execute("SELECT balance FROM users WHERE id=?", (m.from_user.id,)).fetchone()
    bot.send_message(m.chat.id, f"👛 Số dư: <b>{u['balance']:,}đ</b>\\nMuốn nạp tiền, liên hệ quản trị viên để được hướng dẫn.")

@bot.message_handler(func=lambda m: m.text == "📦 Đơn hàng")
def orders(m):
    with db() as c:
        rows = c.execute("""SELECT o.id,o.price,o.status,o.created_at,p.name
                            FROM orders o JOIN products p ON p.id=o.product_id
                            WHERE o.user_id=? ORDER BY o.id DESC LIMIT 10""", (m.from_user.id,)).fetchall()
    if not rows:
        return bot.send_message(m.chat.id, "Mày chưa có đơn hàng nào.")
    text = "📦 <b>10 đơn gần nhất</b>\\n" + "\\n".join([f"#{r['id']} · {r['name']} · {r['price']:,}đ · {r['status']}" for r in rows])
    bot.send_message(m.chat.id, text)

@bot.message_handler(func=lambda m: m.text == "🛠 Quản trị")
def admin_help(m):
    if not is_admin(m.from_user.id):
        return
    bot.send_message(m.chat.id,
        "<b>Lệnh quản trị</b>\\n"
        "/addproduct Tên sản phẩm | giá_vnd\\n"
        "/addkeys ID_sản_phẩm rồi gửi từng key, mỗi dòng một key\\n"
        "/products — xem sản phẩm và tồn kho\\n"
        "/credit Telegram_ID | số_tiền — cộng số dư\\n"
        "/myid — xem Telegram ID")

@bot.message_handler(commands=["addproduct"])
def addproduct(m):
    if not is_admin(m.from_user.id): return
    try:
        name, price = m.text.split(" ",1)[1].rsplit("|",1)
        price = int(price.strip())
        with db() as c:
            cur = c.execute("INSERT INTO products(name,price) VALUES(?,?)", (name.strip(), price))
            pid = cur.lastrowid
        bot.reply_to(m, f"Đã tạo sản phẩm ID <b>{pid}</b>: {name.strip()} — {price:,}đ")
    except Exception:
        bot.reply_to(m, "Cú pháp: /addproduct Tên sản phẩm | 20000")

@bot.message_handler(commands=["addkeys"])
def addkeys(m):
    if not is_admin(m.from_user.id): return
    try:
        pid = int(m.text.split()[1])
        msg = bot.reply_to(m, f"Gửi các key cho sản phẩm ID {pid}, mỗi dòng một key. Gửi /done khi xong.")
        bot.register_next_step_handler(msg, save_keys, pid)
    except Exception:
        bot.reply_to(m, "Cú pháp: /addkeys ID_sản_phẩm")

def save_keys(m, pid):
    if not is_admin(m.from_user.id): return
    if m.text.strip() == "/done":
        return bot.reply_to(m, "Đã kết thúc nhập kho.")
    lines = [x.strip() for x in m.text.splitlines() if x.strip()]
    with db() as c:
        exists = c.execute("SELECT id FROM products WHERE id=?", (pid,)).fetchone()
        if not exists: return bot.reply_to(m, "Không tìm thấy sản phẩm.")
        c.executemany("INSERT INTO keys(product_id,secret) VALUES(?,?)", [(pid,x) for x in lines])
    bot.reply_to(m, f"Đã nhập {len(lines)} key. Gửi tiếp key hoặc /done.")
    bot.register_next_step_handler(m, save_keys, pid)

@bot.message_handler(commands=["products"])
def products(m):
    if not is_admin(m.from_user.id): return
    with db() as c:
        rows = c.execute("""SELECT p.id,p.name,p.price,
          (SELECT COUNT(*) FROM keys k WHERE k.product_id=p.id AND k.sold_to IS NULL) stock
          FROM products p ORDER BY p.id""").fetchall()
    bot.reply_to(m, "\\n".join([f"ID {r['id']}: {r['name']} — {r['price']:,}đ — còn {r['stock']} key" for r in rows]) or "Chưa có sản phẩm.")

@bot.message_handler(commands=["credit"])
def credit(m):
    if not is_admin(m.from_user.id): return
    try:
        uid, amount = m.text.split(" ",1)[1].split("|")
        uid, amount = int(uid.strip()), int(amount.strip())
        if amount <= 0: raise ValueError()
        ensure_user(uid)
        with db() as c:
            c.execute("UPDATE users SET balance=balance+? WHERE id=?", (amount,uid))
        bot.reply_to(m, f"Đã cộng {amount:,}đ cho tài khoản {uid}.")
    except Exception:
        bot.reply_to(m, "Cú pháp: /credit Telegram_ID | 50000")

if __name__ == "__main__":
    init()
    logging.info("SOP TBANG STORE bot is running")
    bot.infinity_polling(skip_pending=True, timeout=30, long_polling_timeout=30)
