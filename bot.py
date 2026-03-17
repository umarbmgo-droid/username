import discord
from discord.ext import commands, tasks
import aiohttp
import asyncio
import string
import itertools
import os
from datetime import datetime

# ===== CONFIG =====
TOKEN = os.environ.get('TOKEN')  # Your bot token
YOUR_USER_ID = 361069640962801664  # Your Discord ID
CHECK_DELAY = 2  # Seconds between checks (be nice to Discord)

# Only letters (no numbers, no symbols)
LETTERS = string.ascii_lowercase  # a-z

# ===== BOT SETUP =====
intents = discord.Intents.default()
intents.dm_messages = True
bot = commands.Bot(command_prefix='!', intents=intents)

# Tracking progress (just in memory, resets if bot restarts)
checked_3l = 0
checked_4l = 0
found_3l = 0
found_4l = 0
current_scan = None  # '3l' or '4l'

@bot.event
async def on_ready():
    print(f"✅ Username Hunter Bot Online")
    print(f"🎯 Hunting 3 and 4 letter usernames")
    print(f"📬 Will DM all finds to <@{YOUR_USER_ID}>")
    print(f"⏱️  Delay: {CHECK_DELAY}s between checks")
    
    # Set the streaming status
    await bot.change_presence(activity=discord.Streaming(
        name="watching username for umar",
        url="https://www.twitch.tv/umar"  # Twitch URL required for streaming status
    ))
    
    # Ask what to scan first
    await send_to_dm(
        "🔍 **Username Hunter Bot Ready!**\n\n"
        "Type `!scan3` to start scanning 3-letter usernames\n"
        "Type `!scan4` to start scanning 4-letter usernames\n"
        "Type `!status` to see progress\n"
        "Type `!stop` to pause scanning\n\n"
        "⚠️ This will take a long time and send MANY messages!"
    )

async def check_username(username):
    """Check if username is available on Discord"""
    url = "https://discord.com/api/v9/users/@me"
    headers = {
        'Authorization': f'Bot {TOKEN}',
        'Content-Type': 'application/json'
    }
    
    payload = {'username': username}
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.patch(url, headers=headers, json=payload) as response:
                if response.status == 200:
                    return True  # Available!
                elif response.status == 400:
                    return False  # Taken
                elif response.status == 429:
                    # Rate limited - wait and retry
                    retry_after = int(response.headers.get('Retry-After', 5))
                    await asyncio.sleep(retry_after)
                    return await check_username(username)
                else:
                    return False
    except Exception as e:
        print(f"Error checking {username}: {e}")
        return None

async def send_to_dm(content):
    """Send message to your DM"""
    try:
        user = await bot.fetch_user(YOUR_USER_ID)
        await user.send(content)
    except Exception as e:
        print(f"Failed to send DM: {e}")

@bot.command()
async def scan3(ctx):
    """Scan all 3-letter usernames"""
    global current_scan, checked_3l, found_3l
    
    if ctx.author.id != YOUR_USER_ID:
        return
    
    if current_scan:
        await ctx.send(f"❌ Already scanning {current_scan}. Use `!stop` first.")
        return
    
    current_scan = '3l'
    checked_3l = 0
    found_3l = 0
    
    await ctx.send("🔍 **Starting scan of ALL 3-letter usernames**\nThis will take a while...")
    await send_to_dm("📋 **3-LETTER USERNAMES FOUND:**\n(New ones will appear here)")
    
    try:
        for letters in itertools.product(LETTERS, repeat=3):
            if current_scan != '3l':
                break  # Stop if interrupted
                
            username = ''.join(letters)
            checked_3l += 1
            
            # Check the username
            is_available = await check_username(username)
            
            if is_available:
                found_3l += 1
                # DM each found username immediately
                await send_to_dm(f"✅ **{username}** (3L)")
            
            # Progress update every 1000 checks
            if checked_3l % 1000 == 0:
                await send_to_dm(
                    f"📊 **Progress:** {checked_3l}/17,576 3-letter names checked\n"
                    f"✅ Found: {found_3l} available"
                )
            
            await asyncio.sleep(CHECK_DELAY)
        
        # Scan complete
        await send_to_dm(
            f"🏁 **3-LETTER SCAN COMPLETE!**\n"
            f"Checked: {checked_3l} usernames\n"
            f"Found: {found_3l} available\n\n"
            f"Scroll up to see all {found_3l} usernames!"
        )
        
    except Exception as e:
        await send_to_dm(f"❌ Error during scan: {e}")
    finally:
        current_scan = None

