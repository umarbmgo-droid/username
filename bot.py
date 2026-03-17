import discord
from discord.ext import commands, tasks
import aiohttp
import asyncio
import os
from datetime import datetime
import json

# ===== CONFIG =====
TOKEN = os.environ.get('TOKEN')  # Your bot token
YOUR_USER_ID = 361069640962801664  # Your Discord ID
CHECK_INTERVAL = 30  # Seconds between checks for monitored usernames

# ===== BOT SETUP =====
intents = discord.Intents.default()
intents.dm_messages = True
bot = commands.Bot(command_prefix='!', intents=intents)

# Store monitored usernames and notification status
monitored_usernames = {}  # {username: {"notified": False, "added_by": user_id, "added_at": timestamp}}
data_file = 'monitored_usernames.json'

# Load saved data
def load_data():
    global monitored_usernames
    try:
        if os.path.exists(data_file):
            with open(data_file, 'r') as f:
                monitored_usernames = json.load(f)
                print(f"📂 Loaded {len(monitored_usernames)} monitored usernames")
    except Exception as e:
        print(f"Error loading data: {e}")
        monitored_usernames = {}

def save_data():
    try:
        with open(data_file, 'w') as f:
            json.dump(monitored_usernames, f, indent=2)
    except Exception as e:
        print(f"Error saving data: {e}")

# Load on startup
load_data()

async def check_username_availability(username):
    """
    Check if a username is currently available/claimable on Discord.
    Returns True if available, False if not.
    """
    url = "https://discord.com/api/v9/users/@me"
    headers = {
        'Authorization': f'Bot {TOKEN}',
        'Content-Type': 'application/json'
    }
    
    payload = {'username': username}
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.patch(url, headers=headers, json=payload) as response:
                # 200 = available RIGHT NOW
                if response.status == 200:
                    return True
                # 400 = still unavailable (taken or on cooldown)
                elif response.status == 400:
                    return False
                # 429 = rate limited
                elif response.status == 429:
                    retry_after = int(response.headers.get('Retry-After', 5))
                    await asyncio.sleep(retry_after)
                    return await check_username_availability(username)
                else:
                    return False
    except Exception as e:
        print(f"Error checking {username}: {e}")
        return False

async def send_instant_notification(username):
    """Send urgent DM that username is now available"""
    try:
        user = await bot.fetch_user(YOUR_USER_ID)
        embed = discord.Embed(
            title="🚨 **USERNAME JUST BECAME AVAILABLE!**",
            description=f"**{username}** can now be claimed!",
            color=0x00ff00,
            timestamp=datetime.now()
        )
        embed.add_field(
            name="⏱️ Action Required",
            value=f"[CLAIM IT NOW!](https://discord.com/settings/profile)\nBe quick—someone else might snipe it!",
            inline=False
        )
        embed.set_footer(text="Cooldown Watcher Bot")
        
        await user.send(embed=embed)
        return True
    except Exception as e:
        print(f"Failed to send notification: {e}")
        return False

# ===== BACKGROUND TASK =====
@tasks.loop(seconds=CHECK_INTERVAL)
async def monitor_usernames():
    """Constantly check all monitored usernames"""
    if not monitored_usernames:
        return
    
    print(f"🔍 Checking {len(monitored_usernames)} monitored usernames...")
    
    for username, data in list(monitored_usernames.items()):
        # Skip if already notified
        if data.get('notified', False):
            continue
            
        is_available = await check_username_availability(username)
        
        if is_available:
            # Send notification
            await send_instant_notification(username)
            
            # Mark as notified
            monitored_usernames[username]['notified'] = True
            monitored_usernames[username]['available_at'] = datetime.now().isoformat()
            save_data()
            
            print(f"✅ {username} is now AVAILABLE - notification sent")
        
        # Small delay between checks to be nice
        await asyncio.sleep(2)

@monitor_usernames.before_loop
async def before_monitor():
    await bot.wait_until_ready()

# ===== EVENTS =====
@bot.event
async def on_ready():
    print(f"✅ Cooldown Watcher Bot Online")
    print(f"🤖 Bot: {bot.user.name}")
    print(f"👑 Owner: <@{YOUR_USER_ID}>")
    print(f"📊 Monitoring: {len(monitored_usernames)} usernames")
    print(f"⏱️  Check interval: {CHECK_INTERVAL} seconds")
    
    # Set streaming status
    await bot.change_presence(activity=discord.Streaming(
        name="Umar",
        url="https://www.twitch.tv/umar"
    ))
    
    # Send startup notification
    try:
        user = await bot.fetch_user(YOUR_USER_ID)
        await user.send(f"✅ **Cooldown Watcher Online**\nMonitoring {len(monitored_usernames)} usernames\nInterval: {CHECK_INTERVAL}s")
    except:
        pass
    
    # Start monitoring
    monitor_usernames.start()

# ===== COMMANDS =====
@bot.command(name='incheck')
async def incheck(ctx, username: str):
    """
    Add a username to monitor - will DM you instantly when available
    Usage: !incheck wnrk
    """
    if ctx.author.id != YOUR_USER_ID:
        return
    
    username = username.lower().strip()
    
    # Basic validation
    if not username:
        await ctx.send("❌ Please provide a username")
        return
    
    if len(username) < 2 or len(username) > 32:
        await ctx.send("❌ Username must be between 2-32 characters")
        return
    
    # Check if already monitoring
    if username in monitored_usernames:
        await ctx.send(f"⚠️ Already monitoring `{username}`")
        return
    
    # Add to monitoring
    monitored_usernames[username] = {
        "notified": False,
        "added_by": ctx.author.id,
        "added_at": datetime.now().isoformat()
    }
    save_data()
    
    await ctx.send(f"✅ Now monitoring `{username}` - I'll DM you the instant it becomes available!")

