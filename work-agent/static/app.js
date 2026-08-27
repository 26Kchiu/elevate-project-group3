// WorkAgent Client Application Logic

const PERSONA_DATA = {
  "EMP-001": {
    name: "Sarah Chen",
    initials: "SC",
    title: "VP People Operations & Staff Engineer",
    badge: "EMP-001 • Sydney, AU"
  },
  "EMP-002": {
    name: "Alex Rivera",
    initials: "AR",
    title: "IT Operations Director",
    badge: "EMP-002 • London, UK"
  },
  "EMP-003": {
    name: "Jordan Lee",
    initials: "JL",
    title: "Senior Product Manager",
    badge: "EMP-003 • Mountain View, US"
  }
};

let currentEmployeeId = "EMP-001";
const userId = "user-" + Math.random().toString(36).substring(2, 9);

document.addEventListener("DOMContentLoaded", () => {
  const select = document.getElementById("personaSelect");
  select.addEventListener("change", (e) => {
    currentEmployeeId = e.target.value;
    updatePersonaCard(currentEmployeeId);
    appendSystemMessage(`Switched active employee context to <strong>${PERSONA_DATA[currentEmployeeId].name} (${currentEmployeeId})</strong>.`);
  });
});

function updatePersonaCard(empId) {
  const data = PERSONA_DATA[empId] || PERSONA_DATA["EMP-001"];
  document.getElementById("empAvatar").innerText = data.initials;
  document.getElementById("empName").innerText = data.name;
  document.getElementById("empTitle").innerText = data.title;
  document.getElementById("empIdBadge").innerText = data.badge;
}

function sendQuickPrompt(text) {
  document.getElementById("messageInput").value = text;
  handleFormSubmit(new Event("submit"));
}

function handleKeyDown(e) {
  if (e.key === "Enter" && !e.shiftKey) {
    e.preventDefault();
    handleFormSubmit(e);
  }
}

async function handleFormSubmit(e) {
  if (e) e.preventDefault();
  const input = document.getElementById("messageInput");
  const text = input.value.trim();
  if (!text) return;

  appendUserMessage(text);
  input.value = "";

  const sendBtn = document.getElementById("sendBtn");
  sendBtn.disabled = true;

  // Add typing indicator
  const typingId = appendTypingIndicator();

  try {
    const res = await fetch("/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        user_id: userId,
        employee_id: currentEmployeeId,
        message: text
      })
    });

    removeMessage(typingId);

    if (!res.ok) {
      const err = await res.json();
      appendAgentMessage("⚠️ Error: " + (err.detail || "Server error"));
      return;
    }

    const data = await res.json();
    appendAgentResponse(data);
  } catch (err) {
    removeMessage(typingId);
    appendAgentMessage("⚠️ Network error: " + err.message);
  } finally {
    sendBtn.disabled = false;
  }
}

function appendUserMessage(text) {
  const stream = document.getElementById("chatStream");
  const row = document.createElement("div");
  row.className = "message-row user";
  row.innerHTML = `<div class="user-bubble">${escapeHtml(text)}</div>`;
  stream.appendChild(row);
  stream.scrollTop = stream.scrollHeight;
}

function appendSystemMessage(htmlText) {
  const stream = document.getElementById("chatStream");
  const row = document.createElement("div");
  row.className = "message-row system";
  row.innerHTML = `<div class="system-bubble">${htmlText}</div>`;
  stream.appendChild(row);
  stream.scrollTop = stream.scrollHeight;
}

function appendTypingIndicator() {
  const stream = document.getElementById("chatStream");
  const row = document.createElement("div");
  const id = "typing-" + Date.now();
  row.id = id;
  row.className = "message-row agent";
  row.innerHTML = `<div class="agent-bubble"><em>WorkAgent is querying WorkWeek SaaS...</em></div>`;
  stream.appendChild(row);
  stream.scrollTop = stream.scrollHeight;
  return id;
}

function removeMessage(id) {
  const elem = document.getElementById(id);
  if (elem) elem.remove();
}

