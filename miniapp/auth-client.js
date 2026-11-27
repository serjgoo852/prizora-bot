(() => {
  "use strict";

  const configuredOrigin = (window.PRIZORA_AUTH_API_ORIGIN || document.querySelector('meta[name="prizora-auth-api-origin"]')?.content || "").trim();
  const API_ORIGIN = configuredOrigin.replace(/\/+$/, "");
  const API = API_ORIGIN + "/auth";
  const DATA_API = API_ORIGIN + "/api";
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
  const wait = (ms) => new Promise((resolve) => window.setTimeout(resolve, ms));
  let browserLoginInProgress = false;

  async function apiGet(path) {
    const response = await fetch(API_ORIGIN + path, {
      method: "GET", credentials: "include", cache: "no-store",
      headers: { "Accept": "application/json" }
    });
    if (!response.ok) throw new Error("api_get_failed_" + response.status);
    return response.json();
  }

  function money(kopecks) {
    const amount = Number(kopecks || 0) / 100;
    return new Intl.NumberFormat("ru-RU", { style: "currency", currency: "RUB", maximumFractionDigits: 2 }).format(amount);
  }

  function makeLine(title, value) {
    const line = document.createElement("p");
    line.style.margin = "7px 0";
    const strong = document.createElement("strong");
    strong.textContent = title + ": ";
    line.append(strong, document.createTextNode(String(value ?? "—")));
    return line;
  }

  function renderList(container, items, emptyText, titleFor, detailFor) {
    container.replaceChildren();
    if (!Array.isArray(items) || !items.length) {
      const empty = document.createElement("p");
      empty.textContent = emptyText;
      container.append(empty);
      return;
    }
    const list = document.createElement("div");
    list.style.display = "grid";
    list.style.gap = "9px";
    items.forEach((item) => {
      const card = document.createElement("article");
      card.style.cssText = "padding:11px;border:1px solid #765321;border-radius:11px;background:#120e08";
      const heading = document.createElement("strong");
      heading.style.color = "#ffdc83";
      heading.textContent = titleFor(item);
      card.append(heading);
      const detail = document.createElement("p");
      detail.style.cssText = "margin:5px 0 0;color:#c9bda7;font-size:12px;line-height:1.5";
      detail.textContent = detailFor(item);
      card.append(detail);
      list.append(card);
    });
    container.append(list);
  }

  function renderCabinet(data) {
    const menu = document.getElementById("menu");
    const profilePanel = document.getElementById("user-stats");
    const contestsPanel = document.getElementById("user-contests");
    const walletPanel = document.getElementById("user-wallet");
    const adsPanel = document.getElementById("user-ads");
    const supportPanel = document.getElementById("user-support");
    if (!data || !data.profile) return;

    const profile = data.profile;
    const name = profile.display_name || profile.username || ("ID " + profile.telegram_id);
    const balance = money(data.wallet && data.wallet.balance_kopecks);
    if (menu) {
      menu.dataset.authenticated = "true";
      const heading = menu.querySelector(".section-head h2");
      if (heading) heading.textContent = "Личный кабинет · " + name;
    }
    if (profilePanel) {
      profilePanel.replaceChildren();
      const heading = document.createElement("h3");
      heading.textContent = "Профиль и статистика";
      profilePanel.append(heading);
      profilePanel.append(
        makeLine("Telegram ID", profile.telegram_id || profile.user_id),
        makeLine("Имя", name),
        makeLine("Баланс", balance),
        makeLine("Создано конкурсов", (data.my_contests || []).length),
        makeLine("Участий", (data.joined_contests || []).length)
      );
    }
    if (contestsPanel) {
      const heading = document.createElement("h3");
      heading.textContent = "Мои конкурсы и участия";
      const mine = document.createElement("div");
      renderList(mine, data.my_contests, "Вы ещё не создавали конкурсы.", x => x.prize_name || "Конкурс", x => "Формат: " + (x.contest_format || "—") + " · Участников: " + (x.participant_count ?? 0) + " · Статус: " + (x.drawn_at ? "Завершён" : "Активен"));
      const joinedHeading = document.createElement("h3");
      joinedHeading.style.marginTop = "18px";
      joinedHeading.textContent = "Мои участия";
      const joined = document.createElement("div");
      renderList(joined, data.joined_contests, "Вы пока не участвуете в конкурсах.", x => x.prize_name || "Конкурс", x => "Формат: " + (x.contest_format || "—") + " · Дата участия: " + (x.joined_at || "—") + " · " + (x.drawn_at ? "Розыгрыш завершён" : "Ожидает результата"));
      contestsPanel.replaceChildren(heading, mine, joinedHeading, joined);
    }
    if (walletPanel) {
      walletPanel.replaceChildren();
      const heading = document.createElement("h3");
      heading.textContent = "Баланс и кошелёк";
      walletPanel.append(heading, makeLine("Текущий баланс", balance));
      const note = document.createElement("p");
      note.textContent = "Здесь отображается баланс из общей базы PRIZORA. Операции пополнения и оплаты через сайт пока не включены.";
      walletPanel.append(note);
      const historyHeading = document.createElement("h3");
      historyHeading.style.marginTop = "18px";
      historyHeading.textContent = "Последние операции";
      const history = document.createElement("div");
      walletPanel.append(historyHeading, history);
      apiGet("/api/wallet/transactions?limit=10").then(result => {
        renderList(history, result.transactions, "История операций пока пуста.", x => money(x.amount_kopecks) + " · " + (x.reason || "Операция"), x => "После операции: " + money(x.balance_after_kopecks) + " · " + (x.created_at || ""));
      }).catch(() => {
        history.textContent = "Не удалось загрузить историю операций.";
      });
    }
    if (adsPanel) {
      const existing = adsPanel.querySelector(".ad-cabinet-grid");
      if (existing) {
        const heading = document.createElement("h3");
        heading.textContent = "Мои рекламные кампании";
        const campaigns = document.createElement("div");
        renderList(campaigns, data.ad_campaigns, "Рекламных кампаний пока нет.", x => x.title || "Рекламная кампания", x => "Статус: " + (x.status || "—") + " · Срок: " + (x.requested_days || "—") + " дн.");
        existing.replaceWith(heading, campaigns);
      }
    }
    if (supportPanel) {
      supportPanel.replaceChildren();
      const heading = document.createElement("h3");
      heading.textContent = "Поддержка";
      supportPanel.append(heading);
      if (data.support) {
        supportPanel.append(makeLine("Статус обращения", data.support.status), makeLine("Непрочитанных сообщений", data.support.unread_count || 0));
        if (data.support.last_message_preview) supportPanel.append(makeLine("Последнее сообщение", data.support.last_message_preview));
      } else {
        const empty = document.createElement("p");
        empty.textContent = "Активных обращений в поддержку нет.";
        supportPanel.append(empty);
      }
    }
  }

  async function loadCabinet() {
    try {
      const data = await apiGet("/api/cabinet");
      renderCabinet(data);
    } catch (_) {
      setStatus("Аккаунт подключён, но данные кабинета пока не загрузились.");
    }
  }

  async function getCurrentSession() {
    const response = await fetch(API + "/me", {
      method: "GET", credentials: "include", cache: "no-store",
      headers: { "Accept": "application/json" }
    });
    if (!response.ok) throw new Error("session_check_failed");
    return response.json();
  }

  function displayAuthenticatedUser(user) {
    hideLogin();
    const name = user && (user.display_name || user.username || user.first_name);
    setStatus(name ? "Вы вошли через Telegram: " + name : "Аккаунт Telegram подключён.");
    loadCabinet();
  }

  async function signInMiniApp(initData) {
    const response = await fetch(API + "/telegram/miniapp", {
      method: "POST", credentials: "include", cache: "no-store",
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

  async function startBrowserLogin(event) {
    event.preventDefault();
    if (browserLoginInProgress) return;
    const telegramTab = window.open("about:blank", "_blank");
    if (!telegramTab) {
      setStatus("Разрешите всплывающие окна, чтобы подтвердить вход через Telegram.");
      return;
    }
    browserLoginInProgress = true;
    action.setAttribute("aria-disabled", "true");
    setStatus("Создаём защищённый запрос на вход…");
    try {
      const response = await fetch(API + "/browser/request", {
        method: "POST", credentials: "include", cache: "no-store",
        headers: { "Content-Type": "application/json", "Accept": "application/json" },
        body: "{}"
      });
      if (!response.ok) throw new Error("browser_login_request_failed");
      const challenge = await response.json();
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

  async function initialize() {
    const telegram = window.Telegram && window.Telegram.WebApp;
    if (telegram) {
      try { telegram.ready(); if (typeof telegram.expand === "function") telegram.expand(); } catch (_) {}
    }
    const initData = telegram && typeof telegram.initData === "string" ? telegram.initData : "";
    if (initData) {
      setStatus("Проверяем ваш аккаунт Telegram…");
      hideLogin();
      try {
        await signInMiniApp(initData);
        const session = await getCurrentSession();
        if (session && session.authenticated && session.user) displayAuthenticatedUser(session.user);
        else { setStatus("Telegram подтвердил вход, но сессию пока не удалось прочитать."); showLogin(); }
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
    } catch (_) {}
    setStatus("Откройте PRIZORA через Telegram — аккаунт подключится автоматически.");
    showLogin();
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", initialize, { once: true });
  else initialize();
})();