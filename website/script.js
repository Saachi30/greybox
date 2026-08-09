(function () {
  const tabs = document.querySelectorAll(".tab");
  const panels = document.querySelectorAll(".install-panel");

  function activate(osKey) {
    tabs.forEach((t) => t.classList.toggle("active", t.dataset.os === osKey));
    panels.forEach((p) => p.classList.toggle("active", p.id === "panel-" + osKey));
  }

  function detectOS() {
    const ua = navigator.userAgent || "";
    if (/Windows/i.test(ua)) return "windows";
    if (/Mac OS X|Macintosh/i.test(ua)) return "mac";
    return "linux";
  }

  const detected = detectOS();
  tabs.forEach((t) => {
    if (t.dataset.os === detected) t.setAttribute("data-detected", "");
    t.addEventListener("click", () => activate(t.dataset.os));
  });
  activate(detected);

  window.copyBlock = function (button) {
    const panel = document.getElementById(button.dataset.target);
    const code = panel.querySelector("code").innerText;
    navigator.clipboard.writeText(code).then(() => {
      const original = button.textContent;
      button.textContent = "copied";
      setTimeout(() => (button.textContent = original), 1500);
    });
  };
})();
