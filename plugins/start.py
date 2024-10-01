# line number 160-169 check for changes - token
from pymongo import MongoClient
import asyncio
import base64
import logging
import os
import random
import re
import string
import time
from pyrogram import Client, filters, __version__
from pyrogram.enums import ParseMode
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from pyrogram.errors import FloodWait, UserIsBlocked, InputUserDeactivated
from bot import Bot
from config import (
    ADMINS,
    BAN,
    FORCE_MSG,
    START_MSG,
    CUSTOM_CAPTION,
    IS_VERIFY,
    VERIFY_EXPIRE,
    SHORTLINK_API,
    SHORTLINK_URL,
    DISABLE_CHANNEL_BUTTON,
    PROTECT_CONTENT,
    TUT_VID,
    OWNER_ID,
    DB_NAME,
    DB_URI,
)
from helper_func import subscribed, encode, decode, get_messages, get_shortlink, get_verify_status, update_verify_status, get_exp_time
from database.database import add_user, del_user, full_userbase, present_user
from shortzy import Shortzy
import pytz
from motor.motor_asyncio import AsyncIOMotorClient

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

mongo_client = AsyncIOMotorClient(DB_URI)
db = mongo_client[DB_NAME]  # Replace with your database name
phdlust = db['tokens']  # Collection for token counts
tz = pytz.timezone('Asia/Kolkata')

client = MongoClient(DB_URI)  # Replace with your MongoDB URI
db = client[DB_NAME]  # Database name
pusers = db["pusers"]  # Collection for users

# MongoDB Helper Functions
async def add_premium_user(user_id, duration_in_days):
    expiry_time = time.time() + (duration_in_days * 86400)  # Calculate expiry time in seconds
    pusers.update_one(
        {"user_id": user_id},
        {"$set": {"is_premium": True, "expiry_time": expiry_time}},
        upsert=True
    )

async def remove_premium_user(user_id):
    pusers.update_one(
        {"user_id": user_id},
        {"$set": {"is_premium": False, "expiry_time": None}}
    )

async def get_user_subscription(user_id):
    user = pusers.find_one({"user_id": user_id})
    if user:
        return user.get("is_premium", False), user.get("expiry_time", None)
    return False, None

async def is_premium_user(user_id):
    is_premium, expiry_time = await get_user_subscription(user_id)
    if is_premium and expiry_time > time.time():
        return True
    return False

# Helper Functions for Token Counting
async def increment_token_count(user_id: int):
    """Increments the total token count and the user's token count."""
    today = datetime.now(tz).strftime('%Y-%m-%d')
    # Increment total tokens for today
    await phdlust.update_one(
        {'date': today},
        {'$inc': {'today_tokens': 1, 'total_tokens': 1}},
        upsert=True
    )
    # Increment user's token count
    await phdlust.update_one(
        {'user_id': user_id},
        {'$inc': {'user_tokens': 1}},
        upsert=True
    )

async def get_today_token_count():
    """Retrieves today's total token count."""
    today = datetime.now(tz).strftime('%Y-%m-%d')
    doc = await phdlust.find_one({'date': today})
    return doc['today_tokens'] if doc and 'today_tokens' in doc else 0

async def get_total_token_count():
    """Retrieves the total token count."""
    pipeline = [
        {
            '$group': {
                '_id': None,
                'total': {'$sum': '$total_tokens'}
            }
        }
    ]
    result = await phdlust.aggregate(pipeline).to_list(length=1)
    return result[0]['total'] if result else 0

async def get_user_token_count(user_id: int):
    """Retrieves the token count for a specific user."""
    doc = await phdlust.find_one({'user_id': user_id})
    return doc['user_tokens'] if doc and 'user_tokens' in doc else 0



