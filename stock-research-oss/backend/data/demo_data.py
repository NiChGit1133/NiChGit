"""Demo/mock data for when real financial data APIs are unavailable.

Provides realistic-looking data for 秦川机床(000837) and a few other stocks.
This allows the system to be demonstrated even without AkShare connectivity.
"""

import random
from datetime import datetime, timedelta

# ─── Demo Stock Database ─────────────────────────────────────────────

DEMO_STOCKS = {
    "000837": {
        "name": "秦川机床",
        "sector": "机械设备/工业母机",
        "concept": "人形机器人/丝杠/工业母机",
    },
    "300706": {
        "name": "麦捷科技",
        "sector": "电子",
        "concept": "5G/半导体",
    },
    "300750": {
        "name": "宁德时代",
        "sector": "电力设备",
        "concept": "锂电池/储能",
    },
    "600519": {
        "name": "贵州茅台",
        "sector": "食品饮料",
        "concept": "白酒/消费",
    },
    # US Stocks (primary market for this deployment)
    "AAPL": {
        "name": "Apple Inc.",
        "sector": "Technology",
        "concept": "Consumer Electronics/AI/iPhone",
    },
    "TSLA": {
        "name": "Tesla Inc.",
        "sector": "Automotive/Energy",
        "concept": "EV/Autonomous Driving/Robotics",
    },
    "NVDA": {
        "name": "NVIDIA Corp.",
        "sector": "Semiconductors",
        "concept": "AI/GPU/Data Center",
    },
    "MSFT": {
        "name": "Microsoft Corp.",
        "sector": "Technology",
        "concept": "Cloud/AI/Enterprise Software",
    },
    "GOOGL": {
        "name": "Alphabet Inc.",
        "sector": "Technology",
        "concept": "Search/AI/Cloud/Advertising",
    },
    "META": {
        "name": "Meta Platforms",
        "sector": "Technology",
        "concept": "Social Media/Metaverse/AI",
    },
    "AMZN": {
        "name": "Amazon.com Inc.",
        "sector": "E-commerce/Cloud",
        "concept": "E-commerce/AWS/AI",
    },
    "AMD": {
        "name": "Advanced Micro Devices",
        "sector": "Semiconductors",
        "concept": "CPU/GPU/AI Chips",
    },
}


def generate_demo_quote(code: str) -> dict | None:
    """Generate realistic demo quote data for a stock."""
    info = DEMO_STOCKS.get(code)
    if not info:
        return None

    # Deterministic-ish price based on code
    seed = sum(ord(c) for c in code)
    rng = random.Random(seed)
    base_price = 10 + rng.random() * 90

    # Add some randomness
    price = base_price * (1 + random.uniform(-0.03, 0.03))
    change_pct = random.uniform(-3.0, 3.0)
    pre_close = price / (1 + change_pct / 100)

    return {
        "code": code,
        "name": info["name"],
        "price": round(price, 2),
        "change_pct": round(change_pct, 2),
        "change_amount": round(price - pre_close, 2),
        "volume": int(base_price * 100000 * random.uniform(0.5, 2)),
        "amount": int(base_price * price * 100000 * random.uniform(0.5, 2)),
        "high": round(price * random.uniform(1.005, 1.03), 2),
        "low": round(price * random.uniform(0.97, 0.995), 2),
        "open": round(pre_close * random.uniform(0.99, 1.01), 2),
        "pre_close": round(pre_close, 2),
        "turnover": round(random.uniform(1.0, 5.0), 2),
        "pe": round(base_price * random.uniform(15, 250), 2),
        "pb": round(random.uniform(2.0, 8.0), 2),
        "total_mv": round(base_price * random.uniform(50, 500) * 10000, 2),
        "circ_mv": round(base_price * random.uniform(30, 300) * 10000, 2),
    }


