// Pokédex — lógica da página. Sem framework: o servidor entrega JSON pronto.
"use strict";

const $ = (sel) => document.querySelector(sel);
const state = {
  current: null,
  shiny: false,
  maxId: 1025,
  ai: false,
  chat: [],          // histórico da conversa com a IA (por Pokémon)
  loadToken: 0,      // evita que uma resposta antiga sobrescreva uma nova
  audio: null,
};

const el = {
  lamp: $("#lamp"), art: $("#artwork"), artScreen: $("#artScreen"), artEmpty: $("#artEmpty"),
  dexNo: $("#dexNo"), name: $("#pkName"), types: $("#pkTypes"), status: $("#status"),
  search: $("#searchInput"), names: $("#names"),
  info: $("#panelInfo"), stats: $("#panelStats"), defense: $("#panelDefense"), evo: $("#panelEvo"),
  aiOn: $("#aiOn"), aiOff: $("#aiOff"), aiLabel: $("#aiLabel"),
  entry: $("#entryText"), narrate: $("#narrateBtn"), voice: $("#voiceToggle"),
  chat: $("#chatLog"), ask: $("#askInput"), shiny: $("#shinyBtn"), file: $("#fileInput"),
};

// ------------------------------------------------------------------ helpers
function h(tag, attrs = {}, ...children) {
  const node = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (v == null || v === false) continue;
    if (k === "class") node.className = v;
    else if (k.startsWith("on")) node.addEventListener(k.slice(2), v);
    else if (k === "style") node.style.cssText = v;
    else node.setAttribute(k, v === true ? "" : v);
  }
  for (const c of children.flat(Infinity)) {
    if (c == null || c === false) continue;
    node.append(c instanceof Node ? c : document.createTextNode(String(c)));
  }
  return node;
}

function isLight(hex) {
  const n = parseInt(hex.slice(1), 16);
  const [r, g, b] = [(n >> 16) & 255, (n >> 8) & 255, n & 255];
  return 0.299 * r + 0.587 * g + 0.114 * b > 165;
}

const chip = (t) => h("span", { class: `chip${isLight(t.color) ? " light" : ""}`, style: `background:${t.color}` }, t.name);

function statColor(v) {
  if (v < 50) return "#d9534a";
  if (v < 80) return "#e8873d";
  if (v < 100) return "#e3c23a";
  if (v < 120) return "#8cc63f";
  return "#2fae66";
}