#limit based
@Client.on_message(filters.command('start') & filters.private)
async def start_command(client: Client, message: Message):
    user_id = message.from_user.id
    id = message.from_user.id
    UBAN = BAN  # Owner's ID

    # Check if the user is the owner
    if user_id == UBAN:
        await message.reply("You are the U-BAN! Additional actions can be added here.")
        return

    # Register the user if not present
    if not await present_user(user_id):
        try:
            await add_user(user_id)
        except Exception as e:
            logger.error(f"Error adding user {user_id}: {e}")

    # Retrieve user data
    user_data = await user_collection.find_one({"_id": user_id})
    if not user_data:
        logger.error(f"User data not found for user_id: {user_id}")
        await message.reply("An error occurred. Please try again later.")
        return

    user_limit = user_data.get("limit", START_COMMAND_LIMIT)
    previous_token = user_data.get("previous_token")

    premium_status = await is_premium_user(user_id)
    verify_status = await get_verify_status(user_id)

    # Generate a new token if not present
    if not previous_token:
        previous_token = str(uuid.uuid4())
        await user_collection.update_one(
            {"_id": user_id},
            {"$set": {"previous_token": previous_token}},
            upsert=True
        )

    # Generate the verification link
    verification_link = f"https://t.me/{CLIENT_USERNAME}?start=verify_{previous_token}"
    shortened_link = await get_shortlink(SHORTLINK_URL, SHORTLINK_API, verification_link)

    # Check if the user is providing a verification token
    if len(message.text.split()) > 1 and "verify_" in message.text:
        provided_token = message.text.split("verify_", 1)[1]
        if provided_token == previous_token:
            # Verification successful, increase limit
            new_limit = user_limit + LIMIT_INCREASE_AMOUNT
            await update_user_limit(user_id, new_limit)
            await log_verification(user_id)
            await increment_token_count(user_id)
            confirmation_message = await message.reply_text(
                "Your limit has been successfully increased by 10! Use /check to view your credits."
            )
            asyncio.create_task(delete_message_after_delay(confirmation_message, AUTO_DELETE_DELAY))
            return
        else:
            error_message = await message.reply_text("Invalid verification token. Please try again.")
            asyncio.create_task(delete_message_after_delay(error_message, AUTO_DELETE_DELAY))
            return

    # If the user is not premium and the limit is reached, prompt to increase limit
    if not premium_status and user_limit <= 0:
        limit_message = (
            "Your limit has been reached. Use /check to view your credits.\n"
            "Use the following link to increase your limit:"
        )
        buttons = [
            [
                InlineKeyboardButton(
                    text='Increase LIMIT',
                    url=shortened_link
                )
            ],
            [
                InlineKeyboardButton(
                    text='Try Again',
                    url=f"https://t.me/{CLIENT_USERNAME}?start=default"
                )
            ],
            [
                InlineKeyboardButton(
                    text='Verification Tutorial',
                    url=TUT_VID
                )
            ]
        ]

        reply_markup = InlineKeyboardMarkup(buttons)
        await message.reply(
            limit_message,
            reply_markup=reply_markup,
            protect_content=False,
            quote=True
        )
        asyncio.create_task(delete_message_after_delay(message, AUTO_DELETE_DELAY))
        return

    # Deduct 1 from the user's limit only if not premium
    if not premium_status:
        await update_user_limit(user_id, user_limit - 1)

    # Handle the rest of the start command logic
    text = message.text
    if len(text.split()) > 1 and (verify_status['is_verified'] or premium_status):
        try:
            base64_string = text.split(" ", 1)[1]
            decoded_string = await decode(base64_string)
            arguments = decoded_string.split("-")

            ids = []
            if len(arguments) == 3:
                start = int(int(arguments[1]) / abs(YOUR_CHANNEL_ID))  # Adjust if necessary
                end = int(int(arguments[2]) / abs(YOUR_CHANNEL_ID))
                if start <= end:
                    ids = list(range(start, end + 1))
                else:
                    ids = list(range(start, end - 1, -1))
            elif len(arguments) == 2:
                single_id = int(int(arguments[1]) / abs(YOUR_CHANNEL_ID))
                ids = [single_id]
            else:
                logger.error("Invalid number of arguments in decoded string.")
                return

            temp_msg = await message.reply("Please wait...")
            try:
                messages = await get_messages(client, ids)
            except Exception as e:
                await message.reply_text("Something went wrong..!")
                logger.error(f"Error getting messages: {e}")
                return

            await temp_msg.delete()

            for msg in messages:
                if msg.document:
                    caption = CUSTOM_CAPTION.format(
                        previouscaption=msg.caption.html if msg.caption else "",
                        filename=msg.document.file_name
                    )
                else:
                    caption = msg.caption.html if msg.caption else ""

                reply_markup = msg.reply_markup if not DISABLE_CHANNEL_BUTTON else None

                try:
                    sent_message = await msg.copy(
                        chat_id=user_id,
                        caption=caption,
                        parse_mode="html",
                        reply_markup=reply_markup,
                        protect_content=PROTECT_CONTENT
                    )
                    asyncio.create_task(delete_message_after_delay(sent_message, AUTO_DELETE_DELAY))
                    await asyncio.sleep(0.5)
                except FloodWait as e:
                    logger.warning(f"FloodWait encountered. Sleeping for {e.x} seconds.")
                    await asyncio.sleep(e.x)
                    sent_message = await msg.copy(
                        chat_id=user_id,
                        caption=caption,
                        parse_mode="html",
                        reply_markup=reply_markup,
                        protect_content=PROTECT_CONTENT
                    )
                    asyncio.create_task(delete_message_after_delay(sent_message, AUTO_DELETE_DELAY))
                except Exception as e:
                    logger.error(f"Error copying message: {e}")
                    continue
            return
    else:
        # Send welcome message with buttons
        reply_markup = InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton("😊 About Me", callback_data="about"),
                    InlineKeyboardButton("🔒 Close", callback_data="close")
                ]
            ]
        )
        welcome_text = (
            f"Hello, {message.from_user.first_name}!\n"
            f"Your ID: {message.from_user.id}\n"
            f"Username: @{message.from_user.username if message.from_user.username else 'N/A'}"
        )
        welcome_message = await message.reply_text(
            text=welcome_text,
            reply_markup=reply_markup,
            disable_web_page_preview=True,
            quote=True
        )
        asyncio.create_task(delete_message_after_delay(welcome_message, AUTO_DELETE_DELAY))
        return

    
