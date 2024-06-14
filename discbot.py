import os
import random
import discord
from discord.ext import commands, tasks
from dotenv import load_dotenv
from litellm import acompletion
import asyncio
import base64
from datetime import datetime as dt
import logging
from os import environ as env
import requests

# Load environment variables
load_dotenv()
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s: %(message)s",
)

# Constants and Configuration
LLM_IS_LOCAL = env["LLM"].startswith("local/")
LLM_SUPPORTS_IMAGES = any(x in env["LLM"] for x in ("claude-3", "gpt-4-turbo", "gpt-4o", "llava", "vision"))
LLM_SUPPORTS_NAMES = any(env["LLM"].startswith(x) for x in ("gpt", "openai/gpt"))

ALLOWED_FILE_TYPES = ("image", "text")
ALLOWED_CHANNEL_TYPES = (discord.ChannelType.text, discord.ChannelType.public_thread, discord.ChannelType.private_thread, discord.ChannelType.private)
ALLOWED_CHANNEL_IDS = tuple(int(id) for id in env["ALLOWED_CHANNEL_IDS"].split(",") if id)
ALLOWED_ROLE_IDS = tuple(int(id) for id in env["ALLOWED_ROLE_IDS"].split(",") if id)

MAX_TEXT = int(env["MAX_TEXT"])
MAX_IMAGES = int(env["MAX_IMAGES"]) if LLM_SUPPORTS_IMAGES else 0
MAX_MESSAGES = int(env["MAX_MESSAGES"])

EMBED_COLOR = {"incomplete": discord.Color.orange(), "complete": discord.Color.green()}
EMBED_MAX_LENGTH = 4096
EDIT_DELAY_SECONDS = 1.3
MAX_MESSAGE_NODES = 100

convert = lambda string: int(string) if string.isdecimal() else (float(string) if string.replace(".", "", 1).isdecimal() else string)
llm_settings = {k.strip(): convert(v.strip()) for k, v in (x.split("=") for x in env["LLM_SETTINGS"].split(",") if x.strip()) if "#" not in k}

if LLM_IS_LOCAL:
    llm_settings["base_url"] = env["LOCAL_SERVER_URL"]
    if "api_key" not in llm_settings:
        llm_settings["api_key"] = "Not used"
    env["LLM"] = env["LLM"].replace("local/", "", 1)

if env["DISCORD_CLIENT_ID"]:
    print(f"\nBOT INVITE URL:\nhttps://discord.com/api/oauth2/authorize?client_id={env['DISCORD_CLIENT_ID']}&permissions=412317273088&scope=bot\n")

intents = discord.Intents.default()
intents.message_content = True
activity = discord.Game(name=env["DISCORD_STATUS_MESSAGE"][:128] or "github.com/jakobdylanc/discord-llm-chatbot")
bot = discord.Client(intents=intents, activity=activity)

msg_nodes = {}
msg_locks = {}
last_task_time = None


class MsgNode:
    def __init__(self, data, next_msg=None, too_much_text=False, too_many_images=False, has_bad_attachments=False, fetch_next_failed=False):
        self.data = data
        self.next_msg = next_msg
        self.too_much_text = too_much_text
        self.too_many_images = too_many_images
        self.has_bad_attachments = has_bad_attachments
        self.fetch_next_failed = fetch_next_failed


def get_system_prompt():
    system_prompt_extras = [f"Today's date: {dt.now().strftime('%B %d %Y')}"]
    if LLM_SUPPORTS_NAMES:
        system_prompt_extras += ["User's names are their Discord IDs and should be typed as '<@ID>'."]

    return [
        {
            "role": "system",
            "content": "\n".join([env["LLM_SYSTEM_PROMPT"]] + system_prompt_extras),
        }
    ]


@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")
    send_random_comment.start()


@bot.event
async def on_message(new_msg):
    global msg_nodes, msg_locks, last_task_time

    if not is_message_allowed(new_msg):
        return

    reply_chain, user_warnings = await build_reply_chain(new_msg)
    logging.info(f"Message received (user ID: {new_msg.author.id}, attachments: {len(new_msg.attachments)}, reply chain length: {len(reply_chain)}):\n{new_msg.content}")

    response_msgs, response_contents = await generate_responses(new_msg, reply_chain, user_warnings)
    await create_response_msg_nodes(response_msgs, response_contents, new_msg)
    await cleanup_old_nodes()


