/**
 * Frontend logic for WorkWeek HCM Agent Web GUI.
 */

document.addEventListener("DOMContentLoaded", () => {
  syncIdentity();
});

function toggleTokenVisibility() {
  const tokenInput = document.getElementById("mcpTokenInput");
  tokenInput.type = tokenInput.type === "password" ? "text" : "password";
}

async function syncIdentity() {
  const token = document.getElementById("mcpTokenInput").value.trim();

  try {
    // 1. Status & Employee ID
    const statusRes = await fetch("/api/status", {
      headers: { "X-MCP-Token": token }
    });
    if (statusRes.ok) {
      const statusData = await statusRes.json();
      if (statusData.mcp_server && statusData.mcp_server.authenticated_employee_id) {
        document.getElementById("userIdBadge").innerText = `ID: ${statusData.mcp_server.authenticated_employee_id}`;
      }
    }

    // 2. Personal Info & Address
    const profRes = await fetch("/api/me/profile", {
      headers: { "X-MCP-Token": token }
    });
    if (profRes.ok) {
      const profData = await profRes.json();
      const raw = profData.raw_output || "";
      const addrMatch = raw.match(/Address:\s*(.*)/i);
      const phoneMatch = raw.match(/Phone:\s*(.*)/i);
      if (addrMatch && addrMatch[1]) {
        document.getElementById("userAddress").innerText = addrMatch[1].trim();
      }
      if (phoneMatch && phoneMatch[1]) {
        document.getElementById("userPhone").innerText = phoneMatch[1].trim();
      }
    }

    // 3. Leave Balances
    const balRes = await fetch("/api/me/balances", {
      headers: { "X-MCP-Token": token }
    });
    if (balRes.ok) {
      const balData = await balRes.json();
      const text = balData.balances_text || "";
      const vacMatch = text.match(/Vacation:\s*([\d\.]+)\s*days remaining\s*\(([\d\.\/]+)\s*used\)/i);
      const sickMatch = text.match(/Sick:\s*([\d\.]+)\s*days remaining\s*\(([\d\.\/]+)\s*used\)/i);

      if (vacMatch) {
        document.getElementById("vacationRemaining").innerText = `${vacMatch[1]} days`;
        document.getElementById("vacationUsed").innerText = `${vacMatch[2]} days used`;
      }
      if (sickMatch) {
        document.getElementById("sickRemaining").innerText = `${sickMatch[1]} days`;
        document.getElementById("sickUsed").innerText = `${sickMatch[2]} days used`;
      }
    }
  } catch (err) {
    console.error("Failed to sync identity:", err);
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
      appendAgentMessage("⚠️ Execution error: " + (err.detail || "Server error"));
      return;
    }

    const data = await res.json();
    appendAgentResponse(data);

    // Refresh balances & profile in sidebar after action
    syncIdentity();
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

function appendTypingIndicator() {
  const stream = document.getElementById("chatStream");
  const row = document.createElement("div");
  const id = "typing-" + Date.now();
  row.id = id;
  row.className = "message-row agent";
  row.innerHTML = `<div class="agent-bubble"><em>⚡ WorkWeek HCM Agent is querying WorkWeek SaaS MCP Server...</em></div>`;
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

  let formattedReply = formatMarkdown(data.reply || data.result || "");
  let html = `<div class="agent-bubble">${formattedReply}`;

  if (data.tool_calls && data.tool_calls.length > 0) {
    for (const tc of data.tool_calls) {
      const argsStr = JSON.stringify(tc.args || {});
      html += `
        <div class="tool-call-badge">
          <span>⚡ <strong>MCP Tool:</strong> <code>${escapeHtml(tc.name)}</code></span>
          <span>&bull; args: <code>${escapeHtml(argsStr)}</code></span>
        </div>
      `;
    }
  }

  html += `</div>`;
  row.innerHTML = html;
  stream.appendChild(row);
  stream.scrollTop = stream.scrollHeight;
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
        Chat cleared. Ready for new leave, balance, or profile inquiries.
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
