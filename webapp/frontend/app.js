const sections = [
  { key: "overview", label: "Overview" },
  { key: "wind", label: "Wind" },
  { key: "precipitation", label: "Precipitation" },
  { key: "fog_low_cloud", label: "Fog/Low cloud" },
  { key: "smoke_dust", label: "Smoke/Dust" },
];

const state = {
  section: "overview",
  options: null,
};

const dualSliderDefs = [
  { key: "year", minEl: "year-start", maxEl: "year-end", highlightEl: "year-highlight", minValueEl: "year-start-value", maxValueEl: "year-end-value", format: (v) => String(v) },
  { key: "month", minEl: "month-start", maxEl: "month-end", highlightEl: "month-highlight", minValueEl: "month-start-value", maxValueEl: "month-end-value", format: (v) => state.options.months[Number(v) - 1] },
  { key: "hour", minEl: "hour-start", maxEl: "hour-end", highlightEl: "hour-highlight", minValueEl: "hour-start-value", maxValueEl: "hour-end-value", format: (v) => String(v) },
];

const els = {
  categoryRow: document.getElementById("category-row"),
  icao: document.getElementById("icao"),
  yearStart: document.getElementById("year-start"),
  yearEnd: document.getElementById("year-end"),
  monthStart: document.getElementById("month-start"),
  monthEnd: document.getElementById("month-end"),
  hourStart: document.getElementById("hour-start"),
  hourEnd: document.getElementById("hour-end"),
  invertMonth: document.getElementById("invert-month"),
  invertHour: document.getElementById("invert-hour"),
  yearStartValue: document.getElementById("year-start-value"),
  yearEndValue: document.getElementById("year-end-value"),
  monthStartValue: document.getElementById("month-start-value"),
  monthEndValue: document.getElementById("month-end-value"),
  hourStartValue: document.getElementById("hour-start-value"),
  hourEndValue: document.getElementById("hour-end-value"),
  status: document.getElementById("status"),
  loadingOverlay: document.getElementById("loading-overlay"),
  loadingBarFill: document.getElementById("loading-bar-fill"),
  loadingStatus: document.getElementById("loading-status"),
  metrics: document.getElementById("metrics"),
  charts: [
    document.getElementById("chart-1"),
    document.getElementById("chart-2"),
    document.getElementById("chart-3"),
    document.getElementById("chart-4"),
  ],
};

let loadingProgress = 0;
let loadingTimer = null;

function setStatus(message = "") {
  els.status.textContent = message;
}

function setLoadingState(progress, message) {
  loadingProgress = Math.max(0, Math.min(100, progress));
  els.loadingBarFill.style.width = `${loadingProgress}%`;
  if (message) {
    els.loadingStatus.textContent = message;
  }
}

function showLoading(message = "Preparing charts...") {
  if (loadingTimer) {
    clearInterval(loadingTimer);
    loadingTimer = null;
  }
  setLoadingState(12, message);
  els.loadingOverlay.classList.remove("hidden");

  loadingTimer = setInterval(() => {
    if (loadingProgress < 90) {
      setLoadingState(loadingProgress + 6);
    }
  }, 180);
}

function hideLoading() {
  if (loadingTimer) {
    clearInterval(loadingTimer);
    loadingTimer = null;
  }
  setLoadingState(100, "Ready");
  setTimeout(() => {
    els.loadingOverlay.classList.add("hidden");
    setLoadingState(0, "Preparing charts...");
  }, 120);
}

function renderCategories() {
  els.categoryRow.innerHTML = "";
  const buttonRow = document.createElement("div");
  buttonRow.className = "category-buttons";
  sections.forEach((section) => {
    const btn = document.createElement("button");
    btn.className = `category-btn ${section.key === state.section ? "active" : ""}`;
    btn.textContent = section.label;
    btn.addEventListener("click", () => {
      if (state.section === section.key) {
        return;
      }
      state.section = section.key;
      renderCategories();
      fetchCharts();
    });
    buttonRow.appendChild(btn);
  });
  els.categoryRow.appendChild(buttonRow);
}

