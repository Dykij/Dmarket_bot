"""Anthropic Prompt Engineering Integration for DMarket Bot.

This module implements advanced prompt engineering techniques from Anthropic's
interactive tutorial to enhance bot intelligence and user experience:

1. XML-tagged prompt structure (separating data from instructions)
2. Role-based prompting for different contexts
3. Chain-of-thought reasoning for complex decisions
4. Few-shot examples for consistent outputs
5. Hallucination prevention with source citations
6. Pre-filled responses for structured JSON
7. Clear and direct instructions
8. Output formatting control
9. Complex prompt chaining

Based on: https://github.com/anthropics/prompt-eng-interactive-tutorial

Created: January 13, 2026
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from enum import StrEnum
from typing import TYPE_CHECKING, Any

import structlog

if TYPE_CHECKING:
    from src.dmarket.integrated_arbitrage_scanner import ArbitrageOpportunity

logger = structlog.get_logger(__name__)


# ============================================================================
# Role Definitions
# ============================================================================


class BotRole(StrEnum):
    """Available bot roles for different contexts."""

    TRADING_ADVISOR = "trading_advisor"
    MARKET_ANALYST = "market_analyst"
    RISK_MANAGER = "risk_manager"
    EDUCATOR = "educator"
    ASSISTANT = "assistant"


ROLE_PROMPTS = {
    BotRole.TRADING_ADVISOR: """You are an experienced cryptocurrency and CS:GO skin trading advisor with 10+ years of market experience. You provide clear, actionable trading recommendations based on data analysis. You always consider risk, timing, and user's capital constraints.""",
    BotRole.MARKET_ANALYST: """You are a quantitative market data analyst specializing in gaming item marketplaces. You analyze price trends, volume patterns, and cross-platform arbitrage opportunities. Your analysis is data-driven and statistical.""",
    BotRole.RISK_MANAGER: """You are a conservative risk management expert in trading. You identify potential risks, liquidity concerns, and market timing issues. You help users avoid losses and protect their capital.""",
    BotRole.EDUCATOR: """You are a patient, knowledgeable trading educator. You explain complex trading concepts in simple terms, using analogies and examples. You adjust explanations based on user's experience level.""",
    BotRole.ASSISTANT: """You are a helpful trading assistant for DMarket bot users. You answer questions, explain features, and guide users through the platform.""",
}


# ============================================================================
# User Experience Levels
# ============================================================================


class UserLevel(StrEnum):
    """User experience levels for personalized responses."""

    BEGINNER = "beginner"
    INTERMEDIATE = "intermediate"
    ADVANCED = "advanced"
    EXPERT = "expert"


# ============================================================================
# Prompt Templates with XML Structure
# ============================================================================


@dataclass
class PromptContext:
    """Context information for prompt generation."""

    role: BotRole
    user_level: UserLevel
    user_id: int | None = None
    capital_available: Decimal | None = None
    risk_tolerance: str = "medium"


