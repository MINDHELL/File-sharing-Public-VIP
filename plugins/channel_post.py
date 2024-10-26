# https://t.me/Ultroid_Official/524



import asyncio
from pyrogram import filters, Client
from pyrogram.errors import FloodWait
from bot import Bot
from config import ADMINS, CHANNEL_ID, DISABLE_CHANNEL_BUTTON
from helper_func import *
import logging
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton


# Assuming ADMINS, DISABLE_CHANNEL_BUTTON, and encode, encodeb functions are defined elsewhere
COMMANDS = ['start', 'users', 'getpremiumusers', 'broadcast', 'batch', 'genlink', 'upi', 'myplan', 'plans', 'stats', 'removepr', 'addpr']

@Bot.on_message(filters.private & filters.user(ADMINS) & ~filters.command(COMMANDS))
async def channel_post(client: Client, message: Message):
    reply_text = await message.reply_text("Please Wait... 4!", quote=True)
    try:
        post_message = await message.copy(chat_id=client.db_channel.id, disable_notification=True)
    except FloodWait as e:
        await asyncio.sleep(e.x)
        post_message = await message.copy(chat_id=client.db_channel.id, disable_notification=True)
    except Exception as e:
        logging.error(f"Error in channel_post: {e}")
        await reply_text.edit_text("Something went wrong!")
        return

    # Generate normal and premium links
    message_id_factor = post_message.id * abs(client.db_channel.id)
    normal_string = f"got-{message_id_factor}"
    premium_string = f"get-{message_id_factor}"
    
    # Encoding links
    normal_link = f"https://t.me/{client.username}?start={await encode(normal_string)}"
    premium_link = f"https://t.me/{client.username}?start={await encode_premium(premium_string)}"

    reply_markup = InlineKeyboardMarkup([
        [InlineKeyboardButton("🔁 Share Normal URL", url=f'https://telegram.me/share/url?url={normal_link}'),
         InlineKeyboardButton("🔁 Share Premium URL", url=f'https://telegram.me/share/url?url={premium_link}')]
    ])

    try:
        await reply_text.edit(
            f"<b>Here are your links:</b>\n\n🤦‍♂️ Normal: {normal_link} \n\n✨ Premium: {premium_link} \n\nJoin @ultroid_official", 
            reply_markup=reply_markup, 
            disable_web_page_preview=True
        )

        if not DISABLE_CHANNEL_BUTTON:
            await post_message.edit_reply_markup(reply_markup)
    except FloodWait as e:
        await asyncio.sleep(e.x)
        try:
            await post_message.edit_reply_markup(reply_markup)
        except Exception as edit_error:
            logging.error(f"Error editing reply markup after flood wait: {edit_error}")
    except Exception as e:
        logging.error(f"Error editing reply markup: {e}")



@Bot.on_message(filters.channel & filters.incoming & filters.chat(CHANNEL_ID))
async def new_post(client: Client, message: Message):

    if DISABLE_CHANNEL_BUTTON:
        return

    converted_id = message.id * abs(client.db_channel.id)
    string = f"get-{converted_id}"
    base64_string = await encode(string)
    link = f"https://t.me/{client.username}?start={base64_string}"
    reply_markup = InlineKeyboardMarkup([[InlineKeyboardButton("🔁 Share URL", url=f'https://telegram.me/share/url?url={link}')]])
    try:
        await message.edit_reply_markup(reply_markup)
    except FloodWait as e:
        await asyncio.sleep(e.value)
        await message.edit_reply_markup(reply_markup)
    except Exception:
        pass



# https://t.me/Ultroid_Official/524