def is_message_allowed(new_msg):
    return (
        new_msg.channel.type in ALLOWED_CHANNEL_TYPES
        and (new_msg.channel.type == discord.ChannelType.private or bot.user in new_msg.mentions)
        and (not ALLOWED_CHANNEL_IDS or any(id in ALLOWED_CHANNEL_IDS for id in (new_msg.channel.id, getattr(new_msg.channel, "parent_id", None))))
        and (not ALLOWED_ROLE_IDS or new_msg.channel.type == discord.ChannelType.private or any(role.id in ALLOWED_ROLE_IDS for role in new_msg.author.roles))
        and not new_msg.author.bot
    )


async def build_reply_chain(new_msg):
    reply_chain = []
    user_warnings = set()
    curr_msg = new_msg
    while curr_msg and len(reply_chain) < MAX_MESSAGES:
        async with msg_locks.setdefault(curr_msg.id, asyncio.Lock()):
            if curr_msg.id not in msg_nodes:
                await process_message(curr_msg)

            curr_node = msg_nodes[curr_msg.id]
            if curr_node.data["content"]:
                reply_chain.append(curr_node.data)

            update_warnings(curr_node, user_warnings)
            if curr_node.fetch_next_failed or (curr_node.next_msg and len(reply_chain) == MAX_MESSAGES):
                user_warnings.add(f"⚠️ Only using last{'' if (count := len(reply_chain)) == 1 else f' {count}'} message{'' if count == 1 else 's'}")

            curr_msg = curr_node.next_msg

    return reply_chain, user_warnings


async def process_message(curr_msg):
    good_attachments = {type: [att for att in curr_msg.attachments if att.content_type and type in att.content_type] for type in ALLOWED_FILE_TYPES}
    text = "\n".join(
        ([curr_msg.content] if curr_msg.content else [])
        + [embed.description for embed in curr_msg.embeds if embed.description]
        + [requests.get(att.url).text for att in good_attachments["text"]]
    )
    if curr_msg.content.startswith(bot.user.mention):
        text = text.replace(bot.user.mention, "", 1).lstrip()

    content = prepare_content(text, good_attachments)
    data = {"content": content, "role": "assistant" if curr_msg.author == bot.user else "user"}
    if LLM_SUPPORTS_NAMES:
        data["name"] = str(curr_msg.author.id)

    msg_nodes[curr_msg.id] = MsgNode(
        data=data,
        too_much_text=len(text) > MAX_TEXT,
        too_many_images=len(good_attachments["image"]) > MAX_IMAGES,
        has_bad_attachments=len(curr_msg.attachments) > sum(len(att_list) for att_list in good_attachments.values()),
    )
    await fetch_next_message(curr_msg)


def prepare_content(text, good_attachments):
    if LLM_SUPPORTS_IMAGES and good_attachments["image"][:MAX_IMAGES]:
        return ([{"type": "text", "text": text[:MAX_TEXT]}] if text[:MAX_TEXT] else []) + [
            {
                "type": "image_url",
                "image_url": f"data:{att.content_type};base64,{base64.b64encode(requests.get(att.url).content).decode('utf-8')}",
            }
            for att in good_attachments["image"][:MAX_IMAGES]
        ]
    else:
        return text[:MAX_TEXT]


def update_warnings(curr_node, user_warnings):
    if curr_node.too_much_text:
        user_warnings.add(f"⚠️ Max {MAX_TEXT:,} characters per message")
    if curr_node.too_many_images:
        user_warnings.add(f"⚠️ Max {MAX_IMAGES} image{'' if MAX_IMAGES == 1 else 's'} per message" if MAX_IMAGES > 0 else "⚠️ Can't see images")
    if curr_node.has_bad_attachments:
        user_warnings.add("⚠️ Unsupported attachments")


