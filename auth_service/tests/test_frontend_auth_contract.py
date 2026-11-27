from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_miniapp_homepage_exposes_telegram_login_entry_point():
    html = (ROOT / "miniapp" / "index.html").read_text(encoding="utf-8")
    assert 'id="prizora-auth-area"' in html
    assert 'https://telegram.org/js/telegram-web-app.js' in html
    assert 'src="/auth-client.js"' in html
    assert 'name="prizora-auth-api-origin"' in html


def test_auth_client_posts_raw_init_data_and_uses_server_session():
    client = (ROOT / "miniapp" / "auth-client.js").read_text(encoding="utf-8")
    assert 'telegram.initData' in client
    assert 'init_data: initData' in client
    assert 'credentials: "include"' in client
    assert 'API + "/me"' in client
    assert 'BOT_ENTRY_URL' in client
    assert 'https://t.me/Prizora_GlobalBot?start=website' in client
    assert "initDataUnsafe" not in client
    assert "localStorage" not in client
    assert "sessionStorage" not in client


def test_miniapp_docker_image_includes_auth_client():
    dockerfile = (ROOT / "miniapp" / "Dockerfile").read_text(encoding="utf-8")
    assert "COPY auth-client.js /usr/share/nginx/html/auth-client.js" in dockerfile

def test_cabinet_preview_requires_shared_telegram_session():
    cabinet = (ROOT / "cabinet-demo" / "index.html").read_text(encoding="utf-8")
    assert 'id="prizora-cabinet-auth-gate"' in cabinet
    assert 'credentials: "include"' in cabinet
    assert 'AUTH_API + "/me"' in cabinet
    assert 'telegramAccountLabel' in cabinet
    assert 'localStorage' not in cabinet[cabinet.find('<script id="prizora-cabinet-auth">'):]

def test_homepage_container_does_not_bundle_a_second_auth_database():
    dockerfile = (ROOT / "miniapp" / "Dockerfile").read_text(encoding="utf-8")
    assert "COPY auth_service" not in dockerfile
    assert "DATABASE_URL" not in dockerfile


def test_homepage_container_is_static_and_healthcheck_is_local():
    dockerfile = (ROOT / "miniapp" / "Dockerfile").read_text(encoding="utf-8")
    nginx = (ROOT / "miniapp" / "nginx.conf").read_text(encoding="utf-8")
    assert "FROM nginx:" in dockerfile
    assert 'CMD ["nginx", "-g", "daemon off;"]' in dockerfile
    assert "location = /healthz" in nginx
    assert 'return 200 "ok";' in nginx
    assert "location ^~ /auth/" not in nginx

def test_cabinet_profile_uses_verified_telegram_identity_not_demo_ids():
    cabinet = (ROOT / "cabinet-demo" / "index.html").read_text(encoding="utf-8")
    assert 'telegramUsername:""' in cabinet
    assert 'state.telegramUsername = user.username' in cabinet
    assert 'esc(state.telegramUsername||"Подключён")' in cabinet
    assert 'value="100245"' not in cabinet
    assert '@demo_user' not in cabinet
    assert 'Telegram ID: ' not in cabinet
