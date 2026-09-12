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
It is ready to replace that local fallback with the backend's onboarding, scan, and
task endpoints as those endpoints become available.
