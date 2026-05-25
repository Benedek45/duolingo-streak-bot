export default async ({ page }) => {
  const rawHosts = process.env.DUOLINGO_ALLOWED_HOSTS || "duolingo.com,.duolingo.com";
  const allowedHosts = rawHosts
    .split(",")
    .map((host) => host.trim().toLowerCase())
    .filter(Boolean);
  const allowAllWeb = allowedHosts.includes("*");

  const isAllowedHost = (hostname) => {
    const host = hostname.toLowerCase();
    return allowedHosts.some((allowed) => {
      if (allowed.startsWith(".")) {
        const suffix = allowed.slice(1);
        return host === suffix || host.endsWith(allowed);
      }
      return host === allowed;
    });
  };

  await page.route("**/*", async (route) => {
    const request = route.request();
    const url = new URL(request.url());

    if (["about:", "data:", "blob:"].includes(url.protocol)) {
      await route.continue();
      return;
    }

    if ((url.protocol === "https:" || url.protocol === "http:") && (allowAllWeb || isAllowedHost(url.hostname))) {
      await route.continue();
      return;
    }

    console.warn(`[duolingo-network-guard] blocked ${request.method()} ${request.url()}`);
    await route.abort("blockedbyclient");
  });
};
