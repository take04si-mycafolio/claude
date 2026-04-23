#!/usr/bin/env bash
#
# 完全リセット: アプリとDBを一度消して、最新コードで作り直す
# パラメータ不要、質問もしない（ハードコード版）
#
# 実行方法:
#   curl -sLo reset.sh https://raw.githubusercontent.com/take04si-mycafolio/claude/claude/wordpress-data-import-LNuN3/deploy/reset.sh && bash reset.sh
#

set -euo pipefail

DOMAIN="sc-tsusho.jp"
DOMAIN_WWW="www.sc-tsusho.jp"
APP_NAME="tushou"
APP_USER="deploy"
APP_DIR="/home/${APP_USER}/app"
REPO_URL="https://github.com/take04si-mycafolio/claude.git"
BRANCH="claude/wordpress-data-import-LNuN3"
DB_NAME="tushou"
DB_USER="tushou"
LETSENCRYPT_EMAIL="take04si@yahoo.co.jp"
ADMIN_EMAIL="take04si@yahoo.co.jp"
ADMIN_PASSWORD="admin1234"

GREEN='\033[0;32m'; CYAN='\033[0;36m'; RED='\033[0;31m'; YELLOW='\033[1;33m'; NC='\033[0m'
log()  { echo -e "${CYAN}==>${NC} $*"; }
ok()   { echo -e "${GREEN}OK${NC} $*"; }
warn() { echo -e "${YELLOW}!${NC} $*"; }
err()  { echo -e "${RED}ERR${NC} $*" >&2; }

if [ "$(id -u)" -ne 0 ]; then err "Run as root"; exit 1; fi

echo ""
echo "====================================================="
echo " TUSHOU FULL RESET & DEPLOY"
echo "====================================================="
echo ""

# ==================== 1. システム確認 ====================
log "[1/10] Ensure system packages"
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get install -y -qq \
  python3.12 python3.12-venv python3-pip \
  postgresql postgresql-contrib \
  nginx git curl wget \
  ufw \
  certbot python3-certbot-nginx \
  build-essential libpq-dev locales
locale-gen en_US.UTF-8 || true
locale-gen C.UTF-8 || true

# ==================== 2. Firewall ====================
log "[2/10] Firewall"
ufw allow OpenSSH >/dev/null
ufw allow 'Nginx Full' >/dev/null
ufw --force enable >/dev/null || true

# ==================== 3. Create app user ====================
log "[3/10] App user"
if ! id "$APP_USER" &>/dev/null; then
  adduser --disabled-password --gecos "" "$APP_USER"
fi
usermod -aG www-data "$APP_USER" || true

# ==================== 4. Nuke old app dir ====================
log "[4/10] WIPE: stop service + delete app dir + drop DB"
systemctl stop gunicorn-${APP_NAME} 2>/dev/null || true
systemctl disable gunicorn-${APP_NAME} 2>/dev/null || true
rm -f /etc/systemd/system/gunicorn-${APP_NAME}.service
systemctl daemon-reload

rm -rf "${APP_DIR}"
sudo -u postgres dropdb --if-exists "${DB_NAME}"
sudo -u postgres psql -c "DROP ROLE IF EXISTS ${DB_USER};" 2>/dev/null || true
ok "Wiped"

# ==================== 5. Recreate DB (UTF-8 forced) ====================
log "[5/10] Create fresh UTF-8 PostgreSQL DB"
DB_PASSWORD=$(openssl rand -base64 32 | tr -d '/+=' | cut -c1-24)
sudo -u postgres psql <<SQL
CREATE ROLE ${DB_USER} LOGIN PASSWORD '${DB_PASSWORD}';
CREATE DATABASE ${DB_NAME}
  WITH OWNER = ${DB_USER}
       ENCODING = 'UTF8'
       LC_COLLATE = 'C.UTF-8'
       LC_CTYPE = 'C.UTF-8'
       TEMPLATE = template0;
SQL
ENC=$(sudo -u postgres psql -tAc "SELECT pg_encoding_to_char(encoding) FROM pg_database WHERE datname='${DB_NAME}'")
[ "$ENC" = "UTF8" ] || { err "DB not UTF8: $ENC"; exit 1; }
ok "DB encoding: ${ENC}"

# ==================== 6. Clone fresh ====================
log "[6/10] Clone app fresh"
sudo -u "$APP_USER" git clone --branch "${BRANCH}" --depth 1 "${REPO_URL}" "${APP_DIR}"

