// Build every chart from its <canvas data-chart> + <script id=... type=application/json> pair.
// Runs on page load AND on htmx:afterSwap so charts redraw after every HTMX swap.
// Any existing Chart on a canvas is destroyed first, or Chart.js throws
// "Canvas is already in use".
(function () {
  "use strict";

  const PALETTE = [
    "#0c831f", "#1f77b4", "#ff7f0e", "#9467bd", "#8c564b",
    "#e377c2", "#7f7f7f", "#bcbd22", "#17becf", "#aec7e8",
    "#ffbb78", "#98df8a", "#ff9896", "#c5b0d5", "#c49c94"
  ];

  const BASE_OPTIONS = {
    responsive: true,
    maintainAspectRatio: false,
    plugins: {
      legend: { display: false },
      tooltip: {
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
      x: { ticks: { color: "#5a6270" }, grid: { display: false } },
      y: {
        ticks: {
          color: "#5a6270",
          callback: (value) =>
            Math.abs(value) >= 1000 ? value / 1000 + "K" : value
        },
        grid: { color: "#eef0f4" },
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
            backgroundColor: PALETTE[0],
            tension: 0.25,
            fill: false
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
