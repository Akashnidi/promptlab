/**
 * PromptLab v1 by MAx Ops — Atlassian Themed LLM Workbench
 * Toast notifications, Theme switcher, Keyboard shortcuts, and Clipboard helpers
 */

// ============================================================================
// 1. Toast Notification System (Atlassian Flag / Message Style)
// ============================================================================
function showToast(message, type = "info") {
  const container = document.getElementById("toast-container");
  if (!container) return;

  const toast = document.createElement("div");
  toast.className = `toast-enter pointer-events-auto flex items-center gap-3 rounded-lg border px-4 py-3 text-xs font-semibold shadow-lg backdrop-blur-md cursor-pointer select-none transition-all duration-150 hover:shadow-xl`;

  let icon = "ℹ️";
  let bgClasses = "bg-white text-slate-800 border-slate-200 dark:bg-slate-900 dark:text-slate-100 dark:border-slate-700 shadow-slate-200/50";

  if (type === "success") {
    icon = "✅";
    bgClasses = "bg-emerald-50 text-emerald-900 border-emerald-300 dark:bg-emerald-950/80 dark:text-emerald-200 dark:border-emerald-800 shadow-emerald-500/10";
  } else if (type === "error") {
    icon = "⚠️";
    bgClasses = "bg-red-50 text-red-900 border-red-300 dark:bg-red-950/80 dark:text-red-200 dark:border-red-800 shadow-red-500/10";
  } else if (type === "info") {
    icon = "💡";
    bgClasses = "bg-blue-50 text-blue-900 border-blue-300 dark:bg-blue-950/80 dark:text-blue-200 dark:border-blue-800 shadow-blue-500/10";
  }

  toast.className += ` ${bgClasses}`;
  toast.innerHTML = `
    <span class="text-sm flex-shrink-0">${icon}</span>
    <span class="flex-1 leading-snug">${message}</span>
    <button type="button" class="text-slate-400 hover:text-slate-700 dark:hover:text-white ml-2 text-xs font-bold leading-none">✕</button>
  `;

  const dismiss = () => {
    if (toast.dataset.dismissed) return;
    toast.dataset.dismissed = "true";
    toast.classList.remove("toast-enter");
    toast.classList.add("toast-leave");
    setTimeout(() => {
      if (toast.parentElement) toast.remove();
    }, 220);
  };

  toast.addEventListener("click", dismiss);
  container.appendChild(toast);

  // Auto-dismiss after 3.5 seconds
  setTimeout(dismiss, 3500);
}
window.showToast = showToast;

// ============================================================================
// 2. Clipboard Helper
// ============================================================================
function copyToClipboard(text, successMsg = "Copied to clipboard!") {
  if (!text) return;
  if (navigator.clipboard && navigator.clipboard.writeText) {
    navigator.clipboard.writeText(text)
      .then(() => {
        showToast(successMsg, "success");
      })
      .catch((err) => {
        console.error("Clipboard copy failed:", err);
        fallbackCopyToClipboard(text, successMsg);
      });
  } else {
    fallbackCopyToClipboard(text, successMsg);
  }
}
window.copyToClipboard = copyToClipboard;

function fallbackCopyToClipboard(text, successMsg) {
  try {
    const textarea = document.createElement("textarea");
    textarea.value = text;
    textarea.style.position = "fixed";
    textarea.style.opacity = "0";
    document.body.appendChild(textarea);
    textarea.select();
    document.execCommand("copy");
    document.body.removeChild(textarea);
    showToast(successMsg, "success");
  } catch (e) {
    showToast("Failed to copy to clipboard", "error");
  }
}

// ============================================================================
// 3. Theme Manager (Light by default, Clean Dark support)
// ============================================================================
function getStoredTheme() {
  return localStorage.getItem("promptlab_theme") || "light";
}

function applyTheme(theme) {
  const html = document.documentElement;
  const themeIcon = document.getElementById("theme-toggle-icon");
  const themeBtn = document.getElementById("theme-toggle-btn");

  if (theme === "dark") {
    html.classList.add("dark");
    if (themeIcon) themeIcon.textContent = "☀️";
    if (themeBtn) themeBtn.title = "Switch to Light Mode";
  } else {
    html.classList.remove("dark");
    if (themeIcon) themeIcon.textContent = "🌙";
    if (themeBtn) themeBtn.title = "Switch to Dark Mode";
  }
}

function toggleTheme() {
  const current = document.documentElement.classList.contains("dark") ? "dark" : "light";
  const newTheme = current === "dark" ? "light" : "dark";
  localStorage.setItem("promptlab_theme", newTheme);
  applyTheme(newTheme);
  showToast(`Switched to ${newTheme === "light" ? "Light" : "Dark"} theme`, "info");
}
window.toggleTheme = toggleTheme;

