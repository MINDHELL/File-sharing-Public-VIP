import asyncio
import uuid
import logging
import os
import random
import re
import string
import time
from datetime import datetime
from pyrogram import Client, filters
from pyrogram.enums import ParseMode
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from pyrogram.errors import FloodWait, UserIsBlocked, InputUserDeactivated
from motor.motor_asyncio import AsyncIOMotorClient
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
from helper_func import (
    subscribed, encode, decode, get_messages, get_shortlink,
    get_verify_status, update_verify_status, get_exp_time,
    log_verification
)
from database.database import add_user, del_user, full_userbase, present_user, get_user_limit, update_user_limit
from shortzy import Shortzy
import pytz

# Configuration Variables
START_COMMAND_LIMIT = 15
LIMIT_INCREASE_AMOUNT = 10
AUTO_DELETE_DELAY = 60  # in seconds
CLIENT_USERNAME = "YourBotUsername"  # Replace with your bot's username without '@'

# Initialize logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize MongoDB with AsyncIOMotorClient
mongo_client = AsyncIOMotorClient(DB_URI)
db = mongo_client[DB_NAME]  # Replace with your database name

# Define collections
users_collection = db["users"]          # Collection for user data
premium_users_collection = db["pusers"] # Collection for premium users
tokens_collection = db["tokens"]        # Collection for token counts

# Timezone
tz = pytz.timezone('Asia/Kolkata')

# Initialize Shortzy for URL shortening
shortzy = Shortzy(api_key=SHORTLINK_API, base_site=SHORTLINK_URL)

async def get_shortlink_func(link: str) -> str:
    """Generate a shortened link using Shortzy."""
    try:
        verification_link = await shortzy.convert(link)
        return verification_link
    except Exception as e:
        logger.error(f"Error generating short link: {str(e)}")
        return link

async def delete_message_after_delay(message: Message, delay: int):
    """Delete a message after a specified delay."""
    await asyncio.sleep(delay)
    try:
        await message.delete()
    except Exception as e:
        logger.error(f"Failed to delete message: {e}")

# Premium User Management
async def add_premium_user(user_id: int, duration_in_days: int):
    """Add a user as premium with a duration."""
    expiry_time = time.time() + (duration_in_days * 86400)  # Calculate expiry time in seconds
    await premium_users_collection.update_one(
        {"user_id": user_id},
        {"$set": {"is_premium": True, "expiry_time": expiry_time}},
        upsert=True
    )
    logger.info(f"User {user_id} added as premium for {duration_in_days} days.")

async def remove_premium_user(user_id: int):
    """Remove premium status from a user."""
    await premium_users_collection.update_one(
        {"user_id": user_id},
        {"$set": {"is_premium": False, "expiry_time": None}}
    )
    logger.info(f"User {user_id} removed from premium.")

async def get_user_subscription(user_id: int):
    """Retrieve a user's premium subscription status."""
    user = await premium_users_collection.find_one({"user_id": user_id})
    if user:
        return user.get("is_premium", False), user.get("expiry_time", None)
    return False, None

async def is_premium_user(user_id: int) -> bool:
    """Check if a user is currently a premium user."""
    is_premium, expiry_time = await get_user_subscription(user_id)
    if is_premium and expiry_time > time.time():
        return True
    return False

# Token Counting Helper Functions
async def increment_token_count(user_id: int):
    """Increments the total token count and the user's token count."""
    today = datetime.now(tz).strftime('%Y-%m-%d')
    # Increment total tokens for today
    await tokens_collection.update_one(
        {'date': today},
        {'$inc': {'today_tokens': 1, 'total_tokens': 1}},
        upsert=True
    )
    # Increment user's token count
    await tokens_collection.update_one(
        {'user_id': user_id},
        {'$inc': {'user_tokens': 1}},
        upsert=True
    )
    logger.info(f"Token count incremented for user {user_id}.")

