# https://t.me/Ultroid_Official/524

from pyrogram import __version__, Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from pyrogram.enums import ParseMode
from database.database import full_userbase
from bot import Bot
from config import OWNER_ID, ADMINS, CHANNEL, SUPPORT_GROUP, OWNER
from plugins.cmd import *
from plugins.start import is_premium_user


# Callback query handler
@Bot.on_callback_query()
async def cb_handler(client: Bot, query: CallbackQuery):
    data = query.data
    user_id = query.from_user.id

    if data == "about":
        await query.message.edit_text(
            text=f"<b>○ Creator : <a href='tg://user?id=7125905015'>This Person</a>\n"
                 f"○ Language : <code>Python3</code>\n"
                 f"○ Library : <a href='https://docs.pyrogram.org/'>Pyrogram asyncio {__version__}</a>\n"
                 f"○ Source Code : <a href='https://t.me/Xsupprtbot'>Click here</a>\n"
                 f"○ Channel : @{CHANNEL}\n"
                 f"○ Support Group : @{SUPPORT_GROUP}</b>",
            disable_web_page_preview=True,
            reply_markup=InlineKeyboardMarkup(
                [[InlineKeyboardButton("🔒 Close", callback_data="close")]]
            )
        )
    elif data == "close":
        await query.message.delete()
        try:
            await query.message.reply_to_message.delete()
        except Exception as e:
            print(f"Error deleting reply-to message: {e}")

    elif data == "upi_info":
        await upi_info(client, query.message)

    elif data == "show_plans":
        await show_plans(client, query.message)

    elif data == "premium_content":
        # Show an alert and then provide the premium content
        await query.answer("Checking Premium Status...", show_alert=True)
        try:
            if await is_premium_user(user_id):
                await query.message.reply_text("You are Premium One ✨! \nEnjoy Direct Ads-Free Access.")
            else:
                await query.message.reply_text("You are not a premium user.\n\nClick Here : /plans \n\nPlease upgrade to access this content.")
        except:
            await query.message.reply_text("Enable To Find out !! Sorry 🥵 \n\nClick here /myplan")
        
   # elif data == "premium_content":
    # Show an alert and then check if the user is premium
   # await query.answer("Checking Premium Status...", show_alert=True)
    
    
    

# https://t.me/Ultroid_Official/524


# ultroidofficial : YT
