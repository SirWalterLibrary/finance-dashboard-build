// Home page (T19): range buttons, stat cards, category doughnut / month bars, category-filtered transactions.
import { api } from "../api.js";
import { money, date } from "../fmt.js";

let charts = [];
const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

function destroyCharts() {
  for (const c of charts) c.destroy();
  charts = [];
}

function el(tag, cls, text) {
  const n = document.createElement(tag);
  if (cls) n.className = cls;
  if (text !== undefined) n.textContent = text;
  return n;
}

function cssVar(name, fallback) {
  return getComputedStyle(document.documentElement).getPropertyValue(name).trim() || fallback;
}

function iso(d) {
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}

function rangeFrom(key) {
  const now = new Date();
  const first = (mm) => iso(new Date(now.getFullYear(), mm, 1));
  if (key === "1M") return first(now.getMonth());
  if (key === "3M") return first(now.getMonth() - 2);
  if (key === "6M") return first(now.getMonth() - 5);
  if (key === "YTD") return first(0);
  return null;
}

function mLabel(month) {
  const [y, m] = month.split("-");
  return `${MONTHS[Number(m) - 1]} '${y.slice(2)}`;
}

function categoryItems(list) {
  if (list.length <= 8) return list;
  const rest = list.slice(8);
  return [
    ...list.slice(0, 8),
    { name: "Other", cents: rest.reduce((s, r) => s + r.cents, 0), pct: rest.reduce((s, r) => s + (r.pct || 0), 0), color: "#888888" },
  ];
}

const TOOLTIP = { callbacks: { label: (c) => ` ${c.dataset.label ?? c.label}: ${money(c.parsed.y ?? c.parsed)}` } };