async def get_today_token_count() -> int:
    """Retrieves today's total token count."""
    today = datetime.now(tz).strftime('%Y-%m-%d')
    doc = await tokens_collection.find_one({'date': today})
    return doc['today_tokens'] if doc and 'today_tokens' in doc else 0

async def get_total_token_count() -> int:
    """Retrieves the total token count."""
    pipeline = [
        {
            '$group': {
                '_id': None,
                'total': {'$sum': '$total_tokens'}
            }
        }
    ]
    result = await tokens_collection.aggregate(pipeline).to_list(length=1)
    return result[0]['total'] if result else 0

async def get_user_token_count(user_id: int) -> int:
    """Retrieves the token count for a specific user."""
    doc = await tokens_collection.find_one({'user_id': user_id})
    return doc['user_tokens'] if doc and 'user_tokens' in doc else 0

# Initialize Pyrogram Client
Bot = Client(
    "my_bot",
    api_id=os.getenv("API_ID"),          # Ensure to set API_ID in environment variables
    api_hash=os.getenv("API_HASH"),      # Ensure to set API_HASH in environment variables
    bot_token=os.getenv("BOT_TOKEN")     # Ensure to set BOT_TOKEN in environment variables
)

# /check Command Handler
@Bot.on_message(filters.command('check') & filters.private)
async def check_command(client: Client, message: Message):
    user_id = message.from_user.id

    try:
        user_limit = await get_user_limit(user_id)
        limit_message = await message.reply_text(f"Your current limit is {user_limit}.")
        asyncio.create_task(delete_message_after_delay(limit_message, AUTO_DELETE_DELAY))
    except Exception as e:
        logger.error(f"Error in check_command: {e}")
        error_message = await message.reply_text("An error occurred while checking your limit.")
        asyncio.create_task(delete_message_after_delay(error_message, AUTO_DELETE_DELAY))

# /count Command Handler
@Bot.on_message(filters.command('count') & filters.private)
async def count_command(client: Client, message: Message):
    try:
        # Get the count of users who used a token in the last 24 hours
        last_24h_count = await get_verification_count("24h")  # Ensure this function is defined

        # Get the count of users who used a token today
        today_count = await get_verification_count("today")  # Ensure this function is defined

        count_message = (
            f"Token usage stats:\n"
            f"Last 24 hours: {last_24h_count} users\n"
            f"Today's token users: {today_count} users"
        )
        
        response_message = await message.reply_text(count_message)
        asyncio.create_task(delete_message_after_delay(response_message, AUTO_DELETE_DELAY))

    except Exception as e:
        logger.error(f"Error in count_command: {e}")
        error_message = await message.reply_text("An error occurred while retrieving count data.")
        asyncio.create_task(delete_message_after_delay(error_message, AUTO_DELETE_DELAY))

