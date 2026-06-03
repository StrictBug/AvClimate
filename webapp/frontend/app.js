const sections = [
  { key: "overview", label: "Overview" },
  { key: "wind", label: "Wind" },
  { key: "precipitation", label: "Precipitation" },
  { key: "fog_low_cloud", label: "Fog/Low cloud" },
  { key: "smoke_dust", label: "Smoke/Dust" },
];

const infoDataSection = {
  title: "Data sources",
  bullets: [],
};

const infoObservationsSection = {
  title: "Observations",
  bullets: [
    "METAR/SPECI data acquired from the ADAM database: January 1, 2000 to December 31, 2024.",
    "GPATS lightning data acquired from the ADAM database: January 1, 2009 to December 31, 2013.",
    "WZ lightning data acquired from the ADAM database: January 1, 2014 to December 31, 2024.",
  ],
};

const infoClimateDriverSection = {
  title: "Climate drivers",
  bullets: [
    {
      text: "ENSO is characterized using the NINO3.4 sea-surface temperature anomaly index with coupled atmospheric monitoring indicators. Data acquired from ",
      linkText: "Bureau of Meteorology ENSO and IOD monitoring",
      href: "https://www.bom.gov.au/climate/enso/?ninoIndex=nino3.4&index=rnino34&period=weekly#tabs=Overview&overview-section=Monitoring-graphs",
    },
    {
      text: "IOD is characterized using the Dipole Mode Index (DMI), based on the east-west Indian Ocean sea-surface temperature anomaly contrast. Data acquired from ",
      linkText: "Bureau of Meteorology ENSO and IOD monitoring",
      href: "https://www.bom.gov.au/climate/enso/?ninoIndex=nino3.4&index=rnino34&period=weekly#tabs=Overview&overview-section=Monitoring-graphs",
    },
    {
      text: "SAM is characterized using the Marshall SAM index, an observation-based standardized pressure-gradient index between mid and high southern latitudes. Data acquired from ",
      linkText: "BAS observation-based SAM index",
      href: "http://www.nerc-bas.ac.uk/icd/gjma/sam.html",
    },
    {
      text: "MJO is characterized using Real-time Multivariate MJO indices (RMM1 and RMM2) within an amplitude-phase framework. Data acquired from ",
      linkText: "Bureau of Meteorology MJO monitoring",
      href: "https://www.bom.gov.au/climate/mjo/#tabs=Monitoring",
    },
  ],
};

const infoSectionOverview = {
  overview: {
    title: "Overview",
    figureOrder: ["wind_rose", "rain_thunder", "temp_dewpoint", "fog_low_cloud"],
  },
  wind: {
    title: "Wind",
    figureOrder: ["wind_rose", "gale_weather_split"],
  },
  precipitation: {
    title: "Precipitation",
    figureOrder: ["monthly_precip", "precip_split"],
  },
  fog_low_cloud: {
    title: "Fog/Low cloud",
    figureOrder: ["monthly_fog", "fog_share", "cloud_distribution", "fog_cloud_joint"],
  },
  smoke_dust: {
    title: "Smoke/Dust",
    figureOrder: ["monthly_smoke", "hourly_smoke", "scatter_wind_dewpt", "radial_scatter_dust"],
  },
};

const infoFigureDetails = {
  wind_rose: {
    title: "Wind Rose",
    bullets: [
      "Shows relative frequency of wind by direction sector and speed bin.",
      "Wind direction is grouped into directional sectors and wind speed into bins, then normalized to percent of filtered observations.",
    ],
  },
  rain_thunder: {
    title: "Rain/Thunder by Month",
    bullets: [
      "Monthly bars show percent of days classified as rain days and thunderstorm days.",
      "Rain-day logic: any BoM day with RA/DZ/SH/TS weather tokens or PRCP_FM_09 > 0.2.",
      "Thunder-day logic: any BoM day with at least one lightning strike within 8 km of aerodrome reference point; thunder averages are restricted to 2009 onward.",
    ],
  },
  temp_dewpoint: {
    title: "Temperature & Dewpoint",
    bullets: [
      "Shows monthly climatological max/min temperature and dewpoint behavior for the selected filters.",
      "Values are monthly grouped means from filtered observations; secondary axis is used for precipitation context where applicable.",
    ],
  },
  fog_low_cloud: {
    title: "Fog/Low Cloud Frequency",
    bullets: [
      "Shows monthly frequency of fog and low cloud threshold categories.",
      "Fog logic: explicit FG token OR inferred fog when (AIR_TEMP - DWPT) < 2 C, PRCP_10 < 0.2, and visibility < 1.0 km (VSBY or AWS_VSBY).",
      "Cloud classification uses cloud-base bins: 2000-1500 ft, 1500-1000 ft, 1000-500 ft, and <500 ft; rain/non-rain mode toggles change denominator.",
    ],
  },
  gale_weather_split: {
    title: "Gale Weather Split",
    bullets: [
      "Monthly gale climatology split into No wx, SHRA, and TS categories.",
      "Gale logic: WND_SPD > 17.49 m/s (34 kt) OR MAX_WND_GUST_10 > 21.09 m/s (41 kt).",
      "Category logic: TS if lightning is within 8 km and +/-10 minutes of observation; else SHRA if SH+RA weather coding or PRCP_10 > 0.2; else No wx.",
    ],
  },
  monthly_precip: {
    title: "Monthly Precipitation Occurrence",
    bullets: [
      "Shows monthly rain and thunderstorm-day climatology under the active filters.",
      "Rain-day logic: any BoM day with RA/DZ/SH/TS weather tokens or PRCP_FM_09 > 0.2.",
      "Thunder-day logic: any BoM day with at least one lightning strike within 8 km of the aerodrome reference point.",
    ],
  },
  precip_split: {
    title: "Directional Precipitation Split",
    bullets: [
      "Polar chart showing precipitation intensity bucket contribution by wind-direction sector.",
      "Precipitation is grouped into directional sectors and intensity buckets before normalization within filtered sectors.",
    ],
  },
  monthly_fog: {
    title: "Monthly Fog/Low Cloud Frequency",
    bullets: [
      "Monthly stacked frequencies for fog and cloud-base threshold categories.",
      "Fog logic: explicit FG token OR inferred fog when (AIR_TEMP - DWPT) < 2 C, PRCP_10 < 0.2, and visibility < 1.0 km (VSBY or AWS_VSBY).",
      "Cloud classification uses cloud-base bins: 2000-1500 ft, 1500-1000 ft, 1000-500 ft, and <500 ft; mode toggles alter denominator.",
    ],
  },
  fog_share: {
    title: "Hourly Fog/Low Cloud Share",
    bullets: [
      "Shows time-of-day distribution of fog/low cloud occurrences across selected months and years.",
      "Fog logic: explicit FG token OR inferred fog when (AIR_TEMP - DWPT) < 2 C, PRCP_10 < 0.2, and visibility < 1.0 km (VSBY or AWS_VSBY).",
      "Cloud classification uses cloud-base bins: 2000-1500 ft, 1500-1000 ft, 1000-500 ft, and <500 ft, then aggregates by hour.",
    ],
  },
  cloud_distribution: {
    title: "Cloud Distribution vs Wind",
    bullets: [
      "Shows low-cloud behavior relative to wind direction and speed classes.",
      "Low-cloud membership is based on cloud amount coding (BKN/OVC) and cloud-base threshold bins (<2000/<1500/<1000/<500 ft).",
    ],
  },
  fog_cloud_joint: {
    title: "Fog/Cloud Joint Conditions",
    bullets: [
      "Relates fog/low-cloud occurrence to temperature-dewpoint spread groupings.",
      "Fog classification uses explicit FG or inferred fog criteria: spread < 2 C, PRCP_10 < 0.2, visibility < 1.0 km (VSBY/AWS_VSBY).",
      "Cloud classification uses cloud-base bins: 2000-1500 ft, 1500-1000 ft, 1000-500 ft, and <500 ft.",
    ],
  },
  monthly_smoke: {
    title: "Monthly Smoke/Dust Frequency",
    bullets: [
      "Monthly frequency of smoke/dust phenomena from configured code groups.",
      "Classification tokens are FU, DU, SA, and VA from present weather fields; values are month-aggregated from filtered observations.",
    ],
  },
  hourly_smoke: {
    title: "Hourly Smoke/Dust Frequency",
    bullets: [
      "Hour-of-day frequency profile for smoke/dust observations.",
      "Uses the same FU/DU/SA/VA token classification, then aggregates by hour.",
    ],
  },
  scatter_wind_dewpt: {
    title: "Wind Speed vs Dewpoint Spread",
    bullets: [
      "Scatter relationship between wind speed and dewpoint/temperature spread under smoke/dust conditions.",
      "Points are filtered to observations containing FU/DU/SA/VA tokens before plotting wind/dewpoint-spread relationship.",
    ],
  },
  radial_scatter_dust: {
    title: "Directional Smoke/Dust Relative Frequency",
    bullets: [
      "Polar-frequency view of smoke/dust phenomenon occurrence by direction and speed.",
      "Uses FU/DU/SA/VA classified observations grouped by direction and speed, normalized to relative frequency.",
    ],
  },
};

const API_BASE = (window.AVCLIMATE_API_BASE || "").replace(/\/+$/, "");

function apiUrl(path) {
  return API_BASE ? `${API_BASE}${path}` : path;
}

