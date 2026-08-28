/**
 * Frontend logic for Elevate Multi-Agent Portal (WorkWeek HCM & ServiceImmediately ITSM).
 * Features: Auto-Model Selection, Model Auto-Language Alignment, Real-Time Speech-to-Text with 1-Click Lang Pill.
 */

let currentAgentMode = "auto";
let currentModelChoice = "auto";
let recognition = null;
let isRecording = false;
let basePromptText = "";

const VOICE_LANGS = [
  { code: "zh-TW", label: "🇹🇼 中文" },
  { code: "en-US", label: "🇺🇸 EN" },
  { code: "zh-CN", label: "🇨🇳 简中" },
  { code: "ja-JP", label: "🇯🇵 日語" }
];
let currentVoiceLangIndex = 0;

document.addEventListener("DOMContentLoaded", () => {
  syncAllServices();
  initSpeechRecognition();
});

function cycleVoiceLanguage() {
  currentVoiceLangIndex = (currentVoiceLangIndex + 1) % VOICE_LANGS.length;
  const currentLang = VOICE_LANGS[currentVoiceLangIndex];
  const pill = document.getElementById("voiceLangPill");
  if (pill) {
    pill.innerText = currentLang.label;
  }
  if (recognition) {
    recognition.lang = currentLang.code;
  }
  const statusText = document.getElementById("voiceStatusText");
  if (statusText && isRecording) {
    statusText.innerText = `Listening in ${currentLang.label}... Please speak into your microphone`;
  }
}

function handleModelChange() {
  const selector = document.getElementById("modelSelector");
  if (selector) {
    currentModelChoice = selector.value;
  }
  const chip = document.getElementById("modelChip");
  if (chip) {
    if (currentModelChoice === "auto") {
      chip.innerHTML = `<span class="icon">🤖</span> Auto Gemini`;
    } else {
      chip.innerHTML = `<span class="icon">⚡</span> ${escapeHtml(currentModelChoice)}`;
    }
  }
}

function setAgentMode(mode) {
  currentAgentMode = mode;
  const btnAuto = document.getElementById("btnModeAuto");
  const btnHcm = document.getElementById("btnModeHcm");
  const btnItsm = document.getElementById("btnModeItsm");

  if (btnAuto) btnAuto.classList.toggle("active", mode === "auto");
  if (btnHcm) btnHcm.classList.toggle("active", mode === "workweek");
  if (btnItsm) btnItsm.classList.toggle("active", mode === "service_immediately");

  const subtitleLabels = {
    "auto": "Interactive Assistant &bull; Auto-Routing to WorkWeek HCM &amp; ServiceImmediately ITSM",
    "workweek": "Dedicated Specialist &bull; WorkWeek HCM Agent (/work-week/mcp/)",
    "service_immediately": "Dedicated Specialist &bull; ServiceImmediately ITSM Agent (/service-immediately/mcp/)"
  };

  const subtitle = document.getElementById("activeAgentSubtitle");
  if (subtitle) {
    subtitle.innerHTML = subtitleLabels[mode] || "";
  }
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
      micBtn.title = "Speech-to-Text not supported in this browser (Use Google Chrome or Edge)";
      micBtn.style.opacity = "0.5";
    }
    return;
  }

  try {
    recognition = new SpeechRecognition();
    recognition.continuous = true;
    recognition.interimResults = true;
    recognition.maxAlternatives = 1;
    recognition.lang = VOICE_LANGS[currentVoiceLangIndex].code;

    recognition.onstart = () => {
      isRecording = true;
      const input = document.getElementById("messageInput");
      basePromptText = input ? input.value.trim() : "";
      updateVoiceUI(true);
    };

    recognition.onresult = (event) => {
      let interimTranscript = "";
      let finalTranscript = "";

      for (let i = event.resultIndex; i < event.results.length; ++i) {
        const transcript = event.results[i][0].transcript;
        if (event.results[i].isFinal) {
          finalTranscript += transcript;
        } else {
          interimTranscript += transcript;
        }
      }

      if (finalTranscript) {
        basePromptText = (basePromptText ? basePromptText + " " : "") + finalTranscript.trim();
      }

      const input = document.getElementById("messageInput");
      if (input) {
        const displayText = basePromptText + (interimTranscript ? (basePromptText ? " " : "") + interimTranscript : "");
        input.value = displayText;
        input.scrollTop = input.scrollHeight;
      }
    };

    recognition.onerror = (event) => {
      console.warn("Speech recognition event:", event.error);
      const statusText = document.getElementById("voiceStatusText");
      if (event.error === "no-speech") {
        if (statusText) statusText.innerText = "No voice heard yet. Please speak clearly into your microphone...";
      } else if (event.error === "not-allowed") {
        alert("Microphone permission was denied. Please allow microphone access in your browser address bar.");
        stopSpeechRecognition();
      } else {
        stopSpeechRecognition();
      }
    };

    recognition.onend = () => {
      isRecording = false;
      updateVoiceUI(false);
    };
  } catch (err) {
    console.error("Error setting up speech recognition:", err);
  }
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
      recognition.lang = VOICE_LANGS[currentVoiceLangIndex].code;
      recognition.start();
    } catch (err) {
      console.error("Error starting speech recognition:", err);
    }
  }
}