#=====================================================================================##

WAIT_MSG = """"<b>Processing ...</b>"""

REPLY_ERROR = """<code>Use this command as a replay to any telegram message with out any spaces.</code>"""

#=====================================================================================##

# Credits
# Bot Developed by @phdlust
# GitHub: https://github.com/sahiildesai07
# Telegram: https://t.me/ultroidxTeam
# YouTube: https://www.youtube.com/@PhdLust


# Handle Callback Queries for Token Count
@Bot.on_callback_query(filters.regex(r"^check_tokens$"))
async def check_tokens_callback(client: Client, callback_query: CallbackQuery):
    user_id = callback_query.from_user.id
    is_admin = user_id in ADMINS

    # Fetch token counts
    today_tokens = await get_today_token_count()
    total_tokens = await get_total_token_count()
    user_tokens = await get_user_token_count(user_id)

    if is_admin:
        # For admins, optionally display more detailed stats
        users = await full_userbase()
        user_token_details = ""
        for user in users[:10]:  # Limit to first 10 users for brevity
            tokens = await get_user_token_count(user)
            user_token_details += f"User ID: {user} - Tokens: {tokens}\n"
        response = (
            f"<b>🔹 Admin Token Statistics 🔹</b>\n\n"
            f"<b>Today's Token Count:</b> {today_tokens}\n"
            f"<b>Total Token Count:</b> {total_tokens}\n\n"
            f"<b>Top Users:</b>\n{user_token_details}"
        )
    else:
        # For regular users
        response = (
            f"<b>📊 Your Token Statistics 📊</b>\n\n"
            f"<b>Today's Token Count:</b> {today_tokens}\n"
            f"<b>Total Token Count:</b> {total_tokens}\n"
            f"<b>Your Token Count:</b> {user_tokens}"
        )

    await callback_query.answer()
    await callback_query.message.edit_text(
        text=response,
        parse_mode=ParseMode.HTML,
        reply_markup=InlineKeyboardMarkup(
            [[InlineKeyboardButton("Close", callback_data="close")]]
        )
    )


@Bot.on_message(filters.command('start') & filters.private)
async def not_joined(client: Client, message: Message):
    buttons = [
        [
            InlineKeyboardButton(text="Join Channel", url=client.invitelink),
            #InlineKeyboardButton(text="Join Channel", url=client.invitelink2),
        ],
        [
            InlineKeyboardButton(text="Join Channel", url=client.invitelink3),
            #InlineKeyboardButton(text="Join Channel", url=client.invitelink4),
        ]
    ]
    try:
        buttons.append(
            [
                InlineKeyboardButton(
                    text = 'Try Again',
                    url = f"https://t.me/{client.username}?start={message.command[1]}"
                )
            ]
        )
    except IndexError:
        pass

    await message.reply(
        text = FORCE_MSG.format(
                first = message.from_user.first_name,
                last = message.from_user.last_name,
                username = None if not message.from_user.username else '@' + message.from_user.username,
                mention = message.from_user.mention,
                id = message.from_user.id
            ),
        reply_markup = InlineKeyboardMarkup(buttons),
        quote = True,
        disable_web_page_preview = True
    )

