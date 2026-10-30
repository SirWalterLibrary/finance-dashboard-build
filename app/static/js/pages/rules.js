// Rules page: rules table + add form, categorize button, category editor.
import { api } from "../api.js";
import { money } from "../fmt.js";

const KINDS = ["income", "expense", "transfer", "savings", "reimbursement"];
const el = (tag, cls, text) => { const n = document.createElement(tag); if (cls) n.className = cls; if (text !== undefined) n.textContent = text; return n; };
const btn = (text, cls) => { const b = el("button", cls ? `btn ${cls}` : "btn", text); b.type = "button"; return b; };
const labeled = (text, input) => { const l = el("label"); l.append(text, input); return l; };
const headRow = (cols) => { const tr = el("tr"); for (const h of cols) tr.append(el("th", null, h)); return tr; };
const toast = (text) => { const t = el("div", "toast", text); document.body.append(t); setTimeout(() => t.remove(), 3500); };
const usd = (cents) => { const m = money(cents); return m.endsWith(".00") ? m.slice(0, -3) : m; };
const swatchInput = (color) => { const s = el("input", "swatch"); s.type = "color"; if (/^#[0-9a-f]{6}$/i.test(color)) s.value = color; return s; };
const numInput = (ph) => { const i = el("input", "f-num"); i.type = "number"; i.min = "0"; i.step = "0.01"; i.placeholder = ph; return i; };
const dollarsToCents = (v) => { if (v === "") return null; const n = Number(v); return Number.isFinite(n) && n >= 0 ? Math.round(n * 100) : null; };

function rangeText(r) {
  if (r.min_cents != null && r.max_cents != null) return `${usd(r.min_cents)} – ${usd(r.max_cents)}`;
  if (r.min_cents != null) return `≥ ${usd(r.min_cents)}`;
  if (r.max_cents != null) return `≤ ${usd(r.max_cents)}`;
  return "—";
}

export async function render(container, ctx) {
  const scope = ctx.scope;
  let categories = [];

  // Rules card (table + add form)
  const rulesTable = el("table");
  const ruleErr = el("p", "error");
  ruleErr.hidden = true;
  const rulesCard = el("div", "card");
  rulesCard.append(el("h2", null, "Rules"), rulesTable, ruleErr);
  const kwIn = el("input", "f-grow");
  kwIn.placeholder = "keyword (e.g. SAMS CLUB)";
  const catSel = el("select");
  const ruleForm = el("form", "form-flex");
  ruleForm.append(labeled("Keyword", kwIn), labeled("Category", catSel),
    labeled("Min $", numInput("min $")), labeled("Max $", numInput("max $")),
    Object.assign(btn("Add rule"), { type: "submit" }));
  rulesCard.append(ruleForm);
  ruleForm.addEventListener("submit", async (e) => {
    e.preventDefault();
    ruleErr.hidden = true;
    const [min, max] = [dollarsToCents(ruleForm.elements[2].value), dollarsToCents(ruleForm.elements[3].value)];
    const body = { keyword: kwIn.value.trim(), category_id: Number(catSel.value) };
    if (min != null) body.min_cents = min;
    if (max != null) body.max_cents = max;
    try {
      await api("/api/rules", { method: "POST", body });
      toast("Rule added"); ruleForm.reset(); await loadRules();
    } catch (err) { ruleErr.textContent = err.message; ruleErr.hidden = false; }
  });

  function ruleRow(r) {
    const tr = el("tr");
    const pill = el("span", "pill", r.category_name);
    const color = (categories.find((c) => c.id === r.category_id) || {}).color || "#888888";
    pill.style.color = color; pill.style.border = `1px solid ${color}`;
    const del = btn("Delete", "danger small");
    del.addEventListener("click", async () => {
      if (!confirm(`Delete rule "${r.keyword}"?`)) return;
      try {
        await api(`/api/rules/${r.id}`, { method: "DELETE" });
        toast("Rule deleted"); await loadRules();
      } catch (err) { ruleErr.textContent = err.message; ruleErr.hidden = false; }
    });
    tr.append(el("td", null, r.keyword), el("td", null, pill), el("td", "dim", rangeText(r)), el("td", null, del));
    return tr;
  }

  async function loadRules() {
    try {
      const rules = await api("/api/rules");
      rulesTable.replaceChildren(headRow(["Keyword", "Category", "Amount", ""]), ...rules.map(ruleRow));
    } catch (err) { ruleErr.textContent = err.message; ruleErr.hidden = false; }
  }

  // Categorize card
  const runBtn = btn("Categorize uncategorized (rules + AI)", "primary");
  const catOut = el("div", "cat-out");
  const runCard = el("div", "card");
  runCard.append(el("h2", null, "Categorize"), runBtn, catOut);
  runBtn.addEventListener("click", async () => {
    runBtn.disabled = true;
    catOut.replaceChildren(el("p", null, "Running…"));
    try {
      const r = await api("/api/categorize/run", { method: "POST", body: { scope } });
      catOut.replaceChildren(el("p", null, `Rules: ${r.by_rule}, AI: ${r.by_llm}, still uncategorized: ${r.left}.`));
      if (!r.llm_available) catOut.append(el("p", "cat-offline", "AI is offline — rules were applied only."));
    } catch (err) { catOut.replaceChildren(el("p", "error", err.message)); }
    finally { runBtn.disabled = false; }
  });

  // Categories card
  const catTable = el("table");
  const catErr = el("p", "error");
  catErr.hidden = true;
  const catCard = el("div", "card");
  catCard.append(
    el("h2", null, "Categories"),
    el("p", "dim", "The description is what the AI model sees as the criteria for each category — write it like a definition."),
    catTable,
    catErr,
  );
  container.append(el("h1", null, "Rules"), rulesCard, runCard, catCard);

  async function patchCat(c, body) {
    catErr.hidden = true;
    try { await api(`/api/categories/${c.id}`, { method: "PATCH", body }); toast("Saved"); await reloadCats(); }
    catch (err) { catErr.textContent = err.message; catErr.hidden = false; }
  }

  // Click-to-edit text cell: Enter/blur commits, Escape cancels.
  function editableText(td, c, value, field) {
    const span = el("span", "editable", value || "add description…");
    if (!value) span.classList.add("empty");
    span.addEventListener("click", () => {
      const inp = el("input", "inline-input");
      inp.value = value || "";
      td.replaceChildren(inp);
      inp.focus();
      let done = false;
      const commit = async () => {
        if (done) return;
        done = true;
        if (inp.value.trim() !== value) patchCat(c, { [field]: inp.value.trim() });
        else reloadCats();
      };
      inp.addEventListener("change", commit);
      inp.addEventListener("keydown", (e) => { if (e.key === "Enter") commit(); if (e.key === "Escape") { done = true; reloadCats(); } });
    });
    td.append(span);
  }

  function catRow(c) {
    const tr = el("tr");
    const del = btn("Delete", "danger small");
    del.addEventListener("click", async () => {
      if (!confirm(`Delete category "${c.name}"?`)) return;
      try {
        await api(`/api/categories/${c.id}`, { method: "DELETE" });
        toast(`Deleted "${c.name}"`); await reloadCats();
      } catch (err) { catErr.textContent = err.message; catErr.hidden = false; }
    });
    const nameTd = el("td");
    editableText(nameTd, c, c.name, "name");
    const descTd = el("td", "desc");
    editableText(descTd, c, c.description, "description");
    const sw = swatchInput(c.color);
    sw.addEventListener("change", () => patchCat(c, { color: sw.value }));
    tr.append(el("td", null, sw), nameTd, el("td", null, el("span", "badge", c.kind)), descTd, el("td", null, del));
    return tr;
  }

  function fillCatSelect() {
    const cur = catSel.value;
    categories.forEach((c) => { const o = el("option", null, c.name); o.value = c.id; catSel.append(o); });
    if (cur && categories.some((c) => String(c.id) === cur)) catSel.value = cur;
  }

  async function reloadCats() {
    try {
      categories = await api("/api/categories");
      catTable.replaceChildren(headRow(["", "Name", "Kind", "Description", ""]), ...categories.map(catRow));
      catSel.replaceChildren();
      fillCatSelect();
    } catch (err) { catErr.textContent = err.message; catErr.hidden = false; }
  }

  // Add-category form
  const nameIn = el("input", "f-grow");
  nameIn.placeholder = "name";
  const kindSel = el("select");
  KINDS.forEach((k) => kindSel.append(el("option", null, k)));
  kindSel.value = "expense";
  const descIn = el("input", "f-grow");
  descIn.placeholder = "description (what the AI sees)";
  const catForm = el("form", "form-flex");
  catForm.append(labeled("Name", nameIn), labeled("Kind", kindSel), labeled("Color", swatchInput("#5aa9ff")),
    labeled("Description", descIn), Object.assign(btn("Add"), { type: "submit" }));
  catCard.append(catForm);
  catForm.addEventListener("submit", async (e) => {
    e.preventDefault();
    catErr.hidden = true;
    try {
      await api("/api/categories", { method: "POST",
        body: { name: nameIn.value.trim(), kind: kindSel.value, color: catForm.elements[2].value, description: descIn.value.trim() } });
      toast("Category added"); nameIn.value = ""; descIn.value = ""; await reloadCats();
    } catch (err) { catErr.textContent = err.message; catErr.hidden = false; }
  });

  await reloadCats();
  await loadRules();
}
