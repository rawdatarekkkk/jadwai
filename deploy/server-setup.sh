#!/usr/bin/env bash
# One-time setup of a fresh Ubuntu 24.04 ARM server (Oracle Cloud Always Free, 4 OCPU / 24 GB).
# Installs Docker and Ollama, opens ports 80/443 in the host firewall, and lets containers reach Ollama.
# Run on the server: bash ~/jadwai/deploy/server-setup.sh
set -euo pipefail
sudo apt-get update -q
sudo DEBIAN_FRONTEND=noninteractive apt-get install -yq ca-certificates curl git build-essential python3-venv unzip iptables-persistent

if ! command -v docker >/dev/null; then
  sudo install -m 0755 -d /etc/apt/keyrings
  sudo curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
  echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo "$VERSION_CODENAME") stable" \
    | sudo tee /etc/apt/sources.list.d/docker.list >/dev/null
  sudo apt-get update -q
  sudo DEBIAN_FRONTEND=noninteractive apt-get install -yq docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
  sudo usermod -aG docker "$USER"
fi

if ! command -v ollama >/dev/null; then
  curl -fsSL https://ollama.com/install.sh | sh
fi
# Listen on all interfaces so containers can reach it; the firewall below keeps it private.
sudo mkdir -p /etc/systemd/system/ollama.service.d
printf '[Service]\nEnvironment="OLLAMA_HOST=0.0.0.0:11434"\nEnvironment="OLLAMA_KEEP_ALIVE=-1"\nEnvironment="OLLAMA_NUM_PARALLEL=1"\nEnvironment="OLLAMA_MAX_LOADED_MODELS=1"\n' \
  | sudo tee /etc/systemd/system/ollama.service.d/jadwai.conf >/dev/null
sudo systemctl daemon-reload
sudo systemctl restart ollama

# Oracle's Ubuntu image rejects everything except SSH in iptables. Open the web ports, and Ollama for
# Docker networks only (172.16.0.0/12). The cloud security list must also allow 80 and 443.
rule() { sudo iptables -C INPUT "$@" 2>/dev/null || sudo iptables -I INPUT 1 "$@"; }
rule -p tcp --dport 80 -j ACCEPT
rule -p tcp --dport 443 -j ACCEPT
rule -p tcp -s 172.16.0.0/12 --dport 11434 -j ACCEPT
sudo netfilter-persistent save
echo "Server ready. Log out and back in once so the docker group applies."