def generate_demo_kline(code: str, days: int = 250) -> dict | None:
    """Generate realistic-looking K-line data."""
    info = DEMO_STOCKS.get(code)
    if not info:
        return None

    seed = sum(ord(c) for c in code)
    rng = random.Random(seed)
    base_price = 10 + rng.random() * 90

    dates = []
    opens, highs, lows, closes = [], [], [], []
    volumes, amounts = [], []

    price = base_price * 0.7  # Start lower
    current_date = datetime.now()

    for i in range(days):
        d = current_date - timedelta(days=days - 1 - i)
        dates.append(d.strftime("%Y-%m-%d"))

        daily_return = random.gauss(0.0005, 0.02)
        open_price = price * (1 + random.uniform(-0.005, 0.005))
        close_price = open_price * (1 + daily_return)
        high_price = max(open_price, close_price) * (1 + abs(random.gauss(0, 0.01)))
        low_price = min(open_price, close_price) * (1 - abs(random.gauss(0, 0.01)))
        vol = int(abs(random.gauss(1, 0.5)) * 5000000)

        opens.append(round(open_price, 2))
        highs.append(round(high_price, 2))
        lows.append(round(low_price, 2))
        closes.append(round(close_price, 2))
        volumes.append(vol)
        amounts.append(int(vol * close_price))

        price = close_price

    # Compute indicators (as numpy arrays)
    import numpy as np
    close_arr = np.array(closes, dtype=float)
    high_arr = np.array(highs, dtype=float)
    low_arr = np.array(lows, dtype=float)
    vol_arr = np.array(volumes, dtype=float)

    ma5 = _sma(close_arr, 5)
    ma10 = _sma(close_arr, 10)
    ma20 = _sma(close_arr, 20)
    ma60 = _sma(close_arr, 60)

    ema12 = np.array(_ema(close_arr, 12), dtype=float)
    ema26 = np.array(_ema(close_arr, 26), dtype=float)
    dif = (ema12 - ema26).tolist()
    dea = np.array(_ema(np.array(dif), 9), dtype=float).tolist()
    macd = (2 * (np.array(dif) - np.array(dea))).tolist()

    rsi14 = _rsi(close_arr, 14)
    vol_ma5 = _sma(vol_arr, 5)
    vol_ma20 = _sma(vol_arr, 20)
    tr_arr = _atr(high_arr, low_arr, close_arr, 14)

    return {
        "dates": dates,
        "open": opens,
        "high": highs,
        "low": lows,
        "close": closes,
        "volume": volumes,
        "amount": amounts,
        "ma5": ma5,
        "ma10": ma10,
        "ma20": ma20,
        "ma60": ma60,
        "dif": dif,
        "dea": dea,
        "macd": macd,
        "rsi14": rsi14,
        "vol_ma5": vol_ma5,
        "vol_ma20": vol_ma20,
        "atr14": tr_arr,
        "latest_close": closes[-1],
        "data_points": days,
    }


def generate_demo_financial(code: str) -> dict | None:
    """Generate demo financial statement data."""
    info = DEMO_STOCKS.get(code)
    if not info:
        return None

    # Data based on real-ish numbers for 秦川机床
    if code == "000837":
        return {
            "raw_data": [
                {"报告期": "2024-12-31", "营业总收入": 41.2, "净利润": 0.85, "基本每股收益": 0.09, "净资产收益率": 2.1},
                {"报告期": "2024-09-30", "营业总收入": 30.5, "净利润": 0.62, "基本每股收益": 0.07, "净资产收益率": 1.5},
                {"报告期": "2024-06-30", "营业总收入": 19.8, "净利润": 0.38, "基本每股收益": 0.04, "净资产收益率": 0.9},
                {"报告期": "2023-12-31", "营业总收入": 38.5, "净利润": 0.72, "基本每股收益": 0.08, "净资产收益率": 1.8},
                {"报告期": "2022-12-31", "营业总收入": 35.2, "净利润": 0.55, "基本每股收益": 0.06, "净资产收益率": 1.4},
            ],
            "data_points": 5,
            "latest": {
                "report_date": "2024-12-31",
                "revenue": 41.2,
                "net_profit": 0.85,
                "eps": 0.09,
                "roe": 2.1,
            },
            "key_metrics": {
                "毛利率": "14.92% → 19.19% (温和改善)",
                "扣非净利润": "连亏3年，2024年-0.32亿",
                "PE": 251,
                "PB": 3.8,
                "合同负债": "同比+37%（订单充足）",
                "CapEx": "同比下降12%（收缩中）",
                "资产负债率": "58.2%",
                "经营现金流": "1.2亿（正）",
            },
        }

    # Generic data for other stocks
    return {
        "raw_data": [
            {"报告期": "2024-12-31", "营业总收入": round(random.uniform(20, 100), 1), "净利润": round(random.uniform(2, 20), 1)},
            {"报告期": "2023-12-31", "营业总收入": round(random.uniform(18, 95), 1), "净利润": round(random.uniform(1.5, 18), 1)},
        ],
        "data_points": 2,
        "latest": {
            "report_date": "2024-12-31",
            "revenue": round(random.uniform(20, 100), 1),
            "net_profit": round(random.uniform(2, 20), 1),
            "eps": round(random.uniform(0.5, 5), 2),
            "roe": round(random.uniform(5, 25), 1),
        },
    }


