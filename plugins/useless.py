# https://t.me/Ultroid_Official/524

from bot import Bot
from pyrogram.types import Message
from pyrogram import filters
from config import ADMINS, BOT_STATS_TEXT, USER_REPLY_TEXT
from datetime import datetime
from helper_func import get_readable_time
from plugins.start import *

@Bot.on_message(filters.command('stats') & filters.user(ADMINS))
async def stats(bot: Bot, message: Message):
    now = datetime.now()
    delta = now - bot.uptime
    time = get_readable_time(delta.seconds)
    await message.reply(BOT_STATS_TEXT.format(uptime=time))


@Bot.on_message(filters.private & filters.incoming)
async def useless(_,message: Message):
    if USER_REPLY_TEXT:
        await message.reply(USER_REPLY_TEXT)


# Add /addpr command for admins to add premium subscription
@Bot.on_message(filters.private & filters.command('addpr') & filters.user(ADMINS))
#@Bot.on_message(filters.command('addpr') & filters.private)
async def add_premium(client: Client, message: Message):
    if message.from_user.id != ADMINS:
        return await message.reply("You don't have permission to add premium users.")

    try:
        command_parts = message.text.split()
        target_user_id = int(command_parts[1])
        duration_in_days = int(command_parts[2])
        await add_premium_user(target_user_id, duration_in_days)
        await message.reply(f"User {target_user_id} added to premium for {duration_in_days} days.")
    except Exception as e:
        await message.reply(f"Error: {str(e)}")

# Add /removepr command for admins to remove premium subscription
@Bot.on_message(filters.private & filters.command('removepr') & filters.user(ADMINS))
#@Bot.on_message(filters.command('removepr') & filters.private)
async def remove_premium(client: Client, message: Message):
    if message.from_user.id != ADMINS:
        return await message.reply("You don't have permission to remove premium users.")

    try:
        command_parts = message.text.split()
        target_user_id = int(command_parts[1])
        await remove_premium_user(target_user_id)
        await message.reply(f"User {target_user_id} removed from premium.")
    except Exception as e:
        await message.reply(f"Error: {str(e)}")


# https://t.me/Ultroid_Official/524
