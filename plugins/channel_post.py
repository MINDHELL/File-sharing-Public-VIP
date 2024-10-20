# https://t.me/Ultroid_Official/524



import asyncio
from pyrogram import filters, Client
from pyrogram.errors import FloodWait
from bot import Bot
from config import ADMINS, CHANNEL_ID, DISABLE_CHANNEL_BUTTON
from helper_func import encode

import logging
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton

@Bot.on_message(filters.private & filters.user(ADMINS) & ~filters.command(['start','users','getpremiumusers','broadcast','batch','genlink','upi', 'myplan' , 'plans' ,'stats','removepr','addpr']))
async def channel_post(client: Client, message: Message):
    reply_text = await message.reply_text("Please Wait...", quote=True)

    try:
        # Trying to copy the message to the database channel
        post_message = await message.copy(chat_id=client.db_channel.id, disable_notification=True)
    except FloodWait as e:
        # Handling FloodWait exception by sleeping for the required time
        logging.error(f"FloodWait exception: Need to wait for {e.x} seconds.")
        await asyncio.sleep(e.x)
        post_message = await message.copy(chat_id=client.db_channel.id, disable_notification=True)
    except Exception as e:
        # Logging the actual error for debugging
        logging.error(f"Error while copying message: {e}")
        await reply_text.edit_text("Something went wrong! Please try again later.")
        return

    try:
        # Use different encoding for normal and premium links
        normal_string = f"get-{post_message.id * abs(client.db_channel.id)}"
        premium_string = f"premium-{post_message.id * abs(client.db_channel.id)}-{post_message.date}"

        # Base64 encoding for normal link
        normal_base64 = await encode(normal_string)
        # Different Base64 encoding for premium link
        premium_base64 = await encode(premium_string)
        
        # Generate normal and premium links
        normal_link = f"https://t.me/{client.username}?start={normal_base64}"
        premium_link = f"https://t.me/{client.username}?start={premium_base64}"

        # Creating inline buttons for sharing the links
        reply_markup = InlineKeyboardMarkup(
            [[InlineKeyboardButton("🔁 Share Normal URL", url=f'https://telegram.me/share/url?url={normal_link}'),
              InlineKeyboardButton("🔁 Share Premium URL", url=f'https://telegram.me/share/url?url={premium_link}')]]
        )

        await reply_text.edit(
            f"<b>Here are your links:</b>\n\n🤦‍♂️ Normal: {normal_link} \n\n✨ Premium: {premium_link} \n\nJoin @ultroid_official", 
            reply_markup=reply_markup, 
            disable_web_page_preview=True,
            parse_mode="html"  # Directly specify "html" or "markdown" as needed
        )

        # Optionally updating the post in the database channel with a reply markup
        if not DISABLE_CHANNEL_BUTTON:
            await post_message.edit_reply_markup(reply_markup)

    except Exception as e:
        logging.error(f"Error generating links: {e}")



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
    except Exception as e:
        print(e)
        pass






# https://t.me/Ultroid_Official/524
