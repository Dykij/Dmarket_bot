"""Telegram handler for Authentication and Security.

Provides commands for security management:
- /auth - Authentication menu
- /2fa - Two-factor authentication setup
- /security - Security overview

Usage:
    handler = AuthHandler(security_manager, jwt_auth)
    app.add_handler(CommandHandler("auth", handler.handle_auth_command))
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import CallbackQueryHandler, CommandHandler, ContextTypes

from src.security import (
    JWTAuth,
    SecurityManager,
    TokenType,
    create_jwt_auth,
    create_security_manager,
)

logger = logging.getLogger(__name__)


class AuthHandler:
    """Handler for authentication and security commands.

    Manages user authentication, 2FA, and security settings.
    """

    def __init__(
        self,
        security_manager: SecurityManager | None = None,
        jwt_auth: JWTAuth | None = None,
        secret_key: str = "default-secret-change-in-production",
    ) -> None:
        """Initialize handler.

        Args:
            security_manager: Security manager instance
            jwt_auth: JWT auth instance
            secret_key: Secret key for JWT signing
        """
        self._security = security_manager or create_security_manager()
        self._jwt_auth = jwt_auth or create_jwt_auth(secret_key=secret_key)

        # Store pending 2FA setups
        self._pending_2fa: dict[int, dict[str, Any]] = {}

        # API key storage (in production, use database)
        self._api_keys: dict[int, list[dict[str, Any]]] = {}

    async def handle_auth_command(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
    ) -> None:
        """Handle /auth command."""
        if not update.message or not update.effective_user:
            return

        user_id = update.effective_user.id

        # Get security summary
        summary = self._security.get_security_summary(user_id)
        score = summary.get("security_score", 50)

        # Score visualization
        if score >= 80:
            score_emoji = "🟢"
            score_text = "Высокий"
        elif score >= 50:
            score_emoji = "🟡"
            score_text = "Средний"
        else:
            score_emoji = "🔴"
            score_text = "Низкий"

        text = (
            f"🔐 *Безопасность и авторизация*\n\n"
            f"*Security Score:* {score_emoji} {score}/100 ({score_text})\n\n"
            f"*Статус:*\n"
            f"├ 2FA: {'✅ Включён' if summary.get('2fa_enabled') else '❌ Выключен'}\n"
            f"├ Backup коды: {summary.get('backup_codes_remaining', 0)} шт.\n"
            f"├ IP Whitelist: {summary.get('ip_whitelist_count', 0)} адресов\n"
            f"└ Недавние события: {summary.get('recent_security_events', 0)}\n\n"
            f"_Настройте безопасность для защиты аккаунта._"
        )

        keyboard = self._create_auth_keyboard(summary.get("2fa_enabled", False))

        await update.message.reply_text(
            text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown",
        )

    async def handle_2fa_command(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
    ) -> None:
        """Handle /2fa command - direct 2FA management."""
        if not update.message or not update.effective_user:
            return

        user_id = update.effective_user.id
        is_enabled = self._security.is_2fa_enabled(user_id)

        if is_enabled:
            text = (
                "🔐 *Двухфакторная аутентификация*\n\n"
                "✅ 2FA *включена* для вашего аккаунта.\n\n"
                "Для отключения введите код из приложения."
            )
            keyboard = [
                [InlineKeyboardButton("❌ Отключить 2FA", callback_data="auth:2fa:disable_start")],
                [InlineKeyboardButton("🔑 Новые backup коды", callback_data="auth:2fa:new_backup")],
                [InlineKeyboardButton("◀️ Назад", callback_data="auth:back")],
            ]
        else:
            text = (
                "🔐 *Двухфакторная аутентификация*\n\n"
                "❌ 2FA *не включена*.\n\n"
                "Двухфакторная аутентификация добавляет дополнительный "
                "уровень защиты вашего аккаунта."
            )
            keyboard = [
                [InlineKeyboardButton("✅ Включить 2FA", callback_data="auth:2fa:setup")],
                [InlineKeyboardButton("◀️ Назад", callback_data="auth:back")],
            ]

        await update.message.reply_text(
            text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown",
        )

    async def handle_security_command(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
    ) -> None:
        """Handle /security command - security overview."""
        if not update.message or not update.effective_user:
            return

        user_id = update.effective_user.id

        # Get audit logs
        logs = self._security.get_audit_logs(user_id=user_id, limit=10)

        text = "📋 *Журнал безопасности*\n\n"

        if not logs:
            text += "_Нет записей в журнале._"
        else:
            for log in logs[:5]:
                time_str = log.timestamp.strftime("%d.%m %H:%M")
                status = "✅" if log.success else "❌"
                text += f"{status} `{time_str}` {log.action}\n"

        text += (
            "\n\n*Рекомендации:*\n"
            "• Включите 2FA для защиты\n"
            "• Добавьте IP в whitelist\n"
            "• Регулярно проверяйте журнал"
        )

        keyboard = [
            [InlineKeyboardButton("🔐 2FA", callback_data="auth:2fa:menu")],
            [InlineKeyboardButton("🌐 IP Whitelist", callback_data="auth:ip:menu")],
            [InlineKeyboardButton("🔑 API ключи", callback_data="auth:api:menu")],
            [InlineKeyboardButton("◀️ Назад", callback_data="auth:back")],
        ]

        await update.message.reply_text(
            text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown",
        )

    async def handle_callback(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
    ) -> None:
        """Handle auth callback queries."""
        query = update.callback_query
        if not query or not query.data or not update.effective_user:
            return

        await query.answer()

        user_id = update.effective_user.id
        data = query.data
        parts = data.split(":")

        if len(parts) < 2:
            return

        section = parts[1]

        # 2FA handlers
        if section == "2fa":
            action = parts[2] if len(parts) > 2 else "menu"
            await self._handle_2fa(query, user_id, action, context)

        # IP Whitelist handlers
        elif section == "ip":
            action = parts[2] if len(parts) > 2 else "menu"
            await self._handle_ip_whitelist(query, user_id, action)

        # API Key handlers
        elif section == "api":
            action = parts[2] if len(parts) > 2 else "menu"
            await self._handle_api_keys(query, user_id, action)

        # Token handlers
        elif section == "token":
            action = parts[2] if len(parts) > 2 else "generate"
            await self._handle_tokens(query, user_id, action)

        elif section == "back":
            summary = self._security.get_security_summary(user_id)
            keyboard = self._create_auth_keyboard(summary.get("2fa_enabled", False))
            await query.edit_message_text(
                "🔐 *Безопасность и авторизация*\n\nВыберите раздел:",
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode="Markdown",
            )

    async def _handle_2fa(
        self,
        query: Any,
        user_id: int,
        action: str,
        context: ContextTypes.DEFAULT_TYPE,
    ) -> None:
        """Handle 2FA related actions."""
        if action == "menu":
            is_enabled = self._security.is_2fa_enabled(user_id)
            if is_enabled:
                text = "🔐 *2FA включена*\n\nВаш аккаунт защищён двухфакторной аутентификацией."
                keyboard = [
                    [InlineKeyboardButton("❌ Отключить", callback_data="auth:2fa:disable_start")],
                    [InlineKeyboardButton("🔑 Backup коды", callback_data="auth:2fa:show_backup")],
                    [InlineKeyboardButton("◀️ Назад", callback_data="auth:back")],
                ]
            else:
                text = "🔐 *2FA отключена*\n\nВключите для дополнительной защиты."
                keyboard = [
                    [InlineKeyboardButton("✅ Включить", callback_data="auth:2fa:setup")],
                    [InlineKeyboardButton("◀️ Назад", callback_data="auth:back")],
                ]

            await query.edit_message_text(
                text,
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode="Markdown",
            )

        elif action == "setup":
            # Start 2FA setup
            setup_info = self._security.setup_2fa(user_id)

            # Store pending setup
            self._pending_2fa[user_id] = {
                "secret": setup_info["secret"],
                "backup_codes": setup_info["backup_codes"],
            }

            text = (
                "🔐 *Настройка 2FA*\n\n"
                "1️⃣ Отсканируйте QR-код в Google Authenticator\n"
                "   или другом приложении\n\n"
                "2️⃣ Введите код из приложения для подтверждения\n\n"
                f"*Secret (ручной ввод):*\n`{setup_info['secret']}`\n\n"
                "_Сохраните secret в надёжном месте!_"
            )

            # In real app, would generate and send QR code image
            keyboard = [
                [InlineKeyboardButton("✅ Ввести код", callback_data="auth:2fa:verify_prompt")],
                [InlineKeyboardButton("❌ Отмена", callback_data="auth:2fa:menu")],
            ]

            await query.edit_message_text(
                text,
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode="Markdown",
            )

        elif action == "verify_prompt":
            await query.edit_message_text(
                "🔢 *Введите код*\n\n"
                "Отправьте 6-значный код из приложения аутентификации.\n\n"
                "Формат: просто цифры (например: 123456)",
                parse_mode="Markdown",
            )
            # Store state for message handler
            context.user_data["awaiting_2fa_code"] = True

        elif action == "show_backup":
            config = self._security._2fa_configs.get(user_id)
            if config:
                codes = config.backup_codes[:5]  # Show first 5
                codes_text = "\n".join(f"• `{code}`" for code in codes)
                remaining = len(config.backup_codes)

                text = (
                    f"🔑 *Backup коды*\n\n"
                    f"Осталось: {remaining} кодов\n\n"
                    f"{codes_text}\n\n"
                    f"_Каждый код можно использовать только один раз._"
                )
            else:
                text = "❌ 2FA не настроена"

            await query.edit_message_text(
                text,
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("◀️ Назад", callback_data="auth:2fa:menu")]
                ]),
                parse_mode="Markdown",
            )

    async def _handle_ip_whitelist(
        self,
        query: Any,
        user_id: int,
        action: str,
    ) -> None:
        """Handle IP whitelist actions."""
        if action == "menu":
            whitelist = self._security.get_ip_whitelist(user_id)

            text = "🌐 *IP Whitelist*\n\n"

            if not whitelist:
                text += (
                    "_Whitelist не настроен._\n\n"
                    "Все IP адреса разрешены.\n"
                    "Добавьте IP для ограничения доступа."
                )
            else:
                for entry in whitelist[:5]:
                    status = "✅" if entry.is_active and not entry.is_expired() else "❌"
                    text += f"{status} `{entry.ip_address}`\n"
                    if entry.description:
                        text += f"   _{entry.description}_\n"

            keyboard = [
                [
                    InlineKeyboardButton(
                        "➕ Добавить текущий IP", callback_data="auth:ip:add_current"
                    )
                ],
                [InlineKeyboardButton("◀️ Назад", callback_data="auth:back")],
            ]

            await query.edit_message_text(
                text,
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode="Markdown",
            )

        elif action == "add_current":
            # In real app, would get actual IP from update
            demo_ip = "192.168.1.100"

            self._security.add_ip_whitelist(
                user_id=user_id,
                ip_address=demo_ip,
                description="Добавлено через бота",
            )

            await query.edit_message_text(
                f"✅ IP `{demo_ip}` добавлен в whitelist",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("◀️ Назад", callback_data="auth:ip:menu")]
                ]),
                parse_mode="Markdown",
            )

    async def _handle_api_keys(
        self,
        query: Any,
        user_id: int,
        action: str,
    ) -> None:
        """Handle API key actions."""
        if action == "menu":
            keys = self._api_keys.get(user_id, [])

            text = "🔑 *API ключи*\n\n"

            if not keys:
                text += "_Нет созданных ключей._\n\nAPI ключи позволяют интегрировать бота с другими сервисами."
            else:
                for key in keys[:5]:
                    text += f"• `{key['name']}`\n"
                    text += f"  Создан: {key['created_at']}\n"

            keyboard = [
                [InlineKeyboardButton("➕ Создать ключ", callback_data="auth:api:create")],
                [InlineKeyboardButton("◀️ Назад", callback_data="auth:back")],
            ]

            await query.edit_message_text(
                text,
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode="Markdown",
            )

        elif action == "create":
            # Create new API key
            token_pair = self._jwt_auth.create_token_pair(user_id=user_id)

            # Store key info
            if user_id not in self._api_keys:
                self._api_keys[user_id] = []

            self._api_keys[user_id].append({
                "name": f"api_key_{len(self._api_keys[user_id]) + 1}",
                "created_at": datetime.now(UTC).strftime("%Y-%m-%d"),
            })

            text = (
                "✅ *API ключ создан*\n\n"
                f"*Access Token:*\n`{token_pair.access_token[:50]}...`\n\n"
                f"*Refresh Token:*\n`{token_pair.refresh_token[:50]}...`\n\n"
                f"⚠️ _Сохраните токены! Они показываются только один раз._"
            )

            await query.edit_message_text(
                text,
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("◀️ Назад", callback_data="auth:api:menu")]
                ]),
                parse_mode="Markdown",
            )

    async def _handle_tokens(
        self,
        query: Any,
        user_id: int,
        action: str,
    ) -> None:
        """Handle token operations."""
        if action == "generate":
            # Generate new access token
            token = self._jwt_auth.create_token(
                user_id=user_id,
                token_type=TokenType.ACCESS,
            )

            text = f"🎫 *Новый Access Token*\n\n`{token}`\n\n_Действителен 15 минут._"

            await query.edit_message_text(
                text,
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("◀️ Назад", callback_data="auth:back")]
                ]),
                parse_mode="Markdown",
            )

    async def verify_2fa_code(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
    ) -> bool:
        """Verify 2FA code from user message.

        Called when user sends a code during 2FA setup.

        Returns:
            True if code was valid and 2FA enabled
        """
        if not update.message or not update.effective_user:
            return False

        user_id = update.effective_user.id
        code = update.message.text.strip()

        # Check if we're awaiting a code
        if not context.user_data.get("awaiting_2fa_code"):
            return False

        # Clear awaiting flag
        context.user_data["awaiting_2fa_code"] = False

        # Verify code
        if self._security.enable_2fa(user_id, code):
            pending = self._pending_2fa.pop(user_id, {})
            backup_codes = pending.get("backup_codes", [])

            codes_text = "\n".join(f"• `{c}`" for c in backup_codes[:5])

            await update.message.reply_text(
                f"✅ *2FA успешно включена!*\n\n"
                f"*Backup коды (сохраните их!):*\n{codes_text}\n\n"
                f"_Эти коды можно использовать если потеряете доступ к приложению._",
                parse_mode="Markdown",
            )
            return True
        await update.message.reply_text(
            "❌ Неверный код. Попробуйте ещё раз.\n\nИспользуйте /2fa для новой попытки.",
        )
        return False

    def _create_auth_keyboard(
        self,
        is_2fa_enabled: bool,
    ) -> list[list[InlineKeyboardButton]]:
        """Create main auth keyboard."""
        return [
            [
                InlineKeyboardButton(
                    "🔐 2FA" + (" ✅" if is_2fa_enabled else ""),
                    callback_data="auth:2fa:menu",
                ),
                InlineKeyboardButton("🌐 IP Whitelist", callback_data="auth:ip:menu"),
            ],
            [
                InlineKeyboardButton("🔑 API ключи", callback_data="auth:api:menu"),
                InlineKeyboardButton("🎫 Токен", callback_data="auth:token:generate"),
            ],
            [
                InlineKeyboardButton("◀️ Главное меню", callback_data="main_menu"),
            ],
        ]

    def get_handlers(self) -> list:
        """Get list of handlers for registration."""
        return [
            CommandHandler("auth", self.handle_auth_command),
            CommandHandler("2fa", self.handle_2fa_command),
            CommandHandler("security", self.handle_security_command),
            CallbackQueryHandler(
                self.handle_callback,
                pattern=r"^auth:",
            ),
        ]


__all__ = ["AuthHandler"]