function stopSpeechRecognition() {
  if (recognition && isRecording) {
    try {
      recognition.stop();
    } catch (e) {}
  }
  isRecording = false;
  updateVoiceUI(false);
}

function updateVoiceUI(recording) {
  const micBtn = document.getElementById("micBtn");
  const micIcon = document.getElementById("micIcon");
  const banner = document.getElementById("voiceBanner");
  const statusText = document.getElementById("voiceStatusText");
  const currentLang = VOICE_LANGS[currentVoiceLangIndex];

  if (recording) {
    if (micBtn) micBtn.classList.add("recording");
    if (micIcon) micIcon.innerText = "⏹️";
    if (statusText) {
      statusText.innerText = `Listening in ${currentLang.label}... Speak your question (點擊 ⏹️ 完成)`;
    }
    if (banner) banner.style.display = "flex";
  } else {
    if (micBtn) micBtn.classList.remove("recording");
    if (micIcon) micIcon.innerText = "🎙️";
    if (banner) banner.style.display = "none";
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

      const vacElem = document.getElementById("vacationRemaining");
      const vacUsedElem = document.getElementById("vacationUsed");
      const sickElem = document.getElementById("sickRemaining");
      const sickUsedElem = document.getElementById("sickUsed");

      if (vacMatch && vacElem) vacElem.innerText = `${vacMatch[1]} days`;
      if (vacMatch && vacUsedElem) vacUsedElem.innerText = `${vacMatch[2]} used`;
      if (sickMatch && sickElem) sickElem.innerText = `${sickMatch[1]} days`;
      if (sickMatch && sickUsedElem) sickUsedElem.innerText = `${sickMatch[2]} used`;
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
      const countElem = document.getElementById("ticketsCount");
      const snippetElem = document.getElementById("latestTicketSnippet");

      if (countElem) countElem.innerText = `${tickets.length} Ticket(s)`;
      if (snippetElem) {
        if (tickets.length > 0) {
          const t = tickets[0];
          snippetElem.innerText = `${t.ticket_id}: ${t.short_description}`;
        } else {
          snippetElem.innerText = "No active incident tickets.";
        }
      }
    }
  } catch (err) {
    console.error("Failed to sync services:", err);
  }
}

function sendQuickPrompt(text) {
  const input = document.getElementById("messageInput");
  if (input) {
    input.value = text;
  }
  handleFormSubmit(new Event("submit"));
}

function handleKeyDown(e) {
  if (e.key === "Enter" && !e.shiftKey) {
    e.preventDefault();
    handleFormSubmit(e);
  }
}

async function handleFormSubmit(e) {
  if (e && e.preventDefault) e.preventDefault();
  if (isRecording) stopSpeechRecognition();

  const input = document.getElementById("messageInput");
  if (!input) return;
  const text = input.value.trim();
  if (!text) return;

  appendUserMessage(text);
  input.value = "";
  basePromptText = "";

  const sendBtn = document.getElementById("sendBtn");
  if (sendBtn) sendBtn.disabled = true;

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
    if (sendBtn) sendBtn.disabled = false;
  }
}

function appendUserMessage(text) {
  const stream = document.getElementById("chatStream");
  if (!stream) return;
  const row = document.createElement("div");
  row.className = "message-row user";
  row.innerHTML = `<div class="user-bubble">${escapeHtml(text)}</div>`;
  stream.appendChild(row);
  stream.scrollTop = stream.scrollHeight;
}

function appendTypingIndicator() {
  const stream = document.getElementById("chatStream");
  if (!stream) return "typing-dummy";
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
  if (!stream) return;
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
  if (!stream) return;
  const row = document.createElement("div");
  row.className = "message-row agent";
  row.innerHTML = `<div class="agent-bubble">${html}</div>`;
  stream.appendChild(row);
  stream.scrollTop = stream.scrollHeight;
}

function clearChat() {
  const stream = document.getElementById("chatStream");
  if (stream) {
    stream.innerHTML = `
      <div class="message-row system">
        <div class="system-bubble">
          Chat cleared. Ready for new HR/HCM or IT/ITSM inquiries. (支援自動語言偵測與語音輸入)
        </div>
      </div>
    `;
  }
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
