#!/usr/bin/env bash
#
# Recovery script: DBをUTF-8で作り直して、そのまま最後まで通す
# 途中で失敗した場合の「やり直し用」
#
# 実行方法:
#   curl -sL https://raw.githubusercontent.com/take04si-mycafolio/claude/claude/wordpress-data-import-LNuN3/deploy/fix.sh -o fix.sh
#   bash fix.sh
#

set -euo pipefail

DOMAIN="sc-tsusho.jp"
DOMAIN_WWW="www.sc-tsusho.jp"
APP_NAME="tushou"
APP_USER="deploy"
APP_DIR="/home/${APP_USER}/app"
DB_NAME="tushou"
DB_USER="tushou"

GREEN='\033[0;32m'; CYAN='\033[0;36m'; RED='\033[0;31m'; NC='\033[0m'
log() { echo -e "${CYAN}==>${NC} $*"; }
ok()  { echo -e "${GREEN}OK${NC} $*"; }
err() { echo -e "${RED}ERR${NC} $*" >&2; }

if [ "$(id -u)" -ne 0 ]; then err "Run as root"; exit 1; fi

# tty helper (pipe-safe)
read_tty() {
  local prompt="$1" var="$2" silent="${3:-}"
  if [ -t 0 ]; then
    if [ -n "$silent" ]; then read -rsp "$prompt" "$var"; echo ""; else read -rp "$prompt" "$var"; fi
  elif [ -e /dev/tty ]; then
    if [ -n "$silent" ]; then read -rsp "$prompt" "$var" < /dev/tty; echo ""; else read -rp "$prompt" "$var" < /dev/tty; fi
  else err "no tty"; exit 1; fi
}

