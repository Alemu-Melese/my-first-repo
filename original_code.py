"""
Compatibility restore for the deleted legacy file.

This wrapper keeps the old filename (`original_code.py`) runnable while
the real implementation lives in the modular `app/` package.
"""

import asyncio
import logging

from app.main import main


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logging.info("Bot stopped!")
import sqlite3
import asyncio
import logging
from aiogram import Bot, Dispatcher, types, F
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import (
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    ReplyKeyboardRemove,
)
from aiogram.enums import ParseMode

# 1. የቦትህን ቶከን እዚህ ጋር አስገባ (ከ @BotFather ያገኘኸው)
TOKEN = "8742396124:AAGsawWAUEznTuGrh5eglutSRtEqoLQMtCE"

# 2. የአድሚን ID (ያንተን ID እዚህ ያስገቡ - ለ /admin ክፍክ ጥቅም ላይ ይውላል)
ADMIN_IDS = [123456789]

# 3. ቦቱን እና ዲስፓቸሩን ማዘጋጀት
logging.basicConfig(level=logging.INFO)
bot = Bot(token=TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.MARKDOWN))
dp = Dispatcher(storage=MemoryStorage())


# 4. የ FSM (States) ዝርዝር - ለምዝገባ እና ለአድሚን ተግባራት
class RegistrationState(StatesGroup):
    waiting_for_name = State()
    waiting_for_gender = State()
    waiting_for_photo = State()
    waiting_for_password = State()


class AdminStates(StatesGroup):
    waiting_for_broadcast = State()
    waiting_for_ban_id = State()
    waiting_for_boost_id = State()
    waiting_for_duration = State()
    waiting_for_reset_id = State()


# 5. ዳታቤዝ ማስጀመሪያ (Database Initialization)
def init_db():
    conn = sqlite3.connect("love_bot.db")
    cursor = conn.cursor()

    # የተጠቃሚዎች ሰንጠረዥ
    cursor.execute(
        """CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY,
        name TEXT,
        gender TEXT,
        photo_id TEXT,
        password TEXT,
        is_hidden INTEGER DEFAULT 0,
        is_boosted INTEGER DEFAULT 0,
        boost_expire TIMESTAMP NULL,
        last_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        reg_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )"""
    )

    # የትዕዛዝ/ጥያቄዎች ሰንጠረዥ
    cursor.execute(
        """CREATE TABLE IF NOT EXISTS orders (
        order_id INTEGER PRIMARY KEY AUTOINCREMENT,
        sender_id INTEGER,
        receiver_id INTEGER,
        status TEXT DEFAULT 'pending', -- pending, accepted, rejected
        order_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )"""
    )

    # የንግግር (Messages) ሰንጠረዥ
    cursor.execute(
        """CREATE TABLE IF NOT EXISTS messages (
        msg_id INTEGER PRIMARY KEY AUTOINCREMENT,
        order_id INTEGER,
        sender_id INTEGER,
        receiver_id INTEGER,
        content TEXT,
        is_deleted INTEGER DEFAULT 0,
        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )"""
    )

    conn.commit()
    conn.close()


# ዳታቤዙን መፍጠር
init_db()


# --- 2. የምዝገባ ስቴቶች (Registration States) ---
class Registration(StatesGroup):
    waiting_for_name = State()
    waiting_for_gender = State()
    waiting_for_photos = State()


# --- 3. የምዝገባ ሎጅክ (Registration Logic) ---
@dp.message(Command("start"))
async def cmd_start(message: types.Message, state: FSMContext):
    user_id = message.from_user.id

    with sqlite3.connect("love_bot.db") as conn:
        cursor = conn.cursor()
        # 1. መጀመሪያ ተጠቃሚው መኖሩን ቼክ እናድርግ
        cursor.execute("SELECT name FROM users WHERE user_id = ?", (user_id,))
        user = cursor.fetchone()

        # የ Last Seen ሰዓትን ማደስ
        cursor.execute(
            "UPDATE users SET last_seen = CURRENT_TIMESTAMP WHERE user_id = ?",
            (user_id,),
        )
        conn.commit()

    # 2. ተጠቃሚው ከሌለ ወደ ምዝገባ (FSM) እንላከው
    if user is None:
        await state.set_state(RegistrationState.waiting_for_name)
        await message.answer(
            "👋 እንኳን በሰላም መጡ! ለመጀመር መጀመሪያ ይመዝገቡ።\n\nእባክዎ **ሙሉ ስምዎን** ይጻፉልኝ፦"
        )
    else:
        # 3. ቀድሞ ከተመዘገበ ዋናውን ሜኑ አሳየው
        await message.answer(f"እንኳን በደህና ተመለሱ {user[0]}! ❤️")
        # እዚህ ጋር ዋናውን ሜኑ (Keyboard) የምታሳይበትን ፈንክሽን ጥራ


@dp.message(RegistrationState.waiting_for_name)
async def process_name(message: types.Message, state: FSMContext):
    # 1. ስሙን በጊዜያዊነት መያዝ
    await state.update_data(name=message.text)

    # 2. ወደ ሚቀጥለው ስቴት (ጾታ) መሸጋገር
    await state.set_state(RegistrationState.waiting_for_gender)

    # 3. የጾታ መምረጫ በተኖች
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="ወንድ 👨", callback_data="gen_Male"),
                InlineKeyboardButton(text="ሴት 👩", callback_data="gen_Female"),
            ]
        ]
    )

    await message.answer(f"በጣም ጥሩ {message.text}! አሁን ደግሞ ጾታዎን ይምረጡ፦", reply_markup=kb)


@dp.callback_query(RegistrationState.waiting_for_gender, F.data.startswith("gen_"))
async def process_gender(callback: types.CallbackQuery, state: FSMContext):
    # ጾታውን መለየት (Male ወይም Female)
    gender = callback.data.split("_")[1]
    await state.update_data(gender=gender)

    # ወደ ፎቶ መቀበያ ስቴት መሸጋገር
    await state.set_state(RegistrationState.waiting_for_photo)

    await callback.message.edit_text("በጣም አሪፍ! አሁን ደግሞ ለፕሮፋይል የሚሆን **አንድ ፎቶ** ይላኩሉኝ፦")
    await callback.answer()


@dp.message(RegistrationState.waiting_for_photo, F.photo)
async def process_photo(message: types.Message, state: FSMContext):
    # 1. የፎቶውን ID መውሰድ (ከፍተኛ ጥራት ያለው - [-1])
    photo_id = message.photo[-1].file_id
    await state.update_data(photo_id=photo_id)

    # 2. ወደ ፓስወርድ ስቴት መሸጋገር
    await state.set_state(RegistrationState.waiting_for_password)

    # 3. ቀጣዩን ትዕዛዝ መስጠት
    await message.answer(
        "📸 ፎቶው ደርሶኛል! በጣም አሪፍ ነው።\n\n"
        "አሁን በመጨረሻም፦ ወደ 'More' ሜኑ ለመግባት የሚሆን **ሚስጥር ቁጥር (Password)** ይጻፉልኝ፦"
    )


