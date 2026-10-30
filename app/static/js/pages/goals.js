// Goals page (T21): savings strip, goal cards with editable allocation,
// simulate (average monthly savings + ETA per goal), optional AI explain.
import { api } from "../api.js";
import { money, date } from "../fmt.js";

const MONTHS = ["January","February","March","April","May","June","July","August","September","October","November","December"];
const el = (tag, cls, text) => { const n = document.createElement(tag); if (cls) n.className = cls; if (text !== undefined) n.textContent = text; return n; };
const field = (labelText, input) => { const l = el("label", null, labelText); l.append(input); return l; };
const btn = (text, cls) => { const b = el("button", cls ? `btn ${cls}` : "btn", text); b.type = "button"; return b; };
const dollarsToCents = (text) => { const t = String(text).replace(/[$,\s]/g, ""); return /^\d+(\.\d+)?$|^\.\d+$/.test(t) ? Math.round(Number(t) * 100) : null; };
const monthName = (iso) => { const [y, m] = iso.split("-"); return `${MONTHS[Number(m) - 1]} ${y}`; };
const scopeQ = (scope) => `?${new URLSearchParams({ scope })}`;

export async function render(container, ctx) {
  const scope = ctx.scope;
  let goalNames = {};
  const stats = el("div", "stats");
  const statCards = {};
  for (const key of ["balance_cents", "allocated_cents", "unallocated_cents"]) {
    const card = el("div", "card stat"); statCards[key] = card; stats.append(card);
  }
  const addRow = el("div", "card-head");
  const addBtn = btn("Add goal", "primary");
  addBtn.addEventListener("click", openAddDialog);
  addRow.append(addBtn);
  if (scope === "combined") { addBtn.disabled = true; addRow.append(el("p", "note", "Switch to Joint or Mine to add goals")); }
  const list = el("div", "stack");
  const simCard = el("div", "card");
  container.append(el("h1", null, "Goals"), stats, addRow, list, simCard);

  function openAddDialog() {
    const err = el("p", "error"); err.hidden = true;
    const nameInput = el("input"); nameInput.required = true; nameInput.placeholder = "e.g. New car";
    const targetInput = el("input"); targetInput.required = true; targetInput.inputMode = "decimal"; targetInput.placeholder = "0.00";
    const dateInput = el("input"); dateInput.type = "date";
    const cancel = btn("Cancel");
    const submit = btn("Add goal", "primary"); submit.type = "submit";
    const actions = el("div", "actions"); actions.append(cancel, submit);
    const form = el("form");
    form.append(err, field("Name", nameInput), field("Target amount ($)", targetInput), field("Target date (optional)", dateInput), actions);
    const dlg = el("dialog", "dlg");
    dlg.append(el("h2", null, "Add goal"), form);
    dlg.addEventListener("close", () => dlg.remove());
    document.body.append(dlg); dlg.showModal();
    cancel.addEventListener("click", () => dlg.close());
    form.addEventListener("submit", async (e) => {
      e.preventDefault();
      const target = dollarsToCents(targetInput.value);
      if (target == null || target <= 0) { err.hidden = false; err.textContent = "Target amount must be a dollar amount above zero."; return; }
      try {
        await api("/api/goals", { method: "POST", body: { name: nameInput.value.trim(), target_cents: target, target_date: dateInput.value || null, scope } });
        dlg.close(); refresh();
      } catch (e2) { err.hidden = false; err.textContent = e2.message; }
    });
  }

  function goalCard(g) {
    const delBtn = btn("Delete", "small danger");
    delBtn.addEventListener("click", () => deleteGoal(g));
    const head = el("div", "card-head"); head.append(el("h2", null, g.name), delBtn);
    const pct = g.target_cents > 0 ? Math.min(100, Math.round((g.allocated_cents / g.target_cents) * 100)) : 0;
    const fill = el("div", g.allocated_cents > g.target_cents ? "fill over" : "fill"); fill.style.width = `${pct}%`;
    const bar = el("div", "progress"); bar.append(fill);
    const allocRow = el("div", "alloc-row"); allocRow.append(el("span", "alloc-label", "Allocated"), allocEditor(g));
    const card = el("div", "card goal-card");
    card.append(head, el("div", "budget-line", `${money(g.allocated_cents)} of ${money(g.target_cents)}`), bar, allocRow);
    if (g.target_date) card.append(el("p", "dim", `Target date: ${date(g.target_date)}`));
    return card;
  }

  function allocEditor(g) {
    const span = el("span", "limit-edit", money(g.allocated_cents));
    span.addEventListener("click", () => {
      const err = el("p", "error"); err.hidden = true;
      const input = el("input", "limit-input");
      input.inputMode = "decimal";
      input.value = (g.allocated_cents / 100).toFixed(2);
      span.replaceWith(input); input.after(err);
      input.focus(); input.select();
      let done = false;
      const finish = async (save) => {
        if (done) return; done = true;
        const cents = save ? dollarsToCents(input.value) : null;
        if (cents == null) { refresh(); return; } // blank or invalid: cancel
        try {
          await api(`/api/goals/${g.id}${scopeQ(scope)}`, { method: "PATCH", body: { allocated_cents: cents } });
          refresh();
        } catch (e) {
          input.replaceWith(span, err); err.hidden = false;
          err.textContent = e.message === "over_allocated" ? "That's more than you have saved for goals." : e.message;
        }
      };
      input.addEventListener("keydown", (e) => { if (e.key === "Enter") finish(true); else if (e.key === "Escape") finish(false); });
      input.addEventListener("blur", () => finish(true));
    });
    return span;
  }

  async function deleteGoal(g) {
    if (!confirm(`Delete goal “${g.name}”?`)) return;
    try { await api(`/api/goals/${g.id}${scopeQ(scope)}`, { method: "DELETE" }); refresh(); }
    catch (e) { list.append(el("p", "error", e.message)); }
  }

  // Simulate card
  const monthsSel = el("select");
  for (const m of [3, 6, 12]) { const opt = el("option", null, `${m} months of history`); opt.value = m; monthsSel.append(opt); }
  monthsSel.value = "6";
  const overrideInput = el("input"); overrideInput.inputMode = "decimal"; overrideInput.placeholder = "0.00";
  const simBtn = btn("Simulate", "primary");
  const explainBtn = btn("Explain in plain words"); explainBtn.hidden = true;
  const explainText = el("p", "sim-text");
  const simForm = el("div", "sim-form");
  simForm.append(field("History", monthsSel), field("Assume $/month (optional)", overrideInput), simBtn);
  const simHead = el("div", "card-head"); simHead.append(el("h2", null, "Simulate"));
  const simResult = el("div", "sim-result");
  simResult.append(el("p", "dim", "Click Simulate to see when each goal is reachable."));
  simCard.append(simHead, simForm, simResult);

  simBtn.addEventListener("click", async () => {
    simResult.replaceChildren(el("p", "dim", "Simulating…"));
    const params = { scope, months: Number(monthsSel.value) };
    const override = dollarsToCents(overrideInput.value);
    if (override != null) params.monthly_cents = override;
    try {
      const sim = await api(`/api/goals/simulate?${new URLSearchParams(params)}`);
      const head = el("tr");
      head.append(el("th", null, "Goal"), el("th", null, "Estimated"), el("th", null, "Status"));
      const rows = sim.goals.map((g) => {
        let status = "—";
        if (!g.eta_date) status = "Not reachable at current pace";
        else if (g.on_track === true) status = "On track";
        else if (g.on_track === false) status = "Behind target date";
        const tr = el("tr");
        tr.append(
          el("td", null, goalNames[g.id] || `Goal ${g.id}`),
          el("td", null, g.eta_date ? `Estimated: ${monthName(g.eta_date)}` : "—"),
          el("td", null, status),
        );
        return tr;
      });
      const table = el("table"); table.append(head, ...rows);
      simResult.replaceChildren(
        el("p", null, `Based on average monthly savings of ${money(sim.monthly_cents_used)}`),
        table, explainBtn, explainText,
      );
    } catch (e) { simResult.replaceChildren(el("p", "error", e.message)); }
  });

  explainBtn.addEventListener("click", async () => {
    explainBtn.disabled = true;
    explainText.hidden = false;
    explainText.textContent = "Thinking…";
    try {
      const r = await api("/api/explain", { method: "POST", body: { kind: "goals", scope } });
      explainText.textContent = r.llm_available && r.text ? r.text : "Explanation isn't available right now.";
    } catch (e) { explainText.textContent = e.message; }
    finally { explainBtn.disabled = false; }
  });

  async function refresh() {
    try {
      const [sav, goals] = await Promise.all([
        api(`/api/savings${scopeQ(scope)}`),
        api(`/api/goals${scopeQ(scope)}`),
      ]);
      goalNames = {};
      for (const g of goals) goalNames[g.id] = g.name;
      const labels = { balance_cents: "TOTAL SAVINGS", allocated_cents: "ALLOCATED TO GOALS", unallocated_cents: "UNALLOCATED" };
      for (const key of Object.keys(labels))
        statCards[key].replaceChildren(el("div", "stat-label", labels[key]), el("div", "stat-value", money(sav[key])));
      list.replaceChildren();
      if (!goals.length) list.append(el("p", "dim", "No goals yet. Add one to start tracking."));
      for (const g of goals) list.append(goalCard(g));
    } catch (e) { list.replaceChildren(el("p", "error", e.message)); }
  }

  await refresh();
}
