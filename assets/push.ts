// Phone notifications for this device. Loaded only on Settings, and only asks for permission on a tap.
// Shares no modules with app.tsx (see the note there about the entry loading twice in production).
function keyBytes(base64url: string) {
  const raw = atob(base64url.replace(/-/g, "+").replace(/_/g, "/") + "=".repeat((4 - (base64url.length % 4)) % 4));
  return Uint8Array.from(raw, (c) => c.charCodeAt(0));
}

export async function setup(section: HTMLElement) {
  if (!("serviceWorker" in navigator) || !("PushManager" in window) || !("Notification" in window)) return;
  const { key, subscribe, unsubscribe, csrf } = section.dataset as Record<string, string>;
  const button = section.querySelector<HTMLButtonElement>("[data-push-toggle]")!;
  const status = section.querySelector<HTMLElement>("[data-push-status]")!;
  const post = (url: string, body: unknown) =>
    fetch(url, { method: "POST", credentials: "same-origin", headers: { "Content-Type": "application/json", "X-CSRFToken": csrf }, body: JSON.stringify(body) });
  const current = async () => (await navigator.serviceWorker.getRegistration("/"))?.pushManager.getSubscription() ?? null;
  const show = (on: boolean) => {
    button.textContent = on ? "Turn off for this device" : "Turn on for this device";
    status.textContent = on
      ? "On for this device. You'll get a notification when a budget goes over. It never shows amounts or names."
      : "Get a notification on this device when a budget goes over. It never shows amounts or names.";
  };
  show(Boolean(await current()));
  section.hidden = false;
  button.addEventListener("click", async () => {
    button.disabled = true;
    try {
      const existing = await current();
      if (existing) {
        await post(unsubscribe, { endpoint: existing.endpoint });
        await existing.unsubscribe();
        show(false);
      } else if ((await Notification.requestPermission()) !== "granted") {
        status.textContent = "Notifications are blocked for Budget. Allow them in this browser's site settings, then try again.";
      } else {
        const registration = await navigator.serviceWorker.register("/sw.js");
        await navigator.serviceWorker.ready;
        const subscription = await registration.pushManager.subscribe({ userVisibleOnly: true, applicationServerKey: keyBytes(key) });
        if (!(await post(subscribe, subscription.toJSON())).ok) {
          await subscription.unsubscribe();
          throw new Error("not saved");
        }
        show(true);
      }
    } catch {
      status.textContent = "Couldn't change notifications on this device. Try again.";
    } finally {
      button.disabled = false;
    }
  });
}
