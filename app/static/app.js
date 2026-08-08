// --- Recherche de vidéos virales ---
const searchBtn = document.getElementById("search-btn");
if (searchBtn) {
  searchBtn.addEventListener("click", async () => {
    const msg = document.getElementById("search-msg");
    const box = document.getElementById("search-results");
    msg.classList.add("hidden");
    box.innerHTML = "";
    const query = document.getElementById("search-query").value.trim();
    if (!query) {
      msg.textContent = "Entre un thème de recherche.";
      msg.classList.remove("hidden");
      return;
    }
    searchBtn.disabled = true;
    searchBtn.textContent = "⏳ Recherche...";
    try {
      const res = await fetch("/api/search", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          query,
          duration: document.getElementById("search-duration").value,
          recency_days: document.getElementById("search-recency").value,
        }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.error || "Erreur");
      if (!data.results.length) {
        box.innerHTML = '<p class="muted small" style="margin-top:12px">Aucune vidéo trouvée. Essaie d\'autres mots-clés.</p>';
        return;
      }
      renderSearchResults(data.results, box);
    } catch (err) {
      msg.textContent = err.message;
      msg.classList.remove("hidden");
    } finally {
      searchBtn.disabled = false;
      searchBtn.textContent = "🔎 Rechercher";
    }
  });
}

function fmtViews(n) {
  if (n >= 1e6) return (n / 1e6).toFixed(1) + "M";
  if (n >= 1e3) return (n / 1e3).toFixed(0) + "k";
  return String(n);
}
function fmtDur(s) {
  const m = Math.floor(s / 60);
  return m >= 60 ? `${Math.floor(m / 60)}h${String(m % 60).padStart(2, "0")}` : `${m} min`;
}
function esc(s) {
  const d = document.createElement("div");
  d.textContent = s || "";
  return d.innerHTML;
}

function renderSearchResults(results, box) {
  box.innerHTML = '<div class="search-grid"></div>';
  const grid = box.querySelector(".search-grid");
  results.forEach((v, i) => {
    const card = document.createElement("div");
    card.className = "search-card";
    card.innerHTML = `
      <img src="${v.thumbnail}" alt="" loading="lazy">
      <div class="search-body">
        <div class="viral-badge">🔥 ${fmtViews(v.views_per_day)}/jour</div>
        <h4>${esc(v.title)}</h4>
        <p class="muted small">${esc(v.channel)} · ${fmtViews(v.views)} vues · ${fmtDur(v.duration_sec)} · ${v.published}</p>
        <button class="use-btn" type="button">✂️ Utiliser cette vidéo</button>
      </div>`;
    card.querySelector(".use-btn").addEventListener("click", () => {
      const urlField = document.querySelector('#job-form [name="url"]');
      urlField.value = v.url;
      urlField.scrollIntoView({ behavior: "smooth", block: "center" });
      urlField.focus();
    });
    grid.appendChild(card);
  });
}

// --- Formulaire de création de job (page d'accueil) ---
const form = document.getElementById("job-form");
if (form) {
  const modeSelect = document.getElementById("mode-select");
  const manualBlock = document.getElementById("manual-block");
  modeSelect.addEventListener("change", () => {
    manualBlock.classList.toggle("hidden", modeSelect.value !== "manual");
  });

  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    const btn = document.getElementById("submit-btn");
    const errEl = document.getElementById("form-error");
    errEl.classList.add("hidden");
    btn.disabled = true;
    btn.textContent = "⏳ Lancement...";

    const fd = new FormData(form);
    try {
      const res = await fetch("/api/jobs", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          url: fd.get("url"),
          mode: fd.get("mode"),
          framing: fd.get("framing"),
          min_duration: fd.get("min_duration"),
          max_duration: fd.get("max_duration"),
          max_clips: fd.get("max_clips"),
          language: fd.get("language"),
          manual_clips: fd.get("manual_clips"),
        }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.error || "Erreur inconnue");
      window.location.href = `/job/${data.id}`;
    } catch (err) {
      errEl.textContent = err.message;
      errEl.classList.remove("hidden");
      btn.disabled = false;
      btn.textContent = "🚀 Générer les clips";
    }
  });
}

