import asyncio
from datetime import datetime
import logging
import sys
from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import (
    KeyboardButton,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
    Message,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    CallbackQuery,
)

TOKEN = "8543005093:AAFYhex7MKUBxJt0k5KkP8lnFtkFK-XzWmM"

# Rollar uchun Telegram ID lar
ADMIN_IDS = [5332025573]  # Asosiy admin ID
WAREHOUSE_IDS = [8403189546]  # Omborchi ID
CASHIER_IDS = [8403189546]  # Kassir ID

# Mock Ma'lumotlar bazasi (Barcha kerakli maydonlar to'liq kiritildi)
PRODUCTS = [
]

RECEIVERS = [
    "Sardor Naqd pul",
    "Samandar Naqd pul",
    "Sardor (5614 6829 0340 4772)",
    "Samandar (9860 1901 1399 6861)",
]
CART = {}  # {user_id: {product_id: quantity}}
SALES = []  # Barcha cheklar tarixi

dp = Dispatcher(storage=MemoryStorage())

# --- FSM STATE'LARI ---


class AddProduct(StatesGroup):
  name = State()
  size = State()
  qty = State()
  purchase_price = State()
  selling_price = State()
  photo = State()


class POSState(StatesGroup):
  buyer_name = State()


class AddReceiver(StatesGroup):
  name = State()


# --- ASOSIY MENYU ---


def get_main_menu(user_id: int):
  keyboard = [
      [KeyboardButton(text="🛍️ Tovarlar katalogi"), KeyboardButton(text="📜 Cheklar tarixi")],
  ]

  if user_id in ADMIN_IDS:
    keyboard.insert(0, [KeyboardButton(text="📊 Statistika & Moliya")])
    keyboard.insert(1, [KeyboardButton(text="💳 Qabul qiluvchilarni boshqarish")])
  if user_id in WAREHOUSE_IDS or user_id in ADMIN_IDS:
    keyboard.insert(0, [KeyboardButton(text="📦 Tovar qo'shish (Ombor)")])
  if user_id in CASHIER_IDS or user_id in ADMIN_IDS:
    keyboard.insert(0, [KeyboardButton(text="🛒 Kassaga o'tish (POS)")])

  return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)


@dp.message(CommandStart())
async def cmd_start(message: Message):
  user_id = message.from_user.id
  await message.answer(
      f"Assalomu alaykum, *{message.from_user.full_name}*!\n"
      "Do'kon va ombor boshqaruv tizimiga xush kelibsiz. Kerakli bo'limni tanlang:",
      reply_markup=get_main_menu(user_id),
      parse_mode="Markdown",
  )


# ==========================================
# 1. OMBOR QISMI: Tovar qo'shish (FSM)
# ==========================================


@dp.message(F.text == "📦 Tovar qo'shish (Ombor)")
async def start_add_product(message: Message, state: FSMContext):
  user_id = message.from_user.id
  if user_id not in WAREHOUSE_IDS and user_id not in ADMIN_IDS:
    await message.answer("Sizda bu amalni bajarish uchun huquq yo'q! ❌")
    return

  await state.set_state(AddProduct.name)
  await message.answer(
      "📦 **Yangi tovar qo'shish**\n\n1. Tovar nomini kiriting:",
      reply_markup=ReplyKeyboardRemove(),
      parse_mode="Markdown",
  )


@dp.message(AddProduct.name)
async def process_product_name(message: Message, state: FSMContext):
  await state.update_data(name=message.text)
  await state.set_state(AddProduct.size)
  await message.answer("2. Tovarning hajmi yoki o'lchamini kiriting (masalan: 1L, 500g):")


@dp.message(AddProduct.size)
async def process_product_size(message: Message, state: FSMContext):
  await state.update_data(size=message.text)
  await state.set_state(AddProduct.qty)
  await message.answer("3. Ombordagi boshlang'ich miqdorini (sonini) kiriting (faqat raqam):")


