const API = "http://127.0.0.1:8000";

const topicInput = document.getElementById("topic-input");
const topicsList = document.getElementById("topics-list");
const startBtn = document.getElementById("start-btn");
const quizForm = document.getElementById("quiz-form");
const questionsContainer = document.getElementById("questions-container");
const submitBtn = document.getElementById("submit-btn");
const retryBtn = document.getElementById("retry-btn");
const scoreBanner = document.getElementById("score-banner");
const errorEl = document.getElementById("error");
const spinner = document.getElementById("spinner");

let currentQuestions = [];
let currentTopic = "";

async function fetchJSON(url, options) {
  const res = await fetch(url, options);
  const data = await res.json();
  if (!res.ok) throw new Error(data.detail || "Request failed");
  return data;
}

function showError(msg) {
  errorEl.textContent = msg;
  errorEl.style.display = "block";
}

function clearError() {
  errorEl.style.display = "none";
}

function setLoading(on) {
  spinner.style.display = on ? "block" : "none";
  startBtn.disabled = on;
  submitBtn.disabled = on;
}

async function loadTopics() {
  try {
    const data = await fetchJSON(`${API}/topics`);
    topicsList.innerHTML = data.topics
      .map((t) => `<option value="${t}">`)
      .join("");
  } catch {
  }
}

const LABELS = ["A", "B", "C", "D"];

function renderQuestions(questions) {
  questionsContainer.innerHTML = questions
    .map(
      (q) => `
      <div class="question-block" data-id="${q.id}">
        <p>${q.id + 1}. ${q.question}</p>
        ${q.options
          .map(
            (opt, i) => `
          <label class="option">
            <input type="radio" name="q${q.id}" value="${i}" required />
            <strong>${LABELS[i]}.</strong>&nbsp;${opt}
          </label>`
          )
          .join("")}
      </div>`
    )
    .join("");
}

function showResults(results, score, total) {
  quizForm.querySelectorAll("input").forEach((el) => (el.disabled = true));
  submitBtn.style.display = "none";
  retryBtn.style.display = "inline-block";

  results.forEach(({ id, chosen, correct, explanation }) => {
    const block = questionsContainer.querySelector(`[data-id="${id}"]`);
    const labels = block.querySelectorAll(".option");

    labels.forEach((label, i) => {
      if (i === correct && i === chosen) label.classList.add("correct");
      else if (i === chosen) label.classList.add("wrong");
      else if (i === correct) label.classList.add("missed");
    });

    if (explanation) {
      const p = document.createElement("p");
      p.className = "explanation";
      p.textContent = explanation;
      block.appendChild(p);
    }
  });

  const pct = score / total;
  scoreBanner.textContent = `You scored ${score} / ${total} — ${Math.round(pct * 100)}%`;
  scoreBanner.className = pct >= 0.8 ? "good" : pct >= 0.5 ? "ok" : "low";
  scoreBanner.style.display = "block";
  scoreBanner.scrollIntoView({ behavior: "smooth", block: "nearest" });
}

startBtn.addEventListener("click", async () => {
  const topic = topicInput.value.trim();
  if (!topic) {
    showError("Please enter a topic.");
    topicInput.focus();
    return;
  }

  clearError();
  currentTopic = topic;

  setLoading(true);
  try {
    const data = await fetchJSON(`${API}/generate-quiz`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ topic }),
    });
    currentQuestions = data.questions;
    renderQuestions(currentQuestions);
    quizForm.style.display = "block";
    submitBtn.style.display = "inline-block";
    retryBtn.style.display = "none";
    scoreBanner.style.display = "none";
  } catch (e) {
    showError(e.message);
  } finally {
    setLoading(false);
  }
});

quizForm.addEventListener("submit", async (e) => {
  e.preventDefault();
  clearError();

  const answers = {};
  currentQuestions.forEach((q) => {
    const checked = quizForm.querySelector(`input[name="q${q.id}"]:checked`);
    if (checked) answers[q.id] = parseInt(checked.value);
  });

  setLoading(true);
  try {
    const data = await fetchJSON(`${API}/score`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ topic: currentTopic, answers, questions: currentQuestions }),
    });
    showResults(data.results, data.score, data.total);
  } catch (e) {
    showError(e.message);
  } finally {
    setLoading(false);
  }
});

retryBtn.addEventListener("click", () => {
  quizForm.style.display = "none";
  retryBtn.style.display = "none";
  scoreBanner.style.display = "none";
  clearError();
  topicInput.focus();
});

loadTopics();