# /start Command Handler
@Bot.on_message(filters.command('start') & filters.private)
async def start_command(client: Client, message: Message):
    user_id = message.from_user.id
    UBAN = BAN  # Owner's ID

    # Check if the user is the owner (UBAN)
    if user_id == UBAN:
        await message.reply("You are the U-BAN! Additional actions can be added here.")
        return

    # Register the user if not present
    if not await present_user(user_id):
        try:
            await add_user(user_id)
            logger.info(f"User {user_id} added to the database.")
        except Exception as e:
            logger.error(f"Error adding user {user_id}: {e}")
            await message.reply("An error occurred while registering you. Please try again later.")
            return

    # Retrieve user data
    user_data = await users_collection.find_one({"user_id": user_id})
    if not user_data:
        # Initialize user data if not present
        await users_collection.insert_one({
            "user_id": user_id,
            "limit": START_COMMAND_LIMIT,
            "previous_token": None,
            "is_premium": False,
            "is_verified": False
        })
        user_data = await users_collection.find_one({"user_id": user_id})

    user_limit = user_data.get("limit", START_COMMAND_LIMIT)
    previous_token = user_data.get("previous_token")

    premium_status = await is_premium_user(user_id)  # Check if user is premium
    verify_status = await get_verify_status(user_id)  # Ensure this function is defined

    # Generate a new token if not present
    if not previous_token:
        previous_token = str(uuid.uuid4())
        await users_collection.update_one(
            {"user_id": user_id},
            {"$set": {"previous_token": previous_token}},
            upsert=True
        )
        logger.info(f"Generated new token for user {user_id}.")

    # Generate the verification link
    verification_link = f"https://t.me/{CLIENT_USERNAME}?start=verify_{previous_token}"
    shortened_link = await get_shortlink_func(verification_link)

    # Check if the user is providing a verification token
    if len(message.command) > 1 and "verify_" in message.command[1]:
        provided_token = message.command[1].split("verify_", 1)[1]
        if provided_token == previous_token:
            # Verification successful, increase limit
            new_limit = user_limit + LIMIT_INCREASE_AMOUNT
            await update_user_limit(user_id, new_limit)
            await log_verification(user_id)
            await increment_token_count(user_id)
            confirmation_message = await message.reply_text(
                "✅ Your limit has been successfully increased by 10! Use /check to view your credits."
            )
            asyncio.create_task(delete_message_after_delay(confirmation_message, AUTO_DELETE_DELAY))
            return
        else:
            error_message = await message.reply_text("❌ Invalid verification token. Please try again.")
            asyncio.create_task(delete_message_after_delay(error_message, AUTO_DELETE_DELAY))
            return

    # If the user is not premium and the limit is reached, prompt to increase limit
    if not premium_status and user_limit <= 0:
        limit_message = (
            "⚠️ Your limit has been reached. Use /check to view your credits.\n"
            "🔗 Use the following link to increase your limit:"
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

    # Deduct 1 from the user's limit only if they are not premium
    if not premium_status:
        await update_user_limit(user_id, user_limit - 1)
        logger.info(f"Deducted 1 from user {user_id}'s limit. New limit: {user_limit - 1}")

    # Handle the rest of the start command logic
    text = message.text
        if len(message.command) > 1 and (verify_status['is_verified'] or premium_status):
        try:
            base64_string = message.command[1]
            decoded_string = await decode(base64_string)
            arguments = decoded_string.split("-")

            ids = []
            if len(arguments) == 3:
                # Ensure client.db_channel.id is defined
                channel_id = YOUR_CHANNEL_ID  # Define your channel ID as an integer
                start = int(int(arguments[1]) / abs(channel_id))
                end = int(int(arguments[2]) / abs(channel_id))
                if start <= end:
                    ids = list(range(start, end + 1))
                else:
                    ids = list(range(start, end - 1, -1))
            elif len(arguments) == 2:
                single_id = int(int(arguments[1]) / abs(channel_id))
                ids = [single_id]
            else:
                logger.error("Invalid number of arguments in decoded string.")
                return

            temp_msg = await message.reply("⏳ Please wait while we process your request...")
            try:
                messages = await get_messages(client, ids)  # Ensure this function is defined
            except Exception as e:
                await message.reply_text("❌ Something went wrong..!")
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
                        parse_mode=ParseMode.HTML,
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
                        parse_mode=ParseMode.HTML,
                        reply_markup=reply_markup,
                        protect_content=PROTECT_CONTENT
                    )
                    asyncio.create_task(delete_message_after_delay(sent_message, AUTO_DELETE_DELAY))
                except Exception as e:
                    logger.error(f"Error copying message: {e}")
                    continue
        except Exception as e:
            logger.error(f"Error processing command: {e}")
            await message.reply_text("❌ An error occurred while processing your request.")
            return
    else:
        # Send welcome message with buttons
        reply_markup = InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton("😊 About Me", url="https://t.me/YourUsername"),  # Replace with actual URL
                    InlineKeyboardButton("🔒 Close", callback_data="close")
                ]
            ]
        )
        welcome_text = (
            f"👋 Hello, {message.from_user.first_name}!\n"
            f"🔹 Your ID: {message.from_user.id}\n"
            f"🔹 Username: @{message.from_user.username if message.from_user.username else 'N/A'}"
        )
        welcome_message = await message.reply_text(
            text=welcome_text,
            reply_markup=reply_markup,
            disable_web_page_preview=True,
            quote=True
        )
        asyncio.create_task(delete_message_after_delay(welcome_message, AUTO_DELETE_DELAY))
        return


