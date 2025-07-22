import os
import sys
import subprocess
import shutil
import json
import time
import re
import logging
import hashlib
from datetime import datetime, timedelta

def install_requirements():
    import importlib.util
    req_file = os.path.join(os.path.dirname(__file__), 'requirements.txt')
    if not os.path.exists(req_file):
        return
    with open(req_file) as f:
        pkgs = [line.strip().split('==')[0] for line in f if line.strip() and not line.startswith('#')]
    missing = []
    for pkg in pkgs:
        try:
            importlib.import_module(pkg.replace('-', '_'))
        except ImportError:
            missing.append(pkg)
    if missing:
        print(f"\n[Auto-Installer] Installing missing packages: {', '.join(missing)}\n")
        subprocess.check_call([sys.executable, '-m', 'pip', 'install', *missing])

install_requirements()

from pyfiglet import Figlet
import requests
import asyncio
import aiohttp
from aiohttp import ClientTimeout
from typing import Dict, List, Optional, Any, Tuple
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler
from dotenv import load_dotenv
from colorama import init, Fore, Style

def print_banner():
    if os.name == 'nt':
        os.system('cls')
    else:
        os.system('clear')
    terminal_width = shutil.get_terminal_size((100, 20)).columns
    f = Figlet(font='big', width=terminal_width)
    banner_text = "DK3Y Wallet Scanner Bot"
    banner = f.renderText(banner_text)
    init(autoreset=True)
    colors = [
        Fore.RED, Fore.GREEN, Fore.YELLOW, Fore.BLUE, Fore.MAGENTA, Fore.CYAN, Fore.WHITE,
        Fore.LIGHTRED_EX, Fore.LIGHTGREEN_EX, Fore.LIGHTYELLOW_EX, Fore.LIGHTBLUE_EX,
        Fore.LIGHTMAGENTA_EX, Fore.LIGHTCYAN_EX, Fore.LIGHTWHITE_EX
    ]
    color_count = len(colors)
    colored_banner = ""
    color_idx = 0
    for char in banner:
        if char != " " and char != "\n":
            colored_banner += colors[color_idx % color_count] + char + Style.RESET_ALL
            color_idx += 1
        else:
            colored_banner += char
    for line in colored_banner.rstrip().split('\n'):
        print(line.center(terminal_width))

load_dotenv()

def escape_markdown(text: str) -> str:
    if not isinstance(text, str):
        text = str(text)
    escape_chars = r'_*[`'
    return re.sub(f'([{re.escape(escape_chars)}])', r'\\\1', text)

def escape_markdown_v2(text: str) -> str:
    if not isinstance(text, str):
        text = str(text)
    escape_chars = r'_*[]()~`>#+-=|{}.!'
    return re.sub(f'([{re.escape(escape_chars)}])', r'\\\1', text)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("telegram").setLevel(logging.WARNING)
logging.getLogger("apscheduler").setLevel(logging.WARNING)

# API Endpoints
SOLANA_RPC_URL = "https://api.mainnet-beta.solana.com"
SOL_PRICE_API = "https://api.coingecko.com/api/v3/simple/price?ids=solana&vs_currencies=usd"
DEXSCREENER_API = "https://api.dexscreener.com/latest/dex/search"
ETHERSCAN_API = "https://api.etherscan.io/api"
ETH_PRICE_API = "https://api.coingecko.com/api/v3/simple/price?ids=ethereum&vs_currencies=usd"

# Telegram bot token and API keys from .env
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
if TELEGRAM_TOKEN is None:
    raise RuntimeError("TELEGRAM_TOKEN is not set in the environment variables!")

ETHERSCAN_API_KEY = os.getenv("ETHERSCAN_API_KEY")

if not ETHERSCAN_API_KEY:
    raise RuntimeError("ETHERSCAN_API_KEY is not set in the .env file!")

# Admin configuration
ADMIN_CHAT_ID = os.getenv("ADMIN_CHAT_ID")
LOG_CHANNEL_ID = os.getenv("LOG_CHANNEL_ID")  # Optional: for user logs

if ADMIN_CHAT_ID:
    ADMIN_CHAT_ID = int(ADMIN_CHAT_ID)
if LOG_CHANNEL_ID:
    LOG_CHANNEL_ID = int(LOG_CHANNEL_ID)

if not ADMIN_CHAT_ID and not LOG_CHANNEL_ID:
    print("⚠️  Warning: Neither ADMIN_CHAT_ID nor LOG_CHANNEL_ID set in .env file. Admin notifications disabled.")
elif LOG_CHANNEL_ID:
    print("✅ User logging will be sent to private channel/group.")
elif ADMIN_CHAT_ID:
    print("✅ User logging will be sent to admin direct message.")

