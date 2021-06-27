import json, os
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton


def build_menu(buttons, n_cols, header_buttons=None, footer_buttons=None):
    menu = [buttons[i : i + n_cols] for i in range(0, len(buttons), n_cols)]
    if header_buttons:
        menu.insert(0, [header_buttons])
    if footer_buttons:
        menu.append([footer_buttons])
    return menu


def wallet_menu(data, columns=1):
    inline_keyboard_button = [
        InlineKeyboardButton(
            i["wallet_name"], callback_data=i["wallet_address"]["base58"]
        )
        for i in data
    ]
    inline_keyboard_markup = InlineKeyboardMarkup(
        build_menu(inline_keyboard_button, columns)
    )
    return inline_keyboard_markup
