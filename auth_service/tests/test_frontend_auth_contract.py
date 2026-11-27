from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_miniapp_homepage_exposes_telegram_login_entry_point():
    html = (ROOT / "miniapp" / "index.html").read_text(encoding="utf-8")
    assert 'id="prizora-auth-area"' in html
    assert 'https://telegram.org/js/telegram-web-app.js' in html
    assert 'src="/auth-client.js"' in html


def test_auth_client_posts_raw_init_data_and_uses_server_session():
    client = (ROOT / "miniapp" / "auth-client.js").read_text(encoding="utf-8")
    assert 'telegram.initData' in client
    assert 'init_data: initData' in client
    assert 'credentials: "same-origin"' in client
    assert 'API + "/me"' in client
    assert 'API + "/telegram/start"' in client
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