# ፎቶ ካልሆነ ሌላ ነገር ለላከ ሰው የሚሰጥ ማስጠንቀቂያ
@dp.message(RegistrationState.waiting_for_photo)
async def invalid_photo(message: types.Message):
    await message.answer("⚠️ እባክዎ ፎቶ ብቻ ይላኩ!")


# ====passward acsepter===
@dp.message(RegistrationState.waiting_for_password)
async def process_password(message: types.Message, state: FSMContext):
    password = message.text
    data = await state.get_data()
    user_id = message.from_user.id

    # 1. መረጃውን ከ state ውስጥ ማውጣት
    name = data.get("name")
    gender = data.get("gender")
    photo_id = data.get("photo_id")

    try:
        # 2. ዳታቤዝ ውስጥ መመዝገብ
        with sqlite3.connect("love_bot.db") as conn:
            cursor = conn.cursor()
            # INSERT OR REPLACE ተጠቃሚው ቀድሞ ካለ ዳታውን ያድሳል
            cursor.execute(
                """
                INSERT OR REPLACE INTO users (user_id, name, gender, photo_id, password, is_hidden, is_boosted)
                VALUES (?, ?, ?, ?, ?, 0, 0)
            """,
                (user_id, name, gender, photo_id, password),
            )
            conn.commit()

        # 3. ስቴቱን ማጽዳት (FSM ይቆማል)
        await state.clear()

        # 4. የመጨረሻ መልዕክት እና ዋናውን ሜኑ ማሳየት
        await message.answer(
            f"✅ **እንኳን ደስ አለዎት {name}!**\n\nምዝገባዎ በተሳካ ሁኔታ ተጠናቋል። አሁን ሌሎች ተጠቃሚዎችን ማየት ይችላሉ።",
            reply_markup=get_main_interface_with_users(user_id),  # ዋናውን ሜኑ እዚህ ጥራ
        )

    except Exception as e:
        # ስህተት ካለ እዚህ ያሳየናል
        print(f"Database Error: {e}")
        await message.answer("⚠️ ይቅርታ፣ መረጃዎን መመዝገብ አልቻልኩም። እባክዎ ትንሽ ቆይተው ይሞክሩ።")