const state = {
  requestedSection: "overview",
  displayedSection: "overview",
  maximizedChartIndex: null,
  showErrorBars: false,
  fogModes: {
    monthly: "all",
    hourly: "all",
    wind: "all",
    dewpoint: "all",
  },
  options: null,
  latestFigures: [],
  axisLocks: {},
  stackedAxisLabelLocks: {},
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

const strictValueHoverFigureIds = new Set([
  "rain_thunder",
  "monthly_precip",
  "temp_dewpoint",
  "fog_low_cloud",
  "gale_weather_split",
  "monthly_fog",
  "fog_share",
  "monthly_smoke",
  "hourly_smoke",
  "fog_cloud_joint",
]);

const strictGroupedBarOverlayFigureIds = new Set([
  "rain_thunder",
  "monthly_precip",
  "monthly_smoke",
  "hourly_smoke",
]);

const strictStackedBarOverlayFigureIds = new Set([
  "fog_low_cloud",
  "gale_weather_split",
  "monthly_fog",
  "fog_share",
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
  season: document.getElementById("season"),
  enso: document.getElementById("enso"),
  iod: document.getElementById("iod"),
  sam: document.getElementById("sam"),
  mjo: document.getElementById("mjo"),
  errorBarsToggle: document.getElementById("error-bars-toggle"),
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
  infoBtn: document.getElementById("info-btn"),
  infoOverlay: document.getElementById("info-overlay"),
  infoCloseBtn: document.getElementById("info-close-btn"),
  infoBody: document.getElementById("info-body"),
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
  let maximizeButton = card.querySelector(".chart-maximize-btn");

  if (!shell) {
    shell = document.createElement("div");
    shell.className = "chart-shell";
    host.replaceWith(shell);
    shell.appendChild(host);

    legend = document.createElement("div");
    legend.className = "chart-legend hidden";
    shell.appendChild(legend);
  }

  if (!maximizeButton) {
    maximizeButton = document.createElement("button");
    maximizeButton.type = "button";
    maximizeButton.className = "chart-maximize-btn hidden";
    maximizeButton.setAttribute("aria-pressed", "false");
    maximizeButton.title = "Expand chart";
    maximizeButton.textContent = "Maximize";
    maximizeButton.addEventListener("click", () => {
      const chartIndex = Number(maximizeButton.dataset.chartIndex);
      state.maximizedChartIndex = state.maximizedChartIndex === chartIndex ? null : chartIndex;
      applyMaximizedChartState();
      if (state.latestFigures.length) {
        drawCharts(state.latestFigures, state.displayedSection);
      } else {
        applyChartShellHeights(state.displayedSection);
      }
    });
    card.appendChild(maximizeButton);
  }

  return { card, shell, legend, maximizeButton };
}

const chartUi = els.charts.map((host) => ensureChartShell(host));

let infoModalReturnFocusEl = null;

function isInfoModalOpen() {
  return Boolean(els.infoOverlay && !els.infoOverlay.classList.contains("hidden"));
}

function appendInfoSection(host, title, bullets) {
  const section = document.createElement("section");
  section.className = "info-section";

  const heading = document.createElement("h3");
  heading.textContent = title;
  section.appendChild(heading);

  if (Array.isArray(bullets) && bullets.length) {
    const list = renderInfoBulletList(bullets);
    section.appendChild(list);
  }
  host.appendChild(section);
}

function renderInfoBulletList(items) {
  const list = document.createElement("ul");
  list.className = "info-list";

  items.forEach((item) => {
    const li = document.createElement("li");
    if (typeof item === "string") {
      li.textContent = item;
      list.appendChild(li);
      return;
    }

    if (item && typeof item === "object") {
      if (typeof item.href === "string" && item.href.length) {
        const lead = typeof item.text === "string" ? item.text : "";
        if (lead) {
          li.appendChild(document.createTextNode(lead));
        }
        const link = document.createElement("a");
        link.href = item.href;
        link.target = "_blank";
        link.rel = "noopener noreferrer";
        link.textContent = String(item.linkText || item.href);
        li.appendChild(link);
        li.appendChild(document.createTextNode("."));
      } else {
        li.textContent = String(item.text || "");
      }
      if (Array.isArray(item.subBullets) && item.subBullets.length) {
        const subList = renderInfoBulletList(item.subBullets);
        li.appendChild(subList);
      }
      list.appendChild(li);
    }
  });

  return list;
}

function appendInfoSubsection(host, title, bullets) {
  const section = document.createElement("section");
  section.className = "info-subsection";

  const heading = document.createElement("h4");
  heading.textContent = title;
  section.appendChild(heading);

  if (Array.isArray(bullets) && bullets.length) {
    const list = renderInfoBulletList(bullets);
    section.appendChild(list);
  }
  host.appendChild(section);
}

function activeInfoSectionKey() {
  return state.requestedSection || state.displayedSection || "overview";
}

function activeFigureIdsForInfo(sectionKey) {
  const knownOrder = infoSectionOverview[sectionKey]?.figureOrder || [];
  const latestIds = state.latestFigures
    .map((entry) => (entry && typeof entry.id === "string" ? entry.id : ""))
    .filter((id) => id && Object.hasOwn(infoFigureDetails, id));

  if (latestIds.length) {
    const ordered = knownOrder.filter((id) => latestIds.includes(id));
    const extras = latestIds.filter((id) => !ordered.includes(id));
    return [...ordered, ...extras];
  }

  return knownOrder.filter((id) => Object.hasOwn(infoFigureDetails, id));
}

function renderInfoModalContent() {
  if (!els.infoBody) {
    return;
  }

  els.infoBody.innerHTML = "";

  const panels = document.createElement("div");
  panels.className = "info-panels";

  const dataPanel = document.createElement("section");
  dataPanel.className = "info-panel info-panel-data";
  appendInfoSection(dataPanel, infoDataSection.title, infoDataSection.bullets);
  appendInfoSubsection(dataPanel, infoObservationsSection.title, infoObservationsSection.bullets);
  appendInfoSubsection(dataPanel, infoClimateDriverSection.title, infoClimateDriverSection.bullets);

  const graphPanel = document.createElement("section");
  graphPanel.className = "info-panel info-panel-graphs";
  const graphPanelHeader = document.createElement("section");
  graphPanelHeader.className = "info-section";
  const graphHeading = document.createElement("h3");
  graphHeading.textContent = "Graph details";
  graphPanelHeader.appendChild(graphHeading);
  graphPanel.appendChild(graphPanelHeader);

  const sectionKey = activeInfoSectionKey();

  const figureIds = activeFigureIdsForInfo(sectionKey);
  figureIds.forEach((figureId) => {
    const detail = infoFigureDetails[figureId];
    if (!detail) {
      return;
    }
    appendInfoSubsection(graphPanel, detail.title, detail.bullets);
  });

  panels.appendChild(graphPanel);
  panels.appendChild(dataPanel);
  els.infoBody.appendChild(panels);
}

function openInfoModal() {
  if (!els.infoOverlay) {
    return;
  }
  renderInfoModalContent();
  infoModalReturnFocusEl = document.activeElement;
  els.infoOverlay.classList.remove("hidden");
  els.infoOverlay.setAttribute("aria-hidden", "false");
  document.body.classList.add("modal-open");
  if (els.infoCloseBtn) {
    els.infoCloseBtn.focus();
  }
}

function closeInfoModal() {
  if (!els.infoOverlay) {
    return;
  }
  els.infoOverlay.classList.add("hidden");
  els.infoOverlay.setAttribute("aria-hidden", "true");
  document.body.classList.remove("modal-open");
  if (infoModalReturnFocusEl && typeof infoModalReturnFocusEl.focus === "function") {
    infoModalReturnFocusEl.focus();
  }
}

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

function applyMaximizedChartState() {
  const hasMaximizedChart = Number.isInteger(state.maximizedChartIndex);
  const visibleCardCount = state.latestFigures.length ? Math.min(state.latestFigures.length, els.charts.length) : els.charts.length;
  const chartGrid = document.getElementById("chart-grid");
  if (chartGrid) {
    chartGrid.classList.toggle("has-maximized-chart", hasMaximizedChart);
    chartGrid.style.setProperty("--expanded-chart-rows", visibleCardCount > 2 ? "2" : "1");
  }

  chartUi.forEach(({ card, maximizeButton }, index) => {
    const isVisible = !card.classList.contains("hidden");
    const isMaximized = hasMaximizedChart && state.maximizedChartIndex === index && isVisible;
    const shouldHideForMaximized = hasMaximizedChart && state.maximizedChartIndex !== index && isVisible;
    card.classList.toggle("is-maximized", isMaximized);
    card.classList.toggle("is-hidden-for-maximized", shouldHideForMaximized);
    maximizeButton.dataset.chartIndex = String(index);
    maximizeButton.classList.toggle("hidden", !isVisible);
    maximizeButton.classList.toggle("is-active", isMaximized);
    maximizeButton.setAttribute("aria-pressed", isMaximized ? "true" : "false");
    maximizeButton.title = isMaximized ? "Restore chart grid" : "Expand chart";
    maximizeButton.textContent = isMaximized ? "Restore" : "Maximize";
  });
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

function seasonMonthConfig(season) {
  const configs = {
    all: { monthStart: 1, monthEnd: 12, invertMonth: false },
    summer: { monthStart: 2, monthEnd: 12, invertMonth: true },
    autumn: { monthStart: 3, monthEnd: 5, invertMonth: false },
    winter: { monthStart: 6, monthEnd: 8, invertMonth: false },
    spring: { monthStart: 9, monthEnd: 11, invertMonth: false },
    tropical_wet: { monthStart: 4, monthEnd: 10, invertMonth: true },
    tropical_dry: { monthStart: 5, monthEnd: 9, invertMonth: false },
  };

  return configs[season] || configs.all;
}

function applySeasonMonthRange() {
  const config = seasonMonthConfig(els.season.value);
  els.monthStart.value = String(config.monthStart);
  els.monthEnd.value = String(config.monthEnd);
  els.invertMonth.checked = config.invertMonth;
  updateSliderLabels();
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
  if (state.options) {
    return state.options;
  }

  if (fetchOptions.inFlightPromise) {
    await fetchOptions.inFlightPromise;
    return state.options;
  }

  fetchOptions.inFlightPromise = (async () => {
  const res = await fetch(apiUrl("/api/options"));
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
  })();

  try {
    await fetchOptions.inFlightPromise;
  } finally {
    fetchOptions.inFlightPromise = null;
  }

  return state.options;
}

function getParams() {
  const params = new URLSearchParams({
    section: state.requestedSection,
    season: els.season.value,
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

function getSectionFigureBatches(section) {
  if (section === "overview") {
    return [["wind_rose"], ["rain_thunder"], ["temp_dewpoint"], ["fog_low_cloud"]];
  }
  if (section === "wind") {
    return [["wind_rose"], ["gale_weather_split"]];
  }
  if (section === "fog_low_cloud") {
    return [["monthly_fog"], ["fog_share"], ["cloud_distribution"], ["fog_cloud_joint"]];
  }
  return [[]];
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
    { label: "Avg Temp", value: `${metrics.avgTemp.toFixed(1)} °C` },
  ];

  els.metrics.innerHTML = cards
    .map((card) => `<article class="metric"><div class="label">${card.label}</div><div class="value">${card.value}</div></article>`)
    .join("");
}

function clearChart(index) {
  const host = els.charts[index];
  const { card, shell, legend, maximizeButton } = chartUi[index];
  Plotly.purge(host);
  legend.innerHTML = "";
  legend.classList.add("hidden");
  shell.classList.add("no-legend");
  card.classList.add("hidden");
  card.classList.remove("is-maximized", "is-hidden-for-maximized");
  maximizeButton.classList.add("hidden");
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

function parseColorToRgb(color) {
  if (typeof color !== "string") {
    return null;
  }
  const trimmed = color.trim();
  if (!trimmed.length) {
    return null;
  }

  const hex = trimmed.match(/^#([0-9a-f]{3}|[0-9a-f]{6})$/i);
  if (hex) {
    let value = hex[1];
    if (value.length === 3) {
      value = value.split("").map((c) => c + c).join("");
    }
    return {
      r: parseInt(value.slice(0, 2), 16),
      g: parseInt(value.slice(2, 4), 16),
      b: parseInt(value.slice(4, 6), 16),
    };
  }

  const rgb = trimmed.match(/^rgba?\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)/i);
  if (rgb) {
    return {
      r: Math.max(0, Math.min(255, Number(rgb[1]))),
      g: Math.max(0, Math.min(255, Number(rgb[2]))),
      b: Math.max(0, Math.min(255, Number(rgb[3]))),
    };
  }

  return null;
}

function relativeLuminance({ r, g, b }) {
  const toLinear = (v) => {
    const c = v / 255;
    return c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4;
  };
  return (0.2126 * toLinear(r)) + (0.7152 * toLinear(g)) + (0.0722 * toLinear(b));
}

function contrastAwareErrorBarColor(trace, alpha = 0.96) {
  const rgb = parseColorToRgb(getTraceLegendColor(trace));
  if (!rgb) {
    return `rgba(17,24,39,${alpha})`;
  }
  const lum = relativeLuminance(rgb);
  // Dark bars/lines -> white error bars, light bars/lines -> near-black error bars.
  if (lum < 0.42) {
    return `rgba(255,255,255,${alpha})`;
  }
  return `rgba(17,24,39,${alpha})`;
}

function customErrorBarColor(trace, figureId = "", alpha = 0.96) {
  const id = String(figureId || "").trim();
  const name = String(trace?.name || "").trim().toLowerCase();

  if (id === "monthly_fog" || id === "fog_share") {
    if (name === "fog") {
      // Keep Fog as dark blue for contrast with light series.
      return `rgba(33,89,209,${alpha})`;
    }
    // Low-cloud categories are always white for these two charts.
    return `rgba(255,255,255,${alpha})`;
  }

  if (id === "fog_cloud_joint") {
    // Dewpoint panel: force white error bars for all categories.
    return `rgba(255,255,255,${alpha})`;
  }

  return contrastAwareErrorBarColor(trace, alpha);
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
  const withLinkedOverlays = (baseIndices) => {
    const linked = plotData
      .map((trace, index) => {
        const source = Number(trace?.meta?.sourceTrace);
        return Number.isInteger(source) && baseIndices.includes(source) ? index : -1;
      })
      .filter((index) => index >= 0);
    return Array.from(new Set([...baseIndices, ...linked]));
  };

  if (groupclick === "togglegroup" && item.legendgroup) {
    const baseIndices = plotData
      .map((trace, index) => (trace?.legendgroup === item.legendgroup ? index : -1))
      .filter((index) => index >= 0);
    return withLinkedOverlays(baseIndices);
  }

  return withLinkedOverlays([item.index]);
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

const fogWindHoverLayerSpecs = [
  { legendgroup: "Fog", label: "Fog", customdataIndex: 0 },
  { legendgroup: "2000ft - 1500ft cloud", label: "2000ft - 1500ft cloud", customdataIndex: 1 },
  { legendgroup: "1500ft - 1000ft cloud", label: "1500ft - 1000ft cloud", customdataIndex: 2 },
  { legendgroup: "1000ft - 500ft cloud", label: "1000ft - 500ft cloud", customdataIndex: 3 },
  { legendgroup: "< 500ft cloud", label: "< 500ft cloud", customdataIndex: 4 },
];

function buildFogWindHoverTemplate(visibleLayers) {
  const lines = [
    "%{theta:.0f}<br>",
    "%{r:.1f}",
  ];

  visibleLayers.forEach((layer) => {
    lines.push(`<br>%{customdata[${layer.customdataIndex}]:.3f}`);
  });

  return `${lines.join("")}<extra></extra>`;
}

function syncFogWindHoverTemplate(host) {
  const plotData = host?.data || [];
  const hoverTraceIndex = plotData.findIndex((trace) => trace?.meta?.hoverGrid === "fog_layer_values");
  if (hoverTraceIndex < 0) {
    return Promise.resolve();
  }

  const visibleLayers = fogWindHoverLayerSpecs.filter((layer) => {
    const groupIndices = plotData
      .map((trace, index) => (trace?.legendgroup === layer.legendgroup ? index : -1))
      .filter((index) => index >= 0);
    return groupIndices.some((traceIndex) => isTraceVisible(plotData[traceIndex]));
  });

  const hovertemplate = buildFogWindHoverTemplate(visibleLayers);
  return Plotly.restyle(host, { hovertemplate }, [hoverTraceIndex]);
}

function numericArray(values) {
  const decodedBinary = decodePlotlyBinaryArray(values);
  if (decodedBinary) {
    return decodedBinary;
  }

  if (Array.isArray(values)) {
    return values
      .map((v) => Number(v))
      .filter((v) => Number.isFinite(v));
  }
  if (values && typeof values.length === "number") {
    return Array.from(values)
      .map((v) => Number(v))
      .filter((v) => Number.isFinite(v));
  }
  if (values && typeof values === "object" && Array.isArray(values.data)) {
    return values.data
      .map((v) => Number(v))
      .filter((v) => Number.isFinite(v));
  }
  return [];
}

function tracePointCount(values) {
  const decodedBinary = decodePlotlyBinaryArray(values);
  if (decodedBinary) {
    return decodedBinary.length;
  }

  if (Array.isArray(values)) {
    return values.length;
  }
  if (values && typeof values.length === "number") {
    return values.length;
  }
  if (values && typeof values === "object" && Array.isArray(values.data)) {
    return values.data.length;
  }
  return 0;
}

function decodePlotlyBinaryArray(values) {
  if (!values || typeof values !== "object" || typeof values.bdata !== "string") {
    return null;
  }

  const dtypeRaw = String(values.dtype || "").toLowerCase();
  if (!dtypeRaw) {
    return null;
  }

  // Plotly can emit dtypes like "f8", "<f8", "|u1".
  const dtype = dtypeRaw.replace(/^[<>=|]/, "");
  const dtypeInfo = {
    f8: { ctor: Float64Array, bytes: 8 },
    f4: { ctor: Float32Array, bytes: 4 },
    i4: { ctor: Int32Array, bytes: 4 },
    u4: { ctor: Uint32Array, bytes: 4 },
    i2: { ctor: Int16Array, bytes: 2 },
    u2: { ctor: Uint16Array, bytes: 2 },
    i1: { ctor: Int8Array, bytes: 1 },
    u1: { ctor: Uint8Array, bytes: 1 },
  }[dtype];

  if (!dtypeInfo) {
    return null;
  }

  try {
    const binary = atob(values.bdata);
    const bytes = new Uint8Array(binary.length);
    for (let i = 0; i < binary.length; i += 1) {
      bytes[i] = binary.charCodeAt(i);
    }

    if (bytes.byteLength % dtypeInfo.bytes !== 0) {
      return null;
    }

    const typed = new dtypeInfo.ctor(bytes.buffer);
    return Array.from(typed)
      .map((value) => Number(value))
      .filter((value) => Number.isFinite(value));
  } catch {
    return null;
  }
}

function filledErrorArray(values, errorValue) {
  const count = tracePointCount(values);
  if (count <= 0) {
    return [];
  }
  return Array.from({ length: count }, () => errorValue);
}

function pointwiseStdArray(values) {
  const nums = (values || [])
    .map((v) => Number(v))
    .filter((v) => Number.isFinite(v));

  if (!nums.length) {
    return [];
  }

  const globalStd = stdDev(nums);
  if (nums.length === 1) {
    return [globalStd > 0 ? globalStd : 0];
  }

  return nums.map((_, idx) => {
    const left = Math.max(0, idx - 1);
    const right = Math.min(nums.length - 1, idx + 1);
    const localStd = stdDev(nums.slice(left, right + 1));
    if (localStd > 0) {
      return localStd;
    }
    return globalStd > 0 ? globalStd : 0;
  });
}

function representativeStd(values) {
  const valid = (values || [])
    .map((v) => Number(v))
    .filter((v) => Number.isFinite(v) && v > 0);
  if (!valid.length) {
    return 0;
  }
  const avg = valid.reduce((sum, v) => sum + v, 0) / valid.length;
  return Number.isFinite(avg) ? avg : 0;
}

function valueArray(values) {
  if (Array.isArray(values)) {
    return values.slice();
  }
  if (values && typeof values.length === "number") {
    return Array.from(values);
  }
  if (values && typeof values === "object" && Array.isArray(values.data)) {
    return values.data.slice();
  }
  const decodedBinary = decodePlotlyBinaryArray(values);
  return decodedBinary || [];
}

function axisLayoutKeyFromTraceAxis(axisRef, axisType) {
  const normalized = String(axisRef || axisType).toLowerCase();
  if (normalized === axisType) {
    return `${axisType}axis`;
  }
  const suffix = normalized.slice(axisType.length);
  return suffix ? `${axisType}axis${suffix}` : `${axisType}axis`;
}

function paddedAxisCeiling(axisMin, axisMax) {
  const min = Number(axisMin);
  const max = Number(axisMax);
  if (!Number.isFinite(max)) {
    return null;
  }
  const baseline = Number.isFinite(min) ? min : 0;
  const span = Math.max(max - baseline, Math.abs(max) * 0.1, 1);
  const padding = Math.max(span * 0.08, 0.4);
  return max + padding;
}

function traceBoundsWithError(trace) {
  const yVals = valueArray(trace?.y);
  const baseVals = valueArray(trace?.base);
  const errorY = trace?.error_y;
  const hasVisibleError = Boolean(errorY?.visible);
  const errVals = hasVisibleError ? valueArray(errorY?.array) : [];
  const errMinusVals = hasVisibleError ? valueArray(errorY?.arrayminus) : [];
  const fallbackPlus = hasVisibleError ? Number(errorY?.value) : 0;
  const symmetric = errorY?.symmetric !== false;
  const fallbackMinus = hasVisibleError
    ? (Number.isFinite(Number(errorY?.valueminus)) ? Number(errorY?.valueminus) : fallbackPlus)
    : 0;

  const count = Math.max(yVals.length, baseVals.length, errVals.length, errMinusVals.length);
  if (!count) {
    return null;
  }

  let minVal = Number.POSITIVE_INFINITY;
  let maxVal = Number.NEGATIVE_INFINITY;

  for (let i = 0; i < count; i += 1) {
    const yNum = Number(yVals[i]);
    const baseNum = Number(baseVals[i]);
    const center = (trace?.type === "bar" ? (Number.isFinite(baseNum) ? baseNum : 0) : 0)
      + (Number.isFinite(yNum) ? yNum : 0);

    if (!Number.isFinite(center)) {
      continue;
    }

    const errNum = Number(errVals[i]);
    const errPlus = Math.max(0, Number.isFinite(errNum) ? errNum : (Number.isFinite(fallbackPlus) ? fallbackPlus : 0));

    const errMinusNum = Number(errMinusVals[i]);
    const rawErrMinus = symmetric
      ? errPlus
      : (Number.isFinite(errMinusNum) ? errMinusNum : (Number.isFinite(fallbackMinus) ? fallbackMinus : 0));
    const errMinus = Math.max(0, rawErrMinus);

    minVal = Math.min(minVal, center - errMinus);
    maxVal = Math.max(maxVal, center + errPlus);
  }

  if (!Number.isFinite(minVal) || !Number.isFinite(maxVal)) {
    return null;
  }

  return { min: minVal, max: maxVal };
}

function maxWithError(trace) {
  const bounds = traceBoundsWithError(trace);
  return bounds ? bounds.max : null;
}

function traceUpperBound(trace) {
  const bounds = traceBoundsWithError(trace);
  return bounds ? bounds.max : null;
}

function expandAxesForErrorBars(host) {
  if (!host || host?.layout?.polar || !state.showErrorBars) {
    return Promise.resolve();
  }

  const traces = host.data || [];
  const axisMaxima = new Map();
  const barmode = String(host.layout?.barmode || "").toLowerCase();
  const stackByAxisAndX = new Map();

  traces.forEach((trace) => {
    if (!trace || String(trace.type || "").includes("polar") || !trace.error_y?.visible) {
      return;
    }

    const axisKey = axisLayoutKeyFromTraceAxis(trace.yaxis, "y");

    if (trace.type === "bar" && barmode === "stack") {
      const xValues = valueArray(trace.x);
      const yValues = numericArray(trace.y);
      const errValues = valueArray(trace.error_y?.array);
      const fallbackError = Number(trace.error_y?.value);

      for (let i = 0; i < yValues.length; i += 1) {
        const xKey = String(xValues[i] ?? i);
        const yNum = Number(yValues[i]);
        if (!Number.isFinite(yNum)) {
          continue;
        }

        const errNum = Number(errValues[i]);
        const err = Number.isFinite(errNum) ? errNum : (Number.isFinite(fallbackError) ? fallbackError : 0);
        const stackKey = `${axisKey}::${xKey}`;
        const entry = stackByAxisAndX.get(stackKey) || { total: 0, error: 0 };
        entry.total += yNum;
        entry.error = Math.max(entry.error, Math.max(0, err));
        stackByAxisAndX.set(stackKey, entry);
      }
      return;
    }

    const candidateMax = traceUpperBound(trace);
    if (!Number.isFinite(candidateMax)) {
      return;
    }
    const existing = axisMaxima.get(axisKey);
    axisMaxima.set(axisKey, existing == null ? candidateMax : Math.max(existing, candidateMax));
  });

  if (barmode === "stack") {
    stackByAxisAndX.forEach((entry, stackKey) => {
      const axisKey = stackKey.split("::")[0];
      const candidateMax = entry.total + entry.error;
      const existing = axisMaxima.get(axisKey);
      axisMaxima.set(axisKey, existing == null ? candidateMax : Math.max(existing, candidateMax));
    });
  }

  if (!axisMaxima.size) {
    return Promise.resolve();
  }

  const relayout = {};
  axisMaxima.forEach((axisMax, axisKey) => {
    const axisLayout = host.layout?.[axisKey];
    if (!axisLayout || !Array.isArray(axisLayout.range) || axisLayout.range.length < 2) {
      return;
    }

    const currentMin = Number(axisLayout.range[0]);
    const currentMax = Number(axisLayout.range[1]);
    if (!Number.isFinite(currentMin) || !Number.isFinite(currentMax)) {
      return;
    }

    const paddedMax = paddedAxisCeiling(currentMin, axisMax);
    if (Number.isFinite(paddedMax) && paddedMax > currentMax) {
      relayout[`${axisKey}.range`] = [currentMin, paddedMax];
      relayout[`${axisKey}.autorange`] = false;
    }
  });

  return Object.keys(relayout).length ? Plotly.relayout(host, relayout) : Promise.resolve();
}

function resolvedTracePoints(host, trace, traceIndex) {
  const xKey = axisLayoutKeyFromTraceAxis(trace?.xaxis, "x");
  const xAxisType = String(host?.layout?.[xKey]?.type || "").toLowerCase();
  const rawX = valueArray(trace?.x);
  const rawY = valueArray(trace?.y);

  const hasCategoricalX = xAxisType === "category"
    || rawX.some((val) => typeof val === "string" && val.length > 0);

  if (hasCategoricalX) {
    const x = [];
    const y = [];
    const count = Math.min(rawX.length, rawY.length);
    for (let i = 0; i < count; i += 1) {
      const yNum = Number(rawY[i]);
      if (!Number.isFinite(yNum)) {
        continue;
      }
      x.push(rawX[i]);
      y.push(yNum);
    }
    if (x.length && y.length && x.length === y.length) {
      return { x, y };
    }
  }

  const calc = host?.calcdata?.[traceIndex];
  if (Array.isArray(calc) && calc.length) {
    const x = [];
    const y = [];
    calc.forEach((point, idx) => {
      const yRaw = point?.y;
      const yNum = Number(yRaw);
      if (!Number.isFinite(yNum)) {
        return;
      }
      let xVal = point?.x;
      if (xVal == null && Array.isArray(trace?.x)) {
        xVal = trace.x[idx];
      }
      x.push(xVal);
      y.push(yNum);
    });
    if (x.length && y.length && x.length === y.length) {
      return { x, y };
    }
  }

  const xFallback = rawX;
  const yFallback = numericArray(trace?.y);
  const count = Math.min(xFallback.length || yFallback.length, yFallback.length);
  if (count <= 0) {
    return { x: [], y: [] };
  }
  return {
    x: (xFallback.length ? xFallback : Array.from({ length: count }, (_, i) => i)).slice(0, count),
    y: yFallback.slice(0, count),
  };
}

function resolvedBarTopPoints(host, trace, traceIndex) {
  const rawX = valueArray(trace?.x);
  const calc = host?.calcdata?.[traceIndex];
  if (Array.isArray(calc) && calc.length) {
    const x = [];
    const top = [];
    calc.forEach((point, idx) => {
      const yNum = Number(point?.y);
      if (!Number.isFinite(yNum)) {
        return;
      }
      const xVal = rawX[idx] != null ? rawX[idx] : point?.x;
      x.push(xVal);
      top.push(yNum);
    });
    if (x.length && top.length && x.length === top.length) {
      return { x, top };
    }
  }

  const yFallback = numericArray(trace?.y);
  const count = Math.min(rawX.length, yFallback.length);
  if (count <= 0) {
    return { x: [], top: [] };
  }
  return { x: rawX.slice(0, count), top: yFallback.slice(0, count) };
}

function stdDev(values) {
  if (!Array.isArray(values) || values.length < 2) {
    return 0;
  }
  const mean = values.reduce((sum, value) => sum + value, 0) / values.length;
  const variance = values.reduce((sum, value) => sum + ((value - mean) ** 2), 0) / (values.length - 1);
  return Number.isFinite(variance) && variance > 0 ? Math.sqrt(variance) : 0;
}

function supportsErrorBars(trace) {
  return trace?.type === "bar" || trace?.type === "scatter";
}

function isErrorBarOverlayTrace(trace) {
  return trace?.meta?.errorBarOverlay === true;
}

function isStrictValueErrorOverlayTrace(trace) {
  return trace?.meta?.strictValueErrorOverlay === true;
}

function clearPlotErrorBars(host) {
  const traces = host?.data || [];
  const restyles = [];
  traces.forEach((trace, traceIndex) => {
    if (!trace || String(trace.type || "").includes("polar") || !supportsErrorBars(trace)) {
      return;
    }
    clearTraceErrorBars(trace);
    restyles.push(Plotly.restyle(host, { error_y: null, error_x: null }, [traceIndex]));
  });
  return Promise.all(restyles).then(() => undefined);
}

function syncErrorBarOverlayVisibility(host) {
  const traces = host?.data || [];
  const indices = [];
  const values = [];

  traces.forEach((trace, index) => {
    if (!isErrorBarOverlayTrace(trace)) {
      return;
    }

    const sourceIndex = Number(trace?.meta?.sourceTrace);
    if (!Number.isInteger(sourceIndex) || sourceIndex < 0 || sourceIndex >= traces.length) {
      return;
    }

    const sourceTrace = traces[sourceIndex];
    const visible = isTraceVisible(sourceTrace) ? true : "legendonly";
    if (trace?.visible !== visible) {
      indices.push(index);
      values.push(visible);
    }
  });

  if (!indices.length) {
    return Promise.resolve();
  }

  return Plotly.restyle(host, { visible: values }, indices);
}

function rebuildStackErrorBarOverlays(host) {
  const isStackedBars = String(host?.layout?.barmode || "").toLowerCase() === "stack";
  if (!isStackedBars) {
    return Promise.resolve();
  }

  const figureId = host?.dataset?.figureId || "";
  if (strictValueHoverFigureIds.has(figureId)) {
    return Promise.resolve();
  }

  const overlayIndices = (host?.data || [])
    .map((trace, index) => (isErrorBarOverlayTrace(trace) ? index : -1))
    .filter((index) => index >= 0);

  const removeExisting = overlayIndices.length
    ? Plotly.deleteTraces(host, overlayIndices)
    : Promise.resolve();

  return removeExisting.then(() => {
    if (!state.showErrorBars) {
      return Promise.resolve();
    }
    const overlays = buildStackComponentOverlayTraces(host);
    return overlays.length ? Plotly.addTraces(host, overlays) : Promise.resolve();
  });
}

function buildStrictValueErrorOverlayTraces(host) {
  const traces = host?.data || [];
  const overlays = [];
  const figureId = host?.dataset?.figureId || "";
  const isStackedBars = String(host?.layout?.barmode || "").toLowerCase() === "stack";
  const useBarOverlaysForBars = strictGroupedBarOverlayFigureIds.has(figureId);

  if (isStackedBars && strictStackedBarOverlayFigureIds.has(figureId)) {
    const cumulativeByAxis = new Map();

    traces.forEach((trace, traceIndex) => {
      if (!trace || trace.type !== "bar" || isErrorBarOverlayTrace(trace) || String(trace.type || "").includes("polar")) {
        return;
      }
      if (!isTraceVisible(trace)) {
        return;
      }

      const xValues = valueArray(trace.x);
      const yValues = numericArray(trace.y);
      const count = Math.min(xValues.length, yValues.length);
      if (count <= 1) {
        return;
      }

      const yStdArray = pointwiseStdArray(yValues).slice(0, count);
      if (!yStdArray.some((v) => Number(v) > 0)) {
        return;
      }

      const axisKey = axisLayoutKeyFromTraceAxis(trace.yaxis, "y");
      const cumulative = cumulativeByAxis.get(axisKey) || new Map();
      const tops = [];
      const minus = [];

      for (let i = 0; i < count; i += 1) {
        const xKey = String(xValues[i] ?? i);
        const base = cumulative.get(xKey) || 0;
        const yNum = Number(yValues[i]);
        const top = base + (Number.isFinite(yNum) ? yNum : 0);
        cumulative.set(xKey, top);
        tops.push(top);

        const sd = Number(yStdArray[i]);
        const eff = Number.isFinite(sd) ? sd : 0;
        minus.push(Math.min(eff, Math.max(0, top)));
      }
      cumulativeByAxis.set(axisKey, cumulative);

      overlays.push({
        type: "scatter",
        mode: "markers",
        x: xValues.slice(0, count),
        y: tops,
        xaxis: trace.xaxis,
        yaxis: trace.yaxis,
        showlegend: false,
        hoverinfo: "skip",
        cliponaxis: false,
        visible: true,
        marker: {
          size: 2,
          opacity: 0,
          color: "rgba(0,0,0,0)",
        },
        error_y: {
          type: "data",
          array: yStdArray,
          arrayminus: minus,
          symmetric: false,
          visible: true,
          thickness: 1.8,
          width: 5,
          color: customErrorBarColor(trace, figureId),
        },
        meta: {
          errorBarOverlay: true,
          strictValueErrorOverlay: true,
          sourceTrace: traceIndex,
        },
        legendgroup: trace.legendgroup || null,
      });
    });

    return overlays;
  }

  traces.forEach((trace, traceIndex) => {
    if (!trace || String(trace.type || "").includes("polar") || !supportsErrorBars(trace)) {
      return;
    }
    if (isErrorBarOverlayTrace(trace)) {
      return;
    }

    const yValues = numericArray(trace.y);
    const xValues = valueArray(trace.x);
    const count = Math.min(yValues.length, xValues.length || yValues.length);
    if (count <= 1) {
      return;
    }

    const yStdArray = pointwiseStdArray(yValues).slice(0, count);
    const yStd = representativeStd(yStdArray);
    if (!yStdArray.some((v) => Number(v) > 0)) {
      return;
    }

    const x = (xValues.length ? xValues : Array.from({ length: count }, (_, i) => i)).slice(0, count);
    const y = yValues.slice(0, count);

    const errorY = {
      type: "data",
      array: yStdArray,
      arrayminus: y.map((value, i) => {
        const numericValue = Number(value);
        if (!Number.isFinite(numericValue)) {
          return 0;
        }
        const sd = Number(yStdArray[i]);
        const eff = Number.isFinite(sd) ? sd : yStd;
        return Math.min(eff, Math.max(0, numericValue));
      }),
      symmetric: false,
      visible: true,
      thickness: 1.8,
      width: 5,
      color: customErrorBarColor(trace, figureId),
    };

    if (trace.type === "bar" && useBarOverlaysForBars) {
      overlays.push({
        type: "bar",
        x,
        y,
        xaxis: trace.xaxis,
        yaxis: trace.yaxis,
        showlegend: false,
        hoverinfo: "skip",
        visible: isTraceVisible(trace) ? true : "legendonly",
        marker: {
          color: "rgba(0,0,0,0)",
          opacity: 0,
          line: {
            color: "rgba(0,0,0,0)",
            width: 0,
          },
        },
        width: trace.width,
        offset: trace.offset,
        offsetgroup: trace.offsetgroup,
        alignmentgroup: trace.alignmentgroup,
        base: trace.base,
        error_y: errorY,
        meta: {
          errorBarOverlay: true,
          strictValueErrorOverlay: true,
          sourceTrace: traceIndex,
        },
        legendgroup: trace.legendgroup || null,
      });
      return;
    }

    if (trace.type === "bar") {
      const points = resolvedBarTopPoints(host, trace, traceIndex);
      const px = (points.x && points.x.length) ? points.x : x;
      const py = (points.top && points.top.length) ? points.top : y;
      overlays.push({
        type: "scatter",
        mode: "markers",
        x: px,
        y: py,
        xaxis: trace.xaxis,
        yaxis: trace.yaxis,
        showlegend: false,
        hoverinfo: "skip",
        cliponaxis: false,
        visible: isTraceVisible(trace) ? true : "legendonly",
        marker: {
          size: 2,
          opacity: 0,
          color: "rgba(0,0,0,0)",
        },
        error_y: errorY,
        meta: {
          errorBarOverlay: true,
          strictValueErrorOverlay: true,
          sourceTrace: traceIndex,
        },
        legendgroup: trace.legendgroup || null,
      });
      return;
    }

    overlays.push({
      type: "scatter",
      mode: "markers",
      x,
      y,
      xaxis: trace.xaxis,
      yaxis: trace.yaxis,
      showlegend: false,
      hoverinfo: "skip",
      cliponaxis: false,
      visible: isTraceVisible(trace) ? true : "legendonly",
      marker: {
        size: 2,
        opacity: 0,
        color: "rgba(0,0,0,0)",
      },
      error_y: errorY,
      meta: {
        errorBarOverlay: true,
        strictValueErrorOverlay: true,
        sourceTrace: traceIndex,
      },
      legendgroup: trace.legendgroup || null,
    });
  });

  return overlays;
}

function rebuildStrictValueErrorBarOverlays(host) {
  const figureId = host?.dataset?.figureId || "";
  if (!strictValueHoverFigureIds.has(figureId)) {
    return Promise.resolve();
  }

  const overlayIndices = (host?.data || [])
    .map((trace, index) => (isStrictValueErrorOverlayTrace(trace) ? index : -1))
    .filter((index) => index >= 0);

  const removeExisting = overlayIndices.length
    ? Plotly.deleteTraces(host, overlayIndices)
    : Promise.resolve();

  return removeExisting.then(() => {
    if (!state.showErrorBars) {
      return Promise.resolve();
    }
    const overlays = buildStrictValueErrorOverlayTraces(host);
    return overlays.length ? Plotly.addTraces(host, overlays) : Promise.resolve();
  });
}

function buildStackComponentOverlayTraces(host) {
  const traces = host?.data || [];
  const barmode = String(host?.layout?.barmode || "").toLowerCase();
  if (barmode !== "stack") {
    return [];
  }

  const cumulativeByAxis = new Map();
  const overlays = [];
  const figureId = host?.dataset?.figureId || "";

  traces.forEach((trace, traceIndex) => {
    if (!trace || trace.type !== "bar" || isErrorBarOverlayTrace(trace) || String(trace.type || "").includes("polar")) {
      return;
    }
    if (!isTraceVisible(trace)) {
      return;
    }

    const xValues = valueArray(trace.x);
    const yValues = numericArray(trace.y);
    const count = Math.min(xValues.length, yValues.length);
    if (count <= 1) {
      return;
    }

    const yStd = stdDev(yValues);
    if (!Number.isFinite(yStd) || yStd <= 0) {
      return;
    }

    const axisKey = axisLayoutKeyFromTraceAxis(trace.yaxis, "y");
    const cumulative = cumulativeByAxis.get(axisKey) || new Map();

    const tops = [];
    const minus = [];
    for (let i = 0; i < count; i += 1) {
      const xKey = String(xValues[i] ?? i);
      const base = cumulative.get(xKey) || 0;
      const yNum = Number(yValues[i]);
      const top = base + (Number.isFinite(yNum) ? yNum : 0);
      cumulative.set(xKey, top);
      tops.push(top);
      minus.push(Math.min(yStd, Math.max(0, top)));
    }
    cumulativeByAxis.set(axisKey, cumulative);

    overlays.push({
      type: "scatter",
      mode: "markers",
      x: xValues.slice(0, count),
      y: tops,
      xaxis: trace.xaxis,
      yaxis: trace.yaxis,
      showlegend: false,
      hoverinfo: "skip",
      cliponaxis: false,
      marker: {
        size: 2,
        opacity: 0,
        color: "rgba(0,0,0,0)",
      },
      error_y: {
        type: "data",
        array: Array.from({ length: count }, () => yStd),
        arrayminus: minus,
        symmetric: false,
        visible: true,
        thickness: 1.8,
        width: 5,
        color: customErrorBarColor(trace, figureId),
      },
      meta: {
        errorBarOverlay: true,
        stackErrorOverlay: true,
        sourceTrace: traceIndex,
      },
      legendgroup: trace.legendgroup || null,
    });
  });

  return overlays;
}

function buildStackOverlayTraces(host) {
  const traces = host?.data || [];
  const barmode = String(host?.layout?.barmode || "").toLowerCase();
  const figureId = host?.dataset?.figureId || "";
  if (barmode !== "stack") {
    return [];
  }

  const grouped = new Map();
  traces.forEach((trace) => {
    if (!trace || trace.type !== "bar" || String(trace.type || "").includes("polar")) {
      return;
    }
    const axisKey = axisLayoutKeyFromTraceAxis(trace.yaxis, "y");
    const xValues = valueArray(trace.x);
    const yValues = numericArray(trace.y);
    if (!xValues.length || !yValues.length) {
      return;
    }
    const axisGroup = grouped.get(axisKey) || { order: [], totals: new Map() };
    const count = Math.min(xValues.length, yValues.length);
    for (let i = 0; i < count; i += 1) {
      const xKey = String(xValues[i]);
      const yNum = Number(yValues[i]);
      if (!Number.isFinite(yNum)) {
        continue;
      }
      if (!axisGroup.totals.has(xKey)) {
        axisGroup.totals.set(xKey, 0);
        axisGroup.order.push(xValues[i]);
      }
      axisGroup.totals.set(xKey, axisGroup.totals.get(xKey) + yNum);
    }
    grouped.set(axisKey, axisGroup);
  });

  const overlays = [];
  grouped.forEach((axisGroup, axisKey) => {
    const sourceTrace = traces.find((trace) => axisLayoutKeyFromTraceAxis(trace?.yaxis, "y") === axisKey && trace?.type === "bar") || null;
    const totals = axisGroup.order.map((xVal) => axisGroup.totals.get(String(xVal)) || 0);
    const pointCount = totals.length;
    if (pointCount <= 1) {
      return;
    }

    const totalStd = stdDev(totals);
    if (totalStd <= 0) {
      return;
    }

    overlays.push({
      type: "scatter",
      mode: "markers",
      x: axisGroup.order,
      y: totals,
      xaxis: "x",
      yaxis: axisKey.replace("axis", ""),
      showlegend: false,
      hoverinfo: "skip",
      cliponaxis: false,
      marker: {
        size: 2,
        opacity: 0,
        color: "rgba(0,0,0,0)",
      },
      error_y: {
        type: "data",
        array: Array.from({ length: pointCount }, () => totalStd),
        arrayminus: totals.map((value) => {
          const numericValue = Number(value);
          if (!Number.isFinite(numericValue)) {
            return 0;
          }
          return Math.min(totalStd, Math.max(0, numericValue));
        }),
        symmetric: false,
        visible: true,
        thickness: 1.8,
        width: 5,
        color: customErrorBarColor(sourceTrace, figureId),
      },
      meta: {
        errorBarOverlay: true,
        stackErrorOverlay: true,
      },
    });
  });

  return overlays;
}

function clearTraceErrorBars(trace) {
  delete trace.error_y;
  delete trace.error_x;
}

function sanitizeBaseHovertemplate(template) {
  if (typeof template !== "string" || !template.length) {
    return template;
  }

  const bodyOnly = template
    .replace(/<extra>[\s\S]*?<\/extra>/gi, "")
    .replace(/\s*[+\-]\s*%\{error_[^}]+\}/gi, "")
    .replace(/\s*\/\s*[-+]?\s*%\{error_[^}]+\}/gi, "")
    .replace(/%\{error_[^}]+\}/gi, "");

  const tokens = bodyOnly.match(/%\{[^}]+\}/g) || [];
  const yToken = tokens.find((token) => /^%\{y[^}]*\}$/i.test(token));
  const rToken = tokens.find((token) => /^%\{r[^}]*\}$/i.test(token));
  const fallbackToken = tokens.find((token) => !/^%\{(?:x|theta|customdata|text|fullData\.)/i.test(token));
  const valueToken = yToken || rToken || fallbackToken || null;

  if (!valueToken) {
    return "<extra></extra>";
  }

  return `${valueToken}<extra></extra>`;
}

function axisTitleText(layout, axisKey) {
  const axis = layout?.[axisKey];
  if (!axis) {
    return "";
  }
  if (typeof axis.title === "string") {
    return axis.title;
  }
  if (axis.title && typeof axis.title.text === "string") {
    return axis.title.text;
  }
  return "";
}

function inferUnitFromAxisTitle(titleText) {
  if (typeof titleText !== "string" || !titleText.trim().length) {
    return "";
  }
  const text = titleText.trim();
  const inParens = text.match(/\(([^)]+)\)\s*$/);
  if (inParens && inParens[1]) {
    return inParens[1].trim();
  }
  const slashUnit = text.match(/([A-Za-z%]+\/[A-Za-z%]+)\s*$/);
  if (slashUnit && slashUnit[1]) {
    return slashUnit[1].trim();
  }
  const shortUnit = text.match(/\b(kt|kts|kn|mm|cm|m|C|F|K|%)\b\s*$/i);
  if (shortUnit && shortUnit[1]) {
    return shortUnit[1].trim();
  }
  return "";
}

function inferUnitFromTemplate(template) {
  if (typeof template !== "string" || !template.length) {
    return "";
  }
  const bodyOnly = template.replace(/<extra>[\s\S]*?<\/extra>/gi, "");
  const match = bodyOnly.match(/%\{(?:y|r)[^}]*\}\s*([^<\n\r]*)/i);
  if (!match || typeof match[1] !== "string") {
    return "";
  }
  const suffix = match[1]
    .replace(/^[:=\s-]+/, "")
    .replace(/\+\/-.*/i, "")
    .trim();
  if (!suffix.length || /%\{[^}]+\}/.test(suffix)) {
    return "";
  }
  return suffix;
}