# Enhanced Constants
MAX_MESSAGE_LENGTH = 4000
TOKENS_PER_PAGE = 6  # Reduced for cleaner display
CACHE_DURATION = 300  # 5 minutes cache
MIN_TOKEN_VALUE_USD = 0.01  # Filter out dust tokens

# Cache system
cache = {}

# User tracking system
user_data_file = "user_data.json"
user_count = 0

def load_user_data():
    global user_count
    try:
        if os.path.exists(user_data_file):
            with open(user_data_file, 'r') as f:
                data = json.load(f)
                user_count = data.get('user_count', 0)
                return data.get('users', {})
        return {}
    except Exception as e:
        logger.error(f"Error loading user data: {e}")
        return {}

def save_user_data(users_dict):
    try:
        data = {
            'user_count': user_count,
            'users': users_dict
        }
        with open(user_data_file, 'w') as f:
            json.dump(data, f, indent=2)
    except Exception as e:
        logger.error(f"Error saving user data: {e}")

# Load existing user data on startup
known_users = load_user_data()

async def notify_admin_new_user(application, user_id: int, username: Optional[str], first_name: Optional[str], last_name: Optional[str]):
    target_chat_id = LOG_CHANNEL_ID if LOG_CHANNEL_ID else ADMIN_CHAT_ID
    
    if not target_chat_id:
        return
    
    try:
        global user_count, known_users
        user_count += 1
        
        known_users[str(user_id)] = {
            'user_number': user_count,
            'username': username,
            'first_name': first_name,
            'last_name': last_name,
            'join_date': datetime.now().isoformat()
        }
        
        save_user_data(known_users)
        
        username_display = f"@{username}" if username else "No username"
        full_name = f"{first_name or ''} {last_name or ''}".strip()
        if not full_name:
            full_name = "No name"
        
        if LOG_CHANNEL_ID:
            separator = "━━━━━━━━━━━━━━━━━━━━━━"
            admin_msg = (
                f"🆕 **New User \\#{user_count}**\n"
                f"{escape_markdown_v2(separator)}\n"
                f"👤 **Name:** {escape_markdown_v2(full_name)}\n"
                f"🆔 **Username:** {escape_markdown_v2(username_display)}\n"
                f"🔢 **User ID:** `{user_id}`\n"
                f"📅 **Joined:** {escape_markdown_v2(datetime.now().strftime('%Y-%m-%d %H:%M:%S'))}\n"
                f"📊 **Total Users:** `{user_count}`"
            )
        else:
            admin_msg = (
                f"🆕 *New User\\!* \\[{user_count}\\]\n"
                f"👤 *Name:* {escape_markdown_v2(full_name)}\n"
                f"🆔 *Username:* {escape_markdown_v2(username_display)}\n"
                f"🔢 *User ID:* `{user_id}`\n"
                f"📅 *Joined:* {escape_markdown_v2(datetime.now().strftime('%Y-%m-%d %H:%M:%S'))}"
            )
        
        await application.bot.send_message(
            chat_id=target_chat_id,
            text=admin_msg,
            parse_mode="MarkdownV2"
        )
        
        if LOG_CHANNEL_ID and ADMIN_CHAT_ID and user_count % 10 == 0:
            milestone_msg = f"🎉 *Milestone Alert\\!*\n\nBot has reached **{user_count} total users**\\!"
            try:
                await application.bot.send_message(
                    chat_id=ADMIN_CHAT_ID,
                    text=milestone_msg,
                    parse_mode="MarkdownV2"
                )
            except Exception:
                pass
        
    except Exception as e:
        logger.error(f"Error notifying admin about new user: {e}")

def is_new_user(user_id: int) -> bool:
    return str(user_id) not in known_users

def get_cache_key(prefix: str, data: str) -> str:
    return f"{prefix}_{hashlib.md5(data.encode()).hexdigest()[:8]}"

def is_cache_valid(key: str) -> bool:
    if key not in cache:
        return False
    return time.time() - cache[key]['timestamp'] < CACHE_DURATION

def get_from_cache(key: str) -> Optional[Any]:
    if is_cache_valid(key):
        return cache[key]['data']
    return None

def set_cache(key: str, data: Any) -> None:
    cache[key] = {
        'data': data,
        'timestamp': time.time()
    }

def validate_wallet_address(address: str) -> Tuple[bool, str]:
    address = address.strip()
    
    if address.startswith('0x'):
        if len(address) == 42 and re.match(r'^0x[a-fA-F0-9]{40}$', address):
            return True, 'ethereum'
        else:
            return False, 'invalid_ethereum'
    
    elif re.match(r'^[1-9A-HJ-NP-Za-km-z]{32,44}$', address):
        return True, 'solana'
    else:
        return False, 'invalid_solana'