@dp.callback_query(F.data == "finish_reg")
async def finish_registration(callback: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    user_id = callback.from_user.id
    # ፎቶዎችን በኮማ ለይተን እናስቀምጣቸዋለን (Scalable Storage)
    photos_str = ",".join(data["photos_list"])

    conn = sqlite3.connect("love_bot.db")
    cursor = conn.cursor()
    cursor.execute(
        """INSERT INTO users (user_id, name, gender, photos) 
                      VALUES (?, ?, ?, ?)""",
        (user_id, data["full_name"], data["gender"], photos_str),
    )
    conn.commit()
    conn.close()

    await state.clear()
    await callback.message.delete()  # የቀደመውን እናጠፋለን
    await callback.message.answer(
        "🎉 ምዝገባዎ በተሳካ ሁኔታ ተጠናቋል! እንኳን ደህና መጡ።\n(ዲፎልት ፓስወርድዎ፡ 123456 ነው)"
    )
    # ቀጥሎ ደረጃ 2ን እዚህ ጋር እንቀጥላለን...


def get_main_interface(user_id, filter_type="All"):
    # --- Row 1 & 2: ቋሚ Header (ከዳታቤዝ ሊመጣ ይችላል) ---
    # # ለምሳሌ፡ ባላንስ እና ከአድሚን የመጣ መልዕክት
    # user_balance = "0.00 ETB"  # ወደፊት ከዳታቤዝ እናመጣዋለን
    # admin_msg = "📢 አዲስ፡ ዛሬ 10 ሺህ አባላት ተመዝግበዋል!"

    header_text = (
        f"━━━━━━━━━━━━━━\n"
        f"💰 ባላንስ፡ {user_balance} | 📩 ጥያቄ፡ 0/10\n"
        f"✉️ {admin_msg}\n"
        f"━━━━━━━━━━━━━━\n"
        f"አሁን የሚታየው፡ የ{filter_type} ዝርዝር"
    )

    # --- Row 3: Tabs (በአንድ ረድፍ) ---
    tabs = [
        InlineKeyboardButton(text="🔍 Search", callback_data="tab_search"),
        InlineKeyboardButton(text="👥 All", callback_data="tab_all"),
        InlineKeyboardButton(text="👨 Male", callback_data="tab_male"),
        InlineKeyboardButton(text="👩 Female", callback_data="tab_female"),
    ]

    # የኪቦርድ አወቃቀር (Grid)
    keyboard = [tabs]  # ታቦቹ መጀመሪያ ረድፍ ላይ

    # --- የአባላት ዝርዝር (ደረጃ 4 ላይ በዝርዝር እንሰራዋለን) ---
    # ለጊዜው ባዶ ዝርዝር እናስቀምጥ

    # --- Bottom Menu ---
    footer = [
        [
            InlineKeyboardButton(text="🛍 Order Now", callback_data="action_order"),
            InlineKeyboardButton(text="➕ More", callback_data="nav_more"),
        ]
    ]

    for row in footer:
        keyboard.append(row)

    return header_text, InlineKeyboardMarkup(inline_keyboard=keyboard)


@dp.callback_query(F.data.startswith("tab_"))
async def handle_navigation(callback: types.CallbackQuery):
    # የታቡን አይነት መለየት (All, Male, Female, Search)
    tab_type = callback.data.split("_")[1].capitalize()

    # አዲሱን የ UI ይዘት ማዘጋጀት
    text, markup = get_main_interface(callback.from_user.id, filter_type=tab_type)

    # --- Window Cleaning (Edit current message) ---
    try:
        await callback.message.edit_text(text=text, reply_markup=markup)
    except Exception:
        # ኤዲት ማድረግ ካልተቻለ (ለምሳሌ ፎቶ ካለው) አጥፍቶ አዲስ ይልካል
        await callback.message.delete()
        await callback.message.answer(text=text, reply_markup=markup)

    await callback.answer()  # የቴሌግራም Loading ምልክት እንዲጠፋ

    # --- ጊዜያዊ የመረጣ ዝርዝር (ለእያንዳንዱ ተጠቃሚ) ---


# {user_id: [selected_target_ids]}
user_selections = {}


# --- የአባላት ዝርዝርን ከነ Checkbox የሚያመጣ ፈንክሽን ---
def get_user_list_markup(viewer_id, filter_type="All"):
    conn = sqlite3.connect("love_bot.db")
    cursor = conn.cursor()

    # ይህንን init_db ፈንክሽን ውስጥ ጨምረው
    cursor.execute(
        """CREATE TABLE IF NOT EXISTS messages (
        msg_id INTEGER PRIMARY KEY AUTOINCREMENT,
        order_id INTEGER,
        sender_id INTEGER,
        receiver_id INTEGER,
        content TEXT,
        msg_type TEXT, -- 'text', 'photo', 'video'
        is_deleted INTEGER DEFAULT 0,
        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )"""
    )

    cursor.execute(
        "SELECT user_id, name FROM users WHERE is_hidden = 0 AND user_id != ?",
        (viewer_id,),
    )
    try:
        cursor.execute("ALTER TABLE users ADD COLUMN is_boosted INTEGER DEFAULT 0")
        cursor.execute("ALTER TABLE users ADD COLUMN boost_expire TIMESTAMP NULL")
    except:
        pass

    # 1. ዳታቤዝ ውስጥ ያሉ ሰዎችን ማጣራት (Filter)
    if filter_type == "Male":
        cursor.execute(
            "SELECT user_id, name FROM users WHERE gender='Male' AND user_id != ?",
            (viewer_id,),
        )
    elif filter_type == "Female":
        cursor.execute(
            "SELECT user_id, name FROM users WHERE gender='Female' AND user_id != ?",
            (viewer_id,),
        )
    else:
        cursor.execute(
            "SELECT user_id, name FROM users WHERE user_id != ?", (viewer_id,)
        )

    all_users = cursor.fetchall()
    conn.close()

    # የላይኛው Header እና Tabs (ደረጃ 2 ላይ የሰራነው)
    # (እዚህ ጋር ቀድሞ የነበረውን get_main_interface ኮድ እናስታውሳለን)

    keyboard = []

    # Tabs Row (ሁልጊዜ ከላይ)
    tabs = [
        InlineKeyboardButton(text="🔍 Search", callback_data="tab_search"),
        InlineKeyboardButton(text="👥 All", callback_data="tab_all"),
        InlineKeyboardButton(text="👨 Male", callback_data="tab_male"),
        InlineKeyboardButton(text="👩 Female", callback_data="tab_female"),
    ]
    keyboard.append(tabs)

    # 2. የአባላት ዝርዝር ግንባታ (⬜ Name | Profile)
    selected_list = user_selections.get(viewer_id, [])

    for user in all_users:
        u_id, u_name = user
        # ሳጥኑ ተመርጦ ከሆነ ✅ ካልሆነ ⬜ ለማድረግ
        checkbox = "✅" if str(u_id) in selected_list else "⬜"

        row = [
            InlineKeyboardButton(
                text=f"{checkbox} {u_name}",
                callback_data=f"toggle_{u_id}_{filter_type}",
            ),
            InlineKeyboardButton(text="👤 Profile", callback_data=f"view_prof_{u_id}"),
        ]
        keyboard.append(row)

    # 3. የታችኛው Order እና More በተኖች
    order_count = len(selected_list)
    footer = [
        [
            InlineKeyboardButton(
                text=f"🛍 Order ({order_count}/10)", callback_data="act_order"
            ),
            InlineKeyboardButton(text="➕ More", callback_data="nav_more"),
        ]
    ]
    for f_row in footer:
        keyboard.append(f_row)

    return InlineKeyboardMarkup(inline_keyboard=keyboard)


# --- Checkbox ሲነካ የሚሰራ Logic (Toggle ✅/⬜) ---
@dp.callback_query(F.data.startswith("toggle_"))
async def handle_checkbox(callback: types.CallbackQuery):
    data = callback.data.split("_")
    target_id = data[1]
    current_filter = data[2]
    viewer_id = callback.from_user.id

    if viewer_id not in user_selections:
        user_selections[viewer_id] = []

    # መምረጥ ወይም አለመምረጥ (Toggle)
    if target_id in user_selections[viewer_id]:
        user_selections[viewer_id].remove(target_id)
    else:
        if len(user_selections[viewer_id]) < 10:
            user_selections[viewer_id].append(target_id)
        else:
            await callback.answer("ከ10 ሰው በላይ መምረጥ አይቻልም!", show_alert=True)
            return

    # ገጹን አድሶ ማሳየት (Window Refresh)
    new_markup = get_user_list_markup(viewer_id, filter_type=current_filter)
    await callback.message.edit_reply_markup(reply_markup=new_markup)
    await callback.answer()


@dp.callback_query(F.data == "act_order")
async def process_order_action(callback: types.CallbackQuery):
    sender_id = callback.from_user.id
    # የተመረጡ ሰዎችን ዝርዝር ማግኘት
    selected_targets = user_selections.get(sender_id, [])

    if not selected_targets:
        await callback.answer("⚠️ እባክዎ መጀመሪያ ቢያንስ አንድ ሰው ይምረጡ!", show_alert=True)
        return

    conn = sqlite3.connect("love_bot.db")
    cursor = conn.cursor()

    for target_id in selected_targets:
        # 1. ዳታቤዝ ላይ መመዝገብ
        cursor.execute(
            "INSERT INTO orders (sender_id, receiver_id) VALUES (?, ?)",
            (sender_id, int(target_id)),
        )

        # 2. ለተቀባዩ (Receiver) ማሳወቂያ መላክ
        try:
            notification_text = (
                "❤️ **አዲስ የፍቅር ጥያቄ ደርሶዎታል!**\n\n"
                "አንድ ተጠቃሚ ትኩረት ሰጥቶዎታል:: ዝርዝሩን በ 'More -> Inbox' ውስጥ ይመልከቱ::"
            )
            # ተቀባዩ ጋር የሚሄድ 'View' በተን
            notif_kb = InlineKeyboardMarkup(
                inline_keyboard=[
                    [InlineKeyboardButton(text="📩 ጥያቄውን እይ", callback_data="nav_more")]
                ]
            )
            await bot.send_message(
                target_id,
                notification_text,
                reply_markup=notif_kb,
                parse_mode="Markdown",
            )
        except Exception:
            # ተጠቃሚው ቦቱን Block ካደረገው ስህተቱን ለማለፍ
            pass

    conn.commit()
    conn.close()

    # 3. ለላኪው (Sender) ማሳወቂያ መስጠት
    count = len(selected_targets)
    await callback.answer(f"✅ ትዕዛዝዎ ለ {count} ሰዎች በተሳካ ሁኔታ ተልኳል!", show_alert=True)

    # 4. የመረጣቸውን ዝርዝር ማጽዳት (Reset Selection)
    user_selections[sender_id] = []

    # 5. ገጹን አድሶ ባዶ ማድረግ (Window Refresh)
    text, markup = get_user_list_markup(sender_id, filter_type="All")  # ደረጃ 3 ላይ የሰራነው
    await callback.message.edit_text(text=text, reply_markup=markup)


# --- የፍለጋ ስቴት (State) ---
class SearchState(StatesGroup):
    waiting_for_query = State()


@dp.callback_query(F.data == "tab_search")
async def start_search(callback: types.CallbackQuery, state: FSMContext):
    await state.set_state(SearchState.waiting_for_query)
    await callback.message.edit_text("🔍 መፈለግ የሚፈልጉትን ስም ወይም ቁልፍ ቃል ያስገቡ፡")
    await callback.answer()


@dp.message(SearchState.waiting_for_query)
async def process_search(message: types.Message, state: FSMContext):
    query = message.text
    # እዚህ ጋር get_user_list_markupን በመጥራት በፍለጋ ውጤት እናሳያለን
    # (ዳታቤዝ ውስጥ LIKE %query% በመጠቀም)
    await state.clear()
    # ውጤቱን ማሳየት...


@dp.callback_query(F.data.startswith("view_prof_"))
async def show_full_profile(callback: types.CallbackQuery):
    target_id = callback.data.split("_")[2]

    conn = sqlite3.connect("love_bot.db")
    cursor = conn.cursor()
    cursor.execute(
        "SELECT name, gender, photos, bio FROM users WHERE user_id = ?", (target_id,)
    )
    user_data = cursor.fetchone()
    conn.close()

    if not user_data:
        await callback.answer("ይህ ተጠቃሚ አልተገኘም!", show_alert=True)
        return

    name, gender, photos_str, bio = user_data
    photos = photos_str.split(",")  # ፎቶዎቹን ወደ ዝርዝር መቀየር

    # የፕሮፋይል መረጃ ጽሁፍ
    profile_text = (
        f"👤 **ስም፡** {name}\n"
        f"🚻 **ጾታ፡** {gender}\n"
        f"📝 **ስለ እኔ፡** {bio if bio else 'ያልተገለጸ'}\n"
        f"━━━━━━━━━━━━━━"
    )

    # የፕሮፋይል ገጽ በተኖች
    profile_kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="❤️ ምረጥ (Select)", callback_data=f"toggle_{target_id}_All"
                )
            ],
            [InlineKeyboardButton(text="⬅️ ተመለስ (Back)", callback_data="tab_all")],
        ]
    )

    # Window Cleaning: የቆየውን አጥፍቶ በፎቶ መተካት
    await callback.message.delete()

    # መጀመሪያ ያለውን ፎቶ እንደ ዋና ማሳያ እንጠቀማለን
    if photos:
        await callback.message.answer_photo(
            photo=photos[0],
            caption=profile_text,
            reply_markup=profile_kb,
            parse_mode="Markdown",
        )
    else:
        await callback.message.answer(text=profile_text, reply_markup=profile_kb)

    await callback.answer()


