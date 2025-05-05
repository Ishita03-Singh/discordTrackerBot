import discord
import sqlite3
from datetime import datetime, timedelta
from discord.ext import commands
from discord import app_commands
import pytz

# Timezone
IST = pytz.timezone('Asia/Kolkata')

# SQLite Setup
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

# Function to calculate work hours
def get_hours(user_id=None, period='day'):
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
        return c.fetchone()[0] or 0
    else:
        c.execute("SELECT user_id, SUM(duration) FROM work_sessions WHERE start_time >= ? GROUP BY user_id", (start_range.isoformat(),))
        return c.fetchall()

# Bot Setup
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)
tree = bot.tree

@bot.event
async def on_ready():
    await tree.sync()
    print(f"✅ Bot is online as {bot.user}")

# Slash Commands

@tree.command(name="startwork", description="Start tracking work time")
async def startwork(interaction: discord.Interaction):
    user_id = interaction.user.id
    if user_id in active_sessions:
        await interaction.response.send_message("You're already clocked in.")
    else:
        active_sessions[user_id] = datetime.now(IST)
        await interaction.response.send_message(
            f"{interaction.user.display_name} started working at {active_sessions[user_id].strftime('%H:%M:%S')} IST."
        )

@tree.command(name="stopwork", description="Stop work and log time")
async def stopwork(interaction: discord.Interaction):
    user_id = interaction.user.id
    start_time = active_sessions.pop(user_id, None)
    if not start_time:
        await interaction.response.send_message("You haven't started working yet.")
    else:
        end_time = datetime.now(IST)
        duration = (end_time - start_time).total_seconds() / 3600
        c.execute('INSERT INTO work_sessions (user_id, start_time, end_time, duration) VALUES (?, ?, ?, ?)',
                  (user_id, start_time.isoformat(), end_time.isoformat(), duration))
        conn.commit()
        await interaction.response.send_message(
            f"{interaction.user.display_name} stopped working. Total: {duration:.2f} hours."
        )

@tree.command(name="workhours", description="Show your total work hours")
async def workhours(interaction: discord.Interaction):
    user_id = interaction.user.id
    c.execute('SELECT SUM(duration) FROM work_sessions WHERE user_id = ?', (user_id,))
    total = c.fetchone()[0] or 0
    await interaction.response.send_message(f"You’ve worked {total:.2f} hours total.")

@tree.command(name="resetwork", description="Reset your current session")
async def resetwork(interaction: discord.Interaction):
    active_sessions.pop(interaction.user.id, None)
    await interaction.response.send_message("Your current session has been reset.")

@tree.command(name="todayhours", description="Check today's work hours")
async def todayhours(interaction: discord.Interaction, member: discord.Member = None):
    target = member or interaction.user
    total = get_hours(target.id, 'day')
    await interaction.response.send_message(f"{target.display_name} has worked {total:.2f} hours today.")

@tree.command(name="weekhours", description="Check this week's work hours")
async def weekhours(interaction: discord.Interaction, member: discord.Member = None):
    target = member or interaction.user
    total = get_hours(target.id, 'week')
    await interaction.response.send_message(f"{target.display_name} has worked {total:.2f} hours this week.")

@tree.command(name="monthhours", description="Check this month's work hours")
async def monthhours(interaction: discord.Interaction, member: discord.Member = None):
    target = member or interaction.user
    total = get_hours(target.id, 'month')
    await interaction.response.send_message(f"{target.display_name} has worked {total:.2f} hours this month.")

@tree.command(name="leaderboard", description="Show the leaderboard (day/week/month)")
@app_commands.describe(period="Time period (day, week, month)")
async def leaderboard(interaction: discord.Interaction, period: str):
    period = period.lower()
    if period not in ['day', 'week', 'month']:
        await interaction.response.send_message("Invalid period. Use: day, week, or month.")
        return

    rows = get_hours(None, period)
    if not rows:
        await interaction.response.send_message(f"No work hours logged this {period}.")
        return

    leaderboard_text = "\n".join(
        f"<@{uid}>: {hrs:.2f} hrs" for uid, hrs in sorted(rows, key=lambda x: x[1], reverse=True)
    )
    await interaction.response.send_message(f"📊 Leaderboard ({period}):\n{leaderboard_text}")

# Run the bot
bot.run("MTM2ODY0OTc0NDExMjY4NTI4Nw.G99fmF.CvQBo29TjaUqYrn1binj8xcz6qdNmzPHOBt01U")