async def get_sol_balance(wallet_address: str) -> float:
    cache_key = get_cache_key('sol_balance', wallet_address)
    cached_result = get_from_cache(cache_key)
    if cached_result is not None:
        return cached_result
    
    try:
        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "getBalance",
            "params": [wallet_address]
        }
        async with aiohttp.ClientSession() as session:
            async with session.post(SOLANA_RPC_URL, json=payload, timeout=ClientTimeout(total=10)) as response:
                response.raise_for_status()
                balance_data = await response.json()
                balance = balance_data.get("result", {}).get("value", 0) / 1e9
                set_cache(cache_key, balance)
                return balance
    except Exception as e:
        logger.error(f"Error fetching SOL balance: {e}")
        return 0.0

async def get_sol_price() -> float:
    cache_key = get_cache_key('sol_price', 'current')
    cached_result = get_from_cache(cache_key)
    if cached_result is not None:
        return cached_result
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(SOL_PRICE_API, timeout=ClientTimeout(total=10)) as response:
                response.raise_for_status()
                data = await response.json()
                price = data.get("solana", {}).get("usd", 0)
                set_cache(cache_key, price)
                return price
    except Exception as e:
        logger.error(f"Error fetching SOL price: {e}")
        return 0.0

async def get_token_accounts(wallet_address: str) -> List[dict]:
    cache_key = get_cache_key('token_accounts', wallet_address)
    cached_result = get_from_cache(cache_key)
    if cached_result is not None:
        return cached_result
    
    try:
        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "getTokenAccountsByOwner",
            "params": [
                wallet_address,
                {"programId": "TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA"},
                {"encoding": "jsonParsed"}
            ]
        }
        async with aiohttp.ClientSession() as session:
            async with session.post(SOLANA_RPC_URL, json=payload, timeout=ClientTimeout(total=10)) as response:
                response.raise_for_status()
                accounts = (await response.json()).get("result", {}).get("value", [])
                set_cache(cache_key, accounts)
                return accounts
    except Exception as e:
        logger.error(f"Error fetching token accounts: {e}")
        return []

async def get_token_data_dexscreener(session: aiohttp.ClientSession, mint: str, sol_price_usd: float) -> Optional[Dict[str, Any]]:
    cache_key = get_cache_key('token_data', mint)
    cached_result = get_from_cache(cache_key)
    if cached_result is not None:
        return cached_result
    
    try:
        url = f"{DEXSCREENER_API}?q={mint}&chain=solana"
        async with session.get(url, timeout=ClientTimeout(total=15)) as resp:
            resp.raise_for_status()
            data = await resp.json()
            pairs = data.get("pairs", [])
            
            for pair in pairs:
                base_token = pair.get("baseToken", {})
                quote_token = pair.get("quoteToken", {})
                
                # Enhanced token matching
                token_data = None
                if base_token.get("address", "").lower() == mint.lower():
                    name = base_token.get("name", "Unknown")
                    symbol = base_token.get("symbol", "UNK")
                    price_usd = float(pair.get("priceUsd", 0)) if pair.get("priceUsd") else None
                    
                    if quote_token.get("symbol", "").lower() == "sol":
                        price_in_sol = float(pair.get("priceNative", 0)) if pair.get("priceNative") else None
                    else:
                        price_in_sol = price_usd / sol_price_usd if price_usd and sol_price_usd > 0 else None
                    
                    # Get additional metadata
                    market_cap = pair.get("fdv")  # Fully diluted valuation
                    volume_24h = pair.get("volume", {}).get("h24")
                    liquidity = pair.get("liquidity", {}).get("usd")
                    price_change_24h = pair.get("priceChange", {}).get("h24")
                    
                    token_data = {
                        "name": name,
                        "symbol": symbol,
                        "price_usd": price_usd,
                        "price_in_sol": price_in_sol,
                        "market_cap": market_cap,
                        "volume_24h": volume_24h,
                        "liquidity": liquidity,
                        "price_change_24h": price_change_24h,
                        "url": pair.get("url") or f"https://dexscreener.com/solana/{pair.get('pairAddress', mint)}"
                    }
                    
                elif (quote_token.get("address", "").lower() == mint.lower() and 
                      base_token.get("symbol", "").lower() == "sol"):
                    # Handle reverse pair logic
                    name = quote_token.get("name", "Unknown")
                    symbol = quote_token.get("symbol", "UNK")
                    price_native = pair.get("priceNative")
                    
                    if price_native and float(price_native) > 0:
                        price_in_sol = 1 / float(price_native)
                        price_usd = price_in_sol * sol_price_usd if sol_price_usd > 0 else None
                    else:
                        price_in_sol = None
                        price_usd = None
                    
                    token_data = {
                        "name": name,
                        "symbol": symbol,
                        "price_usd": price_usd,
                        "price_in_sol": price_in_sol,
                        "market_cap": None,
                        "volume_24h": None,
                        "liquidity": None,
                        "price_change_24h": None,
                        "url": pair.get("url") or f"https://dexscreener.com/solana/{pair.get('pairAddress', mint)}"
                    }
                
                if token_data:
                    set_cache(cache_key, token_data)
                    return token_data
            
            return None
            
    except Exception as e:
        logger.error(f"Error fetching token data from DexScreener for {mint}: {e}")
        return None

