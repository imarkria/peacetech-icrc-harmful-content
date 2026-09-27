# SignalSafe browser extension

This MVP extension submits the active browser tab as a public report.

## Load locally in Chrome or Edge

1. Start the backend on `http://localhost:8000`.
2. Open `chrome://extensions`.
3. Enable **Developer mode**.
4. Choose **Load unpacked**.
5. Select this `browser-extension` directory.
6. Open a normal `http://` or `https://` page and click the extension.

The extension sends `POST /api/reports` with the current URL, the category `other` and an optional reason. The report joins the reviewer queue with source `PUBLIC`.

The API address defaults to `http://localhost:8000`. To use a deployed backend, open **Settings** in the popup and enter its address; it is remembered. The backend accepts requests from any `chrome-extension://` origin (`cors_origin_regex` in `backend/app/config.py`).

The category is always `other`, like the web form: public users only send the link and a reason, and reviewers set the label.
