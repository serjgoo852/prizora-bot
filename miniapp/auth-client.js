(() => {
  "use strict";

  const configuredOrigin = (window.PRIZORA_AUTH_API_ORIGIN || document.querySelector('meta[name="prizora-auth-api-origin"]')?.content || "").trim();
  const API_ORIGIN = configuredOrigin.replace(/\/+$/, "");
  const API = API_ORIGIN + "/auth";
  const BOT_ENTRY_URL = "https://t.me/Prizora_GlobalBot?start=website";
  const root = document.getElementById("prizora-auth-area");
  if (!root) return;

  const status = document.createElement("p");
  status.className = "prizora-auth-status";
  status.setAttribute("role", "status");
  status.setAttribute("aria-live", "polite");

  const action = document.createElement("a");
  action.className = "prizora-auth-button";
  action.href = BOT_ENTRY_URL;
  action.target = "_blank";
  action.rel = "noopener noreferrer";
  action.textContent = "Войти через Telegram";
  action.hidden = true;

  root.append(status, action);

  const setStatus = (message) => { status.textContent = message; };
  const showLogin = () => { action.hidden = false; };
  const hideLogin = () => { action.hidden = true; };

  let browserLoginInProgress = false;
  const wait = (ms) => new Promise((resolve) => window.setTimeout(resolve, ms));

  async function startBrowserLogin(event) {
    event.preventDefault();
    if (browserLoginInProgress) return;

    // Open synchronously from the click to avoid popup blocking.
    const telegramTab = window.open("about:blank", "_blank");
    if (!telegramTab) {
      setStatus("Разрешите всплывающие окна, чтобы подтвердить вход через Telegram.");
      return;
    }

    browserLoginInProgress = true;
    action.setAttribute("aria-disabled", "true");
    setStatus("Создаём защищённый запрос на вход…");
    try {
      const createResponse = await fetch(API + "/browser/request", {
        method: "POST", credentials: "include", cache: "no-store",
        headers: { "Content-Type": "application/json", "Accept": "application/json" },
        body: "{}"
      });
      if (!createResponse.ok) throw new Error("browser_login_request_failed");
      const challenge = await createResponse.json();
      if (!challenge || !challenge.telegram_url || !challenge.request_id || !challenge.poll_secret) {
        throw new Error("invalid_browser_login_response");
      }
      telegramTab.location.href = challenge.telegram_url;
      setStatus("Подтвердите вход в открывшемся чате PRIZORA в Telegram. Ожидаем подтверждение…");

      const timeoutMs = Math.max(30, Number(challenge.expires_in) || 300) * 1000;
      const deadline = Date.now() + timeoutMs;
      while (Date.now() < deadline) {
        await wait(2000);
        const statusResponse = await fetch(API + "/browser/status", {
          method: "POST", credentials: "include", cache: "no-store",
          headers: { "Content-Type": "application/json", "Accept": "application/json" },
          body: JSON.stringify({ request_id: challenge.request_id, poll_secret: challenge.poll_secret })
        });
        if (!statusResponse.ok) throw new Error("browser_login_status_failed");
        const result = await statusResponse.json();
        if (result.status === "authenticated") {
          const session = await getCurrentSession();
          if (session && session.authenticated && session.user) {
            displayAuthenticatedUser(session.user);
            return;
          }
          throw new Error("browser_login_session_missing");
        }
        if (result.status === "expired") {
          setStatus("Срок запроса истёк. Нажмите кнопку, чтобы начать вход заново.");
          showLogin();
          return;
        }
      }
      setStatus("Время подтверждения истекло. Начните вход заново.");
      showLogin();
    } catch (_) {
      try { telegramTab.close(); } catch (_) {}
      setStatus("Не удалось выполнить вход через Telegram. Проверьте соединение и попробуйте ещё раз.");
      showLogin();
    } finally {
      browserLoginInProgress = false;
      action.removeAttribute("aria-disabled");
    }
  }

  action.addEventListener("click", startBrowserLogin);

  async function getCurrentSession() {
    const response = await fetch(API + "/me", {
      method: "GET",
      credentials: "include",
      headers: { "Accept": "application/json" },
      cache: "no-store"
    });
    if (!response.ok) throw new Error("session_check_failed");
    return response.json();
  }

  async function signInMiniApp(initData) {
    const response = await fetch(API + "/telegram/miniapp", {
      method: "POST",
      credentials: "include",
      cache: "no-store",
      headers: { "Content-Type": "application/json", "Accept": "application/json" },
      body: JSON.stringify({ init_data: initData })
    });
    if (!response.ok) {
      let detail = "";
      try {
        const payload = await response.json();
        detail = typeof payload.detail === "string" ? payload.detail : "";
      } catch (_) {}
      throw new Error(detail || "telegram_auth_failed");
    }
    return response.json();
  }

  function displayAuthenticatedUser(user) {
    hideLogin();
    const name = user && (user.display_name || user.username || user.first_name);
    setStatus(name ? "Вы вошли через Telegram: " + name : "Аккаунт Telegram подключён.");
  }

  async function initialize() {
    const telegram = window.Telegram && window.Telegram.WebApp;
    if (telegram) {
      try {
        telegram.ready();
        if (typeof telegram.expand === "function") telegram.expand();
      } catch (_) {}
    }

    // In a Mini App, always validate the current launch payload first. This
    // prevents a stale browser cookie from masking a Telegram account switch.
    const initData = telegram && typeof telegram.initData === "string"
      ? telegram.initData
      : "";

    if (initData) {
      setStatus("Проверяем ваш аккаунт Telegram…");
      hideLogin();
      try {
        await signInMiniApp(initData);
        const session = await getCurrentSession();
        if (session && session.authenticated && session.user) {
          displayAuthenticatedUser(session.user);
        } else {
          setStatus("Telegram подтвердил вход, но сессию пока не удалось прочитать.");
          showLogin();
        }
      } catch (_) {
        setStatus("Не удалось выполнить вход через Telegram. Попробуйте ещё раз.");
        showLogin();
      }
      return;
    }

    try {
      const session = await getCurrentSession();
      if (session && session.authenticated && session.user) {
        displayAuthenticatedUser(session.user);
        return;
      }
    } catch (_) {
      // The public page remains usable if the auth API is not deployed yet.
    }

    setStatus("Откройте PRIZORA через Telegram — аккаунт подключится автоматически.");
    showLogin();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initialize, { once: true });
  } else {
    initialize();
  }
})();