function normalizeUnitSuffix(unitText) {
  if (typeof unitText !== "string") {
    return "";
  }
  let unit = unitText.trim();
  if (!unit.length) {
    return "";
  }
  if (/^c$/i.test(unit) || /^celsius$/i.test(unit)) {
    unit = "°C";
  }
  unit = unit.replace(/\(\s*c\s*\)/gi, "(°C)").replace(/(^|\s)c(\b)/gi, (match, lead, tail) => `${lead}°C${tail}`);
  if (unit.startsWith("%") || unit.startsWith("/")) {
    return unit;
  }
  return ` ${unit}`;
}

function ensureBaseHovertemplate(trace, layout = null) {
  if (!trace) {
    return null;
  }
  trace.meta = trace.meta || {};
  if (!Object.prototype.hasOwnProperty.call(trace.meta, "baseHovertemplate")) {
    const original = (typeof trace.hovertemplate === "string") ? trace.hovertemplate : null;
    trace.meta.baseHovertemplate = sanitizeBaseHovertemplate(original);
    const axisKey = axisLayoutKeyFromTraceAxis(trace.yaxis, "y");
    const axisUnit = inferUnitFromAxisTitle(axisTitleText(layout, axisKey));
    const templateUnit = inferUnitFromTemplate(original);
    trace.meta.hoverUnitSuffix = normalizeUnitSuffix(templateUnit || axisUnit);
  } else if (!Object.prototype.hasOwnProperty.call(trace.meta, "hoverUnitSuffix")) {
    const axisKey = axisLayoutKeyFromTraceAxis(trace.yaxis, "y");
    const axisUnit = inferUnitFromAxisTitle(axisTitleText(layout, axisKey));
    trace.meta.hoverUnitSuffix = normalizeUnitSuffix(axisUnit);
  }
  return trace.meta.baseHovertemplate;
}

