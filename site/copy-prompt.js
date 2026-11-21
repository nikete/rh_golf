const copyButton = document.getElementById("copy-prompt");
const promptText = document.getElementById("agent-prompt");
const copyStatus = document.getElementById("copy-status");

if (navigator.clipboard && navigator.clipboard.writeText) {
  copyButton.hidden = false;
  copyButton.addEventListener("click", async () => {
    try {
      await navigator.clipboard.writeText(promptText.textContent);
      copyStatus.textContent = "Copied. Paste the prompt into your agent.";
    } catch {
      document.getElementById("agent-details").open = true;
      promptText.focus();
      const range = document.createRange();
      range.selectNodeContents(promptText);
      const selection = window.getSelection();
      selection.removeAllRanges();
      selection.addRange(range);
      copyStatus.textContent = "Prompt selected. Use your usual copy shortcut.";
    }
  });
}
