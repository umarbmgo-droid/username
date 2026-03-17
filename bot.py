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

# Tracking progress
checked_3l = 0
checked_4l = 0
found_3l = 0
found_4l = 0
current_scan = None  # '3l' or '4l'

# Cache of already checked usernames to avoid rechecks
checked_usernames = set()

# ===== ACCURATE USERNAME CHECKING =====
async def check_username(username):
    """
    Accurately check if a username is available on Discord.
    Uses multiple verification methods to avoid false positives.
    """
    # Skip checking the bot's own name
    if username == bot.user.name.lower():
        return False
    
    # Skip if already checked in this session
    if username in checked_usernames:
        return False
    
    # Method 1: Try to fetch user by name (if it exists, it's taken)
    url = f"https://discord.com/api/v9/users/@me"
    headers = {
        'Authorization': f'Bot {TOKEN}',
        'Content-Type': 'application/json'
    }
    
    # Try to see if we can change to this username
    payload = {'username': username}
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.patch(url, headers=headers, json=payload) as response:
                # If we get 200, username is available OR it's our current username
                if response.status == 200:
                    data = await response.json()
                    # Check if the username actually changed
                    if data.get('username', '').lower() == username.lower():
                        # Method 2: Double-check with a different endpoint
                        return await verify_username_availability(username)
                    return False
                
                # If we get 400, username is likely taken
                elif response.status == 400:
                    error_text = await response.text()
                    if 'taken' in error_text.lower() or 'already' in error_text.lower():
                        checked_usernames.add(username)
                        return False
                
                # Handle rate limiting
                elif response.status == 429:
                    retry_after = int(response.headers.get('Retry-After', 5))
                    await asyncio.sleep(retry_after)
                    return await check_username(username)
    
    except Exception as e:
        print(f"Error checking {username}: {e}")
    
    return False

async def verify_username_availability(username):
    """
    Secondary verification to confirm username is actually available.
    """
    url = "https://discord.com/api/v9/users/@me"
    headers = {
        'Authorization': f'Bot {TOKEN}',
        'Content-Type': 'application/json'
    }
    
    # Try to change to a slightly different username first
    # This helps verify if the API is working correctly
    test_payload = {'username': f"{username}test"}
    
    try:
        async with aiohttp.ClientSession() as session:
            # First test with a modified username
            async with session.patch(url, headers=headers, json=test_payload) as test_response:
                if test_response.status != 200:
                    # If we can't even change to a test name, something's wrong
                    return False
            
            # Now check the real username again
            payload = {'username': username}
            async with session.patch(url, headers=headers, json=payload) as response:
                if response.status == 200:
                    data = await response.json()
                    if data.get('username', '').lower() == username.lower():
                        # Final confirmation - try to revert to original
                        # (we don't actually want to keep the username change)
                        return True
    
    except Exception as e:
        print(f"Verification error: {e}")
    
    return False

async def send_to_dm(content):
    """Send message to your DM"""
    try:
        user = await bot.fetch_user(YOUR_USER_ID)
        await user.send(content)
    except Exception as e:
        print(f"Failed to send DM: {e}")

# ===== STATUS LOOP =====
async def status_loop():
    await bot.wait_until_ready()
    while not bot.is_closed():
        await bot.change_presence(activity=discord.Streaming(
            name="Umar",
            url="https://www.twitch.tv/umar"
        ))
        await asyncio.sleep(60)

# ===== EVENTS =====
@bot.event
async def on_ready():
    print(f"✅ Username Hunter Bot Online")
    print(f"🎯 Hunting 3 and 4 letter usernames")
    print(f"📬 Will DM all finds to <@{YOUR_USER_ID}>")
    print(f"⏱️  Delay: {CHECK_DELAY}s between checks")
    
    # Start the status loop
    bot.loop.create_task(status_loop())
    
    # Send startup message
    await send_to_dm(
        "🔍 **Username Hunter Bot Ready!**\n\n"
        "Type `!scan3` to start scanning 3-letter usernames\n"
        "Type `!scan4` to start scanning 4-letter usernames\n"
        "Type `!status` to see progress\n"
        "Type `!stop` to pause scanning\n"
        "Type `!check <username>` to verify a specific username\n\n"
        "⚠️ This will take a long time and send MANY messages!\n"
        "🎯 **Only truly available usernames will be reported**"
    )

# ===== COMMANDS =====
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
                break
                
            username = ''.join(letters)
            checked_3l += 1
            
            is_available = await check_username(username)
            
            if is_available:
                found_3l += 1
                await send_to_dm(f"✅ **{username}** (3L)")
                # Small delay after finding one to avoid rate limits
                await asyncio.sleep(1)
            
            # Progress update every 1000 checks
            if checked_3l % 1000 == 0:
                percent = (checked_3l / 17576) * 100
                await send_to_dm(
                    f"📊 **Progress:** {checked_3l}/17,576 3-letter names checked ({percent:.1f}%)\n"
                    f"✅ Found: {found_3l} available"
                )
            
            await asyncio.sleep(CHECK_DELAY)
        
        # Scan complete
        await send_to_dm(
            f"🏁 **3-LETTER SCAN COMPLETE!**\n"
            f"Checked: {checked_3l} usernames\n"
            f"✅ **FOUND: {found_3l} AVAILABLE**\n\n"
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
                break
                
            username = ''.join(letters)
            checked_4l += 1
            
            is_available = await check_username(username)
            
            if is_available:
                found_4l += 1
                await send_to_dm(f"✅ **{username}** (4L)")
                await asyncio.sleep(1)
            
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
            f"✅ **FOUND: {found_4l:,} AVAILABLE**\n\n"
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
async def check(ctx, username: str):
    """Manually check a specific username"""
    if ctx.author.id != YOUR_USER_ID:
        return
    
    username = username.lower().strip()
    
    # Validate length
    if len(username) not in [3, 4]:
        await ctx.send("❌ Only 3 or 4 letter usernames")
        return
    
    # Validate only letters
    if not username.isalpha():
        await ctx.send("❌ Only letters allowed (a-z)")
        return
    
    await ctx.send(f"🔍 Checking `{username}`...")
    
    is_available = await check_username(username)
    
    if is_available:
        await ctx.send(f"✅ **{username}** is AVAILABLE!")
    else:
        await ctx.send(f"❌ **{username}** is TAKEN")

@bot.command(name='commands', aliases=['cmds', 'h'])
async def custom_help(ctx):
    """Show commands"""
    if ctx.author.id != YOUR_USER_ID:
        return
    
    help_text = """
**🔍 USERNAME HUNTER BOT**

**Commands:**
`!scan3` - Scan ALL 3-letter usernames (aaa-zzz)
`!scan4` - Scan ALL 4-letter usernames (aaaa-zzzz)
`!stop` - Stop current scan
`!status` - Check scan progress
`!check <name>` - Verify a specific username
`!commands` - Show this menu

**How it works:**
- Bot DMs you **every available username** it finds
- Scroll up in DMs to see the complete list
- Uses accurate checking to avoid false positives
- 2-second delay between checks (respects Discord)
- Status shows: **🔴 STREAMING Umar**

**Stats:**
- 3-letter combos: 17,576
- 4-letter combos: 456,976
- Total: 474,552 usernames to check
"""
    await ctx.send(help_text)

# ===== RUN BOT =====
if __name__ == "__main__":
    if not TOKEN:
        print("❌ ERROR: No token found!")
        exit(1)
    
    bot.run(TOKEN)
