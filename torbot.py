import os
import random
import asyncio
import logging
from logging.handlers import RotatingFileHandler
from typing import Optional
from dotenv import load_dotenv

import nest_asyncio
nest_asyncio.apply()

from stem import Signal
from stem.control import Controller
from telegram import Update, InlineQueryResultArticle, InputTextMessageContent
from telegram.ext import (
    ApplicationBuilder,
    Application,
    CommandHandler,
    ContextTypes,
    InlineQueryHandler,
    JobQueue,
    Job,
)


load_dotenv()

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

file_handler = RotatingFileHandler('bot.log', maxBytes=5*1024*1024, backupCount=2)
file_formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
file_handler.setFormatter(file_formatter)
logger.addHandler(file_handler)

console_handler = logging.StreamHandler()
console_formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
console_handler.setFormatter(console_formatter)
logger.addHandler(console_handler)

import telegram
logger.info(f"python-telegram-bot version: {telegram.__version__}")

# Load environment variables
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN') # it takes from .env file
AUTH_PASSWORD = os.getenv('AUTH_PASSWORD', 'AUTHENTICATE_PASSWORD_MUST_BE_HERE')
TOR_CONTROL_PASSWORD = os.getenv('TOR_CONTROL_PASSWORD', 'YOUR_PASSWORD_MUST_BE_HERE')
TOR_CONTROL_PORT = int(os.getenv('TOR_CONTROL_PORT', '9051'))
ALLOWED_COUNTRIES_ENV = os.getenv('ALLOWED_COUNTRIES', 'NO,FI,DK,SE,IS,NL,DE,CA,CH,NZ,AU,BE,IE,EE,PT,LU,UY,TW,JP,KR')

# Blocked user IDs
BLOCKED_USER_IDS = {123456789, 987654321}

# Don't look here too
EASTER_EGG_FILE = 'easter_egg.mp3'  # Be sure that this file in the same dir with .py code

VALID_COUNTRIES = set(country.strip().upper() for country in ALLOWED_COUNTRIES_ENV.split(',') if country.strip())

authenticated_users = {}
user_preferences = {}

RATE_LIMIT = 5 * 60
user_last_update = {}

def is_blocked(user_id: int) -> bool:
    return user_id in BLOCKED_USER_IDS

def update_identity(preferred_country: Optional[str] = None):
    try:
        with Controller.from_port(port=TOR_CONTROL_PORT) as controller:
            controller.authenticate(password=TOR_CONTROL_PASSWORD)
            if preferred_country and preferred_country.upper() in VALID_COUNTRIES:
                controller.set_options({
                    'ExitNodes': f'{{{preferred_country.upper()}}}',
                    'StrictNodes': '1',
                })
                logger.info(f"Set ExitNodes to country: {preferred_country.upper()}")
            else:
                controller.set_options({
                    'ExitNodes': '',
                    'StrictNodes': '0',
                })
                logger.info("Cleared ExitNodes preferences.")

            controller.signal(Signal.NEWNYM)
        logger.info("Tor identity updated successfully.")
    except Exception as e:
        logger.error(f"Error while updating Tor identity: {e}")
        raise



async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    try:
        if is_blocked(user_id):
            if os.path.exists(EASTER_EGG_FILE):
                with open(EASTER_EGG_FILE, 'rb') as audio_file:
                    # So yeah, it sends audio file.
                    await update.message.reply_audio(audio=audio_file)
                logger.info(f"Easter egg sent to blocked user {update.effective_user.first_name} (ID: {user_id}).")
            else:
                await update.message.reply_text('Easter egg file not found. Please call the administrator.')
                logger.error(f"Easter egg file '{EASTER_EGG_FILE}' not found.")
            return

        await update.message.reply_text(
            'Tor management bot. Use /auth <password> to authenticate.'
        )
        logger.info(f"Bot started by user {update.effective_user.first_name} (ID: {user_id}).")
    except Exception as e:
        logger.error(f"Error in start command: {e}")
        await update.message.reply_text('An error occurred while processing your request.')

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    try:
        if is_blocked(user_id):
            await update.message.reply_text('A?')
            logger.info(f"Blocked user {update.effective_user.first_name} (ID: {user_id}) attempted to use /help.")
            return

        help_text = (
            "<b>Available commands:</b>\n\n"
            "/start - Start the bot.\n"
            "/auth &lt;password&gt; - Authenticate to use protected commands.\n"
            "/update - Update your Tor identity.\n"
            "/setcountry &lt;country_code&gt; - Set your preferred country for Tor exit nodes (e.g., US, JP).\n"
            "/reset - Reset your preferred country and update Tor identity without restrictions.\n"
            "/countries - Show a list of available countries for selection.\n"
            "/help - Show this help message."
        )
        await update.message.reply_text(help_text, parse_mode='HTML')
        logger.info(f"Help requested by user {update.effective_user.first_name} (ID: {user_id}).")
    except Exception as e:
        logger.error(f"Error in help command: {e}")
        await update.message.reply_text('An error occurred while generating the help message.')

