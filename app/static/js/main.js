// App shell: hash router, top bar, scope toggle, theme toggle, logout.
import { api } from "./api.js";
import * as loginPage from "./pages/login.js";
import * as accountsPage from "./pages/accounts.js";
import * as budgetPage from "./pages/budget.js";
import * as forecastPage from "./pages/forecast.js";
import * as goalsPage from "./pages/goals.js";
import * as homePage from "./pages/home.js";
import * as rulesPage from "./pages/rules.js";
import * as transactionsPage from "./pages/transactions.js";

const PAGES = {
  login: loginPage,
  home: homePage,
  transactions: transactionsPage,
  budget: budgetPage,
  goals: goalsPage,
  forecast: forecastPage,
  accounts: accountsPage,
  rules: rulesPage,
};

const NAV = [
  ["home", "Home", "#/home"],
  ["transactions", "Transactions", "#/transactions"],
  ["budget", "Budget", "#/budget"],
  ["goals", "Goals", "#/goals"],
  ["forecast", "Forecast", "#/forecast"],
  ["accounts", "Accounts", "#/accounts"],
  ["rules", "Rules", "#/rules"],
];

const SCOPE_LABELS = { joint: "Joint", personal: "Mine", combined: "Both" };
const THEME_KEY = "fd_theme";
const SCOPE_KEY = "fd_scope";

let user = null;

function getScope() {
  const s = localStorage.getItem(SCOPE_KEY);
  return s === "personal" || s === "combined" ? s : "joint";
}

function setScope(scope) {
  localStorage.setItem(SCOPE_KEY, scope);
  render();
}

function routeName() {
  const h = location.hash.replace(/^#\/?/, "");
  return PAGES[h] ? h : "home";
}

function applyTheme() {
  const theme = localStorage.getItem(THEME_KEY) || "dark";
  document.documentElement.dataset.theme = theme;
  const btn = document.getElementById("theme-toggle");
  if (btn) btn.textContent = theme === "dark" ? "Light" : "Dark";
}

function toggleTheme() {
  const theme = document.documentElement.dataset.theme === "light" ? "dark" : "light";
  localStorage.setItem(THEME_KEY, theme);
  applyTheme();
}

function topBar(active) {
  const bar = document.createElement("div");
  bar.className = "topbar";
  const brand = document.createElement("a");
  brand.className = "brand";
  brand.href = "#/home";
  brand.textContent = "Finance Dashboard";
  bar.appendChild(brand);

  const nav = document.createElement("nav");
  nav.className = "nav";
  for (const [name, label, href] of NAV) {
    const a = document.createElement("a");
    a.href = href;
    a.textContent = label;
    if (name === active) a.className = "active";
    nav.appendChild(a);
  }
  bar.appendChild(nav);

  const scope = getScope();
  const seg = document.createElement("div");
  seg.className = "segmented";
  for (const value of ["joint", "personal", "combined"]) {
    const b = document.createElement("button");
    b.textContent = SCOPE_LABELS[value];
    b.dataset.scope = value;
    if (value === scope) b.className = "active";
    b.addEventListener("click", () => setScope(value));
    seg.appendChild(b);
  }
  bar.appendChild(seg);

  const themeBtn = document.createElement("button");
  themeBtn.id = "theme-toggle";
  themeBtn.className = "btn";
  themeBtn.textContent = "Light";
  themeBtn.addEventListener("click", toggleTheme);
  bar.appendChild(themeBtn);

  const outBtn = document.createElement("button");
  outBtn.className = "btn";
  outBtn.textContent = "Log out";
  outBtn.addEventListener("click", async () => {
    try {
      await api("/api/logout", { method: "POST" });
    } catch {
      // not signed in; just clear
    }
    user = null;
    location.hash = "#/login";
  });
  bar.appendChild(outBtn);
  return bar;
}

async function render() {
  applyTheme();
  const name = routeName();
  const app = document.getElementById("app");
  app.innerHTML = "";

  if (name !== "login") {
    if (!user) {
      try {
        user = await api("/api/me");
      } catch {
        location.hash = "#/login";
        return;
      }
    }
    app.appendChild(topBar(name));
  }

  const page = document.createElement("main");
  page.className = "page";
  const ctx = { scope: getScope(), user };
  await PAGES[name].render(page, ctx);
  app.appendChild(page);
}

window.addEventListener("hashchange", render);
render();
