#!/usr/bin/env bash
#
# 美容家電TUSHOU 自動セットアップスクリプト
#
# 実行方法（ConoHaコンソールにroot でログイン後）:
#   curl -sL https://raw.githubusercontent.com/take04si-mycafolio/claude/claude/wordpress-data-import-LNuN3/deploy/setup.sh | bash
#
# 途中で Let's Encrypt 用メールアドレスと管理者パスワードを聞かれます。
#

set -euo pipefail

# ==================== 設定 ====================
DOMAIN="sc-tsusho.jp"
DOMAIN_WWW="www.sc-tsusho.jp"
APP_NAME="tushou"
APP_USER="deploy"
APP_DIR="/home/${APP_USER}/app"
REPO_URL="https://github.com/take04si-mycafolio/claude.git"
BRANCH="claude/wordpress-data-import-LNuN3"
WP_XML_URL_ID="1s6F0SmGrvRthzIFut4QTPDwA65eea5hz"  # Google Drive ファイルID
DB_NAME="tushou"
DB_USER="tushou"

# ==================== 画面出力ヘルパ ====================
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
CYAN='\033[0;36m'
NC='\033[0m'

log()  { echo -e "${CYAN}==>${NC} $*"; }
ok()   { echo -e "${GREEN}✓${NC} $*"; }
warn() { echo -e "${YELLOW}!${NC} $*"; }
err()  { echo -e "${RED}✗${NC} $*" >&2; }

if [ "$(id -u)" -ne 0 ]; then
  err "rootで実行してください"
  exit 1
fi

# ==================== 対話プロンプト ====================
# 環境変数で事前指定されていない場合はttyから読む
read_tty() {
  local prompt="$1" var="$2" silent="${3:-}"
  if [ -t 0 ]; then
    if [ -n "$silent" ]; then read -rsp "$prompt" "$var"; echo ""; else read -rp "$prompt" "$var"; fi
  elif [ -e /dev/tty ]; then
    if [ -n "$silent" ]; then read -rsp "$prompt" "$var" < /dev/tty; echo ""; else read -rp "$prompt" "$var" < /dev/tty; fi
  else
    err "interactive input not available. Please run: bash setup.sh"
    exit 1
  fi
}

echo ""
echo "====================================================="
echo " TUSHOU (biyou-kaden) Setup / セットアップ"
echo "====================================================="
echo ""
echo "Domain / ドメイン: ${DOMAIN}"
echo ""
echo "If Japanese text looks garbled, please ignore - it's"
echo "just font rendering on the console. / 文字化けは表示のみ"
echo ""

read_tty "Email for SSL cert (Let's Encrypt) / SSL用メール: " LETSENCRYPT_EMAIL
if [[ -z "$LETSENCRYPT_EMAIL" || ! "$LETSENCRYPT_EMAIL" =~ ^.+@.+\..+$ ]]; then
  err "Invalid email / メールアドレスが不正"
  exit 1
fi

read_tty "Admin email (blank=same as above) / 管理者メール: " ADMIN_EMAIL
if [[ -z "$ADMIN_EMAIL" ]]; then
  ADMIN_EMAIL="$LETSENCRYPT_EMAIL"
fi

