import os, logging
from datetime import datetime
import pytz
from multiprocessing import Process
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
from faunadb.errors import NotFound
from dotenv import load_dotenv
import utils
import errors

load_dotenv()
client = utils.load_db()
Process(target=utils.blockchain_runner).start()
messages = utils.load_messages()
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.DEBUG
)
(
    ASK_WALLET_NAME,
    ALL_WALLET,
    WALLET_SELECTION,
    AMOUNT_NUMBER,
    RECIEVER_ADDRESS,
    DELETE_WALLET,
) = range(6)


def start(update, context):
    chat_id = update.effective_chat.id
    try:
        user = client.query(q.get(q.match(q.index("user_index"), chat_id)))
        try:
            context.bot.send_message(
                chat_id=chat_id,
                text=messages["allWalletFound"],
                reply_markup=utils.generate_wallet_menu(client, chat_id),
            )
        except errors.WalletNotFound:
            context.bot.send_message(
                chat_id=chat_id,
                text=messages["allWalletNotFound"],
                parse_mode=telegram.ParseMode.MARKDOWN,
            )

    except NotFound:
        data = {
            "user_id": chat_id,
            "username": update.message.chat.username,
            "firstname": update.message.chat.first_name,
            "lastname": update.message.chat.last_name,
            "date": datetime.now(pytz.UTC),
        }
        utils.save_user(client, data)
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


def wallet_detail_callback(update, context):
    chat_id = update.effective_chat.id
    query_data = update.callback_query.data
    try:
        wallet, stream = utils.get_wallet_detail(client, chat_id, query_data)
        context.bot.send_message(
            chat_id=chat_id,
            text=messages["walletDetail"].format(
                wallet["wallet_name"],
                wallet["wallet_address"]["base58"],
                wallet["wallet_account_balance"],
            ),
            parse_mode=telegram.ParseMode.MARKDOWN,
        )
        context.bot.sendPhoto(chat_id=chat_id, photo=stream)
    except errors.WalletNotFound:
        context.bot.send_message(
            chat_id=chat_id,
            text=messages["walletNotFound"].format(query_data),
            parse_mode=telegram.ParseMode.MARKDOWN,
        )


def send_token(update, context):
    chat_id = update.effective_chat.id
    context.bot.send_message(
        chat_id=chat_id,
        text=messages["sendTokenInstruction"],
        reply_markup=utils.generate_wallet_keyboard(client, chat_id),
        parse_mode=telegram.ParseMode.MARKDOWN,
    )
    return WALLET_SELECTION


def ask_amount(update, context):
    chat_id = update.effective_chat.id
    wallet_name = update.message.text.strip().lower()
    try:
        wallet = utils.get_wallets(client, chat_id, wallet_name=wallet_name)
        context.user_data["current_wallet"] = wallet
        context.bot.send_message(
            chat_id=chat_id,
            text=messages["askAmount"].format(wallet["wallet_account_balance"]),
            parse_mode=telegram.ParseMode.MARKDOWN,
        )
    except errors.WalletNotFound:
        context.bot.send_message(
            chat_id=chat_id,
            text=messages["walletNotFound"].format(wallet_name),
            parse_mode=telegram.ParseMode.MARKDOWN,
        )
    return AMOUNT_NUMBER


def ask_reciever_address(update, context):
    chat_id = update.effective_chat.id
    amount = update.message.text
    is_valid = False
    try:
        amount = int(amount)
        context.user_data["current_amount"] = amount
        is_valid = True
    except:
        is_valid = False
    while is_valid == False:
        return WALLET_SELECTION
    context.bot.send_message(
        chat_id=chat_id,
        text=messages["recieverAddress"],
        parse_mode=telegram.ParseMode.MARKDOWN,
    )
    return RECIEVER_ADDRESS


def send_transaction(update, context):
    print("AT SEND TRANSACTION")
    chat_id = update.effective_chat.id
    address = update.message.text.strip()
    print(address)
    try:
        utils.send_trx(
            context.user_data["current_wallet"]["encrypted_private_key"],
            address,
            context.user_data["current_amount"],
        )
        context.bot.send_message(
            chat_id=chat_id,
            text=messages["transactionSuccess"].format(
                context.user_data["current_amount"],
                context.user_data["current_wallet"]["wallet_name"],
                address,
            ),
            parse_mode=telegram.ParseMode.MARKDOWN,
        )
    except errors.InsufficientBalance:
        print("insufficient balance")
        context.bot.send_message(
            chat_id=chat_id,
            text=messages["transactionUnsuccessful"].format(
                context.user_data["current_amount"],
                context.user_data["current_wallet"]["wallet_name"],
                address,
                "Insufficient Balance",
            ),
            parse_mode=telegram.ParseMode.MARKDOWN,
        )
        return -1
    except ValueError:
        context.bot.send_message(
            chat_id=chat_id,
            text=messages["incorrectAddress"].format(address),
            parse_mode=telegram.ParseMode.MARKDOWN,
        )
        return -1


