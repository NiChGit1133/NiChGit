"""Base agent class with LLM call helpers and structured output parsing."""
import json
import logging
from typing import TypeVar, Type
from pydantic import BaseModel
from langchain_deepseek import ChatDeepSeek
from ..config import (
    DEEPSEEK_API_KEY, DEEPSEEK_BASE_URL, DEFAULT_MODEL,
    ANALYST_TEMPERATURE, RED_TEAM_TEMPERATURE, CHIEF_TEMPERATURE
)

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)

# Model instances (reused across agents)
_models: dict[str, ChatDeepSeek] = {}


def get_model(temperature: float = 0.7) -> ChatDeepSeek:
    """Get or create a ChatDeepSeek instance with the given temperature."""
    key = f"{DEFAULT_MODEL}_{temperature}"
    if key not in _models:
        _models[key] = ChatDeepSeek(
            model="deepseek-chat",
            api_key=DEEPSEEK_API_KEY,
            api_base=DEEPSEEK_BASE_URL,
            temperature=temperature,
            max_tokens=4096,
            timeout=120,
        )
    return _models[key]


def get_analyst_model() -> ChatDeepSeek:
    """Model for standard analyst agents."""
    return get_model(ANALYST_TEMPERATURE)


def get_red_team_model() -> ChatDeepSeek:
    """Model for red team (higher temperature for more creative skepticism)."""
    return get_model(RED_TEAM_TEMPERATURE)


def get_chief_model() -> ChatDeepSeek:
    """Model for chief strategist (lower temperature for consistent judgment)."""
    return get_model(CHIEF_TEMPERATURE)