@dp.message(AddProduct.qty)
async def process_product_qty(message: Message, state: FSMContext):
  if not message.text.isdigit():
    await message.answer("Iltimos, faqat musbat raqam kiriting!")
    return
  await state.update_data(qty=int(message.text))
  await state.set_state(AddProduct.purchase_price)
  await message.answer("4. **Sotib olish narxini** kiriting (so'mda):", parse_mode="Markdown")


@dp.message(AddProduct.purchase_price)
async def process_purchase_price(message: Message, state: FSMContext):
  try:
    price = float(message.text)
  except ValueError:
    await message.answer("Iltimos, to'g'ri narx kiriting!")
    return
  await state.update_data(purchase_price=price)
  await state.set_state(AddProduct.selling_price)
  await message.answer("5. **Sotish narxini** kiriting (so'mda):", parse_mode="Markdown")


@dp.message(AddProduct.selling_price)
async def process_selling_price(message: Message, state: FSMContext):
  try:
    price = float(message.text)
  except ValueError:
    await message.answer("Iltimos, to'g'ri narx kiriting!")
    return
  await state.update_data(selling_price=price)
  await state.set_state(AddProduct.photo)
  await message.answer("6. Tovarning **rasmini** yuboring (yoki rasm bo'lmasa istalgan matn yuboring):")


@dp.message(AddProduct.photo)
async def process_product_photo(message: Message, state: FSMContext):
  photo_id = None
  if message.photo:
    photo_id = message.photo[-1].file_id

  data = await state.get_data()
  new_id = max([p["id"] for p in PRODUCTS], default=0) + 1

  new_product = {
      "id": new_id,
      "name": data["name"],
      "size": data["size"],
      "qty": data["qty"],
      "purchase_price": data["purchase_price"],
      "selling_price": data["selling_price"],
      "photo": photo_id,
  }
  PRODUCTS.append(new_product)
  await state.clear()

  user_id = message.from_user.id
  await message.answer(
      f"✅ Tovar omborga muvaffaqiyatli qo'shildi!\n\n"
      f"🆔 ID: #{new_product['id']}\n"
      f"📦 Nomi: {new_product['name']} ({new_product['size']})\n"
      f"🔢 Soni: {new_product['qty']} dona\n"
      f"📥 Xarid narxi: {new_product['purchase_price']} so'm\n"
      f"🏷️ Sotish narxi: {new_product['selling_price']} so'm",
      reply_markup=get_main_menu(user_id),
  )


# ==========================================
# 2. TOVARLAR KATALOGI
# ==========================================


@dp.message(F.text == "🛍️ Tovarlar katalogi")
async def show_product_catalog(message: Message):
  if not PRODUCTS:
    await message.answer("Hozircha omborda mahsulotlar mavjud emas.")
    return

  await message.answer("🛍️ **Ombordagi tovarlar katalogi:**", parse_mode="Markdown")
  for p in PRODUCTS:
    status_icon = "🟢" if p["qty"] > 5 else ("🟡" if p["qty"] > 0 else "🔴")
    # Xavfsiz tarzda olish (.get) xatolikning oldini oladi
    p_price = p.get("purchase_price", 0)
    s_price = p.get("selling_price", 0)

    text = (
        f"🆔 ID: *#{p['id']}* | {status_icon}\n"
        f"📦 *{p['name']}* ({p['size']})\n"
        f"🏷️ Sotish narxi: *{s_price} so'm*\n"
        f"📥 Xarid narxi: {p_price} so'm\n"
        f"📊 Qoldiq miqdori: *{p['qty']} dona*"
    )
    if p["photo"]:
      await message.answer_photo(photo=p["photo"], caption=text, parse_mode="Markdown")
    else:
      await message.answer(text, parse_mode="Markdown")


# ==========================================
# 3. KASSIR (POS) INLINE TUGMALI TIZIMI
# ==========================================


