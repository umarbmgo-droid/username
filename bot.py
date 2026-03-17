import discord
from discord.ext import commands, tasks
import aiohttp
import asyncio
import os
import random
import string
import json
from datetime import datetime
import itertools

# ===== CONFIG =====
TOKEN = os.environ.get('TOKEN')  # Your BOT token
YOUR_USER_ID = 361069640962801664  # Your Discord ID

# ===== BOT SETUP =====
intents = discord.Intents.default()
intents.dm_messages = True
bot = commands.Bot(command_prefix='!', intents=intents, help_command=None)

# Store settings and results
available_usernames = []
scanning_active = False
scan_type = None  # 'generate' or 'list'
scan_length = 0
scan_amount = 0
current_progress = 0
total_to_scan = 0
scan_start_time = None
delay_between_checks = 2  # seconds

# Character sets (from DSV)
LETTERS = string.ascii_lowercase
DIGITS = string.digits
PUNCTUATION = "_."  # Discord allows underscore and period

async def check_username_availability(username):
    """
    DSV's username checking method using Discord's pomelo-attempt endpoint
    """
    url = "https://discord.com/api/v9/users/@me/pomelo-attempt"
    headers = {
        'Authorization': f'Bot {TOKEN}',
        'Content-Type': 'application/json',
        'Origin': 'https://discord.com/'
    }
    
    payload = {'username': username}
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, headers=headers, json=payload) as response:
                if response.status == 200:
                    data = await response.json()
                    if data.get('taken') is False:
                        return {"available": True, "reason": "available", "message": "Username is available!"}
                    elif data.get('taken') is True:
                        return {"available": False, "reason": "taken", "message": "Username is already taken"}
                    else:
                        return {"available": False, "reason": "unknown", "message": "Unknown response"}
                
                elif response.status == 400:
                    try:
                        data = await response.json()
                        if 'taken' in str(data).lower():
                            return {"available": False, "reason": "taken", "message": "Username is taken"}
                        else:
                            return {"available": False, "reason": "invalid", "message": data.get('message', 'Invalid username')}
                    except:
                        return {"available": False, "reason": "error", "message": "Bad request"}
                
                elif response.status == 429:
                    retry_after = int(response.headers.get('Retry-After', 5))
                    await asyncio.sleep(retry_after)
                    return await check_username_availability(username)
                
                else:
                    return {"available": False, "reason": "error", "message": f"API error: {response.status}"}
                    
    except Exception as e:
        print(f"Error checking {username}: {e}")
        return {"available": False, "reason": "exception", "message": f"Error: {str(e)}"}

def generate_username(length, use_letters=True, use_digits=False, use_punctuation=False):
    """Generate a random username based on DSV's method"""
    chars = ""
    if use_letters:
        chars += LETTERS
    if use_digits:
        chars += DIGITS
    if use_punctuation:
        chars += PUNCTUATION
    
    return ''.join(random.sample(chars, length))

async def send_dm_result(username, result):
    """Send result to user's DM"""
    try:
        user = await bot.fetch_user(YOUR_USER_ID)
        
        if result["available"]:
            embed = discord.Embed(
                title="✅ USERNAME AVAILABLE!",
                description=f"**{username}**",
                color=0x00ff00,
                timestamp=datetime.now()
            )
            embed.add_field(name="Action", value="[Claim it now!](https://discord.com/settings/profile)", inline=False)
        else:
            embed = discord.Embed(
                title="❌ Username Taken",
                description=f"**{username}** - {result['message']}",
                color=0xff0000,
                timestamp=datetime.now()
            )
        
        await user.send(embed=embed)
    except Exception as e:
        print(f"Failed to send DM: {e}")

async def send_progress_update():
    """Send progress update to DM"""
    try:
        user = await bot.fetch_user(YOUR_USER_ID)
        
        elapsed = datetime.now() - scan_start_time
        elapsed_str = str(elapsed).split('.')[0]  # Remove microseconds
        
        percent = (current_progress / total_to_scan) * 100 if total_to_scan > 0 else 0
        
        embed = discord.Embed(
            title="📊 Scan Progress",
            description=f"**Type:** {'Generating' if scan_type == 'generate' else 'Checking list'}\n"
                       f"**Progress:** {current_progress}/{total_to_scan} ({percent:.1f}%)\n"
                       f"**Found:** {len(available_usernames)} available\n"
                       f"**Elapsed:** {elapsed_str}\n"
                       f"**Delay:** {delay_between_checks}s",
            color=0x3498db
        )
        
        await user.send(embed=embed)
    except Exception as e:
        print(f"Failed to send progress: {e}")

