// Formatting helpers. Money is integer cents; dates are ISO YYYY-MM-DD text.

export function money(cents) {
  const n = Number(cents) || 0;
  const sign = n < 0 ? "-" : "";
  const abs = Math.abs(n);
  const dollars = Math.floor(abs / 100);
  const rest = String(abs % 100).padStart(2, "0");
  return `${sign}$${String(dollars).replace(/\B(?=(\d{3})+(?!\d))/g, ",")}.${rest}`;
}

export function date(iso) {
  if (!iso) return "";
  const [y, m, d] = iso.split("-").map(Number);
  const months = [
    "Jan", "Feb", "Mar", "Apr", "May", "Jun",
    "Jul", "Aug", "Sep", "Oct", "Nov", "Dec",
  ];
  return `${months[m - 1]} ${d}, ${y}`;
}