class MoreMenuState(StatesGroup):
    waiting_for_password = State()
    in_more_menu = State()


@dp.callback_query(F.data == "nav_more")
async def ask_password(callback: types.CallbackQuery, state: FSMContext):
    await state.set_state(MoreMenuState.waiting_for_password)
    await callback.message.edit_text(
        "🔒 ይህ ክፍል በፓስወርድ የተቆለፈ ነው::\nእባክዎ ሚስጥር ቁጥርዎን ያስገቡ፦"
    )
    await callback.answer()


@dp.message(MoreMenuState.waiting_for_password)
async def check_password(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    conn = sqlite3.connect("love_bot.db")
    cursor = conn.cursor()
    cursor.execute("SELECT password FROM users WHERE user_id = ?", (user_id,))
    db_password = cursor.fetchone()[0]
    conn.close()

    if message.text == db_password:
        # Window Cleaning: ፓስወርዱን አጥፍቶ ሜኑውን ማሳየት
        await message.delete()
        await state.set_state(MoreMenuState.in_more_menu)
        await show_more_icons(message)
    else:
        await message.answer("❌ የተሳሳተ ፓስወርድ ነው! እባክዎ ድጋሚ ይሞክሩ ወይም ለትዝታ /start ይበሉ::")


async def show_more_icons(message: types.Message):
    # 7 አይኮኖች በ Grid አቀማመጥ
    more_kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="💬 Chat Hist", callback_data="toggle_chat"),
                InlineKeyboardButton(text="🔒 Prof Hide", callback_data="toggle_prof"),
            ],
            [
                InlineKeyboardButton(text="⚙️ Settings", callback_data="nav_settings"),
                InlineKeyboardButton(text="📩 Inbox (Love)", callback_data="nav_inbox"),
            ],
            [
                InlineKeyboardButton(
                    text="📤 Outbox (His)", callback_data="nav_outbox"
                ),
                InlineKeyboardButton(text="🤝 Match Chat", callback_data="nav_match"),
            ],
            [InlineKeyboardButton(text="🏠 ወደ ዋናው ገጽ", callback_data="tab_all")],
        ]
    )

    header = "➕ **ተጨማሪ ተግባራት (More Menu)**\nየግል መረጃዎን እና ታሪክዎን እዚህ ያስተዳድሩ::"

    # አሮጌውን መልዕክት አጥፍቶ አዲሱን ሜኑ መላክ
    await message.answer(header, reply_markup=more_kb, parse_mode="Markdown")


@dp.callback_query(F.data == "toggle_prof")
async def toggle_profile_visibility(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    conn = sqlite3.connect("love_bot.db")
    cursor = conn.cursor()

    # 1. አሁን ያለውን የሁኔታ መረጃ (Status) ማምጣት
    cursor.execute("SELECT is_hidden FROM users WHERE user_id = ?", (user_id,))
    current_status = cursor.fetchone()[0]

    # 2. ሁኔታውን መገልበጥ (0 ከሆነ 1፣ 1 ከሆነ 0 ማድረግ)
    new_status = 1 if current_status == 0 else 0
    cursor.execute(
        "UPDATE users SET is_hidden = ? WHERE user_id = ?", (new_status, user_id)
    )
    conn.commit()
    conn.close()

    # 3. ለተጠቃሚው አዲሱን ሁኔታ ማሳወቅ
    status_text = "🙈 ተደብቋል (Hidden)" if new_status == 1 else "👀 ይታያል (Visible)"
    await callback.answer(f"ፕሮፋይልዎ አሁን {status_text} ነው።", show_alert=True)

    # 4. የ More Menu ዊንዶው ላይ ያለውን በተን ስም መቀየር (Window Refresh)
    await refresh_more_menu(callback.message, new_status)


# የ More Menu በተኖችን ለማደስ (Icon Change)
async def refresh_more_menu(message: types.Message, is_hidden):
    toggle_icon = "👁 Show Profile" if is_hidden == 1 else "🔒 Hide Profile"

    more_kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="💬 Chat Hist", callback_data="toggle_chat"),
                InlineKeyboardButton(text=toggle_icon, callback_data="toggle_prof"),
            ],
            # ... ሌሎቹ 7 አይኮኖች እዚህ ይቀጥላሉ ...
            [InlineKeyboardButton(text="🏠 ወደ ዋናው ገጽ", callback_data="tab_all")],
        ]
    )

    await message.edit_reply_markup(reply_markup=more_kb)


