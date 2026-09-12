(() => {
  const risk = document.getElementById("risk");
  const score = risk?.closest(".score");
  if (!risk || !score) return;

  const syncTheme = () => {
    const label = risk.childNodes[0]?.textContent.trim();
    const theme = label === "TỐT" ? "is-good" : label === "LƯU Ý" ? "is-warning" : label === "RỦI RO" ? "is-risk" : "is-warning";
    if (!score.classList.contains(theme)) {
      score.classList.remove("is-good", "is-warning", "is-risk");
      score.classList.add(theme);
    }
    const caption = risk.querySelector("small");
    if (caption && label !== "--" && caption.textContent !== "TÀI CHÍNH") caption.textContent = "TÀI CHÍNH";
  };

  new MutationObserver(syncTheme).observe(risk, { childList: true, characterData: true, subtree: true });
  syncTheme();
})();