function valueTokenWithTwoDecimals(baseTemplate) {
  const rawToken = primaryValueTokenFromTemplate(baseTemplate);
  const parsed = rawToken.match(/^%\{([^}:]+)(?::[^}]*)?\}$/);
  if (!parsed || !parsed[1]) {
    return "%{y:.2f}";
  }
  const ref = parsed[1].trim();
  if (!ref.length) {
    return "%{y:.2f}";
  }
  return `%{${ref}:.2f}`;
}

function hovertemplateWithStd(baseTemplate, sdValue = null, unitSuffix = "") {
  const valueToken = valueTokenWithTwoDecimals(baseTemplate);
  const unit = typeof unitSuffix === "string" ? unitSuffix : "";
  if (!Number.isFinite(sdValue) || sdValue <= 0) {
    return `${valueToken}${unit}<extra></extra>`;
  }
  return `${valueToken}${unit} ± ${Number(sdValue).toFixed(2)}${unit}<extra></extra>`;
}

function primaryValueTokenFromTemplate(baseTemplate) {
  const template = (typeof baseTemplate === "string" && baseTemplate.length)
    ? baseTemplate
    : "%{y:.2f}<extra></extra>";
  const tokens = template.match(/%\{[^}]+\}/g) || [];
  const yToken = tokens.find((token) => /^%\{y[^}]*\}$/i.test(token));
  const rToken = tokens.find((token) => /^%\{r[^}]*\}$/i.test(token));
  return yToken || rToken || "%{y:.2f}";
}

