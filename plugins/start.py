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
from hashlib import sha256
from bot import Bot
from config import *
from helper_func import *
from database.database import add_user, del_user, full_userbase, present_user
#from apscheduler.schedulers.asyncio import AsyncIOScheduler


client = MongoClient(DB_URI)  # Replace with your MongoDB URI
db = client[DB_NAME]  # Database name
pusers = db["pusers"]  # Collection for users

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
    user = pusers.find_one({"user_id": user_i
                            d})
    if user:
        return user.get("is_premium", False), user.get("expiry_time", None)
    return False, None

async def is_premium_user(user_id):
    is_premium, expiry_time = await get_user_subscription(user_id)
    if is_premium and expiry_time > time.time():
        return True
    return False

async def auto_delete_message(client, chat_id, message_id, delay=3600):  # Set default delay to 1 hour
    await asyncio.sleep(delay)
    try:
        await client.delete_messages(chat_id, message_id)
    except Exception as e:
        logging.error(f"Failed to delete message: {e}")



@Bot.on_message(filters.command('start') & filters.private & subscribed)
async def start_command(client: Client, message: Message):
    user_id = message.from_user.id

    # Check if the user exists in the database
    if not await present_user(user_id):
        try:
            await add_user(user_id)
            logging.info(f"Added new user: {user_id}")
        except Exception as e:
            logging.error(f"Error adding user {user_id}: {e}")

    # Check if the user is a premium user
    premium_status = await is_premium_user(user_id)

    # Handle encoded string in the message (if provided)
    if len(message.text) > 7:
        encoded_string = message.text.split(" ", 1)[1]
        if not encoded_string:
            return

        # Log the encoded string for debugging
        logging.info(f"Encoded string received: {encoded_string}")

        try:
            # Multi-step decoding logic
            decoded_string = encoded_string
            while "get-" not in decoded_string and "base64" in decoded_string:
                # Decode the string repeatedly if "base64" is found after each decode
                decoded_string = await decode(decoded_string)

            if decoded_string is None or "get-" in decoded_string:
                await message.reply_text("This link is for premium users only! Upgrade to access.")
                return
            
            logging.info(f"Decoded string: {decoded_string}")

            # Process the decoded message and extract message IDs
            argument = decoded_string.split("-")
            ids = []

            # Logic to calculate message IDs
            if len(argument) == 3:
                start = int(argument[1]) // abs(client.db_channel.id)
                end = int(argument[2]) // abs(client.db_channel.id)
                ids = range(start, end + 1) if start <= end else []
            elif len(argument) == 2:
                ids = [int(argument[1]) // abs(client.db_channel.id)]

            temp_msg = await message.reply("Please wait... 1")

            # Fetch and send the requested messages
            try:
                messages = await get_messages(client, ids)
            except Exception as e:
                await message.reply_text("Something went wrong while fetching messages!")
                logging.error(f"Error fetching messages: {e}")
                return

            await temp_msg.delete()

            for msg in messages:
                caption = (
                    CUSTOM_CAPTION.format(previouscaption=msg.caption.html, filename=msg.document.file_name)
                    if CUSTOM_CAPTION and msg.document else msg.caption or ""
                )
                reply_markup = None if DISABLE_CHANNEL_BUTTON else msg.reply_markup

                try:
                    sent_message = await msg.copy(
                        chat_id=user_id,
                        caption=caption,
                        parse_mode="HTML",
                        reply_markup=reply_markup,
                        protect_content=PROTECT_CONTENT
                    )
                    # Schedule auto-delete task for sent message
                    asyncio.create_task(auto_delete_message(client, sent_message.chat.id, sent_message.id, delay=3600))
                    await asyncio.sleep(0.5)
                except FloodWait as e:
                    await asyncio.sleep(e.x)
                    sent_message = await msg.copy(
                        chat_id=user_id,
                        caption=caption,
                        parse_mode="HTML",
                        reply_markup=reply_markup,
                        protect_content=PROTECT_CONTENT
                    )
                    asyncio.create_task(auto_delete_message(client, sent_message.chat.id, sent_message.id, delay=3600))
                except Exception as e:
                    logging.error(f"Error sending message copy: {e}")

        except ValueError:
            await message.reply_text("Invalid link format.")
            logging.error("Invalid link format received.")
            return
        except Exception as e:
            logging.error(f"Error processing encoded string: {e}")
            await message.reply_text("An error occurred while processing the link.")
            return

    else:
        # Default reply if no encoded link is provided
        reply_markup = InlineKeyboardMarkup([
            [InlineKeyboardButton("😊 About Me", callback_data="about"),
             InlineKeyboardButton("🔒 Close", callback_data="close")],
            [InlineKeyboardButton("✨ Upgrade to Premium" if not premium_status else "✨ Premium Content", callback_data="premium_content")]
        ])
        welcome_text = f"Welcome {message.from_user.first_name}! " + (
            "As a premium user, you have access to exclusive content!"
            if premium_status else
            "Enjoy using the bot. Upgrade to premium for more features!"
        )
        await message.reply_text(
            text=welcome_text,
            reply_markup=reply_markup,
            disable_web_page_preview=True,
            quote=True
        )
        


    
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



@Bot.on_message(filters.command('users') & filters.private & filters.user(ADMINS))
async def get_users(client: Bot, message: Message):
    msg = await client.send_message(chat_id=message.chat.id, text=WAIT_MSG)
    users = await full_userbase()
    await msg.edit(f"{len(users)} users are using this bot")

@Bot.on_message(filters.private & filters.command('broadcast') & filters.user(ADMINS))
async def send_text(client: Bot, message: Message):
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