def generate_demo_news(code: str, limit: int = 15) -> list[dict]:
    """Generate demo news articles."""
    info = DEMO_STOCKS.get(code, {"name": code, "concept": "TMT"})

    templates = [
        {
            "title": f"{info['name']}获{random.randint(3, 10)}家机构调研，重点关注{info.get('concept', '主营业务')}进展",
            "source": "证券时报",
        },
        {
            "title": f"工信部发布{info.get('concept', '智能制造')}产业支持政策，{info['name']}有望受益",
            "source": "财联社",
        },
        {
            "title": f"{info['name']}发布业绩预告：预计2024年营收同比增长{random.randint(5, 25)}%",
            "source": "公司公告",
        },
        {
            "title": f"券商研报：{info['name']}估值偏高但成长性可期，给予'增持'评级",
            "source": "中信证券",
        },
        {
            "title": f"{info.get('sector', '制造业')}赛道回暖，{info['name']}订单量创新高",
            "source": "东方财富",
        },
        {
            "title": f"外资连续{random.randint(3, 10)}日净买入{info['name']}，北向资金持仓占比提升",
            "source": "新浪财经",
        },
        {
            "title": f"机器人产业链爆发前夜，{info['name']}丝杠业务获市场关注",
            "source": "上证报",
        },
        {
            "title": f"{info['name']}：合同负债同比增长{random.randint(20, 50)}%，在手订单充裕",
            "source": "互动易",
        },
    ]

    rng = random.Random(sum(ord(c) for c in code))
    rng.shuffle(templates)

    news = []
    now = datetime.now()
    for i in range(min(limit, len(templates))):
        t = now - timedelta(hours=random.randint(1, 72))
        news.append({
            "title": templates[i]["title"],
            "time": t.strftime("%Y-%m-%d %H:%M"),
            "source": templates[i]["source"],
            "url": f"https://example.com/news/{i}",
        })

    return news


def generate_demo_fund_flows(code: str) -> dict | None:
    """Generate demo fund flow data."""
    rng = random.Random(sum(ord(c) for c in code))

    days = 20
    dates = []
    main_net = []
    main_pct = []
    super_large = []
    large_net = []
    medium_net = []
    small_net = []

    now = datetime.now()
    main_cum = 0.0
    for i in range(days):
        dates.append((now - timedelta(days=days - 1 - i)).strftime("%Y-%m-%d"))
        mn = round(random.uniform(-0.5, 0.5), 2)
        main_net.append(mn)
        main_pct.append(round(random.uniform(-5, 5), 2))
        super_large.append(round(mn * random.uniform(0.3, 0.7), 2))
        large_net.append(round(mn * random.uniform(0.2, 0.4), 2))
        medium_net.append(round(mn * random.uniform(-0.2, 0.2), 2))
        small_net.append(round(mn * random.uniform(-0.2, 0.1), 2))
        main_cum += mn

    return {
        "dates": dates,
        "main_net_inflow": main_net,
        "main_net_inflow_pct": main_pct,
        "super_large_net": super_large,
        "large_net": large_net,
        "medium_net": medium_net,
        "small_net": small_net,
        "data_points": days,
    }


# ─── Indicator Helpers ───────────────────────────────────────────────

import numpy as np


def _sma(arr, window):
    """Simple moving average with NaN padding."""
    result = np.full(len(arr), np.nan)
    for i in range(window - 1, len(arr)):
        result[i] = np.mean(arr[i - window + 1 : i + 1])
    return result.tolist()


def _ema(arr, window):
    """Exponential moving average."""
    result = np.full(len(arr), np.nan)
    if len(arr) > 0:
        result[0] = arr[0]
        alpha = 2 / (window + 1)
        for i in range(1, len(arr)):
            result[i] = alpha * arr[i] + (1 - alpha) * result[i - 1]
    return result.tolist()


def _rsi(close, window):
    """RSI indicator."""
    delta = np.diff(close, prepend=close[0])
    gain = np.where(delta > 0, delta, 0.0)
    loss = np.where(delta < 0, -delta, 0.0)
    result = np.full(len(close), np.nan)
    for i in range(window, len(close)):
        avg_gain = np.mean(gain[i - window + 1 : i + 1])
        avg_loss = np.mean(loss[i - window + 1 : i + 1])
        if avg_loss == 0:
            result[i] = 100.0
        else:
            rs = avg_gain / avg_loss
            result[i] = 100.0 - (100.0 / (1.0 + rs))
    return result.tolist()


def _atr(high, low, close, window):
    """Average True Range."""
    tr = np.maximum(
        high - low,
        np.maximum(
            np.abs(high - np.roll(close, 1)),
            np.abs(low - np.roll(close, 1)),
        ),
    )
    tr[0] = high[0] - low[0]
    return _sma(tr, window)
