import discord
from discord import app_commands
from discord.ext import commands
import os
import sqlite3
from datetime import datetime, timedelta
import pytz
from flask import Flask
from threading import Thread

app = Flask('')


@app.route('/')
def home():
    return "Bot is alive!"


def run():
    app.run(host='0.0.0.0', port=8080)


def keep_alive():
    t = Thread(target=run)
    t.start()


intents = discord.Intents.default()
intents.message_content = True  # Required to read messages

client = discord.Client(intents=intents)
bot = commands.Bot(command_prefix='/', intents=intents)

# Define IST timezone
IST = pytz.timezone('Asia/Kolkata')

# SQLite DB setup
conn = sqlite3.connect('text_work_hours.db')
c = conn.cursor()
c.execute('''
CREATE TABLE IF NOT EXISTS work_sessions (
    user_id INTEGER,
    start_time TEXT,
    end_time TEXT,
    duration REAL
)
''')
conn.commit()


# Function to get work hours for a given user and period (day, week, month)
def get_hours(user_id=None, period='day'):
    global c
    now = datetime.now(IST)
    if period == 'day':
        start_range = now.replace(hour=0, minute=0, second=0, microsecond=0)
    elif period == 'week':
        start_range = now - timedelta(days=now.weekday())
        start_range = start_range.replace(hour=0,
                                          minute=0,
                                          second=0,
                                          microsecond=0)
    elif period == 'month':
        start_range = now.replace(day=1,
                                  hour=0,
                                  minute=0,
                                  second=0,
                                  microsecond=0)

    if user_id:
        c.execute(
            "SELECT SUM(duration) FROM work_sessions WHERE user_id = ? AND start_time >= ?",
            (user_id, start_range.isoformat()))
        total = c.fetchone()[0] or 0
        return total
    else:
        c.execute(
            "SELECT user_id, SUM(duration) FROM work_sessions WHERE start_time >= ? GROUP BY user_id",
            (start_range.isoformat(), ))
        return c.fetchall()


# Active session tracking
active_sessions = {}


# Slash Command: Start Work
@bot.tree.command(name="startwork")
async def startwork(interaction: discord.Interaction):
    user_id = interaction.user.id
    if user_id in active_sessions:
        await interaction.response.send_message("You're already clocked in.")
    else:
        active_sessions[user_id] = datetime.now(IST)
        await interaction.response.send_message(
            f"{interaction.user.display_name} started working at {active_sessions[user_id].strftime('%H:%M:%S')}"
        )


# Slash Command: Stop Work
@bot.tree.command(name="stopwork")
async def stopwork(interaction: discord.Interaction):
    user_id = interaction.user.id
    start_time = active_sessions.pop(user_id, None)
    if not start_time:
        await interaction.response.send_message(
            "You haven't started working yet.")
    else:
        end_time = datetime.now(IST)
        duration = (end_time - start_time).total_seconds() / 3600  # in hours
        c.execute(
            'INSERT INTO work_sessions (user_id, start_time, end_time, duration) VALUES (?, ?, ?, ?)',
            (user_id, start_time.isoformat(), end_time.isoformat(), duration))
        conn.commit()
        await interaction.response.send_message(
            f"{interaction.user.display_name} stopped working. Total: {duration:.2f} hours"
        )


# Slash Command: Reset Work Session
@bot.tree.command(name="resetwork")
async def resetwork(interaction: discord.Interaction):
    user_id = interaction.user.id
    active_sessions.pop(user_id, None)
    await interaction.response.send_message(
        "Your current session has been reset.")


# Slash Command: Get Today's Work Hours
@bot.tree.command(name="todayhours")
async def todayhours(interaction: discord.Interaction,
                     user: discord.User = None):
    target = user or interaction.user  # If no user is mentioned, use the command user's ID
    total = get_hours(target.id, 'day')
    await interaction.response.send_message(
        f"{target.display_name} has worked {total:.2f} hours today.")


# Slash Command: Get Work Hours for the Month
@bot.tree.command(name="monthhours")
async def monthhours(interaction: discord.Interaction,
                     user: discord.User = None):
    target = user or interaction.user  # If no user is mentioned, use the command user's ID
    total = get_hours(target.id, 'month')
    await interaction.response.send_message(
        f"{target.display_name} has worked {total:.2f} hours this month.")


# Slash Command: Work Leaderboard
@bot.tree.command(name="leaderboard")
async def leaderboard(interaction: discord.Interaction, period: str = 'day'):
    rows = get_hours(None, period)
    if not rows:
        await interaction.response.send_message(
            f"No work hours logged this {period}.")
    else:
        leaderboard = [
            f"<@{uid}>: {hrs:.2f} hrs"
            for uid, hrs in sorted(rows, key=lambda x: x[1], reverse=True)
        ]
        await interaction.response.send_message(
            f"📊 Leaderboard ({period}):\n" + "\n".join(leaderboard))


# Event: Sync Commands on Ready
@bot.event
async def on_ready():
    await bot.tree.sync()  # Sync the slash commands with Discord
    print(f'Bot is online as {bot.user}')


# Run the bot with your Discord token
TOKEN = os.getenv("DISCORD_TOKEN")
keep_alive()
bot.run(TOKEN)
