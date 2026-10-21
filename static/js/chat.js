// "Ask PlayPath": floating AI chat. Plan questions are answered from her plan (built on the server
// from our database); general sports questions are answered generally. History lives only in memory.
import { api } from "./api.js";
import { $, esc } from "./dom.js";
import { blankProfile, state } from "./state.js";

const SUGGESTIONS = [
  "Which of my matches fits my schedule best?",
  "What should I bring to my first practice?",
  "How can I get less nervous about tryouts?",
];
const history = []; // [{ role: "user" | "assistant", content }]

export function mountChat() {
  const root = document.createElement("div");
  root.id = "chat";
  root.innerHTML = `
    <button type="button" class="chat-open btn" aria-expanded="false" aria-controls="chat-panel">Ask PlayPath</button>
    <section class="chat-panel" id="chat-panel" role="dialog" aria-label="Ask PlayPath" hidden>
      <header class="chat-head">
        <div><strong>Ask PlayPath</strong> <span class="ai-label">AI</span></div>
        <button type="button" class="chat-close ghost small" aria-label="Close chat">Close</button>
      </header>
      <p class="chat-note">Answers come from an AI. Questions about your plan use your matches from our database.
        Don't share personal details like your address or phone number.</p>
      <div class="chat-log" aria-live="polite"></div>
      <div class="chat-suggest">${SUGGESTIONS.map((q) => `<button type="button" class="chip-btn">${esc(q)}</button>`).join("")}</div>
      <form class="chat-form">
        <input name="q" maxlength="1000" autocomplete="off" placeholder="Ask a question…" aria-label="Your question" />
        <button class="btn small" type="submit">Send</button>
      </form>
    </section>`;
  document.body.appendChild(root);

  const panel = $(".chat-panel", root);
  const openBtn = $(".chat-open", root);
  const log = $(".chat-log", root);
  const form = $(".chat-form", root);
  const input = $("input", form);

  const setOpen = (open) => {
    panel.hidden = !open;
    openBtn.hidden = open;
    openBtn.setAttribute("aria-expanded", String(open));
    if (open) input.focus();
  };
  openBtn.addEventListener("click", () => setOpen(true));
  $(".chat-close", root).addEventListener("click", () => setOpen(false));
  document.addEventListener("keydown", (e) => { if (e.key === "Escape" && !panel.hidden) setOpen(false); });

  const bubble = (role, text, extra = "") => {
    log.insertAdjacentHTML("beforeend", `<p class="msg ${role} ${extra}">${esc(text)}</p>`);
    log.scrollTop = log.scrollHeight;
    return log.lastElementChild;
  };

  async function send(question) {
    question = question.trim();
    if (!question) return;
    $(".chat-suggest", root).hidden = true;
    bubble("user", question);
    history.push({ role: "user", content: question });
    const thinking = bubble("assistant", "Thinking…", "pending");
    form.querySelector("button").disabled = true;
    try {
      const { reply } = await api("/api/chat", {
        method: "POST",
        body: { quiz: { ...blankProfile(), ...(state.profile || {}) }, messages: history.slice(-10) },
      });
      thinking.remove();
      bubble("assistant", reply);
      history.push({ role: "assistant", content: reply });
    } catch (err) {
      thinking.remove();
      bubble("assistant", err.message, "error");
      history.pop(); // don't keep a question that never got an answer
    } finally {
      form.querySelector("button").disabled = false;
      input.focus();
    }
  }

  form.addEventListener("submit", (e) => { e.preventDefault(); const q = input.value; input.value = ""; send(q); });
  root.querySelectorAll(".chip-btn").forEach((b) => b.addEventListener("click", () => send(b.textContent)));
}
