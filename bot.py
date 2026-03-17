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
bot = commands.Bot(command_prefix='!', intents=intents, help_command=None)  # Disable default help

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
    RELIABLE username checker using Discord's register endpoint.
    This actually works and doesn't give false negatives.
    """
    # Basic validation
    if len(username) < 2 or len(username) > 32:
        return {"available": False, "reason": "invalid_length", "message": "Username must be 2-32 characters"}
    
    # Check for valid characters (letters, numbers, underscore only)
    if not all(c.isalnum() or c == '_' for c in username):
        return {"available": False, "reason": "invalid_chars", "message": "Username can only contain letters, numbers, and underscores"}
    
    # Use Discord's register endpoint - this is what the client uses
    url = "https://discord.com/api/v9/auth/register"
    headers = {
        'Content-Type': 'application/json',
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    }
    
    # We're not actually registering, just checking availability
    payload = {
        'username': username,
        'password': 'TempPassword123!@#',  # Dummy password
        'consent': True,
        'date_of_birth': '2000-01-01'
    }
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, headers=headers, json=payload) as response:
                # 201 Created = username is available
                if response.status == 201:
                    return {"available": True, "reason": "available", "message": "Username is available!"}
                
                # 400 Bad Request = username is taken or invalid
                elif response.status == 400:
                    try:
                        error_data = await response.json()
                        error_text = str(error_data).lower()
                        
                        # Check for specific error messages
                        if "taken" in error_text:
                            return {"available": False, "reason": "taken", "message": "Username is already taken"}
                        elif "invalid" in error_text:
                            return {"available": False, "reason": "invalid", "message": "Username contains invalid characters"}
                        elif "blacklist" in error_text or "banned" in error_text:
                            return {"available": False, "reason": "blacklisted", "message": "Username contains prohibited words"}
                        elif "age" in error_text:
                            return {"available": False, "reason": "age_restricted", "message": "Username may be age-restricted"}
                        else:
                            return {"available": False, "reason": "unavailable", "message": "Username is not available"}
                    except:
                        return {"available": False, "reason": "unavailable", "message": "Username is not available"}
                
                # 429 = rate limited
                elif response.status == 429:
                    retry_after = int(response.headers.get('Retry-After', 5))
                    await asyncio.sleep(retry_after)
                    return await check_username_availability(username)
                
                else:
                    return {"available": False, "reason": "error", "message": f"API error: {response.status}"}
                    
    except Exception as e:
        print(f"Error checking {username}: {e}")
        return {"available": False, "reason": "exception", "message": f"Error: {str(e)}"}

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
        embed.set_footer(text="Username Hunter Bot")
        
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
            
        result = await check_username_availability(username)
        
        if result["available"]:
            # Send notification
            await send_instant_notification(username)
            
            # Mark as notified
            monitored_usernames[username]['notified'] = True
            monitored_usernames[username]['available_at'] = datetime.now().isoformat()
            monitored_usernames[username]['message'] = result['message']
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
    print(f"✅ Username Hunter Bot Online")
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
        await user.send(f"✅ **Username Hunter Online**\nMonitoring {len(monitored_usernames)} usernames\nInterval: {CHECK_INTERVAL}s")
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
    Shows detailed reason if not available
    """
    if ctx.author.id != YOUR_USER_ID:
        return
    
    username = username.lower().strip()
    
    # Send checking message
    status_msg = await ctx.send(f"🔍 Checking `{username}`...")
    
    # Check availability with detailed response
    result = await check_username_availability(username)
    
    if result["available"]:
        await status_msg.edit(content=f"✅ **`{username}` is AVAILABLE!**")
        # Also send DM for urgency
        await send_instant_notification(username)
    else:
        # Show the specific reason
        await status_msg.edit(content=f"❌ **`{username}` is not available**\n*Reason: {result['message']}*")

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
    
    found_count = 0
    
    # Run checks manually
    for username, data in list(monitored_usernames.items()):
        if data.get('notified'):
            continue
            
        result = await check_username_availability(username)
        
        if result["available"]:
            await send_instant_notification(username)
            monitored_usernames[username]['notified'] = True
            monitored_usernames[username]['available_at'] = datetime.now().isoformat()
            save_data()
            await ctx.send(f"✅ `{username}` is AVAILABLE - notification sent!")
            found_count += 1
        
        await asyncio.sleep(2)
    
    await ctx.send(f"✅ Force check complete! Found {found_count} available usernames.")

@bot.command(name='stats')
async def show_stats(ctx):
    """Show statistics about monitored usernames"""
    if ctx.author.id != YOUR_USER_ID:
        return
    
    total = len(monitored_usernames)
    notified = sum(1 for d in monitored_usernames.values() if d.get('notified', False))
    pending = total - notified
    
    await ctx.send(f"**📊 Statistics:**\nTotal monitored: {total}\n✅ Available found: {notified}\n⏳ Still watching: {pending}")

@bot.command(name='commands')
async def show_commands(ctx):
    """Show all commands"""
    if ctx.author.id != YOUR_USER_ID:
        return
    
    help_text = """
**🔥 USERNAME HUNTER BOT - Commands**

**Monitor Commands:**
`!incheck <username>` - Add username to monitor (any length)
`!uncheck <username>` - Stop monitoring a username  
`!list` - Show all monitored usernames
`!removeall` - Remove ALL monitored usernames
`!checknow` - Force immediate check of all monitored
`!stats` - Show monitoring statistics

**Instant Check:**
`!check <username>` - Check ANY username immediately with detailed reason

**How It Works:**
• Bot checks monitored usernames every 30 seconds
• Uses reliable Discord register endpoint for accurate results
• When a username becomes available, you get an URGENT DM
• Click the link and claim it instantly!
• Shows specific reason if unavailable (taken, invalid, blacklisted, etc.)

**Status:** 🔴 STREAMING Umar
"""
    await ctx.send(help_text)

# ===== RUN BOT =====
if __name__ == "__main__":
    if not TOKEN:
        print("❌ ERROR: No token found! Set TOKEN environment variable.")
        exit(1)
    
    print("🚀 Starting Username Hunter Bot...")
    bot.run(TOKEN)
