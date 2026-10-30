// Forecast page (T22): projection line chart with saving/balance inputs and horizon,
// forecast items grouped by group (add/edit/delete dialog), Home/Child starters.
import { api } from "../api.js";
import { money, date } from "../fmt.js";

let chart = null;
const MONTHS = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"];
const el = (tag, cls, text) => { const n = document.createElement(tag); if (cls) n.className = cls; if (text !== undefined) n.textContent = text; return n; };
const btn = (text, cls) => { const b = el("button", cls ? `btn ${cls}` : "btn", text); b.type = "button"; return b; };
const field = (labelText, input) => { const l = el("label", null, labelText); l.append(input); return l; };
const dollarsToCents = (text) => { const t = String(text).replace(/[$,\s]/g, ""); return /^\d+(\.\d+)?$|^\.\d+$/.test(t) ? Math.round(Number(t) * 100) : null; };
const monthLabel = (mm) => { const [y, m] = mm.split("-"); return `${MONTHS[Number(m) - 1]} '${y.slice(2)}`; };
const monthName = (iso) => { const [y, m] = iso.split("-"); return `${MONTHS[Number(m) - 1]} ${y}`; };
const cssVar = (name, fallback) => getComputedStyle(document.documentElement).getPropertyValue(name).trim() || fallback;
const isoToday = () => { const d = new Date(); return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`; };
const scopeQ = (s) => `?${new URLSearchParams({ scope: s })}`;
const sel = (pairs, value) => { const s = el("select"); for (const [v, l] of pairs) { const o = el("option", null, l); o.value = v; s.append(o); } s.value = value; return s; };

export async function render(container, ctx) {
  const scope = ctx.scope;
  if (chart) { chart.destroy(); chart = null; }
  const canCreate = scope !== "combined";

  // Inputs above chart
  const monthsSel = sel([[60, "5 years"], [120, "10 years"], [180, "15 years"]], "120");
  const monthlyIn = el("input"); monthlyIn.inputMode = "decimal";
  const startIn = el("input"); startIn.inputMode = "decimal";
  const inputsForm = el("div", "fc-inputs");
  inputsForm.append(field("Assume saving $/month", monthlyIn), field("Starting balance ($)", startIn), field("Horizon", monthsSel));
  const inputsCard = el("div", "card"); inputsCard.append(inputsForm);
  const canvas = document.createElement("canvas"); const chartWrap = el("div", "chart-wrap"); chartWrap.append(canvas);
  const verdict = el("p", "fc-verdict"); verdict.hidden = true;
  const chartCard = el("div", "card"); chartCard.append(chartWrap, verdict);

  // Events list + add dialog + starters
  const eventsHead = el("div", "card-head");
  const addBtn = btn("Add item", "primary");
  const homeBtn = btn("Home");
  const childBtn = btn("Child");
  const starterRow = el("div", "actions");
  starterRow.append(el("span", "dim", "Starters (prefill the dialog, blank amounts):"), homeBtn, childBtn);
  eventsHead.append(el("h2", null, "Forecast items"), addBtn);
  const list = el("div", "event-groups");
  const eventsCard = el("div", "card");
  eventsCard.append(eventsHead, starterRow, list);
  container.append(el("h1", null, "Forecast"), inputsCard, chartCard, eventsCard);

  addBtn.addEventListener("click", () => openDialog("add"));
  homeBtn.addEventListener("click", () => openDialog("home"));
  childBtn.addEventListener("click", () => openDialog("child"));
  for (const b of [addBtn, homeBtn, childBtn]) b.disabled = !canCreate;
  if (!canCreate) eventsCard.append(el("p", "dim", "Switch to Joint or Mine to add items"));
  for (const n of [monthlyIn, startIn, monthsSel]) n.addEventListener("change", recalc);

  let first = true;
  async function recalc() {
    const p = new URLSearchParams({ scope, months: monthsSel.value });
    const monthly = dollarsToCents(monthlyIn.value);
    const start = dollarsToCents(startIn.value);
    if (monthly != null) p.set("monthly_cents", monthly);
    if (start != null) p.set("start_balance_cents", start);
    verdict.hidden = false; verdict.className = "fc-verdict dim"; verdict.textContent = "Calculating…";
    try {
      const proj = await api(`/api/forecast/projection?${p}`);
      if (first) { monthlyIn.value = (proj.baseline_monthly_cents / 100).toFixed(2); startIn.value = (proj.start_balance_cents / 100).toFixed(2); first = false; } // defaults from API
      drawChart(proj);
      verdict.className = proj.first_negative_month ? "fc-verdict spend" : "fc-verdict income";
      verdict.textContent = proj.first_negative_month ? `Balance first goes negative in ${monthName(proj.first_negative_month)}.` : "Stays positive.";
    } catch (e) { verdict.className = "fc-verdict spend"; verdict.textContent = e.message; }
  }

  function drawChart(proj) {
    if (chart) chart.destroy();
    const dim = cssVar("--text-dim", "#9aa4b2");
    const accent = cssVar("--accent", "#5aa9ff");
    const red = cssVar("--spend", "#f87171");
    const pts = proj.points;
    chart = new Chart(canvas, {
      type: "line",
      data: {
        labels: pts.map((pt) => monthLabel(pt.month)),
        datasets: [
          { label: "Balance", data: pts.map((pt) => pt.balance_cents / 100), borderColor: accent,
            pointBackgroundColor: (c) => (c.parsed.y < 0 ? red : accent), pointRadius: 2, pointHoverRadius: 4,
            borderWidth: 2, fill: false, tension: 0.1 },
          { label: "Below zero", data: pts.map((pt) => (pt.balance_cents < 0 ? pt.balance_cents / 100 : null)),
            borderColor: red, backgroundColor: "rgba(248,113,113,0.18)", pointRadius: 0, borderWidth: 2, fill: "origin", tension: 0.1 },
        ],
      },
      options: {
        maintainAspectRatio: false,
        interaction: { mode: "index", intersect: false },
        scales: {
          x: { ticks: { color: dim, maxTicksLimit: 12, font: { size: 12 } }, grid: { display: false } },
          y: { ticks: { color: dim, callback: (v) => money(Math.round(v * 100)) } },
        },
        plugins: { legend: { display: false }, tooltip: { callbacks: { label: (c) => (c.datasetIndex === 0 ? ` Balance: ${money(c.parsed.y * 100)}` : null) } } },
      },
    });
  }

  const itemText = (e) => e.kind === "one_time"
    ? `One-time ${money(e.amount_cents)} on ${date(e.start_date)}`
    : `${money(e.amount_cents)} per ${e.frequency} from ${date(e.start_date)} to ${e.end_date ? date(e.end_date) : "ongoing"}`;

  async function loadEvents() {
    try {
      const items = await api(`/api/forecast/events${scopeQ(scope)}`);
      list.replaceChildren();
      if (!items.length) { list.append(el("p", "dim", "No forecast items yet. Add one, or use a starter.")); return; }
      const groups = {};
      for (const e of items) {
        const key = e.group_name || "No group";
        if (!groups[key]) { const g = el("div"); g.append(el("h2", null, key)); list.append(g); groups[key] = g; }
        const editBtn = btn("Edit", "small"); const delBtn = btn("Delete", "small danger");
        editBtn.addEventListener("click", () => openDialog("edit", e));
        delBtn.addEventListener("click", () => delItem(e));
        const row = el("div", "event-row");
        row.append(el("span", "event-name", e.name), el("span", `badge ${e.direction}`, e.direction),
          el("span", "event-desc", itemText(e)), editBtn, delBtn);
        groups[key].append(row);
      }
    } catch (e2) { list.replaceChildren(el("p", "error", e2.message)); }
  }

  async function delItem(e) {
    if (!confirm(`Delete “${e.name}”?`)) return;
    try { await api(`/api/forecast/events/${e.id}${scopeQ(scope)}`, { method: "DELETE" }); refreshAll(); }
    catch (e2) { list.append(el("p", "error", e2.message)); }
  }

  const refreshAll = () => { loadEvents(); recalc(); };

  function itemFields(values) {
    const f = el("div", "form-grid");
    const nameIn = el("input"); nameIn.required = true; nameIn.placeholder = "e.g. Mortgage"; nameIn.value = values.name || "";
    const groupIn = el("input"); groupIn.placeholder = "e.g. Home"; groupIn.value = values.group_name || "";
    const dirSel = sel([["expense", "expense"], ["income", "income"]], values.direction || "expense");
    const kindSel = sel([["one_time", "One-time"], ["recurring", "Recurring"]], values.kind || "one_time");
    const amountIn = el("input"); amountIn.required = true; amountIn.inputMode = "decimal"; amountIn.placeholder = "0.00";
    amountIn.value = values.amount_cents != null ? (values.amount_cents / 100).toFixed(2) : "";
    const startIn = el("input"); startIn.type = "date"; startIn.required = true; startIn.value = values.start_date || "";
    const endIn = el("input"); endIn.type = "date"; endIn.value = values.end_date || "";
    const freqSel = sel([["monthly", "monthly"], ["yearly", "yearly"]], values.frequency || "monthly");
    const endField = field("End date (recurring only)", endIn);
    const freqField = field("Frequency", freqSel);
    const syncKind = () => { const r = kindSel.value === "recurring"; endField.hidden = !r; freqField.hidden = !r; };
    kindSel.addEventListener("change", syncKind); syncKind();
    f.append(field("Name", nameIn), field("Group (free text)", groupIn), field("Type", dirSel), field("Timing", kindSel),
      field("Amount ($)", amountIn), field("Start date", startIn), endField, freqField);
    const read = () => {
      const cents = dollarsToCents(amountIn.value);
      if (!nameIn.value.trim() || cents == null || cents <= 0 || !startIn.value) return null;
      const r = kindSel.value === "recurring";
      return { name: nameIn.value.trim(), group_name: groupIn.value.trim(), direction: dirSel.value, kind: kindSel.value,
        amount_cents: cents, start_date: startIn.value, end_date: r ? endIn.value || null : null, frequency: r ? freqSel.value : null };
    };
    return { f, read };
  }

  function openDialog(mode, event = null) {
    const err = el("p", "error"); err.hidden = true;
    const cancel = btn("Cancel"); const submit = btn(mode === "edit" ? "Save changes" : "Add item", "primary"); submit.type = "submit";
    const actions = el("div", "actions"); actions.append(cancel, submit);
    const form = el("form");
    const titles = { add: "Add forecast item", home: "Home — two items", child: "Child — one item", edit: "Edit forecast item" };
    const items = mode === "home"
      ? [{ name: "Down payment", group_name: "Home", direction: "expense", kind: "one_time", start_date: isoToday() },
         { name: "Mortgage", group_name: "Home", direction: "expense", kind: "recurring", frequency: "monthly", start_date: isoToday() }]
      : mode === "child"
        ? [{ name: "Child", group_name: "Child", direction: "expense", kind: "recurring", frequency: "monthly", start_date: isoToday() }]
        : [event || {}];
    const reads = [];
    for (const v of items) {
      const { f, read } = itemFields(v); reads.push(read);
      if (items.length > 1) form.append(el("h3", null, v.name));
      form.append(f);
    }
    form.append(actions);
    const dlg = el("dialog", "dlg");
    dlg.append(el("h2", null, titles[mode]), err, form);
    dlg.addEventListener("close", () => dlg.remove());
    document.body.append(dlg); dlg.showModal(); cancel.addEventListener("click", () => dlg.close());
    form.addEventListener("submit", async (e) => {
      e.preventDefault();
      const bodies = reads.map((r) => r());
      if (bodies.some((b) => b == null)) { err.hidden = false; err.textContent = "Every item needs a name, a dollar amount above zero, and a start date."; return; }
      try {
        if (mode === "edit") await api(`/api/forecast/events/${event.id}${scopeQ(scope)}`, { method: "PATCH", body: bodies[0] });
        else for (const item of bodies) await api("/api/forecast/events", { method: "POST", body: { ...item, scope } });
        dlg.close();
        refreshAll();
      } catch (e2) { err.hidden = false; err.textContent = e2.message; }
    });
  }

  await Promise.all([recalc(), loadEvents()]);
}
