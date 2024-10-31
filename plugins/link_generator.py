# @ultroidxTeam


from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from bot import Bot
from config import ADMINS
from helper_func import *



@Bot.on_message(filters.private & filters.user(ADMINS) & filters.command('batch'))
async def batch(client: Client, message: Message):
    while True:
        try:
            first_message = await client.ask(text = "Forward the First Message from DB Channel (With Quotes)..\n\nOr Send the DB Channel Post Link", chat_id = message.from_user.id, filters=(filters.forwarded | (filters.text & ~filters.forwarded)), timeout=60)
        except:
            return
        f_msg_id = await get_message_id(client, first_message)
        if f_msg_id:
            break
        else:
            await first_message.reply("❌ Error\n\nThis Forwarded Post is not from my DB Channel or this Link is taken from DB Channel", quote = True)
            continue

    while True:
        try:
            second_message = await client.ask(text = "Forward the Last Message from DB Channel (with Quotes)..\nor Send the DB Channel Post link", chat_id = message.from_user.id, filters=(filters.forwarded | (filters.text & ~filters.forwarded)), timeout=60)
        except:
            return
        s_msg_id = await get_message_id(client, second_message)
        if s_msg_id:
            break
        else:
            await second_message.reply("❌ Error\n\nThis Forwarded Post is not from my DB Channel or this Link is taken from DB Channel", quote = True)
            continue
   # Generate unique IDs and links
    converted_id = f_msg_id * abs(client.db_channel.id) - s_msg_id * abs(client.db_channel.id)
    string = f"get-{converted_id}"
    vipstring = f"vip-{converted_id}"

    # Encode both normal and premium strings
    base64_string = await encode(string)
    vipbase64_string = await encode_premium(vipstring)

    # Generate normal and premium links
    normal_link = f"https://t.me/{client.username}?start={base64_string}"
    premium_link = f"https://t.me/{client.username}?start={vipbase64_string}"

    # Create share URL button
    reply_markup = InlineKeyboardMarkup([[InlineKeyboardButton("🔁 Share URL", url=f'https://telegram.me/share/url?url={normal_link}')]])

    # Send links to user
    await message.reply(
        f"<b>Here are your links:</b>\n\n🤦‍♂️ Normal: {normal_link} \n\n✨ Premium: {premium_link} \n\nJoin @ultroid_official",
        reply_markup=reply_markup,
        disable_web_page_preview=True
    )




@Bot.on_message(filters.private & filters.user(ADMINS) & filters.command('genlink'))
async def link_generator(client: Client, message: Message):
    while True:
        try:
            channel_message = await client.ask(text = "Forward Message from the DB Channel (with Quotes)..\nor Send the DB Channel Post link", chat_id = message.from_user.id, filters=(filters.forwarded | (filters.text & ~filters.forwarded)), timeout=60)
        except:
            return
        msg_id = await get_message_id(client, channel_message)
        if msg_id:
            break
        else:
            await channel_message.reply("❌ Error\n\nthis Forwarded Post is not from my DB Channel or this Link is not taken from DB Channel", quote = True)
            continue

    converted_id = post_message.id * abs(client.db_channel.id)
    string = f"get-{converted_id}"
    vipstring = f"vip-{converted_id}"
    
    # Encode both normal and premium strings
    base64_string = await encode(string)
    vipbase64_string = await encode_premium(vipstring)
    
    # Generate normal and premium links
    normal_link = f"https://t.me/{client.username}?start={base64_string}"
    premium_link = f"https://t.me/{client.username}?start={vipbase64_string}"
    

    await channel_message.reply_text(f"<b>Here are your links:</b>\n\n🤦‍♂️ Normal: {normal_link} \n\n✨ Premium: {premium_link} \n\nJoin @ultroid_official", quote=True, reply_markup=reply_markup)







# ultroidxTeam 