function fillSelect(select, options, selectedValue) {
  select.innerHTML = "";
  options.forEach((value) => {
    const opt = document.createElement("option");
    opt.value = value;
    opt.textContent = value;
    if (value === selectedValue) {
      opt.selected = true;
    }
    select.appendChild(opt);
  });
}

function monthNameFromNumber(value) {
  const idx = Math.max(1, Math.min(12, Number(value))) - 1;
  return state.options.months[idx];
}

function updateDualSliderTrack(def) {
  const minInput = document.getElementById(def.minEl);
  const maxInput = document.getElementById(def.maxEl);
  const highlight = document.getElementById(def.highlightEl);

  const min = Number(minInput.min);
  const max = Number(minInput.max);
  const start = Number(minInput.value);
  const end = Number(maxInput.value);

  const leftPct = ((start - min) / (max - min)) * 100;
  const rightPct = ((end - min) / (max - min)) * 100;

  highlight.style.left = `${leftPct}%`;
  highlight.style.width = `${Math.max(0, rightPct - leftPct)}%`;
}

function updateSliderLabels() {
  dualSliderDefs.forEach((def) => {
    const minInput = document.getElementById(def.minEl);
    const maxInput = document.getElementById(def.maxEl);
    const minValueEl = document.getElementById(def.minValueEl);
    const maxValueEl = document.getElementById(def.maxValueEl);

    minValueEl.textContent = def.format(minInput.value);
    maxValueEl.textContent = def.format(maxInput.value);
    updateDualSliderTrack(def);
  });
}

function normalizeRanges(changedField) {
  let yearStart = Number(els.yearStart.value);
  let yearEnd = Number(els.yearEnd.value);
  let monthStart = Number(els.monthStart.value);
  let monthEnd = Number(els.monthEnd.value);
  let hourStart = Number(els.hourStart.value);
  let hourEnd = Number(els.hourEnd.value);

  if (yearStart > yearEnd) {
    if (changedField === "year-start") {
      yearEnd = yearStart;
      els.yearEnd.value = String(yearEnd);
    } else {
      yearStart = yearEnd;
      els.yearStart.value = String(yearStart);
    }
  }

  if (monthStart > monthEnd) {
    if (changedField === "month-start") {
      monthEnd = monthStart;
      els.monthEnd.value = String(monthEnd);
    } else {
      monthStart = monthEnd;
      els.monthStart.value = String(monthStart);
    }
  }

  if (hourStart > hourEnd) {
    if (changedField === "hour-start") {
      hourEnd = hourStart;
      els.hourEnd.value = String(hourEnd);
    } else {
      hourStart = hourEnd;
      els.hourStart.value = String(hourStart);
    }
  }
}

async function fetchOptions() {
  const res = await fetch("/api/options");
  const data = await res.json();
  state.options = data;

  fillSelect(els.icao, data.airports, data.defaultAirport);

  els.yearStart.value = data.default.yearStart;
  els.yearEnd.value = data.default.yearEnd;
  els.monthStart.value = String(data.months.indexOf(data.default.monthStart) + 1);
  els.monthEnd.value = String(data.months.indexOf(data.default.monthEnd) + 1);
  els.hourStart.value = data.default.hourStart;
  els.hourEnd.value = data.default.hourEnd;
  els.invertMonth.checked = data.default.invertMonth;
  els.invertHour.checked = data.default.invertHour;
  state.section = data.default.section;
  updateSliderLabels();
}

function getParams() {
  const params = new URLSearchParams({
    section: state.section,
    icao: els.icao.value,
    yearStart: String(els.yearStart.value),
    yearEnd: String(els.yearEnd.value),
    monthStart: monthNameFromNumber(els.monthStart.value),
    monthEnd: monthNameFromNumber(els.monthEnd.value),
    hourStart: String(els.hourStart.value),
    hourEnd: String(els.hourEnd.value),
    invertMonth: String(els.invertMonth.checked),
    invertHour: String(els.invertHour.checked),
  });
  return params;
}

