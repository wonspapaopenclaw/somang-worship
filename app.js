const DATA_URL = "./data/latest.json";
const state = { data: null, selectedTime: null, openHymns: new Set(), openReadings: new Set(), openScriptures: new Set() };

const $ = (selector) => document.querySelector(selector);

async function loadData() {
  const response = await fetch(DATA_URL);
  if (!response.ok) throw new Error(`주보 데이터를 불러오지 못했습니다: ${response.status}`);
  state.data = await response.json();
  state.selectedTime = state.data.services[0].times[0];
  render();
}

function escapeHtml(value = "") {
  return String(value).replace(/[&<>'"]/g, (char) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", "'": "&#39;", '"': "&quot;" }[char]));
}

function render() {
  const service = state.data.services[0];
  $("#issue-label").textContent = `${state.data.issueDate} · 주보 ${state.data.bulletinNumber}호`;
  $("#source-link").href = state.data.sourcePdf;
  $("#time-tabs").innerHTML = service.times.map((time) => `
    <button class="time-tab" type="button" role="tab" aria-selected="${time === state.selectedTime}" data-time="${time}">${time}</button>
  `).join("");
  document.querySelectorAll(".time-tab").forEach((button) => button.addEventListener("click", () => {
    state.selectedTime = button.dataset.time;
    render();
  }));
  $("#service-summary").innerHTML = `
    <div class="summary-item"><p>선택한 예배</p><strong>${escapeHtml(service.name)} · ${escapeHtml(state.selectedTime)}</strong></div>
    <div class="summary-item"><p>예배 인도</p><strong>${escapeHtml(service.leader)}</strong></div>
  `;
  $("#worship-order").innerHTML = service.order.map((item, index) => renderOrderItem(item, index, service.timeOverrides?.[state.selectedTime] || {})).join("");
  document.querySelectorAll(".expand-button").forEach((button) => button.addEventListener("click", () => {
    const index = Number(button.dataset.index);
    const target = button.dataset.expand === "reading" ? state.openReadings : button.dataset.expand === "scripture" ? state.openScriptures : state.openHymns;
    target.has(index) ? target.delete(index) : target.add(index);
    render();
  }));
}

function renderOrderItem(item, index, overrides) {
  const participant = item.participants ? "기도자" : (item.label === "찬양" ? "찬양대" : (item.participant || ""));
  let detail = "";
  if (item.hymn) {
    const open = state.openHymns.has(index);
    detail = `<button class="expand-button hymn-button" type="button" data-expand="hymn" data-index="${index}">${item.hymn.number}장 · ${escapeHtml(item.hymn.title)} ${open ? "▲" : "▼"}</button>${item.note ? `<p class="muted">${escapeHtml(item.note)}</p>` : ""}${open ? `<img class="hymn-image" src="./${item.hymn.image}" alt="찬송가 ${item.hymn.number}장 악보" />` : ""}`;
  } else if (item.label === "성경봉독") {
    const open = state.openScriptures.has(index);
    detail = `<button class="expand-button scripture-button" type="button" data-expand="scripture" data-index="${index}">${escapeHtml(item.reference)} ${open ? "▲" : "▼"}</button>${open ? `<div class="scripture">${item.verses.map((verse) => `<p class="verse"><span class="verse-number">${verse.verse}</span>${escapeHtml(verse.content)}</p>`).join("")}</div>` : ""}`;
  } else if (item.label === "성시교독") {
    const open = state.openReadings.has(index);
    detail = `<button class="expand-button reading-button" type="button" data-expand="reading" data-index="${index}">교독문 ${item.number} · ${escapeHtml(item.reference)} ${open ? "▲" : "▼"}</button>${open ? `<div class="reading-lines">${item.reading.lines.map((line) => `<div class="reading-line ${line.speaker}"><span class="speaker">${speakerLabel(line.speaker)}</span>${escapeHtml(line.text)}</div>`).join("")}</div>` : ""}`;
  } else if (item.label === "찬양") {
    const praise = overrides.praise ? [overrides.praise[0]] : item.items;
    detail = `<div class="detail">${praise.map((value) => `<div>${escapeHtml(value)}</div>`).join("")}</div>`;
    detail += `<p class="muted">${escapeHtml(overrides.praise?.[1] || item.participant || "")}</p>`;
  } else if (item.title) {
    detail = `<div class="detail"><strong>${escapeHtml(item.title)}</strong>${item.preacher ? `<span class="muted"> · ${escapeHtml(item.preacher)}</span>` : ""}</div>`;
  } else if (item.name) {
    detail = `<div class="detail">${escapeHtml(item.name)}</div>`;
  } else if (item.participants) {
    detail = `<div class="detail">${escapeHtml(overrides.prayer || item.participants)}</div>`;
  }
  return `<article class="order-card"><div class="order-top"><span class="order-label">${escapeHtml(item.label)}</span><span class="participant">${escapeHtml(participant)}</span></div>${detail ? `<div class="detail">${detail}</div>` : ""}</article>`;
}

function speakerLabel(speaker) {
  return { leader: "인도자", congregation: "회중", all: "다같이" }[speaker] || speaker;
}

$("#font-toggle").addEventListener("click", () => {
  const enabled = document.body.classList.toggle("large-type");
  $("#font-toggle").setAttribute("aria-pressed", String(enabled));
});

loadData().catch((error) => {
  $("#worship-order").innerHTML = `<section class="order-card"><h2>주보를 불러오지 못했습니다.</h2><p class="muted">${escapeHtml(error.message)}</p></section>`;
});
