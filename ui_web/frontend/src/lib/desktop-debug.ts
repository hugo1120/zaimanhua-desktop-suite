export function emitDesktopLog(
  component: string,
  event: string,
  payload?: Record<string, unknown>,
) {
  // @ts-ignore
  const api = window.pywebview?.api;
  if (!api || !api.log_debug) {
    return;
  }

  try {
    void Promise.resolve(api.log_debug(component, event, payload ?? {})).catch(() => {});
  } catch {
    return;
  }
}
