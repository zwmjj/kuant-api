"""Open-source credits and citations endpoint."""

from fastapi import APIRouter

router = APIRouter()

CREDITS_DATA = {
    "categories": [
        {
            "id": "frameworks",
            "title": "Full-Stack Quant Frameworks",
            "icon": "\U0001f3d7\ufe0f",
            "projects": [
                {
                    "name": "Qlib",
                    "author": "Microsoft",
                    "github": "https://github.com/microsoft/qlib",
                    "stars": "16k+",
                    "license": "MIT",
                    "description": (
                        "AI-oriented quantitative investment platform. Full ML pipeline covering "
                        "alpha seeking, risk modeling, portfolio optimization, and order execution."
                    ),
                    "usage": "ML model integration (LightGBM, XGBoost) for factor combination and alpha prediction",
                    "tags": ["ML", "Factor", "Portfolio"],
                },
                {
                    "name": "VNpy",
                    "author": "VeighNa",
                    "github": "https://github.com/vnpy/vnpy",
                    "stars": "25k+",
                    "license": "MIT",
                    "description": (
                        "Open-source quantitative trading system development framework for "
                        "Chinese markets with CTP/CTP-mini gateway support and rich built-in strategies."
                    ),
                    "usage": "Reference architecture for event-driven trading engine and CN market connectivity",
                    "tags": ["Trading", "CN Market", "Event-Driven"],
                },
                {
                    "name": "QuantConnect Lean",
                    "author": "QuantConnect",
                    "github": "https://github.com/QuantConnect/Lean",
                    "stars": "10k+",
                    "license": "Apache 2.0",
                    "description": (
                        "Lean Algorithmic Trading Engine \u2013 cloud-based or on-prem backtesting "
                        "and live trading across multiple asset classes and brokerages."
                    ),
                    "usage": "Inspiration for multi-asset backtesting architecture and strategy abstraction layer",
                    "tags": ["Backtesting", "Multi-Asset", "Cloud"],
                },
                {
                    "name": "FinRL",
                    "author": "AI4Finance Foundation",
                    "github": "https://github.com/AI4Finance-Foundation/FinRL",
                    "stars": "10k+",
                    "license": "MIT",
                    "description": (
                        "Deep reinforcement learning framework for quantitative finance. "
                        "Provides DRL agents for stock trading, portfolio allocation, and crypto trading."
                    ),
                    "usage": "Deep RL strategy exploration and benchmark comparison for ML-based approaches",
                    "tags": ["DRL", "ML", "Portfolio"],
                },
            ],
        },
        {
            "id": "backtesting",
            "title": "Backtesting Engines",
            "icon": "\u23ea",
            "projects": [
                {
                    "name": "Backtrader",
                    "author": "mementum",
                    "github": "https://github.com/mementum/backtrader",
                    "stars": "15k+",
                    "license": "GPL-3.0",
                    "description": (
                        "Feature-rich Python framework for backtesting and live trading. "
                        "Supports multiple data feeds, brokers, analyzers, and plotting."
                    ),
                    "usage": "Strategy backtesting engine and performance analyzer integration",
                    "tags": ["Backtesting", "Strategy", "Analyzer"],
                },
                {
                    "name": "Backtesting.py",
                    "author": "kernc",
                    "github": "https://github.com/kernc/backtesting.py",
                    "stars": "6k+",
                    "license": "AGPL-3.0",
                    "description": (
                        "Lightweight, fast backtesting framework with built-in interactive "
                        "HTML plots and optimization support."
                    ),
                    "usage": "Quick strategy prototyping and interactive visualization of backtest results",
                    "tags": ["Backtesting", "Visualization", "Lightweight"],
                },
                {
                    "name": "Zipline Reloaded",
                    "author": "Stefan Jansen",
                    "github": "https://github.com/stefan-jansen/zipline-reloaded",
                    "stars": "1k+",
                    "license": "Apache 2.0",
                    "description": (
                        "Maintained fork of Quantopian's Zipline backtester. "
                        "Pythonic event-driven system for backtesting with pipeline API."
                    ),
                    "usage": "Pipeline-based factor computation and event-driven backtest engine reference",
                    "tags": ["Backtesting", "Pipeline", "Event-Driven"],
                },
                {
                    "name": "hftbacktest",
                    "author": "nkaz001",
                    "github": "https://github.com/nkaz001/hftbacktest",
                    "stars": "4k+",
                    "license": "MIT",
                    "description": (
                        "High-frequency trading backtesting tool with tick-level simulation, "
                        "supporting order latency modeling and queue position tracking."
                    ),
                    "usage": "Reference for tick-level simulation and microstructure-aware backtesting",
                    "tags": ["HFT", "Tick Data", "Microstructure"],
                },
            ],
        },
        {
            "id": "research",
            "title": "Factor Research & Alpha",
            "icon": "\U0001f9ea",
            "projects": [
                {
                    "name": "Alphalens",
                    "author": "Quantopian",
                    "github": "https://github.com/quantopian/alphalens",
                    "stars": "3k+",
                    "license": "Apache 2.0",
                    "description": (
                        "Performance analysis of alpha factors. Provides factor return analysis, "
                        "information coefficient computation, and turnover analysis."
                    ),
                    "usage": "Factor performance analysis, IC computation, and quantile return analysis",
                    "tags": ["Factor", "Alpha", "Analysis"],
                },
                {
                    "name": "Machine Learning for Trading",
                    "author": "Stefan Jansen",
                    "github": "https://github.com/stefan-jansen/machine-learning-for-trading",
                    "stars": "13k+",
                    "license": "",
                    "description": (
                        "Comprehensive code repository for the book 'Machine Learning for Algorithmic Trading'. "
                        "Contains 100+ alpha factors including WorldQuant 101 implementations."
                    ),
                    "usage": "Alpha factor library reference including WorldQuant 101 formulaic alpha implementations",
                    "tags": ["ML", "Alpha", "WorldQuant 101"],
                },
                {
                    "name": "WorldQuant 101 Alphas",
                    "author": "Zura Kakushadze",
                    "github": "",
                    "stars": "",
                    "license": "",
                    "description": (
                        "Based on the paper '101 Formulaic Alphas' by Zura Kakushadze. "
                        "A collection of 101 real-life quantitative trading alphas expressed as mathematical formulas."
                    ),
                    "usage": "Core formulaic alpha factor library for cross-sectional equity factor research",
                    "tags": ["Alpha", "Factor", "Research Paper"],
                },
            ],
        },
        {
            "id": "data",
            "title": "Data Sources",
            "icon": "\U0001f4ca",
            "projects": [
                {
                    "name": "AKShare",
                    "author": "AKFamily",
                    "github": "https://github.com/akfamily/akshare",
                    "stars": "9k+",
                    "license": "MIT",
                    "description": (
                        "Open-source financial data interface library providing free A-share "
                        "market data, futures, options, funds, bonds, and macro-economic data."
                    ),
                    "usage": "Free A-share historical data acquisition for CN market backtesting",
                    "tags": ["A-Share", "Free Data", "CN Market"],
                },
                {
                    "name": "Tushare",
                    "author": "waditu",
                    "github": "https://github.com/waditu/tushare",
                    "stars": "13k+",
                    "license": "BSD-3",
                    "description": (
                        "Professional-grade financial data service for A-share market. "
                        "Tushare Pro API provides high-quality, well-structured market data."
                    ),
                    "usage": "A-share pro data source for comprehensive CN market data coverage",
                    "tags": ["A-Share", "Pro Data", "CN Market"],
                },
                {
                    "name": "baostock",
                    "author": "baostock",
                    "github": "https://github.com/baostock/baostock.github.io",
                    "stars": "",
                    "license": "",
                    "description": (
                        "Free, open-source A-share securities data tool providing "
                        "historical K-line data, valuation metrics, and industry classification."
                    ),
                    "usage": "Supplementary free A-share data source for historical price and fundamental data",
                    "tags": ["A-Share", "Free Data", "CN Market"],
                },
                {
                    "name": "yfinance",
                    "author": "Ran Aroussi",
                    "github": "https://github.com/ranaroussi/yfinance",
                    "stars": "14k+",
                    "license": "Apache 2.0",
                    "description": (
                        "Download market data from Yahoo! Finance API. "
                        "Provides reliable access to US and international equity, ETF, and index data."
                    ),
                    "usage": "Primary US market data source for equities, ETFs, and benchmark index data",
                    "tags": ["US Market", "Free Data", "Global"],
                },
                {
                    "name": "WRDS",
                    "author": "Wharton Research Data Services",
                    "github": "",
                    "stars": "",
                    "license": "",
                    "description": (
                        "Academic financial database providing access to CRSP, Compustat, TAQ, "
                        "and other premier research datasets used in top finance publications."
                    ),
                    "usage": "Academic-grade data for research validation and factor model benchmarking",
                    "tags": ["Academic", "CRSP", "Compustat"],
                },
            ],
        },
        {
            "id": "trading",
            "title": "Live Trading",
            "icon": "\u26a1",
            "projects": [
                {
                    "name": "EasyTrader",
                    "author": "shidenggui",
                    "github": "https://github.com/shidenggui/easytrader",
                    "stars": "8k+",
                    "license": "MIT",
                    "description": (
                        "A-share automated trading library supporting multiple broker clients "
                        "including TongHuaShun, HaiTong, and YinHe for programmatic order execution."
                    ),
                    "usage": "A-share automated order execution and broker connectivity",
                    "tags": ["A-Share", "Auto Trading", "Broker API"],
                },
                {
                    "name": "Alpaca-py",
                    "author": "Alpaca",
                    "github": "https://github.com/alpacahq/alpaca-py",
                    "stars": "",
                    "license": "Apache 2.0",
                    "description": (
                        "Official Python SDK for Alpaca's commission-free US stock trading API. "
                        "Supports market data, trading, and account management."
                    ),
                    "usage": "US market live trading API integration for paper and live order execution",
                    "tags": ["US Market", "API", "Commission-Free"],
                },
            ],
        },
        {
            "id": "core",
            "title": "Core Libraries",
            "icon": "\U0001f9f1",
            "projects": [
                {
                    "name": "NumPy",
                    "author": "NumPy",
                    "github": "https://github.com/numpy/numpy",
                    "stars": "",
                    "license": "BSD-3",
                    "description": "Fundamental package for scientific computing with Python. Provides N-dimensional arrays and mathematical functions.",
                    "usage": "Core numerical computation engine for all factor calculations and matrix operations",
                    "tags": ["Numerical", "Array", "Core"],
                },
                {
                    "name": "Pandas",
                    "author": "pandas-dev",
                    "github": "https://github.com/pandas-dev/pandas",
                    "stars": "",
                    "license": "BSD-3",
                    "description": "Powerful data analysis and manipulation library providing DataFrame and Series data structures.",
                    "usage": "Primary data structure for time-series manipulation, factor data, and backtest results",
                    "tags": ["DataFrame", "Time Series", "Core"],
                },
                {
                    "name": "SciPy",
                    "author": "SciPy",
                    "github": "https://github.com/scipy/scipy",
                    "stars": "",
                    "license": "BSD-3",
                    "description": "Library for scientific and technical computing. Provides optimization, statistics, signal processing, and linear algebra.",
                    "usage": "Statistical tests, optimization routines, and signal processing for factor research",
                    "tags": ["Statistics", "Optimization", "Core"],
                },
                {
                    "name": "FastAPI",
                    "author": "fastapi",
                    "github": "https://github.com/fastapi/fastapi",
                    "stars": "",
                    "license": "MIT",
                    "description": "Modern, fast web framework for building APIs with Python based on standard type hints.",
                    "usage": "Backend API framework powering all Kuant endpoints",
                    "tags": ["API", "Backend", "Core"],
                },
                {
                    "name": "Next.js",
                    "author": "Vercel",
                    "github": "https://github.com/vercel/next.js",
                    "stars": "",
                    "license": "MIT",
                    "description": "React framework for production with server-side rendering, static generation, and API routes.",
                    "usage": "Frontend framework for the Kuant web application",
                    "tags": ["Frontend", "SSR", "React"],
                },
                {
                    "name": "React",
                    "author": "Facebook",
                    "github": "https://github.com/facebook/react",
                    "stars": "",
                    "license": "MIT",
                    "description": "A JavaScript library for building user interfaces with a component-based architecture.",
                    "usage": "UI component library for all interactive frontend views",
                    "tags": ["Frontend", "UI", "Components"],
                },
                {
                    "name": "Recharts",
                    "author": "recharts",
                    "github": "https://github.com/recharts/recharts",
                    "stars": "",
                    "license": "MIT",
                    "description": "Composable charting library built on React components and D3 for data visualization.",
                    "usage": "Interactive charts for backtest results, factor analysis, and portfolio dashboards",
                    "tags": ["Charts", "Visualization", "React"],
                },
                {
                    "name": "TailwindCSS",
                    "author": "Tailwind Labs",
                    "github": "https://github.com/tailwindlabs/tailwindcss",
                    "stars": "",
                    "license": "MIT",
                    "description": "Utility-first CSS framework for rapidly building custom user interfaces.",
                    "usage": "Styling framework for all Kuant frontend components",
                    "tags": ["CSS", "Styling", "Frontend"],
                },
                {
                    "name": "Monaco Editor",
                    "author": "Microsoft",
                    "github": "https://github.com/microsoft/monaco-editor",
                    "stars": "",
                    "license": "MIT",
                    "description": "The code editor that powers VS Code, providing rich IntelliSense, validation, and syntax highlighting.",
                    "usage": "In-browser code editor for strategy scripting and factor formula editing",
                    "tags": ["Editor", "Code", "IDE"],
                },
            ],
        },
    ],
}


def _build_response():
    """Build the full credits response with computed summary counts."""
    category_id_map = {
        "frameworks": "frameworks",
        "backtesting": "backtesting",
        "research": "research",
        "data": "data",
        "trading": "trading",
        "core": "core",
    }
    summary = {}
    total = 0
    for cat in CREDITS_DATA["categories"]:
        count = len(cat["projects"])
        total += count
        key = category_id_map.get(cat["id"], cat["id"])
        summary[key] = count

    return {
        **CREDITS_DATA,
        "total_projects": total,
        "summary": summary,
    }


CREDITS_RESPONSE = _build_response()


@router.get("/credits")
async def get_credits():
    """Return open-source project credits and citations."""
    return CREDITS_RESPONSE