@bot.event
async def on_ready():
    print(f"✅ DSV Bot Online")
    print(f"🤖 Bot: {bot.user.name}")
    print(f"👑 Owner: <@{YOUR_USER_ID}>")
    
    # Set streaming status
    await bot.change_presence(activity=discord.Streaming(
        name="Umar",
        url="https://www.twitch.tv/umar"
    ))
    
    # Send startup message
    try:
        user = await bot.fetch_user(YOUR_USER_ID)
        await user.send(
            "**🔍 DSV Username Checker Bot Ready!**\n\n"
            "**Commands:**\n"
            "`!scan <length> <amount>` - Generate and check random usernames\n"
            "`!scanlist` - Check usernames from usernames.txt\n"
            "`!stop` - Stop current scan\n"
            "`!progress` - Show current progress\n"
            "`!results` - Show all found usernames\n"
            "`!setdelay <seconds>` - Set delay between checks\n"
            "`!config` - Show current settings\n"
            "`!commands` - Show this menu"
        )
    except:
        pass

@tasks.loop(seconds=1)
async def scan_task():
    global scanning_active, current_progress, available_usernames
    
    if not scanning_active:
        return
    
    # This is just a placeholder - actual scanning is done in the commands
    # to maintain proper async flow
    pass

@bot.command(name='scan')
async def scan_generate(ctx, length: int = None, amount: int = None):
    """Generate and scan random usernames
    Usage: !scan 4 1000 (checks 1000 random 4-letter usernames)
    """
    global scanning_active, scan_type, scan_length, scan_amount, current_progress, total_to_scan, scan_start_time, available_usernames
    
    if ctx.author.id != YOUR_USER_ID:
        return
    
    if scanning_active:
        await ctx.send("❌ A scan is already in progress. Use `!stop` first.")
        return
    
    if not length or not amount:
        await ctx.send("❌ Usage: `!scan <length> <amount>`\nExample: `!scan 4 1000`")
        return
    
    if length < 2 or length > 32:
        await ctx.send("❌ Length must be between 2-32 characters")
        return
    
    if amount < 1 or amount > 10000:
        await ctx.send("❌ Amount must be between 1-10000")
        return
    
    scanning_active = True
    scan_type = 'generate'
    scan_length = length
    scan_amount = amount
    current_progress = 0
    total_to_scan = amount
    available_usernames = []
    scan_start_time = datetime.now()
    
    await ctx.send(f"🔍 Starting scan: Generating {amount} random {length}-character usernames...")
    
    try:
        for i in range(amount):
            if not scanning_active:
                break
            
            # Generate random username (using DSV method)
            username = generate_username(length, use_letters=True, use_digits=False, use_punctuation=False)
            
            # Check availability
            result = await check_username_availability(username)
            
            if result["available"]:
                available_usernames.append(username)
                await send_dm_result(username, result)
            
            current_progress += 1
            
            # Progress update every 100 checks
            if current_progress % 100 == 0:
                await send_progress_update()
            
            await asyncio.sleep(delay_between_checks)
        
        # Scan complete
        elapsed = datetime.now() - scan_start_time
        elapsed_str = str(elapsed).split('.')[0]
        
        await ctx.send(
            f"✅ **Scan Complete!**\n"
            f"Checked: {current_progress} usernames\n"
            f"Found: {len(available_usernames)} available\n"
            f"Time: {elapsed_str}"
        )
        
        if available_usernames:
            # Send list of found usernames
            chunks = [available_usernames[i:i+20] for i in range(0, len(available_usernames), 20)]
            for chunk in chunks:
                await ctx.send("📋 Available usernames:\n" + "\n".join([f"✅ {u}" for u in chunk]))
        
    except Exception as e:
        await ctx.send(f"❌ Error during scan: {str(e)}")
    finally:
        scanning_active = False

@bot.command(name='scanlist')
async def scan_list(ctx):
    """Check usernames from usernames.txt file"""
    global scanning_active, scan_type, current_progress, total_to_scan, scan_start_time, available_usernames
    
    if ctx.author.id != YOUR_USER_ID:
        return
    
    if scanning_active:
        await ctx.send("❌ A scan is already in progress. Use `!stop` first.")
        return
    
    # Check if usernames.txt exists
    if not os.path.exists('usernames.txt'):
        await ctx.send("❌ usernames.txt not found. Please create it with one username per line.")
        return
    
    # Read usernames from file
    with open('usernames.txt', 'r') as f:
        usernames = [line.strip() for line in f if line.strip()]
    
    if not usernames:
        await ctx.send("❌ usernames.txt is empty")
        return
    
    scanning_active = True
    scan_type = 'list'
    current_progress = 0
    total_to_scan = len(usernames)
    available_usernames = []
    scan_start_time = datetime.now()
    
    await ctx.send(f"🔍 Starting scan: Checking {len(usernames)} usernames from list...")
    
    try:
        for username in usernames:
            if not scanning_active:
                break
            
            # Check availability
            result = await check_username_availability(username)
            
            if result["available"]:
                available_usernames.append(username)
                await send_dm_result(username, result)
            
            current_progress += 1
            
            # Progress update every 50 checks
            if current_progress % 50 == 0:
                await send_progress_update()
            
            await asyncio.sleep(delay_between_checks)
        
        # Scan complete
        elapsed = datetime.now() - scan_start_time
        elapsed_str = str(elapsed).split('.')[0]
        
        await ctx.send(
            f"✅ **Scan Complete!**\n"
            f"Checked: {current_progress}/{total_to_scan} usernames\n"
            f"Found: {len(available_usernames)} available\n"
            f"Time: {elapsed_str}"
        )
        
        if available_usernames:
            # Send list of found usernames
            chunks = [available_usernames[i:i+20] for i in range(0, len(available_usernames), 20)]
            for chunk in chunks:
                await ctx.send("📋 Available usernames:\n" + "\n".join([f"✅ {u}" for u in chunk]))
        
    except Exception as e:
        await ctx.send(f"❌ Error during scan: {str(e)}")
    finally:
        scanning_active = False