@dp.callback_query(F.data == "nav_inbox")
async def show_inbox(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    conn = sqlite3.connect("love_bot.db")
    cursor = conn.cursor()

    # 1. 'Pending' የሆኑ የፍቅር ጥያቄዎችን ከነ ላኪው ስም ማምጣት
    cursor.execute(
        """
        SELECT orders.order_id, users.name, users.user_id 
        FROM orders 
        JOIN users ON orders.sender_id = users.user_id 
        WHERE orders.receiver_id = ? AND orders.status = 'pending'
        ORDER BY orders.order_date DESC
    """,
        (user_id,),
    )

    requests = cursor.fetchall()
    conn.close()

    if not requests:
        await callback.answer("📩 ኢንቦክስዎ ባዶ ነው!", show_alert=True)
        return

    # የመጀመሪያውን ጥያቄ እናሳያለን (Window Cleaning)
    order_id, sender_name, sender_id = requests[0]

    inbox_text = f"📩 **አዲስ የፍቅር ጥያቄ!**\n\nከ፡ {sender_name}\nሁኔታ፡ ምላሽ እየጠበቀ ነው..."

    inbox_kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✅ ተቀበል (Accept)", callback_data=f"acc_{order_id}_{sender_id}"
                ),
                InlineKeyboardButton(
                    text="❌ ሰርዝ (Reject)", callback_data=f"rej_{order_id}"
                ),
            ],
            [
                InlineKeyboardButton(
                    text="👤 ፕሮፋይሉን እይ", callback_data=f"view_prof_{sender_id}"
                )
            ],
            [InlineKeyboardButton(text="🏠 ተመለስ", callback_data="nav_more")],
        ]
    )

    await callback.message.edit_text(
        text=inbox_text, reply_markup=inbox_kb, parse_mode="Markdown"
    )


@dp.callback_query(F.data.startswith(("acc_", "rej_")))
async def handle_inbox_action(callback: types.CallbackQuery):
    action_data = callback.data.split("_")
    action = action_data[0]
    order_id = action_data[1]

    conn = sqlite3.connect("love_bot.db")
    cursor = conn.cursor()

    if action == "acc":
        sender_id = action_data[2]
        # 1. ሁኔታውን ወደ Accepted መቀየር
        cursor.execute(
            "UPDATE orders SET status = 'accepted' WHERE order_id = ?", (order_id,)
        )
        # 2. ለላኪው (Sender) ማሳወቂያ መላክ
        try:
            await bot.send_message(
                sender_id,
                "🎉 ደስ የሚል ዜና! የላኩት የፍቅር ጥያቄ ተቀባይነት አግኝቷል። አሁን በ 'Match Chat' ማውራት ትችላላችሁ!",
            )
        except:
            pass
        await callback.answer("ጥያቄውን ተቀብለዋል! ❤️", show_alert=True)

    else:  # Reject
        cursor.execute("DELETE FROM orders WHERE order_id = ?", (order_id,))
        await callback.answer("ጥያቄው ተሰርዟል።", show_alert=True)

    conn.commit()
    conn.close()

    # ወደ ኢንቦክስ ተመለስ (ሌላ ጥያቄ ካለ ለማየት)
    await show_inbox(callback)


@dp.callback_query(F.data == "nav_outbox")
async def show_outbox(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    conn = sqlite3.connect("love_bot.db")
    cursor = conn.cursor()

    # 1. የላኳቸውን ጥያቄዎች ብዛት በየአይነቱ መቆጠር (Stats)
    cursor.execute(
        "SELECT status, COUNT(*) FROM orders WHERE sender_id = ? GROUP BY status",
        (user_id,),
    )
    stats_data = dict(cursor.fetchall())

    sent_total = sum(stats_data.values())
    accepted = stats_data.get("accepted", 0)
    pending = stats_data.get("pending", 0)

    # 2. የላኳቸውን ሰዎች ዝርዝር ማምጣት
    cursor.execute(
        """
        SELECT orders.order_id, users.name, orders.status 
        FROM orders 
        JOIN users ON orders.receiver_id = users.user_id 
        WHERE orders.sender_id = ? 
        ORDER BY orders.order_date DESC LIMIT 5
    """,
        (user_id,),
    )

    sent_requests = cursor.fetchall()
    conn.close()

    # 3. የስታቲስቲክስ ጽሁፍ ማዘጋጀት
    outbox_text = (
        f"📤 **የላኳቸው ጥያቄዎች (Outbox)**\n\n"
        f"📊 **አጠቃላይ ስታቲስቲክስ፦**\n"
        f"• የላኳቸው በድምሩ፡ {sent_total}\n"
        f"• ተቀባይነት ያገኙ፡ {accepted}\n"
        f"• ምላሽ የሚጠባበቁ፡ {pending}\n"
        f"━━━━━━━━━━━━━━\n"
        f"የቅርብ ጊዜ እንቅስቃሴዎች፦"
    )

    keyboard = []
    for order_id, name, status in sent_requests:
        status_icon = "⏳" if status == "pending" else "❤️"
        # ገና ምላሽ ካላገኙ መሰረዝ (Delete for Everyone) ይቻላል
        btn_text = f"{status_icon} {name} ({status})"
        keyboard.append(
            [InlineKeyboardButton(text=btn_text, callback_data=f"out_view_{order_id}")]
        )

        if status == "pending":
            keyboard.append(
                [
                    InlineKeyboardButton(
                        text=f"🗑 ጥያቄውን ሰርዝ (Delete)",
                        callback_data=f"del_order_{order_id}",
                    )
                ]
            )

    keyboard.append([InlineKeyboardButton(text="🏠 ተመለስ", callback_data="nav_more")])

    await callback.message.edit_text(
        text=outbox_text,
        reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard),
        parse_mode="Markdown",
    )


@dp.callback_query(F.data.startswith("del_order_"))
async def delete_sent_order(callback: types.CallbackQuery):
    order_id = callback.data.split("_")[2]

    conn = sqlite3.connect("love_bot.db")
    cursor = conn.cursor()
    # ጥያቄውን ከዳታቤዝ ማጥፋት (Delete for everyone)
    cursor.execute("DELETE FROM orders WHERE order_id = ?", (order_id,))
    conn.commit()
    conn.close()

    await callback.answer("ጥያቄው ለሁለቱም ወገን ተሰርዟል! 🗑", show_alert=True)
    # ገጹን አድሶ ማሳየት
    await show_outbox(callback)


