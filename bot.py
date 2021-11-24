import sqlite3
import telebot
from telebot import types
import os
import html
import logging
from text import *

TOKEN = open("token.txt", "r").read()
DB = f'{os.path.dirname(os.path.abspath(__file__))}/telebot.db'
bot = telebot.TeleBot(TOKEN)
logging.basicConfig(
    filename=f'{os.path.dirname(os.path.abspath(__file__))}/logs.log', level=logging.WARNING)

if not TOKEN:
    print("Please add bot token!")
    exit()


def _get_table_name(chat_id):
    return f'group{str(chat_id).replace("-", "_")}'


def _check_if_table_exist(chat_id):
    table = _get_table_name(chat_id)
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute(
        f"""SELECT name FROM sqlite_master WHERE type='table' AND name='{table}';""")
    exits = c.fetchone()
    conn.close()
    return True if exits else False


def _create_new_table(chat_id):
    table = _get_table_name(chat_id)
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute(
        f"""CREATE TABLE {table} (id INTEGER PRIMARY KEY AUTOINCREMENT, product TEXT)""")
    conn.commit()
    conn.close()


def _activate_bot(msg):
    bot.send_message(msg.chat.id, ACTIVATE_BOT, parse_mode="html")


def welcome_message(msg):
    bot.send_message(
        msg.chat.id, f"Hi {msg.from_user.first_name.title()} 👋\n" + WELCOME, parse_mode="html")


def confirm():
    markup = types.InlineKeyboardMarkup()
    markup.add(
        types.InlineKeyboardButton(
            text=NO,
            callback_data=f"no"
        ),
        types.InlineKeyboardButton(
            text=YES,
            callback_data=f"yes"
        )
    )
    return markup


@bot.message_handler(commands=['clear'])
def command_delete(msg):
    if _check_if_table_exist(msg.chat.id):
        bot.reply_to(msg, CONFIRM, reply_markup=confirm())
    else:
        if not _check_if_table_exist(msg.chat.id):
            _activate_bot(msg)
            return


@bot.callback_query_handler(func=lambda call: call.data in ["no", 'yes'])
def command_delete_handler(call):
    if call.data == "no":
        bot.delete_message(call.message.chat.id, call.message.message_id)
    elif call.data == "yes":
        table = _get_table_name(call.message.chat.id)
        conn = sqlite3.connect(DB)
        c = conn.cursor()
        c.execute(f"DELETE FROM {table};")
        conn.commit()
        bot.edit_message_text(chat_id=call.message.chat.id,
                              text=CLEAR, message_id=call.message.message_id)


@bot.message_handler(commands=['help'])
def command_help(msg):
    if _check_if_table_exist(msg.chat.id):
        welcome_message(msg)
    else:
        if not _check_if_table_exist(msg.chat.id):
            _activate_bot(msg)
            return


@bot.message_handler(commands=['start'])
def command_start(msg):
    if _check_if_table_exist(msg.chat.id):
        welcome_message(msg)
    else:
        _create_new_table(msg.chat.id)
        welcome_message(msg)


@bot.message_handler(commands=['list'])
def command_list(msg, edit_mode=False):
    if not _check_if_table_exist(msg.chat.id):
        _activate_bot(msg)
        return
    table = _get_table_name(msg.chat.id)
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute(f"SELECT count(*), product FROM {table} GROUP BY product;")
    list = c.fetchall()
    if not list:
        bot.reply_to(msg, EMPTY)
        return
    len_nr = len(str(len(list)))
    text = ""
    for i, x in enumerate(list):
        text += f"<code>{i + 1:{len_nr}d}. <b>{x[0]}x</b>-</code> {html.escape(x[1].title())}\n"
    if edit_mode:
        bot.send_message(msg.chat.id, text,
                         reply_markup=makeKeyboard(list), parse_mode="html")
    else:
        bot.send_message(msg.chat.id, text, parse_mode="html")


@bot.message_handler(commands=['add'])
def command_add(msg):
    if not _check_if_table_exist(msg.chat.id):
        _activate_bot(msg)
        return
    try:
        text = msg.text[5:]
        products = ",".join(
            '("' + p.strip().lower() + '")' for p in text.split(',') if p)
        if not products:
            return
        table = _get_table_name(msg.chat.id)
        conn = sqlite3.connect(DB)
        c = conn.cursor()
        c.execute(f"INSERT INTO {table} (product) VALUES {products};")
        conn.commit()
    except Exception as e:
        print(e)
        bot.reply_to(msg, WRONG)
    conn.close()


@bot.message_handler(commands=['edit'])
def command_edit(msg):
    if not _check_if_table_exist(msg.chat.id):
        _activate_bot(msg)
        return
    command_list(msg, edit_mode=True)


def makeKeyboard(list):
    markup = types.InlineKeyboardMarkup()

    for i, p in enumerate(list):
        markup.add(
            types.InlineKeyboardButton(
                # Spaces added to alight text to left side
                text=f"{REMOVE}{p[1].title()}{' '*50}.",
                callback_data=f"{i},del"
            ),
            types.InlineKeyboardButton(
                text=MINUS,
                callback_data=f"{i},rm"
            ),
            types.InlineKeyboardButton(
                text=PLUS,
                callback_data=f"{i},add"
            ),
        )
    markup.add(
        types.InlineKeyboardButton(
            text=CLOSE,
            callback_data=f"0,clo"
        ),
        types.InlineKeyboardButton(
            text=REFRESH,
            callback_data=f"0,ref"
        )
    )

    return markup


@bot.callback_query_handler(func=lambda call: True)
def handle_query(call):
    table = _get_table_name(call.message.chat.id)
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute(f"SELECT count(*), product FROM {table} GROUP BY product;")
    list = c.fetchall()
    try:
        id, action = call.data.split(',')
        id = int(id)
        if action == "add":
            c.execute(
                f"INSERT INTO {table} (product) VALUES ('{list[id][1]}');")
            conn.commit()
        elif action == "rm":
            c.execute(
                f"DELETE FROM {table} WHERE product = '{list[id][1]}' LIMIT 1;")
            conn.commit()
        elif action == "del":
            c.execute(f"DELETE FROM {table} WHERE product = '{list[id][1]}';")
            conn.commit()

        c.execute(f"SELECT count(*), product FROM {table} GROUP BY product;")
        list = c.fetchall()

        len_nr = len(str(len(list)))
        text = ""
        for i, x in enumerate(list):
            text += f"<code>{i + 1:{len_nr}d}. <b>{x[0]}x</b>-</code> {html.escape(x[1].title())}\n"

        bot.edit_message_text(
            chat_id=call.message.chat.id,
            text=text if text else EMPTY,
            message_id=call.message.message_id,
            reply_markup=None if not list or action == "clo" else makeKeyboard(
                list),
            parse_mode='HTML'
        )
    except Exception as e:
        logging.warning(e)


bot.polling()