async def get_eth_balance(wallet_address: str) -> float:
    cache_key = get_cache_key('eth_balance', wallet_address)
    cached_result = get_from_cache(cache_key)
    if cached_result is not None:
        return cached_result
    
    try:
        payload = {
            "module": "account",
            "action": "balance",
            "address": wallet_address,
            "tag": "latest",
            "apikey": ETHERSCAN_API_KEY
        }
        async with aiohttp.ClientSession() as session:
            async with session.get(ETHERSCAN_API, params=payload, timeout=ClientTimeout(total=10)) as response:
                response.raise_for_status()
                balance = int((await response.json()).get("result", 0)) / 1e18
                set_cache(cache_key, balance)
                return balance
    except Exception as e:
        logger.error(f"Error fetching ETH balance: {e}")
        return 0.0

async def get_eth_price() -> float:
    cache_key = get_cache_key('eth_price', 'current')
    cached_result = get_from_cache(cache_key)
    if cached_result is not None:
        return cached_result
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(ETH_PRICE_API, timeout=ClientTimeout(total=10)) as response:
                response.raise_for_status()
                data = await response.json()
                price = data.get("ethereum", {}).get("usd", 0)
                set_cache(cache_key, price)
                return price
    except Exception as e:
        logger.error(f"Error fetching ETH price: {e}")
        return 0.0

def format_large_number(num: float) -> str:
    if num is None or num == 0:
        return "0.00"
    
    if num >= 1e12:
        return f"{num/1e12:.2f}T"
    elif num >= 1e9:
        return f"{num/1e9:.2f}B"
    elif num >= 1e6:
        return f"{num/1e6:.2f}M"
    elif num >= 1e3:
        return f"{num/1e3:.2f}K"
    elif num >= 1:
        return f"{num:.2f}"
    elif num >= 0.01:
        return f"{num:.4f}"
    else:
        return f"{num:.8f}"

def format_percentage(pct: Optional[float]) -> str:
    if pct is None:
        return ""
    
    if pct > 0:
        return f"🟢 +{pct:.2f}%"
    elif pct < 0:
        return f"🔴 -{abs(pct):.2f}%"
    else:
        return "⚪ 0.00%"

def create_wallet_keyboard(wallet_address: str, wallet_type: str) -> InlineKeyboardMarkup:
    if wallet_type == 'solana':
        buttons = [
            [InlineKeyboardButton("🌐 Solscan", url=f"https://solscan.io/account/{wallet_address}")]
        ]
    else:  # ethereum
        buttons = [
            [InlineKeyboardButton("🌐 DeBank", url=f"https://debank.com/profile/{wallet_address}")]
        ]
    return InlineKeyboardMarkup(buttons)

