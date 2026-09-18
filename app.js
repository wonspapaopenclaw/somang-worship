const BULLETIN_INDEX_URL = "./data/bulletins/index.json";
const state = { data: null, bulletins: [], selectedDate: null, selectedTime: null, openHymns: new Set(), openReadings: new Set(), openScriptures: new Set() };

const $ = (selector) => document.querySelector(selector);

async function loadData() {
  const indexResponse = await fetch(BULLETIN_INDEX_URL);
  if (!indexResponse.ok) throw new Error(`주보 목록을 불러오지 못했습니다: ${indexResponse.status}`);
  state.bulletins = await indexResponse.json();
  const requestedDate = new URLSearchParams(window.location.search).get("date");
  const selected = state.bulletins.find((bulletin) => bulletin.date === requestedDate) || state.bulletins[0];
  await selectBulletin(selected.date, false);
}

async function selectBulletin(date, updateUrl = true) {
  const bulletin = state.bulletins.find((item) => item.date === date);
  if (!bulletin) return;
  const response = await fetch(`./data/bulletins/${bulletin.file}`);
  if (!response.ok) throw new Error(`주보 데이터를 불러오지 못했습니다: ${response.status}`);
  state.data = await response.json();
  state.selectedDate = bulletin.date;
  state.selectedTime = state.data.services[0].times[0];
  state.openHymns.clear();
  state.openReadings.clear();
  state.openScriptures.clear();
  if (updateUrl) history.replaceState(null, "", `?date=${encodeURIComponent(bulletin.date)}`);
  render();
}

function escapeHtml(value = "") {
  return String(value).replace(/[&<>'"]/g, (char) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", "'": "&#39;", '"': "&quot;" }[char]));
}

function render() {
  const service = state.data.services[0];
  const bulletinSelect = $("#bulletin-select");
  bulletinSelect.innerHTML = state.bulletins.map((bulletin) => `<option value="${escapeHtml(bulletin.date)}" ${bulletin.date === state.selectedDate ? "selected" : ""}>${escapeHtml(bulletin.label)}</option>`).join("");
  bulletinSelect.onchange = () => selectBulletin(bulletinSelect.value).catch(showError);
  $("#bulletin-picker-status").textContent = `${state.data.issueDate} · 주보 ${state.data.bulletinNumber}호를 보고 있습니다.`;
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

function showError(error) {
  $("#worship-order").innerHTML = `<section class="order-card"><h2>주보를 불러오지 못했습니다.</h2><p class="muted">${escapeHtml(error.message)}</p></section>`;
}

function renderOrderItem(item, index, overrides) {
  const participant = item.participants ? "기도자" : (item.label === "찬양" ? "찬양대" : (item.participant || ""));
  let detail = "";
  if (item.hymn) {
    const open = state.openHymns.has(index);
    const hymnImage = open && item.hymn.image ? `<img class="hymn-image" src="./${item.hymn.image}" alt="찬송가 ${item.hymn.number}장 악보" />` : "";
    detail = `<button class="expand-button hymn-button" type="button" data-expand="hymn" data-index="${index}">${item.hymn.number}장 · ${escapeHtml(item.hymn.title)} ${open ? "▲" : "▼"}</button>${item.note ? `<p class="muted">${escapeHtml(item.note)}</p>` : ""}${hymnImage}`;
  } else if (item.label === "성경봉독") {
    const scripture = variantFor(item) || overrides.scripture || item;
    const open = state.openScriptures.has(index);
    const verseCount = scripture.verses ? scripture.verses.length : 0;
    const scriptureBody = open && verseCount ? `<div class="scripture">${scripture.verses.map((verse) => `<p class="verse"><span class="verse-number">${verse.verse}</span>${escapeHtml(verse.content)}</p>`).join("")}</div>` : (open && !verseCount ? `<p class="muted">본문 데이터가 없습니다.</p>` : "");
    detail = `<button class="expand-button scripture-button" type="button" data-expand="scripture" data-index="${index}">${escapeHtml(scripture.reference || "")} (${verseCount}절) ${open ? "▲" : "▼"}</button>${scriptureBody}`;
  } else if (item.label === "성시교독") {
    const open = state.openReadings.has(index);
    detail = `<button class="expand-button reading-button" type="button" data-expand="reading" data-index="${index}">교독문 ${item.number} · ${escapeHtml(item.reference)} ${open ? "▲" : "▼"}</button>${open ? `<div class="reading-lines">${item.reading.lines.map((line) => `<div class="reading-line ${line.speaker}"><span class="speaker">${speakerLabel(line.speaker)}</span>${escapeHtml(line.text)}</div>`).join("")}</div>` : ""}`;
  } else if (item.label === "찬양") {
    const praise = overrides.praise ? [overrides.praise[0]] : item.items;
    detail = `<div class="detail">${praise.map((value) => `<div>${escapeHtml(value)}</div>`).join("")}</div>`;
    detail += `<p class="muted">${escapeHtml(overrides.praise?.[1] || item.participant || "")}</p>`;
  } else if (item.title || item.timeVariants) {
    const message = variantFor(item) || overrides.message || item;
    detail = `<div class="detail"><strong>${escapeHtml(message.title || "")}</strong>${message.preacher ? `<span class="muted"> · ${escapeHtml(message.preacher)}</span>` : ""}</div>`;
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

function variantFor(item) {
  if (!item.timeVariants || !item.timeVariants.length) return null;
  return item.timeVariants.find((variant) => variant.time === state.selectedTime) || item.timeVariants[0];
}

$("#font-toggle").addEventListener("click", () => {
  const enabled = document.body.classList.toggle("large-type");
  $("#font-toggle").setAttribute("aria-pressed", String(enabled));
});

loadData().catch(showError);