function appendAgentResponse(data) {
  const stream = document.getElementById("chatStream");
  const row = document.createElement("div");
  row.className = "message-row agent";

  let formattedReply = formatMarkdown(data.reply);
  let html = `<div class="agent-bubble">${formattedReply}`;

  // If tool calls were made, render structured SoR banner
  if (data.tool_calls && data.tool_calls.length > 0) {
    for (const tc of data.tool_calls) {
      html += `
        <div class="tool-call-card">
          <div class="tool-call-header">
            <span>⚡ Tool Executed: ${escapeHtml(tc.name)}</span>
            <span>WorkWeek HCM Live</span>
          </div>
        </div>
      `;
    }
  }

  // If a confirmation card was staged, render the interactive card
  if (data.confirmation_card) {
    const card = data.confirmation_card;
    const staged = card.staged_request || card.staged_update || {};
    html += `
      <div class="confirmation-card" id="card-${card.confirmation_token}">
        <div class="confirm-header">
          <span>⚠️ Action Confirmation Required (SDD Section 4.2)</span>
        </div>
        <div class="confirm-details">
          <div><strong>Action:</strong> ${escapeHtml(card.action_required || "Submit Leave")}</div>
          <div><strong>Employee:</strong> ${escapeHtml(staged.employee_id || currentEmployeeId)}</div>
          <div><strong>Leave Type:</strong> ${escapeHtml(staged.leave_type || "N/A")}</div>
          <div><strong>Dates:</strong> ${escapeHtml(staged.start_date || "")} to ${escapeHtml(staged.end_date || "")}</div>
          <div class="confirm-token-badge">Token: ${escapeHtml(card.confirmation_token)} (SHA-256 bound)</div>
        </div>
        <div class="confirm-actions">
          <button class="btn btn-confirm btn-sm" onclick="executeConfirmation('${card.confirmation_token}', '${escapeHtml(JSON.stringify(staged))}')">Confirm &amp; Execute</button>
          <button class="btn btn-cancel btn-sm" onclick="cancelConfirmation('${card.confirmation_token}')">Cancel</button>
        </div>
      </div>
    `;
  }

  html += `</div>`;
  row.innerHTML = html;
  stream.appendChild(row);
  stream.scrollTop = stream.scrollHeight;
}

async function executeConfirmation(token, stagedJsonStr) {
  const staged = JSON.parse(stagedJsonStr);
  const cardElem = document.getElementById("card-" + token);
  if (cardElem) {
    cardElem.innerHTML = `<div style="color: #10B981;"><em>Executing verified transaction with token ${token}...</em></div>`;
  }

  appendUserMessage(`Confirming action with token ${token}`);

  try {
    const res = await fetch("/api/confirm", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        action: "submit_leave_request",
        confirmation_token: token,
        payload: staged
      })
    });

    const data = await res.json();
    if (data.receipt) {
      appendAgentMessage(`
        ✅ <strong>Transaction Committed Successfully to WorkWeek HCM</strong><br>
        • <strong>Reference ID:</strong> <code>${data.receipt.reference}</code><br>
        • <strong>Days Deducted:</strong> ${data.receipt.days_deducted} days<br>
        • <strong>Remaining Balance:</strong> ${data.receipt.remaining_balance} days<br>
        • <strong>Committed At:</strong> ${data.receipt.committed_at}
      `);
    } else {
      appendAgentMessage(`❌ Action failed: ${JSON.stringify(data)}`);
    }
  } catch (err) {
    appendAgentMessage(`❌ Confirmation error: ${err.message}`);
  }
}

function cancelConfirmation(token) {
  const cardElem = document.getElementById("card-" + token);
  if (cardElem) {
    cardElem.innerHTML = `<div style="color: #EF4444;"><em>Action cancelled by user. Token ${token} invalidated.</em></div>`;
  }
}

function appendAgentMessage(html) {
  const stream = document.getElementById("chatStream");
  const row = document.createElement("div");
  row.className = "message-row agent";
  row.innerHTML = `<div class="agent-bubble">${html}</div>`;
  stream.appendChild(row);
  stream.scrollTop = stream.scrollHeight;
}

function clearChat() {
  const stream = document.getElementById("chatStream");
  stream.innerHTML = `
    <div class="message-row system">
      <div class="system-bubble">
        Chat cleared. Ready for new inquiries for <strong>${PERSONA_DATA[currentEmployeeId].name}</strong>.
      </div>
    </div>
  `;
}

function escapeHtml(str) {
  if (!str) return "";
  return String(str).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}

function formatMarkdown(text) {
  if (!text) return "";
  let out = escapeHtml(text);
  out = out.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
  out = out.replace(/\*(.*?)\*/g, '<em>$1</em>');
  out = out.replace(/`([^`]+)`/g, '<code>$1</code>');
  out = out.replace(/\n/g, '<br>');
  return out;
}
