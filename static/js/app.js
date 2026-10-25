/**
 * PromptLab v1 by MAx Ops — Enterprise Prompt Engineering Workbench
 * Toast notifications, Theme switcher, Keyboard shortcuts, and Clipboard helpers
 */

// ============================================================================
// 1. Toast Notification System
// ============================================================================
function showToast(message, type = "info") {
  const container = document.getElementById("toast-container");
  if (!container) return;

  const toast = document.createElement("div");
  toast.className = `toast-enter pointer-events-auto flex items-center gap-2.5 rounded-xl border px-4 py-3 text-xs font-medium shadow-2xl backdrop-blur-md cursor-pointer select-none transition-all duration-200 hover:scale-[1.02]`;

  let icon = "ℹ️";
  let bgClasses = "bg-slate-900/95 border-slate-700/80 text-slate-100";

  if (type === "success") {
    icon = "✅";
    bgClasses = "bg-emerald-950/90 border-emerald-500/40 text-emerald-200 shadow-emerald-950/30";
  } else if (type === "error") {
    icon = "⚠️";
    bgClasses = "bg-rose-950/90 border-rose-500/40 text-rose-200 shadow-rose-950/30";
  } else if (type === "info") {
    icon = "💡";
    bgClasses = "bg-indigo-950/90 border-indigo-500/40 text-indigo-200 shadow-indigo-950/30";
  }

  toast.className += ` ${bgClasses}`;
  toast.innerHTML = `
    <span class="text-sm flex-shrink-0">${icon}</span>
    <span class="flex-1">${message}</span>
    <button type="button" class="text-slate-400 hover:text-white ml-2 text-xs font-bold leading-none">✕</button>
  `;

  const dismiss = () => {
    if (toast.dataset.dismissed) return;
    toast.dataset.dismissed = "true";
    toast.classList.remove("toast-enter");
    toast.classList.add("toast-leave");
    setTimeout(() => {
      if (toast.parentElement) toast.remove();
    }, 250);
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
// 3. Theme Manager (Dark / Light)
// ============================================================================
function getStoredTheme() {
  return localStorage.getItem("promptlab_theme") || "dark";
}

function applyTheme(theme) {
  const html = document.documentElement;
  const themeIcon = document.getElementById("theme-toggle-icon");
  const themeBtn = document.getElementById("theme-toggle-btn");

  if (theme === "light") {
    html.classList.add("light-theme");
    html.classList.remove("dark");
    if (themeIcon) themeIcon.textContent = "🌙";
    if (themeBtn) themeBtn.title = "Switch to Dark Mode";
  } else {
    html.classList.remove("light-theme");
    html.classList.add("dark");
    if (themeIcon) themeIcon.textContent = "☀️";
    if (themeBtn) themeBtn.title = "Switch to Light Mode";
  }
}

function toggleTheme() {
  const current = document.documentElement.classList.contains("light-theme") ? "light" : "dark";
  const newTheme = current === "light" ? "dark" : "light";
  localStorage.setItem("promptlab_theme", newTheme);
  applyTheme(newTheme);
  showToast(`Switched to ${newTheme === "light" ? "Light" : "Dark"} theme`, "info");
}
window.toggleTheme = toggleTheme;

// Apply stored theme on script load
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
  const shortcutsModal = document.getElementById("shortcuts-modal");
  if (shortcutsModal) shortcutsModal.classList.add("hidden");
}
window.closeModal = closeModal;

// ============================================================================
// 5. Global Keyboard Shortcuts Listener
// ============================================================================
document.addEventListener("keydown", (e) => {
  // Ctrl + Enter (or Cmd + Enter): Send Prompt
  if ((e.ctrlKey || e.metaKey) && e.key === "Enter") {
    e.preventDefault();
    const sendBtn =
      document.getElementById("btn-send-prompt") ||
      document.getElementById("send-button") ||
      document.querySelector('#prompt-form button[type="submit"]');
    if (sendBtn && !sendBtn.disabled) {
      sendBtn.click();
    }
  }

  // Ctrl + L (or Cmd + L): Clear current prompt if focused
  if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "l" && !e.shiftKey) {
    const promptInput = document.getElementById("prompt-input");
    if (promptInput && document.activeElement === promptInput) {
      e.preventDefault();
      promptInput.value = "";
      promptInput.dispatchEvent(new Event("input", { bubbles: true }));
      showToast("Prompt cleared", "info");
    }
  }

  // Ctrl + K (or Cmd + K): Focus History Search
  if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "k") {
    e.preventDefault();
    const searchInput = document.querySelector('input[name="q"]');
    if (searchInput) {
      searchInput.focus();
      searchInput.select();
    }
  }

  // Escape: Close modals or clear search focus
  if (e.key === "Escape") {
    const historyModal = document.getElementById("history-detail-modal");
    if (historyModal && historyModal.innerHTML.trim() !== "") {
      historyModal.innerHTML = "";
    }
    const shortcutsModal = document.getElementById("shortcuts-modal");
    if (shortcutsModal && !shortcutsModal.classList.contains("hidden")) {
      shortcutsModal.classList.add("hidden");
    }
  }
});

