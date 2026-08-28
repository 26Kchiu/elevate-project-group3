/**
 * Frontend logic for Elevate Multi-Agent Portal (WorkWeek HCM & ServiceImmediately ITSM).
 * Features: Auto-Model Selection, Multi-Language Alignment, and Speech-to-Text (Voice Input).
 */

let currentAgentMode = "auto"; // "auto", "workweek", "service_immediately"
let currentModelChoice = "auto"; // "auto", "gemini-3.7-flash", "gemini-2.5-flash", etc.
let recognition = null;
let isRecording = false;

document.addEventListener("DOMContentLoaded", () => {
  syncAllServices();
  initSpeechRecognition();
});

function handleModelChange() {
  const selector = document.getElementById("modelSelector");
  currentModelChoice = selector.value;
  const chip = document.getElementById("modelChip");
  if (currentModelChoice === "auto") {
    chip.innerHTML = `<span class="icon">🤖</span> Auto Gemini`;
  } else {
    chip.innerHTML = `<span class="icon">⚡</span> ${currentModelChoice}`;
  }
}

function setAgentMode(mode) {
  currentAgentMode = mode;
  document.getElementById("btnModeAuto").classList.toggle("active", mode === "auto");
  document.getElementById("btnModeHcm").classList.toggle("active", mode === "workweek");
  document.getElementById("btnModeItsm").classList.toggle("active", mode === "service_immediately");

  const subtitleLabels = {
    "auto": "Interactive Assistant &bull; Auto-Routing to WorkWeek HCM &amp; ServiceImmediately ITSM",
    "workweek": "Dedicated Specialist &bull; WorkWeek HCM Agent (/work-week/mcp/)",
    "service_immediately": "Dedicated Specialist &bull; ServiceImmediately ITSM Agent (/service-immediately/mcp/)"
  };

  document.getElementById("activeAgentSubtitle").innerHTML = subtitleLabels[mode] || "";
}

/**
 * Initialize Speech-To-Text (Web Speech API)
 */
function initSpeechRecognition() {
  const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
  if (!SpeechRecognition) {
    console.warn("Speech Recognition API is not supported in this browser.");
    const micBtn = document.getElementById("micBtn");
    if (micBtn) {
      micBtn.title = "Speech-to-Text not supported in this browser (Use Chrome / Edge)";
      micBtn.style.opacity = "0.5";
    }
    return;
  }

  recognition = new SpeechRecognition();
  recognition.continuous = true;
  recognition.interimResults = true;
  // Automatically adapt to user's system/browser language (supports zh-TW, zh-CN, en-US, etc.)
  recognition.lang = navigator.language || "en-US";

  recognition.onstart = () => {
    isRecording = true;
    updateVoiceUI(true);
  };

  recognition.onresult = (event) => {
    let finalTranscript = "";
    let interimTranscript = "";

    for (let i = event.resultIndex; i < event.results.length; ++i) {
      if (event.results[i].isFinal) {
        finalTranscript += event.results[i][0].transcript;
      } else {
        interimTranscript += event.results[i][0].transcript;
      }
    }

    const input = document.getElementById("messageInput");
    if (finalTranscript) {
      input.value = (input.value ? input.value + " " : "") + finalTranscript;
    }
  };

  recognition.onerror = (event) => {
    console.error("Speech recognition error:", event.error);
    stopSpeechRecognition();
  };

  recognition.onend = () => {
    isRecording = false;
    updateVoiceUI(false);
  };
}

function toggleSpeechRecognition() {
  if (!recognition) {
    alert("Speech recognition is not supported in your browser. Please use Google Chrome or Microsoft Edge.");
    return;
  }
  if (isRecording) {
    stopSpeechRecognition();
  } else {
    try {
      recognition.lang = navigator.language || "en-US";
      recognition.start();
    } catch (err) {
      console.error("Error starting speech recognition:", err);
    }
  }
}

function stopSpeechRecognition() {
  if (recognition && isRecording) {
    recognition.stop();
  }
  isRecording = false;
  updateVoiceUI(false);
}

function updateVoiceUI(recording) {
  const micBtn = document.getElementById("micBtn");
  const micIcon = document.getElementById("micIcon");
  const banner = document.getElementById("voiceBanner");

  if (recording) {
    micBtn.classList.add("recording");
    micIcon.innerText = "⏹️";
    banner.style.display = "flex";
  } else {
    micBtn.classList.remove("recording");
    micIcon.innerText = "🎙️";
    banner.style.display = "none";
  }
}

async function syncAllServices() {
  try {
    // 1. Fetch HCM Balances
    const balRes = await fetch("/api/hcm/balances");
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
    const itsmRes = await fetch("/api/itsm/tickets");
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
  if (isRecording) stopSpeechRecognition();

  const input = document.getElementById("messageInput");
  const text = input.value.trim();
  if (!text) return;

  appendUserMessage(text);
  input.value = "";

  const sendBtn = document.getElementById("sendBtn");
  sendBtn.disabled = true;

  const typingId = appendTypingIndicator();

  try {
    const res = await fetch("/api/chat", {
      method: "POST",
      headers: {
        "Content-Type": "application/json"
      },
      body: JSON.stringify({
        message: text,
        agent_target: currentAgentMode,
        model: currentModelChoice
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

    // Refresh dashboard counters
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
  row.innerHTML = `<div class="agent-bubble"><em>⚡ Multi-Agent is analyzing intent and executing SaaS MCP tools...</em></div>`;
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
        <span>${tagIcon}</span> ${escapeHtml(agentName)} &bull; ${escapeHtml(data.model || "Gemini")}
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
        Chat cleared. Ready for new HR/HCM or IT/ITSM inquiries. (支援多國語言與語音輸入)
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