WAIT_MSG = """"<b>Processing ...</b>"""

REPLY_ERROR = """<code>Use this command as a replay to any telegram message with out any spaces.</code>"""

# Existing /users Command for Admins
@Bot.on_message(filters.command('users') & filters.private & filters.user(ADMINS))
async def get_users(client: Client, message: Message):
    msg = await client.send_message(chat_id=message.chat.id, text=WAIT_MSG)
    users = await full_userbase()
    await msg.edit(f"{len(users)} users are using this bot")

# Existing /broadcast Command for Admins
@Bot.on_message(filters.private & filters.command('broadcast') & filters.user(ADMINS))
async def send_text(client: Client, message: Message):
    if message.reply_to_message:
        query = await full_userbase()
        broadcast_msg = message.reply_to_message
        total = 0
        successful = 0
        blocked = 0
        deleted = 0
        unsuccessful = 0

        pls_wait = await message.reply("<i>Broadcasting Message.. This will Take Some Time</i>")
        for chat_id in query:
            try:
                await broadcast_msg.copy(chat_id)
                successful += 1
            except FloodWait as e:
                await asyncio.sleep(e.x)
                await broadcast_msg.copy(chat_id)
                successful += 1
            except UserIsBlocked:
                await del_user(chat_id)
                blocked += 1
            except InputUserDeactivated:
                await del_user(chat_id)
                deleted += 1
            except:
                unsuccessful += 1
                pass
            total += 1

        status = f"""<b><u>Broadcast Completed</u>

Total Users: <code>{total}</code>
Successful: <code>{successful}</code>
Blocked Users: <code>{blocked}</code>
Deleted Accounts: <code>{deleted}</code>
Unsuccessful: <code>{unsuccessful}</code></b>"""

        return await pls_wait.edit(status)

    else:
        msg = await message.reply(REPLY_ERROR)
        await asyncio.sleep(8)
        await msg.delete()

# Add a New Command /tokencount for Users and Admins
@Bot.on_message(filters.command('tokencount') & filters.private)
async def token_count_command(client: Client, message: Message):
    user_id = message.from_user.id
    is_admin = user_id in ADMINS

# Credits
# Bot Developed by @phdlust
# GitHub: https://github.com/sahiildesai07
# Telegram: https://t.me/ultroidxTeam
# YouTube: https://www.youtube.com/@PhdLust

    # Fetch token counts
    today_tokens = await get_today_token_count()
    total_tokens = await get_total_token_count()
    user_tokens = await get_user_token_count(user_id)

    if is_admin:
        # For admins, optionally display more detailed stats
        users = await full_userbase()
        user_token_details = ""
        for user in users[:10]:  # Limit to first 10 users for brevity
            tokens = await get_user_token_count(user)
            user_token_details += f"User ID: {user} - Tokens: {tokens}\n"
        response = (
            f"<b>🔹 Admin Token Statistics 🔹</b>\n\n"
            f"<b>Today's Token Count:</b> {today_tokens}\n"
            f"<b>Total Token Count:</b> {total_tokens}\n\n"
            f"<b>Top Users:</b>\n{user_token_details}"
        )
    else:
        # For regular users
        response = (
            f"<b>📊 Your Token Statistics 📊</b>\n\n"
            f"<b>Today's Token Count:</b> {today_tokens}\n"
            f"<b>Total Token Count:</b> {total_tokens}\n"
            f"<b>Your Token Count:</b> {user_tokens}"
        )

    await message.reply_text(
        text=response,
        parse_mode=ParseMode.HTML,
        reply_markup=InlineKeyboardMarkup(
            [[InlineKeyboardButton("Close", callback_data="close")]]
        )
    )


# Credits
# Bot Developed by @phdlust
# GitHub: https://github.com/sahiildesai07
# Telegram: https://t.me/ultroidxTeam
# YouTube: https://www.youtube.com/@PhdLust
