const sections = [
  { key: "overview", label: "Overview" },
  { key: "wind", label: "Wind" },
  { key: "precipitation", label: "Precipitation" },
  { key: "fog_low_cloud", label: "Fog/Low cloud" },
  { key: "smoke_dust", label: "Smoke/Dust" },
];

const state = {
  requestedSection: "overview",
  displayedSection: "overview",
  fogModes: {
    monthly: "all",
    hourly: "all",
    wind: "all",
    dewpoint: "all",
  },
  options: null,
  latestFigures: [],
};

const fogLegendOrder = new Map([
  ["2000ft - 1500ft cloud", 0],
  ["1500ft - 1000ft cloud", 1],
  ["1000ft - 500ft cloud", 2],
  ["< 500ft cloud", 3],
  ["Fog", 4],
]);

const smokeLegendOrder = new Map([
  ["FU", 0],
  ["DU", 1],
  ["SA", 2],
  ["VA", 3],
]);

const fogPanels = [
  { key: "monthly", toolbarId: "fog-mode-toolbar-1" },
  { key: "hourly", toolbarId: "fog-mode-toolbar-2" },
  { key: "wind", toolbarId: "fog-mode-toolbar-3" },
  { key: "dewpoint", toolbarId: "fog-mode-toolbar-4" },
];

const frequencyFigureIds = new Set([
  "rain_thunder",
  "temp_dewpoint",
  "fog_low_cloud",
  "gale_weather_split",
  "monthly_precip",
  "monthly_fog",
  "fog_share",
  "fog_cloud_joint",
  "monthly_smoke",
  "hourly_smoke",
]);

const overviewFogToolbarId = "fog-mode-toolbar-4";

const dualSliderDefs = [
  { key: "year", minEl: "year-start", maxEl: "year-end", highlightEl: "year-highlight", minValueEl: "year-start-value", maxValueEl: "year-end-value", format: (v) => String(v) },
  { key: "month", minEl: "month-start", maxEl: "month-end", highlightEl: "month-highlight", invertEl: "invert-month", minValueEl: "month-start-value", maxValueEl: "month-end-value", format: (v) => state.options.months[Number(v) - 1] },
  { key: "hour", minEl: "hour-start", maxEl: "hour-end", highlightEl: "hour-highlight", invertEl: "invert-hour", minValueEl: "hour-start-value", maxValueEl: "hour-end-value", format: (v) => `${String(v).padStart(2, "0")}Z` },
];

const els = {
  categoryRow: document.getElementById("category-row"),
  icao: document.getElementById("icao"),
  enso: document.getElementById("enso"),
  iod: document.getElementById("iod"),
  sam: document.getElementById("sam"),
  mjo: document.getElementById("mjo"),
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
  fogModeToolbars: fogPanels.reduce((acc, panel) => {
    acc[panel.key] = document.getElementById(panel.toolbarId);
    return acc;
  }, {}),
  overviewFogModeToolbar: document.getElementById(overviewFogToolbarId),
  charts: [
    document.getElementById("chart-1"),
    document.getElementById("chart-2"),
    document.getElementById("chart-3"),
    document.getElementById("chart-4"),
  ],
};

function ensureChartShell(host) {
  const card = host.closest(".chart-card");
  let shell = card.querySelector(".chart-shell");
  let legend = card.querySelector(".chart-legend");

  if (!shell) {
    shell = document.createElement("div");
    shell.className = "chart-shell";
    host.replaceWith(shell);
    shell.appendChild(host);

    legend = document.createElement("div");
    legend.className = "chart-legend hidden";
    shell.appendChild(legend);
  }

  return { card, shell, legend };
}

const chartUi = els.charts.map((host) => ensureChartShell(host));

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
  // Add loading class to chart grid to lock layout
  const chartGrid = document.getElementById("chart-grid");
  if (chartGrid) chartGrid.classList.add("is-loading");

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
    // Remove loading class from chart grid
    const chartGrid = document.getElementById("chart-grid");
    if (chartGrid) chartGrid.classList.remove("is-loading");
    setLoadingState(0, "Preparing charts...");
  }, 120);
}

function renderCategories() {
  els.categoryRow.innerHTML = "";
  const buttonRow = document.createElement("div");
  buttonRow.className = "category-buttons";
  sections.forEach((section) => {
    const btn = document.createElement("button");
    btn.className = `category-btn ${section.key === state.requestedSection ? "active" : ""}`;
    btn.textContent = section.label;
    btn.addEventListener("click", () => {
      if (state.requestedSection === section.key) {
        return;
      }
      state.requestedSection = section.key;
      renderCategories();
      fetchCharts();
    });
    buttonRow.appendChild(btn);
  });
  els.categoryRow.appendChild(buttonRow);
}

