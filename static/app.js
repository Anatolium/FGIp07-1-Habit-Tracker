"use strict";

const els = {
  alert: document.getElementById("alert"),
  todayLabel: document.getElementById("today-label"),
  question: document.getElementById("question"),
  answeredHint: document.getElementById("answered-hint"),
  motivation: document.getElementById("motivation"),
  btnYes: document.getElementById("btn-yes"),
  btnNo: document.getElementById("btn-no"),
  settingsToggle: document.getElementById("settings-toggle"),
  settingsCard: document.getElementById("settings-card"),
  habitInput: document.getElementById("habit-input"),
  habitSave: document.getElementById("habit-save"),
  reminderInput: document.getElementById("reminder-input"),
  reminderSave: document.getElementById("reminder-save"),
  statStreak: document.getElementById("stat-streak"),
  statWins: document.getElementById("stat-wins"),
  statBest: document.getElementById("stat-best"),
  achievements: document.getElementById("achievements"),
  history: document.getElementById("history"),
};

const MONTHS = ["января", "февраля", "марта", "апреля", "мая", "июня",
  "июля", "августа", "сентября", "октября", "ноября", "декабря"];

function showAlert(message) {
  els.alert.textContent = message;
  els.alert.hidden = !message;
}

async function api(url, options) {
  const response = await fetch(url, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  let data = null;
  try {
    data = await response.json();
  } catch (error) {
    data = null;
  }
  if (!response.ok) {
    throw new Error((data && data.error) || "Не удалось выполнить запрос.");
  }
  return data;
}

function formatDate(value) {
  const parts = value.split("-").map(Number);
  return `${parts[2]} ${MONTHS[parts[1] - 1]} ${parts[0]}`;
}

function render(state) {
  els.todayLabel.textContent = "Сегодня " + formatDate(state.today);
  els.question.textContent = `Удалось сегодня ${state.habit.toLowerCase()}?`;

  els.statStreak.textContent = state.stats.current_streak;
  els.statWins.textContent = state.stats.total_wins;
  els.statBest.textContent = state.stats.best_streak;

  els.achievements.innerHTML = "";
  state.achievements.forEach((item) => {
    const badge = document.createElement("div");
    badge.className = "badge" + (item.unlocked ? " unlocked" : "");
    badge.innerHTML =
      `<span class="medal">${item.unlocked ? "🏅" : "🔒"}</span>` +
      `<span><strong>${item.days} дней</strong>` +
      `<small>${item.unlocked ? "Достигнуто" : "Ещё впереди"}</small></span>`;
    els.achievements.appendChild(badge);
  });

  els.history.innerHTML = "";
  state.history.forEach((item) => {
    const day = document.createElement("div");
    day.className = "day " + item.status + (item.day === state.today ? " today" : "");
    day.title = formatDate(item.day) + ": " +
      (item.status === "done" ? "выполнено" : item.status === "miss" ? "пропуск" : "нет ответа");
    day.textContent = item.day.slice(8);
    els.history.appendChild(day);
  });

  const answered = state.today_done !== null && state.today_done !== undefined;
  els.btnYes.classList.toggle("selected", state.today_done === true);
  els.btnNo.classList.toggle("selected", state.today_done === false);
  els.answeredHint.hidden = !answered;
  if (answered) {
    els.answeredHint.textContent = "Сегодня вы ответили: «" +
      (state.today_done ? "Да" : "Нет") + "». Отметку можно изменить.";
  }

  if (answered && state.today_message) {
    els.motivation.textContent = state.today_message;
    els.motivation.hidden = false;
  } else {
    els.motivation.hidden = true;
    els.motivation.textContent = "";
  }

  if (document.activeElement !== els.habitInput) {
    els.habitInput.value = state.habit;
  }
  els.reminderInput.value = state.reminder_time || "";
}

async function refresh() {
  try {
    const state = await api("/api/state");
    showAlert("");
    render(state);
  } catch (error) {
    showAlert(error.message);
  }
}

async function sendAnswer(done) {
  els.btnYes.disabled = true;
  els.btnNo.disabled = true;
  try {
    const state = await api("/api/answer", {
      method: "POST",
      body: JSON.stringify({ done: done }),
    });
    showAlert("");
    render(state);
    if (state.message) {
      els.motivation.textContent = state.message;
      els.motivation.hidden = false;
    }
  } catch (error) {
    showAlert(error.message);
  } finally {
    els.btnYes.disabled = false;
    els.btnNo.disabled = false;
  }
}

els.btnYes.addEventListener("click", () => sendAnswer(true));
els.btnNo.addEventListener("click", () => sendAnswer(false));

els.settingsToggle.addEventListener("click", () => {
  els.settingsCard.hidden = !els.settingsCard.hidden;
  if (!els.settingsCard.hidden) {
    els.habitInput.focus();
  }
});

els.habitSave.addEventListener("click", async () => {
  try {
    const state = await api("/api/habit", {
      method: "POST",
      body: JSON.stringify({ habit: els.habitInput.value }),
    });
    showAlert("");
    render(state);
  } catch (error) {
    showAlert(error.message);
  }
});

els.reminderSave.addEventListener("click", async () => {
  try {
    const state = await api("/api/reminder", {
      method: "POST",
      body: JSON.stringify({ reminder_time: els.reminderInput.value }),
    });
    showAlert("");
    render(state);
  } catch (error) {
    showAlert(error.message);
  }
});

refresh();