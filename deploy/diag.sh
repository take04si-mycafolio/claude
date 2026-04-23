#!/usr/bin/env bash
# Simple diagnostic - no paste-sensitive quotes or special chars
set +e
echo "========== DIAGNOSTIC =========="
echo ""
echo "-- 1. App dir exists?"
ls -la /home/deploy/app 2>&1 | head -3
echo ""
echo "-- 2. Git commit (should be latest hash)"
sudo -u deploy git -C /home/deploy/app log -1 --oneline 2>&1
echo ""
echo "-- 3. Model max_length values (should show '500' many times)"
grep max_length /home/deploy/app/apps/products/models.py
echo ""
echo "-- 4. DB schema for products_product"
sudo -u postgres psql -d tushou -c '\d products_product' 2>&1 | grep -E 'varying|character'
echo ""
echo "-- 5. DB schema for products_category"
sudo -u postgres psql -d tushou -c '\d products_category' 2>&1 | grep -E 'varying|character'
echo ""
echo "-- 6. Services"
systemctl is-active gunicorn-tushou 2>&1
systemctl is-active nginx 2>&1
systemctl is-active postgresql 2>&1
echo ""
echo "-- 7. Applied migrations"
sudo -u deploy /home/deploy/app/.venv/bin/python /home/deploy/app/manage.py showmigrations products 2>&1 | tail -10
echo ""
echo "========== END =========="