async def auth_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    try:
        if is_blocked(user_id):
            await update.message.reply_text('A?')
            logger.info(f"Blocked user {update.effective_user.first_name} (ID: {user_id}) attempted to use /auth.")
            return

        if user_id in authenticated_users:
            await update.message.reply_text('You are already authenticated.')
            logger.info(f"User {update.effective_user.first_name} (ID: {user_id}) attempted to re-authenticate.")
            return

        if len(context.args) != 1:
            await update.message.reply_text('Usage: /auth <password>')
            logger.warning(f"User {update.effective_user.first_name} (ID: {user_id}) used incorrect /auth command format.")
            return

        input_password = context.args[0].strip()
        correct_password = AUTH_PASSWORD.strip()

        if input_password == correct_password:
            authenticated_users[user_id] = True
            await update.message.reply_text('Authentication successful! Now you can use commands.')
            logger.info(f"User {update.effective_user.first_name} (ID: {user_id}) authenticated successfully.")
        else:
            await update.message.reply_text('Incorrect password. Please try again.')
            logger.warning(f"User {update.effective_user.first_name} (ID: {user_id}) failed authentication.")
    except Exception as e:
        logger.error(f"Error in auth command: {e}")
        await update.message.reply_text('An error occurred during authentication.')

async def update_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id

    try:
        if is_blocked(user_id):
            await update.message.reply_text('You are not allowed to use this bot.')
            logger.info(f"Blocked user {update.effective_user.first_name} (ID: {user_id}) attempted to use /update.")
            return

        if user_id not in authenticated_users:
            await update.message.reply_text(
                'You are not authenticated! Please authenticate using /auth <password>.'
            )
            logger.info(f"Unauthenticated user {update.effective_user.first_name} (ID: {user_id}) attempted to update identity.")
            return

        current_time = asyncio.get_event_loop().time()
        last_update = user_last_update.get(user_id, 0)
        if current_time - last_update < RATE_LIMIT:
            wait_time = RATE_LIMIT - (current_time - last_update)
            await update.message.reply_text(
                f'Please wait {int(wait_time)} seconds before the next update.'
            )
            logger.info(f"User {update.effective_user.first_name} (ID: {user_id}) is rate limited for /update.")
            return

        preferred_country = user_preferences.get(user_id)

        update_identity(preferred_country)
        user_last_update[user_id] = current_time
        await update.message.reply_text('Your Tor identity has been updated!')
        logger.info(f"User {update.effective_user.first_name} (ID: {user_id}) updated their Tor identity.")
    except Exception as e:
        logger.error(f"Error in update command: {e}")
        await update.message.reply_text('An error occurred while updating your identity.')

async def set_country_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id

    try:
        if is_blocked(user_id):
            await update.message.reply_text('A?')
            logger.info(f"Blocked user {update.effective_user.first_name} (ID: {user_id}) attempted to use /setcountry.")
            return

        if user_id not in authenticated_users:
            await update.message.reply_text(
                'You are not authenticated! Please authenticate using /auth <password>.'
            )
            logger.info(f"Unauthenticated user {update.effective_user.first_name} (ID: {user_id}) attempted to set country.")
            return

        if len(context.args) != 1:
            await update.message.reply_text('Usage: /setcountry <country_code>')
            logger.warning(f"User {update.effective_user.first_name} (ID: {user_id}) used incorrect /setcountry command format.")
            return

        country_code = context.args[0].upper()
        if country_code not in VALID_COUNTRIES:
            await update.message.reply_text(
                'Invalid country code. Please use a two letter ISO code of country (e.g., US, JP, KR).'
            )
            logger.warning(f"User {update.effective_user.first_name} (ID: {user_id}) provided invalid country code: {country_code}.")
            return

        user_preferences[user_id] = country_code
        await update.message.reply_text(f'Preferred country set to: {country_code}')
        logger.info(f"User {update.effective_user.first_name} (ID: {user_id}) set preferred country to {country_code}.")
    except Exception as e:
        logger.error(f"Error in set_country command: {e}")
        await update.message.reply_text('An error occurred while setting your preferred country.')