class AgentBase:
    """Base class for all analyst agents. Model is lazily initialized."""

    def __init__(self, name: str, system_prompt: str, temperature: float = ANALYST_TEMPERATURE):
        self.name = name
        self.system_prompt = system_prompt
        self.temperature = temperature
        self._model = None  # Lazy init

    @property
    def model(self):
        if self._model is None:
            self._model = get_model(self.temperature)
        return self._model

    def _format_data_context(self, state: dict) -> str:
        """Format the available data for the LLM prompt."""
        parts = [f"## 股票信息\n代码: {state.get('stock_code', 'N/A')}\n名称: {state.get('stock_name', 'N/A')}\n"]

        # Quote
        quote = state.get("market_data", {})
        if quote:
            parts.append(f"""## 实时行情
- 最新价: ¥{quote.get('price', 'N/A')}
- 涨跌幅: {quote.get('change_pct', 'N/A'):+.2f}%
- 涨跌额: {quote.get('change_amount', 'N/A')}
- 今开: ¥{quote.get('open', 'N/A')}
- 最高: ¥{quote.get('high', 'N/A')}
- 最低: ¥{quote.get('low', 'N/A')}
- 成交量: {quote.get('volume', 'N/A')}
- 成交额: {quote.get('amount', 'N/A')}
- 换手率: {quote.get('turnover', 'N/A')}%
- 市盈率: {quote.get('pe', 'N/A')}
- 市净率: {quote.get('pb', 'N/A')}
- 总市值: {quote.get('total_mv', 'N/A')}
""")

        # K-line data summary
        kline = state.get("market_data", {})
        if kline and "close" in kline:
            closes = kline["close"]
            ma5 = kline.get("ma5", [])
            ma20 = kline.get("ma20", [])
            dif = kline.get("dif", [])
            dea = kline.get("dea", [])
            macd_vals = kline.get("macd", [])
            rsi = kline.get("rsi14", [])
            atr = kline.get("atr14", [])

            valid_close = [c for c in closes if c and c == c]
            valid_rsi = [r for r in rsi if r and r == r]
            valid_macd = [m for m in macd_vals if m and m == m]
            valid_atr = [a for a in atr if a and a == a]

            parts.append(f"""## 日K线数据 ({kline.get('data_points', 0)}个交易日)
### 最近5日收盘价: {valid_close[-5:] if len(valid_close) >= 5 else valid_close}

### 最近指标值:
""")

            if valid_close:
                parts.append(f"- 最新收盘价: ¥{valid_close[-1]:.2f}")
            if ma5 and len(ma5) > 0 and ma5[-1] == ma5[-1]:
                parts.append(f"- MA5: {ma5[-1]:.2f}")
            if ma20 and len(ma20) > 0 and ma20[-1] == ma20[-1]:
                parts.append(f"- MA20: {ma20[-1]:.2f}")
            if dif and len(dif) > 0 and dif[-1] == dif[-1]:
                parts.append(f"- MACD DIF: {dif[-1]:.4f}")
            if dea and len(dea) > 0 and dea[-1] == dea[-1]:
                parts.append(f"- MACD DEA: {dea[-1]:.4f}")
            if valid_macd:
                parts.append(f"- MACD柱: {valid_macd[-1]:.4f}")
            if valid_rsi:
                parts.append(f"- RSI(14): {valid_rsi[-1]:.1f}")
            if valid_atr:
                parts.append(f"- ATR(14): {valid_atr[-1]:.2f}")

            # Recent trend
            if len(valid_close) >= 20:
                chg_5 = (valid_close[-1] / valid_close[-6] - 1) * 100 if len(valid_close) >= 6 else 0
                chg_20 = (valid_close[-1] / valid_close[-21] - 1) * 100 if len(valid_close) >= 21 else 0
                parts.append(f"\n- 近5日涨跌: {chg_5:+.2f}%")
                parts.append(f"- 近20日涨跌: {chg_20:+.2f}%")

        # Financial data
        fin = state.get("financial_data", {})
        if fin:
            parts.append(f"\n## 财务数据\n```json\n{json.dumps(fin, ensure_ascii=False, indent=2, default=str)}\n```")

        # News
        news = state.get("news_data", [])
        if news:
            parts.append(f"\n## 近期新闻 ({len(news)}条)")
            for i, n in enumerate(news[:10]):
                parts.append(f"{i+1}. [{n.get('time', '?')}] {n.get('title', '')}")

        # Fund flows
        ff = state.get("sentiment_data", {})
        if ff:
            parts.append(f"\n## 资金流向数据\n```json\n{json.dumps(ff, ensure_ascii=False, indent=2, default=str)}\n```")

        return "\n".join(parts)

    def _parse_json_response(self, text: str) -> dict:
        """Extract JSON from LLM response, handling various formats."""
        # Try direct parse
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass

        # Try to find JSON block in markdown
        import re
        json_match = re.search(r'```(?:json)?\s*\n?(.*?)\n?```', text, re.DOTALL)
        if json_match:
            try:
                return json.loads(json_match.group(1))
            except json.JSONDecodeError:
                pass

        # Try to find JSON object
        json_match = re.search(r'\{(?:[^{}]|(?:\{[^{}]*\}))*\}', text, re.DOTALL)
        if json_match:
            try:
                return json.loads(json_match.group(0))
            except json.JSONDecodeError:
                pass

        logger.error(f"Failed to parse JSON from response: {text[:200]}...")
        return {"error": "JSON parse failed", "raw_text": text}

    async def invoke(self, state: dict, output_schema: Type[T] | None = None) -> dict:
        """Call the LLM with the state data and return parsed response."""
        from langchain_core.messages import SystemMessage, HumanMessage

        data_context = self._format_data_context(state)

        messages = [
            SystemMessage(content=self.system_prompt),
            HumanMessage(content=f"请基于以下数据进行分析并输出JSON格式结果:\n\n{data_context}"),
        ]

        logger.info(f"[{self.name}] Invoking LLM ({self.temperature} temp)...")
        response = await self.model.ainvoke(messages)

        content = response.content if hasattr(response, "content") else str(response)
        logger.info(f"[{self.name}] Response length: {len(content)} chars")

        parsed = self._parse_json_response(content)

        if output_schema and "error" not in parsed:
            try:
                return output_schema(**parsed).model_dump()
            except Exception as e:
                logger.warning(f"[{self.name}] Schema validation failed: {e}")
                # Return partial result
                parsed["_validation_error"] = str(e)
                return parsed

        return parsed
