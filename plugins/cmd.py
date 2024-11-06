# Import required libraries and modules
from bot import Bot
from pyrogram import filters
from config import *
from datetime import datetime
from plugins.start import *
from pyrogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from pyrogram.enums import ParseMode
import time

# Command to add a premium subscription for a user (admin only)
@Bot.on_message(filters.private & filters.command('addpr') & filters.user(ADMINS))
async def add_premium(bot: Bot, message: Message):
    if message.from_user.id not in ADMINS:
        return await message.reply("You don't have permission to add premium users.")

    try:
        args = message.text.split()
        if len(args) < 3:
            return await message.reply("Usage: /addpr 'user_id' 'duration_in_days'")
        
        target_user_id = int(args[1])
        duration_in_days = int(args[2])
        await add_premium_user(target_user_id, duration_in_days)
        await message.reply(f"User {target_user_id} added to premium for {duration_in_days} days.")
    except Exception as e:
        await message.reply(f"Error: {str(e)}")

# Command to remove a premium subscription for a user (admin only)
@Bot.on_message(filters.private & filters.command('removepr') & filters.user(ADMINS))
async def remove_premium(bot: Bot, message: Message):
    if message.from_user.id not in ADMINS:
        return await message.reply("You don't have permission to remove premium users.")

    try:
        args = message.text.split()
        if len(args) < 2:
            return await message.reply("Usage: /removepr 'user_id'")
        
        target_user_id = int(args[1])
        await remove_premium_user(target_user_id)
        await message.reply(f"User {target_user_id} removed from premium.")
    except Exception as e:
        await message.reply(f"Error: {str(e)}")

# Command for users to check their premium subscription status
@Bot.on_message(filters.command('myplan') & filters.private)
async def my_plan(bot: Bot, message: Message):
    is_premium, expiry_time = await get_user_subscription(message.from_user.id)
    time_left = int(expiry_time - time.time())
    
    if is_premium and time_left > 0:
        days, hours, minutes = time_left // 86400, (time_left % 86400) // 3600, (time_left % 3600) // 60
        response_text = (
            f"✅ Your premium subscription is active.\n\n"
            f"🕒 Time remaining: {days} days, {hours} hours, {minutes} minutes."
        )
        buttons = InlineKeyboardMarkup([
            [InlineKeyboardButton("Upgrade Plan", callback_data="show_plans")],
            [InlineKeyboardButton("Contact Support", url=f"https://t.me/{OWNER}")]
        ])
    elif is_premium and time_left <= 0:
        response_text = (
            "⚠️ Your premium subscription has expired.\n\n"
            "Renew your subscription to continue enjoying premium features. Check: /plans"
        )
        buttons = InlineKeyboardMarkup([
            [InlineKeyboardButton("Renew Plan", callback_data="show_plans")],
            [InlineKeyboardButton("Contact Support", url=f"https://t.me/{OWNER}")]
        ])
    else:
        response_text = "❌ You are not a premium user. View available plans to upgrade.\n\nClick HERE: /plans"
        buttons = InlineKeyboardMarkup([
            [InlineKeyboardButton("View Plans", callback_data="show_plans")],
            [InlineKeyboardButton("Contact Support", url=f"https://t.me/{OWNER}")]
        ])
    await message.reply_text(response_text, reply_markup=buttons)

# Command to show subscription plans
@Bot.on_message(filters.command('plans') & filters.private)
async def show_plans(bot: Bot, message: Message):
    plans_text = """
<b>Available Subscription Plans:</b>

1. 7 Days Premium  - 20₹
2. 15 Days Premium - 35₹
3. 30 Days Premium - 50₹
4. 90 Days Premium - 100₹

🎁 <b>Premium Features Included</b>

To subscribe, click the "Pay via UPI" button below.
"""
    buttons = InlineKeyboardMarkup([
        [InlineKeyboardButton("Pay via UPI", callback_data="upi_info")],
        [InlineKeyboardButton("Contact Support", url=f"https://t.me/{OWNER}")]
    ])
    await message.reply(plans_text, reply_markup=buttons, parse_mode=ParseMode.HTML)

# Command to show UPI payment QR code and instructions
@Bot.on_message(filters.command('upi') & filters.private)
async def upi_info(bot: Bot, message: Message):
    await bot.send_photo(
        chat_id=message.chat.id,
        photo=PAYMENT_QR,
        caption=PAYMENT_TEXT,
        parse_mode=ParseMode.HTML,
        reply_markup=InlineKeyboardMarkup(
            [[InlineKeyboardButton("Contact Owner", url=f"https://t.me/{OWNER}")]]
        )
    )

# Command to retrieve a list of active premium users (admin only)
@Bot.on_message(filters.private & filters.command('getpremiumusers') & filters.user(ADMINS))
async def get_premium_users(bot: Bot, message: Message):
    try:
        premium_users = pusers.find({"is_premium": True, "expiry_time": {"$gt": time.time()}})
        if not pusers.count_documents({"is_premium": True, "expiry_time": {"$gt": time.time()}}):
            return await message.reply("No active premium users found.")

        users_list = [
            f"User ID: {user.get('user_id')} - Premium Expires in {max(int((user.get('expiry_time') - time.time()) / 86400), 0)} days"
            for user in premium_users
        ]
        await message.reply("<b>Premium Users:</b>\n\n" + "\n".join(users_list), parse_mode=ParseMode.HTML)
    except Exception as e:
        await message.reply(f"Error: {str(e)}")
