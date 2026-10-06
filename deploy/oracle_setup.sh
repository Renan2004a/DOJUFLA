#!/usr/bin/env bash
# ============================================================
# DOJUFLA - setup em uma VM Ubuntu (Oracle Cloud / qualquer VPS)
# Uso:  bash oracle_setup.sh
#       (rode como o usuário 'ubuntu', que tem sudo)
# ============================================================
set -euo pipefail

REPO_URL="${REPO_URL:-https://github.com/Renan2004a/DOJUFLA.git}"
APP_DIR="$HOME/DOJUFLA"

echo "==> Instalando dependências do sistema..."
sudo apt-get update -y
sudo apt-get install -y python3-venv python3-pip git nginx libgomp1

echo "==> Baixando/atualizando o projeto..."
if [ -d "$APP_DIR/.git" ]; then
    git -C "$APP_DIR" pull --ff-only
else
    git clone "$REPO_URL" "$APP_DIR"
fi

cd "$APP_DIR"

echo "==> Criando ambiente virtual e instalando dependências (pode demorar)..."
python3 -m venv venv
./venv/bin/pip install --upgrade pip
./venv/bin/pip install -r requirements.txt gunicorn==22.0.0

echo "==> Pré-baixando o modelo de embeddings..."
./venv/bin/python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('all-MiniLM-L6-v2')"

if [ ! -f .env ]; then
    echo "==> Criando .env (edite depois com sua GROQ_API_KEY)..."
    cat > .env <<EOF
DOJUFLA_SECRET_KEY=$(openssl rand -hex 32)
GROQ_API_KEY=troque-por-sua-chave
OLLAMA_URL=http://localhost:11434/api/generate
EOF
fi

echo "==> Configurando o serviço (systemd)..."
sudo cp deploy/dojufla.service /etc/systemd/system/dojufla.service
sudo systemctl daemon-reload
sudo systemctl enable --now dojufla

echo "==> Configurando o Nginx (proxy na porta 80)..."
sudo cp deploy/nginx-doJufla.conf /etc/nginx/sites-available/dojufla
sudo ln -sf /etc/nginx/sites-available/dojufla /etc/nginx/sites-enabled/dojufla
sudo rm -f /etc/nginx/sites-enabled/default
sudo nginx -t
sudo systemctl restart nginx

echo "==> Liberando a porta 80 no firewall da VM (iptables)..."
sudo iptables -I INPUT -p tcp --dport 80 -j ACCEPT || true
sudo iptables -I INPUT -p tcp --dport 443 -j ACCEPT || true
if command -v netfilter-persistent >/dev/null 2>&1; then
    sudo netfilter-persistent save || true
fi

echo
echo "============================================================"
echo " PRONTO!"
echo " - Edite o arquivo:  $APP_DIR/.env  (coloque a GROQ_API_KEY)"
echo " - Reinicie depois:  sudo systemctl restart dojufla"
echo " - Acesse:           http://<IP-PUBLICO-DA-VM>"
echo "============================================================"