export async function render(container, ctx) {
  destroyCharts();
  const scope = ctx.scope;
  const state = { range: "6M", from: "", to: "", view: "category", catId: 0, catName: "" };
  let summary = null;
  const canvas = document.createElement("canvas");

  container.append(el("h1", null, "Home"));

  // Range bar
  const bar = el("div", "card range-bar");
  const seg = el("div", "segmented");
  const rangeBtns = {};
  const customWrap = el("div", "range-custom");
  const fromIn = el("input"); fromIn.type = "date";
  const toIn = el("input"); toIn.type = "date";
  for (const inp of [fromIn, toIn])
    inp.addEventListener("change", () => {
      state.from = fromIn.value;
      state.to = toIn.value;
      if (state.range === "Custom") refresh();
    });
  for (const r of ["1M", "3M", "6M", "YTD", "ALL", "Custom"]) {
    const b = el("button", r === state.range ? "active" : null, r);
    b.type = "button";
    b.addEventListener("click", () => {
      state.range = r;
      for (const k of Object.keys(rangeBtns)) rangeBtns[k].classList.toggle("active", k === r);
      customWrap.hidden = r !== "Custom";
      refresh();
    });
    rangeBtns[r] = b;
    seg.append(b);
  }
  customWrap.hidden = true;
  customWrap.append(el("label", null, "From"), fromIn, el("label", null, "To"), toIn);
  bar.append(seg, customWrap);

  // Stat cards
  const stats = el("div", "stats");
  const cards = {};
  for (const key of ["income", "spending", "net", "saved"]) {
    cards[key] = el("div", "card stat");
    stats.append(cards[key]);
  }
  const review = el("p", "review-link");
  review.hidden = true;

  // Chart + breakdown grid
  const grid = el("div", "home-grid");
  const viewSeg = el("div", "segmented view-seg");
  const viewBtns = {};
  for (const [v, label] of [["category", "By category"], ["month", "By month"]]) {
    const b = el("button", v === state.view ? "active" : null, label);
    b.type = "button";
    b.addEventListener("click", () => {
      state.view = v;
      for (const k of ["category", "month"]) viewBtns[k].classList.toggle("active", k === v);
      if (summary) drawCharts(); else refresh();
    });
    viewBtns[v] = b;
    viewSeg.append(b);
  }
  const left = el("div", "card");
  const chartWrap = el("div", "chart-wrap");
  chartWrap.append(canvas);
  left.append(viewSeg, chartWrap);
  const right = el("div", "card");
  const rightHead = el("h2", null, "Spending by category");
  const table = el("table");
  right.append(rightHead, table);
  grid.append(left, right);
  const txCard = el("div", "card");
  txCard.hidden = true;

  container.append(bar, stats, review, grid, txCard);

  function summaryParams() {
    const p = new URLSearchParams({ scope });
    if (state.range === "Custom") {
      if (state.from) p.set("from", state.from);
      if (state.to) p.set("to", state.to);
    } else {
      const f = rangeFrom(state.range);
      if (f) p.set("from", f);
    }
    return p.toString();
  }

  async function refresh() {
    try {
      summary = await api(`/api/summary?${summaryParams()}`);
    } catch (err) {
      stats.replaceChildren(el("p", "error", err.message));
      return;
    }
    renderStats();
    drawCharts();
    renderBreakdown();
    if (state.catId) loadTx(); else txCard.hidden = true;
  }

  function renderStats() {
    cards.income.replaceChildren(el("div", "stat-label", "INCOME"), el("div", "stat-value income", money(summary.income_cents)));
    const subs = summary.reimbursed_cents > 0 ? [el("div", "stat-sub", `after ${money(summary.reimbursed_cents)} work reimbursements`)] : [];
    cards.spending.replaceChildren(el("div", "stat-label", "SPENDING"), el("div", "stat-value spend", money(summary.spending_cents)), ...subs);
    cards.net.replaceChildren(el("div", "stat-label", "NET"), el("div", summary.net_cents >= 0 ? "stat-value income" : "stat-value spend", money(summary.net_cents)));
    cards.saved.replaceChildren(el("div", "stat-label", "SAVED TO SAVINGS"), el("div", "stat-value", money(summary.saved_cents)));
    review.hidden = summary.uncategorized_count <= 0;
    if (summary.uncategorized_count > 0) {
      const a = el("a", null, `${summary.uncategorized_count} uncategorized — Review`);
      a.href = "#/transactions";
      review.replaceChildren(a);
    }
  }

  function drawCharts() {
    destroyCharts();
    const dim = cssVar("--text-dim", "#9aa4b2");
    const legend = { position: "bottom", labels: { color: dim, boxWidth: 12 } };
    if (state.view === "category") {
      const items = categoryItems(summary.by_category);
      charts.push(new Chart(canvas, {
        type: "doughnut",
        data: {
          labels: items.map((i) => i.name),
          datasets: [{ data: items.map((i) => i.cents), backgroundColor: items.map((i) => i.color || "#888888"), borderWidth: 0 }],
        },
        options: { maintainAspectRatio: false, cutout: "60%", plugins: { legend, tooltip: TOOLTIP } },
      }));
      rightHead.textContent = "Spending by category";
      return;
    }
    const months = summary.by_month;
    const totals = {};
    for (const m of months) for (const [n, cents] of Object.entries(m.by_category)) totals[n] = (totals[n] || 0) + cents;
    const top = Object.keys(totals).sort((a, b) => totals[b] - totals[a]).slice(0, 8);
    const colorOf = {};
    for (const c of summary.by_category) colorOf[c.name] = c.color;
    const restNames = Object.keys(totals).filter((n) => !top.includes(n));
    const datasets = top.map((n) => ({ label: n, data: months.map((m) => m.by_category[n] || 0), backgroundColor: colorOf[n] || "#888888" }));
    if (restNames.length)
      datasets.push({ label: "Other", data: months.map((m) => restNames.reduce((s, n) => s + (m.by_category[n] || 0), 0)), backgroundColor: "#888888" });
    datasets.push({
      type: "line", label: "Income", data: months.map((m) => m.income_cents), yAxisID: "y1",
      borderColor: cssVar("--income", "#4ade80"), backgroundColor: cssVar("--income", "#4ade80"), pointRadius: 3,
    });
    charts.push(new Chart(canvas, {
      type: "bar",
      data: { labels: months.map((m) => mLabel(m.month)), datasets },
      options: {
        maintainAspectRatio: false,
        scales: {
          x: { stacked: true, ticks: { color: dim } },
          y: { stacked: true, ticks: { color: dim, callback: (v) => money(v) } },
          y1: { position: "right", ticks: { color: dim, callback: (v) => money(v) }, grid: { drawOnChartArea: false } },
        },
        plugins: { legend, tooltip: TOOLTIP },
      },
    }));
    rightHead.textContent = "By month";
  }

  function renderBreakdown() {
    table.replaceChildren();
    if (state.view === "month") {
      const head = el("tr");
      for (const h of ["Month", "Income", "Spending"]) head.append(el("th", null, h));
      const rows = summary.by_month.map((m) => {
        const tr = el("tr");
        tr.append(el("td", null, mLabel(m.month)), el("td", "num income", money(m.income_cents)), el("td", "num spend", money(m.spending_cents)));
        return tr;
      });
      table.append(head, ...rows);
      return;
    }
    const items = categoryItems(summary.by_category);
    const head = el("tr");
    head.append(el("th"), el("th", null, "Category"), el("th", null, "Amount"), el("th", null, "%"));
    const rows = items.map((it) => {
      const tr = el("tr", it.category_id ? "clickable" : null);
      if (it.category_id)
        tr.addEventListener("click", () => { state.catId = it.category_id; state.catName = it.name; loadTx(); });
      const dot = el("span", "dot");
      dot.style.background = it.color || "#888888";
      const dotTd = el("td");
      dotTd.append(dot);
      tr.append(dotTd, el("td", null, it.name), el("td", "num", money(it.cents)), el("td", "num", `${it.pct}%`));
      return tr;
    });
    table.append(head, ...rows);
  }

  async function loadTx() {
    const p = new URLSearchParams(summaryParams());
    p.set("category_id", String(state.catId));
    p.set("limit", "50");
    p.set("offset", "0");
    txCard.hidden = false;
    const head = el("div", "card-head");
    head.append(el("h2", null, `Transactions — ${state.catName}`));
    const clear = el("a", null, "Clear");
    clear.href = "#";
    clear.addEventListener("click", (e) => {
      e.preventDefault();
      state.catId = 0;
      state.catName = "";
      txCard.hidden = true;
    });
    head.append(clear);
    txCard.replaceChildren(head);
    try {
      const data = await api(`/api/transactions?${p}`);
      if (!data.items.length) {
        txCard.append(el("p", "dim", "No transactions in this category for this range."));
        return;
      }
      const t = el("table");
      const headRow = el("tr");
      for (const h of ["Date", "Description", "Account", "Amount"]) headRow.append(el("th", null, h));
      const rows = data.items.map((tx) => {
        const tr = el("tr");
        const desc = el("td", "desc", tx.description);
        desc.title = tx.description;
        tr.append(el("td", null, date(tx.date)), desc, el("td", null, tx.account_name), el("td", `num ${tx.amount_cents > 0 ? "income" : "spend"}`, money(tx.amount_cents)));
        return tr;
      });
      t.append(headRow, ...rows);
      txCard.append(t);
      if (data.total > data.items.length) txCard.append(el("p", "dim", `First 50 of ${data.total}.`));
    } catch (err) {
      txCard.append(el("p", "error", err.message));
    }
  }

  await refresh();
}
