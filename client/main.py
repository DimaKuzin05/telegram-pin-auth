import os

import flet as ft
import httpx

API_URL = os.getenv("API_URL", "http://127.0.0.1:3000").rstrip("/")
BOT_URL = os.getenv("BOT_URL", "https://t.me/your_bot_name")


def main(page: ft.Page):
    page.title = "Telegram Login"
    page.theme_mode = ft.ThemeMode.LIGHT
    page.bgcolor = "#f4f6fb"
    page.padding = 24
    page.window.width = 430
    page.window.height = 760
    page.window.min_width = 360
    page.window.min_height = 620
    page.horizontal_alignment = ft.CrossAxisAlignment.CENTER
    page.vertical_alignment = ft.MainAxisAlignment.CENTER

    def open_bot(_):
        page.launch_url(BOT_URL)

    def show_login():
        pin = ft.TextField(
            label="PIN-код",
            hint_text="Введите 6 цифр из Telegram",
            prefix_icon=ft.Icons.LOCK_OUTLINE,
            keyboard_type=ft.KeyboardType.NUMBER,
            max_length=6,
            autofocus=True,
            border_radius=12,
            text_size=16,
        )
        error = ft.Text("", color="#b42318", size=13)

        async def login(_):
            value = (pin.value or "").strip()
            if len(value) != 6 or not value.isdigit():
                error.value = "Введите шестизначный PIN-код"
                page.update()
                return
            try:
                async with httpx.AsyncClient(timeout=8) as client:
                    response = await client.post(f"{API_URL}/auth", json={"key": value})
                if response.is_success:
                    show_profile(response.json())
                else:
                    error.value = response.json().get("error", "Не удалось выполнить вход")
                    page.update()
            except httpx.HTTPError:
                error.value = "Сервер недоступен. Проверьте подключение и попробуйте снова."
                page.update()

        page.controls.clear()
        page.add(
            ft.Container(
                width=360,
                padding=30,
                border_radius=22,
                bgcolor=ft.Colors.WHITE,
                shadow=ft.BoxShadow(blur_radius=24, color="#14213d14", offset=ft.Offset(0, 8)),
                content=ft.Column(
                    horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
                    spacing=16,
                    controls=[
                        ft.Container(
                            width=64,
                            height=64,
                            border_radius=20,
                            bgcolor="#e8efff",
                            alignment=ft.Alignment(0, 0),
                            content=ft.Icon(ft.Icons.TELEGRAM, color="#2878e5", size=34),
                        ),
                        ft.Text("Вход в приложение", size=25, weight=ft.FontWeight.BOLD, color="#172033"),
                        ft.Text("Получите одноразовый код у Telegram-бота", size=14, color="#697386"),
                        pin,
                        error,
                        ft.Button(
                            "Войти",
                            icon=ft.Icons.ARROW_FORWARD,
                            on_click=login,
                            style=ft.ButtonStyle(
                                bgcolor="#2878e5",
                                color=ft.Colors.WHITE,
                                padding=16,
                                shape=ft.RoundedRectangleBorder(radius=12),
                            ),
                        ),
                        ft.TextButton("Открыть Telegram-бота", icon=ft.Icons.OPEN_IN_NEW, on_click=open_bot),
                    ],
                ),
            )
        )
        page.update()

    def show_profile(user: dict):
        name = user.get("first_name") or "Пользователь"
        last_name = user.get("last_name") or "—"
        username = f"@{user['username']}" if user.get("username") else "Не указан"
        avatar = ft.CircleAvatar(
            radius=48,
            bgcolor="#dbe8ff",
            color="#2878e5",
            content=ft.Text(name[:1].upper(), size=36, weight=ft.FontWeight.BOLD),
        )
        if user.get("photo_url"):
            avatar.foreground_image_src = user["photo_url"]

        def row(label: str, value: str):
            return ft.Container(
                padding=14,
                border_radius=12,
                bgcolor="#f5f7fb",
                content=ft.Column(
                    spacing=4,
                    controls=[ft.Text(label, size=12, color="#697386"), ft.Text(value, size=16, color="#172033")],
                ),
            )

        page.controls.clear()
        page.add(
            ft.Container(
                width=360,
                padding=30,
                border_radius=22,
                bgcolor=ft.Colors.WHITE,
                shadow=ft.BoxShadow(blur_radius=24, color="#14213d14", offset=ft.Offset(0, 8)),
                content=ft.Column(
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    spacing=18,
                    controls=[
                        avatar,
                        ft.Text("Профиль", size=25, weight=ft.FontWeight.BOLD, color="#172033"),
                        row("Имя", name),
                        row("Фамилия", last_name),
                        row("Имя пользователя", username),
                        ft.OutlinedButton("Выйти", icon=ft.Icons.LOGOUT, on_click=lambda _: show_login()),
                    ],
                ),
            )
        )
        page.update()

    show_login()


ft.run(main)
