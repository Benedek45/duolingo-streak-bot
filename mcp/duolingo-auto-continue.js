(() => {
  const successPhrases = [
    "Remek",
    "Szép volt",
    "Szép munka",
    "Helyes",
    "Fantasztikus",
    "Ez igen",
  ];
  const finalScreenPhrases = [
    "Hibátlan lecke",
    "Napi feladat teljesítve",
    "Összesen",
    "napos széria",
    "LECKE ÁTNÉZÉSE",
    "Mutasd meg, hogy igazi legenda vagy",
  ];
  let pending = false;
  let lastText = "";

  function clean(text) {
    return (text || "").replace(/\s+/g, " ").trim();
  }

  function visible(element) {
    if (!(element instanceof HTMLElement)) return false;
    const style = window.getComputedStyle(element);
    const rect = element.getBoundingClientRect();
    return style.display !== "none" && style.visibility !== "hidden" && rect.width > 0 && rect.height > 0;
  }

  function enabled(element) {
    return !element.disabled && element.getAttribute("aria-disabled") !== "true";
  }

  function maybeContinue() {
    if (pending || !location.pathname.startsWith("/lesson")) return;
    const bodyText = clean(document.body ? document.body.innerText : "");
    if (!successPhrases.some((phrase) => bodyText.includes(phrase))) return;
    if (finalScreenPhrases.some((phrase) => bodyText.includes(phrase))) return;

    const button = document.querySelector('[data-test="player-next"], [data-testid="player-next"]');
    if (!visible(button) || !enabled(button) || !clean(button.innerText).includes("TOVÁBB")) return;

    const key = bodyText.slice(0, 500);
    if (key === lastText) return;
    lastText = key;
    pending = true;

    const delay = 900 + Math.floor(Math.random() * 1800);
    window.setTimeout(() => {
      pending = false;
      const currentText = clean(document.body ? document.body.innerText : "");
      const currentButton = document.querySelector('[data-test="player-next"], [data-testid="player-next"]');
      if (
        location.pathname.startsWith("/lesson") &&
        successPhrases.some((phrase) => currentText.includes(phrase)) &&
        !finalScreenPhrases.some((phrase) => currentText.includes(phrase)) &&
        visible(currentButton) &&
        enabled(currentButton) &&
        clean(currentButton.innerText).includes("TOVÁBB")
      ) {
        currentButton.click();
        window.__duolingoAutoContinueLastClick = new Date().toISOString();
      }
    }, delay);
  }

  window.__duolingoAutoContinueEnabled = true;
  new MutationObserver(maybeContinue).observe(document.documentElement, { childList: true, subtree: true, characterData: true });
  window.setInterval(maybeContinue, 1000);
})();