echo ""
echo "======================================="
echo " TUSHOU fix & complete setup"
echo "======================================="
echo ""
read_tty "Let's Encrypt email / SSL email: " LETSENCRYPT_EMAIL
read_tty "Admin email (blank=SSL email): " ADMIN_EMAIL
[ -z "$ADMIN_EMAIL" ] && ADMIN_EMAIL="$LETSENCRYPT_EMAIL"
read_tty "Admin password (8+ chars): " ADMIN_PASSWORD "silent"
read_tty "Confirm: " ADMIN_PASSWORD2 "silent"
[ "$ADMIN_PASSWORD" = "$ADMIN_PASSWORD2" ] || { err "password mismatch"; exit 1; }
[ ${#ADMIN_PASSWORD} -ge 8 ] || { err "password too short"; exit 1; }

echo ""
log "[1] Ensure locale C.UTF-8"
locale-gen en_US.UTF-8 2>/dev/null || true

log "[2] Stop Gunicorn (if running)"
systemctl stop gunicorn-${APP_NAME} 2>/dev/null || true

log "[3] Recreate PostgreSQL DB with UTF-8"
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

# 既存DB問答無用で削除、UTF8で作り直し
sudo -u postgres dropdb --if-exists "${DB_NAME}"
sudo -u postgres psql <<SQL
CREATE DATABASE ${DB_NAME}
  WITH OWNER = ${DB_USER}
       ENCODING = 'UTF8'
       LC_COLLATE = 'C.UTF-8'
       LC_CTYPE = 'C.UTF-8'
       TEMPLATE = template0;
SQL
ok "DB recreated with UTF-8"

# エンコーディング確認
ENC=$(sudo -u postgres psql -tAc "SELECT pg_encoding_to_char(encoding) FROM pg_database WHERE datname='${DB_NAME}'")
echo "  encoding: ${ENC}"
[ "$ENC" = "UTF8" ] || { err "DB is not UTF8! Got: ${ENC}"; exit 1; }

log "[4] Update .env"
DJANGO_SECRET=$(openssl rand -base64 50 | tr -d '/+=' | cut -c1-50)
cat > "${APP_DIR}/.env" <<ENV
DJANGO_SECRET_KEY=${DJANGO_SECRET}
DJANGO_DEBUG=False
DJANGO_ALLOWED_HOSTS=${DOMAIN},${DOMAIN_WWW},localhost
DJANGO_CSRF_TRUSTED_ORIGINS=https://${DOMAIN},https://${DOMAIN_WWW}
DATABASE_URL=postgres://${DB_USER}:${DB_PASSWORD}@localhost:5432/${DB_NAME}
DJANGO_EMAIL_BACKEND=django.core.mail.backends.console.EmailBackend
DEFAULT_FROM_EMAIL=no-reply@${DOMAIN}
SITE_NAME=美容家電TUSHOU
ENV
chown ${APP_USER}:${APP_USER} "${APP_DIR}/.env"
chmod 600 "${APP_DIR}/.env"

log "[5] Pull latest code"
sudo -u "$APP_USER" git -C "${APP_DIR}" fetch origin claude/wordpress-data-import-LNuN3 --depth 1
sudo -u "$APP_USER" git -C "${APP_DIR}" reset --hard FETCH_HEAD
sudo -u "$APP_USER" "${APP_DIR}/.venv/bin/pip" install -r "${APP_DIR}/requirements.txt" -q

log "[6] Migrate + init data + import WordPress"
sudo -u "$APP_USER" bash <<EOF
set -e
cd "${APP_DIR}"
.venv/bin/python manage.py migrate --noinput
.venv/bin/python manage.py init_product_types
.venv/bin/python manage.py collectstatic --noinput -v 0

XML=/tmp/wordpress-export.xml
if [ ! -s "\$XML" ] || ! head -c 30 "\$XML" | grep -q '<?xml'; then
  echo "  downloading WordPress XML..."
  FID=1s6F0SmGrvRthzIFut4QTPDwA65eea5hz
  curl -sL -c /tmp/gck.txt "https://drive.google.com/uc?export=download&id=\${FID}" -o /tmp/gdrive_first.html || true
  UUID=\$(grep -oE 'uuid=[^&"]*' /tmp/gdrive_first.html | head -1 | cut -d= -f2 || echo "")
  curl -sL -b /tmp/gck.txt "https://drive.usercontent.google.com/download?id=\${FID}&export=download&confirm=t&uuid=\${UUID}" -o "\$XML"
fi

if head -c 30 "\$XML" | grep -q '<?xml'; then
  .venv/bin/python manage.py import_wordpress "\$XML"
else
  echo "  WARNING: XML download failed, skipping import"
fi

.venv/bin/python manage.py shell <<PY
from django.contrib.auth import get_user_model
U = get_user_model()
email = "${ADMIN_EMAIL}"
u, created = U.objects.get_or_create(email=email, defaults={
    "username": email, "is_staff": True, "is_superuser": True, "email_verified": True,
})
u.is_staff = True; u.is_superuser = True; u.email_verified = True
u.set_password("${ADMIN_PASSWORD}")
u.save()
print(f"admin user: {email} ({'created' if created else 'updated'})")
PY
EOF
ok "DB + data ready"

log "[7] Ensure systemd service"
if [ ! -f /etc/systemd/system/gunicorn-${APP_NAME}.service ]; then
  cat > /etc/systemd/system/gunicorn-${APP_NAME}.service <<UNIT
[Unit]
Description=Gunicorn for ${APP_NAME}
After=network.target postgresql.service

[Service]
User=${APP_USER}
Group=www-data
WorkingDirectory=${APP_DIR}
EnvironmentFile=${APP_DIR}/.env
ExecStart=${APP_DIR}/.venv/bin/gunicorn --workers 3 --bind unix:${APP_DIR}/app.sock --umask 007 --access-logfile - config.wsgi:application
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
UNIT
  systemctl daemon-reload
  systemctl enable gunicorn-${APP_NAME}
fi
systemctl restart gunicorn-${APP_NAME}
sleep 2
systemctl is-active --quiet gunicorn-${APP_NAME} || { err "gunicorn not running"; exit 1; }
ok "Gunicorn running"

log "[8] Ensure Nginx config"
if [ ! -f /etc/nginx/sites-available/${APP_NAME} ]; then
  cat > /etc/nginx/sites-available/${APP_NAME} <<NGINX
server {
    listen 80;
    listen [::]:80;
    server_name ${DOMAIN} ${DOMAIN_WWW};
    client_max_body_size 20M;
    location /static/ { alias ${APP_DIR}/staticfiles/; expires 30d; }
    location /media/  { alias ${APP_DIR}/media/; expires 30d; }
    location / {
        proxy_set_header Host \$http_host;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_pass http://unix:${APP_DIR}/app.sock;
    }
}
NGINX
  rm -f /etc/nginx/sites-enabled/default
  ln -sf /etc/nginx/sites-available/${APP_NAME} /etc/nginx/sites-enabled/${APP_NAME}
fi
nginx -t
systemctl reload nginx
ok "Nginx ready"

log "[9] SSL"
certbot --nginx --non-interactive --agree-tos --email "${LETSENCRYPT_EMAIL}" --redirect \
    -d "${DOMAIN}" -d "${DOMAIN_WWW}" || echo "  SSL later: certbot --nginx -d ${DOMAIN} -d ${DOMAIN_WWW}"

echo ""
echo "======================================="
echo -e " ${GREEN}DONE${NC}"
echo "======================================="
echo " https://${DOMAIN}/"
echo " https://${DOMAIN}/admin/  ($ADMIN_EMAIL)"
echo ""
echo " DB password (save!): ${DB_PASSWORD}"
echo "======================================="