// --- Page de suivi d'un job ---
const jobView = document.getElementById("job-view");
if (jobView) {
  const jobId = jobView.dataset.jobId;
  const STEP_ORDER = ["download", "transcribe", "analyze", "cut", "done"];
  const STEP_LABELS = {
    download: "Téléchargement de la vidéo…",
    transcribe: "Transcription audio (Whisper)…",
    analyze: "Analyse des moments viraux par l'IA…",
    cut: "Montage des clips (ffmpeg)…",
    done: "Terminé ✅",
  };
  let rendered = false;

  async function poll() {
    const res = await fetch(`/api/jobs/${jobId}`);
    if (!res.ok) return;
    const job = await res.json();
    render(job);
    if (job.status === "running" || job.status === "pending") {
      setTimeout(poll, 1500);
    }
  }

  function render(job) {
    document.getElementById("job-title").textContent = job.video_title || job.url;
    const idx = STEP_ORDER.indexOf(job.step);
    document.querySelectorAll("#steps li").forEach((li) => {
      const i = STEP_ORDER.indexOf(li.dataset.step);
      li.classList.toggle("done", i < idx || job.status === "done");
      li.classList.toggle("active", i === idx && job.status === "running");
    });
    document.getElementById("bar-fill").style.width = `${Math.round(job.progress * 100)}%`;
    document.getElementById("job-status").textContent =
      job.status === "error" ? "" : STEP_LABELS[job.step] || "";

    const errEl = document.getElementById("job-error");
    if (job.error) {
      errEl.textContent = "❌ " + job.error;
      errEl.classList.remove("hidden");
    }

    if (job.video_summary) {
      document.getElementById("video-summary").textContent = "📝 " + job.video_summary;
    }

    if (job.clips && job.clips.length && !rendered && (job.status === "done" || job.status === "running")) {
      renderClips(job);
      if (job.status === "done") rendered = true;
    }
  }

  function renderClips(job) {
    const container = document.getElementById("clips");
    container.innerHTML = "";
    for (const c of job.clips) {
      const card = document.createElement("div");
      card.className = "clip-card";
      const partBadge =
        c.part && c.series_total > 1
          ? `<span class="badge-part">PARTIE ${c.part}/${c.series_total}</span> `
          : "";
      const score = c.viral_score
        ? `<span class="score">🔥 ${c.viral_score}/100</span>`
        : "";
      card.innerHTML = `
        <video controls preload="metadata" src="/clips/${job.id}/${c.filename}"></video>
        <div class="clip-body">
          <h3>${partBadge}${escapeHtml(c.title)}</h3>
          ${score}
          ${c.reasoning ? `<p class="small muted">${escapeHtml(c.reasoning)}</p>` : ""}
          ${c.caption ? `<div class="caption">${escapeHtml(c.caption)}</div>` : ""}
          <div class="clip-actions">
            <a href="/clips/${job.id}/${c.filename}" download>⬇️ Télécharger</a>
            ${c.caption ? `<button data-caption="${escapeAttr(c.caption)}">📋 Légende</button>` : ""}
          </div>
        </div>`;
      const copyBtn = card.querySelector("button[data-caption]");
      if (copyBtn) {
        copyBtn.addEventListener("click", () => {
          navigator.clipboard.writeText(copyBtn.dataset.caption);
          copyBtn.textContent = "✅ Copié !";
          setTimeout(() => (copyBtn.textContent = "📋 Légende"), 1500);
        });
      }
      container.appendChild(card);
    }
  }

  function escapeHtml(s) {
    const div = document.createElement("div");
    div.textContent = s || "";
    return div.innerHTML;
  }
  function escapeAttr(s) {
    return (s || "").replace(/"/g, "&quot;");
  }

  poll();
}