// Apply theme on script load
applyTheme(getStoredTheme());

// ============================================================================
// 4. Modal & Shortcuts Cheatsheet Helpers
// ============================================================================
function toggleShortcutsModal() {
  const modal = document.getElementById("shortcuts-modal");
  if (!modal) return;
  modal.classList.toggle("hidden");
}
window.toggleShortcutsModal = toggleShortcutsModal;

function closeModal() {
  const modal = document.getElementById("history-detail-modal");
  if (modal) modal.innerHTML = "";
}
window.closeModal = closeModal;

// ============================================================================
// 5. Global Keyboard Shortcuts
// ============================================================================
document.addEventListener("keydown", function (e) {
  // Ctrl+K: Focus history search or toggle shortcuts modal
  if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "k") {
    e.preventDefault();
    const searchInput = document.querySelector('input[name="q"]');
    if (searchInput) {
      searchInput.focus();
      searchInput.select();
    }
  }

  // Escape: Close open modals
  if (e.key === "Escape") {
    const shortcutsModal = document.getElementById("shortcuts-modal");
    if (shortcutsModal && !shortcutsModal.classList.contains("hidden")) {
      shortcutsModal.classList.add("hidden");
    }
    const historyModal = document.getElementById("history-detail-modal");
    if (historyModal && historyModal.innerHTML.trim() !== "") {
      historyModal.innerHTML = "";
    }
  }

  // Ctrl+Enter / Cmd+Enter: Submit prompt form
  if ((e.ctrlKey || e.metaKey) && e.key === "Enter") {
    const target = e.target;
    if (target && (target.id === "prompt-input" || target.id === "system-prompt-input")) {
      e.preventDefault();
      const sendBtn = document.getElementById("send-btn");
      if (sendBtn) {
        sendBtn.click();
      }
    }
  }
});

// ============================================================================
// 6. Direct Prompt Loader from History
// ============================================================================
function loadPromptDirectly(item) {
  if (!item) return;

  const promptInput = document.getElementById("prompt-input");
  if (promptInput) {
    promptInput.value = item.prompt || "";
    if (window.updateCountAndResize) {
      window.updateCountAndResize(promptInput);
    }
  }

  const modelSelect = document.getElementById("model-select");
  if (modelSelect && item.model) {
    let found = false;
    for (let i = 0; i < modelSelect.options.length; i++) {
      if (modelSelect.options[i].value === item.model) {
        modelSelect.selectedIndex = i;
        found = true;
        break;
      }
    }
    if (!found) {
      const opt = document.createElement("option");
      opt.value = item.model;
      opt.textContent = `${item.model} (From History)`;
      opt.selected = true;
      modelSelect.appendChild(opt);
    }
  }

  const tempInput = document.getElementById("temperature-input");
  const tempVal = document.getElementById("temp-val");
  if (tempInput && item.temperature !== undefined) {
    tempInput.value = item.temperature;
    if (tempVal) tempVal.textContent = item.temperature;
  }

  if (promptInput) {
    promptInput.scrollIntoView({ behavior: "smooth", block: "center" });
    promptInput.focus();
  }

  showToast(`Loaded prompt (${item.model}) into workspace`, "info");
}
window.loadPromptDirectly = loadPromptDirectly;

// ============================================================================
// 7. Arena Pick Winner Helper
// ============================================================================
function pickWinner(comparisonId, modelName, cardId) {
  const cards = document.querySelectorAll(`[id^="arena-card-${comparisonId}"]`);
  cards.forEach((c) => {
    c.classList.remove("ring-2", "ring-emerald-500", "border-emerald-500", "bg-emerald-50/20", "dark:bg-emerald-950/20");
    const badge = c.querySelector(".winner-badge");
    if (badge) badge.remove();
  });

  const winnerCard = document.getElementById(cardId);
  if (winnerCard) {
    winnerCard.classList.add("ring-2", "ring-emerald-500", "border-emerald-500", "bg-emerald-50/20", "dark:bg-emerald-950/20");
    const header = winnerCard.querySelector(".border-b");
    if (header) {
      const winBadge = document.createElement("span");
      winBadge.className = "winner-badge inline-flex items-center gap-1 rounded px-2 py-0.5 text-[10px] font-bold lozenge-green uppercase";
      winBadge.innerHTML = "🏆 Chosen Winner";
      header.appendChild(winBadge);
    }
  }

  showToast(`Selected ${modelName} as the winning output!`, "success");
}
window.pickWinner = pickWinner;