function validateRanges() {
  const yearStart = Number(els.yearStart.value);
  const yearEnd = Number(els.yearEnd.value);
  const hourStart = Number(els.hourStart.value);
  const hourEnd = Number(els.hourEnd.value);

  if (Number.isNaN(yearStart) || Number.isNaN(yearEnd) || yearStart > yearEnd) {
    setStatus("Year range is invalid.");
    return false;
  }

  if (Number.isNaN(hourStart) || Number.isNaN(hourEnd) || hourStart > hourEnd) {
    setStatus("Hour range is invalid.");
    return false;
  }

  return true;
}

function renderMetrics(metrics) {
  if (!metrics || state.section === "overview") {
    els.metrics.innerHTML = "";
    return;
  }

  const cards = [
    { label: "Observations", value: metrics.observations.toLocaleString() },
    { label: "Mean Speed", value: `${metrics.meanSpeed.toFixed(1)} kt` },
    { label: "Max Gust", value: `${metrics.maxGust.toFixed(1)} kt` },
    { label: "Avg Temp", value: `${metrics.avgTemp.toFixed(1)} C` },
  ];

  els.metrics.innerHTML = cards
    .map((card) => `<article class="metric"><div class="label">${card.label}</div><div class="value">${card.value}</div></article>`)
    .join("");
}

function clearChart(index) {
  const host = els.charts[index];
  Plotly.purge(host);
  host.parentElement.classList.add("hidden");
}

function drawCharts(figures) {
  for (let i = 0; i < els.charts.length; i += 1) {
    clearChart(i);
  }

  figures.slice(0, 4).forEach((item, idx) => {
    const host = els.charts[idx];
    host.parentElement.classList.remove("hidden");
    const figure = item.figure;
    Plotly.newPlot(host, figure.data || [], figure.layout || {}, {
      displayModeBar: false,
      responsive: false,
    });
  });
}

let pendingFetch = null;
let hasShownInitialLoading = false;

async function fetchCharts() {
  if (!validateRanges()) {
    return;
  }

  const showOverlay = !hasShownInitialLoading;

  const controller = new AbortController();
  if (pendingFetch) {
    pendingFetch.abort();
  }
  pendingFetch = controller;

  if (showOverlay) {
    showLoading("Loading charts...");
  }
  const query = getParams().toString();

  try {
    const res = await fetch(`/api/charts?${query}`, { signal: controller.signal });
    if (showOverlay) {
      setLoadingState(55, "Processing data...");
    }
    const data = await res.json();
    if (showOverlay) {
      setLoadingState(82, "Rendering charts...");
    }

    if (controller.signal.aborted) {
      return;
    }

    if (data.error) {
      setStatus(data.error);
      return;
    }

    if (data.warning) {
      setStatus(data.warning);
    } else {
      setStatus("");
    }

    drawCharts(data.figures || []);
    renderMetrics(data.metrics);
  } catch (err) {
    if (err.name !== "AbortError") {
      setStatus("Failed to load charts.");
    }
  } finally {
    if (pendingFetch === controller) {
      pendingFetch = null;
      if (showOverlay) {
        hasShownInitialLoading = true;
        hideLoading();
      }
    }
  }
}

function wireControls() {
  els.icao.addEventListener("change", fetchCharts);

  [
    [els.yearStart, "year-start"],
    [els.yearEnd, "year-end"],
    [els.monthStart, "month-start"],
    [els.monthEnd, "month-end"],
    [els.hourStart, "hour-start"],
    [els.hourEnd, "hour-end"],
  ].forEach(([el, field]) => {
    el.addEventListener("input", () => {
      normalizeRanges(field);
      updateSliderLabels();
    });
    el.addEventListener("change", () => {
      normalizeRanges(field);
      updateSliderLabels();
      fetchCharts();
    });
  });

  [els.invertMonth, els.invertHour].forEach((el) => {
    el.addEventListener("change", fetchCharts);
  });
}

async function init() {
  renderCategories();
  await fetchOptions();
  renderCategories();
  wireControls();
  fetchCharts();
}

init();
