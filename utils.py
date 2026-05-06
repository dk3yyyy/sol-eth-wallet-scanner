import re
from typing import Optional, Tuple

def escape_markdown(text: str) -> str:
    """Helper function to escape telegram markdown symbols"""
    if not isinstance(text, str):
        text = str(text)
    escape_chars = r'_*[`'
    return re.sub(f'([{re.escape(escape_chars)}])', r'\\\1', text)

def escape_markdown_v2(text: str) -> str:
    """Helper function to escape telegram markdown v2 symbols"""
    if not isinstance(text, str):
        text = str(text)
    escape_chars = r'_*[]()~`>#+-=|{}.!'
    return re.sub(f'([{re.escape(escape_chars)}])', r'\\\1', text)

def format_large_number(num: Optional[float]) -> str:
    """Formats large numbers into readable K/M/B/T strings"""
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
    """Formats percentage with emoji indicators"""
    if pct is None:
        return ""
    
    if pct > 0:
        return f"🟢 +{pct:.2f}%"
    elif pct < 0:
        return f"🔴 -{abs(pct):.2f}%"
    else:
        return "⚪ 0.00%"

def validate_wallet_address(address: str) -> Tuple[bool, str]:
    """Validates Solana and Ethereum wallet addresses"""
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
