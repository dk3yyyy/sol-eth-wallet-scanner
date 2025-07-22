# DK3Y Wallet Scanner Bot

A professional, feature-rich Telegram bot for analyzing Solana and Ethereum wallet addresses. Get comprehensive portfolio insights with real-time market data, interactive navigation, and professional UI design.

## ✨ Features

### 🚀 **Core Functionality**

- **Multi-chain Support**: Analyze both Solana and Ethereum wallets
- **Real-time Data**: Live price feeds from CoinGecko and DexScreener
- **Portfolio Analytics**: Token allocation, value distribution, market metrics
- **Smart Filtering**: Automatic dust token filtering (>$0.01 threshold)

### 💎 **User Experience**

- **Progressive Loading**: Real-time progress indicators during analysis
- **Interactive Pagination**: Navigate through large token portfolios
- **Professional UI**: Clean, modern interface with emoji indicators
- **Explorer Integration**: Direct links to Solscan (Solana) and DeBank (Ethereum)

### ⚡ **Performance**

- **Smart Caching**: 5-minute cache for faster repeated queries
- **Async Processing**: Concurrent API calls for optimal speed  
- **Rate Limiting**: Built-in protections for API stability
- **Error Handling**: Graceful degradation and user-friendly error messages

## 🎮 Usage

### **Commands**

- `/start` — Welcome message and feature overview
- `/status` or `/ping` — Bot health check and uptime

### **Wallet Analysis**

Simply send any valid wallet address:

- **Solana**: `11111112D4FgiiiikjQKNNh4rJN4rENWDCK8`  
- **Ethereum**: `0x742d35Cc6634C0532925a3b8D4037C973B26Ed33`

The bot will automatically detect the wallet type and provide:

- Balance and USD value
- Token holdings with market data
- Portfolio allocation percentages  
- Interactive navigation for large portfolios

## 🛠️ Setup

### **Prerequisites**

- Python 3.8+
- Telegram Bot Token (from [@BotFather](https://t.me/botfather))
- Etherscan API Key (from [etherscan.io](https://etherscan.io/apis))

### **Installation**

1. **Clone the repository:**

   ```sh
   git clone <your-repo-url>
   cd "solana wallet scan"
   ```

2. **Install dependencies:**

   ```sh
   pip install -r requirements.txt
   ```

3. **Create environment file:**

   ```env
   TELEGRAM_TOKEN=your_telegram_bot_token_here
   ETHERSCAN_API_KEY=your_etherscan_api_key_here
   ```

4. **Run the bot:**

   ```sh
   python main.py
   ```

## 📋 Dependencies

**Core Libraries:**

- `python-telegram-bot==22.3` — Telegram Bot API wrapper
- `aiohttp==3.12.14` — Async HTTP client for API calls
- `requests==2.32.4` — HTTP library for sync requests  
- `python-dotenv` — Environment variable management

**Full dependency list available in `requirements.txt`**

## 🔧 Configuration

### **Environment Variables**

| Variable | Description | Required |
|----------|-------------|----------|
| `TELEGRAM_TOKEN` | Your Telegram bot token from BotFather | ✅ Yes |
| `ETHERSCAN_API_KEY` | Your Etherscan API key for Ethereum data | ✅ Yes |

### **Bot Settings**

- **Cache Duration**: 5 minutes (300 seconds)
- **Dust Filter**: $0.01 minimum token value
- **Tokens Per Page**: 6 tokens maximum
- **Message Length**: 4000 character limit

## 🔒 Security

- ✅ **Environment Variables**: All secrets stored in `.env` file
- ✅ **Git Protection**: `.env` excluded from version control  
- ✅ **Error Handling**: Safe error messages without exposing internals
- ✅ **Rate Limiting**: Built-in API call protections

## 🚀 API Integrations

- **Solana RPC**: `api.mainnet-beta.solana.com`
- **CoinGecko**: Price feeds for SOL/ETH
- **DexScreener**: Solana token metadata and market data
- **Etherscan**: Ethereum balance and transaction data

## 📊 Features in Detail

### **Solana Analysis**

- SOL balance and USD value
- SPL token detection and analysis  
- Market cap and volume data
- 24h price change indicators
- Direct links to Solscan explorer

### **Ethereum Analysis**

- ETH balance and USD value
- Basic portfolio overview
- Direct links to DeBank explorer

### **Progressive Loading**

- Real-time status updates during analysis
- Step-by-step progress indicators
- User-friendly loading experience

## 🐛 Troubleshooting

**Common Issues:**

1. **"TELEGRAM_TOKEN not found"**
   - Ensure `.env` file exists with valid bot token

2. **"ETHERSCAN_API_KEY not set"**
   - Add your Etherscan API key to `.env` file

3. **Slow response times**
   - Normal for large portfolios with many tokens
   - Bot uses caching to improve subsequent requests

## 📄 License

MIT License - See LICENSE file for details

## 👥 Contributing

Contributions welcome! Please:

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Submit a pull request

## 🙏 Credits

**Developer:** [dk3yyyy](https://github.com/dk3yyyy)

**APIs & Services:**

- Telegram Bot API
- Solana RPC Network  
- CoinGecko API
- DexScreener API
- Etherscan API

---

*🌟 Star this repo if you find it useful! Open source and free to use.*

## 💸 Tips

If you'd like to support the project, you can send tips to any of the following addresses:

- **SOL:** `CZXTNF5k7BWTW8fR7KGNjXTmyUedRgMMPXmi8jWKPfeK`
- **ETH:** `0x6327E5374d244a11cf1d68f189E55f27e3EEe043`
- **BTC:** `bc1qtwe8mxt8nu9guquh0s9g3ap9uuftd057qfp57s`
- **USDT (Tron):** `TJMSyxu2J8zvMCcv6buN7zJNkmWn1n9qMQ`