def create_wallet(update, context):
    chat_id = update.effective_chat.id
    valid, wallet_name = utils.wallet_name_validator(update.message.text)
    while valid is False:
        context.bot.send_message(
            chat_id=chat_id,
            text=messages["newWallet"],
            parse_mode=telegram.ParseMode.MARKDOWN,
        )
        return ASK_WALLET_NAME
    address = utils.create_wallet(client, chat_id, wallet_name)
    context.bot.send_message(
        chat_id=chat_id,
        text=messages["createWalletSuccess"].format(wallet_name, address),
        parse_mode=telegram.ParseMode.MARKDOWN,
    )
    return -1


def all_wallet(update, context):
    chat_id = update.effective_chat.id
    context.bot.send_message(
        chat_id=chat_id,
        text=messages["allWalletFound"],
        reply_markup=utils.generate_wallet_menu(client, chat_id),
    )
    return ALL_WALLET


def delete_wallet_select(update, context):
    chat_id = update.effective_chat.id
    try:
        context.bot.send_message(
            chat_id=chat_id,
            text=messages["allWalletFound"],
            reply_markup=utils.generate_wallet_menu(client, chat_id, with_ref=True),
        )
        return DELETE_WALLET
    except errors.WalletNotFound:
        context.bot.send_message(
            chat_id=chat_id,
            text=messages["allWalletNotFound"],
            parse_mode=telegram.ParseMode.MARKDOWN,
        )
        return -1


def delete_wallet(update, context):
    chat_id = update.effective_chat.id
    query_data = update.callback_query.data
    print(query_data)
    try:
        utils.delete_wallet(client, chat_id, query_data)
        context.bot.send_message(
            chat_id=chat_id,
            text=messages["deleteWalletSuccess"].format(query_data),
            parse_mode=telegram.ParseMode.MARKDOWN,
        )
    except errors.WalletNotFound:
        context.bot.send_message(
            chat_id=chat_id,
            text=messages["walletNotFound"].format(wallet_name),
            parse_mode=telegram.ParseMode.MARKDOWN,
        )


def main():
    updater = Updater(token=os.getenv("TOKEN"), use_context=True)
    dispatcher = updater.dispatcher
    entry_ = CommandHandler("start", start)
    helper_ = CommandHandler("help", helper)
    new_wallet_conv = ConversationHandler(
        entry_points=[CommandHandler("newwallet", new_wallet)],
        states={
            ASK_WALLET_NAME: [MessageHandler(Filters.regex(r"\w*"), create_wallet)]
        },
        allow_reentry=True,
        fallbacks=[CommandHandler("newwallet", new_wallet)],
    )
    wallet_operation = ConversationHandler(
        entry_points=[CommandHandler("allwallet", all_wallet)],
        states={ALL_WALLET: [CallbackQueryHandler(wallet_detail_callback)]},
        allow_reentry=True,
        fallbacks=[CommandHandler("allwallet", all_wallet)],
    )

    send_operation = ConversationHandler(
        entry_points=[CommandHandler("sendtoken", send_token)],
        states={
            WALLET_SELECTION: [MessageHandler(Filters.regex(r"\w*"), ask_amount)],
            AMOUNT_NUMBER: [
                MessageHandler(Filters.regex(r"\w*"), ask_reciever_address)
            ],
            RECIEVER_ADDRESS: [MessageHandler(Filters.regex(r"\w*"), send_transaction)],
        },
        fallbacks=[CommandHandler("sendtoken", send_token)],
    )

    delete_operation = ConversationHandler(
        entry_points=[CommandHandler("deletewallet", delete_wallet_select)],
        states={DELETE_WALLET: [CallbackQueryHandler(delete_wallet)]},
        allow_reentry=True,
        fallbacks=[CommandHandler("deletewallet", delete_wallet_select)],
    )

    dispatcher.add_handler(entry_)
    dispatcher.add_handler(helper_)
    dispatcher.add_handler(new_wallet_conv)
    dispatcher.add_handler(wallet_operation)
    dispatcher.add_handler(send_operation)
    dispatcher.add_handler(delete_operation)

    updater.start_polling()
    updater.idle()


if __name__ == "__main__":
    main()
