#!/usr/bin/env bash
# OmenCtl Web Installer
# Fetches the latest stable release from GitHub and installs it.

set -euo pipefail

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

log() { echo -e "${GREEN}[✓]${NC} $1"; }
err() { echo -e "${RED}[✗]${NC} $1"; exit 1; }
info() { echo -e "${CYAN}[i]${NC} $1"; }

REPO="yunusemreyl/OmenCtl"
TMP_DIR="/tmp/omenctl-release"

if [ "$EUID" -ne 0 ]; then
    err "This script must be run as root. Try: curl -sL https://raw.githubusercontent.com/$REPO/main/install.sh | sudo bash"
fi

info "Checking for latest OmenCtl release..."

# Fetch latest release data from GitHub API
if command -v curl &> /dev/null; then
    RELEASE_JSON=$(curl -s "https://api.github.com/repos/$REPO/releases/latest")
elif command -v wget &> /dev/null; then
    RELEASE_JSON=$(wget -qO- "https://api.github.com/repos/$REPO/releases/latest")
else
    err "curl or wget is required to download the release."
fi

# Extract the tag name and tarball URL
TAG=$(echo "$RELEASE_JSON" | grep -m 1 '"tag_name":' | sed -E 's/.*"([^"]+)".*/\1/')
TARBALL_URL=$(echo "$RELEASE_JSON" | grep -m 1 '"tarball_url":' | sed -E 's/.*"([^"]+)".*/\1/')

if [ -z "$TAG" ] || [ -z "$TARBALL_URL" ]; then
    err "Failed to fetch release information from GitHub. Are there any published releases?"
fi

log "Found latest release: $TAG"

# Clean up any previous temp dir
rm -rf "$TMP_DIR"
mkdir -p "$TMP_DIR"
cd "$TMP_DIR"

info "Downloading release tarball..."
if command -v curl &> /dev/null; then
    curl -sL "$TARBALL_URL" -o omenctl.tar.gz
else
    wget -qO omenctl.tar.gz "$TARBALL_URL"
fi

info "Extracting..."
tar -xzf omenctl.tar.gz
rm omenctl.tar.gz

# GitHub creates a directory like yunusemreyl-OmenCtl-xxxxxxx, find it
EXTRACTED_DIR=$(find . -mindepth 1 -maxdepth 1 -type d | head -n 1)

if [ -z "$EXTRACTED_DIR" ]; then
    err "Extraction failed."
fi

cd "$EXTRACTED_DIR"

if [ ! -x "./setup.sh" ]; then
    chmod +x ./setup.sh
fi

log "Starting OmenCtl setup ($TAG)..."
./setup.sh install

# Cleanup
cd /tmp
rm -rf "$TMP_DIR"
log "OmenCtl $TAG installed successfully!"