class PromptEngineer:
    """AI-powered prompt engineering for enhanced bot responses.

    Implements techniques from Anthropic's prompt engineering tutorial:
    - XML-tagged structured prompts
    - Role-based prompting
    - Chain-of-thought reasoning
    - Few-shot examples
    - Hallucination prevention
    - Pre-filled responses
    """

    def __init__(
        self,
        api_key: str | None = None,
        model: str = "claude-3-5-sonnet-20241022",
        max_tokens: int = 1024,
        temperature: float = 0.7,
    ):
        """Initialize prompt engineer.

        Args:
            api_key: Anthropic API key (optional, can use env var)
            model: Claude model to use
            max_tokens: Maximum tokens in response
            temperature: Response randomness (0-1)
        """
        self.api_key = api_key
        self.model = model
        self.max_tokens = max_tokens
        self.temperature = temperature
        self.client = None  # Lazy initialization

        logger.info(
            "prompt_engineer_initialized",
            model=model,
            max_tokens=max_tokens,
            temperature=temperature,
        )

    def _ensure_client(self) -> None:
        """Lazy initialization of Anthropic client."""
        if self.client is None:
            try:
                from anthropic import AsyncAnthropic

                self.client = AsyncAnthropic(api_key=self.api_key)
                logger.info("anthropic_client_initialized")
            except ImportError:
                logger.warning(
                    "anthropic_not_installed",
                    message="Install with: pip install anthropic",
                )
                raise ImportError("anthropic package not installed")

    # ========================================================================
    # Technique 1: XML-Tagged Prompt Structure
    # ========================================================================

    def _build_xml_prompt(
        self,
        context: PromptContext,
        data: dict[str, Any],
        instructions: str,
        examples: list[dict[str, str]] | None = None,
    ) -> str:
        """Build structured prompt with XML tags.

        This technique (Chapter 4) separates context, data, and instructions
        for better Claude comprehension.

        Args:
            context: User and role context
            data: Input data
            instructions: Task instructions
            examples: Optional few-shot examples

        Returns:
            XML-structured prompt
        """
        prompt_parts = []

        # Role assignment (Chapter 3)
        prompt_parts.append(ROLE_PROMPTS[context.role])
        prompt_parts.append("")

        # Context section
        prompt_parts.append("<context>")
        prompt_parts.append(f"<user_level>{context.user_level}</user_level>")
        if context.capital_available:
            prompt_parts.append(
                f"<capital_available>{float(context.capital_available)}</capital_available>"
            )
        prompt_parts.append(
            f"<risk_tolerance>{context.risk_tolerance}</risk_tolerance>"
        )
        prompt_parts.append("</context>")
        prompt_parts.append("")

        # Data section
        prompt_parts.append("<data>")
        for key, value in data.items():
            prompt_parts.append(f"<{key}>{value}</{key}>")
        prompt_parts.extend(("</data>", ""))

        # Examples (Chapter 7: Few-shot prompting)
        if examples:
            prompt_parts.append("<examples>")
            for i, example in enumerate(examples, 1):
                prompt_parts.append(f"<example_{i}>")
                prompt_parts.append(f"<input>{example['input']}</input>")
                prompt_parts.append(f"<output>{example['output']}</output>")
                prompt_parts.append(f"</example_{i}>")
            prompt_parts.extend(("</examples>", ""))

        # Instructions
        prompt_parts.extend(("<instructions>", instructions, "</instructions>"))

        return "\n".join(prompt_parts)

    # ========================================================================
    # Technique 2 & 6: Chain-of-Thought Reasoning
    # ========================================================================

    async def analyze_arbitrage_with_reasoning(
        self, opportunity: ArbitrageOpportunity, context: PromptContext
    ) -> str:
        """Analyze arbitrage with transparent chain-of-thought reasoning.

        Uses Chapter 6 technique: Precognition (thinking step by step).

        Args:
            opportunity: Arbitrage opportunity to analyze
            context: User context

        Returns:
            Analysis with visible reasoning steps
        """
        data = {
            "item_name": opportunity.item_name,
            "buy_platform": opportunity.buy_platform,
            "buy_price": f"${float(opportunity.buy_price):.2f}",
            "sell_platform": opportunity.sell_platform,
            "sell_price": f"${float(opportunity.sell_price):.2f}",
            "profit": f"${float(opportunity.profit_usd):.2f}",
            "roi": f"{float(opportunity.profit_percent):.1f}%",
            "liquidity_score": f"{opportunity.liquidity_score}/3",
            "timestamp": datetime.now(UTC).isoformat(),
        }

        instructions = """Analyze this arbitrage opportunity using step-by-step reasoning:

<thinking>
Step 1: Assess liquidity - Is the item available on multiple platforms? What does this mean for risk?
Step 2: Calculate net profit - After all commissions, what's the real profit?
Step 3: Evaluate timing - When should the user execute this trade?
Step 4: Identify risks - What could go wrong? Price volatility, market timing, etc.
Step 5: Provide recommendation - Should the user take this trade? Why or why not?
</thinking>

After your analysis, provide a clear recommendation with:
- Risk level (Low/Medium/High)
- Action (Buy Now / Wait / Skip)
- Reasoning (2-3 sentences)

IMPORTANT: Only use the data provided. Do not invent prices or make up information.
"""

        prompt = self._build_xml_prompt(context, data, instructions)

        try:
            self._ensure_client()
            response = await self.client.messages.create(
                model=self.model,
                max_tokens=self.max_tokens,
                temperature=self.temperature,
                messages=[{"role": "user", "content": prompt}],
            )

            return response.content[0].text

        except Exception as e:
            logger.error("analysis_failed", error=str(e))
            # Fallback to rule-based analysis
            return self._fallback_analysis(opportunity)

    # ========================================================================
    # Technique 7: Few-Shot Examples for Consistent Outputs
    # ========================================================================

    FEW_SHOT_EXAMPLES = {
        "explain_arbitrage": [
            {
                "input": "AK-47 | Redline (FT), Buy $8.50, Sell $11.20, Profit $2.03 (23.9%)",
                "output": "🎯 Great find! The AK-47 | Redline is currently underpriced on DMarket at $8.50. After buying and selling on Waxpeer at $11.20 (minus 6% commission = $10.53), you'd profit $2.03, which is a solid 23.9% return. This is a low-risk opportunity since the Redline is a popular skin with good liquidity.",
            },
            {
                "input": "M4A4 | Howl (MW), Buy $1,250, Sell $1,350, Profit $26.90 (2.2%)",
                "output": "⚠️ Proceed with caution. While there's a $26.90 profit opportunity with the M4A4 | Howl, the ROI is only 2.2%. For a high-value item like this, consider: (1) Howls have low liquidity - they may take days to sell, (2) Small price fluctuations could erase your profit, (3) You're tying up $1,250 in capital. Unless you have significant capital and patience, this might not be optimal.",
            },
        ],
        "strategy_recommendation": [
            {
                "input": "Capital $100, Risk Medium, Experience Beginner",
                "output": "📚 For a $100 budget, I recommend starting with the DMarket-only strategy. Focus on items in the $5-15 range with 10-15% ROI. This gives you: (1) Quick trades (30 min - 2 hours), (2) Lower risk than cross-platform, (3) Opportunity to learn without long holds. Aim for 3-5 small wins to build confidence before trying holds.",
            }
        ],
    }

    async def explain_arbitrage(
        self,
        opportunity: ArbitrageOpportunity,
        context: PromptContext,
        include_reasoning: bool = False,
    ) -> str:
        """Explain arbitrage opportunity with consistent format.

        Uses few-shot prompting (Chapter 7) for quality and consistency.

        Args:
            opportunity: Arbitrage to explain
            context: User context
            include_reasoning: Include chain-of-thought analysis

        Returns:
            User-friendly explanation
        """
        if include_reasoning:
            return await self.analyze_arbitrage_with_reasoning(opportunity, context)

        data = {
            "item_name": opportunity.item_name,
            "buy_platform": opportunity.buy_platform,
            "buy_price": f"${float(opportunity.buy_price):.2f}",
            "sell_platform": opportunity.sell_platform,
            "sell_price": f"${float(opportunity.sell_price):.2f}",
            "profit": f"${float(opportunity.profit_usd):.2f}",
            "roi": f"{float(opportunity.profit_percent):.1f}%",
            "liquidity": f"{opportunity.liquidity_score}/3",
        }

        instructions = """Explain this arbitrage opportunity in a friendly, clear way.

Match the style and structure of the examples provided.
- Use emojis sparingly (1-2 max)
- Keep it concise (2-4 sentences)
- Mention key factors: profit, risk, liquidity
- Adjust complexity based on user_level
- End with clear recommendation (Good opportunity / Proceed with caution / Skip)

IMPORTANT: Only use the provided data. Do not make up prices or information."""

        prompt = self._build_xml_prompt(
            context,
            data,
            instructions,
            examples=self.FEW_SHOT_EXAMPLES["explain_arbitrage"],
        )

        try:
            self._ensure_client()
            response = await self.client.messages.create(
                model=self.model,
                max_tokens=self.max_tokens,
                temperature=self.temperature,
                messages=[{"role": "user", "content": prompt}],
            )

            return response.content[0].text

        except Exception as e:
            logger.error("explanation_failed", error=str(e))
            return self._fallback_explanation(opportunity)

    # ========================================================================
    # Technique 8: Hallucination Prevention
    # ========================================================================

    async def generate_market_insights(
        self, opportunities: list[ArbitrageOpportunity], context: PromptContext
    ) -> str:
        """Generate market insights with hallucination prevention.

        Uses Chapter 8 techniques to ensure factual accuracy.

        Args:
            opportunities: List of opportunities
            context: User context

        Returns:
            Market insights with source citations
        """
        # Prepare verified data
        total_opportunities = len(opportunities)
        avg_roi = (
            sum(o.profit_percent for o in opportunities) / total_opportunities
            if total_opportunities > 0
            else Decimal(0)
        )

        liquid_count = sum(1 for o in opportunities if o.liquidity_score >= 2)

        platform_distribution = {}
        for opp in opportunities:
            key = f"{opp.buy_platform} → {opp.sell_platform}"
            platform_distribution[key] = platform_distribution.get(key, 0) + 1

        data = {
            "total_opportunities": str(total_opportunities),
            "average_roi": f"{float(avg_roi):.1f}%",
            "liquid_opportunities": str(liquid_count),
            "timestamp": datetime.now(UTC).isoformat(),
            "platform_distribution": str(platform_distribution),
        }

        instructions = """Generate concise market insights based on the provided data.

CRITICAL RULES to prevent hallucinations:
1. ONLY use the data provided in the <data> section
2. If asked about information not provided, say "I don't have that data"
3. Do NOT invent trends, prices, or statistics
4. Cite your sources: "Based on X opportunities analyzed..."
5. Do NOT predict future prices - only describe current state

Format:
📊 Market Snapshot

[2-3 key observations from the data]

[1 actionable insight for the user]

📖 Source: [describe the data used]
🕐 Updated: [timestamp]
"""

        prompt = self._build_xml_prompt(context, data, instructions)

        try:
            self._ensure_client()
            response = await self.client.messages.create(
                model=self.model,
                max_tokens=self.max_tokens,
                temperature=0.3,  # Lower temperature for factual content
                messages=[{"role": "user", "content": prompt}],
            )

            return response.content[0].text

        except Exception as e:
            logger.error("insights_generation_failed", error=str(e))
            return self._fallback_insights(opportunities)

    # ========================================================================
    # Technique 5 & 9: Pre-filled Responses for Structured Output
    # ========================================================================

    async def generate_structured_recommendation(
        self, opportunity: ArbitrageOpportunity, context: PromptContext
    ) -> dict[str, Any]:
        """Generate structured JSON recommendation.

        Uses Chapter 5 technique: pre-filling assistant output.

        Args:
            opportunity: Opportunity to analyze
            context: User context

        Returns:
            Structured recommendation dict
        """
        data = {
            "item_name": opportunity.item_name,
            "profit_percent": f"{float(opportunity.profit_percent):.1f}",
            "liquidity_score": str(opportunity.liquidity_score),
            "buy_price": f"{float(opportunity.buy_price):.2f}",
            "sell_price": f"{float(opportunity.sell_price):.2f}",
        }

        instructions = """Generate a structured recommendation in JSON format with these fields:
- action: "buy" | "hold" | "skip"
- confidence: "low" | "medium" | "high"
- risk_level: "low" | "medium" | "high"
- reasoning: brief explanation (1-2 sentences)
- estimated_time: "minutes" | "hours" | "days"

Base your recommendation on:
- Liquidity score (2+ = safer)
- ROI (15%+ = good, 5-15% = okay, <5% = skip)
- User's risk tolerance"""

        prompt = self._build_xml_prompt(context, data, instructions)

        # Pre-fill to ensure JSON format
        prefill = '{"action": "'

        try:
            self._ensure_client()
            response = await self.client.messages.create(
                model=self.model,
                max_tokens=self.max_tokens,
                temperature=0.5,
                messages=[
                    {"role": "user", "content": prompt},
                    {"role": "assistant", "content": prefill},
                ],
            )

            # Extract and parse JSON
            import json

            json_text = prefill + response.content[0].text
            return json.loads(json_text)

        except Exception as e:
            logger.error("structured_recommendation_failed", error=str(e))
            return self._fallback_recommendation(opportunity)

    # ========================================================================
    # Fallback Methods (when AI unavailable)
    # ========================================================================

    def _fallback_explanation(self, opp: ArbitrageOpportunity) -> str:
        """Rule-based explanation fallback."""
        if opp.profit_percent >= 20:
            emoji = "🎯"
            rating = "excellent"
        elif opp.profit_percent >= 10:
            emoji = "✅"
            rating = "good"
        else:
            emoji = "⚠️"
            rating = "moderate"

        return f"""{emoji} {opp.item_name}

Buy on {opp.buy_platform}: ${float(opp.buy_price):.2f}
Sell on {opp.sell_platform}: ${float(opp.sell_price):.2f}
Profit: ${float(opp.profit_usd):.2f} ({float(opp.profit_percent):.1f}%)
Liquidity: {opp.liquidity_score}/3

This is a {rating} opportunity with {'low' if opp.liquidity_score >= 2 else 'medium'} risk."""

    def _fallback_analysis(self, opp: ArbitrageOpportunity) -> str:
        """Rule-based analysis fallback."""
        risk = (
            "Low" if opp.liquidity_score >= 2 and opp.profit_percent >= 10 else "Medium"
        )
        action = "Buy Now" if opp.profit_percent >= 15 else "Evaluate"

        return f"""Analysis of {opp.item_name}:

Risk Level: {risk}
Recommended Action: {action}

Reasoning: ROI of {float(opp.profit_percent):.1f}% with liquidity score {opp.liquidity_score}/3.
{"Good opportunity for quick profit." if opp.profit_percent >= 15 else "Moderate opportunity - consider your capital allocation."}"""

    def _fallback_insights(self, opportunities: list[ArbitrageOpportunity]) -> str:
        """Rule-based insights fallback."""
        total = len(opportunities)
        liquid = sum(1 for o in opportunities if o.liquidity_score >= 2)
        avg_roi = (
            sum(o.profit_percent for o in opportunities) / total
            if total > 0
            else Decimal(0)
        )

        return f"""📊 Market Snapshot

Found {total} arbitrage opportunities
Average ROI: {float(avg_roi):.1f}%
High liquidity items: {liquid}/{total}

Current market shows {'strong' if avg_roi >= 15 else 'moderate'} arbitrage opportunities.

📖 Source: {total} live opportunities analyzed
🕐 Updated: {datetime.now(UTC).strftime('%Y-%m-%d %H:%M UTC')}"""

    def _fallback_recommendation(self, opp: ArbitrageOpportunity) -> dict[str, Any]:
        """Rule-based recommendation fallback."""
        if opp.profit_percent >= 15 and opp.liquidity_score >= 2:
            action = "buy"
            confidence = "high"
            risk = "low"
        elif opp.profit_percent >= 10:
            action = "hold"
            confidence = "medium"
            risk = "medium"
        else:
            action = "skip"
            confidence = "low"
            risk = "high"

        return {
            "action": action,
            "confidence": confidence,
            "risk_level": risk,
            "reasoning": f"ROI {float(opp.profit_percent):.1f}% with {opp.liquidity_score}/3 liquidity",
            "estimated_time": "hours" if action == "buy" else "days",
        }


