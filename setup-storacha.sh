#!/bin/bash
# =============================================================================
# Storacha IPFS Storage Setup Script
# =============================================================================
# This script helps you set up Storacha (formerly web3.storage) for the
# 1024 Oracle to store research data on IPFS.
# =============================================================================

set -e

echo "╔══════════════════════════════════════════════════════════════════════════════╗"
echo "║            🌐 Storacha IPFS Storage Setup for 1024 Oracle                     ║"
echo "╚══════════════════════════════════════════════════════════════════════════════╝"
echo ""

# Check if storacha CLI is installed
if ! command -v storacha &> /dev/null; then
    echo "📦 Installing Storacha CLI..."
    npm install -g @storacha/cli
    echo "✅ Storacha CLI installed!"
else
    echo "✅ Storacha CLI already installed: $(storacha --version)"
fi

echo ""

# Check current login status
echo "🔑 Checking login status..."
WHOAMI=$(storacha whoami 2>&1 || true)
if [[ "$WHOAMI" == did:key:* ]]; then
    echo "✅ Already logged in as: $WHOAMI"
else
    echo "🔐 You need to log in to Storacha."
    echo ""
    echo "Please run: storacha login"
    echo "Then follow the email verification link."
    echo ""
    read -p "Press Enter after you've completed the login process..."
fi

echo ""

# List spaces
echo "📂 Checking your spaces..."
SPACES=$(storacha space ls 2>&1)
echo "$SPACES"

if [[ -z "$SPACES" ]] || [[ "$SPACES" == *"Error"* ]]; then
    echo ""
    echo "📝 Creating a new space for 1024-oracle..."
    storacha space create "1024-oracle-$(date +%s)" --no-recovery || {
        echo "⚠️ Space creation might require interactive setup."
        echo "Please run: storacha space create \"1024-oracle\""
    }
fi

echo ""

# Get current space info
echo "📊 Current space info:"
storacha space info 2>&1

# Check if space has a provider
SPACE_INFO=$(storacha space info 2>&1)
if [[ "$SPACE_INFO" == *"Providers: none"* ]]; then
    echo ""
    echo "⚠️ Your space doesn't have a storage provider!"
    echo ""
    echo "To add a storage provider (required for uploads), run:"
    echo ""
    echo "  storacha space provision <space-name> --customer your-email@example.com"
    echo ""
    echo "Or visit: https://console.storacha.network/ to manage your space."
    echo ""
fi

# Get the current space DID
SPACE_DID=$(storacha space ls 2>&1 | grep "^\*" | awk '{print $2}')
if [[ -n "$SPACE_DID" ]]; then
    echo ""
    echo "╔══════════════════════════════════════════════════════════════════════════════╗"
    echo "║                              📋 Configuration                                 ║"
    echo "╠══════════════════════════════════════════════════════════════════════════════╣"
    echo "║                                                                              ║"
    echo "║  Add this to your .env file:                                                 ║"
    echo "║                                                                              ║"
    echo "║  STORACHA_SPACE_DID=$SPACE_DID"
    echo "║  STORACHA_USE_CLI=true                                                       ║"
    echo "║                                                                              ║"
    echo "╚══════════════════════════════════════════════════════════════════════════════╝"
fi

echo ""
echo "🎉 Setup complete! Restart the Oracle service to apply changes."
