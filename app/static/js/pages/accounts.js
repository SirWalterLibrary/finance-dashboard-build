// Accounts page: list cards, add, CSV import, set balance, delete.
import { api } from "../api.js";
import { money } from "../fmt.js";

const prompted = new Set(); // account ids that already got the balance prompt

function dollarsToCents(text) {
  const s = String(text).trim().replace(/[$,\s]/g, "");
  if (s === "" || !isFinite(Number(s))) return null;
  return Math.round(Number(s) * 100);
}

function badge(text, cls) {
  const s = document.createElement("span");
  s.className = cls ? `badge ${cls}` : "badge";
  s.textContent = text;
  return s;
}

function btn(text, cls) {
  const b = document.createElement("button");
  b.type = "button";
  b.className = cls ? `btn ${cls}` : "btn";
  b.textContent = text;
  return b;
}

function field(labelText, { required, placeholder, inputmode } = {}) {
  const label = document.createElement("label");
  const input = document.createElement("input");
  if (required) input.required = true;
  if (placeholder) input.placeholder = placeholder;
  if (inputmode) input.inputMode = inputmode;
  label.append(labelText, input);
  return label;
}

function dialog(title, body) {
  const dlg = document.createElement("dialog");
  dlg.className = "dlg";
  const h2 = document.createElement("h2");
  h2.textContent = title;
  dlg.append(h2, body);
  dlg.addEventListener("close", () => dlg.remove());
  document.body.append(dlg);
  dlg.showModal();
  return dlg;
}

function errorList(errors) {
  const details = document.createElement("details");
  const summary = document.createElement("summary");
  summary.textContent = `Import problems (${errors.length})`;
  const ul = document.createElement("ul");
  for (const e of errors) {
    const li = document.createElement("li");
    li.textContent = e;
    ul.append(li);
  }
  details.append(summary, ul);
  return details;
}

