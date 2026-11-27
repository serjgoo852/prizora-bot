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
  action.textContent = "Открыть PRIZORA в Telegram";
  action.hidden = true;

  root.append(status, action);

  const setStatus = (message) => { status.textContent = message; };
  const showLogin = () => { action.hidden = false; };
  const hideLogin = () => { action.hidden = true; };

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
      credentials: "same-origin",
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