async def create_enhanced_solana_analysis(wallet_address: str, progress_callback=None) -> Tuple[str, List[str], InlineKeyboardMarkup]:
    # Fetch all data concurrently
    sol_balance_task = get_sol_balance(wallet_address)
    sol_price_task = get_sol_price()
    token_accounts_task = get_token_accounts(wallet_address)
    
    sol_balance, sol_price_usd, token_accounts = await asyncio.gather(
        sol_balance_task, sol_price_task, token_accounts_task
    )
    
    # Update progress after basic data is fetched
    if progress_callback:
        await progress_callback(
            f"🔍 *Analyzing Solana wallet...*\n"
            f"✅ Wallet balance loaded\n"
            f"✅ Current prices fetched\n"
            f"✅ Token accounts loaded\n"
            f"⏳ Processing token data..."
        )
    
    sol_usd_value = sol_balance * sol_price_usd if sol_price_usd > 0 else 0.0
    
    # Process token accounts (no NFT detection)
    mint_balances: Dict[str, float] = {}
    for account in token_accounts:
        info = account.get("account", {}).get("data", {}).get("parsed", {}).get("info", {})
        mint = info.get("mint")
        balance = info.get("tokenAmount", {}).get("uiAmount", 0)
        if mint and balance > 0:
            mint_balances[mint] = mint_balances.get(mint, 0) + balance
    
    # Get last updated time (use the latest cache timestamp among sol_balance, sol_price, token_accounts)
    cache_keys = [
        get_cache_key('sol_balance', wallet_address),
        get_cache_key('sol_price', 'current'),
        get_cache_key('token_accounts', wallet_address)
    ]
    last_updated_ts = max([cache.get(k, {}).get('timestamp', time.time()) for k in cache_keys])
    last_updated_str = datetime.fromtimestamp(last_updated_ts).strftime('%H:%M:%S')

    # Create main header
    header_msg = (
        f"🟣 *Enhanced Solana Analysis*\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"💰 *SOL Balance:* `{escape_markdown(format_large_number(sol_balance))}` SOL\n"
        f"💵 *SOL Price:* `${escape_markdown(f'{sol_price_usd:,.2f}')}`\n"
        f"💎 *SOL Value:* `${escape_markdown(f'{sol_usd_value:,.2f}')}`\n"
        f"🪙 *SPL Tokens:* `{escape_markdown(str(len(mint_balances)))}` different tokens\n"
    )
    
    if not mint_balances:
        header_msg += f"📭 *No SPL Tokens Found*\n\n"
        header_msg += f"🏦 *Total Portfolio Value:* `${escape_markdown(f'{sol_usd_value:,.2f}')}`"
        return header_msg, [], create_wallet_keyboard(wallet_address, 'solana')

    
    # Fetch token data concurrently
    token_details = []
    total_tokens_value_sol = 0.0
    total_tokens_value_usd = 0.0
    valuable_tokens = 0
    
    async with aiohttp.ClientSession() as session:
        tasks = [get_token_data_dexscreener(session, mint, sol_price_usd) for mint in mint_balances.keys()]
        token_data_list = await asyncio.gather(*tasks)
    
    # Process token data
    for mint, balance, token_data in zip(mint_balances.keys(), mint_balances.values(), token_data_list):
        if token_data and token_data["name"] != "Unknown":
            token_sol_value = balance * token_data["price_in_sol"] if token_data["price_in_sol"] else 0
            token_usd_value = balance * token_data["price_usd"] if token_data["price_usd"] else 0
            
            # Filter out dust tokens
            if token_usd_value >= MIN_TOKEN_VALUE_USD:
                valuable_tokens += 1
                total_tokens_value_sol += token_sol_value
                total_tokens_value_usd += token_usd_value
                
                token_details.append({
                    "name": token_data["name"],
                    "symbol": token_data["symbol"],
                    "mint": mint,
                    "balance": balance,
                    "token_sol_value": token_sol_value,
                    "token_usd_value": token_usd_value,
                    "price_usd": token_data["price_usd"],
                    "market_cap": token_data["market_cap"],
                    "volume_24h": token_data["volume_24h"],
                    "price_change_24h": token_data["price_change_24h"],
                    "url": token_data["url"]
                })
    
    # Sort by USD value
    token_details.sort(key=lambda x: x['token_usd_value'], reverse=True)
    
    # Update progress after token processing
    if progress_callback:
        await progress_callback(
            f"🔍 *Analyzing Solana wallet...*\n"
            f"✅ Wallet balance loaded\n"
            f"✅ Current prices fetched\n"
            f"✅ Token accounts loaded\n"
            f"✅ Token data processed\n"
            f"⏳ Generating report..."
        )
    
    # Calculate totals
    total_wallet_value = sol_usd_value + total_tokens_value_usd
    
    # Enhanced header with analytics
    header_msg += f"💼 *Portfolio Analytics:*\n"
    header_msg += f"🪙 *Valuable Tokens:* `{escape_markdown(str(valuable_tokens))}` (>${escape_markdown(str(MIN_TOKEN_VALUE_USD))})\n"
    header_msg += f"💰 *Token Value:* `{escape_markdown(format_large_number(total_tokens_value_sol))}` SOL (`${escape_markdown(f'{total_tokens_value_usd:,.2f}')}`)\n"
    header_msg += f"🏦 *Total Portfolio:* `${escape_markdown(f'{total_wallet_value:,.2f}')}`\n"
    if total_wallet_value > 0:
        header_msg += f"📊 *Token Allocation:* `{escape_markdown(f'{(total_tokens_value_usd/total_wallet_value*100):.1f}%')}`\n"
    else:
        header_msg += f"📊 *Token Allocation:* `{escape_markdown('0.0%')}`\n"
    header_msg += f"\n⏰ *Last Updated:* `{escape_markdown(last_updated_str)}`"
    
    # Create token pages with enhanced info
    token_messages = []
    if token_details:
        for i in range(0, len(token_details), TOKENS_PER_PAGE):
            chunk = token_details[i:i + TOKENS_PER_PAGE]
            page_num = (i // TOKENS_PER_PAGE) + 1
            total_pages = (len(token_details) + TOKENS_PER_PAGE - 1) // TOKENS_PER_PAGE
            
            token_msg = f"🪙 *Top Holdings - Page {escape_markdown(str(page_num))}/{escape_markdown(str(total_pages))}*\n━━━━━━━━━━━━━━━━━━━━━━\n\n"
            
            for j, token in enumerate(chunk, 1):
                rank = i + j
                display_name = token['name'][:20] + "..." if len(token['name']) > 23 else token['name']
                
                token_msg += f"#{escape_markdown(str(rank))} *{escape_markdown(display_name)}* (`{escape_markdown(token['symbol'])}`)\n"
                token_msg += f"📊 *Balance:* `{escape_markdown(format_large_number(token['balance']))}`\n"
                token_msg += f"💰 *Value:* `${escape_markdown(f'{token['token_usd_value']:,.2f}')}`\n"
                
                # Add market data if available
                extras = []
                if token['market_cap']:
                    extras.append(f"MC: ${escape_markdown(format_large_number(token['market_cap']))}")
                if token['price_change_24h'] is not None:
                    extras.append(escape_markdown(format_percentage(token['price_change_24h'])))
                
                if extras:
                    token_msg += f"📈 {' • '.join(extras)}\n"
                
                # Escape URL for MarkdownV2
                escaped_url = token['url'].replace('(', r'\(').replace(')', r'\)')
                token_msg += f"🔗 [DexScreener]({escaped_url})\n\n"
            
            # Ensure message isn't too long
            if len(token_msg) > MAX_MESSAGE_LENGTH:
                token_msg = token_msg[:MAX_MESSAGE_LENGTH-100] + "...\n\n📱 *Message truncated*"
            
            token_messages.append(token_msg)

    # Final progress update
    if progress_callback:
        await progress_callback(
            f"🔍 *Analyzing Solana wallet...*\n"
            f"✅ Wallet balance loaded\n"
            f"✅ Current prices fetched\n"
            f"✅ Token accounts loaded\n"
            f"✅ Token data processed\n"
            f"✅ Report generated\n"
            f"🎉 *Analysis complete!*"
        )

    return header_msg, token_messages, create_wallet_keyboard(wallet_address, 'solana')

async def create_enhanced_ethereum_analysis(wallet_address: str) -> Tuple[str, InlineKeyboardMarkup]:
    eth_balance, eth_price_usd = await asyncio.gather(
        get_eth_balance(wallet_address),
        get_eth_price()
    )
    
    eth_usd_value = eth_balance * eth_price_usd if eth_price_usd > 0 else 0.0
    
    response = (
        f"🔷 *Enhanced Ethereum Analysis*\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"💰 *ETH Balance:* `{escape_markdown(format_large_number(eth_balance))}` ETH\n"
        f"💵 *ETH Price:* `${escape_markdown(f'{eth_price_usd:,.2f}')}`\n"
        f"💎 *Portfolio Value:* `${escape_markdown(f'{eth_usd_value:,.2f}')}`\n\n"
        f"⏰ *Last Updated:* `{escape_markdown(datetime.now().strftime('%H:%M:%S'))}`"
    )
    
    return response, create_wallet_keyboard(wallet_address, 'ethereum')

async def send_enhanced_wallet_analysis(update: Update, wallet_address: str, wallet_type: str, processing_msg=None):
    try:
        if wallet_type == 'ethereum':
            message, keyboard = await create_enhanced_ethereum_analysis(wallet_address)
            if update.effective_message:
                await update.effective_message.reply_text(
                    message,
                    parse_mode="Markdown",
                    reply_markup=keyboard,
                    disable_web_page_preview=True
                )
        else:  # solana
            # Define progress callback function
            async def update_progress(message_text):
                if processing_msg:
                    try:
                        await processing_msg.edit_text(message_text, parse_mode="Markdown")
                    except Exception:
                        pass  # Message might be deleted or expired
            
            header_msg, token_messages, keyboard = await create_enhanced_solana_analysis(wallet_address, update_progress)
            
            # Small delay to show completion message
            if processing_msg:
                await asyncio.sleep(0.5)
            
            if update.effective_message:
                # Send header with keyboard
                await update.effective_message.reply_text(
                    header_msg,
                    parse_mode="Markdown",
                    reply_markup=keyboard,
                    disable_web_page_preview=True
                )
                # Send first token page with pagination buttons if there are token pages
                if token_messages:
                    page = 0
                    total_pages = len(token_messages)
                    nav_keyboard = get_token_pagination_keyboard(wallet_address, page, total_pages)
                    await update.effective_message.reply_text(
                        token_messages[page],
                        parse_mode="Markdown",
                        reply_markup=nav_keyboard,
                        disable_web_page_preview=True
                    )
    except Exception as e:
        logger.error(f"Error in enhanced analysis: {e}")
        if update.effective_message:
            await update.effective_message.reply_text(
                f"❌ *Error:* `{escape_markdown(str(e))}`",
                parse_mode="Markdown"
            )


def get_token_pagination_keyboard(wallet_address: str, page: int, total_pages: int) -> InlineKeyboardMarkup:
    buttons = []
    if total_pages > 1:
        nav_buttons = []
        if page > 0:
            nav_buttons.append(InlineKeyboardButton("⬅️ Prev", callback_data=f"tokens_{wallet_address}_{page-1}"))
        nav_buttons.append(InlineKeyboardButton(f"Page {page+1}/{total_pages}", callback_data="noop"))
        if page < total_pages - 1:
            nav_buttons.append(InlineKeyboardButton("Next ➡️", callback_data=f"tokens_{wallet_address}_{page+1}"))
        buttons.append(nav_buttons)
    return InlineKeyboardMarkup(buttons)

# Callback handler for interactive buttons and token pagination
async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if query is None:
        return
    await query.answer()

    # Token pagination callback: tokens_{wallet_address}_{page}
    if query.data and query.data.startswith("tokens_"):
        try:
            _, wallet_address, page_str = query.data.split("_", 2)
            page = int(page_str)
            # Recreate token messages for this wallet
            _, token_messages, _ = await create_enhanced_solana_analysis(wallet_address)
            total_pages = len(token_messages)
            if 0 <= page < total_pages:
                nav_keyboard = get_token_pagination_keyboard(wallet_address, page, total_pages)
                await query.edit_message_text(
                    token_messages[page],
                    parse_mode="Markdown",
                    reply_markup=nav_keyboard,
                    disable_web_page_preview=True
                )
        except Exception as e:
            await query.edit_message_text(f"❌ *Error:* `{escape_markdown(str(e))}`", parse_mode="Markdown")
        return

    if query.data == "about":
        about_msg = (
            "🤖 *DK3Y Wallet Scanner *\n\n"
            "👤 *Developer:* [dk3yyyy](https://github.com/dk3yyyy)\n\n"
            "🛠️ *Built with:*\n"
            "• 🐍 Python + python-telegram-bot\n"
            "• 🌐 Real-time API integrations\n"
            "• ⚡ Advanced caching system\n"
            "• 🎨 Professional UI/UX\n\n"
            "🔥 *Features:*\n"
            "• 🔗 Multi-chain support\n"
            "• 📈 Market data integration\n"
            "• 📊 Portfolio analytics\n"
            "• 🧹 Dust token filtering\n"
            "• 🤖 Interactive interface"
        )
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("⬅️ Back", callback_data="back")]
        ])
        await query.edit_message_text(about_msg, parse_mode="Markdown", disable_web_page_preview=False, reply_markup=keyboard)
    elif query.data == "back":
        welcome_msg = (
            "🚀 *DK3Y Wallet Scanner*\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n\n"
            "✨ *Enhanced Features:*\n"
            "• 🚀 Real-time price data & market metrics\n"
            "• 📊 Portfolio analytics & token filtering\n"
            "• 💎 Interactive buttons & refresh capability\n"
            "• ⚡ Smart caching for faster responses\n"
            "• 🎯 Dust token filtering (>$0\\.01)\n\n"
            "📤 *Send any wallet address:*\n"
            "🟣 *Solana:* `11111112D4FgiiiikjQKNNh4rJN4rENWDCK8`\n"
            "🔷 *Ethereum:* `0x742d35Cc6634C0532925a3b8D4037C973B26Ed33`\n\n"
            "🔥 *Try it now!*"
        )
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("ℹ️ About", callback_data="about")]
        ])
        await query.edit_message_text(welcome_msg, parse_mode="Markdown", reply_markup=keyboard)