async def reset_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id

    try:
        if is_blocked(user_id):
            await update.message.reply_text('A?')
            logger.info(f"Blocked user {update.effective_user.first_name} (ID: {user_id}) attempted to use /reset.")
            return

        if user_id not in authenticated_users:
            await update.message.reply_text(
                'You are not authenticated! Please authenticate using /auth <password>.'
            )
            logger.info(f"Unauthenticated user {update.effective_user.first_name} (ID: {user_id}) attempted to reset preferences.")
            return

        current_time = asyncio.get_event_loop().time()
        last_update = user_last_update.get(user_id, 0)
        if current_time - last_update < RATE_LIMIT:
            wait_time = RATE_LIMIT - (current_time - last_update)
            await update.message.reply_text(
                f'Please wait {int(wait_time)} seconds before the next update.'
            )
            logger.info(f"User {update.effective_user.first_name} (ID: {user_id}) is rate limited for /reset.")
            return

        if user_id in user_preferences:
            del user_preferences[user_id]
            logger.info(f"User {update.effective_user.first_name} (ID: {user_id}) reset their country preference.")

        update_identity()
        user_last_update[user_id] = current_time
        await update.message.reply_text('Your country preferences have been reset and Tor identity updated!')
        logger.info(f"User {update.effective_user.first_name} (ID: {user_id}) reset preferences and updated Tor identity.")
    except Exception as e:
        logger.error(f"Error in reset command: {e}")
        await update.message.reply_text('An error occurred while resetting your preferences.')

async def countries_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    try:
        if is_blocked(user_id):
            await update.message.reply_text('You are not allowed to use this bot.')
            logger.info(f"Blocked user {update.effective_user.first_name} (ID: {user_id}) attempted to use /countries.")
            return

        if user_id not in authenticated_users:
            await update.message.reply_text(
                'You are not authenticated! Please authenticate using /auth <password>.'
            )
            logger.info(f"Unauthenticated user {update.effective_user.first_name} (ID: {user_id}) attempted to use /countries.")
            return

        if len(context.args) > 0:
            await update.message.reply_text('Usage: /countries')
            logger.warning(f"User {update.effective_user.first_name} (ID: {user_id}) used incorrect /countries command format.")
            return

        countries_list = ', '.join(sorted(VALID_COUNTRIES))
        await update.message.reply_text(
            f"Available countries:\n{countries_list}",
            parse_mode='HTML'
        )
        logger.info(f"Countries list requested by user {update.effective_user.first_name} (ID: {user_id}).")
    except Exception as e:
        logger.error(f"Error in countries command: {e}")
        await update.message.reply_text('An error occurred while fetching the countries list.')

async def inline_query_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.inline_query.query
    if not query:
        return

    user_id = update.effective_user.id
    try:
        if is_blocked(user_id):
            await context.bot.answer_inline_query(update.inline_query.id, [], cache_time=1)
            logger.info(f"Blocked user {update.effective_user.first_name} (ID: {user_id}) attempted to use inline query.")
            return

        update_identity()
        result = InlineQueryResultArticle(
            id='1',
            title='Update Tor Identity',
            input_message_content=InputTextMessageContent('Your Tor identity has been updated!')
        )
        await context.bot.answer_inline_query(update.inline_query.id, [result], cache_time=1)
        logger.info(f"Inline query handled by user {update.effective_user.first_name} (ID: {user_id}).")
    except Exception as e:
        logger.error(f"Error in inline query handler: {e}")


async def tor_identity_update_job(context: ContextTypes.DEFAULT_TYPE) -> None:
    try:
        update_identity()
        logger.info("Periodic Tor identity update completed.")
    except Exception as e:
        logger.error(f"Error during periodic Tor identity update: {e}")


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.error(msg="Exception while handling an update:", exc_info=context.error)
    if isinstance(update, Update) and update.effective_message:
        await update.effective_message.reply_text('An error occurred. Please try again later.')


async def main():
    if not TELEGRAM_BOT_TOKEN:
        logger.error("TELEGRAM_BOT_TOKEN is not set. Exiting.")
        return

    application = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()

    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("auth", auth_command))
    application.add_handler(CommandHandler("update", update_command))
    application.add_handler(CommandHandler("setcountry", set_country_command))
    application.add_handler(CommandHandler("reset", reset_command))
    application.add_handler(CommandHandler("countries", countries_command))
    application.add_handler(InlineQueryHandler(inline_query_handler))

    application.add_error_handler(error_handler)

    job_queue: JobQueue = application.job_queue

    # It sometimes updating your identify randomly between some time
    initial_interval = random.randint(2700, 4500)
    job_queue.run_once(tor_identity_update_job, initial_interval)
    logger.info(f"Scheduled first Tor identity update after {initial_interval} seconds.")

    logger.info("Starting bot")
    await application.run_polling()

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Bot stopped by user.")
    except RuntimeError as e:
        logger.error(f"RuntimeError: {e}")
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
