import os
import discord
import asyncio
from dotenv import load_dotenv

from conversation.router import route
from agents.manager import handle_request
from core.logger import log

# -----------------------
# Load Environment Variables
# -----------------------
load_dotenv()

TOKEN = os.getenv("DISCORD_TOKEN")

# -----------------------
# Discord Setup
# -----------------------
intents = discord.Intents.default()
intents.message_content = True

client = discord.Client(intents=intents)

# -----------------------
# Bot Ready
# -----------------------
@client.event
async def on_ready():
    print(f"✅ Logged in as {client.user}")
    log("AI-OS started successfully.")

# -----------------------
# Message Handler
# -----------------------
@client.event
async def on_message(message):

    # Ignore the bot's own messages
    if message.author == client.user:
        return

    user_message = message.content.strip()

    # Ignore empty messages
    if not user_message:
        return

    # ---------------------------------
    # Temporary compatibility
    # ---------------------------------

    if user_message.startswith("!ask"):
        user_message = user_message[len("!ask"):].strip()

    elif user_message.startswith("!remember"):
        user_message = "remember " + user_message[len("!remember"):].strip()

    elif user_message.startswith("!recall"):
        user_message = "recall " + user_message[len("!recall"):].strip()

    thinking = await message.channel.send("🤔 Thinking...")

    try:

        # Route the message through the Conversation Engine
        request = route(user_message)

        # Send structured request to the Manager
        response = await asyncio.to_thread(
           handle_request,
           request
        ) 

        if len(response) > 1900:
            response = response[:1900]

        await thinking.edit(content=response)

    except Exception as e:

        log(f"ERROR: {e}")

        await thinking.edit(
            content=f"❌ Error:\n{e}"
        )

# -----------------------
# Start Bot
# -----------------------
client.run(TOKEN)