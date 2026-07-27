(() => {
  const root = document.querySelector("[data-analytics-dashboard]");
  if (!root || typeof Chart === "undefined") return;

  let payload = {};
  try {
    const node = document.getElementById("analytics-chart-data");
    payload = JSON.parse(node ? node.textContent : "{}");
  } catch (_err) {
    return;
  }

  const palette = {
    teal: "#0f766e",
    tealSoft: "rgba(15, 118, 110, 0.18)",
    ink: "#1c1917",
    amber: "#d97706",
    rose: "#e11d48",
    sky: "#0284c7",
    stone: "#78716c",
    multi: ["#0f766e", "#0284c7", "#d97706", "#e11d48", "#7c3aed", "#059669", "#b45309", "#334155"],
  };

  const baseOptions = {
    responsive: true,
    maintainAspectRatio: false,
    plugins: {
      legend: { display: false },
      tooltip: {
        backgroundColor: "#1c1917",
        titleFont: { family: "system-ui" },
        bodyFont: { family: "system-ui" },
      },
    },
    scales: {
      x: {
        grid: { display: false },
        ticks: { maxRotation: 0, autoSkip: true, maxTicksLimit: 8, color: palette.stone },
      },
      y: {
        beginAtZero: true,
        ticks: { precision: 0, color: palette.stone },
        grid: { color: "rgba(120, 113, 108, 0.12)" },
      },
    },
  };

  const makeLine = (canvasId, series, color) => {
    const el = document.getElementById(canvasId);
    if (!el || !series) return;
    new Chart(el, {
      type: "line",
      data: {
        labels: series.labels || [],
        datasets: [
          {
            data: series.values || [],
            borderColor: color,
            backgroundColor: palette.tealSoft,
            fill: true,
            tension: 0.3,
            pointRadius: 0,
            pointHoverRadius: 4,
            borderWidth: 2,
          },
        ],
      },
      options: baseOptions,
    });
  };

  const makeBar = (canvasId, series, horizontal = false) => {
    const el = document.getElementById(canvasId);
    if (!el || !series) return;
    new Chart(el, {
      type: "bar",
      data: {
        labels: series.labels || [],
        datasets: [
          {
            data: series.values || [],
            backgroundColor: palette.multi,
            borderRadius: 6,
            maxBarThickness: horizontal ? 28 : 36,
          },
        ],
      },
      options: {
        ...baseOptions,
        indexAxis: horizontal ? "y" : "x",
        plugins: { ...baseOptions.plugins },
      },
    });
  };

  const makeDoughnut = (canvasId, series) => {
    const el = document.getElementById(canvasId);
    if (!el || !series) return;
    new Chart(el, {
      type: "doughnut",
      data: {
        labels: series.labels || [],
        datasets: [
          {
            data: series.values || [],
            backgroundColor: [palette.teal, palette.sky, palette.amber, palette.rose],
            borderWidth: 0,
          },
        ],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: { position: "bottom", labels: { boxWidth: 12, color: palette.ink } },
        },
      },
    });
  };

  makeLine("chart-views", payload.views, palette.teal);
  makeLine("chart-subscribers", payload.subscribers, palette.sky);
  makeDoughnut("chart-newsletter", payload.newsletter);
  makeBar("chart-countries", payload.countries);
  makeBar("chart-most-read", payload.mostRead, true);
  makeBar("chart-reading", payload.reading);
})();