// ============================================================================
// 6. Auto-resize Textarea & Char/Word/Token Counter Helper
// ============================================================================
function updateCounterAndResize(textarea) {
  if (!textarea) return;

  // Auto-resize
  textarea.style.height = "auto";
  textarea.style.height = Math.max(120, textarea.scrollHeight) + "px";

  // Counters
  const val = textarea.value || "";
  const chars = val.length;
  const words = val.trim().length > 0 ? val.trim().split(/\s+/).length : 0;
  const tokens = Math.ceil(chars / 4);

  const counterEl = document.getElementById("char-count");
  if (counterEl) {
    counterEl.textContent = `${chars.toLocaleString()} chars · ${words.toLocaleString()} words · ~${tokens.toLocaleString()} tokens`;
  }
}
window.updateCounterAndResize = updateCounterAndResize;

// DOMContentLoaded hook for setup
document.addEventListener("DOMContentLoaded", () => {
  // Sync initial theme icons
  applyTheme(getStoredTheme());

  // Attach auto-resize to prompt-input
  const promptInput = document.getElementById("prompt-input");
  if (promptInput) {
    promptInput.addEventListener("input", () => {
      updateCounterAndResize(promptInput);
    });
    updateCounterAndResize(promptInput);
  }
});

// ============================================================================
// 7. Arena Helpers (Pick Winner & Copy)
// ============================================================================
function selectArenaWinner(button, modelName, cardId) {
  const card = document.getElementById(cardId);
  if (!card) return;

  const comparisonContainer = card.closest(".response-card");
  if (comparisonContainer) {
    // Remove previous winner styling from other cards in the same comparison
    comparisonContainer.querySelectorAll(".arena-result-card").forEach((c) => {
      c.classList.remove("ring-2", "ring-emerald-500", "border-emerald-500", "bg-emerald-950/20", "shadow-emerald-500/20");
      const btn = c.querySelector(".pick-winner-btn");
      if (btn) {
        btn.innerHTML = "<span>🏆</span><span>Pick Winner</span>";
        btn.className = "pick-winner-btn inline-flex items-center gap-1 rounded-lg border border-indigo-500/40 bg-indigo-500/10 px-3 py-1 text-xs font-semibold text-indigo-300 hover:bg-indigo-500/20 hover:border-indigo-500/60 transition-all active:scale-95";
      }
    });
  }

  // Highlight winner card
  card.classList.add("ring-2", "ring-emerald-500", "border-emerald-500", "bg-emerald-950/20", "shadow-emerald-500/20");

  button.innerHTML = "<span>🏆</span><span>Winner Chosen!</span>";
  button.className = "pick-winner-btn inline-flex items-center gap-1 rounded-lg border border-emerald-500 bg-emerald-500/20 text-emerald-300 px-3 py-1 text-xs font-bold transition-all shadow-sm";

  if (window.showToast) {
    window.showToast(`Selected ${modelName} as the winner! 🏆`, "success");
  }
}
window.selectArenaWinner = selectArenaWinner;

function copyArenaResponse(button, textareaId, modelName) {
  const textarea = document.getElementById(textareaId);
  if (!textarea) return;

  if (window.copyToClipboard) {
    window.copyToClipboard(textarea.value, `Copied ${modelName} response!`);
  } else {
    navigator.clipboard.writeText(textarea.value);
  }

  const original = button.innerHTML;
  button.innerHTML = "<span>✅</span><span>Copied!</span>";
  button.classList.add("border-emerald-500/40", "text-emerald-300");
  setTimeout(() => {
    button.innerHTML = original;
    button.classList.remove("border-emerald-500/40", "text-emerald-300");
  }, 1800);
}
window.copyArenaResponse = copyArenaResponse;