function renderDayTypeToggle(toolbar, modeKey) {
  if (!toolbar) {
    return;
  }

  toolbar.innerHTML = "";
  toolbar.classList.remove("hidden");

  const group = document.createElement("div");
  group.className = "segmented-toggle";

  [
    { value: "all", label: "All days" },
    { value: "rain", label: "Rain days" },
    { value: "non_rain", label: "Non-rain days" },
  ].forEach((option) => {
    const button = document.createElement("button");
    button.type = "button";
    button.className = `segmented-toggle-btn ${state.fogModes[modeKey] === option.value ? "active" : ""}`;
    button.textContent = option.label;
    button.addEventListener("click", () => {
      if (state.fogModes[modeKey] === option.value) {
        return;
      }
      state.fogModes[modeKey] = option.value;
      renderFogModeToolbars();
      fetchCharts();
    });
    group.appendChild(button);
  });

  toolbar.appendChild(group);
}

function renderFogModeToolbars(section = state.displayedSection) {
  fogPanels.forEach((panel) => {
    const toolbar = els.fogModeToolbars[panel.key];
    if (!toolbar) {
      return;
    }
    toolbar.innerHTML = "";
    toolbar.classList.add("hidden");
  });

  if (!state.latestFigures.length) {
    return;
  }

  if (section === "fog_low_cloud") {
    fogPanels.forEach((panel) => {
      renderDayTypeToggle(els.fogModeToolbars[panel.key], panel.key);
    });
    return;
  }

  if (section === "overview") {
    renderDayTypeToggle(els.overviewFogModeToolbar, "monthly");
  }
}

function applySectionLayout(section = state.displayedSection) {
  const chartGrid = document.getElementById("chart-grid");
  if (!chartGrid) {
    return;
  }
  chartGrid.classList.toggle("smoke-dust-layout", section === "smoke_dust");
  renderFogModeToolbars(section);
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
  const invertInput = def.invertEl ? document.getElementById(def.invertEl) : null;

  const min = Number(minInput.min);
  const max = Number(minInput.max);
  const start = Number(minInput.value);
  const end = Number(maxInput.value);

  const span = Math.max(1, max - min);
  const startPct = ((start - min) / span) * 100;
  const endPct = ((end - min) / span) * 100;
  const isInverted = Boolean(invertInput && invertInput.checked);

  // Use two-tone track colors so invert mode is visibly different at a glance.
  const selectedColor = "rgba(170, 214, 255, 0.95)";
  const unselectedColor = "rgba(17, 43, 88, 0.45)";

  highlight.style.left = "0%";
  highlight.style.width = "100%";

  if (isInverted) {
    highlight.style.background = `linear-gradient(to right, ${selectedColor} 0%, ${selectedColor} ${startPct}%, ${unselectedColor} ${startPct}%, ${unselectedColor} ${endPct}%, ${selectedColor} ${endPct}%, ${selectedColor} 100%)`;
    highlight.classList.add("is-inverted");
    return;
  }

  highlight.style.background = `linear-gradient(to right, ${unselectedColor} 0%, ${unselectedColor} ${startPct}%, ${selectedColor} ${startPct}%, ${selectedColor} ${endPct}%, ${unselectedColor} ${endPct}%, ${unselectedColor} 100%)`;
  highlight.classList.remove("is-inverted");
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
  state.requestedSection = data.default.section;
  state.displayedSection = data.default.section;
  updateSliderLabels();
}

