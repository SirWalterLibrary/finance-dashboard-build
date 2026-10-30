// Goals page (placeholder until its task).
export async function render(container, ctx) {
  const h1 = document.createElement("h1");
  h1.textContent = "Goals";
  const p = document.createElement("p");
  p.textContent = "Coming soon";
  container.append(h1, p);
}