@bot.command(name='stop')
async def stop_scan(ctx):
    """Stop the current scan"""
    global scanning_active
    
    if ctx.author.id != YOUR_USER_ID:
        return
    
    if scanning_active:
        scanning_active = False
        await ctx.send("🛑 Scan stopped")
    else:
        await ctx.send("❌ No scan is running")

@bot.command(name='progress')
async def show_progress(ctx):
    """Show current scan progress"""
    if ctx.author.id != YOUR_USER_ID:
        return
    
    if not scanning_active:
        await ctx.send("📊 No scan currently running")
        return
    
    await send_progress_update()
    await ctx.send("✅ Progress sent to DMs")

@bot.command(name='results')
async def show_results(ctx):
    """Show all found usernames from current scan"""
    if ctx.author.id != YOUR_USER_ID:
        return
    
    if not available_usernames:
        await ctx.send("📭 No usernames found yet")
        return
    
    # Send results in chunks
    chunks = [available_usernames[i:i+20] for i in range(0, len(available_usernames), 20)]
    for chunk in chunks:
        await ctx.send("📋 **Available usernames:**\n" + "\n".join([f"✅ {u}" for u in chunk]))

@bot.command(name='setdelay')
async def set_delay(ctx, seconds: float = None):
    """Set delay between checks (seconds)"""
    global delay_between_checks
    
    if ctx.author.id != YOUR_USER_ID:
        return
    
    if seconds is None:
        await ctx.send(f"⏱️ Current delay: {delay_between_checks}s")
        return
    
    if seconds < 0.5:
        await ctx.send("❌ Delay must be at least 0.5 seconds")
        return
    
    delay_between_checks = seconds
    await ctx.send(f"✅ Delay set to {seconds} seconds")

@bot.command(name='config')
async def show_config(ctx):
    """Show current configuration"""
    if ctx.author.id != YOUR_USER_ID:
        return
    
    config_text = f"""
**🔧 Current Configuration**

**Scan Settings:**
• Delay between checks: `{delay_between_checks}s`
• Character sets: Letters only (a-z)

**Current Status:**
• Scan active: `{scanning_active}`
• Type: `{scan_type or 'None'}`
• Progress: `{current_progress}/{total_to_scan}` ({((current_progress/total_to_scan)*100) if total_to_scan > 0 else 0:.1f}%)
• Found: `{len(available_usernames)}` usernames

**Commands:**
`!scan <length> <amount>` - Generate random usernames
`!scanlist` - Check from file
`!stop` - Stop scan
`!progress` - Show progress
`!results` - Show found usernames
`!setdelay <seconds>` - Change delay
`!config` - Show this menu
"""
    await ctx.send(config_text)

@bot.command(name='commands')
async def show_commands(ctx):
    """Show all commands"""
    if ctx.author.id != YOUR_USER_ID:
        return
    
    help_text = """
**🔍 DSV USERNAME CHECKER BOT - Commands**

**Scan Commands:**
`!scan <length> <amount>` - Generate and scan random usernames
  Example: `!scan 4 1000` (checks 1000 random 4-letter usernames)

`!scanlist` - Check usernames from `usernames.txt` file

**Control Commands:**
`!stop` - Stop current scan
`!progress` - Show progress in DMs
`!results` - Show all found usernames
`!setdelay <seconds>` - Set delay between checks (default: 2s)

**Info Commands:**
`!config` - Show current configuration
`!commands` - Show this menu

**How it works:**
• Uses DSV's pomelo-attempt endpoint for accurate checking
• Results are DM'd to you instantly
• Progress updates every 100 checks
• All found usernames are saved in memory

**Status:** 🔴 STREAMING Umar
"""
    await ctx.send(help_text)

# ===== RUN BOT =====
if __name__ == "__main__":
    if not TOKEN:
        print("❌ ERROR: No token found! Set TOKEN environment variable.")
        exit(1)
    
    print("🚀 Starting DSV Bot...")
    bot.run(TOKEN)