@bot.command(name='uncheck')
async def uncheck(ctx, username: str):
    """
    Stop monitoring a username
    Usage: !uncheck wnrk
    """
    if ctx.author.id != YOUR_USER_ID:
        return
    
    username = username.lower().strip()
    
    if username in monitored_usernames:
        del monitored_usernames[username]
        save_data()
        await ctx.send(f"✅ Stopped monitoring `{username}`")
    else:
        await ctx.send(f"❌ `{username}` is not being monitored")

@bot.command(name='check')
async def check(ctx, username: str):
    """
    Check ANY username immediately (any length)
    Usage: !check wnrk
    Usage: !check a
    Usage: !check reallylongusername
    """
    if ctx.author.id != YOUR_USER_ID:
        return
    
    username = username.lower().strip()
    
    # Basic validation
    if not username:
        await ctx.send("❌ Please provide a username")
        return
    
    if len(username) < 2 or len(username) > 32:
        await ctx.send("❌ Username must be between 2-32 characters")
        return
    
    # Send checking message
    status_msg = await ctx.send(f"🔍 Checking `{username}`...")
    
    # Check availability
    is_available = await check_username_availability(username)
    
    if is_available:
        await status_msg.edit(content=f"✅ **`{username}` is AVAILABLE right now!**")
        # Also send DM for urgency
        await send_instant_notification(username)
    else:
        await status_msg.edit(content=f"❌ **`{username}` is not available** (taken or on cooldown)")

@bot.command(name='list')
async def list_monitored(ctx):
    """List all monitored usernames and their status"""
    if ctx.author.id != YOUR_USER_ID:
        return
    
    if not monitored_usernames:
        await ctx.send("📭 No usernames being monitored")
        return
    
    # Build status list
    status_lines = []
    for username, data in monitored_usernames.items():
        status = "✅ AVAILABLE" if data.get('notified') else "⏳ Monitoring"
        added = datetime.fromisoformat(data['added_at']).strftime("%m/%d %H:%M") if 'added_at' in data else "unknown"
        status_lines.append(f"`{username}` - {status} (added: {added})")
    
    # Send in chunks if too long
    chunks = [status_lines[i:i+15] for i in range(0, len(status_lines), 15)]
    
    for i, chunk in enumerate(chunks):
        if i == 0:
            await ctx.send(f"**📋 Monitored Usernames ({len(monitored_usernames)}):**\n" + "\n".join(chunk))
        else:
            await ctx.send("\n".join(chunk))

@bot.command(name='removeall')
async def remove_all(ctx):
    """Remove ALL monitored usernames"""
    if ctx.author.id != YOUR_USER_ID:
        return
    
    if not monitored_usernames:
        await ctx.send("📭 No usernames to remove")
        return
    
    count = len(monitored_usernames)
    monitored_usernames.clear()
    save_data()
    
    await ctx.send(f"✅ Removed all {count} monitored usernames")

@bot.command(name='checknow')
async def check_now(ctx):
    """Force an immediate check of all monitored usernames"""
    if ctx.author.id != YOUR_USER_ID:
        return
    
    if not monitored_usernames:
        await ctx.send("📭 No usernames to check")
        return
    
    await ctx.send(f"🔍 Forcing check of {len(monitored_usernames)} usernames...")
    
    # Run checks manually
    for username, data in list(monitored_usernames.items()):
        if data.get('notified'):
            continue
            
        is_available = await check_username_availability(username)
        
        if is_available:
            await send_instant_notification(username)
            monitored_usernames[username]['notified'] = True
            monitored_usernames[username]['available_at'] = datetime.now().isoformat()
            save_data()
            await ctx.send(f"✅ `{username}` is AVAILABLE - notification sent!")
        
        await asyncio.sleep(2)
    
    await ctx.send("✅ Force check complete!")

@bot.command(name='commands', aliases=['cmds', 'help'])
async def custom_help(ctx):
    """Show all commands"""
    if ctx.author.id != YOUR_USER_ID:
        return
    
    help_text = """
**🔥 COOLDOWN WATCHER BOT - Commands**

**Monitor Commands:**
`!incheck <username>` - Add username to monitor (any length)
`!uncheck <username>` - Stop monitoring a username  
`!list` - Show all monitored usernames
`!removeall` - Remove ALL monitored usernames
`!checknow` - Force immediate check of all monitored

**Instant Check:**
`!check <username>` - Check ANY username immediately (any length)

**How It Works:**
• Bot checks monitored usernames every 30 seconds
• When a username becomes available, you get an URGENT DM
• Click the link and claim it instantly!
• Usernames on cooldown will trigger the moment they're free

**Status:** 🔴 STREAMING Umar
"""
    await ctx.send(help_text)

# ===== RUN BOT =====
if __name__ == "__main__":
    if not TOKEN:
        print("❌ ERROR: No token found! Set TOKEN environment variable.")
        exit(1)
    
    print("🚀 Starting Cooldown Watcher Bot...")
    bot.run(TOKEN)