export async function render(container, ctx) {
  const scope = ctx.scope;
  const h1 = document.createElement("h1");
  h1.textContent = "Accounts";
  const addBtn = btn("Add account", "primary");
  const list = document.createElement("div");
  list.className = "stack";
  list.style.marginTop = "24px";
  container.append(h1, addBtn, list);

  function setStatus(el, text) {
    el.hidden = false;
    el.textContent = text;
  }

  async function refresh() {
    list.innerHTML = "";
    let accounts = [];
    try {
      accounts = await api(`/api/accounts?scope=${scope}`);
    } catch (err) {
      const p = document.createElement("p");
      p.className = "error";
      p.textContent = err.message;
      list.append(p);
      return;
    }
    if (!accounts.length) {
      const card = document.createElement("div");
      card.className = "card";
      const p = document.createElement("p");
      p.textContent =
        "No accounts here yet. First add an account (checking, savings, or credit card), " +
        "then import a CSV export from your bank, and finally tell the dashboard what " +
        "the account's balance is today.";
      card.append(p);
      list.append(card);
      return;
    }
    for (const a of accounts) list.append(accountCard(a));
  }

  function accountCard(a) {
    const el = document.createElement("div");
    el.className = "card";
    const head = document.createElement("div");
    head.className = "account-head";
    const h2 = document.createElement("h2");
    h2.textContent = a.name;
    head.append(
      h2,
      badge(a.type),
      badge(a.shared ? "Joint" : "Personal", a.shared ? "joint" : "personal"),
    );
    el.append(head);

    const meta = document.createElement("p");
    meta.className = "dim";
    meta.textContent = [a.institution, money(a.balance_cents), `${a.tx_count} transactions`]
      .filter(Boolean)
      .join(" · ");
    el.append(meta);

    const status = document.createElement("div");
    status.className = "result";
    status.hidden = true;
    el.append(status);

    const actions = document.createElement("div");
    actions.className = "actions";

    const file = document.createElement("input");
    file.type = "file";
    file.accept = ".csv,.tsv";
    file.hidden = true;
    file.addEventListener("change", () => runImport(a, file, status));
    const importBtn = btn("Import CSV");
    importBtn.addEventListener("click", () => file.click());
    const balBtn = btn("Set balance");
    balBtn.addEventListener("click", () => showBalanceDialog(a));
    const delBtn = btn("Delete", "danger");
    delBtn.addEventListener("click", async () => {
      if (!confirm(`Delete "${a.name}" and all of its transactions?`)) return;
      try {
        await api(`/api/accounts/${a.id}`, { method: "DELETE" });
        await refresh();
      } catch (err) {
        setStatus(status, err.message);
      }
    });
    actions.append(file, importBtn, balBtn, delBtn);
    el.append(actions);
    return el;
  }

  async function runImport(a, file, status) {
    const f = file.files[0];
    if (!f) return;
    const form = new FormData();
    form.append("file", f);
    file.value = "";
    setStatus(status, `Importing ${f.name}…`);
    try {
      const data = await api(`/api/accounts/${a.id}/import`, {
        method: "POST",
        formData: form,
      });
      status.hidden = false;
      status.innerHTML = "";
      const p = document.createElement("p");
      p.textContent =
        `Added ${data.added} new transactions, skipped ${data.skipped_duplicates} duplicates.` +
        (data.skipped_pending > 0
          ? ` Skipped ${data.skipped_pending} pending transactions.`
          : "");
      status.append(p);
      if (data.errors && data.errors.length) status.append(errorList(data.errors));
      const catBtn = btn("Categorize now");
      catBtn.addEventListener("click", () => runCategorize(status));
      status.append(catBtn);
      if (data.added > 0 && !prompted.has(a.id)) {
        prompted.add(a.id);
        showBalanceDialog(a);
      }
    } catch (err) {
      setStatus(status, err.message);
    }
  }

  async function runCategorize(status) {
    setStatus(status, "Categorizing…");
    try {
      const r = await api("/api/categorize/run", { method: "POST", body: { scope } });
      setStatus(
        status,
        `Categorized ${r.by_rule} by rule and ${r.by_llm} by AI. ${r.left} transactions left to review.`,
      );
    } catch (err) {
      setStatus(status, err.message);
    }
  }

  function showBalanceDialog(a) {
    const form = document.createElement("form");
    form.className = "stack";
    const p = document.createElement("p");
    p.textContent = `What is this account's balance today?`;
    const balF = field("Balance (dollars)", { inputmode: "decimal", placeholder: "0.00", required: true });
    const err = document.createElement("p");
    err.className = "error";
    err.hidden = true;
    const btns = document.createElement("div");
    btns.className = "actions";
    const cancel = btn("Cancel");
    const save = btn("Save", "primary");
    save.type = "submit";
    btns.append(cancel, save);
    form.append(p, balF, err, btns);
    const dlg = dialog(`Set balance — ${a.name}`, form);
    cancel.addEventListener("click", () => dlg.close());
    form.addEventListener("submit", async (e) => {
      e.preventDefault();
      err.hidden = true;
      const cents = dollarsToCents(balF.querySelector("input").value);
      if (cents === null) {
        err.textContent = "Enter a valid amount, like 1234.56.";
        err.hidden = false;
        return;
      }
      try {
        await api(`/api/accounts/${a.id}/balance`, {
          method: "PUT",
          body: { current_balance_cents: cents },
        });
        dlg.close();
        await refresh();
      } catch (err2) {
        err.textContent = err2.message;
        err.hidden = false;
      }
    });
  }

  function showAddDialog() {
    const form = document.createElement("form");
    form.className = "stack";
    const nameF = field("Name", { required: true, placeholder: "Everyday Checking" });
    const instF = field("Institution", { placeholder: "Wells Fargo" });
    const typeLabel = document.createElement("label");
    const typeSel = document.createElement("select");
    for (const [value, label] of [
      ["checking", "Checking"],
      ["savings", "Savings"],
      ["credit", "Credit card"],
    ]) {
      const o = document.createElement("option");
      o.value = value;
      o.textContent = label;
      typeSel.append(o);
    }
    typeLabel.append("Type", typeSel);
    const sharedLabel = document.createElement("label");
    sharedLabel.className = "check";
    const shared = document.createElement("input");
    shared.type = "checkbox";
    shared.checked = true;
    sharedLabel.append(shared, "Shared with spouse");
    const openF = field("Opening balance (dollars)", { inputmode: "decimal", placeholder: "0.00" });
    const err = document.createElement("p");
    err.className = "error";
    err.hidden = true;
    const btns = document.createElement("div");
    btns.className = "actions";
    const cancel = btn("Cancel");
    const save = btn("Add account", "primary");
    save.type = "submit";
    btns.append(cancel, save);
    form.append(nameF, instF, typeLabel, sharedLabel, openF, err, btns);
    const dlg = dialog("Add account", form);
    cancel.addEventListener("click", () => dlg.close());
    form.addEventListener("submit", async (e) => {
      e.preventDefault();
      err.hidden = true;
      const name = nameF.querySelector("input").value.trim();
      if (!name) {
        err.textContent = "Give the account a name.";
        err.hidden = false;
        return;
      }
      const body = {
        name,
        institution: instF.querySelector("input").value.trim(),
        type: typeSel.value,
        shared: shared.checked,
      };
      const opening = dollarsToCents(openF.querySelector("input").value);
      if (opening !== null && opening !== 0) body.opening_balance_cents = opening;
      try {
        await api("/api/accounts", { method: "POST", body });
        dlg.close();
        await refresh();
      } catch (err2) {
        err.textContent = err2.message;
        err.hidden = false;
      }
    });
  }

  addBtn.addEventListener("click", showAddDialog);
  await refresh();
}