@dp.callback_query(F.data.startswith("chat_with_"))
async def open_match_chat(callback: types.CallbackQuery, state: FSMContext):
    target_id = callback.data.split("_")[2]
    viewer_id = callback.from_user.id

    # የቆዩ መልዕክቶችን ከዳታቤዝ ማምጣት
    conn = sqlite3.connect("love_bot.db")
    cursor = conn.cursor()
    cursor.execute(
        """SELECT sender_id, content, msg_id FROM messages 
                      WHERE (sender_id = ? AND receiver_id = ?) 
                      OR (sender_id = ? AND receiver_id = ?) 
                      AND is_deleted = 0 ORDER BY timestamp ASC""",
        (viewer_id, target_id, target_id, viewer_id),
    )
    chat_history = cursor.fetchall()
    conn.close()

    chat_text = "━━━━━━━━━━━━━━\n🤝 **የግል የንግግር መስኮት**\n━━━━━━━━━━━━━━\n"
    keyboard = []

    for s_id, content, m_id in chat_history:
        side = "➡️ የእርስዎ" if s_id == viewer_id else "⬅️ የእሱ/የሷ"
        chat_text += f"{side}፡ {content}\n"
        # እያንዳንዱ መልዕክት ስር "Delete" በተን መጨመር (ለሁለቱም ወገን)
        if s_id == viewer_id:
            keyboard.append(
                [
                    InlineKeyboardButton(
                        text=f"🗑 አጥፋ፡ {content[:10]}...",
                        callback_data=f"drop_{m_id}_{target_id}",
                    )
                ]
            )

    keyboard.append([InlineKeyboardButton(text="🏠 ተመለስ", callback_data="nav_more")])

    await callback.message.edit_text(
        text=chat_text, reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard)
    )


# 8.5 seting
@dp.callback_query(F.data == "nav_settings")
async def show_settings(callback: types.CallbackQuery):
    settings_text = (
        "⚙️ **የግል መረጃ ማስተካከያ (Settings)**\n\n" "ለመቀየር የሚፈልጉትን መረጃ ከታች ካሉት በተኖች ይምረጡ፦"
    )

    settings_kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="📝 ስም ለመቀየር (Change Name)", callback_data="set_name"
                )
            ],
            [
                InlineKeyboardButton(
                    text="🚻 ጾታ ለመቀየር (Change Gender)", callback_data="set_gender"
                )
            ],
            [
                InlineKeyboardButton(
                    text="🖼 ፎቶ ለመቀየር (Change Photos)", callback_data="set_photos"
                )
            ],
            [
                InlineKeyboardButton(
                    text="🔐 ፓስወርድ ለመቀየር (Change Password)", callback_data="set_pass"
                )
            ],
            [InlineKeyboardButton(text="✍️ ስለ እኔ (Edit Bio)", callback_data="set_bio")],
            [InlineKeyboardButton(text="🏠 ተመለስ", callback_data="nav_more")],
        ]
    )

    await callback.message.edit_text(
        text=settings_text, reply_markup=settings_kb, parse_mode="Markdown"
    )


class SettingsState(StatesGroup):
    waiting_for_new_name = State()
    waiting_for_new_pass = State()
    waiting_for_new_bio = State()


# ፓስወርድ ለመቀየር ሲነካ
@dp.callback_query(F.data == "set_pass")
async def change_password_start(callback: types.CallbackQuery, state: FSMContext):
    await state.set_state(SettingsState.waiting_for_new_pass)
    await callback.message.edit_text("🔐 አዲሱን 6 ዲጂት ፓስወርድ ያስገቡ፦")
    await callback.answer()


# አዲሱን ፓስወርድ ተቀብሎ ዳታቤዝ ላይ መመዝገብ
@dp.message(SettingsState.waiting_for_new_pass)
async def process_new_pass(message: types.Message, state: FSMContext):
    new_pass = message.text

    if len(new_pass) < 4:
        await message.answer("❌ ፓስወርድ በጣም አጭር ነው! እባክዎ ድጋሚ ይሞክሩ።")
        return

    user_id = message.from_user.id
    conn = sqlite3.connect("love_bot.db")
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE users SET password = ? WHERE user_id = ?", (new_pass, user_id)
    )
    conn.commit()
    conn.close()

    await state.clear()
    # Window Cleaning: ሜሴጁን አጥፍቶ ወደ ሴቲንግ መመለስ
    await message.delete()
    await message.answer("✅ ፓስወርድዎ በተሳካ ሁኔታ ተቀይሯል!")
    # ተመልሶ የሴቲንግ ማውጫውን እንዲያይ ማድረግ
    await show_settings_from_msg(message)


# wede back


@dp.callback_query(F.data == "tab_all")
async def back_to_home(callback: types.CallbackQuery, state: FSMContext):
    # 1. ማንኛውንም ክፍት የሆነ ስቴት (State) ማጽዳት (ለምሳሌ ፓስወርድ እየጠየቀ ከሆነ)
    await state.clear()

    user_id = callback.from_user.id
    user_name = callback.from_user.first_name

    # 2. ንጹህ የዋና ገጽ UI ማዘጋጀት (ደረጃ 2 እና 3 ላይ የሰራነው ፈንክሽን)
    # ማሳሰቢያ፡ እዚህ ጋር get_user_list_markupን እንጠራዋለን
    text, markup = get_main_interface_with_users(user_id, filter_type="All")

    # 3. Window Cleaning: የ More Menu ገጽን በዋናው ገጽ መተካት
    try:
        await callback.message.edit_text(
            text=text, reply_markup=markup, parse_mode="Markdown"
        )
    except:
        # ፎቶ ካለው ኤዲት ስለማይደረግ አጥፍቶ አዲስ መላክ
        await callback.message.delete()
        await callback.message.answer(
            text=text, reply_markup=markup, parse_mode="Markdown"
        )

    await callback.answer("ወደ ዋናው ገጽ ተመልሰዋል! 🏠")


# ============admin=============
# --- ዳታቤዝ ውስጥ ያሉ ተጠቃሚዎችን በጾታ ለይቶ መቁጠሪያ (SQL Logic) ---
def get_user_stats():
    conn = sqlite3.connect("love_bot.db")
    cursor = conn.cursor()

    # በአንድ የ SQL ጥያቄ (Query) ሁሉንም መረጃ እናመጣለን (Scalable approach)
    cursor.execute(
        """
        SELECT 
            COUNT(*) as total,
            SUM(CASE WHEN gender = 'Male' THEN 1 ELSE 0 END) as males,
            SUM(CASE WHEN gender = 'Female' THEN 1 ELSE 0 END) as females
        FROM users
    """
    )

    result = cursor.fetchone()
    conn.close()

    # መረጃው ባዶ ከሆነ 0 እንዲመልስ
    total = result[0] if result[0] else 0
    males = result[1] if result[1] else 0
    females = result[2] if result[2] else 0

    return total, males, females


