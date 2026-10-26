(() => {
  const palette = ['#ff5c00', '#1473e6', '#20a779', '#8b5cf6', '#e7a008', '#e5484d', '#20a4b8', '#64748b'];
  const statusPalette = ['#e5484d', '#20a779', '#a3aab5', '#e7a008', '#8b5cf6'];

  function chartConfig(type, labels, values, title, colors = palette, horizontal = false) {
    return {
      type,
      data: {
        labels,
        datasets: [{
          label: title,
          data: values,
          backgroundColor: type === 'doughnut' ? colors : colors[0],
          borderColor: type === 'doughnut' ? '#fff' : colors[0],
          borderWidth: type === 'doughnut' ? 3 : 0,
          borderRadius: type === 'bar' ? 7 : 0,
          maxBarThickness: 34,
          hoverBackgroundColor: type === 'doughnut' ? colors : '#d84d00',
        }],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        indexAxis: horizontal ? 'y' : 'x',
        plugins: {
          legend: { display: type === 'doughnut', position: 'bottom', labels: { usePointStyle: true, padding: 18 } },
          tooltip: { enabled: true, displayColors: type !== 'doughnut' },
        },
        scales: type === 'doughnut' ? {} : horizontal ? {
          x: { beginAtZero: true, grid: { color: '#eff0f2' }, ticks: { precision: 0, color: '#6e6e73' } },
          y: { grid: { display: false }, ticks: { color: '#6e6e73' } },
        } : {
          x: { grid: { display: false }, ticks: { color: '#6e6e73', maxRotation: 0, autoSkip: true } },
          y: { beginAtZero: true, grid: { color: '#eff0f2' }, ticks: { precision: 0, color: '#6e6e73' } },
        },
      },
    };
  }

  function showEmptyState(canvas, message) {
    const state = document.createElement('p');
    state.className = 'dashboard-chart-empty';
    state.textContent = message;
    canvas.replaceWith(state);
  }

  function renderChart(id, type, labels, values, title, colors, horizontal = false) {
    const canvas = document.getElementById(id);
    if (!canvas) return;
    if (!labels.length || !values.some((value) => Number(value) > 0)) {
      showEmptyState(canvas, 'No data available yet');
      return;
    }
    new Chart(canvas, chartConfig(type, labels, values, title, colors, horizontal));
  }

  function initializeDashboardCharts() {
    const dataElement = document.getElementById('dashboardChartData');
    if (!dataElement) return;
    if (typeof Chart === 'undefined') {
      console.error('Dashboard charts could not load because Chart.js is unavailable.');
      document.querySelectorAll('.dashboard-chart-canvas canvas').forEach((canvas) => {
        showEmptyState(canvas, 'Charts are temporarily unavailable. Please refresh the page.');
      });
      return;
    }

    let data;
    try {
      data = JSON.parse(dataElement.textContent);
    } catch (error) {
      console.error('Unable to read dashboard chart data.', error);
      document.querySelectorAll('.dashboard-chart-canvas canvas').forEach((canvas) => {
        showEmptyState(canvas, 'Chart data could not be loaded. Please refresh the page.');
      });
      return;
    }

    let primaryLabels = data.primary_labels || [];
    let primaryValues = data.primary_values || [];
    let primaryThresholds = data.primary_thresholds || [];
    const primaryRows = primaryLabels.map((label, index) => ({
      label,
      value: Number(primaryValues[index]) || 0,
      threshold: primaryThresholds[index] === null ? null : Number(primaryThresholds[index]),
      index,
    }));
    if (data.category === 'stock' || data.category === 'samples') {
      primaryRows.sort((a, b) => b.value - a.value);
      primaryRows.splice(12);
      primaryLabels = primaryRows.map((row) => row.label);
      primaryValues = primaryRows.map((row) => row.value);
      primaryThresholds = primaryRows.map((row) => row.threshold);
    }

    const primaryCanvas = document.getElementById('dashboardPrimaryChart');
    if (primaryCanvas && primaryLabels.length && primaryValues.some((value) => Number(value) > 0)) {
      const datasets = [{
        type: 'bar',
        label: data.category === 'equipment' ? 'Equipment' : (data.category === 'samples' ? 'Volume' : 'Packs'),
        data: primaryValues,
        backgroundColor: primaryValues.map((value, index) => {
          const threshold = primaryThresholds[index];
          return threshold !== null && threshold !== undefined && value < threshold ? '#e5484d' : '#ff7a33';
        }),
        borderRadius: 7,
        maxBarThickness: 34,
      }];
      if (primaryThresholds.some((value) => value !== null && value !== undefined)) {
        datasets.push({
          type: 'line',
          label: 'Low-stock threshold',
          data: primaryThresholds,
          borderColor: '#e5484d',
          backgroundColor: '#e5484d',
          pointRadius: 3,
          pointHoverRadius: 5,
          borderDash: [5, 4],
          spanGaps: true,
        });
      }
      new Chart(primaryCanvas, {
        type: 'bar',
        data: { labels: primaryLabels, datasets },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          indexAxis: primaryLabels.length > 7 || data.category === 'equipment' ? 'y' : 'x',
          plugins: {
            legend: { display: datasets.length > 1, position: 'bottom', labels: { usePointStyle: true, padding: 18 } },
            tooltip: { enabled: true },
          },
          scales: (primaryLabels.length > 7 || data.category === 'equipment') ? {
            x: { beginAtZero: true, grid: { color: '#eff0f2' }, ticks: { precision: 0, color: '#6e6e73' } },
            y: { grid: { display: false }, ticks: { color: '#6e6e73' } },
          } : {
            x: { grid: { display: false }, ticks: { color: '#6e6e73', maxRotation: 0, autoSkip: true } },
            y: { beginAtZero: true, grid: { color: '#eff0f2' }, ticks: { precision: 0, color: '#6e6e73' } },
          },
        },
      });
    } else if (primaryCanvas) {
      showEmptyState(primaryCanvas, 'No data available yet');
    }

    renderChart(
      'dashboardDistributionChart',
      'doughnut',
      data.distribution_labels || [],
      data.distribution_values || [],
      data.distribution_title,
      statusPalette,
    );
    renderChart(
      'dashboardSecondaryChart',
      'bar',
      data.secondary_labels || [],
      data.secondary_values || [],
      data.secondary_title,
      palette,
      true,
    );
    renderChart(
      'dashboardTertiaryChart',
      'bar',
      data.tertiary_labels || [],
      data.tertiary_values || [],
      data.tertiary_title,
      palette,
      true,
    );
  }

  document.addEventListener('DOMContentLoaded', initializeDashboardCharts);
})();
