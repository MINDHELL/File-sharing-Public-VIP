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
from datetime import datetime, timedelta
from pyrogram import Client, filters, __version__
from pyrogram.enums import ParseMode
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from pyrogram.errors import FloodWait, UserIsBlocked, InputUserDeactivated

from bot import Bot
from config import *
from helper_func import *
from database.database import add_user, del_user, full_userbase, present_user

from apscheduler.schedulers.asyncio import AsyncIOScheduler

client = MongoClient(DB_URI)  # Replace with your MongoDB URI
db = client[DB_NAME]  # Database name
pusers = db["pusers"]  # Collection for users
deletions = db["deletions"]  # Collection for scheduled deletions

delete_after = 600

# Scheduler setup
scheduler = AsyncIOScheduler()


# Function to schedule a message for deletion after a specific delay
async def schedule_message_deletion(chat_id, message_id, delete_after):
    # Calculate deletion time and store in database
    delete_at = datetime.now() + timedelta(seconds=delete_after)
    deletions.insert_one({
        "chat_id": chat_id,
        "message_id": message_id,
        "delete_at": delete_at
    })
    logging.info(f"Scheduled deletion for message {message_id} in chat {chat_id} at {delete_at}")

# Function to check for expired messages and delete them
async def delete_scheduled_messages():
    # Periodically check for messages to delete
    while True:
        current_time = datetime.now()
        messages_to_delete = deletions.find({"delete_at": {"$lt": current_time}})

        for deletion in messages_to_delete:
            chat_id, message_id = deletion["chat_id"], deletion["message_id"]
            try:
                await client.delete_messages(chat_id, message_id)
                deletions.delete_one({"_id": deletion["_id"]})  # Remove entry after deletion
                logging.info(f"Deleted message {message_id} in chat {chat_id}")
            except Exception as e:
                logging.error(f"Error deleting message {message_id} in chat {chat_id}: {e}")
        
        # Wait for a specified interval before checking again
        await asyncio.sleep(60

# Run the deletion check every 5 minutes
scheduler.add_job(delete_scheduled_messages, 'interval', minutes=5)
scheduler.start()
"""
# MongoDB Helper Functions (For deletions)
async def schedule_message_deletion(chat_id, message_id, delete_at):
    #Schedule the message to be deleted at a specified time.
    db.deletions.insert_one({
        "chat_id": chat_id,
        "message_id": message_id,
        "delete_at": delete_at
    })

async def delete_scheduled_messages():
    #Your function to delete scheduled messages
    current_time = datetime.now()
    deletions = db.deletions.find({"delete_at": {"$lt": current_time}}).to_list(length=None)
    messages_to_delete = []
    
    for deletion in deletions:
        messages_to_delete.append((deletion["chat_id"], deletion["message_id"]))
        await db.deletions.delete_one({"_id": deletion["_id"]})  # Remove entry after deletion

    for chat_id, message_id in messages_to_delete:
        try:
            await client.delete_messages(chat_id, message_id)
        except Exception as e:
            print(f"Error deleting message {message_id} in {chat_id}: {e}")

# Schedule the deletion task every 5 minutes
scheduler.add_job(delete_scheduled_messages, 'interval', minutes=5)

"""


# MongoDB Helper Functions
async def add_premium_user(user_id, duration_in_days):
    expiry_time = time.time() + (duration_in_days * 86400
                                 )  # Calculate expiry time in seconds
    pusers.update_one(
        {"user_id": user_id},
        {"$set": {
            "is_premium": True,
            "expiry_time": expiry_time
        }},
        upsert=True)


async def remove_premium_user(user_id):
    pusers.update_one({"user_id": user_id},
                      {"$set": {
                          "is_premium": False,
                          "expiry_time": None
                      }})


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


async def auto_delete_message(client,
                              chat_id,
                              message_id,
                              delay=3600):  # Set default delay to 1 hour
    await asyncio.sleep(delay)
    try:
        await client.delete_messages(chat_id, message_id)
    except Exception as e:
        logging.error(f"Failed to delete message: {e}")


# Bot command to handle /start command in private messages
@Client.on_message(filters.command('start') & filters.private)
async def start_command(client: Client, message: Message):
    user_id = message.from_user.id
    logger.info(f"Received /start command from user ID: {user_id}")

    # Check if the user exists in the database
    if not await present_user(user_id):
        try:
            await add_user(user_id)
            logger.info(f"Added new user with ID: {user_id}")
        except Exception as e:
            logger.error(f"Error adding user {user_id}: {e}")

    # Check if the user is a premium user
    premium_status = await is_premium_user(user_id)
    logger.info(f"Premium status for user {user_id}: {premium_status}")

    # Handle base64 encoded string if provided
    if len(message.text) > 7:
        base64_string = message.text.split(" ", 1)[1]
        is_premium_link = False
        logger.info(f"Base64 string received: {base64_string}")

        # Try to decode as a premium link
        try:
            decoded_string = await decode_premium(base64_string)
            is_premium_link = True
            logger.info("Decoded as premium link.")
        except Exception as e:
            # Fallback to decode as a normal link if not premium
            try:
                decoded_string = await decode(base64_string)
                logger.info("Decoded as normal link.")
            except Exception as e:
                logger.error(f"Decoding error: {e}")
                await message.reply_text("Invalid link provided. \n\nGet help /upi")
                return

        if "vip-" in decoded_string:
            logger.info(f"'vip-' detected in decoded string: {decoded_string}")
            if not premium_status:
                logger.warning("Access denied: User tried to access a VIP link without VIP status.")
                await message.reply_text(
                    "This VIP content is only accessible to premium (VIP) users! \n\nUpgrade to VIP to access. \nClick here /myplan"
                )
                return 

        # Check premium status if it's a premium link
        if is_premium_link and not premium_status:
            logger.warning("Access denied: User tried to use a premium link without premium status.")
            await message.reply_text("This link is for premium users only! \n\nUpgrade to access. \nClick here /myplan")
            return

        # Process message IDs based on decoded string
        argument = decoded_string.split("-")
        ids = []

        if len(argument) == 3:
            try:
                start = int(int(argument[1]) / abs(client.db_channel.id))
                end = int(int(argument[2]) / abs(client.db_channel.id))
                ids = list(range(start, end + 1)) if start <= end else list(range(end, start + 1))
                logger.info(f"Decoded message ID range: {ids}")
            except Exception as e:
                logger.error(f"Error decoding message ID range: {e}")
                return
        elif len(argument) == 2:
            try:
                ids = [int(int(argument[1]) / abs(client.db_channel.id))]
                logger.info(f"Decoded single message ID: {ids[0]}")
            except Exception as e:
                logger.error(f"Error decoding single message ID: {e}")
                return

        temp_msg = await message.reply("Please wait...")
        logger.info("Fetching messages...")

        try:
            messages = await get_messages(client, ids)

            for msg in messages:
                sent_message = await msg.copy(chat_id=message.from_user.id, protect_content=PROTECT_CONTENT)
                if sent_message:
                    await schedule_message_deletion(sent_message.chat.id, sent_message.id, delete_after)
                    logger.info(f"Message sent and scheduled for deletion: {sent_message.id}")
                await asyncio.sleep(0.5)
        except FloodWait as e:
            logger.warning(f"Rate limit hit. Waiting for {e.x} seconds.")
            await asyncio.sleep(e.x)
        finally:
            await temp_msg.delete()
            logger.info("Temp message deleted.")
    else:
        reply_markup = InlineKeyboardMarkup(
            [
                [InlineKeyboardButton("😊 About Me", callback_data="about"), InlineKeyboardButton("🔒 Close", callback_data="close")],
                [InlineKeyboardButton("✨ Upgrade to Premium" if not premium_status else "✨ Premium Content", callback_data="premium_content")],
            ]
        )
        welcome_text = (
            f"Welcome {message.from_user.first_name}! "
            + ("As a premium user, you have access to exclusive content!" if premium_status else "Enjoy using the bot. Upgrade to premium for more features! \n\nCheck Your current Plan : /myplan")
        )
        await message.reply_text(
            text=welcome_text,
            reply_markup=reply_markup,
            disable_web_page_preview=True,
            quote=True
        )
        logger.info(f"Sent welcome message to user {user_id} with premium status: {premium_status}")



#=====================================================================================##

WAIT_MSG = """"<b>Processing ...</b>"""

REPLY_ERROR = """<code>Use this command as a replay to any telegram message with out any spaces.</code>"""

#=====================================================================================##


@Bot.on_message(filters.command('start') & filters.private)
async def not_joined(client: Client, message: Message):
    buttons = [
        [
            InlineKeyboardButton(text="Join Channel", url=client.invitelink),
            InlineKeyboardButton(text="Join Channel", url=client.invitelink2),
        ],
        [
            InlineKeyboardButton(text="Join Channel", url=client.invitelink3),
            #InlineKeyboardButton(text="Join Channel", url=client.invitelink4),
        ]
    ]
    try:
        buttons.append([
            InlineKeyboardButton(
                text='Try Again',
                url=f"https://t.me/{client.username}?start={message.command[1]}"
            )
        ])
    except IndexError:
        pass

    await message.reply(text=FORCE_MSG.format(
        first=message.from_user.first_name,
        last=message.from_user.last_name,
        username=None if not message.from_user.username else '@' +
        message.from_user.username,
        mention=message.from_user.mention,
        id=message.from_user.id),
                        reply_markup=InlineKeyboardMarkup(buttons),
                        quote=True,
                        disable_web_page_preview=True)


@Bot.on_message(
    filters.command('users') & filters.private & filters.user(ADMINS))
async def get_users(client: Bot, message: Message):
    msg = await client.send_message(chat_id=message.chat.id, text=WAIT_MSG)
    users = await full_userbase()
    await msg.edit(f"{len(users)} users are using this bot")


@Bot.on_message(filters.private & filters.command('broadcast')
                & filters.user(ADMINS))
async def send_text(client: Bot, message: Message):
    if message.reply_to_message:
        query = await full_userbase()
        broadcast_msg = message.reply_to_message
        total = 0
        successful = 0
        blocked = 0
        deleted = 0
        unsuccessful = 0

        pls_wait = await message.reply(
            "<i>Broadcasting Message.. This will Take Some Time</i>")
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


"""
# Add /addpr command for admins to add premium subscription
@Bot.on_message(filters.command('addpr') & filters.private)
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
@Bot.on_message(filters.command('removepr') & filters.private)
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
"""
'''
# Add /myplan command for users to check their premium subscription status
@Bot.on_message(filters.command('myplan') & filters.private)
async def my_plan(client: Client, message: Message):
    is_premium, expiry_time = await get_user_subscription(message.from_user.id)
    if is_premium:
        time_left = expiry_time - time.time()
        days_left = int(time_left / 86400)
        await message.reply(f"Your premium subscription is active. Time left: {days_left} days.")
    else:
        await message.reply("You are not a premium user.")

# Add /plans command to show available subscription plans
@Bot.on_message(filters.command('plans') & filters.private)
async def show_plans(client: Client, message: Message):
    plans_text = """
Available Subscription Plans:

1. 7 Days Premium - $5
2. 30 Days Premium - $15
3. 90 Days Premium - $35

Use /upi to make the payment.
"""
    await message.reply(plans_text)

# Add /upi command to provide UPI payment details
@Bot.on_message(filters.command('upi') & filters.private)
async def upi_info(client: Client, message: Message):
    upi_text = """
To subscribe to premium, please make the payment via UPI.

UPI ID: your-upi-id@bank

After payment, contact the bot admin to activate your premium subscription.
"""
    await message.reply(upi_text)

'''
