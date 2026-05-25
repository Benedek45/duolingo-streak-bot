(() => {
  function delay(ms) {
    return new Promise((resolve) => window.setTimeout(resolve, ms));
  }

  function nativeValueSetter(element) {
    const proto = element instanceof HTMLTextAreaElement ? HTMLTextAreaElement.prototype : HTMLInputElement.prototype;
    return Object.getOwnPropertyDescriptor(proto, "value")?.set;
  }

  function setValue(element, value) {
    const setter = nativeValueSetter(element);
    if (setter) {
      setter.call(element, value);
    } else {
      element.value = value;
    }
  }

  function keyFor(character) {
    return character === " " ? " " : character;
  }

  window.__duolingoHumanType = async (selector, value, options = {}) => {
    const element = document.querySelector(selector);
    if (!(element instanceof HTMLInputElement || element instanceof HTMLTextAreaElement)) {
      return { ok: false, error: `No input found for selector: ${selector}` };
    }

    const minDelay = Number(options.minDelay ?? 45);
    const maxDelay = Number(options.maxDelay ?? 140);
    const clear = options.clear !== false;

    element.focus();
    element.click();
    await delay(120 + Math.floor(Math.random() * 180));

    if (clear) {
      setValue(element, "");
      element.dispatchEvent(new InputEvent("input", { bubbles: true, inputType: "deleteContentBackward" }));
      await delay(80 + Math.floor(Math.random() * 120));
    }

    let current = element.value || "";
    for (const character of String(value)) {
      const key = keyFor(character);
      element.dispatchEvent(new KeyboardEvent("keydown", { bubbles: true, cancelable: true, key }));
      current += character;
      setValue(element, current);
      element.dispatchEvent(new InputEvent("input", { bubbles: true, data: character, inputType: "insertText" }));
      element.dispatchEvent(new KeyboardEvent("keyup", { bubbles: true, cancelable: true, key }));
      const span = Math.max(0, maxDelay - minDelay);
      await delay(minDelay + Math.floor(Math.random() * (span + 1)));
    }

    element.dispatchEvent(new Event("change", { bubbles: true }));
    return { ok: true, typedLength: String(value).length };
  };
})();