async def fetch_next_message(curr_msg):
    try:
        if (
            not curr_msg.reference
            and curr_msg.channel.type != discord.ChannelType.private
            and bot.user.mention not in curr_msg.content
            and (prev_msg_in_channel := ([m async for m in curr_msg.channel.history(before=curr_msg, limit=1)] or [None])[0])
            and any(prev_msg_in_channel.type == type for type in (discord.MessageType.default, discord.MessageType.reply))
            and prev_msg_in_channel.author == curr_msg.author
        ):
            msg_nodes[curr_msg.id].next_msg = prev_msg_in_channel

        elif curr_msg.reference:
            next_msg_id = curr_msg.reference.message_id
            msg_nodes[curr_msg.id].next_msg = (
                next_is_thread_parent := (new_msg.reference.resolved.parent if isinstance(new_msg.reference.resolved, discord.Message) else None)
            ) or (
                next_is_thread_parent := (r if isinstance(r := new_msg.reference.resolved.parent, discord.Message) else await new_msg.channel.parent.fetch_message(next_msg_id))
            ) or (
                r if isinstance(r := curr_msg.reference.resolved, discord.Message) else await curr_msg.channel.fetch_message(next_msg_id)
            )
    except Exception:
        msg_nodes[curr_msg.id].fetch_next_failed = True


async def generate_responses(new_msg, reply_chain, user_warnings):
    response_msgs, response_contents = [], []

    try:
        async with msg_locks.setdefault(new_msg.id, asyncio.Lock()):
            response = await acompletion(
                env["LLM"],
                get_system_prompt() + list(reversed(reply_chain)),
                **llm_settings,
            )
            if not (choices := response.get("choices")):
                raise ValueError("No response")
            raw_response = choices[0]["message"]["content"]
            if raw_response.startswith("Assistant:"):
                raw_response = raw_response[len("Assistant:") :].lstrip()
            if not raw_response:
                raise ValueError("Empty response")
            logging.info(f"Reply: {raw_response}")
            remaining_content = raw_response
            while remaining_content:
                response_msgs.append(await new_msg.reply("...", mention_author=False))
                response_contents.append(remaining_content[:EMBED_MAX_LENGTH])
                remaining_content = remaining_content[EMBED_MAX_LENGTH:]
    except Exception as e:
        logging.error(f"Error generating response: {e}")
        user_warnings.add("⚠️ Error generating response")
        if not response_msgs:
            response_msgs.append(await new_msg.reply("⚠️ Error generating response", mention_author=False))

    return response_msgs, response_contents


async def create_response_msg_nodes(response_msgs, response_contents, new_msg):
    global last_task_time
    last_task_time = dt.now()

    for response_msg, response_content in zip(response_msgs, response_contents):
        async with msg_locks.setdefault(response_msg.id, asyncio.Lock()):
            if response_msg.id not in msg_nodes:
                msg_nodes[response_msg.id] = MsgNode(
                    data={
                        "content": response_content,
                        "role": "assistant",
                        "name": str(bot.user.id),
                    },
                    next_msg=new_msg,
                )

    await asyncio.sleep(EDIT_DELAY_SECONDS)
    for response_msg, response_content in zip(response_msgs, response_contents):
        async with msg_locks[response_msg.id]:
            await response_msg.edit(content=response_content[:EMBED_MAX_LENGTH])


async def cleanup_old_nodes():
    global msg_nodes, last_task_time

    if not last_task_time or (dt.now() - last_task_time).total_seconds() < 60:
        return

    if len(msg_nodes) <= MAX_MESSAGE_NODES:
        return

    async with asyncio.Lock():
        sorted_ids = sorted(msg_nodes.keys(), key=lambda k: k)
        for msg_id in sorted_ids[: len(sorted_ids) - MAX_MESSAGE_NODES]:
            msg_nodes.pop(msg_id, None)


@tasks.loop(minutes=30)
async def send_random_comment():
    await bot.wait_until_ready()
    random_comments = [
        "Hey everyone! How's it going?",
        "Remember, you can @pixify bot to chat or get help!",
        "Need any assistance? I'm here to help!",
        "What's everyone up to today?",
        "Feel free to ask me anything!",
    ]
    for guild in bot.guilds:
        for channel in guild.text_channels:
            permissions = channel.permissions_for(guild.me)
            if permissions.send_messages:
                try:
                    await channel.send(random.choice(random_comments))
                except Exception as e:
                    logging.error(f"Error sending random comment to {channel.name} in {guild.name}: {e}")


bot.run(env["DISCORD_BOT_TOKEN"])
