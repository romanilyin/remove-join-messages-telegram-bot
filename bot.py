import json
import os
import re
import logging
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters

# Настройка логирования, чтобы ошибки были видны в systemd (journalctl)
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# File paths for configs
CONFIG_FILE = "config.json"
ALLOWED_CHATS_FILE = "allowed_chats.json"
PENDING_USERS_FILE = "pending_users.json"
PENDING_CHATS_FILE = "pending_chats.json"
ADMINS_FILE = "admins.json"

# MarkdownV2 special characters that need escaping
MDV2_SPECIAL_CHARS = r'_*[]()~`>#+-=|{}.!'

def escape_markdown_v2(text):
    """Escape special characters for Telegram MarkdownV2"""
    if not isinstance(text, str):
        text = str(text)
    return re.sub(f'([{re.escape(MDV2_SPECIAL_CHARS)}])', r'\\\1', text)

# Load config.json
def load_config():
    if not os.path.exists(CONFIG_FILE):
        raise FileNotFoundError(
            f"Файл {CONFIG_FILE} не найден. Скопируйте config.example.json в {CONFIG_FILE} и укажите токен."
        )
    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

config = load_config()
BOT_TOKEN = config.get("telegram_token")

if not BOT_TOKEN:
    raise ValueError("Поле 'telegram_token' отсутствует или пустое в config.json")

# Admins management (ИСПРАВЛЕНО: приведение всех ID к целым числам)
def load_admins():
    if os.path.exists(ADMINS_FILE):
        with open(ADMINS_FILE, "r", encoding="utf-8") as f:
            admins = json.load(f)
            # Приводим все ID к целым числам для единообразия
            return [int(a) for a in admins if str(a).strip()]
    # Fallback: use admins from config (only on first run)
    initial_admins = config.get("admins",[])
    # Приводим к целым числам
    admins_normalized =[int(a) for a in initial_admins if str(a).strip()]
    if admins_normalized:
        save_admins(admins_normalized)
    return admins_normalized

def save_admins(admins):
    # Сохраняем как список целых чисел
    with open(ADMINS_FILE, "w", encoding="utf-8") as f:
        json.dump(admins, f, ensure_ascii=False)