read_tty "Admin password (8+ chars) / 管理者パスワード: " ADMIN_PASSWORD "silent"
if [[ ${#ADMIN_PASSWORD} -lt 8 ]]; then
  err "Password must be 8+ chars / 8文字以上必要"
  exit 1
fi
read_tty "Confirm password / 確認: " ADMIN_PASSWORD2 "silent"
if [[ "$ADMIN_PASSWORD" != "$ADMIN_PASSWORD2" ]]; then
  err "Passwords do not match / パスワード不一致"
  exit 1
fi

echo ""
log "Starting setup (10-20 min) / セットアップ開始"
echo ""

# ==================== 1. システム更新 & 必要パッケージ ====================
log "[1/10] Updating system & installing packages"
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get upgrade -y -qq
apt-get install -y -qq \
  python3.12 python3.12-venv python3-pip \
  postgresql postgresql-contrib \
  nginx \
  git curl wget ca-certificates \
  ufw \
  certbot python3-certbot-nginx \
  build-essential libpq-dev
ok "必要ソフトのインストール完了"

# ==================== 2. ファイアウォール ====================
log "[2/10] Firewall setup"
ufw --force reset
ufw default deny incoming
ufw default allow outgoing
ufw allow OpenSSH
ufw allow 'Nginx Full'
ufw --force enable
ok "ファイアウォール設定完了"

# ==================== 3. 作業ユーザー作成 ====================
log "[3/10] Creating app user"
if ! id "$APP_USER" &>/dev/null; then
  adduser --disabled-password --gecos "" "$APP_USER"
fi
# nginxがソケットにアクセスできるように
usermod -aG www-data "$APP_USER" || true
ok "ユーザー ${APP_USER} 準備完了"

# ==================== 4. PostgreSQL ====================
log "[4/10] PostgreSQL database setup"
DB_PASSWORD=$(openssl rand -base64 32 | tr -d '/+=' | cut -c1-24)
sudo -u postgres psql <<SQL
DO \$\$ BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname='${DB_USER}') THEN
    CREATE ROLE ${DB_USER} LOGIN PASSWORD '${DB_PASSWORD}';
  ELSE
    ALTER ROLE ${DB_USER} WITH PASSWORD '${DB_PASSWORD}';
  END IF;
END \$\$;
SQL
sudo -u postgres psql -tc "SELECT 1 FROM pg_database WHERE datname = '${DB_NAME}'" | grep -q 1 || \
  sudo -u postgres createdb -O "${DB_USER}" "${DB_NAME}"
ok "DB (${DB_NAME}) 作成完了"

# ==================== 5. アプリクローン ====================
log "[5/10] Cloning app source"
if [ ! -d "${APP_DIR}" ]; then
  sudo -u "$APP_USER" git clone --branch "${BRANCH}" --depth 1 "${REPO_URL}" "${APP_DIR}"
else
  sudo -u "$APP_USER" git -C "${APP_DIR}" fetch origin "${BRANCH}" --depth 1
  sudo -u "$APP_USER" git -C "${APP_DIR}" checkout "${BRANCH}"
  sudo -u "$APP_USER" git -C "${APP_DIR}" reset --hard FETCH_HEAD
fi
ok "アプリ取得完了"

# ==================== 6. Python環境と依存関係 ====================
log "[6/10] Python venv & dependencies"
sudo -u "$APP_USER" bash <<EOF
set -e
cd "${APP_DIR}"
if [ ! -d .venv ]; then
  python3.12 -m venv .venv
fi
.venv/bin/pip install --upgrade pip -q
.venv/bin/pip install -r requirements.txt -q
EOF
ok "Python環境構築完了"

# ==================== 7. .env生成 + マイグレーション + データ投入 ====================
log "[7/10] Config + DB init + WordPress import"
DJANGO_SECRET=$(openssl rand -base64 50 | tr -d '/+=' | cut -c1-50)
sudo -u "$APP_USER" bash <<EOF
set -e
cd "${APP_DIR}"
cat > .env <<ENV
DJANGO_SECRET_KEY=${DJANGO_SECRET}
DJANGO_DEBUG=False
DJANGO_ALLOWED_HOSTS=${DOMAIN},${DOMAIN_WWW},localhost
DJANGO_CSRF_TRUSTED_ORIGINS=https://${DOMAIN},https://${DOMAIN_WWW}
DATABASE_URL=postgres://${DB_USER}:${DB_PASSWORD}@localhost:5432/${DB_NAME}
DJANGO_EMAIL_BACKEND=django.core.mail.backends.console.EmailBackend
DEFAULT_FROM_EMAIL=no-reply@${DOMAIN}
SITE_NAME=美容家電TUSHOU
ENV
chmod 600 .env

.venv/bin/python manage.py migrate --noinput
.venv/bin/python manage.py init_product_types
.venv/bin/python manage.py collectstatic --noinput -v 0

# WordPress XMLダウンロード + インポート
XML=/tmp/wordpress-export.xml
if [ ! -s "\$XML" ]; then
  echo "  WordPress XMLをダウンロード中…"
  FIRST=\$(curl -sL -c /tmp/gck.txt "https://drive.google.com/uc?export=download&id=${WP_XML_URL_ID}")
  UUID=\$(echo "\$FIRST" | grep -oE 'uuid=[^&"]*' | head -1 | cut -d= -f2 || echo "")
  curl -sL -b /tmp/gck.txt "https://drive.usercontent.google.com/download?id=${WP_XML_URL_ID}&export=download&confirm=t&uuid=\${UUID}" -o "\$XML"
fi
if head -c 30 "\$XML" | grep -q '<?xml'; then
  .venv/bin/python manage.py import_wordpress "\$XML"
else
  echo "  ⚠ XMLのダウンロードに失敗。後で手動インポートしてください。"
fi

# 管理者アカウント作成
.venv/bin/python manage.py shell <<PY
from django.contrib.auth import get_user_model
U = get_user_model()
email = "${ADMIN_EMAIL}"
u, created = U.objects.get_or_create(email=email, defaults={
    "username": email, "is_staff": True, "is_superuser": True, "email_verified": True,
})
u.is_staff = True
u.is_superuser = True
u.email_verified = True
u.set_password("${ADMIN_PASSWORD}")
u.save()
print(f"admin: {email} ({'created' if created else 'updated'})")
PY
EOF
ok "DB初期化と管理者作成完了"

# ==================== 8. Gunicorn (systemd) ====================
log "[8/10] Gunicorn systemd service"
cat > /etc/systemd/system/gunicorn-${APP_NAME}.service <<UNIT
[Unit]
Description=Gunicorn for ${APP_NAME}
After=network.target postgresql.service

[Service]
User=${APP_USER}
Group=www-data
WorkingDirectory=${APP_DIR}
EnvironmentFile=${APP_DIR}/.env
ExecStart=${APP_DIR}/.venv/bin/gunicorn \\
    --workers 3 \\
    --bind unix:${APP_DIR}/app.sock \\
    --umask 007 \\
    --access-logfile - \\
    config.wsgi:application
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
UNIT

systemctl daemon-reload
systemctl enable gunicorn-${APP_NAME}
systemctl restart gunicorn-${APP_NAME}
sleep 2
if systemctl is-active --quiet gunicorn-${APP_NAME}; then
  ok "Gunicorn起動完了"
else
  err "Gunicornの起動に失敗。systemctl status gunicorn-${APP_NAME} で確認してください"
  exit 1
fi

# ==================== 9. Nginx ====================
log "[9/10] Nginx configuration"
cat > /etc/nginx/sites-available/${APP_NAME} <<NGINX
server {
    listen 80;
    listen [::]:80;
    server_name ${DOMAIN} ${DOMAIN_WWW};

    client_max_body_size 20M;

    location /static/ {
        alias ${APP_DIR}/staticfiles/;
        expires 30d;
        add_header Cache-Control "public, immutable";
    }
    location /media/ {
        alias ${APP_DIR}/media/;
        expires 30d;
    }
    location / {
        proxy_set_header Host \$http_host;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_pass http://unix:${APP_DIR}/app.sock;
    }
}
NGINX

# 既存のdefaultを無効化
rm -f /etc/nginx/sites-enabled/default
ln -sf /etc/nginx/sites-available/${APP_NAME} /etc/nginx/sites-enabled/${APP_NAME}
nginx -t
systemctl reload nginx
ok "Nginx設定完了（http://${DOMAIN}/ でアクセス可能）"

# ==================== 10. Let's Encrypt SSL ====================
log "[10/10] SSL certificate (Let's Encrypt)"
certbot --nginx \
    --non-interactive \
    --agree-tos \
    --email "${LETSENCRYPT_EMAIL}" \
    --redirect \
    -d "${DOMAIN}" -d "${DOMAIN_WWW}" || {
  warn "SSL証明書の取得に失敗しました。DNS反映待ちの可能性があります。"
  warn "後ほど以下を実行してください:"
  warn "  certbot --nginx -d ${DOMAIN} -d ${DOMAIN_WWW}"
}

# ==================== 完了 ====================
echo ""
echo "====================================================="
echo -e " ${GREEN}Setup complete / セットアップ完了${NC}"
echo "====================================================="
echo ""
echo " Site URL    : https://${DOMAIN}/"
echo " Admin page  : https://${DOMAIN}/admin/"
echo " Admin email : ${ADMIN_EMAIL}"
echo ""
echo " IMPORTANT - Save these / 以下は必ず控えておいてください:"
echo " DB name     : ${DB_NAME}"
echo " DB user     : ${DB_USER}"
echo " DB password : ${DB_PASSWORD}"
echo ""
echo " App dir     : ${APP_DIR}"
echo " Service     : gunicorn-${APP_NAME}"
echo ""
echo " --- Useful commands ---"
echo " Restart : systemctl restart gunicorn-${APP_NAME}"
echo " Logs    : journalctl -u gunicorn-${APP_NAME} -f"
echo " Update  : cd ${APP_DIR} && sudo -u ${APP_USER} git pull && systemctl restart gunicorn-${APP_NAME}"
echo ""
echo " Open https://${DOMAIN}/ in your browser!"
echo "====================================================="
