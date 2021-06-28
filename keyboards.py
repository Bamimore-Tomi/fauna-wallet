import json, os
from telegram import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
)


def build_menu(buttons, n_cols, header_buttons=None, footer_buttons=None):
    menu = [buttons[i : i + n_cols] for i in range(0, len(buttons), n_cols)]
    if header_buttons:
        menu.insert(0, [header_buttons])
    if footer_buttons:
        menu.append([footer_buttons])
    return menu


def wallet_menu(data, columns=1, with_address=False, with_ref=False):
    if with_address == True:
        inline_keyboard_button = [
            InlineKeyboardButton(
                i["wallet_name"], callback_data=i["wallet_address"]["base58"]
            )
            for i in data
        ]
    elif with_ref == True:
        inline_keyboard_button = [
            InlineKeyboardButton(i["wallet_name"], callback_data=i["ref"]) for i in data
        ]
    else:
        inline_keyboard_button = [
            InlineKeyboardButton(i["wallet_name"], callback_data=i["wallet_name"])
            for i in data
        ]
    inline_keyboard_markup = InlineKeyboardMarkup(
        build_menu(inline_keyboard_button, columns)
    )
    return inline_keyboard_markup


def wallet_keyboard(data, columns=2):
    keyboard_button = [KeyboardButton(text=i["wallet_name"]) for i in data]
    keyboard_menu = ReplyKeyboardMarkup(
        build_menu(keyboard_button, columns),
        resize_keyboard=True,
        one_time_keyboard=True,
    )
    return keyboard_menu
