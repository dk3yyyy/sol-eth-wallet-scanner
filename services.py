import os
import ssl
import time
import hashlib
import logging
import aiohttp
import certifi
from typing import Optional, Dict, List, Any
from aiohttp import ClientTimeout

# ── Logging ────────────────────────────────────────────────────────────────
logger = logging.getLogger(__name__)

# ── API Endpoints ──────────────────────────────────────────────────────────
SOLANA_RPC_URL = "https://api.mainnet-beta.solana.com"
SOL_PRICE_API = "https://api.coingecko.com/api/v3/simple/price?ids=solana&vs_currencies=usd"
DEXSCREENER_API = "https://api.dexscreener.com/latest/dex/search"
ETHERSCAN_API = "https://api.etherscan.io/api"
ETH_PRICE_API = "https://api.coingecko.com/api/v3/simple/price?ids=ethereum&vs_currencies=usd"

# ── Configuration ──────────────────────────────────────────────────────────
ETHERSCAN_API_KEY = os.getenv("ETHERSCAN_API_KEY")
CACHE_DURATION = 300  # 5 minutes

# ── Secure SSL Context ─────────────────────────────────────────────────────
ssl_context = ssl.create_default_context(cafile=certifi.where())

# ── Cache Service ──────────────────────────────────────────────────────────
class CacheService:
    def __init__(self):
        self._cache: Dict[str, Dict[str, Any]] = {}
        self._last_cleanup = time.time()
        self._cleanup_interval = 600

    def _cleanup(self):
        now = time.time()
        if now - self._last_cleanup > self._cleanup_interval:
            expired_keys = [k for k, v in self._cache.items() if now - v['timestamp'] > CACHE_DURATION]
            for k in expired_keys:
                del self._cache[k]
            self._last_cleanup = now

    def get(self, key: str) -> Optional[Any]:
        self._cleanup()
        if key in self._cache:
            entry = self._cache[key]
            if time.time() - entry['timestamp'] < CACHE_DURATION:
                return entry['data']
            else:
                del self._cache[key]
        return None

    def set(self, key: str, data: Any):
        self._cache[key] = {'data': data, 'timestamp': time.time()}
        self._cleanup()

    def get_key(self, prefix: str, data: str) -> str:
        return f"{prefix}_{hashlib.md5(data.encode()).hexdigest()[:8]}"

cache_service = CacheService()

# ── Solana API Functions ───────────────────────────────────────────────────
async def get_sol_balance(wallet_address: str) -> float:
    cache_key = cache_service.get_key('sol_balance', wallet_address)
    cached_result = cache_service.get(cache_key)
    if cached_result is not None:
        return cached_result
    
    try:
        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "getBalance",
            "params": [wallet_address]
        }
        async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(ssl=ssl_context)) as session:
            async with session.post(SOLANA_RPC_URL, json=payload, timeout=ClientTimeout(total=10)) as response:
                response.raise_for_status()
                balance_data = await response.json()
                balance = balance_data.get("result", {}).get("value", 0) / 1e9
                cache_service.set(cache_key, balance)
                return balance
    except Exception as e:
        logger.error(f"Error fetching SOL balance: {e}")
        return 0.0

async def get_sol_price() -> float:
    cache_key = cache_service.get_key('sol_price', 'current')
    cached_result = cache_service.get(cache_key)
    if cached_result is not None:
        return cached_result
    
    try:
        async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(ssl=ssl_context)) as session:
            async with session.get(SOL_PRICE_API, timeout=ClientTimeout(total=10)) as response:
                response.raise_for_status()
                data = await response.json()
                price = data.get("solana", {}).get("usd", 0)
                cache_service.set(cache_key, price)
                return price
    except Exception as e:
        logger.error(f"Error fetching SOL price: {e}")
        return 0.0

async def get_token_accounts(wallet_address: str) -> List[dict]:
    cache_key = cache_service.get_key('token_accounts', wallet_address)
    cached_result = cache_service.get(cache_key)
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
        async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(ssl=ssl_context)) as session:
            async with session.post(SOLANA_RPC_URL, json=payload, timeout=ClientTimeout(total=10)) as response:
                response.raise_for_status()
                accounts = (await response.json()).get("result", {}).get("value", [])
                cache_service.set(cache_key, accounts)
                return accounts
    except Exception as e:
        logger.error(f"Error fetching token accounts: {e}")
        return []

async def get_token_data_dexscreener(session: aiohttp.ClientSession, mint: str, sol_price_usd: float) -> Optional[Dict[str, Any]]:
    cache_key = cache_service.get_key('token_data', mint)
    cached_result = cache_service.get(cache_key)
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
                
                token_data = None
                if base_token.get("address", "").lower() == mint.lower():
                    name = base_token.get("name", "Unknown")
                    symbol = base_token.get("symbol", "UNK")
                    price_usd = float(pair.get("priceUsd", 0)) if pair.get("priceUsd") else None
                    
                    if quote_token.get("symbol", "").lower() == "sol":
                        price_in_sol = float(pair.get("priceNative", 0)) if pair.get("priceNative") else None
                    else:
                        price_in_sol = price_usd / sol_price_usd if price_usd and sol_price_usd > 0 else None
                    
                    token_data = {
                        "name": name,
                        "symbol": symbol,
                        "price_usd": price_usd,
                        "price_in_sol": price_in_sol,
                        "market_cap": pair.get("fdv"),
                        "volume_24h": pair.get("volume", {}).get("h24"),
                        "liquidity": pair.get("liquidity", {}).get("usd"),
                        "price_change_24h": pair.get("priceChange", {}).get("h24"),
                        "url": pair.get("url") or f"https://dexscreener.com/solana/{pair.get('pairAddress', mint)}"
                    }
                    
                elif (quote_token.get("address", "").lower() == mint.lower() and 
                      base_token.get("symbol", "").lower() == "sol"):
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
                    cache_service.set(cache_key, token_data)
                    return token_data
            
            return None
            
    except Exception as e:
        logger.error(f"Error fetching token data from DexScreener for {mint}: {e}")
        return None

# ── Ethereum API Functions ─────────────────────────────────────────────────
async def get_eth_balance(wallet_address: str) -> float:
    cache_key = cache_service.get_key('eth_balance', wallet_address)
    cached_result = cache_service.get(cache_key)
    if cached_result is not None:
        return cached_result
    
    if not ETHERSCAN_API_KEY:
        logger.error("ETHERSCAN_API_KEY not set")
        return 0.0

    try:
        payload = {
            "module": "account",
            "action": "balance",
            "address": wallet_address,
            "tag": "latest",
            "apikey": ETHERSCAN_API_KEY
        }
        async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(ssl=ssl_context)) as session:
            async with session.get(ETHERSCAN_API, params=payload, timeout=ClientTimeout(total=10)) as response:
                response.raise_for_status()
                balance = int((await response.json()).get("result", 0)) / 1e18
                cache_service.set(cache_key, balance)
                return balance
    except Exception as e:
        logger.error(f"Error fetching ETH balance: {e}")
        return 0.0

async def get_eth_price() -> float:
    cache_key = cache_service.get_key('eth_price', 'current')
    cached_result = cache_service.get(cache_key)
    if cached_result is not None:
        return cached_result
    
    try:
        async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(ssl=ssl_context)) as session:
            async with session.get(ETH_PRICE_API, timeout=ClientTimeout(total=10)) as response:
                response.raise_for_status()
                data = await response.json()
                price = data.get("ethereum", {}).get("usd", 0)
                cache_service.set(cache_key, price)
                return price
    except Exception as e:
        logger.error(f"Error fetching ETH price: {e}")
        return 0.0
