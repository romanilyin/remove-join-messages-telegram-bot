import asyncio
import json
import os
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

# Bot token - replace with your actual bot token
BOT_TOKEN = "YOUR_BOT_TOKEN_HERE"

# File paths for configs
ALLOWED_CHATS_FILE = "allowed_chats.json"
PENDING_USERS_FILE = "pending_users.json"
PENDING_CHATS_FILE = "pending_chats.json"
ADMINS_FILE = "admins.json"

# Load allowed chats
def load_allowed_chats():
    if os.path.exists(ALLOWED_CHATS_FILE):
        with open(ALLOWED_CHATS_FILE, "r") as f:
            return json.load(f)
    return []

# Save allowed chats
def save_allowed_chats(chats):
    with open(ALLOWED_CHATS_FILE, "w") as f:
        json.dump(chats, f)

# Load pending users
def load_pending_users():
    if os.path.exists(PENDING_USERS_FILE):
        with open(PENDING_USERS_FILE, "r") as f:
            return json.load(f)
    return []

# Save pending users
def save_pending_users(users):
    with open(PENDING_USERS_FILE, "w") as f:
        json.dump(users, f)

# Load pending chats
def load_pending_chats():
    if os.path.exists(PENDING_CHATS_FILE):
        with open(PENDING_CHATS_FILE, "r") as f:
            return json.load(f)
    return []

# Save pending chats
def save_pending_chats(chats):
    with open(PENDING_CHATS_FILE, "w") as f:
        json.dump(chats, f)

# Load admins
def load_admins():
    if os.path.exists(ADMINS_FILE):
        with open(ADMINS_FILE, "r") as f:
            return json.load(f)
    return []

# Save admins
def save_admins(admins):
    with open(ADMINS_FILE, "w") as f:
        json.dump(admins, f)

# Check if user is admin
def is_admin(user_id):
    admins = load_admins()
    return str(user_id) in [str(a) for a in admins]

# Check if chat is allowed
def is_chat_allowed(chat_id):
    allowed_chats = load_allowed_chats()
    return str(chat_id) in [str(c) for c in allowed_chats]

# Scheduled deletions dictionary
scheduled_deletions = {}