@bot.command()
async def scan4(ctx):
    """Scan all 4-letter usernames"""
    global current_scan, checked_4l, found_4l
    
    if ctx.author.id != YOUR_USER_ID:
        return
    
    if current_scan:
        await ctx.send(f"❌ Already scanning {current_scan}. Use `!stop` first.")
        return
    
    current_scan = '4l'
    checked_4l = 0
    found_4l = 0
    
    await ctx.send("🔍 **Starting scan of ALL 4-letter usernames**\nThis will take a VERY long time...")
    await send_to_dm("📋 **4-LETTER USERNAMES FOUND:**\n(New ones will appear here)")
    
    try:
        for letters in itertools.product(LETTERS, repeat=4):
            if current_scan != '4l':
                break  # Stop if interrupted
                
            username = ''.join(letters)
            checked_4l += 1
            
            # Check the username
            is_available = await check_username(username)
            
            if is_available:
                found_4l += 1
                # DM each found username immediately
                await send_to_dm(f"✅ **{username}** (4L)")
            
            # Progress update every 1000 checks
            if checked_4l % 1000 == 0:
                percent = (checked_4l / 456976) * 100
                await send_to_dm(
                    f"📊 **Progress:** {checked_4l:,}/456,976 4-letter names checked ({percent:.1f}%)\n"
                    f"✅ Found: {found_4l:,} available"
                )
            
            await asyncio.sleep(CHECK_DELAY)
        
        # Scan complete
        await send_to_dm(
            f"🏁 **4-LETTER SCAN COMPLETE!**\n"
            f"Checked: {checked_4l:,} usernames\n"
            f"Found: {found_4l:,} available\n\n"
            f"Scroll up to see all {found_4l:,} usernames!"
        )
        
    except Exception as e:
        await send_to_dm(f"❌ Error during scan: {e}")
    finally:
        current_scan = None

@bot.command()
async def stop(ctx):
    """Stop the current scan"""
    global current_scan
    
    if ctx.author.id != YOUR_USER_ID:
        return
    
    if current_scan:
        scan_type = current_scan
        current_scan = None
        await ctx.send(f"🛑 Stopped {scan_type} scan")
        await send_to_dm(f"🛑 **Scan stopped** at your request")
    else:
        await ctx.send("❌ No scan is running")

@bot.command()
async def status(ctx):
    """Check current scan status"""
    if ctx.author.id != YOUR_USER_ID:
        return
    
    if current_scan == '3l':
        percent = (checked_3l / 17576) * 100
        await ctx.send(
            f"📊 **Current Scan:** 3-letter\n"
            f"✅ Checked: {checked_3l}/17,576 ({percent:.1f}%)\n"
            f"🎯 Found: {found_3l} available"
        )
    elif current_scan == '4l':
        percent = (checked_4l / 456976) * 100
        await ctx.send(
            f"📊 **Current Scan:** 4-letter\n"
            f"✅ Checked: {checked_4l:,}/456,976 ({percent:.1f}%)\n"
            f"🎯 Found: {found_4l:,} available"
        )
    else:
        await ctx.send("📊 No scan currently running")

@bot.command()
async def help(ctx):
    """Show commands"""
    if ctx.author.id != YOUR_USER_ID:
        return
    
    help_text = """
**🔍 Username Hunter Bot Commands**

`!scan3` - Start scanning ALL 3-letter usernames (aaa-zzz)
`!scan4` - Start scanning ALL 4-letter usernames (aaaa-zzzz)
`!stop` - Stop current scan
`!status` - Check scan progress
`!help` - Show this menu

**How it works:**
- Bot DMs you every available username it finds
- Scroll up in DMs to see the complete list
- Scan will take days to complete (be patient!)
- Uses 2-second delay to avoid rate limits
- Status shows: "watching username for umar"
"""
    await ctx.send(help_text)

# ===== RUN BOT =====
if __name__ == "__main__":
    if not TOKEN:
        print("❌ ERROR: No token found!")
        exit(1)
    
    bot.run(TOKEN)
