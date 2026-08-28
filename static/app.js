/**
 * Frontend logic for Elevate Multi-Agent Portal (WorkWeek HCM & ServiceImmediately ITSM).
 * Incorporates SSO authentication with IdP (login.corp.google.com) and dynamic MCP token minting.
 */

let currentAgentMode = "auto"; // "auto", "workweek", "service_immediately"

document.addEventListener("DOMContentLoaded", async () => {
  await initSSOAndSession();
});

function toggleTokenVisibility() {
  const tokenInput = document.getElementById("mcpTokenInput");
  tokenInput.type = tokenInput.type === "password" ? "text" : "password";
}

function setAgentMode(mode) {
  currentAgentMode = mode;
  document.getElementById("btnModeAuto").classList.toggle("active", mode === "auto");
  document.getElementById("btnModeHcm").classList.toggle("active", mode === "workweek");
  document.getElementById("btnModeItsm").classList.toggle("active", mode === "service_immediately");

  const modeLabels = {
    "auto": "🤖 Auto-Route Mode",
    "workweek": "💼 WorkWeek HCM Mode",
    "service_immediately": "🎫 ServiceImmediately Mode"
  };
  const subtitleLabels = {
    "auto": "Interactive Assistant &bull; Auto-Routing to WorkWeek HCM &amp; ServiceImmediately ITSM",
    "workweek": "Dedicated Specialist &bull; WorkWeek HCM Agent (/work-week/mcp/)",
    "service_immediately": "Dedicated Specialist &bull; ServiceImmediately ITSM Agent (/service-immediately/mcp/)"
  };

  document.getElementById("activeModeChip").innerHTML = `<span class="icon">${mode === "auto" ? "🤖" : (mode === "workweek" ? "💼" : "🎫")}</span> ${modeLabels[mode] || mode}`;
  document.getElementById("activeAgentSubtitle").innerHTML = subtitleLabels[mode] || "";
}

/**
 * Validates SSO authentication / Session and generates or loads
 * a user-bound MCP Token via POST /api/mcp-tokens or local session.
 */
async function initSSOAndSession() {
  try {
    const storedSessionRaw = localStorage.getItem("elevate_session");
    let activeUserLdap = "";

    // 1. Validate SSO status or IAP
    const ssoRes = await fetch("/api/auth/sso-status");
    let ssoData = null;
    if (ssoRes.ok) {
      ssoData = await ssoRes.json();
    }

    // If no session stored and not authenticated via real IAP, redirect to login page
    if (!storedSessionRaw && (!ssoData || ssoData.auth_source !== "GOOGLE_IAP_JWT_VERIFIED")) {
      window.location.href = "/login";
      return;
    }

    let sessionData = ssoData;
    if (storedSessionRaw) {
      try {
        sessionData = JSON.parse(storedSessionRaw);
      } catch (e) {
        console.error("Failed to parse stored session", e);
      }
    }

    if (sessionData) {
      activeUserLdap = sessionData.ldap || "ansonk";
      console.log("Active Session Authenticated:", sessionData);

      // Update UI elements with profile
      const idpBadge = document.getElementById("ssoIdpBadge");
      if (idpBadge) {
        idpBadge.innerText = sessionData.auth_source === "GOOGLE_IAP_JWT_VERIFIED" ? "IAP (JWT Verified)" : (sessionData.idp || "login.corp.google.com");
      }

      const ldapLabel = document.getElementById("ssoLdapLabel");
      if (ldapLabel) ldapLabel.innerText = sessionData.ldap || "ansonk";

      const userName = document.getElementById("userName");
      if (userName) userName.innerText = sessionData.display_name || sessionData.ldap;

      const userRole = document.getElementById("userRole");
      if (userRole) userRole.innerText = sessionData.email || `${sessionData.ldap}@google.com`;

      const userIdBadge = document.getElementById("userIdBadge");
      if (userIdBadge) userIdBadge.innerText = `ID: ${sessionData.employee_id || 'EMP-545'}`;

      const avatar = document.getElementById("userAvatar");
      if (avatar && sessionData.display_name) {
        const initials = sessionData.display_name
          .split(" ")
          .filter(Boolean)
          .map(w => w[0])
          .join("")
          .toUpperCase()
          .slice(0, 2);
        avatar.innerText = initials || "GO";
      }

      // Populate or generate MCP token
      const tokenInput = document.getElementById("mcpTokenInput");
      if (sessionData.token) {
        if (tokenInput) tokenInput.value = sessionData.token;
      } else {
        const tokenRes = await fetch("/api/mcp-tokens", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ ldap: activeUserLdap })
        });
        if (tokenRes.ok) {
          const tokenData = await tokenRes.json();
          if (tokenInput) tokenInput.value = tokenData.token || "";
        }
      }
    }
  } catch (err) {
    console.error("SSO and Token initialization error:", err);
  } finally {
    await syncAllServices();
  }
}

