// Transactions page: filters, table with category pills, pagination, delete.
import { api } from "../api.js";
import { money, date } from "../fmt.js";

const PAGE_SIZE = 50;

function toast(text) {
  const t = document.createElement("div");
  t.className = "toast";
  t.textContent = text;
  document.body.append(t);
  setTimeout(() => t.remove(), 3500);
}

function el(tag, cls, text) {
  const n = document.createElement(tag);
  if (cls) n.className = cls;
  if (text !== undefined) n.textContent = text;
  return n;
}

function btn(text, cls) {
  const b = el("button", cls ? `btn ${cls}` : "btn", text);
  b.type = "button";
  return b;
}

function labeled(text, input) {
  const l = el("label");
  l.append(text, input);
  return l;
}

function fillOptions(sel, pairs) {
  for (const [value, label] of pairs) {
    const o = el("option", null, label);
    o.value = value;
    sel.append(o);
  }
}

function showDialog(title, body) {
  const dlg = el("dialog", "dlg");
  dlg.append(el("h2", null, title), body);
  dlg.addEventListener("close", () => dlg.remove());
  document.body.append(dlg);
  dlg.showModal();
  return dlg;
}

export async function render(container, ctx) {
  const scope = ctx.scope;
  const state = { q: "", account_id: "", category_id: "", direction: "", from: "", to: "", source: "", offset: 0 };
  let categories = [];

  const filters = el("div", "card filters");
  const qInput = el("input");
  qInput.placeholder = "Search description…";
  const accSel = el("select");
  const catSel = el("select");
  const dirSel = el("select");
  const fromIn = el("input");
  fromIn.type = "date";
  const toIn = el("input");
  toIn.type = "date";
  const chipReview = btn("Needs review", "chip");
  const chipAi = btn("AI-guessed", "chip");
  const chips = el("div", "chips");
  chips.append(chipReview, chipAi);
  filters.append(
    labeled("Search", qInput),
    labeled("Account", accSel),
    labeled("Category", catSel),
    labeled("Direction", dirSel),
    labeled("From", fromIn),
    labeled("To", toIn),
    chips,
  );

  const tableWrap = el("div", "card");
  const table = el("table");
  const pager = el("div", "pager");
  const emptyMsg = el("p", "dim", "No transactions match these filters.");
  container.append(el("h1", null, "Transactions"), filters, tableWrap, pager);

  let debounce;
  qInput.addEventListener("input", () => {
    clearTimeout(debounce);
    debounce = setTimeout(() => {
      state.q = qInput.value.trim();
      state.offset = 0;
      load();
    }, 300);
  });
  accSel.addEventListener("change", () => { state.account_id = accSel.value; state.offset = 0; load(); });
  catSel.addEventListener("change", () => { state.category_id = catSel.value; state.offset = 0; load(); });
  dirSel.addEventListener("change", () => { state.direction = dirSel.value; state.offset = 0; load(); });
  fromIn.addEventListener("change", () => { state.from = fromIn.value; state.offset = 0; load(); });
  toIn.addEventListener("change", () => { state.to = toIn.value; state.offset = 0; load(); });
  function setSource(source, chip) {
    state.source = state.source === source ? "" : source;
    chip.classList.toggle("active", state.source === source);
    (chip === chipReview ? chipAi : chipReview).classList.remove("active");
    state.offset = 0;
    load();
  }
  chipReview.addEventListener("click", () => setSource("none", chipReview));
  chipAi.addEventListener("click", () => setSource("llm", chipAi));

  function renderPager(total, shown) {
    const page = Math.floor(state.offset / PAGE_SIZE) + 1;
    const pages = Math.max(1, Math.ceil(total / PAGE_SIZE));
    const prev = btn("← Prev");
    const next = btn("Next →");
    const info = el("span", "dim", `${total} transaction${total === 1 ? "" : "s"} · page ${page} of ${pages}`);
    prev.disabled = state.offset === 0;
    next.disabled = state.offset + shown >= total;
    prev.addEventListener("click", () => { state.offset -= PAGE_SIZE; load(); });
    next.addEventListener("click", () => { state.offset += PAGE_SIZE; load(); });
    pager.replaceChildren(prev, info, next);
  }

  async function load() {
    const p = new URLSearchParams({ scope });
    for (const [key, val] of Object.entries(state)) if (val !== "" && key !== "offset") p.set(key, val);
    p.set("limit", String(PAGE_SIZE));
    p.set("offset", String(state.offset));
    tableWrap.replaceChildren();
    try {
      const data = await api(`/api/transactions?${p}`);
      if (!data.items.length) {
        tableWrap.append(emptyMsg);
      } else {
        const head = el("tr");
        for (const h of ["Date", "Description", "Account", "Category", "Amount", ""]) head.append(el("th", null, h));
        table.replaceChildren(head, ...data.items.map(row));
        tableWrap.append(table);
      }
      renderPager(data.total, data.items.length);
    } catch (err) {
      tableWrap.append(el("p", "error", err.message));
    }
  }

  function row(tx) {
    const tr = el("tr");
    const desc = el("td", "desc", tx.description);
    desc.title = tx.description;
    const amt = el("td", `num ${tx.amount_cents > 0 ? "income" : "spend"}`, money(tx.amount_cents));
    const delTd = el("td");
    const del = btn("Delete", "danger small");
    del.addEventListener("click", () => removeTx(tx));
    delTd.append(del);
    tr.append(el("td", null, date(tx.date)), desc, el("td", null, tx.account_name), categoryCell(tx), amt, delTd);
    return tr;
  }

  function categoryCell(tx) {
    const td = el("td");
    const pill = el("button", `pill pill-${tx.category_source}`);
    pill.type = "button";
    const color = tx.category_color || "#888888";
    if (tx.category_source === "manual") {
      pill.style.background = color;
      pill.style.borderColor = color;
      pill.style.color = "#fff";
      pill.textContent = tx.category_name;
    } else if (tx.category_source === "none") {
      pill.textContent = "Uncategorized";
    } else {
      pill.style.color = color;
      pill.style.borderColor = color;
      pill.textContent = tx.category_name;
      pill.append(el("span", "pill-auto", "auto"));
      if (tx.category_source === "llm") {
        pill.title = `AI-guessed (${Math.round((tx.category_confidence ?? 0) * 100)}% confident)`;
      }
    }
    pill.addEventListener("click", () => showPicker(td, tx));
    td.append(pill);
    return td;
  }

  function showPicker(td, tx) {
    const sel = el("select", "pill-select");
    fillOptions(sel, categories.map((c) => [c.id, c.name]));
    sel.value = String(tx.category_id);
    sel.addEventListener("change", () => {
      if (Number(sel.value) === tx.category_id) return;
      askSimilar(tx, Number(sel.value));
    });
    td.replaceChildren(sel);
    sel.focus();
  }

  function catName(id) {
    const c = categories.find((c) => c.id === id);
    return c ? c.name : "";
  }

  function askSimilar(tx, categoryId) {
    const form = el("form", "stack");
    const prefilled = tx.suggested_keyword || "";
    const p = el("p", null, `Apply to all similar transactions ('${prefilled}')?`);
    const kw = el("input");
    kw.value = prefilled;
    kw.placeholder = "keyword";
    const err = el("p", "error");
    err.hidden = true;
    const btns = el("div", "actions");
    const onlyBtn = btn("Only this one");
    const allBtn = btn("Apply to all similar", "primary");
    allBtn.type = "submit";
    btns.append(onlyBtn, allBtn);
    form.append(p, labeled("Keyword", kw), err, btns);
    const dlg = showDialog(`Move to "${catName(categoryId)}"`, form);

    async function save(applyToSimilar) {
      err.hidden = true;
      try {
        const r = await api(`/api/transactions/${tx.id}`, {
          method: "PATCH",
          body: { category_id: categoryId, apply_to_similar: applyToSimilar, keyword: kw.value.trim() },
        });
        dlg.close();
        await load();
        toast(`Updated ${r.updated} transaction${r.updated === 1 ? "" : "s"}`);
      } catch (e2) {
        err.textContent = e2.message;
        err.hidden = false;
      }
    }
    onlyBtn.addEventListener("click", () => save(false));
    form.addEventListener("submit", (e) => { e.preventDefault(); save(true); });
  }

  async function removeTx(tx) {
    if (!confirm(`Delete this transaction from ${tx.account_name} (${date(tx.date)})?`)) return;
    try {
      await api(`/api/transactions/${tx.id}`, { method: "DELETE" });
      await load();
      toast("Transaction deleted");
    } catch (err) {
      toast(err.message);
    }
  }

  try {
    const [accounts, cats] = await Promise.all([
      api(`/api/accounts?scope=${scope}`),
      api("/api/categories"),
    ]);
    categories = cats;
    fillOptions(accSel, [["", "All accounts"], ...accounts.map((a) => [a.id, a.name])]);
    fillOptions(catSel, [["", "All categories"], ...categories.map((c) => [c.id, c.name])]);
    fillOptions(dirSel, [["", "All"], ["in", "Money in"], ["out", "Money out"]]);
  } catch (err) {
    tableWrap.append(el("p", "error", err.message));
    return;
  }
  await load();
}