async def handle_new_members(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle new member joining the chat"""
    if not is_chat_allowed(update.effective_chat.id):
        return  # Ignore if not in allowed chat
    
    if update.message and update.message.new_chat_members:
        # Get the message ID of the join notification
        message_id = update.message.id
        
        # Schedule deletion after 5 minutes (300 seconds)
        job_queue = context.job_queue
        job_queue.run_once(delete_message, when=300, data={'chat_id': update.effective_chat.id, 'message_id': message_id})

async def delete_message(context):
    """Delete a message after 5 minutes"""
    job = context.job
    data = job.data
    
    try:
        await context.bot.delete_message(chat_id=data['chat_id'], message_id=data['message_id'])
    except Exception as e:
        # Message might already be deleted or bot lacks permissions
        pass

async def add_chat_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Add current chat to allowed list (admin only)"""
    user_id = update.effective_user.id
    
    # Check if user is admin
    if not is_admin(user_id):
        await update.message.reply_text("У вас нет прав для выполнения этой команды.")
        return
    
    # Get chat info
    chat_id = update.effective_chat.id
    chat_title = update.effective_chat.title
    chat_username = update.effective_chat.username
    
    # Add to allowed chats
    allowed_chats = load_allowed_chats()
    if str(chat_id) not in [str(c) for c in allowed_chats]:
        allowed_chats.append({
            "id": chat_id,
            "title": chat_title,
            "username": chat_username
        })
        save_allowed_chats(allowed_chats)
        await update.message.reply_text(f"Чат '{chat_title}' добавлен в список разрешённых.")
    else:
        await update.message.reply_text("Этот чат уже в списке разрешённых.")

async def add_me_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Add user to pending list only"""
    user_id = update.effective_user.id
    user_name = update.effective_user.full_name
    
    # Add to pending users
    pending_users = load_pending_users()
    if str(user_id) not in [str(u) for u in pending_users]:
        pending_users.append({
            "id": user_id,
            "name": user_name
        })
        save_pending_users(pending_users)
        await update.message.reply_text("Ваш запрос отправлен администратору. Ожидайте подтверждения.")
    else:
        await update.message.reply_text("Вы уже подавали запрос на добавление.")

async def request_chat_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Add current chat to pending list (available for all users)"""
    user_id = update.effective_user.id
    user_name = update.effective_user.full_name
    
    # Get chat info
    chat_id = update.effective_chat.id
    chat_title = update.effective_chat.title
    chat_username = update.effective_chat.username
    
    # Add to pending chats
    pending_chats = load_pending_chats()
    if str(chat_id) not in [str(c) for c in pending_chats]:
        pending_chats.append({
            "id": chat_id,
            "title": chat_title,
            "username": chat_username,
            "requested_by": {
                "id": user_id,
                "name": user_name
            }
        })
        save_pending_chats(pending_chats)
        await update.message.reply_text("Запрос на добавление чата отправлен администратору. Ожидайте подтверждения.")
    else:
        await update.message.reply_text("Этот чат уже находится в списке ожидания.")

async def list_pending_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """List pending users and chats"""
    user_id = update.effective_user.id
    
    # Check if user is admin
    if not is_admin(user_id):
        await update.message.reply_text("У вас нет прав для выполнения этой команды.")
        return
    
    pending_users = load_pending_users()
    pending_chats = load_pending_chats()
    
    response = ""
    
    if pending_users:
        response += "*Ожидающие пользователи:*\n"
        for i, user in enumerate(pending_users, 1):
            response += f"{i}. {user['name']} (ID: `{user['id']}`) - `/adduser {user['id']}`\n"
        response += "\n"
    else:
        response += "*Нет ожидающих пользователей*\n\n"
    
    if pending_chats:
        response += "*Ожидающие чаты:*\n"
        for i, chat in enumerate(pending_chats, 1):
            requested_by = chat.get('requested_by', {})
            requested_by_info = f" (запрос от {requested_by.get('name', 'N/A')})" if requested_by else ""
            response += f"{i}. {chat['title']} (ID: `{chat['id']}`){requested_by_info} - `/addchatid {chat['id']}`\n"
        response += "\n"
    else:
        response += "*Нет ожидающих чатов*\n\n"
    
    # Add clickable commands for adding users/chats
    response += "*Команды для добавления:*\n"
    response += "Для добавления пользователя: `/adduser <user_id>`\n"
    response += "Для добавления чата: `/addchatid <chat_id>`\n"
    
    await update.message.reply_text(response, parse_mode='Markdown')

async def add_admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Add admin (usage: /addadmin <user_id>)"""
    user_id = update.effective_user.id
    
    # Check if user is admin
    if not is_admin(user_id):
        await update.message.reply_text("У вас нет прав для выполнения этой команды.")
        return
    
    if len(context.args) != 1:
        await update.message.reply_text("Использование: /addadmin <user_id>")
        return
    
    try:
        new_admin_id = int(context.args[0])
        
        # Add to admins
        admins = load_admins()
        if str(new_admin_id) not in [str(a) for a in admins]:
            admins.append(new_admin_id)
            save_admins(admins)
            await update.message.reply_text(f"Пользователь {new_admin_id} добавлен как администратор.")
        else:
            await update.message.reply_text("Этот пользователь уже является администратором.")
    except ValueError:
        await update.message.reply_text("Неверный формат ID пользователя.")

async def add_user_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Add user by ID (usage: /adduser <user_id>)"""
    user_id = update.effective_user.id
    
    # Check if user is admin
    if not is_admin(user_id):
        await update.message.reply_text("У вас нет прав для выполнения этой команды.")
        return
    
    if len(context.args) != 1:
        await update.message.reply_text("Использование: /adduser <user_id>")
        return
    
    try:
        target_user_id = int(context.args[0])
        
        # Remove from pending users
        pending_users = load_pending_users()
        original_count = len(pending_users)
        pending_users = [u for u in pending_users if u['id'] != target_user_id]
        
        if len(pending_users) < original_count:
            save_pending_users(pending_users)
            await update.message.reply_text(f"Пользователь {target_user_id} добавлен и удалён из списка ожидания.")
        else:
            await update.message.reply_text("Пользователь не найден в списке ожидания.")
    except ValueError:
        await update.message.reply_text("Неверный формат ID пользователя.")

async def add_chat_id_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Add chat by ID (usage: /addchatid <chat_id>)"""
    user_id = update.effective_user.id
    
    # Check if user is admin
    if not is_admin(user_id):
        await update.message.reply_text("У вас нет прав для выполнения этой команды.")
        return
    
    if len(context.args) != 1:
        await update.message.reply_text("Использование: /addchatid <chat_id>")
        return
    
    try:
        target_chat_id = int(context.args[0])
        
        # Find chat in pending list
        pending_chats = load_pending_chats()
        target_chat = None
        for chat in pending_chats:
            if chat['id'] == target_chat_id:
                target_chat = chat
                break
        
        if target_chat:
            # Move from pending to allowed
            pending_chats.remove(target_chat)
            save_pending_chats(pending_chats)
            
            allowed_chats = load_allowed_chats()
            if str(target_chat_id) not in [str(c) for c in allowed_chats]:
                allowed_chats.append(target_chat)
                save_allowed_chats(allowed_chats)
            
            await update.message.reply_text(f"Чат '{target_chat['title']}' добавлен и удалён из списка ожидания.")
        else:
            await update.message.reply_text("Чат не найден в списке ожидания.")
    except ValueError:
        await update.message.reply_text("Неверный формат ID чата.")

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start command handler"""
    await update.message.reply_text(
        "Добро пожаловать! Этот бот удаляет сообщения о новых участниках через 5 минут.\n\n"
        "Доступные команды:\n"
        "/addme - запрос на добавление (для обычных пользователей)\n"
        "/requestchat - запрос на добавление текущего чата\n"
        "\n"
        "Команды для администраторов:\n"
        "/addchat - добавить текущий чат в список разрешённых\n"
        "/listpending - список ожидающих пользователей и чатов\n"
        "/addadmin <user_id> - добавить нового администратора\n"
        "/adduser <user_id> - добавить пользователя из списка ожидания\n"
        "/addchatid <chat_id> - добавить чат из списка ожидания"
    )

def main():
    """Start the bot"""
    application = Application.builder().token(BOT_TOKEN).build()
    
    # Add handlers
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("addchat", add_chat_command))
    application.add_handler(CommandHandler("addme", add_me_command))
    application.add_handler(CommandHandler("requestchat", request_chat_command))
    application.add_handler(CommandHandler("listpending", list_pending_command))
    application.add_handler(CommandHandler("addadmin", add_admin_command))
    application.add_handler(CommandHandler("adduser", add_user_command))
    application.add_handler(CommandHandler("addchatid", add_chat_id_command))
    
    # Add handler for new members (only in allowed chats)
    application.add_handler(
        application.handlers.telegram_handler_class(handle_new_members)
    )
    
    # Start the bot
    application.run_polling()

if __name__ == '__main__':
    main()