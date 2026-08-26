import os
import discord
import asyncio
from dotenv import load_dotenv

from conversation.router import route
from agents.manager import handle_request
from core.logger import log
from workflow.interaction import interaction

load_dotenv()

TOKEN = os.getenv("DISCORD_TOKEN")

intents = discord.Intents.default()
intents.message_content = True

client = discord.Client(intents=intents)


@client.event
async def on_ready():
    print(f"✅ Logged in as {client.user}")
    log("AI-OS started successfully.")


@client.event
async def on_message(message):
    if message.author == client.user:
        return

    user_message = message.content.strip()
    if not user_message:
        return

    # Interactive autonomy controls.
    # Usage:
    #   !approve <run_id> <request_id>
    #   !deny <run_id> <request_id>
    #   !pending
    parts = user_message.split()
    command = parts[0].lower() if parts else ""

    if command in {"!approve", "!deny"}:
        if len(parts) != 3:
            await message.channel.send(
                f"❌ Usage: {command} <run_id> <request_id>"
            )
            return

        run_id, request_id = parts[1], parts[2]
        try:
            if command == "!approve":
                run = await asyncio.to_thread(
                    interaction.approve, run_id, request_id
                )
            else:
                run = await asyncio.to_thread(
                    interaction.deny, run_id, request_id
                )
            await message.channel.send(interaction.format_result(run))
        except Exception as exc:
            log(f"Approval control error: {exc}")
            await message.channel.send(f"❌ {exc}")
        return

    if command == "!pending":
        try:
            requests = await asyncio.to_thread(interaction.pending_approvals)
            if not requests:
                await message.channel.send("✅ No pending approvals.")
                return
            lines = ["⚠️ **Pending approvals:**"]
            for request in requests:
                lines.append(
                    f"• `{request.id}` — **{request.tool}** "
                    f"({request.permission.value}) — {request.description}"
                )
            await message.channel.send("\n".join(lines))
        except Exception as exc:
            log(f"Pending approval error: {exc}")
            await message.channel.send(f"❌ {exc}")
        return

    if user_message.startswith("!ask"):
        user_message = user_message[len("!ask"):].strip()
    elif user_message.startswith("!remember"):
        user_message = "remember " + user_message[len("!remember"):].strip()
    elif user_message.startswith("!recall"):
        user_message = "recall " + user_message[len("!recall"):].strip()

    thinking = await message.channel.send("🤔 Thinking...")

    try:
        request = route(user_message)
        response = await asyncio.to_thread(handle_request, request)

        if len(response) > 1900:
            response = response[:1900]

        await thinking.edit(content=response)

    except Exception as e:
        log(f"ERROR: {e}")
        await thinking.edit(content=f"❌ Error:\n{e}")


client.run(TOKEN)
