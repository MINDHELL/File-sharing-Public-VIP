# https://t.me/Ultroid_Official/524

# https://t.me/Ultroid_Official/524

from bot import Bot
from pyrogram import filters
from config import *
from datetime import datetime
from plugins.start import *
from pyrogram.types import Message, CallbackQuery
from pyrogram.enums import ParseMode
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
import time

# Add /addpr command for admins to add premium subscription
@Bot.on_message(filters.private & filters.command('addpr') & filters.user(ADMINS))
async def add_premium(bot: Bot, message: Message):  # Changed `client: Client` to match `Bot`
    if message.from_user.id not in ADMINS:  # Fix: check if user is in ADMINS
        return await message.reply("You don't have permission to add premium users.")

    try:
        command_parts = message.text.split()
        if len(command_parts) < 3:  # Check if enough arguments are provided
            return await message.reply("Usage: /addpr 'user_id' 'duration_in_days'")

        target_user_id = int(command_parts[1])
        duration_in_days = int(command_parts[2])
        await add_premium_user(target_user_id, duration_in_days)
        await message.reply(f"User {target_user_id} added to premium for {duration_in_days} days.")
    except Exception as e:
        await message.reply(f"Error: {str(e)}")

# Add /removepr command for admins to remove premium subscription
@Bot.on_message(filters.private & filters.command('removepr') & filters.user(ADMINS))
async def remove_premium(bot: Bot, message: Message):  # Changed `client: Client` to match `Bot`
    if message.from_user.id not in ADMINS:  # Fix: check if user is in ADMINS
        return await message.reply("You don't have permission to remove premium users.")

    try:
        command_parts = message.text.split()
        if len(command_parts) < 2:  # Check if enough arguments are provided
            return await message.reply("Usage: /removepr 'user_id'")

        target_user_id = int(command_parts[1])
        await remove_premium_user(target_user_id)
        await message.reply(f"User {target_user_id} removed from premium.")
    except Exception as e:
        await message.reply(f"Error: {str(e)}")

# /myplan command to check user subscription status
@Bot.on_message(filters.command('myplan') & filters.private)
async def my_plan(bot: Bot, message: Message):
    is_premium, expiry_time = await get_user_subscription(message.from_user.id)
    time_left = int(expiry_time - time.time())
    
    if is_premium and time_left > 0:
        days_left = time_left // 86400
        hours_left = (time_left % 86400) // 3600
        minutes_left = (time_left % 3600) // 60

        response_text = (
            f"✅ Your premium subscription is active.\n\n"
            f"🕒 Time remaining: {days_left} days, {hours_left} hours, {minutes_left} minutes."
        )
        
        buttons = InlineKeyboardMarkup(
            [
                [InlineKeyboardButton("Upgrade Plan", callback_data="show_plans")],
                [InlineKeyboardButton("Contact Support", url=f"https://t.me/{OWNER}")]
            ]
        )

    elif is_premium and time_left <= 0:
        # Subscription expired
        response_text = (
            "⚠️ Your premium subscription has expired.\n\n"
            " "
            "Renew your subscription to continue enjoying premium features."
            " "
            "Check : /plans"
        )
        
        buttons = InlineKeyboardMarkup(
            [
                [InlineKeyboardButton("Renew Plan", callback_data="show_plans")],
                [InlineKeyboardButton("Contact Support", url=f"https://t.me/{OWNER}")]
            ]
        )

    else:
        # User is not a premium member
        response_text = "❌ You are not a premium user. \nView available plans to upgrade. \n\nClick HERE : \plans"
        
        buttons = InlineKeyboardMarkup(
            [
                [InlineKeyboardButton("View Plans", callback_data="show_plans")],
                [InlineKeyboardButton("Contact Support", url=f"https://t.me/{OWNER}")]
            ]
        )

    await message.reply_text(response_text, reply_markup=buttons)


# /plans command to show subscription plans
@Bot.on_message(filters.command('plans') & filters.private)
async def show_plans(bot: Bot, message: Message):
    plans_text = """
<b>Available Subscription Plans:</b>

1. 7 Days Premium  - 20₹
2. 15 Days Premium - 35₹
3. 30 Days Premium - 50₹
4. 90 Days Premium - 100₹

🎁 <b>Premium Features Applied</b>

To subscribe, click the "Pay via UPI" button below.
"""
    buttons = InlineKeyboardMarkup(
        [[InlineKeyboardButton("Pay via UPI", callback_data="upi_info")],
         [InlineKeyboardButton("Contact Support", url=f"https://t.me/{OWNER}")]]
    )

    await message.reply(plans_text, reply_markup=buttons, parse_mode=ParseMode.HTML)

# /upi command to show payment QR and options
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


@Client.on_message(filters.private & filters.command('getpremiumusers') & filters.user(ADMINS))
async def get_premium_users(client: Client, message: Message):
    try:
        # Retrieve premium users with active status
        premium_users = pusers.find({"is_premium": True, "expiry_time": {"$gt": time.time()}})
        
        # Check if there are any premium users
        if pusers.count_documents({"is_premium": True, "expiry_time": {"$gt": time.time()}}) == 0:
            return await message.reply("No active premium users found.")
        
        users_list = []
        for user in premium_users:
            user_id = user.get('user_id')
            expiry_time = user.get('expiry_time')
            time_left = expiry_time - time.time()
            days_left = max(int(time_left / 86400), 0)  # Ensure non-negative days left
            users_list.append(f"User ID: {user_id} - Premium Expires in {days_left} days")

        # Join the list and send the message
        users_text = "\n".join(users_list)
        await message.reply(f"<b>Premium Users:</b>\n\n{users_text}", parse_mode=ParseMode.HTML)
    except Exception as e:
        await message.reply(f"Error: {str(e)}")
