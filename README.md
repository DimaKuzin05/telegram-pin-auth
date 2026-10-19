# Telegram PIN Login

Учебное клиент-серверное приложение для входа по одноразовому PIN из Telegram:

- клиент: Python и Flet;
- API: TypeScript и Express;
- Telegram-бот: Python и Aiogram, webhook;
- PIN: шесть цифр, действует 15 минут и используется один раз.

## Требования

- Python 3.12 или совместимая версия;
- Node.js и npm;
- ngrok для HTTPS webhook Telegram;
- Telegram-бот, созданный через [@BotFather](https://t.me/BotFather).

## Подготовка

Из корня проекта создайте виртуальное окружение и установите зависимости:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt -r bot/requirements.txt
npm install
cp .env.example .env
```

Откройте `.env` и задайте:

- `TELEGRAM_BOT_TOKEN` — токен бота от @BotFather;
- `BOT_SHARED_SECRET` — случайный секрет для связи бота с API;
- `BOT_WEBHOOK_SECRET` — отдельный случайный секрет webhook;
- `BOT_WEBHOOK_HOST` — HTTPS-адрес ngrok без завершающего `/`.

Секреты можно создать командами `openssl rand -hex 32`; используйте разные значения. Токен ngrok и `TELEGRAM_BOT_TOKEN` — разные токены. Не публикуйте `.env` и не отправляйте его в Git.

Установите ngrok на macOS и настройте его authtoken один раз:

```bash
brew install ngrok
ngrok config add-authtoken ВАШ_NGROK_AUTHTOKEN
```

`run.py` запускает туннель сам. Укажите его HTTPS-адрес в `BOT_WEBHOOK_HOST`. Если ngrok выдаёт новый адрес при следующем запуске, обновите переменную в `.env`. `BOT_URL` можно указать как `https://t.me/имя_бота`; если не указать, скрипт получит username бота у Telegram автоматически.

## Запуск всего проекта

Запустите из корня проекта:

```bash
.venv/bin/python run.py
```

Скрипт запускает Express API, ngrok, Aiogram и окно Flet. Не закрывайте терминал, пока пользуетесь приложением. Чтобы остановить все компоненты, нажмите `Ctrl+C` в терминале запуска.

Откройте чат с ботом и отправьте `/start`. Введите последний полученный PIN в приложении: новый PIN аннулирует предыдущий.

## Ручной запуск компонентов

Можно запускать компоненты в отдельных терминалах из корня проекта:

```bash
npm run dev
```

```bash
set -a
source .env
set +a
.venv/bin/python bot/main.py
```

```bash
ngrok http 8080
```

```bash
API_URL=http://127.0.0.1:3000 BOT_URL=https://t.me/имя_бота .venv/bin/python client/main.py
```

Убедитесь, что адрес ngrok совпадает со значением `BOT_WEBHOOK_HOST` в `.env`.

## API

- `GET /health` — проверка сервера, ответ `{ "status": "ok" }`.
- `POST /bot/credentials` — внутренний endpoint бота; принимает данные профиля Telegram и требует заголовок `x-bot-secret`.
- `POST /auth` — принимает `{ "key": "123456" }` и возвращает профиль Telegram при действующем PIN.
- Aiogram принимает webhook updates на `/aiogram/webhook` на порту `8080`.

PIN-коды хранятся в памяти API и сбрасываются при перезапуске. Для постоянного развёртывания замените это хранилище на базу данных.

## Диагностика

- Если `run.py` сообщает, что API не запустился, проверьте, не занят ли порт `3000`.
- Если ngrok не запускается, проверьте authtoken и совпадение его HTTPS-адреса с `BOT_WEBHOOK_HOST`.
- Если Telegram не присылает PIN, проверьте, что `npm run dev` и бот запущены, затем отправьте боту `/start` ещё раз.
- Проверить API можно по адресу `http://127.0.0.1:3000/health`.