# --- የአድሚን ዳሽቦርድ ማሳያ (UI Logic) ---
@dp.callback_query(F.data == "adm_dash")
async def show_admin_dashboard(callback: types.CallbackQuery):
    # 1. መረጃውን ከዳታቤዝ ማምጣት
    total, males, females = get_user_stats()

    # 2. ፕሮፌሽናል የሆነ የአቀራረብ ጽሁፍ
    dashboard_text = (
        "🎆 **የአስተዳዳሪ ዳሽቦርድ (Dashboard)**\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        "👥 **የተጠቃሚዎች ስታቲስቲክስ፦**\n"
        f"• **ጠቅላላ ተጠቃሚዎች (Total):** `{total}`\n"
        f"• **ወንዶች (Male):** `{males}`\n"
        f"• **ሴቶች (Female):** `{females}`\n\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "ምን ማድረግ ይፈልጋሉ?"
    )

    # 3. የአናሊቲክስ ማጣሪያዎች (Analytics Filters)
    dash_kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="📅 Daily", callback_data="filt_daily"),
                InlineKeyboardButton(text="📅 Weekly", callback_data="filt_weekly"),
                InlineKeyboardButton(text="📅 Monthly", callback_data="filt_monthly"),
            ],
            [InlineKeyboardButton(text="⬅️ ወደ አድሚን ሜኑ", callback_data="nav_admin_main")],
        ]
    )

    # Window Cleaning: ያለውን የአድሚን ሜኑ በዳሽቦርድ መተካት
    await callback.message.edit_text(
        text=dashboard_text, reply_markup=dash_kb, parse_mode="Markdown"
    )
    await callback.answer()


# --- 9.1.2. Active Users የመቁጠሪያ ፈንክሽን ---
def get_active_users_stats():
    conn = sqlite3.connect("love_bot.db")
    cursor = conn.cursor()

    # 1. Daily (ባለፉት 24 ሰዓት)
    cursor.execute(
        "SELECT COUNT(*) FROM users WHERE last_seen >= datetime('now', '-1 day')"
    )
    daily = cursor.fetchone()[0]

    # 2. Weekly (ባለፉት 7 ቀናት)
    cursor.execute(
        "SELECT COUNT(*) FROM users WHERE last_seen >= datetime('now', '-7 days')"
    )
    weekly = cursor.fetchone()[0]

    # 3. Monthly (ባለፉት 30 ቀናት)
    cursor.execute(
        "SELECT COUNT(*) FROM users WHERE last_seen >= datetime('now', '-30 days')"
    )
    monthly = cursor.fetchone()[0]

    conn.close()
    return daily, weekly, monthly


# --- የአድሚን አክቲቭ ተጠቃሚዎች ማሳያ (UI) ---
@dp.callback_query(F.data == "filt_daily")  # ወይም "filt_weekly", "filt_monthly"
async def show_active_stats(callback: types.CallbackQuery):
    daily, weekly, monthly = get_active_users_stats()

    active_text = (
        "📈 **የአክቲቭ ተጠቃሚዎች ዝርዝር (Active Users)**\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        f"📅 **ዛሬ (Daily):** `{daily}` ተጠቃሚዎች\n"
        f"📅 **በዚህ ሳምንት (Weekly):** `{weekly}` ተጠቃሚዎች\n"
        f"📅 **በዚህ ወር (Monthly):** `{monthly}` ተጠቃሚዎች\n\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "ይህ ቁጥር ባለፉት ቀናት ቦቱን የተጠቀሙ ሰዎችን ብቻ ያሳያል።"
    )

    back_kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="⬅️ ተመለስ", callback_data="adm_dash")]
        ]
    )

    await callback.message.edit_text(
        text=active_text, reply_markup=back_kb, parse_mode="Markdown"
    )
    await callback.answer()


# ====9.1.3===


def get_order_analytics():
    conn = sqlite3.connect("love_bot.db")
    cursor = conn.cursor()

    # 9.1.3 & 9.1.4 በአንድ ጥያቄ ሁሉንም ሁኔታዎች መቁጠር
    cursor.execute(
        """
        SELECT 
            COUNT(*) as total_sent,
            SUM(CASE WHEN status = 'accepted' THEN 1 ELSE 0 END) as accepted,
            SUM(CASE WHEN status = 'pending' THEN 1 ELSE 0 END) as pending,
            SUM(CASE WHEN status = 'rejected' THEN 1 ELSE 0 END) as rejected
        FROM orders
    """
    )

    result = cursor.fetchone()
    conn.close()

    # መረጃው ባዶ ከሆነ 0 እንዲመልስ (Scalable handling)
    return result if result[0] is not None else (0, 0, 0, 0)


@dp.callback_query(F.data == "adm_order_stats")
async def show_order_analytics(callback: types.CallbackQuery):
    total, accepted, pending, rejected = get_order_analytics()

    stats_text = (
        "📊 **የጥያቄዎች እና የግንኙነት ሁኔታ (Order Stats)**\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        f"📩 **ጠቅላላ የተላኩ ጥያቄዎች:** `{total}`\n"
        f"❤️ **የተሳኩ ግንኙነቶች (Matches):** `{accepted}`\n"
        f"⏳ **ምላሽ የሚጠባበቁ:** `{pending}`\n"
        f"❌ **ውድቅ የተደረጉ:** `{rejected}`\n\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "የግንኙነት ስኬት ፍጥነት (Success Rate): "
        f"`{round((accepted/total)*100, 1) if total > 0 else 0}%`"
    )

    back_kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="⬅️ ወደ ዳሽቦርድ ተመለስ", callback_data="adm_dash")]
        ]
    )

    await callback.message.edit_text(
        text=stats_text, reply_markup=back_kb, parse_mode="Markdown"
    )
    await callback.answer()

    # ======9.4====


@dp.callback_query(F.data == "adm_bc")
async def start_broadcast(callback: types.CallbackQuery, state: FSMContext):
    await state.set_state(AdminStates.waiting_for_broadcast)
    await callback.message.edit_text(
        "📢 **የማስታወቂያ መልዕክት መላኪያ**\n\nለሁሉም ተጠቃሚዎች እንዲደርስ የሚፈልጉትን ጽሁፍ አሁን ይላኩ፦\n(ለመሰረዝ /cancel ይበሉ)"
    )
    await callback.answer()


@dp.message(AdminStates.waiting_for_broadcast)
async def process_broadcast(message: types.Message, state: FSMContext):
    broadcast_text = message.text

    conn = sqlite3.connect("love_bot.db")
    cursor = conn.cursor()
    cursor.execute("SELECT user_id FROM users")
    users = cursor.fetchall()
    conn.close()

    success_count = 0
    fail_count = 0

    # ጊዜያዊ መልዕክት ለአስተዳዳሪው
    status_msg = await message.answer(f"⏳ መላክ ተጀምሯል... (ለ {len(users)} ተጠቃሚዎች)")

    for user in users:
        try:
            # ለእያንዳንዱ ተጠቃሚ መላክ
            await bot.send_message(
                user[0], f"📢 **ከአስተዳዳሪው የተላከ መልዕክት፦**\n\n{broadcast_text}"
            )
            success_count += 1
        except Exception:
            # ተጠቃሚው ቦቱን Block ካደረገ ወይም አካውንቱን ካጠፋ
            fail_count += 1

    await state.clear()

    final_report = (
        "✅ **ብሮድካስት ተጠናቋል!**\n\n"
        f"✔️ በተሳካ ሁኔታ የደረሳቸው፡ `{success_count}`\n"
        f"✖️ ያልደረሳቸው (Blocked)፡ `{fail_count}`"
    )
    await status_msg.edit_text(final_report, parse_mode="Markdown")


