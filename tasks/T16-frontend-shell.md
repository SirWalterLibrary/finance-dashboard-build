# T16 — Frontend shell, login, scope toggle
Needs: T10
Files: app/static/index.html, app/static/css/app.css, app/static/js/{main,api,fmt}.js, app/static/package.json, app/static/vendor/chart.umd.js

Do:
1. `app/static/package.json` = `{"type":"module"}` (lets `make check-js` syntax-check ES modules).
2. Chart.js: `npm install chart.js@4 --prefix /tmp/cjs` then copy the UMD build (`ls /tmp/cjs/node_modules/chart.js/dist/*umd*.js`) to `app/static/vendor/chart.umd.js`.
   Load it with a normal `<script>` tag before `main.js`.
3. `api.js`: `api(path, {method, body, formData})` → JSON; on 401 → `location.hash="#/login"`. `fmt.js`: `money(cents)` ("$1,234.56", negatives "-$5.00"), `date(iso)` ("Sep 29, 2026").
4. `main.js`: hash router for `#/login #/home #/transactions #/budget #/goals #/forecast #/accounts #/rules`. Each page = `js/pages/<name>.js`
   exporting `render(container, ctx)`; unfinished pages render a heading + "Coming soon". `ctx = {scope, user}`.
5. Top bar: app name, nav links (active underlined), **scope toggle** (segmented: `Joint | Mine | Both` → `joint|personal|combined`) saved in
   `localStorage`, default `joint`, light/dark toggle, logout. Changing scope re-renders the current page.
6. `css/app.css`: CSS variables, dark default, light theme via `data-theme`. Cards, buttons, tables, form inputs, progress bar.
   Large readable fonts, plenty of whitespace, green = income, red = spending. Works on phone width.
7. Login page: username + password → `POST /api/login` → `#/home`. Show plain-language error.

Verify: `make check-js`; `make test`.
USER CHECK: `make seed && make dev`, open http://localhost:8000, log in demo1/demo; nav works; scope toggle visibly changes the selected state; theme toggle works.