# Allowed chats management
def load_allowed_chats():
    if os.path.exists(ALLOWED_CHATS_FILE):
        with open(ALLOWED_CHATS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return[]

def save_allowed_chats(chats):
    with open(ALLOWED_CHATS_FILE, "w", encoding="utf-8") as f:
        json.dump(chats, f, ensure_ascii=False)

# Pending users management
def load_pending_users():
    if os.path.exists(PENDING_USERS_FILE):
        with open(PENDING_USERS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return[]

def save_pending_users(users):
    with open(PENDING_USERS_FILE, "w", encoding="utf-8") as f:
        json.dump(users, f, ensure_ascii=False)

# Pending chats management
def load_pending_chats():
    if os.path.exists(PENDING_CHATS_FILE):
        with open(PENDING_CHATS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return[]

def save_pending_chats(chats):
    with open(PENDING_CHATS_FILE, "w", encoding="utf-8") as f:
        json.dump(chats, f, ensure_ascii=False)

# Check if user is admin (ИСПРАВЛЕНО: сравнение чисел)
def is_admin(user_id):
    admins = load_admins()
    return int(user_id) in admins  # Сравниваем числа, а не строки

# Check if chat is allowed
def is_chat_allowed(chat_id):
    allowed_chats = load_allowed_chats()
    return str(chat_id) in[str(c.get('id')) for c in allowed_chats]

async def handle_new_members(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle new member joining the chat"""
    if not is_chat_allowed(update.effective_chat.id):
        return
    
    if update.message and update.message.new_chat_members:
        message_id = update.message.id
        job_queue = context.job_queue
        
        if not job_queue:
            logger.error("JobQueue не инициализирован! Проверьте, установлена ли зависимость python-telegram-bot[job-queue].")
            return

        # Добавляем задачу на удаление через 300 секунд (5 минут)
        job_queue.run_once(delete_message, when=300, data={
            'chat_id': update.effective_chat.id,
            'message_id': message_id
        })
        logger.info(f"Запланировано удаление сообщения {message_id} в чате {update.effective_chat.id} через 5 минут.")

async def delete_message(context):
    """Delete a message after 5 minutes"""
    job = context.job
    data = job.data
    try:
        await context.bot.delete_message(chat_id=data['chat_id'], message_id=data['message_id'])
        logger.info(f"Сообщение {data['message_id']} успешно удалено из чата {data['chat_id']}.")
    except Exception as e:
        # Теперь бот не будет молчать, если у него нет прав на удаление сообщений
        logger.error(f"Ошибка при удалении сообщения {data['message_id']} в чате {data['chat_id']}: {e}")

async def add_chat_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Add current chat to allowed list (admin only)"""
    user_id = update.effective_user.id
    if not is_admin(user_id):
        await update.message.reply_text("У вас нет прав для выполнения этой команды\\.", parse_mode='MarkdownV2')
        return
    
    chat_id = update.effective_chat.id
    chat_title = update.effective_chat.title or "Без названия"
    chat_username = update.effective_chat.username
    
    allowed_chats = load_allowed_chats()
    if str(chat_id) not in[str(c.get('id')) for c in allowed_chats]:
        allowed_chats.append({
            "id": chat_id,
            "title": chat_title,
            "username": chat_username
        })
        save_allowed_chats(allowed_chats)
        escaped_title = escape_markdown_v2(chat_title)
        await update.message.reply_text(f"Чат '{escaped_title}' добавлен в список разрешённых\\.", parse_mode='MarkdownV2')
    else:
        await update.message.reply_text("Этот чат уже в списке разрешённых\\.", parse_mode='MarkdownV2')

async def add_me_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Add user to pending list only"""
    user_id = update.effective_user.id
    user_name = update.effective_user.full_name
    
    pending_users = load_pending_users()
    if str(user_id) not in[str(u.get('id')) for u in pending_users]:
        pending_users.append({"id": user_id, "name": user_name})
        save_pending_users(pending_users)
        await update.message.reply_text("Ваш запрос отправлен администратору\\. Ожидайте подтверждения\\.", parse_mode='MarkdownV2')
    else:
        await update.message.reply_text("Вы уже подавали запрос на добавление\\.", parse_mode='MarkdownV2')

async def request_chat_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Add current chat to pending list (available for all users)"""
    user_id = update.effective_user.id
    user_name = update.effective_user.full_name
    chat_id = update.effective_chat.id
    chat_title = update.effective_chat.title or "Без названия"
    chat_username = update.effective_chat.username
    
    pending_chats = load_pending_chats()
    if str(chat_id) not in[str(c.get('id')) for c in pending_chats]:
        pending_chats.append({
            "id": chat_id,
            "title": chat_title,
            "username": chat_username,
            "requested_by": {"id": user_id, "name": user_name}
        })
        save_pending_chats(pending_chats)
        escaped_title = escape_markdown_v2(chat_title)
        await update.message.reply_text(f"Запрос на добавление чата '{escaped_title}' отправлен администратору\\. Ожидайте подтверждения\\.", parse_mode='MarkdownV2')
    else:
        await update.message.reply_text("Этот чат уже находится в списке ожидания\\.", parse_mode='MarkdownV2')

async def list_pending_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """List pending users and chats with clickable commands"""
    user_id = update.effective_user.id
    if not is_admin(user_id):
        await update.message.reply_text("У вас нет прав для выполнения этой команды\\.", parse_mode='MarkdownV2')
        return
    
    pending_users = load_pending_users()
    pending_chats = load_pending_chats()
    
    response = "*Ожидающие пользователи:*\n"
    
    if pending_users:
        for i, user in enumerate(pending_users, 1):
            escaped_name = escape_markdown_v2(user['name'])
            response += f"{i}\\. {escaped_name} \\(ID: `{user['id']}`\\) \\- `/adduser {user['id']}`\n"
        response += "\n"
    else:
        response += "Нет ожидающих пользователей\\.\n\n"
    
    response += "*Ожидающие чаты:*\n"
    
    if pending_chats:
        for i, chat in enumerate(pending_chats, 1):
            escaped_title = escape_markdown_v2(chat['title'])
            req = chat.get('requested_by', {})
            req_name = escape_markdown_v2(req.get('name', 'N/A')) if req else 'N/A'
            response += f"{i}\\. {escaped_title} \\(ID: `{chat['id']}`\\) \\(запрос от {req_name}\\) \\- `/addchatid {chat['id']}`\n"
        response += "\n"
    else:
        response += "Нет ожидающих чатов\\.\n\n"
    
    response += "*Команды для добавления:*\n"
    response += "`/adduser <user\\_id>` — добавить пользователя из списка ожидания\\.\n"
    response += "`/addchatid <chat\\_id>` — добавить чат из списка ожидания\\."
    
    await update.message.reply_text(response, parse_mode='MarkdownV2')

async def info_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show info about admins and allowed chats (admin only)"""
    user_id = update.effective_user.id
    if not is_admin(user_id):
        await update.message.reply_text("У вас нет прав для выполнения этой команды\\.", parse_mode='MarkdownV2')
        return
    
    admins = load_admins()
    allowed_chats = load_allowed_chats()
    
    response = "*📋 Информация о боте*\n\n"
    
    # Admins list
    response += "*Администраторы:*\n"
    if admins:
        for i, admin_id in enumerate(admins, 1):
            response += f"{i}\\. `{admin_id}`\n"
    else:
        response += "Нет администраторов\\.\n"
    response += "\n"
    
    # Allowed chats list
    response += "*Разрешённые чаты:*\n"
    if allowed_chats:
        for i, chat in enumerate(allowed_chats, 1):
            escaped_title = escape_markdown_v2(chat['title'])
            chat_id = chat['id']
            response += f"{i}\\. {escaped_title} \\(ID: `{chat_id}`\\)\n"
    else:
        response += "Нет разрешённых чатов\\.\n"
    
    await update.message.reply_text(response, parse_mode='MarkdownV2')

async def add_admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Add admin (usage: /addadmin <user_id>)"""
    user_id = update.effective_user.id
    if not is_admin(user_id):
        await update.message.reply_text("У вас нет прав для выполнения этой команды\\.", parse_mode='MarkdownV2')
        return
    
    if len(context.args) != 1:
        await update.message.reply_text("Использование: `/addadmin <user\\_id>`", parse_mode='MarkdownV2')
        return
    
    try:
        new_admin_id = int(context.args[0])
        admins = load_admins()
        if new_admin_id not in admins:  # Сравниваем числа напрямую
            admins.append(new_admin_id)
            save_admins(admins)
            await update.message.reply_text(f"Пользователь `{new_admin_id}` добавлен как администратор\\.", parse_mode='MarkdownV2')
        else:
            await update.message.reply_text("Этот пользователь уже является администратором\\.", parse_mode='MarkdownV2')
    except ValueError:
        await update.message.reply_text("Неверный формат ID пользователя\\.", parse_mode='MarkdownV2')

async def add_user_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Add user by ID (usage: /adduser <user_id>)"""
    user_id = update.effective_user.id
    if not is_admin(user_id):
        await update.message.reply_text("У вас нет прав для выполнения этой команды\\.", parse_mode='MarkdownV2')
        return
    
    if len(context.args) != 1:
        await update.message.reply_text("Использование: `/adduser <user\\_id>`", parse_mode='MarkdownV2')
        return
    
    try:
        target_user_id = int(context.args[0])
        pending_users = load_pending_users()
        original_count = len(pending_users)
        pending_users = [u for u in pending_users if u['id'] != target_user_id]
        
        if len(pending_users) < original_count:
            save_pending_users(pending_users)
            await update.message.reply_text(f"Пользователь `{target_user_id}` добавлен и удалён из списка ожидания\\.", parse_mode='MarkdownV2')
        else:
            await update.message.reply_text("Пользователь не найден в списке ожидания\\.", parse_mode='MarkdownV2')
    except ValueError:
        await update.message.reply_text("Неверный формат ID пользователя\\.", parse_mode='MarkdownV2')

async def add_chat_id_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Add chat by ID (usage: /addchatid <chat_id>)"""
    user_id = update.effective_user.id
    if not is_admin(user_id):
        await update.message.reply_text("У вас нет прав для выполнения этой команды\\.", parse_mode='MarkdownV2')
        return
    
    if len(context.args) != 1:
        await update.message.reply_text("Использование: `/addchatid <chat\\_id>`", parse_mode='MarkdownV2')
        return
    
    try:
        target_chat_id = int(context.args[0])
        pending_chats = load_pending_chats()
        target_chat = None
        for chat in pending_chats:
            if chat['id'] == target_chat_id:
                target_chat = chat
                break
        
        if target_chat:
            pending_chats.remove(target_chat)
            save_pending_chats(pending_chats)
            
            allowed_chats = load_allowed_chats()
            if str(target_chat_id) not in[str(c.get('id')) for c in allowed_chats]:
                allowed_chats.append(target_chat)
                save_allowed_chats(allowed_chats)
            
            escaped_title = escape_markdown_v2(target_chat['title'])
            await update.message.reply_text(f"Чат '{escaped_title}' добавлен и удалён из списка ожидания\\.", parse_mode='MarkdownV2')
        else:
            await update.message.reply_text("Чат не найден в списке ожидания\\.", parse_mode='MarkdownV2')
    except ValueError:
        await update.message.reply_text("Неверный формат ID чата\\.", parse_mode='MarkdownV2')

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start command handler"""
    help_text = (
        "Добро пожаловать\\! Этот бот удаляет сообщения о новых участниках через 5 минут\\.\n\n"
        "*Доступные команды:*\n"
        "`/addme` — запрос на добавление \\(для обычных пользователей\\)\n"
        "`/requestchat` — запрос на добавление текущего чата\n"
        "`/info` — информация об админах и разрешённых чатах \\(только для админов\\)\n"
        "\n"
        "*Команды для администраторов:*\n"
        "`/addchat` — добавить текущий чат в список разрешённых\n"
        "`/listpending` — список ожидающих пользователей и чатов\n"
        "`/addadmin <user\\_id>` — добавить нового администратора\n"
        "`/adduser <user\\_id>` — добавить пользователя из списка ожидания\n"
        "`/addchatid <chat\\_id>` — добавить чат из списка ожидания"
    )
    await update.message.reply_text(help_text, parse_mode='MarkdownV2')

def main():
    application = Application.builder().token(BOT_TOKEN).build()
    
    # Command handlers
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("addchat", add_chat_command))
    application.add_handler(CommandHandler("addme", add_me_command))
    application.add_handler(CommandHandler("requestchat", request_chat_command))
    application.add_handler(CommandHandler("listpending", list_pending_command))
    application.add_handler(CommandHandler("info", info_command))
    application.add_handler(CommandHandler("addadmin", add_admin_command))
    application.add_handler(CommandHandler("adduser", add_user_command))
    application.add_handler(CommandHandler("addchatid", add_chat_id_command))
    
    # New member handler
    application.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, handle_new_members))
    
    application.run_polling()

if __name__ == '__main__':
    main()