// Build every chart from its <canvas data-chart> + <script id=... type=application/json> pair.
// Runs on page load AND on htmx:afterSwap so charts redraw after every HTMX swap.
// Any existing Chart on a canvas is destroyed first, or Chart.js throws
// "Canvas is already in use".
(function () {
  "use strict";

  /* Blinkit brand palette: green-yellow alternating with depth */
  const PALETTE = [
    "#0C831F", "#F9C023", "#16A34A", "#FBBF24",
    "#15803D", "#F59E0B", "#166534", "#D97706",
    "#14532D", "#B45309", "#052e16", "#92400e",
    "#1aab36", "#e6ae1a", "#27AE60"
  ];

  const BASE_OPTIONS = {
    responsive: true,
    maintainAspectRatio: false,
    animation: { duration: 500, easing: "easeOutQuart" },
    plugins: {
      legend: { display: false },
      tooltip: {
        backgroundColor: "#111827",
        titleColor: "#F9FAFB",
        bodyColor: "#D1D5DB",
        padding: 10,
        cornerRadius: 8,
        callbacks: {
          label: (ctx) => {
            const value = ctx.parsed.y !== undefined ? ctx.parsed.y : ctx.parsed;
            const label = ctx.dataset.label ? ctx.dataset.label + ": " : "";
            return label + Number(value).toLocaleString(undefined, {
              maximumFractionDigits: 2
            });
          }
        }
      }
    },
    scales: {
      x: {
        ticks: categoryAxisTicks(),
        grid: { display: false },
        border: { display: false }
      },
      y: {
        ticks: valueAxisTicks(),
        grid: { color: "#F3F4F6", drawBorder: false },
        border: { display: false, dash: [4, 4] },
        beginAtZero: true
      }
    }
  };

  function list(data) {
    return Array.isArray(data) ? data : [];
  }

  // Deep clone for plain config objects (functions pass through by
  // reference). Chart.js mutates the options object it is given, so every
  // chart must get its own copy — sharing them corrupts scale resolution
  // across charts (this is why the horizontal bars used to break whenever
  // the line chart had rendered).
  function cloneDeep(value) {
    if (Array.isArray(value)) return value.map(cloneDeep);
    if (value && typeof value === "object") {
      const out = {};
      for (const key of Object.keys(value)) out[key] = cloneDeep(value[key]);
      return out;
    }
    return value;
  }

  // Tick formatting for a VALUE axis: compact K notation.
  function valueAxisTicks() {
    return {
      color: "#6B7280",
      font: { size: 11, family: "Inter, system-ui" },
      callback: (value) =>
        Math.abs(value) >= 1000 ? (value / 1000).toFixed(0) + "K" : value
    };
  }

  // Tick styling for a CATEGORY axis. No callback: overriding it makes
  // Chart.js print raw indices instead of the labels.
  function categoryAxisTicks() {
    return {
      color: "#6B7280",
      font: { size: 11, family: "Inter, system-ui" }
    };
  }

  // True when a hex color is light enough that dark text reads better on it
  // (used to pick label color on top of chart slices).
  function isLightColor(hex) {
    const value = hex.replace("#", "");
    const r = parseInt(value.substr(0, 2), 16);
    const g = parseInt(value.substr(2, 2), 16);
    const b = parseInt(value.substr(4, 2), 16);
    return 0.299 * r + 0.587 * g + 0.114 * b > 160;
  }

  // Draws the percentage of the total on each pie slice. Tiny slices (<4%)
  // are skipped — their share still shows in the tooltip.
  const percentLabels = {
    id: "percentLabels",
    afterDatasetsDraw(chart) {
      const dataset = chart.data.datasets[0];
      const total = dataset.data.reduce((sum, v) => sum + v, 0);
      if (!total) return;
      const meta = chart.getDatasetMeta(0);
      const ctx = chart.ctx;
      ctx.save();
      ctx.font = "600 11px Inter, system-ui";
      ctx.textAlign = "center";
      ctx.textBaseline = "middle";
      meta.data.forEach((arc, i) => {
        const share = (dataset.data[i] / total) * 100;
        if (share < 4) return;
        const position = arc.tooltipPosition();
        const color = dataset.backgroundColor[i % dataset.backgroundColor.length] || "";
        ctx.fillStyle = isLightColor(color) ? "#1F2937" : "#FFFFFF";
        ctx.fillText(share.toFixed(1) + "%", position.x, position.y);
      });
      ctx.restore();
    }
  };

  const RADIAL_LEGEND = {
    display: true,
    position: "right",
    labels: {
      usePointStyle: true,
      boxWidth: 8,
      padding: 12,
      color: "#374151",
      font: { size: 11, family: "Inter, system-ui" }
    }
  };

  function barConfig(data, extra = {}, valueField = "sales", datasetLabel = "Sales") {
    // For horizontal bars the value axis is x and the category axis is y,
    // so the K-format callback moves to x and the y ticks stay label-only.
    const horizontal = extra.indexAxis === "y";
    const options = cloneDeep(BASE_OPTIONS);
    options.indexAxis = extra.indexAxis;
    if (horizontal) {
      options.scales.x.ticks = valueAxisTicks();
      options.scales.y.ticks = categoryAxisTicks();
    }
    return {
      type: "bar",
      data: {
        labels: data.map((r) => r.label),
        datasets: [
          {
            label: datasetLabel,
            data: data.map((r) => r[valueField]),
            backgroundColor: data.map(
              (_, i) => PALETTE[i % PALETTE.length]
            ),
            borderRadius: 4
          }
        ]
      },
      options
    };
  }

  function lineConfig(data) {
    return {
      type: "line",
      data: {
        labels: data.map((r) => r.label),
        datasets: [
          {
            label: "Sales",
            data: data.map((r) => r.sales),
            borderColor: PALETTE[0],
            backgroundColor: "rgba(12,131,31,0.10)",
            tension: 0.35,
            fill: true,
            pointBackgroundColor: PALETTE[0],
            pointBorderColor: "#fff",
            pointBorderWidth: 2,
            pointRadius: 4,
            pointHoverRadius: 7
          }
        ]
      },
      options: cloneDeep(BASE_OPTIONS)
    };
  }

  function doughnutConfig(data) {
    return {
      type: "doughnut",
      data: {
        labels: data.map((r) => r.label),
        datasets: [
          {
            label: "Sales",
            data: data.map((r) => r.sales),
            backgroundColor: data.map(
              (_, i) => PALETTE[i % PALETTE.length]
            ),
            borderColor: "#FFFFFF",
            borderWidth: 2,
            hoverOffset: 8
          }
        ]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        cutout: "55%",
        plugins: {
          legend: RADIAL_LEGEND,
          tooltip: {
            callbacks: {
              label: (ctx) =>
                ctx.label + ": " + Number(ctx.parsed).toLocaleString(undefined, {
                  maximumFractionDigits: 2
                })
            }
          }
        }
      }
    };
  }

  function pieConfig(data) {
    return {
      type: "pie",
      data: {
        labels: data.map((r) => r.label),
        datasets: [
          {
            label: "Sales",
            data: data.map((r) => r.sales),
            backgroundColor: data.map((_, i) => PALETTE[i % PALETTE.length]),
            borderColor: "#FFFFFF",
            borderWidth: 2,
            hoverOffset: 8
          }
        ]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: RADIAL_LEGEND,
          tooltip: {
            backgroundColor: "#111827",
            titleColor: "#F9FAFB",
            bodyColor: "#D1D5DB",
            padding: 10,
            cornerRadius: 8,
            callbacks: {
              label: (ctx) => {
                const total = ctx.dataset.data.reduce((s, v) => s + v, 0);
                const share = ((ctx.parsed / total) * 100).toFixed(1);
                return " " + ctx.label + ": " + Number(ctx.parsed).toLocaleString(undefined, {
                  maximumFractionDigits: 2
                }) + " (" + share + "%)";
              }
            }
          }
        }
      },
      plugins: [percentLabels]
    };
  }

  function polarAreaConfig(data) {
    return {
      type: "polarArea",
      data: {
        labels: data.map((r) => r.label),
        datasets: [
          {
            label: "Sales",
            data: data.map((r) => r.sales),
            backgroundColor: data.map((_, i) => PALETTE[i % PALETTE.length] + "B3"),
            borderColor: data.map((_, i) => PALETTE[i % PALETTE.length]),
            borderWidth: 1
          }
        ]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: RADIAL_LEGEND,
          tooltip: {
            backgroundColor: "#111827",
            titleColor: "#F9FAFB",
            bodyColor: "#D1D5DB",
            padding: 10,
            cornerRadius: 8,
            callbacks: {
              label: (ctx) =>
                " " + ctx.label + ": " + Number(ctx.parsed.r !== undefined ? ctx.parsed.r : ctx.parsed).toLocaleString(undefined, {
                  maximumFractionDigits: 2
                })
            }
          }
        },
        scales: {
          r: {
            ticks: {
              color: "#6B7280",
              backdropColor: "transparent",
              font: { size: 10, family: "Inter, system-ui" },
              callback: (value) =>
                Math.abs(value) >= 1000 ? (value / 1000).toFixed(0) + "K" : value
            },
            grid: { color: "#E5E7EB" },
            angleLines: { color: "#E5E7EB" }
          }
        }
      }
    };
  }

  // Stacked horizontal bar for {tier, size, sales} rows: one bar per tier,
  // segments per outlet size — reads cleanly at 3×3 without the crowding
  // the doughnut version had.
  function stackedHConfig(data) {
    const tiers = [...new Set(data.map((d) => d.tier))];
    const sizes = [...new Set(data.map((d) => d.size))];
    const lookup = new Map(data.map((d) => [d.tier + "|" + d.size, d.sales]));
    const options = cloneDeep(BASE_OPTIONS);
    options.indexAxis = "y";
    options.scales.x.ticks = valueAxisTicks();
    options.scales.y.ticks = categoryAxisTicks();
    options.scales.x.stacked = true;
    options.scales.y.stacked = true;
    options.plugins = {
      ...options.plugins,
      legend: {
        display: true,
        position: "top",
        labels: {
          usePointStyle: true,
          boxWidth: 8,
          padding: 12,
          color: "#374151",
          font: { size: 11, family: "Inter, system-ui" }
        }
      }
    };
    return {
      type: "bar",
      data: {
        labels: tiers,
        datasets: sizes.map((size, i) => ({
          label: size,
          data: tiers.map((tier) => lookup.get(tier + "|" + size) ?? 0),
          backgroundColor: ["#0C831F", "#F9C023", "#F59E0B"][i % 3],
          maxBarThickness: 48,
          borderRadius: 4
        }))
      },
      options
    };
  }

  // Radar for {tier, size, sales} rows: labels = tiers, one filled polygon
  // per outlet size — how each size performs across location tiers.
  function radarConfig(data) {
    const tiers = [...new Set(data.map((d) => d.tier))];
    const sizes = [...new Set(data.map((d) => d.size))];
    const lookup = new Map(data.map((d) => [d.tier + "|" + d.size, d.sales]));
    return {
      type: "radar",
      data: {
        labels: tiers,
        datasets: sizes.map((size, i) => {
          const color = PALETTE[(i * 2 + 1) % PALETTE.length];
          return {
            label: size,
            data: tiers.map((tier) => lookup.get(tier + "|" + size) ?? 0),
            borderColor: color,
            backgroundColor: color + "33",
            borderWidth: 2,
            pointBackgroundColor: color,
            pointBorderColor: "#fff",
            pointBorderWidth: 1,
            pointRadius: 3,
            pointHoverRadius: 6
          };
        })
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: {
            display: true,
            position: "top",
            labels: {
              usePointStyle: true,
              boxWidth: 8,
              padding: 12,
              color: "#374151",
              font: { size: 11, family: "Inter, system-ui" }
            }
          },
          tooltip: {
            backgroundColor: "#111827",
            titleColor: "#F9FAFB",
            bodyColor: "#D1D5DB",
            padding: 10,
            cornerRadius: 8
          }
        },
        scales: {
          r: {
            beginAtZero: true,
            ticks: {
              color: "#6B7280",
              backdropColor: "transparent",
              font: { size: 10, family: "Inter, system-ui" },
              callback: (value) =>
                Math.abs(value) >= 1000 ? (value / 1000).toFixed(0) + "K" : value
            },
            grid: { color: "#E5E7EB" },
            angleLines: { color: "#E5E7EB" },
            pointLabels: {
              color: "#374151",
              font: { size: 12, family: "Inter, system-ui" }
            }
          }
        }
      }
    };
  }

  // Proper histogram: bins touch each other (no gaps, no rounding), one
  // green gradient over all bars.
  function histogramConfig(data) {
    const gradient = document
      .createElement("canvas")
      .getContext("2d")
      .createLinearGradient(0, 0, 0, 280);
    gradient.addColorStop(0, "#16A34A");
    gradient.addColorStop(1, "#86EFAC");
    return {
      type: "bar",
      data: {
        labels: data.map((r) => r.label),
        datasets: [
          {
            label: "Records",
            data: data.map((r) => r.count),
            backgroundColor: gradient,
            borderColor: "#0C831F",
            borderWidth: 1,
            categoryPercentage: 1.0,
            barPercentage: 1.0,
            borderRadius: 0
          }
        ]
      },
      options: { ...BASE_OPTIONS }
    };
  }

  // Pivot [{tier, size, sales}] into grouped bars: labels = tiers,
  // one dataset per outlet size.
  function groupedConfig(data) {
    const tiers = [...new Set(data.map((d) => d.tier))];
    const sizes = [...new Set(data.map((d) => d.size))];
    const lookup = new Map(
      data.map((d) => [d.tier + "|" + d.size, d.sales])
    );
    return {
      type: "bar",
      data: {
        labels: tiers,
        datasets: sizes.map((size, i) => ({
          label: size,
          data: tiers.map((tier) => lookup.get(tier + "|" + size) ?? 0),
          backgroundColor: PALETTE[i % PALETTE.length],
          borderRadius: 4
        }))
      },
      options: {
        ...cloneDeep(BASE_OPTIONS),
        plugins: {
          ...cloneDeep(BASE_OPTIONS).plugins,
          legend: { display: true, position: "top" }
        }
      }
    };
  }

  function hbarValueConfig(data) {
    // Generic horizontal bar for {label, value} rows (e.g. feature
    // importance). Sorted ascending so the largest value ends up on top.
    const sorted = [...data].sort((a, b) => a.value - b.value);
    // Horizontal: x is the value axis (plain ticks — importances are small
    // decimals), y is the category axis (labels, no callback).
    const options = cloneDeep(BASE_OPTIONS);
    options.indexAxis = "y";
    options.scales.x.ticks = categoryAxisTicks();
    options.scales.y.ticks = categoryAxisTicks();
    return {
      type: "bar",
      data: {
        labels: sorted.map((r) => r.label),
        datasets: [
          {
            label: "Value",
            data: sorted.map((r) => r.value),
            backgroundColor: sorted.map((_, i) => PALETTE[i % PALETTE.length]),
            borderRadius: 4
          }
        ]
      },
      options: {
        ...options,
        plugins: {
          ...options.plugins,
          tooltip: {
            callbacks: {
              label: (ctx) => Number(ctx.parsed.x).toLocaleString(undefined, {
                maximumFractionDigits: 4
              })
            }
          }
        }
      }
    };
  }

  function scatterConfig(points) {
    // Scatter of {actual, predicted} plus a dashed diagonal reference line.
    const values = points
      .flatMap((p) => [p.actual, p.predicted])
      .filter((v) => Number.isFinite(v));
    if (!values.length) {
      return null;
    }
    const lo = Math.min(...values);
    const hi = Math.max(...values);
    const pad = (hi - lo) * 0.05 || 1;
    const start = Math.max(0, lo - pad);
    const end = hi + pad;
    return {
      type: "scatter",
      data: {
        datasets: [
          {
            label: "Predictions",
            data: points.map((p) => ({ x: p.actual, y: p.predicted })),
            backgroundColor: PALETTE[1],
            pointRadius: 5
          },
          {
            label: "Perfect prediction",
            type: "line",
            data: [
              { x: start, y: start },
              { x: end, y: end }
            ],
            borderColor: "#9aa2b1",
            borderDash: [6, 4],
            borderWidth: 1,
            pointRadius: 0,
            fill: false
          }
        ]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: { display: true, position: "top" },
          tooltip: {
            callbacks: {
              label: (ctx) =>
                "actual " + Number(ctx.parsed.x).toLocaleString(undefined, {
                  maximumFractionDigits: 1
                }) + " / predicted " + Number(ctx.parsed.y).toLocaleString(undefined, {
                  maximumFractionDigits: 1
                })
            }
          }
        },
        scales: {
          x: {
            title: { display: true, text: "Actual sales" },
            ticks: { color: "#5a6270" },
            grid: { color: "#eef0f4" }
          },
          y: {
            title: { display: true, text: "Predicted sales" },
            ticks: { color: "#5a6270" },
            grid: { color: "#eef0f4" }
          }
        }
      }
    };
  }

  function buildChart(canvas) {
    if (!window.Chart || !canvas) return;
    const source = document.getElementById(canvas.dataset.source);
    if (!source) return;
    let data;
    try {
      data = JSON.parse(source.textContent);
    } catch {
      return;
    }

    const existing = Chart.getChart(canvas);
    if (existing) existing.destroy();

    switch (canvas.dataset.chart) {
      case "bar":
        new Chart(canvas, barConfig(list(data)));
        break;
      case "bar-count":
        new Chart(canvas, barConfig(list(data), {}, "count", "Records"));
        break;
      case "bar-horizontal":
        new Chart(canvas, barConfig(list(data), { indexAxis: "y" }));
        break;
      case "bar-horizontal-value":
        new Chart(canvas, hbarValueConfig(list(data)));
        break;
      case "scatter":
        const config = scatterConfig(list(data));
        if (config) new Chart(canvas, config);
        break;
      case "line":
        new Chart(canvas, lineConfig(list(data)));
        break;
      case "doughnut":
        new Chart(canvas, doughnutConfig(list(data)));
        break;
      case "pie":
        new Chart(canvas, pieConfig(list(data)));
        break;
      case "polar-area":
        new Chart(canvas, polarAreaConfig(list(data)));
        break;
      case "radar":
        new Chart(canvas, radarConfig(list(data)));
        break;
      case "bar-stacked-h":
        new Chart(canvas, stackedHConfig(list(data)));
        break;
      case "histogram":
        new Chart(canvas, histogramConfig(list(data)));
        break;
      case "grouped":
        new Chart(canvas, groupedConfig(list(data)));
        break;
    }
  }

  function refresh(root) {
    (root || document).querySelectorAll("canvas[data-chart]").forEach(buildChart);
  }

  // Re-fit every chart when the main content area changes width (sidebar
  // collapse/expand, window resize). Chart.js already observes each chart's
  // own container, but this is a safety net for interrupted sidebar
  // transitions (which fire `transitioncancel`, not `transitionend`).
  const mainWrapper = document.getElementById("main-wrapper");
  if (mainWrapper && typeof ResizeObserver === "function") {
    let lastWidth = mainWrapper.clientWidth;
    let frame = null;
    new ResizeObserver(() => {
      if (mainWrapper.clientWidth === lastWidth) return;
      lastWidth = mainWrapper.clientWidth;
      if (frame) return;
      frame = requestAnimationFrame(() => {
        frame = null;
        document.querySelectorAll("canvas[data-chart]").forEach((canvas) => {
          const chart = window.Chart.getChart(canvas);
          if (chart) chart.resize();
        });
      });
    }).observe(mainWrapper);
  }

  document.addEventListener("DOMContentLoaded", () => refresh(document));
  document.addEventListener("htmx:afterSwap", () => refresh(document));
})();
