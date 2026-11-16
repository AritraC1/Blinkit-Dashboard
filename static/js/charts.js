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
        ticks: { color: "#6B7280", font: { size: 11, family: "Inter, system-ui" } },
        grid: { display: false },
        border: { display: false }
      },
      y: {
        ticks: {
          color: "#6B7280",
          font: { size: 11, family: "Inter, system-ui" },
          callback: (value) =>
            Math.abs(value) >= 1000 ? (value / 1000).toFixed(0) + "K" : value
        },
        grid: { color: "#F3F4F6", drawBorder: false },
        border: { display: false, dash: [4, 4] },
        beginAtZero: true
      }
    }
  };

  function list(data) {
    return Array.isArray(data) ? data : [];
  }

  function barConfig(data, extra = {}) {
    return {
      type: "bar",
      data: {
        labels: data.map((r) => r.label),
        datasets: [
          {
            label: "Sales",
            data: data.map((r) => r.sales),
            backgroundColor: data.map(
              (_, i) => PALETTE[i % PALETTE.length]
            ),
            borderRadius: 4
          }
        ]
      },
      options: { ...BASE_OPTIONS, ...extra, indexAxis: extra.indexAxis }
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
      options: BASE_OPTIONS
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
            borderWidth: 1
          }
        ]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        cutout: "55%",
        plugins: {
          legend: { display: true, position: "right" },
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
        ...BASE_OPTIONS,
        plugins: {
          ...BASE_OPTIONS.plugins,
          legend: { display: true, position: "top" }
        }
      }
    };
  }

  function hbarValueConfig(data) {
    // Generic horizontal bar for {label, value} rows (e.g. feature
    // importance). Sorted ascending so the largest value ends up on top.
    const sorted = [...data].sort((a, b) => a.value - b.value);
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
        ...BASE_OPTIONS,
        indexAxis: "y",
        plugins: {
          ...BASE_OPTIONS.plugins,
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
      case "grouped":
        new Chart(canvas, groupedConfig(list(data)));
        break;
    }
  }

  function refresh(root) {
    (root || document).querySelectorAll("canvas[data-chart]").forEach(buildChart);
  }

  document.addEventListener("DOMContentLoaded", () => refresh(document));
  document.addEventListener("htmx:afterSwap", () => refresh(document));
})();
