// Plaid Link for connecting a bank. Loaded only on the Connect a bank page, which is also the only page that loads Plaid's script.
// Shares no modules with app.tsx (see the note there about the entry loading twice in production).
type Handler = { open: () => void };
type Metadata = { institution?: { name?: string } | null };
declare const Plaid: { create: (config: { token: string; onSuccess: (publicToken: string, metadata: Metadata) => void; onExit: () => void }) => Handler };

export function setup(section: HTMLElement) {
  const { token, exchange, csrf } = section.dataset as Record<string, string>;
  const button = section.querySelector<HTMLButtonElement>("[data-plaid-open]")!;
  const status = section.querySelector<HTMLElement>("[data-plaid-status]")!;
  const script = document.createElement("script");
  script.src = "https://cdn.plaid.com/link/v2/stable/link-initialize.js";
  script.onerror = () => { status.textContent = "Plaid didn't load. Check your connection and reload the page."; };
  script.onload = () => {
    const handler = Plaid.create({
      token,
      onExit: () => { button.disabled = false; },
      onSuccess: async (publicToken, metadata) => {
        status.textContent = "Connecting…";
        const response = await fetch(exchange, {
          method: "POST", credentials: "same-origin", headers: { "Content-Type": "application/json", "X-CSRFToken": csrf },
          body: JSON.stringify({ public_token: publicToken, institution: metadata.institution?.name ?? "" }),
        }).catch(() => null);
        if (response?.ok) location.assign((await response.json()).next);
        else { status.textContent = "Plaid couldn't finish connecting. Try again."; button.disabled = false; }
      },
    });
    button.disabled = false;
    button.addEventListener("click", () => { button.disabled = true; handler.open(); });
  };
  document.head.append(script);
  section.hidden = false;
}
