import os
import logging
from pathlib import Path
from shutil import rmtree
from asyncio import get_running_loop
from functools import partial

import aiofiles
from dotenv import load_dotenv
from pyrogram import Client, filters
from pyrogram.types import Message
from utils import download_files, add_to_zip  # Assuming these are compatible with Pyrogram

# Load environment variables
load_dotenv()

API_ID = int(os.environ['API_ID'])
API_HASH = os.environ['API_HASH']
BOT_TOKEN = os.environ['BOT_TOKEN']
CONC_MAX = int(os.environ.get('CONC_MAX', 3))
STORAGE = Path('./files/')

# Set up logging
logging.basicConfig(
    format='[%(levelname)s/%(asctime)s] %(name)s: %(message)s',
    level=logging.INFO,
    handlers=[logging.StreamHandler()]
)

# Dictionary to keep track of tasks for every user
tasks = {}

# Initialize the bot
bot = Client('quick-zip-bot', api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)


@bot.on_message(filters.command('add'))
async def start_task_handler(client: Client, message: Message):
    """
    Notifies the bot that the user is going to send the media.
    """
    tasks[message.from_user.id] = []
    await message.reply_text('OK, send me some files.')


@bot.on_message(filters.private & filters.media)
async def add_file_handler(client: Client, message: Message):
    """
    Stores the ID of messages sent with files by this user.
    """
    if message.from_user.id in tasks:
        tasks[message.from_user.id].append(message.id)


@bot.on_message(filters.command('zip'))
async def zip_handler(client: Client, message: Message):
    """
    Zips the media of messages corresponding to the IDs saved for this user in
    tasks. The zip filename must be provided in the command.
    """
    if len(message.command) < 2:
        await message.reply_text('Please provide a name for the zip file.')
        return

    if message.from_user.id not in tasks:
        await message.reply_text('You must use /add first.')
        return

    if not tasks[message.from_user.id]:
        await message.reply_text('You must send me some files first.')
        return

    messages = [await client.get_messages(message.chat.id, msg_id) for msg_id in tasks[message.from_user.id]]
    zip_size = sum([msg.document.file_size for msg in messages if msg.document])

    if zip_size > 1024 * 1024 * 2000:  # zip_size > 1.95 GB approximately
        await message.reply_text('Total filesize must not exceed 2.0 GB.')
        return

    root = STORAGE / f'{message.from_user.id}/'
    zip_name = root / (message.command[1] + '.zip')

    # Create root directory if it doesn't exist
    root.mkdir(parents=True, exist_ok=True)

    async for file in download_files(messages, CONC_MAX, root):
        await get_running_loop().run_in_executor(None, partial(add_to_zip, zip_name, file))

    await message.reply_document(zip_name)

    await get_running_loop().run_in_executor(None, rmtree, root)
    tasks.pop(message.from_user.id)


@bot.on_message(filters.command('cancel'))
async def cancel_handler(client: Client, message: Message):
    """
    Cleans the list of tasks for the user.
    """
    tasks.pop(message.from_user.id, None)
    await message.reply_text('Canceled zip. For a new one, use /add.')


if __name__ == '__main__':
    bot.run()
