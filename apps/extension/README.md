# OpenTabs Chrome extension

The extension sidebar lives here. It uses the supplied Broadsheet design tokens in
`public/design-system/` and a Chrome Manifest V3 side panel.

## Run locally

```sh
npm install
npm run build
```

Open `chrome://extensions`, enable **Developer mode**, choose **Load unpacked**,
then select `apps/extension/dist`.

The sidebar stores pre-seeded demo tasks locally so it stays useful when backend
jobs are unavailable. The service worker also detects the PRD's URL-first GitHub,
research, Gmail, travel, and cart signals, with developer-task signals checked first.

## Run against the backend

Start the Python API from the repository root:

```sh
uv sync --locked
uv run uvicorn backend.app.main:app --reload
```

Start the sidebar app in another shell:

```sh
cd apps/extension
npm install
npm run dev
```

The Vite-launched sidebar connects directly to `http://localhost:8000`, creates an
anonymous installation credential, and stores it in `localStorage`. Override the API
URL with `VITE_OPEN_TABS_API_BASE_URL` when needed.