function strictValueHovertemplate(baseTemplate, sdValue = null, unitSuffix = "") {
  const valueToken = valueTokenWithTwoDecimals(baseTemplate);
  const unit = typeof unitSuffix === "string" ? unitSuffix : "";
  if ((typeof sdValue === "string" && sdValue.length > 0)) {
    return `${valueToken}${unit} ± ${sdValue}${unit}<extra></extra>`;
  }
  if (!Number.isFinite(sdValue) || sdValue <= 0) {
    return `${valueToken}${unit}<extra></extra>`;
  }
  return `${valueToken}${unit} ± ${Number(sdValue).toFixed(2)}${unit}<extra></extra>`;
}

function strictValueHovertemplateArray(baseTemplate, sdValues = [], unitSuffix = "") {
  return (sdValues || []).map((sd) => strictValueHovertemplate(baseTemplate, Number(sd), unitSuffix));
}

function applyStrictValueHoverTemplatesToFigure(figure, figureId) {
  if (!strictValueHoverFigureIds.has(figureId)) {
    return;
  }

  const traces = figure?.data || [];
  traces.forEach((trace) => {
    if (!trace || String(trace.type || "").includes("polar") || !supportsErrorBars(trace)) {
      return;
    }

    const baseHover = ensureBaseHovertemplate(trace, figure?.layout);
    const unitSuffix = trace?.meta?.hoverUnitSuffix || "";
    const yValues = numericArray(trace.y);
    const yStdArray = pointwiseStdArray(yValues);
    if (state.showErrorBars && yValues.length > 1 && yStdArray.some((v) => Number(v) > 0)) {
      trace.customdata = null;
      trace.hovertemplate = strictValueHovertemplateArray(baseHover, yStdArray, unitSuffix);
    } else {
      trace.customdata = null;
      trace.hovertemplate = strictValueHovertemplate(baseHover, null, unitSuffix);
    }
  });
}

