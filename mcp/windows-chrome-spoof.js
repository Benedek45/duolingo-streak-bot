(() => {
  const chromeMajor = globalThis.process?.env?.CHROME_MAJOR || "136";
  const userAgent = globalThis.process?.env?.BROWSER_USER_AGENT ||
    `Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/${chromeMajor}.0.0.0 Safari/537.36`;
  const width = Number(globalThis.process?.env?.BROWSER_WIDTH || 1366);
  const height = Number(globalThis.process?.env?.BROWSER_HEIGHT || 768);
  const defineGetter = (obj, prop, value) => {
    try {
      Object.defineProperty(obj, prop, { get: () => value, configurable: true });
    } catch (_) {}
  };

  defineGetter(Navigator.prototype, "webdriver", undefined);
  defineGetter(Navigator.prototype, "platform", "Win32");
  defineGetter(Navigator.prototype, "vendor", "Google Inc.");
  defineGetter(Navigator.prototype, "hardwareConcurrency", 8);
  defineGetter(Navigator.prototype, "deviceMemory", 8);
  defineGetter(Navigator.prototype, "maxTouchPoints", 0);
  defineGetter(Navigator.prototype, "languages", ["en-US", "en"]);
  defineGetter(Navigator.prototype, "userAgent", userAgent);

  if (!window.chrome) {
    Object.defineProperty(window, "chrome", { value: { runtime: {} }, configurable: true });
  }

  const userAgentData = {
    brands: [
      { brand: "Not/A)Brand", version: "8" },
      { brand: "Chromium", version: chromeMajor },
      { brand: "Google Chrome", version: chromeMajor }
    ],
    mobile: false,
    platform: "Windows",
    getHighEntropyValues: async (hints) => {
      const values = {
        architecture: "x86",
        bitness: "64",
        brands: userAgentData.brands,
        fullVersionList: [
          { brand: "Not/A)Brand", version: "8.0.0.0" },
          { brand: "Chromium", version: `${chromeMajor}.0.0.0` },
          { brand: "Google Chrome", version: `${chromeMajor}.0.0.0` }
        ],
        mobile: false,
        model: "",
        platform: "Windows",
        platformVersion: "15.0.0",
        uaFullVersion: `${chromeMajor}.0.0.0`,
        wow64: false
      };
      return Object.fromEntries(hints.map((hint) => [hint, values[hint]]));
    }
  };
  defineGetter(Navigator.prototype, "userAgentData", userAgentData);

  const originalGetParameter = WebGLRenderingContext.prototype.getParameter;
  WebGLRenderingContext.prototype.getParameter = function(parameter) {
    if (parameter === 37445) return "Google Inc. (Intel)";
    if (parameter === 37446) return "ANGLE (Intel, Intel(R) UHD Graphics Direct3D11 vs_5_0 ps_5_0, D3D11)";
    return originalGetParameter.call(this, parameter);
  };

  const originalQuery = window.navigator.permissions && window.navigator.permissions.query;
  if (originalQuery) {
    window.navigator.permissions.query = (parameters) => (
      parameters && parameters.name === "notifications"
        ? Promise.resolve({ state: Notification.permission })
        : originalQuery(parameters)
    );
  }

  defineGetter(Screen.prototype, "availWidth", width);
  defineGetter(Screen.prototype, "availHeight", height);
  defineGetter(Screen.prototype, "width", width);
  defineGetter(Screen.prototype, "height", height);
})();
