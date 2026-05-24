(() => {
  const interestingRoles = new Set(["button", "link", "textbox", "radio", "checkbox", "option"]);

  function isVisible(element) {
    if (!(element instanceof HTMLElement)) return false;
    const style = window.getComputedStyle(element);
    if (style.visibility === "hidden" || style.display === "none" || Number(style.opacity) === 0) return false;
    const rect = element.getBoundingClientRect();
    return rect.width > 0 && rect.height > 0 && rect.bottom >= 0 && rect.right >= 0 && rect.top <= window.innerHeight && rect.left <= window.innerWidth;
  }

  function clean(text, limit = 180) {
    return (text || "").replace(/\s+/g, " ").trim().slice(0, limit);
  }

  function labelFor(element) {
    return clean(
      element.getAttribute("aria-label") ||
        element.getAttribute("title") ||
        element.getAttribute("placeholder") ||
        element.innerText ||
        element.textContent ||
        element.getAttribute("alt") ||
        ""
    );
  }

  function selectorFor(element) {
    const dataTest = element.getAttribute("data-test") || element.getAttribute("data-testid");
    if (dataTest) return `[data-test="${CSS.escape(dataTest)}"], [data-testid="${CSS.escape(dataTest)}"]`;
    const aria = element.getAttribute("aria-label");
    if (aria) return `${element.tagName.toLowerCase()}[aria-label="${CSS.escape(aria)}"]`;
    const id = element.id;
    if (id) return `#${CSS.escape(id)}`;
    return null;
  }

  function compactControls() {
    const nodes = Array.from(document.querySelectorAll("button, a, input, textarea, select, [role]"));
    return nodes
      .filter(isVisible)
      .map((element, index) => {
        const role = element.getAttribute("role") || element.tagName.toLowerCase();
        const label = labelFor(element);
        if (!label && !interestingRoles.has(role)) return null;
        return {
          index,
          role,
          label,
          selector: selectorFor(element),
          disabled: Boolean(element.disabled || element.getAttribute("aria-disabled") === "true"),
        };
      })
      .filter(Boolean)
      .slice(0, 80);
  }

  function compactText() {
    const text = clean(document.body ? document.body.innerText : "", 4500);
    return text;
  }

  window.__duolingoCompactView = () => ({
    url: location.href,
    title: document.title,
    text: compactText(),
    controls: compactControls(),
  });
})();
