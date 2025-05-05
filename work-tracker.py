import discord
import sqlite3
from datetime import datetime, timedelta

import pytz

# Define IST timezone
IST = pytz.timezone('Asia/Kolkata')

def get_hours(user_id=None, period='day'):
    global c
    now = datetime.now(IST)
    if period == 'day':
        start_range = now.replace(hour=0, minute=0, second=0, microsecond=0)
    elif period == 'week':
        start_range = now - timedelta(days=now.weekday())
        start_range = start_range.replace(hour=0, minute=0, second=0, microsecond=0)
    elif period == 'month':
        start_range = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    if user_id:
        c.execute("SELECT SUM(duration) FROM work_sessions WHERE user_id = ? AND start_time >= ?", (user_id, start_range.isoformat()))
        total = c.fetchone()[0] or 0
        return total
    else:
        c.execute("SELECT user_id, SUM(duration) FROM work_sessions WHERE start_time >= ? GROUP BY user_id", (start_range.isoformat(),))
        return c.fetchall()


intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True
intents.messages = True

client = discord.Client(intents=intents)

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

active_sessions = {}

@client.event
async def on_ready():
    print(f'Bot is online as {client.user}')

@client.event
async def on_message(message):
    if message.author.bot:
        return

    user_id = message.author.id
    content = message.content.lower()

    if content.startswith('/startwork'):
        if user_id in active_sessions:
            await message.channel.send("You're already clocked in.")
        else:
            active_sessions[user_id] = datetime.now(IST)
            await message.channel.send(f"{message.author.display_name} started working at {active_sessions[user_id].strftime('%H:%M:%S')}")

    elif content.startswith('/stopwork'):
        start_time = active_sessions.pop(user_id, None)
        if not start_time:
            await message.channel.send("You haven't started working yet.")
        else:
            end_time = datetime.now(IST)
            duration = (end_time - start_time).total_seconds() / 3600  # in hours
            c.execute('INSERT INTO work_sessions (user_id, start_time, end_time, duration) VALUES (?, ?, ?, ?)',
                      (user_id, start_time.isoformat(), end_time.isoformat(), duration))
            conn.commit()
            await message.channel.send(f"{message.author.display_name} stopped working. Total: {duration:.2f} hours")

    elif content.startswith('/workhours'):
        c.execute('SELECT SUM(duration) FROM work_sessions WHERE user_id = ?', (user_id,))
        total = c.fetchone()[0] or 0
        await message.channel.send(f"{message.author.display_name}, you’ve worked {total:.2f} hours total.")

    elif content.startswith('/resetwork'):
        active_sessions.pop(user_id, None)
        await message.channel.send("Your current session has been reset.")
    elif content.startswith('/todayhours'):
        target = message.mentions[0] if message.mentions else message.author
        total = get_hours(target.id, 'day')
        await message.channel.send(f"{target.display_name} has worked {total:.2f} hours today.")

    elif content.startswith('/weekhours'):
        target = message.mentions[0] if message.mentions else message.author
        total = get_hours(target.id, 'week')
        await message.channel.send(f"{target.display_name} has worked {total:.2f} hours this week.")

    elif content.startswith('/monthhours'):
        target = message.mentions[0] if message.mentions else message.author
        total = get_hours(target.id, 'month')
        await message.channel.send(f"{target.display_name} has worked {total:.2f} hours this month.")

    elif content.startswith('/leaderboard'):
        period = 'day'
        if 'week' in content:
            period = 'week'
        elif 'month' in content:
            period = 'month'

        rows = get_hours(None, period)
        if not rows:
            await message.channel.send(f"No work hours logged this {period}.")
        else:
            leaderboard = [f"<@{uid}>: {hrs:.2f} hrs" for uid, hrs in sorted(rows, key=lambda x: x[1], reverse=True)]
            await message.channel.send(f"📊 Leaderboard ({period}):\n" + "\n".join(leaderboard))

# Replace with your real token from Discord Developer Portal
client.run('MTM2ODY0OTc0NDExMjY4NTI4Nw.G99fmF.CvQBo29TjaUqYrn1binj8xcz6qdNmzPHOBt01U')
