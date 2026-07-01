#!/usr/bin/env bash
# 🩺 YJCryptoSignal System Diagnostic and Process Conflict Resolver
# Designed for the host system to clear 409 conflicts and guarantee stable execution.
set -euo pipefail

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
CYAN='\033[0;36m'; NC='\033[0m'; BOLD='\033[1m'

echo -e "${CYAN}═══════════════════════════════════════════════════════════════${NC}"
echo -e "${BOLD}🩺 YJCryptoSignal Host Doctor & Process Conflict Resolver${NC}"
echo -e "${CYAN}═══════════════════════════════════════════════════════════════${NC}"

# Check for root
if [[ $EUID -ne 0 ]]; then
   echo -e "${YELLOW}⚠ Warning: Not running as root (some operations like systemctl might fail).${NC}"
fi

echo -e "\n${BOLD}🔍 Phase 1: Environment Diagnostics${NC}"
PROJECT_DIR="/root/projects/YJCryptoSignal/Dev"
ENV_FILE="${PROJECT_DIR}/.env"

if [[ -f "$ENV_FILE" ]]; then
    echo -e "  ${GREEN}✓${NC} .env file found at: $ENV_FILE"
    # Read variables
    BOT_TOKEN=$(grep -E "^BOT_TOKEN=" "$ENV_FILE" | cut -d'=' -f2- | tr -d '"' | tr -d "'")
    MAX_SL_PCT=$(grep -E "^MAX_SL_PCT=" "$ENV_FILE" | cut -d'=' -f2- | tr -d '"' | tr -d "'")
    MAX_ACTIVE_TRADES=$(grep -E "^MAX_ACTIVE_TRADES=" "$ENV_FILE" | cut -d'=' -f2- | tr -d '"' | tr -d "'")
    PORT_SCANNER=$(grep -E "^SCANNER_METRICS_PORT=" "$ENV_FILE" | cut -d'=' -f2- | tr -d '"' | tr -d "'")
    PORT_BOT=$(grep -E "^BOT_METRICS_PORT=" "$ENV_FILE" | cut -d'=' -f2- | tr -d '"' | tr -d "'")
    
    echo -e "     • Bot Token: ${YELLOW}${BOT_TOKEN:0:15}... (hidden for security)${NC}"
    echo -e "     • Max Stop Loss: ${YELLOW}${MAX_SL_PCT:-10.0}%${NC}"
    echo -e "     • Max Active Trades Limit: ${YELLOW}${MAX_ACTIVE_TRADES:-9999} (Unlimited)${NC}"
    echo -e "     • Metrics Scanner Port: ${YELLOW}${PORT_SCANNER:-9090}${NC}"
    echo -e "     • Metrics Bot Port: ${YELLOW}${PORT_BOT:-9091}${NC}"
else
    echo -e "  ${RED}✗ .env file not found at: $ENV_FILE${NC}"
    exit 1
fi

echo -e "\n${BOLD}🔍 Phase 2: Detecting & Terminating Conflict Processes${NC}"
# Find duplicate Telegram polling processes (same bot token or python entrypoints)
conflict_found=false

# Check for bot_main.py running processes
PIDS_BOT=$(pgrep -f "bot/bot_main.py" || true)
if [[ -n "$PIDS_BOT" ]]; then
    echo -e "  ${YELLOW}⚠ Found active bot_main.py processes:${NC} ${PIDS_BOT}"
    conflict_found=true
    for pid in $PIDS_BOT; do
        if [[ $pid -ne $$ ]]; then
            echo -e "    Killing PID $pid..."
            kill -15 "$pid" 2>/dev/null || kill -9 "$pid" 2>/dev/null
        fi
    done
fi

# Check for run_scanner.py running processes
PIDS_SCANNER=$(pgrep -f "run_scanner.py" || true)
if [[ -n "$PIDS_SCANNER" ]]; then
    echo -e "  ${YELLOW}⚠ Found active run_scanner.py processes:${NC} ${PIDS_SCANNER}"
    conflict_found=true
    for pid in $PIDS_SCANNER; do
        if [[ $pid -ne $$ ]]; then
            echo -e "    Killing PID $pid..."
            kill -15 "$pid" 2>/dev/null || kill -9 "$pid" 2>/dev/null
        fi
    done