# ============================================================================
# Educational Content Generator
# ============================================================================


class EducationalContentGenerator:
    """Generate educational content for users learning to trade."""

    def __init__(self, prompt_engineer: PromptEngineer):
        """Initialize with prompt engineer instance."""
        self.prompt_engineer = prompt_engineer

    async def generate_lesson(self, topic: str, user_level: UserLevel) -> str:
        """Generate interactive lesson on trading topic.

        Args:
            topic: Topic to teach (e.g., "arbitrage", "liquidity", "risk")
            user_level: User's experience level

        Returns:
            Educational content
        """
        context = PromptContext(role=BotRole.EDUCATOR, user_level=user_level)

        data = {"topic": topic}

        instructions = f"""Create an interactive lesson on "{topic}" for {user_level} traders.

Structure:
📚 [Topic] 101

🎓 What is [Topic]?
[Clear definition with analogy]

💡 Example:
[Real-world example from CS:GO trading]

🤔 Why is this important?
[2-3 practical reasons]

✅ Quick Tip:
[One actionable tip they can use today]

📖 Next Steps: /learn [related_topic]"""

        prompt = self.prompt_engineer._build_xml_prompt(context, data, instructions)

        try:
            self.prompt_engineer._ensure_client()
            response = await self.prompt_engineer.client.messages.create(
                model=self.prompt_engineer.model,
                max_tokens=self.prompt_engineer.max_tokens,
                temperature=0.7,
                messages=[{"role": "user", "content": prompt}],
            )

            return response.content[0].text

        except Exception as e:
            logger.error("lesson_generation_failed", topic=topic, error=str(e))
            return f"📚 {topic.title()} 101\n\nLesson content temporarily unavailable. Try again later."


# ============================================================================
# Example Usage
# ============================================================================


async def example_usage():
    """Example of using PromptEngineer."""
    # Initialize
    engineer = PromptEngineer(api_key="your-api-key")

    # Create context
    context = PromptContext(
        role=BotRole.TRADING_ADVISOR,
        user_level=UserLevel.INTERMEDIATE,
        user_id=12345,
        capital_available=Decimal("500.00"),
        risk_tolerance="medium",
    )

    # Mock opportunity
    from src.dmarket.integrated_arbitrage_scanner import ArbitrageOpportunity

    opp = ArbitrageOpportunity(
        item_name="AK-47 | Redline (FT)",
        game="csgo",
        buy_price=Decimal("8.50"),
        sell_price=Decimal("11.20"),
        profit_usd=Decimal("2.03"),
        profit_percent=Decimal("23.9"),
        liquidity_score=3,
    )

    # Generate explanation
    explanation = await engineer.explain_arbitrage(opp, context)
    print(explanation)

    # Generate structured recommendation
    recommendation = await engineer.generate_structured_recommendation(opp, context)
    print(recommendation)


if __name__ == "__main__":
    asyncio.run(example_usage())