def generate_pos_keyboard(user_id: int):
  keyboard = []
  for p in PRODUCTS:
    if p["qty"] <= 0:
      continue
    qty_in_cart = CART.get(user_id, {}).get(p["id"], 0)
    s_price = p.get("selling_price", 0)
    label = f"{p['name']} ({p['size']}) - {s_price} so'm [Qoldiq: {p['qty']}]"
    if qty_in_cart > 0:
      label = f"✅ {label} (Savatda: {qty_in_cart})"

    keyboard.append(
        [InlineKeyboardButton(text=f"➕ {label}", callback_data=f"pos_add_{p['id']}")]
    )

  user_cart = CART.get(user_id, {})
  if user_cart:
    keyboard.append([InlineKeyboardButton(text="🚀 Savdoni yakunlash", callback_data="pos_checkout")])
    keyboard.append([InlineKeyboardButton(text="🗑️ Savatni tozalash", callback_data="pos_clear")])

  return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_cart_summary(user_id: int):
  user_cart = CART.get(user_id, {})
  if not user_cart:
    return "🛒 *Savatingiz bo'sh.* \nTovarni tanlash uchun pastdagi tugmalarni bosing:"

  text = "🛒 *Joriy savatcha:*\n\n"
  total_sum = 0
  for prod_id, qty in user_cart.items():
    product = next((p for p in PRODUCTS if p["id"] == prod_id), None)
    if product:
      s_price = product.get("selling_price", 0)
      subtotal = s_price * qty
      total_sum += subtotal
      text += f"▪️ {product['name']} x {qty} dona = *{subtotal} so'm*\n"

  text += f"\n💰 *Jami summa: {total_sum} so'm*"
  return text


@dp.message(F.text == "🛒 Kassaga o'tish (POS)")
async def open_pos_terminal(message: Message):
  user_id = message.from_user.id
  if user_id not in CASHIER_IDS and user_id not in ADMIN_IDS and user_id not in WAREHOUSE_IDS:
    await message.answer("Sizda kassa uchun ruxsat yo'q! ❌")
    return

  if user_id not in CART:
    CART[user_id] = {}

  text = get_cart_summary(user_id)
  await message.answer(text, reply_markup=generate_pos_keyboard(user_id), parse_mode="Markdown")


@dp.callback_query(F.data.startswith("pos_add_"))
async def callback_add_product(callback: CallbackQuery):
  user_id = callback.from_user.id
  prod_id = int(callback.data.split("_")[2])

  product = next((p for p in PRODUCTS if p["id"] == prod_id), None)
  if not product:
    await callback.answer("Tovar topilmadi!", show_alert=True)
    return

  if user_id not in CART:
    CART[user_id] = {}

  current_in_cart = CART[user_id].get(prod_id, 0)
  if product["qty"] <= current_in_cart:
    await callback.answer(f"Omborda yetarli miqdor yo'q! (Qoldiq: {product['qty']} ta)", show_alert=True)
    return

  CART[user_id][prod_id] = current_in_cart + 1
  await callback.answer(f"{product['name']} savatga qo'shildi!")

  text = get_cart_summary(user_id)
  await callback.message.edit_text(text, reply_markup=generate_pos_keyboard(user_id), parse_mode="Markdown")


@dp.callback_query(F.data == "pos_clear")
async def callback_clear_cart(callback: CallbackQuery):
  user_id = callback.from_user.id
  CART[user_id] = {}
  await callback.answer("Savat tozalandi.")
  text = get_cart_summary(user_id)
  await callback.message.edit_text(text, reply_markup=generate_pos_keyboard(user_id), parse_mode="Markdown")


@dp.callback_query(F.data == "pos_checkout")
async def callback_start_checkout(callback: CallbackQuery, state: FSMContext):
  user_id = callback.from_user.id
  if not CART.get(user_id):
    await callback.answer("Savatingiz bo'sh!", show_alert=True)
    return

  await state.set_state(POSState.buyer_name)
  await callback.message.answer("✍️ Haridorning F.I.Sh (Ismini) kiriting:", reply_markup=ReplyKeyboardRemove())
  await callback.answer()