function applyTraceErrorBars(trace) {
  if (!supportsErrorBars(trace)) {
    clearTraceErrorBars(trace);
    return;
  }

  const yValues = numericArray(trace.y);
  const yStdArray = pointwiseStdArray(yValues);
  if (yValues.length > 1 && yStdArray.some((v) => Number(v) > 0)) {
    trace.error_y = {
      type: "data",
      array: yStdArray,
      visible: true,
      thickness: 1.8,
      width: 5,
      color: contrastAwareErrorBarColor(trace),
    };
  } else {
    delete trace.error_y;
  }

  const xValues = numericArray(trace.x);
  const xStdArray = pointwiseStdArray(xValues);
  const mode = String(trace.mode || "").toLowerCase();
  const isScatter = trace.type === "scatter";
  if (isScatter && xValues.length > 1 && xStdArray.some((v) => Number(v) > 0)) {
    trace.error_x = {
      type: "data",
      array: xStdArray,
      visible: true,
      thickness: 1.8,
      width: 5,
      color: contrastAwareErrorBarColor(trace, 0.9),
    };
  } else {
    delete trace.error_x;
  }
}

function applyFigureErrorBars(figure) {
  if (figure?.layout?.polar) {
    return;
  }

  const traces = figure?.data || [];
  traces.forEach((trace) => {
    if (String(trace?.type || "").includes("polar")) {
      clearTraceErrorBars(trace);
      return;
    }
    if (!supportsErrorBars(trace)) {
      return;
    }
    if (!state.showErrorBars) {
      clearTraceErrorBars(trace);
      return;
    }
    applyTraceErrorBars(trace);
  });
}

function restyleSingleTrace(host, traceIndex, update) {
  const payload = { ...update };
  // For Plotly.restyle on a single trace, per-point hovertemplate arrays
  // must be wrapped once more to avoid collapsing to a single value.
  if (Array.isArray(payload.hovertemplate)) {
    payload.hovertemplate = [payload.hovertemplate];
  }
  return Plotly.restyle(host, payload, [traceIndex]);
}

function applyHostErrorBars(host) {
  if (!host || host?.layout?.polar) {
    return Promise.resolve();
  }

  const figureId = host.dataset.figureId || "";
  const useStrictValueHover = strictValueHoverFigureIds.has(figureId);

  if (figureId === "scatter_wind_dewpt") {
    const traces = host.data || [];
    const ciIndices = traces
      .map((trace, index) => (trace?.meta?.ciBand === true ? index : -1))
      .filter((index) => index >= 0);
    const restyles = [];
    const pointHovertemplate = "Dew Point: %{x:.2f} °C<br>Wind Speed: %{y:.2f} kt<extra></extra>";

    traces.forEach((trace, traceIndex) => {
      const baseHover = ensureBaseHovertemplate(trace, host?.layout);
      const unitSuffix = trace?.meta?.hoverUnitSuffix || "";
      if (!trace || isErrorBarOverlayTrace(trace) || String(trace.type || "").includes("polar") || !supportsErrorBars(trace)) {
        return;
      }
      clearTraceErrorBars(trace);
      const mode = String(trace.mode || "").toLowerCase();
      const isPointTrace = trace.type === "scatter" && mode.includes("markers") && trace?.meta?.ciBand !== true;
      const hovertemplate = isPointTrace
        ? pointHovertemplate
        : hovertemplateWithStd(baseHover, null, unitSuffix);
      const update = {
        error_y: null,
        error_x: null,
        hovertemplate,
      };
      if (useStrictValueHover && !isPointTrace) {
        update.customdata = null;
      }
      restyles.push(restyleSingleTrace(host, traceIndex, update));
    });

    if (ciIndices.length) {
      const ciVisible = state.showErrorBars ? true : "legendonly";
      restyles.push(Plotly.restyle(host, { visible: ciVisible }, ciIndices));
    }

    return Promise.all(restyles).then(() => {
      if (!state.showErrorBars || !ciIndices.length) {
        return undefined;
      }

      const ciMax = ciIndices.reduce((maxVal, idx) => {
        const yVals = numericArray(host.data[idx]?.y);
        if (!yVals.length) {
          return maxVal;
        }
        const localMax = Math.max(...yVals);
        return Math.max(maxVal, localMax);
      }, Number.NEGATIVE_INFINITY);

      if (!Number.isFinite(ciMax)) {
        return undefined;
      }

      const yAxis = host.layout?.yaxis;
      if (!yAxis || !Array.isArray(yAxis.range) || yAxis.range.length < 2) {
        return undefined;
      }

      const currentMin = Number(yAxis.range[0]);
      const currentMax = Number(yAxis.range[1]);
      if (!Number.isFinite(currentMin) || !Number.isFinite(currentMax)) {
        return undefined;
      }

      const paddedMax = ciMax * 1.08;
      if (paddedMax > currentMax) {
        return Plotly.relayout(host, { "yaxis.range": [currentMin, paddedMax], "yaxis.autorange": false });
      }
      return undefined;
    });
  }

  const traces = host.data || [];
  const restylePromises = [];
  const axisMaxima = new Map();
  const isStackedBars = String(host.layout?.barmode || "").toLowerCase() === "stack";

  traces.forEach((trace, traceIndex) => {
    const baseHover = ensureBaseHovertemplate(trace, host?.layout);
    const unitSuffix = trace?.meta?.hoverUnitSuffix || "";
    const isStackedBarTrace = isStackedBars && trace?.type === "bar";
    if (!trace || isErrorBarOverlayTrace(trace) || String(trace.type || "").includes("polar") || !supportsErrorBars(trace)) {
      clearTraceErrorBars(trace);
      return;
    }

    clearTraceErrorBars(trace);
    if (!state.showErrorBars) {
      const hovertemplate = useStrictValueHover
        ? strictValueHovertemplate(baseHover, null, unitSuffix)
        : hovertemplateWithStd(baseHover, null, unitSuffix);
      const update = { error_y: null, error_x: null, hovertemplate };
      if (useStrictValueHover) {
        update.customdata = null;
      }
      restylePromises.push(restyleSingleTrace(host, traceIndex, update));
      return;
    }

    const yValues = numericArray(trace.y);
    const yStdArray = pointwiseStdArray(yValues);
    const yStd = representativeStd(yStdArray);
    const yCount = tracePointCount(trace.y);
    if (yCount <= 1 || !yStdArray.some((v) => Number(v) > 0)) {
      const hovertemplate = useStrictValueHover
        ? strictValueHovertemplate(baseHover, null, unitSuffix)
        : hovertemplateWithStd(baseHover, null, unitSuffix);
      const update = { error_y: null, error_x: null, hovertemplate };
      if (useStrictValueHover) {
        update.customdata = null;
      }
      restylePromises.push(restyleSingleTrace(host, traceIndex, update));
      return;
    }

    const yError = {
      type: "data",
      array: yStdArray.slice(0, yCount),
      arrayminus: yValues.slice(0, yCount).map((value, i) => {
        const numericValue = Number(value);
        if (!Number.isFinite(numericValue)) {
          return 0;
        }
        const sd = Number(yStdArray[i]);
        const eff = Number.isFinite(sd) ? sd : yStd;
        return Math.min(eff, Math.max(0, numericValue));
      }),
      symmetric: false,
      visible: true,
      thickness: 1.8,
      width: 5,
      color: customErrorBarColor(trace, figureId),
    };

    const update = {
      error_y: (isStackedBarTrace || useStrictValueHover) ? null : yError,
      hovertemplate: useStrictValueHover
        ? strictValueHovertemplateArray(baseHover, yStdArray.slice(0, yCount), unitSuffix)
        : hovertemplateWithStd(baseHover, yStd, unitSuffix),
    };
    if (useStrictValueHover) {
      update.customdata = null;
    }

    if (trace.type === "scatter") {
      const xValues = numericArray(trace.x);
      const xStdArray = pointwiseStdArray(xValues);
      const xCount = tracePointCount(trace.x);
      if (!useStrictValueHover && xCount > 1 && xStdArray.some((v) => Number(v) > 0)) {
        update.error_x = {
          type: "data",
          array: xStdArray.slice(0, xCount),
          symmetric: true,
          visible: true,
          thickness: 1.8,
          width: 5,
          color: customErrorBarColor(trace, figureId, 0.9),
        };
      }
    }

    if (!isStackedBarTrace) {
      const candidateMax = maxWithError({
        ...trace,
        error_y: yError,
      });
      if (Number.isFinite(candidateMax)) {
        const axisKey = axisLayoutKeyFromTraceAxis(trace.yaxis, "y");
        const existing = axisMaxima.get(axisKey);
        axisMaxima.set(axisKey, existing == null ? candidateMax : Math.max(existing, candidateMax));
      }
    }

    restylePromises.push(restyleSingleTrace(host, traceIndex, update));
  });

  return Promise.all(restylePromises)
    .then(() => {
      const relayout = {};
      axisMaxima.forEach((axisMax, axisKey) => {
        const axisLayout = host.layout?.[axisKey];
        if (!axisLayout || !Array.isArray(axisLayout.range) || axisLayout.range.length < 2) {
          return;
        }

        const currentMin = Number(axisLayout.range[0]);
        const currentMax = Number(axisLayout.range[1]);
        if (!Number.isFinite(currentMin) || !Number.isFinite(currentMax)) {
          return;
        }

        const paddedMax = paddedAxisCeiling(currentMin, axisMax);
        if (Number.isFinite(paddedMax) && paddedMax > currentMax) {
          relayout[`${axisKey}.range`] = [currentMin, paddedMax];
          relayout[`${axisKey}.autorange`] = false;
        }
      });

      const relayoutPromise = Object.keys(relayout).length ? Plotly.relayout(host, relayout) : Promise.resolve();

      if (!isStackedBars) {
        if (!useStrictValueHover) {
          return relayoutPromise;
        }
        return relayoutPromise
          .then(() => rebuildStrictValueErrorBarOverlays(host))
          .then(() => syncErrorBarOverlayVisibility(host));
      }

      const overlayIndices = (host.data || [])
        .map((trace, index) => (isErrorBarOverlayTrace(trace) ? index : -1))
        .filter((index) => index >= 0);

      return relayoutPromise
        .then(() => (overlayIndices.length ? Plotly.deleteTraces(host, overlayIndices) : Promise.resolve()))
        .then(() => {
          if (!state.showErrorBars || useStrictValueHover) {
            return Promise.resolve();
          }
          const overlays = buildStackComponentOverlayTraces(host);
          return overlays.length ? Plotly.addTraces(host, overlays) : Promise.resolve();
        })
        .then(() => rebuildStrictValueErrorBarOverlays(host))
        .then(() => syncErrorBarOverlayVisibility(host));
    });
}

