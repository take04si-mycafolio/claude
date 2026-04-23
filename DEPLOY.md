# ConoHa VPS デプロイ手順

前提: Ubuntu 24.04 LTS、独自ドメインを取得済み（お名前.com等）、ConoHa VPSの最小プラン（1GB〜）で動作可能。

---

## 1. サーバー初期設定

```bash
# rootでログイン後、作業ユーザ作成
adduser deploy
usermod -aG sudo deploy
rsync --archive --chown=deploy:deploy ~/.ssh /home/deploy
# 以降は deploy ユーザでSSHログイン

# システム更新
sudo apt update && sudo apt upgrade -y

# 必要パッケージ
sudo apt install -y python3.12 python3.12-venv python3-pip \
    postgresql postgresql-contrib nginx git ufw certbot python3-certbot-nginx \
    build-essential libpq-dev

# ファイアウォール
sudo ufw allow OpenSSH
sudo ufw allow 'Nginx Full'
sudo ufw enable
```

## 2. PostgreSQL設定

```bash
sudo -u postgres psql <<SQL
CREATE USER bigankiki WITH PASSWORD 'STRONG_PASSWORD_HERE';
CREATE DATABASE bigankiki OWNER bigankiki;
SQL
```

## 3. アプリ配置

```bash
cd /home/deploy
git clone <YOUR_GIT_REPO_URL> app
cd app

python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# .env 作成
cat > .env <<'EOF'
DJANGO_SECRET_KEY=<50文字程度のランダム文字列>
DJANGO_DEBUG=False
DJANGO_ALLOWED_HOSTS=example.com,www.example.com
DJANGO_CSRF_TRUSTED_ORIGINS=https://example.com,https://www.example.com
DATABASE_URL=postgres://bigankiki:STRONG_PASSWORD_HERE@localhost:5432/bigankiki
DJANGO_EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
EMAIL_HOST=<SMTPサーバ>
EMAIL_PORT=587
EMAIL_HOST_USER=<メールユーザ>
EMAIL_HOST_PASSWORD=<メールパスワード>
EMAIL_USE_TLS=True
DEFAULT_FROM_EMAIL=no-reply@example.com
SITE_NAME=美顔器レビュー
EOF

python manage.py migrate
python manage.py collectstatic --noinput
python manage.py createsuperuser
```

## 4. Gunicorn (systemd)

`/etc/systemd/system/gunicorn-bigankiki.service`

```ini
[Unit]
Description=Gunicorn for bigankiki
After=network.target

[Service]
User=deploy
Group=www-data
WorkingDirectory=/home/deploy/app
EnvironmentFile=/home/deploy/app/.env
ExecStart=/home/deploy/app/.venv/bin/gunicorn \
    --workers 3 \
    --bind unix:/home/deploy/app/app.sock \
    config.wsgi:application
Restart=on-failure

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl enable --now gunicorn-bigankiki
sudo systemctl status gunicorn-bigankiki
```

## 5. Nginx

`/etc/nginx/sites-available/bigankiki`

```nginx
server {
    listen 80;
    server_name example.com www.example.com;

    client_max_body_size 20M;

    location /static/ {
        alias /home/deploy/app/staticfiles/;
        expires 30d;
    }
    location /media/ {
        alias /home/deploy/app/media/;
        expires 30d;
    }
    location / {
        proxy_set_header Host $http_host;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_pass http://unix:/home/deploy/app/app.sock;
    }
}
```

```bash
sudo ln -s /etc/nginx/sites-available/bigankiki /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx
```

## 6. ドメイン設定

1. ConoHa VPS管理画面でサーバーのグローバルIPアドレスを確認
2. お名前.com等のDNSで`A`レコードを設定: `example.com` → VPSのIP、`www.example.com` → VPSのIP
3. DNS反映（最大24時間）後に以下でSSL化

```bash
sudo certbot --nginx -d example.com -d www.example.com
```

## 7. デプロイ更新手順

```bash
cd /home/deploy/app
git pull
.venv/bin/pip install -r requirements.txt
.venv/bin/python manage.py migrate
.venv/bin/python manage.py collectstatic --noinput
sudo systemctl restart gunicorn-bigankiki
```

## 8. ソケット権限の注意

Gunicornのsocketにnginx(www-data)がアクセスできる必要があります。もし503が出る場合:

```bash
sudo chown deploy:www-data /home/deploy/app/app.sock
sudo chmod 660 /home/deploy/app/app.sock
```

またはgunicornコマンドに `--umask 007` を追加。