# --- 9.5 Ban User Logic ---
@dp.callback_query(F.data == "adm_ban")
async def start_ban_user(callback: types.CallbackQuery, state: FSMContext):
    await state.set_state(AdminStates.waiting_for_ban_id)
    await callback.message.edit_text(
        "🚫 **ተጠቃሚን ማገጃ (Ban)**\n\nማገድ የሚፈልጉትን የተጠቃሚ ID ቁጥር ያስገቡ፦\n(ለመሰረዝ /cancel ይበሉ)"
    )
    await callback.answer()


@dp.message(AdminStates.waiting_for_ban_id)
async def process_ban(message: types.Message, state: FSMContext):
    target_id = message.text

    if not target_id.isdigit():
        await message.answer("❌ እባክዎ ትክክለኛ የቁጥር ID ያስገቡ!")
        return

    conn = sqlite3.connect("love_bot.db")
    cursor = conn.cursor()
    # ተጠቃሚውን ከዳታቤዝ ማጥፋት (ወይም is_banned የሚል ኮለምን መጠቀም ይቻላል)
    cursor.execute("DELETE FROM users WHERE user_id = ?", (target_id,))
    conn.commit()
    conn.close()

    await state.clear()
    await message.answer(f"✅ ተጠቃሚ `{target_id}` በተሳካ ሁኔታ ታግዷል (ከዳታቤዝ ተሰርዟል)።")


# --- 9.6 Reset Password Logic ---
@dp.callback_query(F.data == "adm_reset")
async def start_reset_pass(callback: types.CallbackQuery, state: FSMContext):
    await state.set_state(AdminStates.waiting_for_reset_id)
    await callback.message.edit_text(
        "🔄 **ፓስወርድ መቀየሪያ (Reset)**\n\nፓስወርዱ እንዲቀየር የሚፈልጉትን የተጠቃሚ ID ያስገቡ፦"
    )
    await callback.answer()


@dp.message(AdminStates.waiting_for_reset_id)
async def process_reset(message: types.Message, state: FSMContext):
    target_id = message.text
    default_pass = "123456"

    conn = sqlite3.connect("love_bot.db")
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE users SET password = ? WHERE user_id = ?", (default_pass, target_id)
    )
    conn.commit()
    conn.close()

    await state.clear()
    await message.answer(f"✅ የተጠቃሚ `{target_id}` ፓስወርድ ወደ `{default_pass}` ተቀይሯል።")

    # ለተጠቃሚው ማሳወቂያ መላክ
    try:
        await bot.send_message(
            target_id, f"🔐 ፓስወርድዎ በአስተዳዳሪው ታድሷል! አዲሱ ሚስጥር ቁጥርዎ፡ `{default_pass}` ነው።"
        )
    except:
        pass


# =====9.7 የአድሚን ቡስት እና የቫይራል ገጽታዎች==


class BoostState(StatesGroup):
    waiting_for_id = State()
    waiting_for_duration = State()


@dp.callback_query(F.data == "adm_boost")
async def start_boost_process(callback: types.CallbackQuery, state: FSMContext):
    await state.set_state(BoostState.waiting_for_id)
    await callback.message.edit_text("🧧 **Admin Boost**\n\nቡስት የሚደረገውን የተጠቃሚ ID ያስገቡ፦")
    await callback.answer()


@dp.message(BoostState.waiting_for_id)
async def process_boost_id(message: types.Message, state: FSMContext):
    await state.update_data(target_id=message.text)
    await state.set_state(BoostState.waiting_for_duration)

    # የጊዜ አማራጮች (9.7.4)
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="1 ቀን (Temporary)", callback_data="dur_1"),
                InlineKeyboardButton(text="7 ቀን (Weekly)", callback_data="dur_7"),
            ],
            [InlineKeyboardButton(text="♾️ ለዘላቂ (Permanent)", callback_data="dur_perm")],
        ]
    )
    await message.answer("⏱ የቡስት ቆይታን ይምረጡ፦", reply_markup=kb)


@dp.callback_query(BoostState.waiting_for_duration)
async def finalize_boost(callback: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    target_id = data["target_id"]
    duration = callback.data.split("_")[1]

    conn = sqlite3.connect("love_bot.db")
    cursor = conn.cursor()

    if duration == "perm":
        cursor.execute(
            "UPDATE users SET is_boosted = 1, boost_expire = NULL WHERE user_id = ?",
            (target_id,),
        )
    else:
        days = int(duration)
        cursor.execute(
            f"UPDATE users SET is_boosted = 1, boost_expire = datetime('now', '+{days} days') WHERE user_id = ?",
            (target_id,),
        )

    conn.commit()
    conn.close()
    await state.clear()

    # 9.7.5 Optional Notification
    try:
        await bot.send_message(
            target_id,
            "🌟 **ደስ የሚል ዜና!**\n\nፕሮፋይልዎ በአስተዳዳሪው **⭐ Featured** ተደርጓል:: አሁን ዝርዝር ላይ ከላይ ይታያሉ!",
        )
    except:
        pass

    await callback.message.edit_text(f"✅ ተጠቃሚ {target_id} ቡስት ተደርጓል!")


def get_boosted_user_list(filter_type="All", search_query=None):
    conn = sqlite3.connect("love_bot.db")
    cursor = conn.cursor()

    # ጊዜያቸው ያለፈባቸውን ቡስቶች በራስ-ሰር ማጽዳት (Automation)
    cursor.execute(
        "UPDATE users SET is_boosted = 0 WHERE boost_expire < CURRENT_TIMESTAMP"
    )

    query = "SELECT user_id, name, is_boosted FROM users WHERE is_hidden = 0 "
    params = []

    if filter_type != "All":
        query += " AND gender = ?"
        params.append(filter_type)

    if search_query:
        query += " AND name LIKE ?"
        params.append(f"%{search_query}%")

    # 9.7.1 & 9.7.3: መጀመሪያ ቡስት የሆኑት፣ ከዚያ በሪጂስትሬሽን ሰዓት
    query += " ORDER BY is_boosted DESC, reg_date DESC LIMIT 20"

    cursor.execute(query, params)
    users = cursor.fetchall()

    keyboard = []
    for u_id, name, is_boosted in users:
        # 9.7.2: Highlighted with badge
        prefix = "⭐ " if is_boosted == 1 else "⬜ "
        keyboard.append(
            [
                InlineKeyboardButton(
                    text=f"{prefix}{name}", callback_data=f"view_prof_{u_id}"
                )
            ]
        )

    return keyboard


async def main():
    # ቦቱ መስራት እንዲጀምር (Polling)
    await dp.start_polling(bot)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logging.info("Bot stopped!")