@dp.message(POSState.buyer_name)
async def process_buyer_name(message: Message, state: FSMContext):
  buyer_name = message.text

  if not RECEIVERS:
    await message.answer("Diqqat: Admin tomonidan qabul qiluvchilar kiritilmagan!")
    await state.clear()
    return

  keyboard = []
  for r in RECEIVERS:
    keyboard.append([InlineKeyboardButton(text=f"📥 {r}", callback_data=f"recv_{r[:20]}")])

  await state.update_data(buyer_name=buyer_name)
  await message.answer(
      f"Haridor: *{buyer_name}*\nPul qabul qilingan hisobni (yoki shaxsni) tanlang:",
      reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard),
      parse_mode="Markdown",
  )


@dp.callback_query(F.data.startswith("recv_"))
async def callback_finish_sale(callback: CallbackQuery, state: FSMContext):
  user_id = callback.from_user.id
  data = await state.get_data()
  buyer_name = data.get("buyer_name")

  short_recv = callback.data.split("_")[1]
  receiver = next((r for r in RECEIVERS if r.startswith(short_recv)), "Noma'lum")

  user_cart = CART.get(user_id, {})
  total_sum = 0
  total_purchase_cost = 0
  sale_details = []
  raw_items_list = []
  sale_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

  for prod_id, qty in user_cart.items():
    product = next((p for p in PRODUCTS if p["id"] == prod_id), None)
    if product:
      product["qty"] -= qty
      s_price = product.get("selling_price", 0)
      p_price = product.get("purchase_price", 0)

      subtotal = s_price * qty
      sub_purchase = p_price * qty
      total_sum += subtotal
      total_purchase_cost += sub_purchase

      sale_details.append(f"- {product['name']} x {qty} dona = {subtotal} so'm")
      raw_items_list.append({
          "name": product["name"],
          "qty": qty,
          "selling_price": s_price,
          "purchase_price": p_price,
          "subtotal": subtotal,
      })

  sale_profit = total_sum - total_purchase_cost

  sale_record = {
      "time": sale_time,
      "buyer": buyer_name,
      "receiver": receiver,
      "total": total_sum,
      "profit": sale_profit,
      "items": sale_details,
      "raw_items": raw_items_list,
      "cashier": callback.from_user.full_name,
  }
  SALES.append(sale_record)

  CART[user_id] = {}
  await state.clear()

  receipt = (
      f"🧾 *SAVDO CHEKI*\n"
      f"-----------------------------------\n"
      f"🕒 Vaqti: {sale_time}\n"
      f"👤 Haridor: {buyer_name}\n"
      f"📥 Qabul qiluvchi: {receiver}\n"
      f"-----------------------------------\n"
      f"🛒 Sotilgan mahsulotlar:\n" + "\n".join(sale_details) + "\n"
      f"-----------------------------------\n"
      f"💰 *Jami to'lov: {total_sum} so'm*\n"
      f"✍️ Kassir: {callback.from_user.full_name}"
  )

  await callback.message.edit_text(receipt, parse_mode="Markdown")
  await callback.message.answer("Asosiy menyu:", reply_markup=get_main_menu(user_id))
  await callback.answer("Savdo muvaffaqiyatli yakunlandi! ✅")


# ==========================================
# 4. CHEKLAR TARIXI
# ==========================================


@dp.message(F.text == "📜 Cheklar tarixi")
async def show_all_receipts(message: Message):
  if not SALES:
    await message.answer("Hozircha do'konda amalga oshirilgan savdolar mavjud emas.")
    return

  text = f"📜 *Barcha savdo cheklari tarixi* (Jami: {len(SALES)} ta):\n\n"
  for idx, s in enumerate(SALES[-10:], 1):
    items_str = ", ".join([f"{i['name']} x{i['qty']}" for i in s["raw_items"]])
    text += (
        f"▪️ *Chek #{idx}* | 🕒 {s['time']}\n"
        f"   👤 Haridor: {s['buyer']} | ✍️ Kassir: {s['cashier']}\n"
        f"   🛒 Tovarlar: {items_str}\n"
        f"   💰 Summa: *{s['total']} so'm* (Foyda: +{s['profit']} so'm)\n"
        f"-----------------------------------\n"
    )

  await message.answer(text, parse_mode="Markdown")