function renderErrorBarsToggle() {
  const button = els.errorBarsToggle;
  if (!button) {
    return;
  }
  const enabled = state.showErrorBars;
  button.textContent = enabled ? "On" : "Off";
  button.classList.toggle("is-active", enabled);
  button.setAttribute("aria-pressed", enabled ? "true" : "false");
}

function computeAxisBounds(figure, axisName = "y") {
  const data = figure?.data || [];
  const layout = figure?.layout || {};
  const barmode = String(layout.barmode || "").toLowerCase();
  const stackByX = barmode === "stack" ? new Map() : null;
  let minValue = Number.POSITIVE_INFINITY;
  let maxValue = Number.NEGATIVE_INFINITY;

  data.forEach((trace) => {
    if (!trace || trace.visible === false || trace.visible === "legendonly") {
      return;
    }

    const traceAxis = trace.yaxis || "y";
    if (traceAxis !== axisName) {
      return;
    }

    if (trace.type === "bar" && stackByX) {
      const yValues = numericArray(trace.y);
      if (!yValues.length) {
        return;
      }
      const xValues = Array.isArray(trace.x) ? trace.x : yValues.map((_, idx) => idx);
      yValues.forEach((yVal, idx) => {
        const xKey = String(xValues[idx] ?? idx);
        stackByX.set(xKey, (stackByX.get(xKey) || 0) + yVal);
      });
      return;
    }

    const bounds = traceBoundsWithError(trace);
    if (!bounds) {
      return;
    }
    minValue = Math.min(minValue, bounds.min);
    maxValue = Math.max(maxValue, bounds.max);
  });

  if (stackByX && stackByX.size) {
    const stackedValues = Array.from(stackByX.values());
    const stackMin = Math.min(...stackedValues);
    const stackMax = Math.max(...stackedValues);
    minValue = Math.min(minValue, stackMin);
    maxValue = Math.max(maxValue, stackMax);
  }

  if (!Number.isFinite(minValue) || !Number.isFinite(maxValue)) {
    return null;
  }

  if (minValue >= 0) {
    minValue = 0;
  }

  if (maxValue <= minValue) {
    maxValue = minValue + 1;
  }

  const span = maxValue - minValue;
  const upperPad = Math.max(span * 0.12, 0.5);
  const lowerPad = minValue < 0 ? Math.max(span * 0.04, 0.25) : 0;
  return {
    min: minValue - lowerPad,
    max: maxValue + upperPad,
  };
}

function expandAxisLock(lock, candidate) {
  if (!candidate) {
    return lock || null;
  }
  if (!lock) {
    return { min: candidate.min, max: candidate.max };
  }
  return {
    min: Math.min(lock.min, candidate.min),
    max: Math.max(lock.max, candidate.max),
  };
}

function layoutAxisRange(axisLayout) {
  if (!axisLayout || !Array.isArray(axisLayout.range) || axisLayout.range.length < 2) {
    return null;
  }
  const min = Number(axisLayout.range[0]);
  const max = Number(axisLayout.range[1]);
  if (!Number.isFinite(min) || !Number.isFinite(max) || max <= min) {
    return null;
  }
  return { min, max };
}

function applyPersistentAxisLock(figure, figureId) {
  const layout = figure?.layout || {};
  if (layout.polar) {
    return;
  }

  const chartKey = `${els.icao.value}::${figureId}`;
  const existing = state.axisLocks[chartKey] || {};
  const yCandidate = computeAxisBounds(figure, "y");
  const y2Candidate = computeAxisBounds(figure, "y2");
  const yDefault = layoutAxisRange(layout.yaxis);
  const y2Default = layoutAxisRange(layout.yaxis2);

  const yBaseline = existing.y || yDefault;
  const y2Baseline = existing.y2 || y2Default;
  const yLock = expandAxisLock(yBaseline, yCandidate);
  const y2Lock = expandAxisLock(y2Baseline, y2Candidate);

  const next = {};
  if (yLock) {
    next.y = yLock;
    layout.yaxis = {
      ...(layout.yaxis || {}),
      range: [yLock.min, yLock.max],
      autorange: false,
    };
  }
  if (y2Lock) {
    next.y2 = y2Lock;
    layout.yaxis2 = {
      ...(layout.yaxis2 || {}),
      range: [y2Lock.min, y2Lock.max],
      autorange: false,
    };
  }

  if (next.y || next.y2) {
    state.axisLocks[chartKey] = next;
  }
}

function stackedAxisLockKey(host) {
  const figureId = host?.dataset?.figureId || "";
  return `${els.icao.value}::${figureId}`;
}

function captureStackedAxisLabelLock(host) {
  if (!host || String(host?.layout?.barmode || "").toLowerCase() !== "stack") {
    return;
  }

  const xaxis = host.layout?.xaxis || {};
  const lock = {
    ticklabelposition: xaxis.ticklabelposition || "outside",
  };

  ["tickmode", "tickangle", "ticklabelstandoff", "ticklabeloverflow", "automargin", "type", "side"].forEach((key) => {
    if (xaxis[key] !== undefined) {
      lock[key] = xaxis[key];
    }
  });

  if (Array.isArray(xaxis.range) && xaxis.range.length === 2) {
    lock.range = [xaxis.range[0], xaxis.range[1]];
  }
  if (Array.isArray(xaxis.tickvals) && xaxis.tickvals.length) {
    lock.tickvals = xaxis.tickvals.slice();
  }
  if (Array.isArray(xaxis.ticktext) && xaxis.ticktext.length) {
    lock.ticktext = xaxis.ticktext.slice();
  }
  if (Array.isArray(xaxis.categoryarray) && xaxis.categoryarray.length) {
    lock.categoryarray = xaxis.categoryarray.slice();
  }
  if (typeof xaxis.categoryorder === "string" && xaxis.categoryorder.length) {
    lock.categoryorder = xaxis.categoryorder;
  }

  const marginBottom = Number(host.layout?.margin?.b);
  if (Number.isFinite(marginBottom)) {
    lock.marginBottom = marginBottom;
  }

  state.stackedAxisLabelLocks[stackedAxisLockKey(host)] = lock;
}

function stableStackedAxisRelayout(host) {
  if (!host || String(host?.layout?.barmode || "").toLowerCase() !== "stack") {
    return {};
  }

  const lock = state.stackedAxisLabelLocks[stackedAxisLockKey(host)];
  if (!lock) {
    return {};
  }

  const relayout = {
    "xaxis.ticklabelposition": lock.ticklabelposition || "outside",
  };

  ["tickmode", "tickangle", "ticklabelstandoff", "ticklabeloverflow", "automargin", "type", "side"].forEach((key) => {
    if (lock[key] !== undefined) {
      relayout[`xaxis.${key}`] = lock[key];
    }
  });

  if (Array.isArray(lock.range) && lock.range.length === 2) {
    relayout["xaxis.range"] = [lock.range[0], lock.range[1]];
    relayout["xaxis.autorange"] = false;
  }
  if (Array.isArray(lock.tickvals) && lock.tickvals.length) {
    relayout["xaxis.tickvals"] = lock.tickvals.slice();
  }
  if (Array.isArray(lock.ticktext) && lock.ticktext.length) {
    relayout["xaxis.ticktext"] = lock.ticktext.slice();
  }
  if (typeof lock.categoryorder === "string" && lock.categoryorder.length) {
    relayout["xaxis.categoryorder"] = lock.categoryorder;
  }
  if (Array.isArray(lock.categoryarray) && lock.categoryarray.length) {
    relayout["xaxis.categoryarray"] = lock.categoryarray.slice();
  }
  if (Number.isFinite(lock.marginBottom)) {
    relayout["margin.b"] = lock.marginBottom;
  }

  return relayout;
}

function rescaleAfterLegendToggle(host) {
  const layout = host.layout || {};

  // Keep polar charts on their own scaling behavior.
  if (layout.polar) {
    return Promise.resolve();
  }

  const isStackedBars = String(layout.barmode || "").toLowerCase() === "stack";

  if (isStackedBars) {
    const relayout = {};
    const yBounds = computeAxisBounds(host, "y");
    if (yBounds) {
      relayout["yaxis.range"] = [yBounds.min, yBounds.max];
      relayout["yaxis.autorange"] = false;
    } else {
      relayout["yaxis.autorange"] = true;
      relayout["yaxis.range"] = null;
    }

    if (layout.yaxis2) {
      const y2Bounds = computeAxisBounds(host, "y2");
      if (y2Bounds) {
        relayout["yaxis2.range"] = [y2Bounds.min, y2Bounds.max];
        relayout["yaxis2.autorange"] = false;
      } else {
        relayout["yaxis2.autorange"] = true;
        relayout["yaxis2.range"] = null;
      }
    }

    const stackedRelayout = stableStackedAxisRelayout(host);
    Object.assign(relayout, stackedRelayout);
    return Plotly.relayout(host, relayout);
  }

  const relayout = {
    "yaxis.autorange": true,
    "yaxis.range": null,
  };

  if (layout.yaxis2) {
    relayout["yaxis2.autorange"] = true;
    relayout["yaxis2.range"] = null;
  }

  const stackedRelayout = stableStackedAxisRelayout(host);
  Object.assign(relayout, stackedRelayout);

  return Plotly.relayout(host, relayout);
}