const fmtMult = (m) => ({ 0: "0×", 0.25: "¼×", 0.5: "½×" }[m] ?? `${m}×`);
const pad = (n) => `#${String(n).padStart(4, "0")}`;
const normalize = (s) => s.trim().toLowerCase().replace(/^#/, "");

function setStatus(message = "", { error = false, suggestions = [] } = {}) {
  el.status.className = `status${error ? " error" : ""}`;
  el.status.replaceChildren(message);
  if (suggestions.length) {
    el.status.append(" Você quis dizer: ");
    suggestions.forEach((s, i) => {
      if (i) el.status.append(", ");
      el.status.append(h("button", { type: "button", onclick: () => load(s) }, s));
    });
    el.status.append("?");
  }
}

function busy(on) { el.lamp.classList.toggle("busy", on); }

async function api(path, options = {}) {
  const res = await fetch(path, {
    ...options,
    headers: { "Content-Type": "application/json", ...(options.headers || {}) },
  });
  const body = await res.json().catch(() => ({}));
  if (!res.ok) {
    const detail = body.detail || {};
    const err = new Error(detail.message || (typeof detail === "string" ? detail : `Erro ${res.status}`));
    err.suggestions = detail.suggestions || [];
    throw err;
  }
  return body;
}

// ------------------------------------------------------------------ carregar
async function load(query) {
  query = normalize(String(query));
  if (!query) return;
  const token = ++state.loadToken;
  busy(true);
  setStatus("Consultando…");
  try {
    const p = await api(`/api/pokemon/${encodeURIComponent(query)}`);
    if (token !== state.loadToken) return;
    state.current = p;
    state.chat = [];
    render(p);
    setStatus("");
    history.replaceState(null, "", `#${p.name}`);
  } catch (e) {
    if (token === state.loadToken) setStatus(e.message, { error: true, suggestions: e.suggestions });
  } finally {
    if (token === state.loadToken) busy(false);
  }
}

function render(p) {
  document.title = `${p.display_name} · Pokédex`;
  el.dexNo.textContent = pad(p.id);
  el.name.textContent = p.display_name;
  el.types.replaceChildren(...p.types.map(chip));
  el.artScreen.style.setProperty("--type-glow", p.types[0].color);
  el.search.value = "";
  showArtwork();
  renderInfo(p);
  renderStats(p);
  renderDefense(p);
  renderEvolution(p);
  resetAi();
}

function showArtwork() {
  const p = state.current;
  const src = (state.shiny && p.shiny_artwork) || p.artwork || p.sprite;
  el.artEmpty.hidden = true;
  el.art.alt = `Arte oficial de ${p.display_name}${state.shiny ? " (shiny)" : ""}`;
  el.art.classList.remove("shown", "reveal");
  el.artScreen.classList.remove("scanning");
  el.art.onload = () => {
    void el.art.offsetWidth; // reinicia a animação
    el.art.classList.add("shown", "reveal");
    el.artScreen.classList.add("scanning");
  };
  el.art.onerror = () => {
    if (el.art.src !== p.sprite && p.sprite) el.art.src = p.sprite;
  };
  el.art.src = src;
}

function renderInfo(p) {
  const s = p.species || {};
  const abilities = p.abilities.map((a, i) => [
    i ? ", " : "",
    a.hidden ? h("span", { class: "hidden-ability" }, `${a.name} (oculta)`) : a.name,
  ]);
  el.info.replaceChildren(
    s.flavor_text ? h("p", { class: "flavor" }, s.flavor_text) : "",
    h("dl", { class: "facts" },
      s.genus ? [h("dt", {}, "Espécie"), h("dd", {}, s.genus)] : [],
      h("dt", {}, "Altura"), h("dd", {}, `${p.height_m.toFixed(1)} m`),
      h("dt", {}, "Peso"), h("dd", {}, `${p.weight_kg.toFixed(1)} kg`),
      h("dt", {}, "Habilidades"), h("dd", {}, abilities),
      s.generation ? [h("dt", {}, "Geração"), h("dd", {}, `${s.generation}ª`)] : [],
      s.capture_rate != null ? [h("dt", {}, "Taxa de captura"), h("dd", {}, `${s.capture_rate} de 255`)] : [],
      (s.legendary || s.mythical) ? [h("dt", {}, ""), h("dd", {},
        s.legendary ? h("span", { class: "tag legendary" }, "Lendário") : "",
        s.mythical ? h("span", { class: "tag mythical" }, "Mítico") : "")] : [],
    ),
  );
}

function renderStats(p) {
  el.stats.replaceChildren(
    ...p.stats.map((s) =>
      h("div", { class: "stat-row" },
        h("span", { class: "label" }, s.label),
        h("span", { class: "value" }, s.value),
        h("div", { class: "bar", role: "img", "aria-label": `${s.label}: ${s.value} de 255` },
          h("span", { style: `width:${(s.value / 255) * 100}%;background:${statColor(s.value)}` })),
      )),
    h("p", { class: "total" }, `Total: ${p.total}`),
  );
}

function renderDefense(p) {
  el.defense.replaceChildren(
    ...p.defense.map((g) =>
      h("div", { class: "def-group" },
        h("div", { class: "def-label" }, g.label, h("small", {}, fmtMult(g.multiplier))),
        h("div", { class: "types" }, g.types.map(chip)),
      )),
  );
}

function renderEvolution(p) {
  const root = p.evolution;
  if (!root || !root.evolves_to.length) {
    el.evo.replaceChildren(h("p", {}, "Este Pokémon não evolui."));
    return;
  }
  const node = (n) => h("button", {
    class: `evo-node${n.name === (p.species?.name ?? p.name) ? " current" : ""}`,
    type: "button",
    title: `Ver ${n.display_name}`,
    onclick: () => load(n.id ?? n.name),
  }, n.artwork ? h("img", { src: n.artwork, alt: "", loading: "lazy" }) : "", n.display_name);

  const build = (n) => {
    if (!n.evolves_to.length) return node(n);
    const steps = n.evolves_to.map((c) =>
      h("div", { class: "evo-step" }, h("span", { class: "evo-arrow" }, c.condition || ""), build(c)));
    return h("div", { class: "evo" }, node(n),
      steps.length > 1 ? h("div", { class: "evo-branches" }, steps) : steps);
  };
  el.evo.replaceChildren(build(root));
}

// ------------------------------------------------------------------ IA
function resetAi() {
  el.entry.textContent = "";
  el.entry.classList.remove("typing");
  el.chat.replaceChildren();
  speechSynthesis?.cancel?.();
}

async function typewrite(target, text) {
  target.textContent = "";
  target.classList.add("typing");
  const reduce = matchMedia("(prefers-reduced-motion: reduce)").matches;
  if (reduce) target.textContent = text;
  else for (const ch of text) {
    target.textContent += ch;
    await new Promise((r) => setTimeout(r, 14));
  }
  target.classList.remove("typing");
}

function speak(text) {
  if (!el.voice.checked || !("speechSynthesis" in window)) return;
  speechSynthesis.cancel();
  const u = new SpeechSynthesisUtterance(text);
  u.lang = "pt-BR";
  u.rate = 1.02;
  u.pitch = 0.9; // um tom levemente mais grave, de aparelho
  const voice = speechSynthesis.getVoices().find((v) => v.lang?.toLowerCase().startsWith("pt"));
  if (voice) u.voice = voice;
  speechSynthesis.speak(u);
}

async function narrate() {
  const p = state.current;
  if (!p) return;
  el.narrate.disabled = true;
  busy(true);
  el.entry.textContent = "Consultando a base de dados…";
  try {
    const { text } = await api(`/api/ai/entry/${p.name}`, { method: "POST" });
    if (state.current !== p) return;
    speak(text);
    await typewrite(el.entry, text);
  } catch (e) {
    el.entry.textContent = "";
    setStatus(e.message, { error: true });
  } finally {
    el.narrate.disabled = false;
    busy(false);
  }
}

async function ask(question) {
  const p = state.current;
  if (!p || !question.trim()) return;
  el.chat.append(h("div", { class: "msg user" }, question));
  const pending = h("div", { class: "msg assistant pending" }, "Pensando…");
  el.chat.append(pending);
  pending.scrollIntoView({ block: "nearest" });
  busy(true);
  try {
    const { text } = await api("/api/ai/ask", {
      method: "POST",
      body: JSON.stringify({ pokemon: p.name, question, history: state.chat }),
    });
    if (state.current !== p) return;
    state.chat.push({ role: "user", content: question }, { role: "assistant", content: text });
    pending.classList.remove("pending");
    pending.textContent = text;
  } catch (e) {
    pending.remove();
    setStatus(e.message, { error: true });
  } finally {
    busy(false);
    pending.scrollIntoView({ block: "nearest" });
  }
}

function readAsDataURL(file) {
  return new Promise((resolve, reject) => {
    const r = new FileReader();
    r.onload = () => resolve(r.result);
    r.onerror = () => reject(new Error("Não consegui ler o arquivo."));
    r.readAsDataURL(file);
  });
}

async function identify(file) {
  if (!state.ai) {
    selectTab("ai");
    setStatus("Para identificar por foto, ligue a IA no arquivo .env.", { error: true });
    return;
  }
  busy(true);
  setStatus("Analisando a imagem…");
  try {
    const image = await readAsDataURL(file);
    const res = await api("/api/ai/identify", { method: "POST", body: JSON.stringify({ image }) });
    const { result } = res;
    if (res.pokemon) {
      await load(res.pokemon);
      const pct = Math.round(result.confianca * 100);
      setStatus(`Identificado com ${pct}% de confiança. ${result.motivo}`);
    } else if (res.suggestions.length) {
      setStatus("Não achei esse nome exato.", { suggestions: res.suggestions });
    } else {
      setStatus(result.motivo || "Não reconheci nenhum Pokémon nessa imagem.", { error: true });
    }
  } catch (e) {
    setStatus(e.message, { error: true });
  } finally {
    busy(false);
    el.file.value = "";
  }
}

// ------------------------------------------------------------------ abas e eventos
function selectTab(name) {
  document.querySelectorAll(".tabs button").forEach((b) => b.setAttribute("aria-selected", String(b.dataset.tab === name)));
  document.querySelectorAll(".panel").forEach((p) => { p.hidden = p.dataset.panel !== name; });
}

document.querySelectorAll(".tabs button").forEach((b) => b.addEventListener("click", () => selectTab(b.dataset.tab)));

$("#searchForm").addEventListener("submit", (e) => { e.preventDefault(); load(el.search.value); });
$("#prevBtn").addEventListener("click", () => state.current?.prev_id && load(state.current.prev_id));
$("#nextBtn").addEventListener("click", () => state.current?.next_id && load(state.current.next_id));
$("#randomBtn").addEventListener("click", () => load(1 + Math.floor(Math.random() * state.maxId)));
$("#cryBtn").addEventListener("click", () => {
  const cry = state.current?.cry;
  if (!cry) return setStatus("Este Pokémon não tem grito disponível.");
  state.audio?.pause();
  state.audio = new Audio(cry);
  state.audio.volume = 0.5;
  state.audio.play().catch(() => setStatus("Não consegui tocar o áudio.", { error: true }));
});
el.shiny.addEventListener("click", () => {
  state.shiny = !state.shiny;
  el.shiny.setAttribute("aria-pressed", String(state.shiny));
  if (state.current) showArtwork();
});
$("#scanBtn").addEventListener("click", () => el.file.click());
el.file.addEventListener("change", () => el.file.files[0] && identify(el.file.files[0]));
el.narrate.addEventListener("click", narrate);
$("#askForm").addEventListener("submit", (e) => {
  e.preventDefault();
  const q = el.ask.value;
  el.ask.value = "";
  ask(q);
});

// arrastar uma imagem para a tela também identifica
el.artScreen.addEventListener("dragover", (e) => e.preventDefault());
el.artScreen.addEventListener("drop", (e) => {
  e.preventDefault();
  const file = [...e.dataTransfer.files].find((f) => f.type.startsWith("image/"));
  if (file) identify(file);
});

document.addEventListener("keydown", (e) => {
  if (e.target.matches("input, textarea") || e.altKey || e.ctrlKey || e.metaKey) return;
  if (e.key === "ArrowLeft") $("#prevBtn").click();
  if (e.key === "ArrowRight") $("#nextBtn").click();
});

window.addEventListener("hashchange", () => {
  const q = decodeURIComponent(location.hash.slice(1));
  if (q && q !== state.current?.name) load(q);
});

// ------------------------------------------------------------------ início
(async function init() {
  try {
    const status = await api("/api/status");
    state.maxId = status.max_id;
    state.ai = status.ai.enabled;
    el.aiOn.hidden = !state.ai;
    el.aiOff.hidden = state.ai;
    el.aiLabel.textContent = state.ai ? `Respostas geradas por IA (${status.ai.label}). Podem conter erros.` : "";
  } catch { /* segue sem IA */ }

  load(decodeURIComponent(location.hash.slice(1)) || "25");

  // a lista de nomes para o autocompletar vem depois, sem travar a página
  api("/api/names").then((names) => {
    el.names.replaceChildren(...names.map((n) => h("option", { value: n })));
  }).catch(() => {});
})();
