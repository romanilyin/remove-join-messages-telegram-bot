# Телеграм-бот для удаления сообщений о вступлении в чат

Это простой Telegram-бот, который автоматически удаляет сообщения о вступлении новых участников через 5 минут. Он позволяет администраторам контролировать, какие чаты отслеживаются, и управлять запросами на доступ.

## Возможности
- Автоматическое удаление сообщений о вступлении новых участников через 5 минут
- Управление доступом администраторами
- Списки разрешённых и ожидающих чатов и пользователей
- Система запросов для пользователей и чатов на добавление в разрешённый список
- Моноширинные команды для удобного копирования в админ-панели

## Установка
1. Клонируйте репозиторий:
   ```bash
   cd /opt
   git clone https://github.com/romanilyin/remove-join-messages-telegram-bot.git
   cd remove-join-messages-telegram-bot
   ```

2. Установите зависимости:
   ```bash
   pip3 install -r requirements.txt
   ```

3. Получите токен бота у @BotFather (https://t.me/BotFather).

4. Скопируйте пример конфигурации и отредактируйте его:
   ```bash
   cp config.example.json config.json
   nano config.json
   ```

   Вставьте ваш токен в поле "telegram_token".
   Добавьте ваш Telegram ID в массив "admins" (ваш ID можно узнать с помощью ботов, например @userinfobot).
   Альтернатива: вы можете передать токен через переменную окружения TELEGRAM_TOKEN.

5. Создайте файл сервиса systemd /etc/systemd/system/remove-join-messages-bot.service:

   ```ini
   [Unit]
   Description=Remove Join Messages Telegram Bot
   After=network.target

   [Service]
   User=ваш_пользователь_системы
   WorkingDirectory=/opt/remove-join-messages-telegram-bot
   ExecStart=/usr/bin/python3 /opt/remove-join-messages-telegram-bot/bot.py
   Restart=always
   Environment="PYTHONPATH=/opt/remove-join-messages-telegram-bot"

   # Если предпочитаете передавать токен через переменную окружения, раскомментируйте строку ниже:
   # Environment="TELEGRAM_TOKEN=ВАШ_ТОКЕН_БОТА_TELEGRAM"

   [Install]
   WantedBy=multi-user.target
   ```

6. Запустите сервис:
   ```bash
   sudo systemctl daemon-reload
   sudo systemctl enable remove-join-messages-bot
   sudo systemctl start remove-join-messages-bot
   ```

7. Добавьте вашего бота в чаты, которые хотите отслеживать, и предоставьте ему разрешение "Удалять сообщения".

## Файлы конфигурации
Бот использует JSON-файлы для хранения своего состояния:
- allowed_chats.json — Список чатов, в которых работает бот
- pending_users.json — Список пользователей, ожидающих подтверждения
- pending_chats.json — Список чатов, ожидающих подтверждения
- admins.json — Список идентификаторов пользователей-администраторов

## Лицензия
Этот проект лицензирован по лицензии MIT — подробности см. в файле LICENSE.