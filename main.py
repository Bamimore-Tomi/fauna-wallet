import os, logging
from datetime import datetime
import pytz
from telegram.ext import Updater
from telegram.ext import (
    CommandHandler,
    MessageHandler,
    Filters,
    ConversationHandler,
    CallbackQueryHandler,
)
from telegram import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
)
import telegram
from faunadb import query as q
from faunadb.objects import Ref
from dotenv import load_dotenv
import utils

load_dotenv()
client = utils.load_db()
messages = utils.load_messages()
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.DEBUG
)
ASK_WALLET_NAME = range(0)


def start(update, context):
    chat_id = update.effective_chat.id
    try:
        user = client.query(q.get(q.match(q.index("user_index"), chat_id)))
    except Exception as e:
        print(e)
        user = client.query(
            q.create(
                q.collection("user"),
                {
                    "data": {
                        "user_id": chat_id,
                        "username": update.message.chat.username,
                        "firstname": update.message.chat.first_name,
                        "lastname": update.message.chat.last_name,
                        "date": datetime.now(pytz.UTC),
                    }
                },
            )
        )
        context.bot.send_message(
            chat_id=chat_id,
            text=messages["welcome"],
            parse_mode=telegram.ParseMode.MARKDOWN,
        )
        context.bot.send_message(
            chat_id=chat_id,
            text=messages["help"],
            parse_mode=telegram.ParseMode.MARKDOWN,
        )


def helper(update, context):
    chat_id = update.effective_chat.id
    context.bot.send_message(
        chat_id=chat_id, text=messages["help"], parse_mode=telegram.ParseMode.MARKDOWN
    )


def new_wallet(update, context):
    chat_id = update.effective_chat.id
    context.bot.send_message(
        chat_id=chat_id,
        text=messages["newWallet"],
        parse_mode=telegram.ParseMode.MARKDOWN,
    )
    return ASK_WALLET_NAME


def create_wallet(update, context):
    chat_id = update.effective_chat.id
    valid, wallet_name = utils.wallet_name_validator(update.message.text)
    while valid is False:
        context.bot.send_message(chat_id=chat_id, text=messages["newWallet"])


def main():
    updater = Updater(token=os.getenv("TOKEN"), use_context=True)
    dispatcher = updater.dispatcher
    entry_ = CommandHandler("start", start)
    helper_ = CommandHandler("help", helper)
    new_wallet_conv = ConversationHandler(
        entry_points=[CommandHandler("NewWallet", new_wallet)],
        states={
            ASK_WALLET_NAME: [MessageHandler(Filters.regex(r"\w*"), create_wallet)]
        },
        fallbacks=[CommandHandler("NewWallet", new_wallet)],
    )

    dispatcher.add_handler(entry_)
    dispatcher.add_handler(helper_)
    dispatcher.add_handler(new_wallet_conv)

    updater.start_polling()
    updater.idle()


if __name__ == "__main__":
    main()