function getParams() {
  const params = new URLSearchParams({
    section: state.requestedSection,
    enso: els.enso.value,
    iod: els.iod.value,
    sam: els.sam.value,
    mjo: els.mjo.value,
    fogMonthlyMode: state.fogModes.monthly,
    fogHourlyMode: state.fogModes.hourly,
    fogWindMode: state.fogModes.wind,
    fogDewpointMode: state.fogModes.dewpoint,
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

function renderMetrics(metrics, section = state.displayedSection) {
  if (!metrics || section === "overview" || section === "wind" || section === "precipitation" || section === "fog_low_cloud" || section === "smoke_dust") {
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
  const { card, shell, legend } = chartUi[index];
  Plotly.purge(host);
  legend.innerHTML = "";
  legend.classList.add("hidden");
  shell.classList.add("no-legend");
  card.classList.add("hidden");
}

function normalizeLegendColor(value) {
  if (Array.isArray(value)) {
    const firstColor = value.find((item) => typeof item === "string" && item.trim()) || value[0];
    return normalizeLegendColor(firstColor);
  }
  if (typeof value === "string" && value.trim()) {
    return value;
  }
  return null;
}

function toOpaqueColor(color) {
  if (typeof color !== "string") return color;
  // Convert rgba(r,g,b,a) → rgba(r,g,b,1) so legend swatches are always fully opaque.
  return color.replace(/rgba\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*,[^)]+\)/gi, "rgba($1,$2,$3,1)");
}

function getTraceLegendColor(trace) {
  const candidates = [
    trace?.meta?.legendColor,
    trace?.marker?.line?.color,
    trace?.marker?.color,
    trace?.line?.color,
    trace?.fillcolor,
  ];

  for (const candidate of candidates) {
    const color = normalizeLegendColor(candidate);
    if (color) {
      return toOpaqueColor(color);
    }
  }

  return "#5f6f8d";
}

function isTraceVisible(trace) {
  return trace?.visible !== false && trace?.visible !== "legendonly";
}

function getLegendItems(figure, section = state.displayedSection, figureId = "") {
  const data = figure?.data || [];
  const legend = figure?.layout?.legend || {};
  const groupclick = legend.groupclick || null;

  const items = data.flatMap((trace, index) => {
    if (trace?.showlegend === false || !trace?.name) {
      return [];
    }

    return [{
      index,
      label: String(trace.name),
      legendgroup: trace.legendgroup || null,
      color: getTraceLegendColor(trace),
    }];
  });

  if (section === "fog_low_cloud" || figureId === "fog_low_cloud") {
    items.sort((left, right) => {
      const leftRank = fogLegendOrder.get(left.label) ?? Number.MAX_SAFE_INTEGER;
      const rightRank = fogLegendOrder.get(right.label) ?? Number.MAX_SAFE_INTEGER;
      if (leftRank !== rightRank) {
        return leftRank - rightRank;
      }
      return left.index - right.index;
    });
  }

  if (section === "smoke_dust") {
    items.sort((left, right) => {
      const leftRank = smokeLegendOrder.get(left.label) ?? Number.MAX_SAFE_INTEGER;
      const rightRank = smokeLegendOrder.get(right.label) ?? Number.MAX_SAFE_INTEGER;
      if (leftRank !== rightRank) {
        return leftRank - rightRank;
      }
      return left.index - right.index;
    });
  }

  return { items, groupclick };
}

function getAffectedTraceIndices(plotData, item, groupclick) {
  if (groupclick === "togglegroup" && item.legendgroup) {
    return plotData
      .map((trace, index) => (trace?.legendgroup === item.legendgroup ? index : -1))
      .filter((index) => index >= 0);
  }

  return [item.index];
}

function refreshLegendState(host, legendHost, legendItems, groupclick) {
  const plotData = host.data || [];
  legendHost.querySelectorAll(".chart-legend-item").forEach((button, index) => {
    const item = legendItems[index];
    if (!item) {
      return;
    }
    const affectedIndices = getAffectedTraceIndices(plotData, item, groupclick);
    const isVisible = affectedIndices.some((traceIndex) => isTraceVisible(plotData[traceIndex]));
    button.classList.toggle("is-inactive", !isVisible);
  });
}

function renderExternalLegend(host, legendHost, figure, section = state.displayedSection, figureId = "") {
  const { items, groupclick } = getLegendItems(figure, section, figureId);
  legendHost.innerHTML = "";
  legendHost.style.minWidth = "";
  legendHost.style.marginLeft = "";
  legendHost.style.marginRight = section === "overview" && figureId === "wind_rose" ? "28px" : "";

  if (!items.length) {
    legendHost.classList.add("hidden");
    legendHost.parentElement.classList.add("no-legend");
    return;
  }

  legendHost.parentElement.classList.remove("no-legend");
  legendHost.classList.remove("hidden");

  items.forEach((item) => {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "chart-legend-item";

    const swatch = document.createElement("span");
    swatch.className = "chart-legend-swatch";
    swatch.style.background = item.color;
    swatch.style.borderColor = item.color;

    const label = document.createElement("span");
    label.className = "chart-legend-label";
    label.textContent = item.label;

    button.appendChild(swatch);
    button.appendChild(label);
    button.addEventListener("click", () => {
      const plotData = host.data || [];
      const affectedIndices = getAffectedTraceIndices(plotData, item, groupclick);
      const anyVisible = affectedIndices.some((traceIndex) => isTraceVisible(plotData[traceIndex]));
      const nextVisibility = anyVisible ? "legendonly" : true;
      Plotly.restyle(host, { visible: affectedIndices.map(() => nextVisibility) }, affectedIndices)
        .then(() => refreshLegendState(host, legendHost, items, groupclick));
    });

    legendHost.appendChild(button);
  });

  refreshLegendState(host, legendHost, items, groupclick);
}

function getChartHeight(section) {
  const isWindSection = section === "wind";
  const isExpandedSection = isWindSection || section === "precipitation";
  const chartGridHeight = document.getElementById("chart-grid")?.clientHeight ?? 0;
  const maxHeight = isExpandedSection ? 900 : 320;

  if (isExpandedSection) {
    return Math.max(380, Math.min(maxHeight, chartGridHeight - 12));
  }

  const headerHeight = document.querySelector(".app-header")?.offsetHeight ?? 0;
  const controlsHeight = document.querySelector(".controls")?.offsetHeight ?? 0;
  const statusHeight = els.status.offsetHeight ?? 0;
  const metricsHeight = els.metrics.offsetHeight ?? 0;
  const footerHeight = document.querySelector(".time-controls")?.offsetHeight ?? 0;
  const viewportHeight = window.innerHeight;

  // Reserve room for page padding, the 2-row grid gap, and Plotly card chrome.
  const fixedChrome = 40;
  const available = Math.max(0, viewportHeight - headerHeight - controlsHeight - statusHeight - metricsHeight - footerHeight - fixedChrome);
  const perRowHeight = Math.floor((available - 8) / 2);

  return Math.max(220, Math.min(maxHeight, perRowHeight - 12));
}

function applyChartShellHeights(section = state.displayedSection) {
  const chartHeight = getChartHeight(section);

  for (let i = 0; i < els.charts.length; i += 1) {
    els.charts[i].style.height = `${chartHeight}px`;
    chartUi[i].card.style.minHeight = `${chartHeight + 10}px`;
  }

  return chartHeight;
}

async function drawCharts(figures, section = state.displayedSection) {
  const isWindSection = section === "wind";
  const isExpandedSection = section === "wind" || section === "precipitation";
  const chartHeight = applyChartShellHeights(section);
  const visibleFigures = figures.slice(0, 4);

  state.latestFigures = figures;

  const renderPromises = visibleFigures.map((item, idx) => {
    const host = els.charts[idx];
    const { card, legend } = chartUi[idx];
    card.classList.remove("hidden");
    const figure = item.figure;
    const isFrequencyFigure = frequencyFigureIds.has(item.id);
    figure.layout = figure.layout || {};
    figure.layout.legend = figure.layout.legend || {};
    figure.layout.showlegend = false;
    figure.layout.margin = {
      ...(figure.layout.margin || {}),
      r: 32,
    };
    if (isFrequencyFigure) {
      figure.layout.height = chartHeight;
    }
    if (item.id === "fog_cloud_joint") {
      figure.layout.margin = {
        ...figure.layout.margin,
        b: 18,
      };
      figure.layout.height = chartHeight - 12;
    }
    if (isExpandedSection) {
      if ((isWindSection && item.id === "wind_rose") || item.id === "precip_split") {
        figure.layout.height = chartHeight - 12;
      } else {
        figure.layout.height = chartHeight;
      }
    }
    return Plotly.react(host, figure.data || [], figure.layout || {}, {
      displayModeBar: false,
      responsive: true,
    }).then(() => {
      renderExternalLegend(host, legend, item.figure, section, item.id);
      Plotly.Plots.resize(host);
    });
  });

  for (let i = visibleFigures.length; i < els.charts.length; i += 1) {
    clearChart(i);
  }

  await Promise.all(renderPromises);
}

let pendingFetch = null;
let hasShownInitialLoading = false;

async function fetchCharts() {
  if (!validateRanges()) {
    return;
  }

  const showOverlay = true;
  const requestedSection = state.requestedSection;

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

    await drawCharts(data.figures || [], requestedSection);

    if (controller.signal.aborted) {
      return;
    }

    state.displayedSection = requestedSection;
    applySectionLayout(requestedSection);
    renderMetrics(data.metrics, requestedSection);
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
  [els.enso, els.iod, els.sam, els.mjo].forEach((el) => {
    el.addEventListener("change", fetchCharts);
  });

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
    el.addEventListener("change", () => {
      updateSliderLabels();
      fetchCharts();
    });
  });

  let resizeFrame = null;
  window.addEventListener("resize", () => {
    if (resizeFrame) {
      cancelAnimationFrame(resizeFrame);
    }
    resizeFrame = requestAnimationFrame(() => {
      if (!state.latestFigures.length) {
        applyChartShellHeights(state.displayedSection);
      } else {
        drawCharts(state.latestFigures, state.displayedSection);
      }
      resizeFrame = null;
    });
  });
}

async function init() {
  renderCategories();
  await fetchOptions();
  renderCategories();
  applySectionLayout();
  applyChartShellHeights();
  wireControls();
  fetchCharts();
}

init();
