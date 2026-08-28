// Dynamic WorkAgent Client Logic

let activeEmployeeId = "";

document.addEventListener("DOMContentLoaded", async () => {
  try {
    const ssoRes = await fetch("/api/auth/sso-status");
    if (ssoRes.ok) {
      const ssoData = await ssoRes.json();
      const ldap = ssoData.ldap || "ansonk";
      const tokenRes = await fetch("/api/mcp-tokens", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ ldap: ldap })
      });
      if (tokenRes.ok) {
        const tokenData = await tokenRes.json();
        const input = document.getElementById("mcpTokenInput");
        if (input) input.value = tokenData.token || "";
      }
    }
  } catch (e) {
    console.error("SSO initialization error:", e);
  }
  loadProfileFromToken();
});

function toggleTokenVisibility() {
  const input = document.getElementById("mcpTokenInput");
  input.type = input.type === "password" ? "text" : "password";
}

async function loadProfileFromToken() {
  const token = document.getElementById("mcpTokenInput").value.trim();
  document.getElementById("userName").innerText = "Resolving...";
  document.getElementById("userRole").innerText = "Querying WorkWeek MCP...";

  try {
    const res = await fetch("/api/me/profile", {
      headers: { "X-MCP-Token": token }
    });
    if (res.ok) {
      const data = await res.json();
      activeEmployeeId = data.employee_id;
      const initials = (data.first_name ? data.first_name[0] : "") + (data.last_name ? data.last_name[0] : (data.name ? data.name[0] : "U"));
      document.getElementById("userAvatar").innerText = initials.toUpperCase() || "WW";
      document.getElementById("userName").innerText = data.name || "Authenticated User";
      document.getElementById("userRole").innerText = data.role || "Enterprise Member";
      document.getElementById("userIdBadge").innerText = `${data.employee_id} • ${data.email}`;
      appendSystemMessage(`Dynamic identity synced: <strong>${data.name} (${data.employee_id})</strong> via WorkWeek MCP.`);
    } else {
      document.getElementById("userName").innerText = "Session Active";
      document.getElementById("userRole").innerText = "MCP Token Configured";
    }
  } catch (err) {
    document.getElementById("userName").innerText = "WorkWeek User";
  }
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

  const typingId = appendTypingIndicator();
  const token = document.getElementById("mcpTokenInput").value.trim();

  try {
    const res = await fetch("/api/chat", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-MCP-Token": token
      },
      body: JSON.stringify({
        message: text,
        mcp_token: token
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
  row.innerHTML = `<div class="agent-bubble"><em>WorkAgent is querying WorkWeek MCP Server...</em></div>`;
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

  if (data.tool_calls && data.tool_calls.length > 0) {
    for (const tc of data.tool_calls) {
      html += `
        <div class="tool-call-card">
          <div class="tool-call-header">
            <span>⚡ MCP Tool: ${escapeHtml(tc.name)}</span>
            <span>WorkWeek Server (/work-week/mcp/)</span>
          </div>
        </div>
      `;
    }
  }

  if (data.confirmation_card) {
    const card = data.confirmation_card;
    const staged = card.staged_request || card.staged_update || {};
    html += `
      <div class="confirmation-card" id="card-${card.confirmation_token}">
        <div class="confirm-header">
          <span>⚠️ Action Confirmation Required (SDD Section 4.2)</span>
        </div>
        <div class="confirm-details">
          <div><strong>Action:</strong> ${escapeHtml(card.action_required || "Book Time Off")}</div>
          <div><strong>Employee ID:</strong> ${escapeHtml(staged.employee_id || activeEmployeeId)}</div>
          <div><strong>Leave Type:</strong> ${escapeHtml(staged.leave_type || "vacation")}</div>
          <div><strong>Dates:</strong> ${escapeHtml(staged.start_date || "")} to ${escapeHtml(staged.end_date || "")}</div>
          <div><strong>Days:</strong> ${escapeHtml(staged.days || 1)} days</div>
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
    cardElem.innerHTML = `<div style="color: #10B981;"><em>Executing verified transaction via WorkWeek MCP Server...</em></div>`;
  }

  appendUserMessage(`Confirming transaction with token ${token}`);
  const mcpTok = document.getElementById("mcpTokenInput").value.trim();

  try {
    const res = await fetch("/api/confirm", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-MCP-Token": mcpTok
      },
      body: JSON.stringify({
        action: "request_time_off",
        confirmation_token: token,
        payload: staged,
        mcp_token: mcpTok
      })
    });

    const data = await res.json();
    if (data.receipt) {
      appendAgentMessage(`
        ✅ <strong>Time-Off Request Committed via WorkWeek MCP Server</strong><br>
        • <strong>Request ID:</strong> <code>${data.receipt.request_id}</code><br>
        • <strong>Leave Type:</strong> ${data.receipt.leave_type}<br>
        • <strong>Days Deducted:</strong> ${data.receipt.days_deducted} days<br>
        • <strong>Remaining Balance:</strong> ${data.receipt.remaining_balance} days<br>
        • <strong>Committed At:</strong> ${data.receipt.committed_at}
      `);
    } else {
      appendAgentMessage(`❌ Transaction failed: ${JSON.stringify(data)}`);
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
        Chat cleared. Ready for new inquiries via WorkWeek MCP.
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