async def status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_message:
        await update.effective_message.reply_text(
            f"✅ *Bot is running!*\n\n⏰ *Uptime:* `{escape_markdown(datetime.now().strftime('%Y-%m-%d %H:%M:%S'))}`",
            parse_mode="Markdown"
        )

async def admin_stats(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Admin command to view user statistics"""
    if update.effective_message and update.effective_user:
        # Check if user is admin
        if not ADMIN_CHAT_ID or update.effective_user.id != ADMIN_CHAT_ID:
            await update.effective_message.reply_text("❌ *Access Denied*", parse_mode="Markdown")
            return
        
        try:
            # Get recent users (last 10)
            recent_users = []
            sorted_users = sorted(
                known_users.items(), 
                key=lambda x: x[1].get('user_number', 0), 
                reverse=True
            )
            
            for user_id, user_info in sorted_users[:10]:
                username = user_info.get('username')
                full_name = f"{user_info.get('first_name', '')} {user_info.get('last_name', '')}".strip()
                user_num = user_info.get('user_number', 0)
                join_date = user_info.get('join_date', '')
                
                if join_date:
                    try:
                        join_dt = datetime.fromisoformat(join_date)
                        join_str = join_dt.strftime('%m-%d %H:%M')
                    except:
                        join_str = "Unknown"
                else:
                    join_str = "Unknown"
                
                username_display = f"@{username}" if username else "No username"
                name_display = full_name if full_name else "No name"
                
                recent_users.append(f"#{user_num} {escape_markdown(name_display)} ({escape_markdown(username_display)}) - {escape_markdown(join_str)}")
            
            # Check logging configuration
            log_destination = "Private Channel/Group" if LOG_CHANNEL_ID else "Direct Messages" if ADMIN_CHAT_ID else "Disabled"
            
            stats_msg = (
                f"📊 *Bot Statistics*\n"
                f"━━━━━━━━━━━━━━━━━━━━━━\n\n"
                f"👥 *Total Users:* `{user_count}`\n"
                f"📍 *Logging to:* `{escape_markdown(log_destination)}`\n"
                f"📅 *Last Updated:* `{escape_markdown(datetime.now().strftime('%Y-%m-%d %H:%M:%S'))}`\n\n"
                f"🆕 *Recent Users (Last 10):*\n"
                f"{chr(10).join(recent_users) if recent_users else 'No users yet'}"
            )
            
            await update.effective_message.reply_text(
                stats_msg,
                parse_mode="Markdown"
            )
        
        except Exception as e:
            await update.effective_message.reply_text(
                f"❌ *Error fetching stats:* `{escape_markdown(str(e))}`",
                parse_mode="Markdown"
            )

# Enhanced start command
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_message and update.effective_user:
        user = update.effective_user
        
        # Check if this is a new user and notify admin
        if is_new_user(user.id):
            await notify_admin_new_user(
                context.application,
                user.id,
                user.username,
                user.first_name,
                user.last_name
            )
        
        welcome_msg = (
            "🚀 *DK3Y Wallet Scanner*\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n\n"
            "✨ *Enhanced Features:*\n"
            "• 🚀 Real-time price data & market metrics\n"
            "• 📊 Portfolio analytics & token filtering\n"
            "• 💎 Interactive buttons & refresh capability\n"
            "• ⚡ Smart caching for faster responses\n"
            "• 🎯 Dust token filtering (>$0\\.01)\n\n"
            "📤 *Send any wallet address:*\n"
            "🟣 *Solana:* `11111112D4FgiiiikjQKNNh4rJN4rENWDCK8`\n"
            "🔷 *Ethereum:* `0x742d35Cc6634C0532925a3b8D4037C973B26Ed33`\n\n"
            "🔥 *Try it now!*"
        )
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("ℹ️ About", callback_data="about")]
        ])
        await update.effective_message.reply_text(
            welcome_msg,
            parse_mode="Markdown",
            reply_markup=keyboard
        )

async def handle_wallet_address(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_message and update.effective_message.text:
        address = update.effective_message.text.strip()

        # Validate address
        is_valid, wallet_type = validate_wallet_address(address)

        if not is_valid:
            error_msg = "❌ *Invalid Wallet Address*\n\n"
            if wallet_type == 'invalid_ethereum':
                error_msg += "🔷 Ethereum addresses must be 42 characters starting with `0x`"
            elif wallet_type == 'invalid_solana':
                error_msg += "🟣 Solana addresses must be 32-44 characters, base58 (no 0, O, I, l), e.g. `4Nd1mY...`"
            else:
                error_msg += "Please send a valid wallet address:\n🟣 *Solana:* Base58 format\n🔷 *Ethereum:* Hex format starting with `0x`"
            await update.effective_message.reply_text(error_msg, parse_mode="Markdown")
            return

        # Send enhanced processing message with progressive loading
        processing_msg = await update.effective_message.reply_text(
            f"🔍 *Analyzing {escape_markdown(wallet_type.title())} wallet...*\n"
            f"⏳ Fetching wallet balance...\n"
            f"⏳ Getting current prices...\n"
            f"⏳ Loading token accounts...\n"
            f"⏳ Analyzing portfolio...",
            parse_mode="Markdown"
        )

        try:
            await send_enhanced_wallet_analysis(update, address, wallet_type, processing_msg)
            try:
                await processing_msg.delete()
            except Exception:
                # Message might already be deleted or expired
                pass
        except Exception as e:
            try:
                await processing_msg.edit_text(
                    f"❌ *Analysis Failed*\n`{escape_markdown(str(e))}`",
                    parse_mode="Markdown"
                )
            except Exception:
                # If editing fails, send a new message
                if update.effective_message:
                    await update.effective_message.reply_text(
                        f"❌ *Analysis Failed*\n`{escape_markdown(str(e))}`",
                        parse_mode="Markdown"
                    )


def main():
    print_banner()
    print("\n" * 3)
    print("🚀 DK3Y Wallet Scanner Bot is running...\n")
    if not TELEGRAM_TOKEN:
        print("❌ Error: TELEGRAM_TOKEN not found in environment variables")
        return
    application = Application.builder().token(TELEGRAM_TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("status", status))
    application.add_handler(CommandHandler("ping", status))
    application.add_handler(CommandHandler("stats", admin_stats))
    application.add_handler(CallbackQueryHandler(handle_callback))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_wallet_address))
    application.run_polling()

if __name__ == "__main__":
    main()

