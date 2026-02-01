"""NLP Command Handler for Telegram Bot.

Модуль обработки естественного языка для команд бота.
Распознает намерения пользователя (intents) и извлекает параметры
из естественных текстовых команд.

SKILL: Natural Language Processing
Category: Data & AI, Content & Media
Status: Phase 2 Implementation (Simplified)

Документация: src/telegram_bot/SKILL_NLP_HANDLER.md

Note: Это упрощенная версия без тяжелых ML библиотек (transformers, torch).
Использует pattern matching и regex для базового NLP.
Для production рекомендуется интеграция с transformers/spacy.
"""

from dataclasses import dataclass, field
import re
from typing import Any

import structlog


logger = structlog.get_logger(__name__)


@dataclass
class IntentResult:
    """Результат распознавания намерения.

    Attributes:
        intent: Тип намерения (scan_arbitrage, show_balance, etc.)
        params: Извлеченные параметры
        confidence: Уверенность распознавания (0.0-1.0)
        language: Детектированный язык
        alternatives: Альтернативные интерпретации
    """

    intent: str
    params: dict[str, Any] = field(default_factory=dict)
    confidence: float = 0.0
    language: str = "en"
    alternatives: list[dict[str, Any]] = field(default_factory=list)


class NLPCommandHandler:
    """Natural Language Processing для user commands.

    Распознает намерения и параметры из естественного языка.
    Поддерживает 4 языка: RU, EN, ES, DE.

    Example:
        >>> nlp = NLPCommandHandler()
        >>> result = await nlp.parse_user_intent("Найди арбитраж в CS:GO", user_id=123)
        >>> print(result.intent)  # "scan_arbitrage"
        >>> print(result.params)  # {"game": "csgo"}
    """

    # Паттерны для intent detection
    INTENT_PATTERNS = {
        "scan_arbitrage": {
            "ru": [
                r"найд.*арбитраж",
                r"покаж.*арбитраж",
                r"скан.*рынок",
                r"возможност",
            ],
            "en": [
                r"find.*arbitrage",
                r"show.*arbitrage",
                r"scan.*market",
                r"opportunit",
            ],
            "es": [r"buscar.*arbitraje", r"mostrar.*arbitraje"],
            "de": [r"finde.*arbitrage", r"zeige.*arbitrage"],
        },
        "show_balance": {
            "ru": [r"баланс", r"деньги", r"средства", r"сколько"],
            "en": [r"balance", r"money", r"funds", r"how much"],
            "es": [r"saldo", r"dinero", r"fondos"],
            "de": [r"guthaben", r"geld"],
        },
        "create_target": {
            "ru": [r"созда.*таргет", r"созда.*цель", r"добав.*таргет"],
            "en": [r"create.*target", r"add.*target", r"new.*target"],
            "es": [r"crear.*objetivo", r"añadir.*objetivo"],
            "de": [r"erstelle.*ziel", r"neue.*ziel"],
        },
        "list_targets": {
            "ru": [r"покаж.*таргет", r"список.*таргет", r"все.*таргет"],
            "en": [r"show.*target", r"list.*target", r"all.*target"],
            "es": [r"mostrar.*objetivo", r"lista.*objetivo"],
            "de": [r"zeige.*ziel", r"liste.*ziel"],
        },
        "delete_target": {
            "ru": [r"удал.*таргет", r"убер.*таргет"],
            "en": [r"delete.*target", r"remove.*target"],
            "es": [r"eliminar.*objetivo", r"borrar.*objetivo"],
            "de": [r"lösche.*ziel", r"entferne.*ziel"],
        },
        "show_stats": {
            "ru": [r"статистик", r"результат", r"как.*дел"],
            "en": [r"statistic", r"result", r"how.*doing"],
            "es": [r"estadística", r"resultado"],
            "de": [r"statistik", r"ergebnis"],
        },
        "help": {
            "ru": [r"помощ", r"справк", r"help"],
            "en": [r"help", r"assist"],
            "es": [r"ayuda"],
            "de": [r"hilfe"],
        },
    }

    # Паттерны для извлечения параметров
    PARAM_PATTERNS = {
        "game": {
            "pattern": r"(?:в|in|en)\s+(cs:?go|cs2|dota\s?2|tf2|rust)",
            "map": {
                "csgo": "csgo",
                "cs2": "csgo",
                "dota2": "dota2",
                "dota 2": "dota2",
                "tf2": "tf2",
                "rust": "rust",
            },
        },
        "price": {
            "pattern": r"(?:до|под|за|under|below|a|at|bei)\s*\$?(\d+(?:\.\d+)?)",
            "converter": float,
        },
        "item_name": {
            "pattern": r"(?:для|for|para|für)\s+([A-Za-z0-9\s\-|]+?)(?:\s+(?:за|at|a|bei)|$)",
            "converter": str.strip,
        },
    }

    def __init__(self):
        """Initialize NLP Command Handler."""
        logger.info("nlp_command_handler_initialized")

    async def parse_user_intent(
        self,
        text: str,
        user_id: int,
        context: dict[str, Any] | None = None,
    ) -> IntentResult:
        """Parse user intent from natural language text.

        Args:
            text: User's text message
            user_id: User ID (for context/personalization)
            context: Optional context from previous messages

        Returns:
            IntentResult with detected intent, params, confidence

        Example:
            >>> result = await nlp.parse_user_intent(
            ...     "Найди арбитраж в CS:GO до $10",
            ...     user_id=123
            ... )
            >>> print(result.intent)  # "scan_arbitrage"
            >>> print(result.params)  # {"game": "csgo", "max_price": 10.0}
        """
        text_lower = text.lower().strip()

        # Detect language
        language = self.detect_language(text_lower)

        logger.info(
            "parsing_intent",
            user_id=user_id,
            text_length=len(text),
            language=language,
        )

        # Find best matching intent
        intent, confidence = self._match_intent(text_lower, language)

        # Extract parameters
        params = self.extract_entities(text_lower, intent)

        # Apply context if available
        if context:
            params = {**context, **params}

        result = IntentResult(
            intent=intent,
            params=params,
            confidence=confidence,
            language=language,
            alternatives=[],
        )

        logger.info(
            "intent_parsed",
            intent=intent,
            confidence=confidence,
            params_count=len(params),
        )

        return result

    def detect_language(self, text: str) -> str:
        """Detect language of text.

        Uses simple character-based detection.

        Args:
            text: Input text

        Returns:
            Language code (ru, en, es, de)
        """
        # Cyrillic = Russian
        if re.search(r"[а-яА-ЯёЁ]", text):
            return "ru"

        # Spanish specific words
        if any(word in text for word in ["para", "crear", "mostrar", "buscar"]):
            return "es"

        # German specific words
        if any(word in text for word in ["für", "erstelle", "zeige", "finde"]):
            return "de"

        # Default to English
        return "en"

    def extract_entities(self, text: str, intent: str) -> dict[str, Any]:
        """Extract entities/parameters from text based on intent.

        Args:
            text: Input text
            intent: Detected intent

        Returns:
            Dictionary of extracted parameters
        """
        params = {}

        # Extract game
        game_match = re.search(
            self.PARAM_PATTERNS["game"]["pattern"], text, re.IGNORECASE
        )
        if game_match:
            game_raw = game_match.group(1).lower().replace(" ", "")
            params["game"] = self.PARAM_PATTERNS["game"]["map"].get(
                game_raw, "csgo"
            )

        # Extract price
        price_match = re.search(self.PARAM_PATTERNS["price"]["pattern"], text)
        if price_match:
            params["max_price"] = float(price_match.group(1))

        # Extract item name (for create_target)
        if intent == "create_target":
            item_match = re.search(
                self.PARAM_PATTERNS["item_name"]["pattern"], text, re.IGNORECASE
            )
            if item_match:
                params["item_name"] = item_match.group(1).strip()

            # Also look for price for target
            if "max_price" in params:
                params["price"] = params.pop("max_price")

        return params

    def _match_intent(self, text: str, language: str) -> tuple[str, float]:
        """Match text against intent patterns.

        Args:
            text: Lowercased text
            language: Detected language

        Returns:
            Tuple of (intent, confidence)
        """
        best_intent = "unknown"
        best_confidence = 0.0

        for intent, patterns_dict in self.INTENT_PATTERNS.items():
            patterns = patterns_dict.get(language, patterns_dict.get("en", []))

            for pattern in patterns:
                if re.search(pattern, text, re.IGNORECASE):
                    # Simple confidence based on pattern length
                    confidence = min(0.95, 0.6 + len(pattern) / 100)

                    if confidence > best_confidence:
                        best_intent = intent
                        best_confidence = confidence

        return best_intent, best_confidence


# Factory function
def create_nlp_handler() -> NLPCommandHandler:
    """Create NLP Command Handler.

    Returns:
        Initialized NLPCommandHandler

    Example:
        >>> nlp = create_nlp_handler()
        >>> result = await nlp.parse_user_intent("What's my balance?", 123)
    """
    return NLPCommandHandler()