async function handleSignOut() {
  localStorage.removeItem("elevate_session");
  try {
    await fetch("/api/auth/logout", { method: "POST" });
  } catch (e) {}
  window.location.href = "/login";
}

async function syncAllServices() {
  const token = document.getElementById("mcpTokenInput").value.trim();

  try {
    // 1. Fetch HCM Balances
    const balRes = await fetch("/api/hcm/balances", {
      headers: { "X-MCP-Token": token }
    });
    if (balRes.ok) {
      const balData = await balRes.json();
      const text = balData.balances_text || "";
      const vacMatch = text.match(/Vacation:\s*([\d\.]+)\s*days remaining\s*\(([\d\.\/]+)\s*used\)/i);
      const sickMatch = text.match(/Sick:\s*([\d\.]+)\s*days remaining\s*\(([\d\.\/]+)\s*used\)/i);

      if (vacMatch) {
        document.getElementById("vacationRemaining").innerText = `${vacMatch[1]} days`;
        document.getElementById("vacationUsed").innerText = `${vacMatch[2]} used`;
      }
      if (sickMatch) {
        document.getElementById("sickRemaining").innerText = `${sickMatch[1]} days`;
        document.getElementById("sickUsed").innerText = `${sickMatch[2]} used`;
      }
    }

    // 2. Fetch ITSM Tickets
    const itsmRes = await fetch("/api/itsm/tickets", {
      headers: { "X-MCP-Token": token }
    });
    if (itsmRes.ok) {
      const itsmData = await itsmRes.json();
      let tickets = [];
      try {
        tickets = JSON.parse(itsmData.tickets_raw || "[]");
      } catch (e) {
        tickets = [];
      }
      document.getElementById("ticketsCount").innerText = `${tickets.length} Ticket(s)`;
      if (tickets.length > 0) {
        const t = tickets[0];
        document.getElementById("latestTicketSnippet").innerText = `${t.ticket_id}: ${t.short_description}`;
      } else {
        document.getElementById("latestTicketSnippet").innerText = "No active incident tickets.";
      }
    }
  } catch (err) {
    console.error("Failed to sync services:", err);
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
        agent_target: currentAgentMode,
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

    // Refresh counters after action
    syncAllServices();
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
  row.innerHTML = `<div class="agent-bubble"><em>⚡ Multi-Agent Hub is dispatching to specialist MCP server...</em></div>`;
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

  const agentName = data.agent_name || "Specialist Agent";
  const isItsm = agentName.toLowerCase().includes("serviceimmediately") || agentName.toLowerCase().includes("itsm");
  const tagClass = isItsm ? "agent-tag itsm" : "agent-tag";
  const tagIcon = isItsm ? "🎫" : "💼";

  let formattedReply = formatMarkdown(data.reply || data.result || "");
  let html = `
    <div class="agent-bubble">
      <div class="${tagClass}">
        <span>${tagIcon}</span> ${escapeHtml(agentName)} &bull; ${escapeHtml(data.model || "Gemini 3.7 Flash")}
      </div>
      <div>${formattedReply}</div>
  `;

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
        Chat cleared. Ready for new HR/HCM or IT/ITSM inquiries.
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

  // Markdown tables
  if (out.includes('|')) {
    const lines = out.split('\n');
    let inTable = false;
    let tableHtml = '<table>';
    let processedLines = [];

    for (let i = 0; i < lines.length; i++) {
      const line = lines[i].trim();
      if (line.startsWith('|') && line.endsWith('|')) {
        if (!inTable) {
          inTable = true;
          tableHtml = '<table>';
        }
        if (line.includes('---')) {
          continue; // header divider
        }
        const cells = line.split('|').filter((_, idx, arr) => idx > 0 && idx < arr.length - 1);
        const tag = tableHtml === '<table>' ? 'th' : 'td';
        tableHtml += '<tr>' + cells.map(c => `<${tag}>${c.trim()}</${tag}>`).join('') + '</tr>';
      } else {
        if (inTable) {
          inTable = false;
          tableHtml += '</table>';
          processedLines.push(tableHtml);
        }
        processedLines.push(line);
      }
    }
    if (inTable) {
      tableHtml += '</table>';
      processedLines.push(tableHtml);
    }
    out = processedLines.join('\n');
  }

  out = out.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
  out = out.replace(/\*(.*?)\*/g, '<em>$1</em>');
  out = out.replace(/`([^`]+)`/g, '<code>$1</code>');
  out = out.replace(/\n/g, '<br>');
  return out;
}