# ==========================================
# 5. STATISTIKA & MOLIYA (Analytics)
# ==========================================


@dp.message(F.text == "📊 Statistika & Moliya")
async def show_statistics(message: Message):
  if message.from_user.id not in ADMIN_IDS:
    await message.answer("Bu bo'lim faqat adminlar uchun! ❌")
    return

  total_revenue = sum(s["total"] for s in SALES)
  total_realized_profit = sum(s["profit"] for s in SALES)
  total_sold_items_count = sum(sum(i["qty"] for i in s["raw_items"]) for s in SALES)

  expected_profit = 0
  total_inventory_purchase_value = 0
  total_inventory_selling_value = 0

  for p in PRODUCTS:
    item_qty = p["qty"]
    p_cost = p.get("purchase_price", 0)
    s_price = p.get("selling_price", 0)

    total_inventory_purchase_value += p_cost * item_qty
    total_inventory_selling_value += s_price * item_qty
    expected_profit += (s_price - p_cost) * item_qty

  text = (
      f"📊 *DO'KON VA OMBOR STATISTIKASI*\n\n"
      f"🛒 **Savdo ko'rsatkichlari:**\n"
      f"• Jami qilingan savdolar soni: *{len(SALES)} ta chek*\n"
      f"• Sotilgan jami mahsulotlar: *{total_sold_items_count} dona*\n"
      f"• Umumiy tushum: *{total_revenue:,.0f} so'm*\n"
      f"• 🟢 *Hozirgacha qilingan sof foyda:* *{total_realized_profit:,.0f} so'm*\n\n"
      f"📦 **Ombor holati va prognoz:**\n"
      f"• Ombordagi xil mahsulotlar: *{len(PRODUCTS)} xil*\n"
      f"• Ombordagi tovarlarning xarid qiymati: *{total_inventory_purchase_value:,.0f} so'm*\n"
      f"• Ombordagi tovarlarning sotuv qiymati: *{total_inventory_selling_value:,.0f} so'm*\n"
      f"• ⏳ *Kutilayotgan sof foyda (ombor sotilsa):* *{expected_profit:,.0f} so'm*\n"
  )

  await message.answer(text, parse_mode="Markdown")


# ==========================================
# 6. ADMIN: QABUL QILUVCHILARNI BOSHQARISH
# ==========================================


@dp.message(F.text == "💳 Qabul qiluvchilarni boshqarish")
async def manage_receivers(message: Message, state: FSMContext):
  if message.from_user.id not in ADMIN_IDS:
    return

  text = "💳 *Hozirgi qabul qiluvchilar (shaxs yoki karta) ro'yxati:*\n"
  for idx, r in enumerate(RECEIVERS, 1):
    text += f"{idx}. {r}\n"

  text += "\nYangi qabul qiluvchi qo'shish uchun uning nomini yoki karta ma'lumotini yuboring:"
  await state.set_state(AddReceiver.name)
  await message.answer(text, parse_mode="Markdown", reply_markup=ReplyKeyboardRemove())


@dp.message(AddReceiver.name)
async def save_receiver(message: Message, state: FSMContext):
  RECEIVERS.append(message.text)
  await state.clear()
  user_id = message.from_user.id
  await message.answer(
      f"✅ Muvaffaqiyatli qo'shildi: *{message.text}*",
      reply_markup=get_main_menu(user_id),
      parse_mode="Markdown",
  )


async def main():
    bot = Bot(token=TOKEN)
    
    # Eski webhookni o'chirish uchun mana shu qatorni qo'shamiz:
    await bot.delete_webhook(drop_pending_updates=True)
    
    print("Complete Store Bot is running without errors...")
    await dp.start_polling(bot)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, stream=sys.stdout)
    asyncio.run(main())
