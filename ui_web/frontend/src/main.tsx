import React from "react";
import ReactDOM from "react-dom/client";
import "@mantine/core/styles.css";
import "./styles/index.css";

function reportBootstrapError(message: string, error: unknown) {
  const details: Record<string, string> = {
    message: error instanceof Error ? error.message : String(error),
  };

  if (error instanceof Error && error.stack) {
    details.stack = error.stack;
  }

  void fetch("/api/debug/frontend-error", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      source: "main.tsx",
      message,
      details,
    }),
  }).catch(() => {});
}

function reportBootstrapSignal(message: string, details: Record<string, string> = {}) {
  void fetch("/api/debug/frontend-error", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      source: "main.tsx",
      message,
      details,
    }),
  }).catch(() => {});
}

window.addEventListener("error", (event) => {
  reportBootstrapError("window.error", event.error ?? event.message);
});

window.addEventListener("unhandledrejection", (event) => {
  reportBootstrapError("window.unhandledrejection", event.reason);
});

const root = ReactDOM.createRoot(document.getElementById("root") as HTMLElement);
reportBootstrapSignal("main.module_loaded");
reportBootstrapSignal("app.import_start");

void import("./App")
  .then(({ default: App }) => {
    reportBootstrapSignal("app.import_succeeded");
    root.render(
      <React.StrictMode>
        <App />
      </React.StrictMode>,
    );
  })
  .catch((error) => {
    reportBootstrapError("app.import_failed", error);
  });
