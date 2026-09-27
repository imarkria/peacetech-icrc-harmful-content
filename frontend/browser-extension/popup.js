const DEFAULT_API_BASE_URL = "http://localhost:8000";

const form = document.querySelector("#report-form");
const urlInput = document.querySelector("#url");
const reasonInput = document.querySelector("#reason");
const counter = document.querySelector("#counter");
const apiUrlInput = document.querySelector("#api-url");
const submitButton = document.querySelector("#submit");
const message = document.querySelector("#message");

function setMessage(text, type = "") {
  message.textContent = text;
  message.className = `message ${type}`;
}

function isWebUrl(value) {
  try {
    const parsed = new URL(value);
    return parsed.protocol === "http:" || parsed.protocol === "https:";
  } catch {
    return false;
  }
}

chrome.storage.local.get({ apiBaseUrl: DEFAULT_API_BASE_URL }, ({ apiBaseUrl }) => {
  apiUrlInput.value = apiBaseUrl;
});

function apiBaseUrl() {
  const value = apiUrlInput.value.trim().replace(/\/$/, "");
  return isWebUrl(value) ? value : DEFAULT_API_BASE_URL;
}

reasonInput.addEventListener("input", () => {
  counter.textContent = `${reasonInput.value.length}/1000`;
});

chrome.tabs.query({ active: true, currentWindow: true }, (tabs) => {
  const currentUrl = tabs[0]?.url || "";
  if (isWebUrl(currentUrl)) urlInput.value = currentUrl;
  else setMessage("This page cannot be reported. Open a regular http or https page.", "error");
});

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  const url = urlInput.value.trim();
  const reason = reasonInput.value.trim();

  if (!isWebUrl(url)) {
    setMessage("Enter a valid http or https URL.", "error");
    return;
  }

  submitButton.disabled = true;
  submitButton.textContent = "Submitting…";
  setMessage("");

  try {
    const base = apiBaseUrl();
    chrome.storage.local.set({ apiBaseUrl: base });
    const response = await fetch(`${base}/api/reports`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ url, category: "other", reason: reason || undefined }),
    });
    const data = await response.json();
    if (!response.ok) throw new Error(data.detail || "Request failed");
    setMessage(`Report submitted. Reference: ${data.reference}`, "success");
    submitButton.textContent = "Submitted";
    setTimeout(() => window.close(), 900);
  } catch (error) {
    setMessage(error.message || "The reporting service is unavailable.", "error");
    submitButton.disabled = false;
    submitButton.textContent = "Submit report";
  }
});
