# SignalSafe browser extension

This MVP extension submits the active browser tab as a public report.

## Load locally in Chrome or Edge

1. Start the backend on `http://localhost:8000`.
2. Open `chrome://extensions`.
3. Enable **Developer mode**.
4. Choose **Load unpacked**.
5. Select this `browser-extension` directory.
6. Open a normal `http://` or `https://` page and click the extension.

The extension sends `POST /api/reports` with the current URL and optional reason. Public reports are added to the reviewer queue and retained for future research.