cd "${APP_DIR}"
# 最新commit確認
echo "  commit: $(sudo -u $APP_USER git -C $APP_DIR rev-parse --short HEAD)"
echo "  max_length check: $(grep -c 'max_length=500' apps/products/models.py) (should be 4+)"

# ==================== 7. Python venv ====================
log "[7/10] Python venv & dependencies"
sudo -u "$APP_USER" python3.12 -m venv "${APP_DIR}/.venv"
sudo -u "$APP_USER" "${APP_DIR}/.venv/bin/pip" install --upgrade pip -q
sudo -u "$APP_USER" "${APP_DIR}/.venv/bin/pip" install -r "${APP_DIR}/requirements.txt" -q
ok "venv ready"

# ==================== 8. .env, migrate, data ====================
log "[8/10] Config + migrate + import WP + admin"
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

sudo -u "$APP_USER" bash <<EOF
set -e
cd "${APP_DIR}"

echo "  running migrations..."
.venv/bin/python manage.py migrate --noinput

echo "  checking schema..."
.venv/bin/python manage.py shell <<PY
from django.db import connection
with connection.cursor() as c:
    c.execute("SELECT column_name, character_maximum_length FROM information_schema.columns WHERE table_name='products_product' AND data_type='character varying' ORDER BY column_name")
    for r in c.fetchall():
        print(f"    products_product.{r[0]} = varchar({r[1]})")
PY

.venv/bin/python manage.py init_product_types
.venv/bin/python manage.py collectstatic --noinput -v 0

# Download WP XML
XML=/tmp/wordpress-export.xml
if [ ! -s "\$XML" ] || ! head -c 30 "\$XML" | grep -q '<?xml'; then
  echo "  downloading WP XML..."
  FID=1s6F0SmGrvRthzIFut4QTPDwA65eea5hz
  curl -sL -c /tmp/gck.txt "https://drive.google.com/uc?export=download&id=\${FID}" -o /tmp/gd.html || true
  UUID=\$(grep -oE 'uuid=[^&"]*' /tmp/gd.html 2>/dev/null | head -1 | cut -d= -f2 || echo "")
  curl -sL -b /tmp/gck.txt "https://drive.usercontent.google.com/download?id=\${FID}&export=download&confirm=t&uuid=\${UUID}" -o "\$XML"
fi

if head -c 30 "\$XML" | grep -q '<?xml'; then
  echo "  importing WordPress data..."
  .venv/bin/python manage.py import_wordpress "\$XML"
else
  echo "  WARN: XML download failed"
fi

echo "  creating admin user..."
.venv/bin/python manage.py shell <<PY
from django.contrib.auth import get_user_model
U = get_user_model()
u, created = U.objects.get_or_create(email="${ADMIN_EMAIL}", defaults={
    "username": "${ADMIN_EMAIL}", "is_staff": True, "is_superuser": True, "email_verified": True,
})
u.is_staff = True; u.is_superuser = True; u.email_verified = True
u.set_password("${ADMIN_PASSWORD}")
u.save()
print(f"    admin user: {u.email} ({'created' if created else 'updated'})")
PY
EOF
ok "DB populated"

# ==================== 9. Gunicorn + Nginx ====================
log "[9/10] Gunicorn + Nginx"
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
systemctl start gunicorn-${APP_NAME}
sleep 2
systemctl is-active --quiet gunicorn-${APP_NAME} || { err "gunicorn failed"; journalctl -u gunicorn-${APP_NAME} -n 20 --no-pager; exit 1; }

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
nginx -t
systemctl reload nginx
ok "Web stack ready"

# ==================== 10. SSL ====================
log "[10/10] SSL (Let's Encrypt)"
certbot --nginx --non-interactive --agree-tos --email "${LETSENCRYPT_EMAIL}" --redirect \
    -d "${DOMAIN}" -d "${DOMAIN_WWW}" || \
    warn "SSL failed. Run later: certbot --nginx -d ${DOMAIN} -d ${DOMAIN_WWW}"

echo ""
echo "====================================================="
echo -e " ${GREEN}DONE${NC}"
echo "====================================================="
echo " URL    : https://${DOMAIN}/"
echo " Admin  : https://${DOMAIN}/admin/  (${ADMIN_EMAIL})"
echo ""
echo " IMPORTANT: Change admin password after login!"
echo " /admin/ -> Users -> take04si@yahoo.co.jp -> change"
echo ""
echo " DB password (save): ${DB_PASSWORD}"
echo "====================================================="
