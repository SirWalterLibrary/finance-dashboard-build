// Budget page (T20): month picker, per-category budget bars, inline limit editing.
import { api } from "../api.js";
import { money } from "../fmt.js";

const MONTHS = [
  "January", "February", "March", "April", "May", "June",
  "July", "August", "September", "October", "November", "December",
];

function el(tag, cls, text) {
  const n = document.createElement(tag);
  if (cls) n.className = cls;
  if (text !== undefined) n.textContent = text;
  return n;
}

function curMonth() {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}`;
}

function shiftMonth(month, delta) {
  const [y, m] = month.split("-").map(Number);
  const d = new Date(y, m - 1 + delta, 1);
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}`;
}

function monthLabel(month) {
  const [y, m] = month.split("-");
  return `${MONTHS[Number(m) - 1]} ${y}`;
}

function dollarsToCents(text) {
  const t = String(text).replace(/[$,\s]/g, "");
  if (!/^\d+(\.\d+)?$|^\.\d+$/.test(t)) return null;
  return Math.round(Number(t) * 100);
}

export async function render(container, ctx) {
  const scope = ctx.scope;
  const readOnly = scope === "combined";
  let month = curMonth();
  let catIds = {};
  let rows = [];

  // Month picker
  const monthBar = el("div", "card month-bar");
  const prevBtn = el("button", "btn month-nav", "←");
  const nextBtn = el("button", "btn month-nav", "→");
  prevBtn.type = "button";
  nextBtn.type = "button";
  const label = el("h2", null, monthLabel(month));
  monthBar.append(prevBtn, label, nextBtn);
  if (readOnly) monthBar.append(el("p", "note", "Switch to Joint or Mine to edit"));

  // Top summary
  const summary = el("div", "stats");
  const budgetedCard = el("div", "card stat");
  const spentCard = el("div", "card stat");
  summary.append(budgetedCard, spentCard);

  // Budget rows
  const tableCard = el("div", "card");
  const table = el("table");
  tableCard.append(table);

  container.append(el("h1", null, "Budget"), monthBar, summary, tableCard);

  prevBtn.addEventListener("click", () => { month = shiftMonth(month, -1); refresh(); });
  nextBtn.addEventListener("click", () => { month = shiftMonth(month, 1); refresh(); });

  function renderSummary() {
    const limit = rows.reduce((s, r) => s + r.limit_cents, 0);
    const spent = rows.reduce((s, r) => s + r.spent_cents, 0);
    budgetedCard.replaceChildren(
      el("div", "stat-label", "BUDGETED"),
      el("div", "stat-value", money(limit)),
    );
    spentCard.replaceChildren(
      el("div", "stat-label", "SPENT"),
      el("div", spent > limit ? "stat-value spend" : "stat-value", money(spent)),
    );
  }

  function rowEl(row) {
    const tr = el("tr");
    tr.append(el("td", null, row.name));
    const cell = el("td", "budget-cell");
    cell.append(el("div", "budget-line", row.limit_cents > 0
      ? `${money(row.spent_cents)} of ${money(row.limit_cents)}`
      : money(row.spent_cents)));
    const bar = el("div", "progress");
    const fill = el("div", row.status === "over" ? "fill over" : row.status === "warn" ? "fill warn" : "fill");
    fill.style.width = `${Math.min(100, Math.max(0, row.pct))}%`;
    bar.append(fill);
    cell.append(bar);
    if (row.status === "over")
      cell.append(el("div", "over", `Over by ${money(row.spent_cents - row.limit_cents)}`));
    tr.append(cell, limitCell(row));
    return tr;
  }

  function limitCell(row) {
    const td = el("td", "num");
    if (readOnly) {
      td.append(el("span", null, row.limit_cents > 0 ? money(row.limit_cents) : "—"));
      return td;
    }
    if (row.id != null) {
      const span = el("span", "limit-edit", row.limit_cents > 0 ? money(row.limit_cents) : "No limit");
      span.addEventListener("click", () => startEdit(span, row));
      td.append(span);
    } else {
      const btn = el("button", "btn small limit-set", "Set budget");
      btn.type = "button";
      btn.addEventListener("click", () => startEdit(btn, row));
      td.append(btn);
    }
    return td;
  }

  function startEdit(anchor, row) {
    const catId = catIds[row.name];
    if (catId == null) return;
    const input = el("input");
    input.type = "text";
    input.inputMode = "decimal";
    input.className = "limit-input";
    input.value = row.limit_cents > 0 ? (row.limit_cents / 100).toFixed(2) : "";
    input.placeholder = "0.00";
    anchor.replaceWith(input);
    input.focus();
    input.select();
    let done = false;
    const finish = (save) => {
      if (done) return;
      done = true;
      if (save) {
        const cents = dollarsToCents(input.value);
        if (cents != null) {
          api("/api/budgets", { method: "PUT", body: { scope, category_id: catId, limit_cents: cents } })
            .then(() => refresh())
            .catch(async (err) => {
              await refresh();
              tableCard.append(el("p", "error", err.message));
            });
          return;
        }
      }
      refresh(); // blank or invalid input: cancel
    };
    input.addEventListener("keydown", (e) => {
      if (e.key === "Enter") finish(true);
      else if (e.key === "Escape") finish(false);
    });
    input.addEventListener("blur", () => finish(true));
  }

  function renderTable() {
    table.replaceChildren();
    if (!rows.length) {
      tableCard.append(el("p", "dim", "No budgets or spending for this month."));
      return;
    }
    const head = el("tr");
    head.append(el("th", null, "Category"), el("th", null, "Spent / limit"), el("th", "num", "Budget"));
    for (const row of rows) table.append(head, rowEl(row));
  }

  async function refresh() {
    try {
      const [b, cats] = await Promise.all([
        api(`/api/budgets?${new URLSearchParams({ scope, month })}`),
        api("/api/categories"),
      ]);
      rows = b;
      catIds = {};
      for (const c of cats) catIds[c.name] = c.id;
      label.textContent = monthLabel(month);
      renderSummary();
      tableCard.replaceChildren(table);
      renderTable();
    } catch (err) {
      tableCard.replaceChildren(el("p", "error", err.message));
    }
  }

  await refresh();
}
