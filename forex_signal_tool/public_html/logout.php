<?php
require_once __DIR__ . '/_user_config.php';
logout_user();
header('Location: /');
exit;