# Handle Callback Queries for Token Count
@Bot.on_callback_query(filters.regex(r"^check_tokens$"))
async def check_tokens_callback(client: Client, callback_query: CallbackQuery):
    user_id = callback_query.from_user.id
    is_admin = user_id in ADMINS

    try:
        # Fetch token counts
        today_tokens = await get_today_token_count()
        total_tokens = await get_total_token_count()
        user_tokens = await get_user_token_count(user_id)

        if is_admin:
            # For admins, optionally display more detailed stats
            users = await full_userbase()  # Ensure this function is defined
            user_token_details = ""
            for user in users[:10]:  # Limit to first 10 users for brevity
                tokens = await get_user_token_count(user)
                user_token_details += f"🔹 User ID: {user} - Tokens: {tokens}\n"
            response = (
                f"<b>🔹 Admin Token Statistics 🔹</b>\n\n"
                f"<b>📅 Today's Token Count:</b> {today_tokens}\n"
                f"<b>🌐 Total Token Count:</b> {total_tokens}\n\n"
                f"<b>📈 Top Users:</b>\n{user_token_details}"
            )
        else:
            # For regular users
            response = (
                f"<b>📊 Your Token Statistics 📊</b>\n\n"
                f"<b>📅 Today's Token Count:</b> {today_tokens}\n"
                f"<b>🌐 Total Token Count:</b> {total_tokens}\n"
                f"<b>🔢 Your Token Count:</b> {user_tokens}"
            )

        await callback_query.answer()
        await callback_query.message.edit_text(
            text=response,
            parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup(
                [[InlineKeyboardButton("🔒 Close", callback_data="close")]]
            )
        )
    except Exception as e:
        logger.error(f"Error in check_tokens_callback: {e}")
        await callback_query.answer("❌ An error occurred while fetching token statistics.", show_alert=True)

# /tokencount Command Handler
@Bot.on_message(filters.command('tokencount') & filters.private)
async def token_count_command(client: Client, message: Message):
    user_id = message.from_user.id
    is_admin = user_id in ADMINS

    try:
        # Fetch token counts
        today_tokens = await get_today_token_count()
        total_tokens = await get_total_token_count()
        user_tokens = await get_user_token_count(user_id)

        if is_admin:
            # For admins, optionally display more detailed stats
            users = await full_userbase()  # Ensure this function is defined
            user_token_details = ""
            for user in users[:10]:  # Limit to first 10 users for brevity
                tokens = await get_user_token_count(user)
                user_token_details += f"🔹 User ID: {user} - Tokens: {tokens}\n"
            response = (
                f"<b>🔹 Admin Token Statistics 🔹</b>\n\n"
                f"<b>📅 Today's Token Count:</b> {today_tokens}\n"
                f"<b>🌐 Total Token Count:</b> {total_tokens}\n\n"
                f"<b>📈 Top Users:</b>\n{user_token_details}"
            )
        else:
            # For regular users
            response = (
                f"<b>📊 Your Token Statistics 📊</b>\n\n"
                f"<b>📅 Today's Token Count:</b> {today_tokens}\n"
                f"<b>🌐 Total Token Count:</b> {total_tokens}\n"
                f"<b>🔢 Your Token Count:</b> {user_tokens}"
            )

        await message.reply_text(
            text=response,
            parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup(
                [[InlineKeyboardButton("🔒 Close", callback_data="close")]]
            )
        )
    except Exception as e:
        logger.error(f"Error in token_count_command: {e}")
        error_message = await message.reply_text("❌ An error occurred while retrieving your token statistics.")
        asyncio.create_task(delete_message_after_delay(error_message, AUTO_DELETE_DELAY))

