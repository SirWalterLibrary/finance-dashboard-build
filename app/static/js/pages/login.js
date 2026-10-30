// Login page: username + password -> POST /api/login -> #/home.
import { api } from "../api.js";

export async function render(container, ctx) {
  const card = document.createElement("div");
  card.className = "card login-card";

  const h1 = document.createElement("h1");
  h1.textContent = "Sign in";
  card.appendChild(h1);

  const form = document.createElement("form");
  form.className = "stack";

  const userLabel = document.createElement("label");
  userLabel.textContent = "Username";
  const userInput = document.createElement("input");
  userInput.name = "username";
  userInput.autocomplete = "username";
  userLabel.appendChild(userInput);

  const pwLabel = document.createElement("label");
  pwLabel.textContent = "Password";
  const pwInput = document.createElement("input");
  pwInput.type = "password";
  pwInput.name = "password";
  pwInput.autocomplete = "current-password";
  pwLabel.appendChild(pwInput);

  const error = document.createElement("p");
  error.className = "error";
  error.hidden = true;

  const submit = document.createElement("button");
  submit.type = "submit";
  submit.className = "btn primary";
  submit.textContent = "Sign in";

  form.append(userLabel, pwLabel, error, submit);
  card.appendChild(form);

  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    error.hidden = true;
    try {
      await api("/api/login", {
        method: "POST",
        body: {
          username: userInput.value.trim(),
          password: pwInput.value,
        },
      });
      location.hash = "#/home";
    } catch (err) {
      error.textContent =
        err.message === "not signed in"
          ? "Wrong username or password. Try again."
          : "Could not sign you in. Please try again.";
      error.hidden = false;
    }
  });

  container.appendChild(card);
}
