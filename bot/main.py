import asyncio
import os
from aiohttp import web
import httpx
from aiogram import Bot, Dispatcher
from aiogram.filters import CommandStart
from aiogram.types import Message, Update

BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
API_BASE_URL = os.getenv("API_BASE_URL", "http://127.0.0.1:3000").rstrip("/")
BOT_SHARED_SECRET = os.environ["BOT_SHARED_SECRET"]
WEBHOOK_HOST = os.environ["BOT_WEBHOOK_HOST"]  # Public HTTPS origin from ngrok or deployment.
WEBHOOK_PATH = "/aiogram/webhook"
WEBHOOK_SECRET = os.environ.get("BOT_WEBHOOK_SECRET", "")
WEB_SERVER_HOST = os.getenv("WEB_SERVER_HOST", "0.0.0.0")
WEB_SERVER_PORT = int(os.getenv("WEB_SERVER_PORT", "8080"))

bot = Bot(BOT_TOKEN)
dp = Dispatcher()


@dp.message(CommandStart())
async def start(message: Message) -> None:
    if message.from_user is None:
        return
    telegram_user = message.from_user.model_dump(
        include={"id", "first_name", "last_name", "username"},
        exclude_none=True,
    )
    async with httpx.AsyncClient(timeout=10) as client:
        response = await client.post(
            f"{API_BASE_URL}/bot/credentials",
            headers={"x-bot-secret": BOT_SHARED_SECRET},
            json={"user": telegram_user},
        )
    if response.is_error:
        await message.answer("Не удалось создать код входа. Попробуйте позже.")
        return
    payload = response.json()
    await message.answer(
        f"Ваш PIN для входа в приложение: <code>{payload['pin']}</code>\n"
        "Код одноразовый и действует 15 минут.",
        parse_mode="HTML",
    )


async def handle_webhook(request: web.Request) -> web.Response:
    if WEBHOOK_SECRET and request.headers.get("X-Telegram-Bot-Api-Secret-Token") != WEBHOOK_SECRET:
        return web.Response(status=401)
    try:
        data = await request.json()
        update = Update.model_validate(data, context={"bot": bot})
        await dp.feed_update(bot, update)
    except Exception:
        return web.Response(status=400)
    return web.Response(status=200)


async def main() -> None:
    app = web.Application(client_max_size=1024 * 1024)
    app.router.add_post(WEBHOOK_PATH, handle_webhook)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, WEB_SERVER_HOST, WEB_SERVER_PORT)
    await site.start()
    await bot.set_webhook(
        f"{WEBHOOK_HOST.rstrip('/')}{WEBHOOK_PATH}",
        secret_token=WEBHOOK_SECRET or None,
        allowed_updates=dp.resolve_used_update_types(),
    )
    print(f"Aiogram webhook listening on http://{WEB_SERVER_HOST}:{WEB_SERVER_PORT}{WEBHOOK_PATH}")
    try:
        await asyncio.Event().wait()
    finally:
        await bot.delete_webhook()
        await runner.cleanup()
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