# /users Command for Admins
@Bot.on_message(filters.command('users') & filters.private & filters.user(ADMINS))
async def get_users(client: Client, message: Message):
    try:
        pls_wait = await message.reply("⏳ Fetching user data...")
        users = await full_userbase()  # Ensure this function is defined
        await pls_wait.edit_text(f"📋 Total Users: {len(users)}")
    except Exception as e:
        logger.error(f"Error in get_users: {e}")
        error_message = await message.reply_text("❌ An error occurred while fetching users.")
        asyncio.create_task(delete_message_after_delay(error_message, AUTO_DELETE_DELAY))

# /broadcast Command for Admins
@Bot.on_message(filters.command('broadcast') & filters.private & filters.user(ADMINS))
async def send_broadcast(client: Client, message: Message):
    if message.reply_to_message:
        query = await full_userbase()  # Ensure this function is defined
        broadcast_msg = message.reply_to_message
        total = 0
        successful = 0
        blocked = 0
        deleted = 0
        unsuccessful = 0

        pls_wait = await message.reply("<i>📢 Broadcasting message... This may take some time.</i>")
        for chat_id in query:
            try:
                await broadcast_msg.copy(chat_id)
                successful += 1
            except FloodWait as e:
                logger.warning(f"FloodWait encountered. Sleeping for {e.x} seconds.")
                await asyncio.sleep(e.x)
                await broadcast_msg.copy(chat_id)
                successful += 1
            except UserIsBlocked:
                await del_user(chat_id)
                blocked += 1
            except InputUserDeactivated:
                await del_user(chat_id)
                deleted += 1
            except Exception as e:
                logger.error(f"Error broadcasting to {chat_id}: {e}")
                unsuccessful += 1
                pass
            total += 1

        status = (
            f"<b>✅ Broadcast Completed</b>\n\n"
            f"<b>Total Users:</b> <code>{total}</code>\n"
            f"<b>Successful:</b> <code>{successful}</code>\n"
            f"<b>Blocked Users:</b> <code>{blocked}</code>\n"
            f"<b>Deleted Accounts:</b> <code>{deleted}</code>\n"
            f"<b>Unsuccessful:</b> <code>{unsuccessful}</code>"
        )
        await pls_wait.edit_text(status)
    else:
        await message.reply(REPLY_ERROR)
        await asyncio.sleep(8)
        await message.delete()

# /tokencount Command for Users and Admins (Already Defined Above)

# /join Command Handler (Example)
@Bot.on_message(filters.command('join') & filters.private)
async def join_command(client: Client, message: Message):
    buttons = [
        [
            InlineKeyboardButton(text="📢 Join Our Channel", url="https://t.me/YourChannelLink"),  # Replace with actual URL
        ],
        [
            InlineKeyboardButton(text="🔙 Back", callback_data="back")
        ]
    ]
    await message.reply(
        text=FORCE_MSG.format(
            first=message.from_user.first_name,
            last=message.from_user.last_name,
            username='@' + message.from_user.username if message.from_user.username else 'N/A',
            mention=message.from_user.mention,
            id=message.from_user.id
        ),
        reply_markup=InlineKeyboardMarkup(buttons),
        quote=True,
        disable_web_page_preview=True
    )

# Callback Query Handler for Closing Messages
@Bot.on_callback_query(filters.regex(r"^close$"))
async def close_callback(client: Client, callback_query: CallbackQuery):
    try:
        await callback_query.message.delete()
    except Exception as e:
        logger.error(f"Error deleting message: {e}")

# Run the Bot
if __name__ == "__main__":
    Bot.run()
