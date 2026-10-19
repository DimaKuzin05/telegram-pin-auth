"""Start the API, ngrok tunnel, Telegram bot, and Flet client together."""

from __future__ import annotations

import asyncio
import json
import os
import re
import shutil
import signal
import subprocess
import sys
import time
from pathlib import Path
from urllib.error import URLError
from urllib.request import urlopen


ROOT = Path(__file__).resolve().parent
PROCESSES: list[tuple[str, subprocess.Popen]] = []


def read_env_file(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.exists():
        raise SystemExit("Файл .env не найден. Создайте его из .env.example и заполните настройки.")
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        values[key.strip()] = value
    return values


def stop_all() -> None:
    for name, process in reversed(PROCESSES):
        if process.poll() is None:
            print(f"Останавливаю {name}…", flush=True)
            if os.name == "nt":
                process.terminate()
            else:
                try:
                    os.killpg(process.pid, signal.SIGTERM)
                except ProcessLookupError:
                    pass
    deadline = time.time() + 5
    for _, process in reversed(PROCESSES):
        if process.poll() is None:
            try:
                process.wait(timeout=max(0.1, deadline - time.time()))
            except subprocess.TimeoutExpired:
                if os.name == "nt":
                    process.kill()
                else:
                    try:
                        os.killpg(process.pid, signal.SIGKILL)
                    except ProcessLookupError:
                        pass


def start(name: str, command: list[str], env: dict[str, str]) -> subprocess.Popen:
    print(f"Запускаю {name}…", flush=True)
    process = subprocess.Popen(
        command,
        cwd=ROOT,
        env=env,
        start_new_session=(os.name != "nt"),
    )
    PROCESSES.append((name, process))
    time.sleep(0.4)
    if process.poll() is not None:
        raise RuntimeError(f"{name} завершился сразу после запуска (код {process.returncode}).")
    return process


def wait_for_api(process: subprocess.Popen, timeout: float = 20) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        if process.poll() is not None:
            raise RuntimeError("API остановился до готовности.")
        try:
            with urlopen("http://127.0.0.1:3000/health", timeout=1) as response:
                if response.status == 200:
                    print("API готов.", flush=True)
                    return
        except (URLError, TimeoutError, OSError):
            time.sleep(0.4)
    raise RuntimeError("API не ответил на http://127.0.0.1:3000/health за 20 секунд.")


def ngrok_tunnels() -> list[dict]:
    try:
        with urlopen("http://127.0.0.1:4040/api/tunnels", timeout=1) as response:
            return json.loads(response.read().decode("utf-8")).get("tunnels", [])
    except (URLError, TimeoutError, OSError, ValueError):
        return []


def tunnel_matches(host: str) -> bool:
    expected = host.rstrip("/")
    for tunnel in ngrok_tunnels():
        address = tunnel.get("config", {}).get("addr", "")
        if tunnel.get("public_url", "").rstrip("/") == expected and address.endswith(":8080"):
            return True
    return False


def wait_for_tunnel(process: subprocess.Popen, host: str, timeout: float = 20) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        if process.poll() is not None:
            raise RuntimeError("ngrok остановился при запуске. Проверьте ngrok authtoken и занятость URL.")
        if tunnel_matches(host):
            print("ngrok готов и адрес совпадает с BOT_WEBHOOK_HOST.", flush=True)
            return
        time.sleep(0.4)
    tunnels = ngrok_tunnels()
    actual = ", ".join(t.get("public_url", "") for t in tunnels) or "туннель не найден"
    raise RuntimeError(f"Не найден ngrok-туннель для {host} на порту 8080 (найдено: {actual}).")


async def discover_bot_url(token: str) -> str:
    from aiogram import Bot

    bot = Bot(token)
    try:
        me = await bot.get_me()
        if not me.username:
            raise RuntimeError("У бота не задан username в Telegram.")
        return f"https://t.me/{me.username}"
    finally:
        await bot.session.close()


def main() -> int:
    env = os.environ.copy()
    env.update(read_env_file(ROOT / ".env"))

    token = env.get("TELEGRAM_BOT_TOKEN", "")
    if not re.fullmatch(r"[0-9]+:[A-Za-z0-9_-]{30,}", token):
        raise SystemExit("В .env укажите настоящий TELEGRAM_BOT_TOKEN от @BotFather.")
    for name in ("BOT_SHARED_SECRET", "BOT_WEBHOOK_SECRET", "BOT_WEBHOOK_HOST"):
        if not env.get(name) or "replace-with" in env[name]:
            raise SystemExit(f"Заполните {name} в .env.")
    if not (ROOT / "node_modules").exists():
        raise SystemExit("Node-пакеты не установлены. Сначала выполните npm install.")
    if not shutil.which("ngrok"):
        raise SystemExit("ngrok не найден. Установите его командой: brew install ngrok")

    bot_url = env.get("BOT_URL", "")
    if not bot_url or "your_bot_name" in bot_url:
        try:
            bot_url = asyncio.run(discover_bot_url(token))
            print("Username бота получен из Telegram.", flush=True)
        except Exception as error:
            raise SystemExit(f"Не удалось определить username бота: {error}. Укажите BOT_URL в .env.") from error
    env["BOT_URL"] = bot_url
    env.setdefault("API_URL", "http://127.0.0.1:3000")

    try:
        api = start("Express API", ["npm", "run", "dev"], env)
        wait_for_api(api)
        if tunnel_matches(env["BOT_WEBHOOK_HOST"]):
            print("Использую уже работающий ngrok-туннель.", flush=True)
        else:
            if ngrok_tunnels():
                raise RuntimeError("Уже запущен ngrok с другим адресом. Остановите его или укажите его HTTPS-адрес в BOT_WEBHOOK_HOST.")
            tunnel = start("ngrok", ["ngrok", "http", "8080"], env)
            wait_for_tunnel(tunnel, env["BOT_WEBHOOK_HOST"])
        start("Aiogram webhook bot", [sys.executable, "bot/main.py"], env)
        start("Flet client", [sys.executable, "client/main.py"], env)
        print("\nВсё запущено. Откройте чат с ботом и отправьте /start.", flush=True)
        print("PIN придёт в Telegram; введите его в окне Flet. Ctrl+C остановит все процессы.\n", flush=True)

        while True:
            for name, process in PROCESSES:
                code = process.poll()
                if code is not None:
                    raise RuntimeError(f"{name} завершился (код {code}).")
            time.sleep(0.5)
    except KeyboardInterrupt:
        print("\nОстанавливаю проект…", flush=True)
    except Exception as error:
        print(f"\nОшибка запуска: {error}", file=sys.stderr, flush=True)
        stop_all()
        return 1
    finally:
        stop_all()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