function stackedUirevisionToken(figureId = "") {
  return [
    els.icao.value,
    figureId,
    els.season.value,
    els.enso.value,
    els.iod.value,
    els.sam.value,
    els.mjo.value,
    els.yearStart.value,
    els.yearEnd.value,
    els.monthStart.value,
    els.monthEnd.value,
    els.hourStart.value,
    els.hourEnd.value,
    els.invertMonth.checked ? "1" : "0",
    els.invertHour.checked ? "1" : "0",
    state.fogModes.monthly,
    state.fogModes.hourly,
    state.fogModes.wind,
    state.fogModes.dewpoint,
  ].join("::");
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
        .then(() => rebuildStackErrorBarOverlays(host))
        .then(() => rebuildStrictValueErrorBarOverlays(host))
        .then(() => syncErrorBarOverlayVisibility(host))
        .then(() => (figureId === "cloud_distribution" ? syncFogWindHoverTemplate(host) : Promise.resolve()))
        .then(() => rescaleAfterLegendToggle(host))
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

const hostResizeFrames = new Map();

function scheduleHostResize(host) {
  if (!host) {
    return Promise.resolve();
  }

  const existingFrame = hostResizeFrames.get(host);
  if (existingFrame) {
    cancelAnimationFrame(existingFrame);
  }

  return new Promise((resolve) => {
    const frameId = requestAnimationFrame(() => {
      hostResizeFrames.delete(host);
      // First pass after DOM/layout updates.
      Promise.resolve(Plotly.Plots.resize(host))
        .then(() => new Promise((rafResolve) => requestAnimationFrame(() => {
          // Second pass handles late legend wrapping / font metrics changes.
          Promise.resolve(Plotly.Plots.resize(host)).finally(rafResolve);
        })))
        .then(() => new Promise((timeoutResolve) => {
          // Final short delayed pass avoids intermittent clipping after section toggles.
          setTimeout(() => {
            Promise.resolve(Plotly.Plots.resize(host)).finally(timeoutResolve);
          }, 60);
        }))
        .finally(resolve);
    });

    hostResizeFrames.set(host, frameId);
  });
}

function applyChartShellHeights(section = state.displayedSection) {
  const chartHeight = getChartHeight(section);
  const visibleCardCount = state.latestFigures.length ? Math.min(state.latestFigures.length, els.charts.length) : els.charts.length;
  const expandedRows = visibleCardCount > 2 ? 2 : 1;
  const expandedHeight = state.maximizedChartIndex === null ? chartHeight : (chartHeight * expandedRows) + (8 * Math.max(0, expandedRows - 1));

  for (let i = 0; i < els.charts.length; i += 1) {
    const isMaximized = state.maximizedChartIndex === i;
    const targetHeight = isMaximized ? expandedHeight : chartHeight;
    els.charts[i].style.height = `${targetHeight}px`;
    chartUi[i].card.style.minHeight = `${targetHeight + 10}px`;
  }

  return chartHeight;
}

async function drawCharts(figures, section = state.displayedSection) {
  const isWindSection = section === "wind";
  const isExpandedSection = section === "wind" || section === "precipitation";
  const chartHeight = applyChartShellHeights(section);
  const visibleFigures = figures.slice(0, 4);

  // Keep maximize controls hidden until all chart renders complete.
  chartUi.forEach(({ maximizeButton }) => {
    maximizeButton.classList.add("hidden");
  });

  state.latestFigures = figures;

  const renderPromises = visibleFigures.map((item, idx) => {
    const host = els.charts[idx];
    host.dataset.figureId = item.id || "";
    const { card, legend } = chartUi[idx];
    card.classList.remove("hidden");
    const targetChartHeight = Number.parseFloat(host.style.height) || chartHeight;
    const figure = item.figure;
    const isFrequencyFigure = frequencyFigureIds.has(item.id);
    figure.layout = figure.layout || {};
    figure.layout.legend = figure.layout.legend || {};
    figure.layout.showlegend = false;
    figure.layout.margin = {
      ...(figure.layout.margin || {}),
      r: 32,
    };
    applyStrictValueHoverTemplatesToFigure(figure, item.id || "");
    if (String(figure.layout.barmode || "").toLowerCase() === "stack") {
      figure.layout.uirevision = stackedUirevisionToken(item.id || "");
    }
    applyPersistentAxisLock(figure, item.id);
    if (isFrequencyFigure) {
      figure.layout.height = targetChartHeight;
    }
    if (item.id === "fog_cloud_joint") {
      figure.layout.margin = {
        ...figure.layout.margin,
        b: 18,
      };
      figure.layout.height = targetChartHeight - 12;
    }
    if (isExpandedSection) {
      if ((isWindSection && item.id === "wind_rose") || item.id === "precip_split") {
        figure.layout.height = targetChartHeight - 12;
      } else {
        figure.layout.height = targetChartHeight;
      }
    }
    return Plotly.react(host, figure.data || [], figure.layout || {}, {
      displayModeBar: false,
      responsive: true,
    }).then(() => {
      return applyHostErrorBars(host)
        .then(() => expandAxesForErrorBars(host))
        .then(() => {
          captureStackedAxisLabelLock(host);
        })
        .then(() => {
      renderExternalLegend(host, legend, item.figure, section, item.id);
      const maybeSync = item.id === "cloud_distribution" ? syncFogWindHoverTemplate(host) : Promise.resolve();
      return maybeSync.then(() => scheduleHostResize(host));
      });
    });
  });

  for (let i = visibleFigures.length; i < els.charts.length; i += 1) {
    clearChart(i);
  }

  if (Number.isInteger(state.maximizedChartIndex) && state.maximizedChartIndex >= visibleFigures.length) {
    state.maximizedChartIndex = null;
  }

  await Promise.all(renderPromises);

  applyMaximizedChartState();
}

let pendingFetch = null;
let hasShownInitialLoading = false;
let fetchDebounceTimer = null;
let chartContainerResizeObserversInitialized = false;
const DRIVER_FETCH_DEBOUNCE_MS = 320;

function initializeChartContainerResizeObservers() {
  if (chartContainerResizeObserversInitialized || typeof ResizeObserver === "undefined") {
    return;
  }

  const lastSizes = new WeakMap();
  const observer = new ResizeObserver((entries) => {
    if (!state.latestFigures.length) {
      return;
    }

    entries.forEach((entry) => {
      const card = entry.target;
      const host = card.querySelector(".chart");
      if (!host || card.classList.contains("hidden")) {
        return;
      }

      const width = Math.round(entry.contentRect.width);
      const height = Math.round(entry.contentRect.height);
      const prev = lastSizes.get(card);
      if (prev && prev.width === width && prev.height === height) {
        return;
      }

      lastSizes.set(card, { width, height });
      scheduleHostResize(host);
    });
  });

  chartUi.forEach(({ card }) => {
    observer.observe(card);
  });

  chartContainerResizeObserversInitialized = true;
}

function scheduleFetchCharts(delayMs = 0) {
  if (fetchDebounceTimer) {
    clearTimeout(fetchDebounceTimer);
    fetchDebounceTimer = null;
  }

  if (delayMs <= 0) {
    fetchCharts();
    return;
  }

  fetchDebounceTimer = setTimeout(() => {
    fetchDebounceTimer = null;
    fetchCharts();
  }, delayMs);
}

async function fetchCharts() {
  if (!validateRanges()) {
    return;
  }

  const showOverlay = true;
  const requestedSection = state.requestedSection;
  const previousDisplayedSection = state.displayedSection;
  if (previousDisplayedSection !== requestedSection) {
    state.maximizedChartIndex = null;
  }

  const controller = new AbortController();
  if (pendingFetch) {
    pendingFetch.abort();
  }
  pendingFetch = controller;

  if (showOverlay) {
    showLoading("Loading charts...");
  }

  try {
    const batches = getSectionFigureBatches(requestedSection);
    const allFigures = [];
    let combinedMetrics = {};
    let combinedWarning = "";

    if (showOverlay) {
      setLoadingState(20, `Processing data (0/${batches.length})...`);
    }

    let completedBatches = 0;
    const batchPromises = batches.map((batch, index) => {
      const params = getParams();
      if (batch.length) {
        params.set("figureIds", batch.join(","));
      }
      if (index > 0) {
        params.set("includeMetrics", "false");
      }

      return fetch(apiUrl(`/api/charts?${params.toString()}`), { signal: controller.signal })
        .then((res) => res.json())
        .then((data) => {
          completedBatches += 1;
          if (!controller.signal.aborted && showOverlay) {
            const batchProgress = 20 + Math.floor((completedBatches / batches.length) * 45);
            setLoadingState(batchProgress, `Processing data (${completedBatches}/${batches.length})...`);
          }
          return { index, data };
        });
    });

    const batchResults = await Promise.all(batchPromises);

    if (controller.signal.aborted) {
      return;
    }

    batchResults
      .sort((a, b) => a.index - b.index)
      .forEach(({ data }) => {
        if (data.error) {
          throw new Error(data.error);
        }

        if (data.warning && !combinedWarning) {
          combinedWarning = data.warning;
        }
        if (data.metrics && Object.keys(data.metrics).length > 0 && Object.keys(combinedMetrics).length === 0) {
          combinedMetrics = data.metrics;
        }
        if (Array.isArray(data.figures) && data.figures.length > 0) {
          allFigures.push(...data.figures);
        }
      });

    const data = {
      figures: allFigures,
      metrics: combinedMetrics,
      warning: combinedWarning,
    };
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

    // Ensure section-specific layout/toolbars are applied before Plotly sizing.
    state.displayedSection = requestedSection;
    applySectionLayout(requestedSection);

    await drawCharts(data.figures || [], requestedSection);

    if (controller.signal.aborted) {
      return;
    }

    renderMetrics(data.metrics, requestedSection);
  } catch (err) {
    if (err.name !== "AbortError") {
      if (err?.message) {
        setStatus(err.message);
        return;
      }
      if (window.location.hostname.endsWith("github.io") && !API_BASE) {
        setStatus("Failed to load charts. Set AVCLIMATE_API_BASE in config.js to your deployed backend URL.");
      } else {
        setStatus("Failed to load charts.");
      }
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
  if (els.infoBtn) {
    els.infoBtn.addEventListener("click", () => {
      openInfoModal();
    });
  }

  if (els.infoCloseBtn) {
    els.infoCloseBtn.addEventListener("click", () => {
      closeInfoModal();
    });
  }

  if (els.infoOverlay) {
    els.infoOverlay.addEventListener("click", (event) => {
      if (event.target === els.infoOverlay) {
        closeInfoModal();
      }
    });
  }

  document.addEventListener("keydown", (event) => {
    if (!isInfoModalOpen()) {
      return;
    }
    if (event.key === "Escape") {
      event.preventDefault();
      closeInfoModal();
    }
  });

  renderErrorBarsToggle();

  if (els.errorBarsToggle) {
    els.errorBarsToggle.addEventListener("click", () => {
      state.showErrorBars = !state.showErrorBars;
      renderErrorBarsToggle();
      if (state.latestFigures.length) {
        drawCharts(state.latestFigures, state.displayedSection);
      }
    });
  }

  els.icao.addEventListener("change", fetchCharts);
  els.season.addEventListener("change", () => {
    applySeasonMonthRange();
    fetchCharts();
  });

  [els.enso, els.iod, els.sam, els.mjo].forEach((el) => {
    el.addEventListener("change", () => scheduleFetchCharts(DRIVER_FETCH_DEBOUNCE_MS));
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
      applyChartShellHeights(state.displayedSection);
      if (state.latestFigures.length) {
        els.charts.forEach((host, index) => {
          if (index < state.latestFigures.length && !chartUi[index].card.classList.contains("hidden")) {
            scheduleHostResize(host);
          }
        });
      }
      resizeFrame = null;
    });
  });
}

async function init() {
  try {
    renderCategories();
    await fetchOptions();
    applySeasonMonthRange();
    renderCategories();
    applySectionLayout();
    applyChartShellHeights();
    initializeChartContainerResizeObservers();
    wireControls();
    fetchCharts();
  } catch (error) {
    if (window.location.hostname.endsWith("github.io") && !API_BASE) {
      setStatus("Frontend loaded. Configure AVCLIMATE_API_BASE in config.js to connect to your backend.");
    } else {
      setStatus("Failed to initialize the app.");
    }
  }
}

init();