fi

# Check for any python processes in old project '/root/projects/crypto-signal'
PIDS_OLD=$(pgrep -f "crypto-signal" || true)
if [[ -n "$PIDS_OLD" ]]; then
    echo -e "  ${YELLOW}⚠ Found active legacy crypto-signal processes:${NC} ${PIDS_OLD}"
    conflict_found=true
    for pid in $PIDS_OLD; do
        if [[ $pid -ne $$ ]]; then
            echo -e "    Killing legacy PID $pid..."
            kill -15 "$pid" 2>/dev/null || kill -9 "$pid" 2>/dev/null
        fi
    done
fi

if [[ "$conflict_found" == "false" ]]; then
    echo -e "  ${GREEN}✓ No active duplicate Python processes found.${NC}"
else
    echo -e "  ${GREEN}✓ All conflicting processes terminated.${NC}"
fi

echo -e "\n${BOLD}🧹 Phase 3: Lock File Cleanup${NC}"
# Remove lock files
if [[ -f /tmp/yjcryptosignal-bot.lock ]]; then
    echo -e "  Removing stale bot lock file..."
    rm -f /tmp/yjcryptosignal-bot.lock
fi
if [[ -f /tmp/yjcryptosignal-scanner.lock ]]; then
    echo -e "  Removing stale scanner lock file..."
    rm -f /tmp/yjcryptosignal-scanner.lock
fi
echo -e "  ${GREEN}✓ Lock files clean.${NC}"

echo -e "\n${BOLD}⚙️ Phase 4: Systemd Service Registration & Activation${NC}"
if command -v systemctl &>/dev/null && systemctl | grep -q "init" 2>/dev/null; then
    echo -e "  Reloading systemd daemon..."
    systemctl daemon-reload
    
    echo -e "  Enabling services on boot..."
    systemctl enable yjcryptosignal-bot.service
    systemctl enable yjcryptosignal-scanner.service
    
    echo -e "  Starting services..."
    systemctl restart yjcryptosignal-bot.service
    systemctl restart yjcryptosignal-scanner.service
    
    echo -e "  ${GREEN}✓ Services started successfully via systemd.${NC}"
else
    echo -e "  ${YELLOW}⚠ systemd is not active in this environment (e.g. inside docker container).${NC}"
    echo -e "    You can run standalone using:"
    echo -e "    - ${BOLD}./start_bot.sh &${NC}"
    echo -e "    - ${BOLD}./start_scanner.sh &${NC}"
fi

echo -e "\n${BOLD}📊 Phase 5: Verification & Status Check${NC}"
if command -v systemctl &>/dev/null && systemctl | grep -q "init" 2>/dev/null; then
    echo -e "\n  ${BOLD}yjcryptosignal-bot status:${NC}"
    systemctl status yjcryptosignal-bot --no-pager || true
    echo -e "\n  ${BOLD}yjcryptosignal-scanner status:${NC}"
    systemctl status yjcryptosignal-scanner --no-pager || true
else
    # Simple process table status
    echo -e "  Bot running status:"
    if pgrep -f "bot/bot_main.py" >/dev/null; then
        echo -e "    ${GREEN}● Bot is running stand-alone${NC}"
    else
        echo -e "    ${RED}✗ Bot is not running${NC}"
    fi
    echo -e "  Scanner running status:"
    if pgrep -f "run_scanner.py" >/dev/null; then
        echo -e "    ${GREEN}● Scanner is running stand-alone${NC}"
    else
        echo -e "    ${RED}✗ Scanner is not running${NC}"
    fi
fi

echo -e "\n${CYAN}═══════════════════════════════════════════════════════════════${NC}"
echo -e "${GREEN}✅ System clean and ready! Please check Telegram to start the bot.${NC}"
echo -e "${CYAN}═══════════════════════════════════════════════════════════════${NC}"
