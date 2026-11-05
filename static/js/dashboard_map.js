(() => {
  'use strict';

  const SVG_NS = 'http://www.w3.org/2000/svg';
  const WIDTH = 800;
  const HEIGHT = 500;
  const MAX_ZOOM = 16;
  const VIEWS = {
    ghana: { bounds: [-4.7, 3.7, 2.8, 12.4], label: 'GHANA' },
    'west-africa': { bounds: [-26, -2, 18, 29], label: 'WEST AFRICA' },
    africa: { bounds: [-20, -37, 54, 39], label: 'AFRICA' },
    world: { bounds: [-180, -58, 180, 84], label: 'WORLD' },
  };
  const PALETTE = [
    'var(--map-scale-low, #ffd1b8)',
    'var(--map-scale-medium, #ff9d66)',
    'var(--map-scale-high, #ff5c00)',
  ];
  const SHARE_THRESHOLDS = [10, 40];
  const WEST_AFRICA = new Set(['BEN', 'BFA', 'CPV', 'CIV', 'GMB', 'GHA', 'GIN', 'GNB', 'LBR', 'MLI', 'MRT', 'NER', 'NGA', 'SEN', 'SLE', 'TGO']);
  const LABEL_NAMES = { CIV: 'Côte d’Ivoire', COD: 'DR Congo', COG: 'Congo', CAF: 'Central African Rep.', CPV: 'Cabo Verde' };
  const SEARCH_ALIASES = { GBR: ['UK', 'Great Britain', 'England'], COD: ['DRC', 'DR Congo', 'Democratic Republic of Congo', 'Congo Kinshasa'], COG: ['Congo Brazzaville'], USA: ['USA', 'United States of America'], CIV: ['Ivory Coast', 'Cote dIvoire'], CPV: ['Cape Verde'], ARE: ['UAE'], KOR: ['South Korea'], PRK: ['North Korea'] };

  function svgElement(tag, attributes, content) {
    const element = document.createElementNS(SVG_NS, tag);
    Object.entries(attributes || {}).forEach(([key, value]) => {
      element.setAttribute(key, String(value));
      if (key === 'font-size') element.style.fontSize = `${value}px`;
    });
    if (content !== undefined) element.textContent = content;
    return element;
  }

  function projection(bounds, width = WIDTH, height = HEIGHT, padding) {
    const [west, south, east, north] = bounds;
    const longitudeScale = Math.cos(((south + north) / 2) * Math.PI / 180);
    const scale = Math.min((width - 2 * (padding ?? 43)) / ((east - west) * longitudeScale), (height - 2 * (padding ?? 41)) / (north - south));
    const middleLongitude = (west + east) / 2;
    const middleLatitude = (south + north) / 2;
    const project = ([longitude, latitude]) => [width / 2 + (longitude - middleLongitude) * scale * longitudeScale, height / 2 - (latitude - middleLatitude) * scale];
    project.invert = ([x, y]) => [middleLongitude + (x - width / 2) / (scale * longitudeScale), middleLatitude - (y - height / 2) / scale];
    return project;
  }

  function geometryPath(geometry, project) {
    const polygons = geometry.type === 'Polygon' ? [geometry.coordinates] : geometry.coordinates;
    return polygons.map((polygon) => polygon.map((ring) => ring.map((coordinate, index) => {
      const [x, y] = project(coordinate);
      return `${index ? 'L' : 'M'}${x.toFixed(2)},${y.toFixed(2)}`;
    }).join('') + 'Z').join('')).join('');
  }

  function metricValue(count, mapped, metric = 'count') {
    return metric === 'percentage' ? (mapped > 0 ? Number(count) / mapped * 100 : 0) : Number(count) || 0;
  }

  function colorIndex(value, maximum, metric = 'count') {
    if (!(value > 0)) return -1;
    if (metric === 'percentage') {
      const index = SHARE_THRESHOLDS.findIndex((limit) => value < limit);
      return index < 0 ? 2 : index;
    }
    const fraction = value / Math.max(1, maximum);
    return fraction > 0.66 ? 2 : fraction > 0.33 ? 1 : 0;
  }

  function countryColor(value, maximum, _isWestAfrica, metric = 'count') {
    const index = colorIndex(value, maximum, metric);
    return index < 0 ? (_isWestAfrica ? 'var(--map-empty-west, #34353b)' : 'var(--map-empty-other, #282a30)') : PALETTE[index];
  }

  function legendBins(maximum, metric = 'count') {
    if (metric === 'percentage') return ['<10%', '10–<40%', '≥40%'].map((label, index) => ({ label, color: PALETTE[index], hidden: false }));
    const limits = [0, Math.floor(maximum * 0.33), Math.floor(maximum * 0.66), maximum];
    return PALETTE.map((color, index) => {
      const lower = limits[index] + 1;
      const upper = limits[index + 1];
      return { color, label: lower === upper ? lower.toLocaleString() : `${lower.toLocaleString()}–${upper.toLocaleString()}`, hidden: maximum < 1 || lower > upper };
    });
  }

  function normalizeSearch(value) {
    return String(value || '').normalize('NFKD').replace(/[\u0300-\u036f]/g, '').toLowerCase().replace(/[^a-z0-9]+/g, ' ').trim();
  }

  function matchCountries(records, query, limit = 8) {
    const needle = normalizeSearch(query);
    return records.map((record) => {
      const names = [record.name, record.code, record.iso_a3, record.iso_a2, ...(record.aliases || []), ...(SEARCH_ALIASES[record.code || record.iso_a3] || [])].map(normalizeSearch).filter(Boolean);
      const score = !needle ? 3 : names.some((name) => name === needle) ? 0 : names.some((name) => name.startsWith(needle)) ? 1 : names.some((name) => name.includes(needle)) ? 2 : 9;
      return { record, score };
    }).filter(({ score }) => score < 9).sort((a, b) => a.score - b.score || (Number(b.record.count) || 0) - (Number(a.record.count) || 0) || a.record.name.localeCompare(b.record.name)).slice(0, limit).map(({ record }) => record);
  }

  function visiblePosition(position, width = WIDTH, height = HEIGHT) {
    return Number.isFinite(position[0]) && Number.isFinite(position[1]) && position[0] > 24 && position[0] < width - 24 && position[1] > 38 && position[1] < height - 26;
  }

  function zoomBounds(bounds, factor, focus, maximumZoom = 3) {
    const zoom = Math.min(maximumZoom, Math.max(1, Number(factor) || 1));
    const [west, south, east, north] = bounds;
    const halfWidth = (east - west) / (2 * zoom);
    const halfHeight = (north - south) / (2 * zoom);
    const center = focus || [(west + east) / 2, (south + north) / 2];
    const longitude = Math.min(east - halfWidth, Math.max(west + halfWidth, center[0]));
    const latitude = Math.min(north - halfHeight, Math.max(south + halfHeight, center[1]));
    return [longitude - halfWidth, latitude - halfHeight, longitude + halfWidth, latitude + halfHeight];
  }

  function panBounds(bounds, deltaLongitude, deltaLatitude, limits = VIEWS.world.bounds) {
    const width = bounds[2] - bounds[0];
    const height = bounds[3] - bounds[1];
    const west = Math.max(limits[0], Math.min(limits[2] - width, bounds[0] + deltaLongitude));
    const south = Math.max(limits[1], Math.min(limits[3] - height, bounds[1] + deltaLatitude));
    return [west, south, west + width, south + height];
  }

  function boxesOverlap(a, b, gap = 5) {
    return a.x < b.x + b.width + gap && a.x + a.width + gap > b.x && a.y < b.y + b.height + gap && a.y + a.height + gap > b.y;
  }

  function placeCallout(point, width, height, occupied, canvasWidth = WIDTH, canvasHeight = HEIGHT) {
    const [x, y] = point;
    const positions = [[x + 18, y - height / 2], [x - width - 18, y - height / 2], [x + 14, y - height - 18], [x - width - 14, y - height - 18], [x + 14, y + 18], [x - width - 14, y + 18]];
    return positions.map(([left, top]) => ({ x: left, y: top, width, height })).find((box) => box.x >= 26 && box.y >= 54 && box.x + width <= canvasWidth - 26 && box.y + height <= canvasHeight - 32 && !occupied.some((other) => boxesOverlap(box, other))) || null;
  }

  const featureCode = (feature) => feature.properties.iso_a3 || feature.properties.code;

  async function initializeMap() {
    const root = document.getElementById('dashboardGeography');
    const dataElement = document.getElementById('dashboard-geography-data');
    if (!root || !dataElement) return;
    const svg = root.querySelector('.dashboard-map-svg');
    const status = root.querySelector('[data-map-status]');
    const tooltip = root.querySelector('[data-map-tooltip]');
    let data;
    try { data = JSON.parse(dataElement.textContent); }
    catch (_) { status.textContent = 'Origin data could not be loaded. Refresh the dashboard to try again.'; return; }
    const countries = Array.isArray(data.countries) ? data.countries : [];
    const locations = Array.isArray(data.locations) ? data.locations : [];
    const countryLookup = new Map(countries.map((country) => [country.code, country]));
    const countMaximum = Math.max(0, ...countries.map((country) => Number(country.count) || 0));
    const mapped = Number(data.summary?.mapped) || 0;
    const total = Number(data.summary?.total) || 0;
    const coverage = total ? Math.min(100, Math.max(0, mapped / total * 100)) : 0;
    root.style.setProperty('--coverage', `${coverage}%`);
    const coverageLabel = root.querySelector('[data-map-coverage-label]');
    if (coverageLabel) coverageLabel.textContent = `${Math.round(coverage)}%`;

    let africaFeatures = [];
    let worldFeatures = null;
    let worldRequest = null;
    let references = [];
    let currentView = VIEWS[data.default_view] ? data.default_view : 'west-africa';
    let selectedCode = 'GHA';
    let selectionLocation = null;
    let metric = 'count';
    let showLocations = true;
    let zoom = 1;
    let currentBounds = [...VIEWS[currentView].bounds];
    let mapHeight = HEIGHT;
    let requestSequence = 0;
    let suppressClickUntil = 0;
    const features = () => worldFeatures || africaFeatures;
    const displayValue = (count) => metricValue(count, mapped, metric);
    const formatValue = (count) => metric === 'percentage' ? `${displayValue(count).toFixed(1)}%` : Number(count).toLocaleString();
    const setText = (selector, value) => { const node = root.querySelector(selector); if (node) node.textContent = value; };

    function findCountry(code) {
      const feature = features().find((item) => featureCode(item) === code || item.properties.iso_a2 === code);
      const canonical = feature ? featureCode(feature) : code;
      const country = countryLookup.get(canonical);
      const reference = references.find((item) => item.iso_a3 === canonical) || feature?.properties || country;
      return { feature, country, reference, code: canonical };
    }

    function searchRecords() {
      const records = new Map();
      references.forEach((item) => records.set(item.iso_a3, { ...item, code: item.iso_a3, count: countryLookup.get(item.iso_a3)?.count || 0 }));
      features().forEach((item) => { const code = featureCode(item); records.set(code, { ...item.properties, code, count: countryLookup.get(code)?.count || 0 }); });
      countries.forEach((item) => records.set(item.code, { ...records.get(item.code), ...item }));
      return [...records.values()];
    }

    async function ensureWorld() {
      if (worldFeatures) return true;
      if (!worldRequest) {
        worldRequest = fetch(root.dataset.worldShapeUrl || '/static/data/world.geojson', { credentials: 'same-origin' }).then((response) => {
          if (!response.ok) throw new Error('World boundaries unavailable');
          return response.json();
        }).then((shape) => {
          if (!Array.isArray(shape.features) || !shape.features.length) throw new Error('Invalid world boundaries');
          worldFeatures = shape.features.filter((item) => item.geometry && ['Polygon', 'MultiPolygon'].includes(item.geometry.type));
          return true;
        }).catch(() => { worldRequest = null; return false; });
      }
      return worldRequest;
    }

    function drawInset() {
      const inset = root.querySelector('[data-map-inset]');
      if (!inset || !africaFeatures.length) return;
      inset.replaceChildren();
      const project = projection([-26, -37, 55, 39], 120, 120, 8);
      africaFeatures.forEach((feature) => inset.append(svgElement('path', { d: geometryPath(feature.geometry, project), class: `map-inset-land${featureCode(feature) === 'GHA' ? ' map-inset-ghana' : ''}${featureCode(feature) === selectedCode ? ' map-inset-selected' : ''}`, 'fill-rule': 'evenodd' })));
      if (currentView !== 'world' && (currentView !== 'africa' || zoom > 1)) {
        const northwest = project([currentBounds[0], currentBounds[3]]);
        const southeast = project([currentBounds[2], currentBounds[1]]);
        inset.append(svgElement('rect', { x: northwest[0], y: northwest[1], width: southeast[0] - northwest[0], height: southeast[1] - northwest[1], rx: 2, class: 'map-inset-viewport' }));
      }
    }

    function updateLegend() {
      const container = root.querySelector('[data-map-legend-bins]');
      if (container) {
        container.replaceChildren();
        legendBins(countMaximum, metric).forEach((bin, index) => {
          const entry = document.createElement('span');
          entry.className = 'dashboard-map-legend-bin';
          entry.dataset.mapBin = String(index);
          entry.hidden = bin.hidden;
          const swatch = document.createElement('i');
          swatch.className = 'dashboard-map-swatch';
          swatch.style.backgroundColor = bin.color;
          const label = document.createElement('span');
          label.className = 'dashboard-map-range';
          label.textContent = bin.label;
          entry.append(swatch, label);
          container.append(entry);
        });
      }
      setText('[data-map-legend-title]', metric === 'percentage' ? 'SHARE OF MAPPED RECORDS' : 'ORIGIN COUNTS');
      root.querySelectorAll('[data-map-metric]').forEach((button) => button.setAttribute('aria-pressed', String(button.dataset.mapMetric === metric)));
      root.dataset.metric = metric;
      root.querySelectorAll('[data-map-country]').forEach((button) => {
        const country = countryLookup.get(button.dataset.mapCountry);
        const count = country?.count || 0;
        const value = button.querySelector('strong');
        if (value) value.textContent = formatValue(count);
        const share = mapped ? count / mapped * 100 : 0;
        const bar = button.querySelector('[data-map-share]');
        if (bar) bar.style.setProperty('--share', `${share}%`);
        button.title = `${country?.name || button.dataset.mapCountry}: ${count} records, ${share.toFixed(1)}% of mapped records`;
      });
    }

    function updateSelection(code, location = null) {
      const found = findCountry(code);
      selectedCode = found.code;
      selectionLocation = location;
      const name = location ? location.label : found.country?.name || found.reference?.name || (code === 'GHA' ? 'Ghana' : code);
      const count = location ? Number(location.count) || 0 : Number(found.country?.count) || 0;
      const region = found.country?.region || (WEST_AFRICA.has(selectedCode) ? 'West Africa' : found.reference?.continent === 'Africa' ? 'Africa' : 'Outside Africa');
      setText('[data-map-selection-title]', name);
      setText('[data-map-selection-region]', location ? location.country : region);
      setText('[data-map-selection-code]', found.reference?.iso_a2 || selectedCode);
      setText('[data-map-selection-count]', formatValue(count));
      setText('[data-map-selection-unit]', metric === 'percentage' ? 'of mapped records' : data.kind === 'samples' ? 'sample records' : 'inventory records');
      const selectedLocations = location ? [location] : locations.filter((item) => item.country_code === selectedCode);
      setText('[data-map-selection-share]', metric === 'percentage' ? `${count.toLocaleString()} recorded ${count === 1 ? 'origin' : 'origins'}` : `${metricValue(count, mapped, 'percentage').toFixed(1)}% of mapped records`);
      let hint = count ? `${selectedLocations.length} recorded origin ${selectedLocations.length === 1 ? 'location' : 'locations'}.` : 'No inventory records currently have a recognised origin in this country.';
      if (location) hint = location.precision === 'coordinates' ? 'Position uses coordinates supplied in the metadata.' : 'Approximate position based on the recorded place name.';
      else if (count && region === 'Outside Africa' && found.feature) hint = 'This international origin is shown in the World view. Recorded locations are listed below.';
      setText('[data-map-selection-hint]', hint);
      const list = root.querySelector('[data-map-location-list]');
      list.replaceChildren();
      selectedLocations.forEach((item) => {
        const entry = document.createElement('li');
        const label = document.createElement('span');
        label.textContent = item.label;
        const amount = document.createElement('strong');
        amount.textContent = formatValue(item.count);
        amount.title = `${item.count} records`;
        const note = document.createElement('small');
        const precision = item.precision === 'coordinates' ? 'Supplied coordinates' : item.precision === 'country' ? 'Country-level origin' : 'Approximate place centre';
        const vendors = Array.isArray(item.vendors) && item.vendors.length ? ` · ${item.vendors.join(', ')}` : '';
        note.textContent = `${precision}${vendors}${item.warning ? ` · ${item.warning}` : ''}`;
        entry.append(label, amount, note);
        list.append(entry);
      });
      root.querySelectorAll('[data-map-country]').forEach((button) => button.setAttribute('aria-pressed', String(findCountry(button.dataset.mapCountry).code === selectedCode)));
      svg.querySelectorAll('.map-country').forEach((path) => {
        const selected = path.dataset.code === selectedCode;
        path.classList.toggle('map-country-selected', selected);
        path.setAttribute('aria-pressed', String(selected));
      });
      svg.querySelectorAll('.map-point').forEach((point) => point.classList.toggle('map-point-selected', location !== null && point.dataset.location === String(locations.indexOf(location))));
      drawInset();
    }

    function tooltipFor(element, message) {
      element.addEventListener('mouseenter', () => { if (Date.now() < suppressClickUntil) return; tooltip.textContent = message; tooltip.hidden = false; });
      element.addEventListener('mouseleave', () => { tooltip.hidden = true; });
      element.addEventListener('blur', () => { tooltip.hidden = true; });
    }

    function activateWithKeyboard(element, action) {
      element.addEventListener('click', () => { if (Date.now() >= suppressClickUntil) action(); });
      element.addEventListener('keydown', (event) => { if (event.key === 'Enter' || event.key === ' ') { event.preventDefault(); action(); } });
    }

    function drawMap() {
      svg.querySelector('[data-map-camera]')?.remove();
      svg.querySelectorAll('[data-map-layer]').forEach((layer) => layer.remove());
      const measuredWidth = svg.clientWidth || WIDTH;
      mapHeight = Math.min(1100, Math.max(HEIGHT, Math.round(WIDTH * (svg.clientHeight || HEIGHT) / measuredWidth)));
      const labelScale = Math.max(1, Math.min(2.2, WIDTH / measuredWidth * 0.9));
      svg.setAttribute('viewBox', `0 0 ${WIDTH} ${mapHeight}`);
      const project = projection(currentBounds, WIDTH, mapHeight);
      const camera = svgElement('g', { 'data-map-camera': 'true' });
      svg.append(camera);
      const grid = svgElement('g', { 'data-map-layer': 'grid', 'aria-hidden': 'true' });
      const interval = currentView === 'ghana' ? 2 : currentView === 'world' ? 30 : currentView === 'africa' ? 10 : 5;
      for (let longitude = -180; longitude <= 180; longitude += interval) {
        const start = project([longitude, -80]); const end = project([longitude, 85]);
        grid.append(svgElement('path', { d: `M${start.join(',')}L${end.join(',')}`, class: 'map-grid-line' }));
      }
      for (let latitude = -60; latitude <= 80; latitude += interval) {
        const start = project([-180, latitude]); const end = project([180, latitude]);
        grid.append(svgElement('path', { d: `M${start.join(',')}L${end.join(',')}`, class: 'map-grid-line' }));
      }
      const depth = svgElement('g', { 'data-map-layer': 'depth', class: 'map-country-depth', 'aria-hidden': 'true' });
      const boundaries = svgElement('g', { 'data-map-layer': 'countries' });
      const labels = svgElement('g', { 'data-map-layer': 'labels', 'aria-hidden': 'true' });
      const labelCandidates = [];
      const knownCodes = new Set(features().map(featureCode));
      features().forEach((feature) => {
        const properties = feature.properties; const code = featureCode(feature);
        const country = countryLookup.get(code); const count = Number(country?.count) || 0;
        const name = country?.name || properties.name;
        const center = project([properties.longitude, properties.latitude]);
        const classes = ['map-country'];
        if (code === 'GHA') classes.push('map-country-ghana');
        if (code === selectedCode) classes.push('map-country-selected');
        if (count) classes.push('map-country-populated');
        const value = displayValue(count);
        const d = geometryPath(feature.geometry, project);
        depth.append(svgElement('path', { d, 'fill-rule': 'evenodd' }));
        const path = svgElement('path', { d, fill: countryColor(value, countMaximum, WEST_AFRICA.has(code), metric), class: classes.join(' '), 'data-code': code, role: 'button', tabindex: visiblePosition(center, WIDTH, mapHeight) ? 0 : -1, 'aria-label': `${name}: ${formatValue(count)}${metric === 'count' ? ` ${count === 1 ? 'record' : 'records'}` : ' of mapped records'}`, 'aria-pressed': String(code === selectedCode), 'fill-rule': 'evenodd' });
        path.append(svgElement('title', {}, `${name}: ${formatValue(count)}${metric === 'percentage' ? ' of mapped records' : ' records'}`));
        activateWithKeyboard(path, () => updateSelection(code));
        path.addEventListener('focus', () => updateSelection(code));
        tooltipFor(path, `${name} · ${formatValue(count)}${metric === 'percentage' ? ' of mapped records' : ' records'}`);
        boundaries.append(path);
        const isReferenceLabel = currentView === 'world' ? ['USA', 'CAN', 'BRA', 'CHN', 'IND', 'RUS', 'AUS', 'EGY', 'ZAF', 'GHA'].includes(code) : currentView === 'africa' ? ['GHA', 'NGA', 'ZAF', 'KEN', 'EGY', 'DZA', 'COD'].includes(code) : currentView === 'west-africa' ? WEST_AFRICA.has(code) : true;
        if (visiblePosition(center, WIDTH, mapHeight) && (isReferenceLabel || count > 0 || code === selectedCode)) labelCandidates.push({ code, name: code === 'GHA' ? 'GHANA' : LABEL_NAMES[code] || name, count, center });
      });
      camera.append(grid, depth, boundaries, labels);
      const points = svgElement('g', { 'data-map-layer': 'locations' });
      const callouts = svgElement('g', { 'data-map-layer': 'callouts', 'aria-hidden': 'true' });
      const markerPositions = [];
      if (showLocations) locations.forEach((location, index) => {
        if (location.precision === 'country' || location.latitude === null || location.longitude === null || !Number.isFinite(Number(location.latitude)) || !Number.isFinite(Number(location.longitude)) || !knownCodes.has(location.country_code)) return;
        const position = project([Number(location.longitude), Number(location.latitude)]);
        if (!visiblePosition(position, WIDTH, mapHeight)) return;
        markerPositions.push({ location, position });
        const radius = Math.min(9, 4.5 + Math.sqrt(Number(location.count) || 0) * 0.45) * Math.min(1.5, labelScale);
        const group = svgElement('g', { class: `map-point${selectionLocation === location ? ' map-point-selected' : ''}`, transform: `translate(${position.join(',')})`, role: 'button', tabindex: 0, 'data-location': index, 'aria-label': `${location.label}: ${location.count} records. ${location.precision === 'coordinates' ? 'Supplied coordinates.' : 'Approximate place centre.'}` });
        group.append(svgElement('circle', { r: radius + 7, class: 'map-point-halo' }), svgElement('circle', { r: radius + 3, class: 'map-point-ring' }), svgElement('circle', { r: radius, class: 'map-point-dot' }));
        group.append(svgElement('title', {}, `${location.label}: ${location.count} records`));
        activateWithKeyboard(group, () => updateSelection(location.country_code, location));
        group.addEventListener('focus', () => updateSelection(location.country_code, location));
        tooltipFor(group, `${location.label} · ${location.count} records · ${location.precision === 'coordinates' ? 'supplied coordinates' : 'approximate'}`);
        points.append(group);
      });
      const occupied = markerPositions.map(({ position }) => ({ x: position[0] - 13, y: position[1] - 13, width: 26, height: 26 }));
      const frame = svg.getBoundingClientRect();
      if (frame.width && frame.height) root.querySelectorAll('.dashboard-map-sidebar, .dashboard-map-selection, .dashboard-map-search, .dashboard-map-views, .dashboard-map-legend, .dashboard-map-context, .dashboard-map-toolbar, .dashboard-map-view-label, .dashboard-map-compass, .dashboard-map-instruction').forEach((overlay) => {
        const rectangle = overlay.getBoundingClientRect();
        if (rectangle.width && rectangle.height) occupied.push({ x: (rectangle.left - frame.left) * WIDTH / frame.width, y: (rectangle.top - frame.top) * mapHeight / frame.height, width: rectangle.width * WIDTH / frame.width, height: rectangle.height * mapHeight / frame.height });
      });
      if (showLocations && (currentView === 'ghana' || zoom >= 2)) markerPositions.filter(({ location }) => location.country_code === (currentView === 'ghana' ? 'GHA' : selectedCode)).sort((a, b) => Number(b.location.count) - Number(a.location.count)).slice(0, 8).forEach(({ location, position }) => {
        const name = location.label.split(',')[0];
        if (name === location.country) return;
        const label = name.length > 23 ? `${name.slice(0, 22)}…` : name;
        const amount = formatValue(location.count);
        const width = Math.max(98, label.length * 6.4 + amount.length * 7 + 34) * labelScale;
        const height = 31 * labelScale;
        const box = placeCallout(position, width, height, occupied, WIDTH, mapHeight);
        if (!box) return;
        occupied.push(box);
        const group = svgElement('g', { class: 'map-place-callout' });
        const lineX = box.x > position[0] ? box.x : box.x + box.width;
        group.append(svgElement('path', { d: `M${position.join(',')}L${lineX},${box.y + box.height / 2}`, class: 'map-callout-line' }));
        group.append(svgElement('rect', { x: box.x, y: box.y, width: box.width, height: box.height, rx: 8 * labelScale, class: 'map-place-shell' }));
        group.append(svgElement('text', { x: box.x + 11 * labelScale, y: box.y + box.height / 2 + 4 * labelScale, 'font-size': 11 * labelScale, class: 'map-place-label' }, label));
        group.append(svgElement('text', { x: box.x + box.width - 10 * labelScale, y: box.y + box.height / 2 + 4 * labelScale, 'font-size': 11 * labelScale, 'text-anchor': 'end', class: 'map-place-count' }, amount));
        callouts.append(group);
      });
      labelCandidates.sort((a, b) => Number(b.code === selectedCode) - Number(a.code === selectedCode) || Number(b.code === 'GHA') - Number(a.code === 'GHA') || b.count - a.count).forEach((candidate) => {
        const fontSize = (candidate.code === selectedCode || candidate.code === 'GHA' ? 13 : 10.5) * labelScale;
        const width = Math.max(candidate.name.length * fontSize * 0.53, candidate.count ? 65 * labelScale : 0);
        const height = (candidate.count ? 32 : 16) * labelScale;
        let center = candidate.center;
        let box = { x: center[0] - width / 2, y: center[1] - 12 * labelScale, width, height };
        if (occupied.some((other) => boxesOverlap(box, other, 7)) || box.x < 22 || box.x + width > WIDTH - 22) {
          if (candidate.code !== 'GHA' && candidate.code !== selectedCode) return;
          box = placeCallout(center, width, height, occupied, WIDTH, mapHeight);
          if (!box) return;
          center = [box.x + width / 2, box.y + 12 * labelScale];
          labels.append(svgElement('path', { d: `M${candidate.center.join(',')}L${center[0]},${box.y + height}`, class: 'map-country-label-leader' }));
        }
        occupied.push(box);
        const text = svgElement('text', { x: center[0], y: center[1], 'font-size': fontSize, class: `map-country-label${candidate.code === 'GHA' ? ' map-country-label-ghana' : ''}${candidate.count ? ' map-country-label-populated' : ''}` }, candidate.name);
        if (candidate.count) text.append(svgElement('tspan', { x: center[0], dy: 16 * labelScale, 'font-size': 10 * labelScale, class: 'map-country-count' }, `${formatValue(candidate.count)}${metric === 'count' ? ' records' : ''}`));
        labels.append(text);
      });
      camera.append(callouts, points);
      setText('[data-map-view-label]', VIEWS[currentView].label);
      root.querySelectorAll('[data-map-view]').forEach((button) => button.setAttribute('aria-pressed', String(button.dataset.mapView === currentView)));
      setText('[data-map-zoom-label]', `${Number(zoom.toFixed(1))}×`);
      root.querySelectorAll('[data-map-zoom]').forEach((button) => { button.disabled = !africaFeatures.length || button.dataset.mapZoom === 'in' && zoom >= MAX_ZOOM || button.dataset.mapZoom === 'out' && zoom <= 1; });
      tooltip.hidden = true;
      drawInset();
    }

    async function changeView(view) {
      if (!VIEWS[view]) return false;
      const request = ++requestSequence;
      if (view === 'world') {
        status.textContent = 'Loading world boundaries…'; status.hidden = false;
        const ready = await ensureWorld();
        if (request !== requestSequence) return false;
        if (!ready) { status.textContent = 'World boundaries could not load. The Africa map and recorded origin details remain available.'; return false; }
      }
      if (request !== requestSequence) return false;
      currentView = view; zoom = 1; currentBounds = [...VIEWS[view].bounds];
      if (view === 'ghana') updateSelection('GHA');
      status.hidden = true;
      if (africaFeatures.length) drawMap();
      return true;
    }

    function fitCountry(found) {
      if (!found.feature) return;
      const geometry = found.feature.geometry;
      const polygons = geometry.type === 'Polygon' ? [geometry.coordinates] : geometry.coordinates;
      const candidates = polygons.map((polygon) => {
        const xs = polygon[0].map((point) => point[0]); const ys = polygon[0].map((point) => point[1]);
        const bounds = [Math.min(...xs), Math.min(...ys), Math.max(...xs), Math.max(...ys)];
        return { bounds, area: (bounds[2] - bounds[0]) * (bounds[3] - bounds[1]) };
      }).sort((a, b) => b.area - a.area);
      const representative = [Number(found.reference?.longitude), Number(found.reference?.latitude)];
      const chosen = candidates.find(({ bounds: b }) => representative[0] >= b[0] && representative[0] <= b[2] && representative[1] >= b[1] && representative[1] <= b[3]) || candidates[0];
      if (!chosen) return;
      const b = chosen.bounds; const base = VIEWS[currentView].bounds;
      const factor = Math.min((base[2] - base[0]) / Math.max(1, (b[2] - b[0]) * 1.55), (base[3] - base[1]) / Math.max(1, (b[3] - b[1]) * 1.55));
      zoom = Math.min(MAX_ZOOM, Math.max(1, factor));
      currentBounds = zoomBounds(base, zoom, [(b[0] + b[2]) / 2, (b[1] + b[3]) / 2], MAX_ZOOM);
    }

    async function chooseCountry(code, fit = true) {
      let found = findCountry(code);
      const isAfrican = africaFeatures.some((feature) => featureCode(feature) === found.code);
      const targetView = found.code === 'GHA' ? 'ghana' : isAfrican ? WEST_AFRICA.has(found.code) ? 'west-africa' : 'africa' : 'world';
      const selectionRequest = requestSequence + 1;
      const ready = await changeView(targetView);
      if (selectionRequest !== requestSequence) return;
      found = findCountry(code);
      updateSelection(found.code);
      if (ready && fit) fitCountry(found);
      if (africaFeatures.length) drawMap();
    }

    function applyZoom(direction) {
      if (!africaFeatures.length) return;
      if (direction === 'reset') { zoom = 1; currentBounds = [...VIEWS[currentView].bounds]; }
      else {
        const next = Math.min(MAX_ZOOM, Math.max(1, direction === 'in' ? zoom * 1.5 : zoom / 1.5));
        const center = [(currentBounds[0] + currentBounds[2]) / 2, (currentBounds[1] + currentBounds[3]) / 2];
        const base = VIEWS[currentView].bounds;
        currentBounds = zoomBounds(base, next, center, MAX_ZOOM);
        zoom = next;
      }
      drawMap();
    }

    root.querySelectorAll('[data-map-country]').forEach((button) => button.addEventListener('click', () => { void chooseCountry(button.dataset.mapCountry); }));
    root.querySelectorAll('[data-map-view]').forEach((button) => button.addEventListener('click', () => { void changeView(button.dataset.mapView); }));
    root.querySelectorAll('[data-map-zoom]').forEach((button) => button.addEventListener('click', () => applyZoom(button.dataset.mapZoom)));
    root.querySelectorAll('[data-map-metric]').forEach((button) => button.addEventListener('click', () => {
      metric = button.dataset.mapMetric === 'percentage' ? 'percentage' : 'count';
      updateLegend(); updateSelection(selectedCode, selectionLocation); if (africaFeatures.length) drawMap();
    }));
    const layer = root.querySelector('input[data-map-layer="locations"]');
    if (layer && layer.tagName === 'INPUT') layer.addEventListener('change', () => { showLocations = layer.checked; if (africaFeatures.length) drawMap(); });
    const panelToggle = root.querySelector('[data-map-panels-toggle]');
    panelToggle?.addEventListener('click', () => {
      const collapsed = root.classList.toggle('map-panels-collapsed');
      panelToggle.setAttribute('aria-pressed', String(collapsed)); panelToggle.setAttribute('aria-expanded', String(!collapsed)); panelToggle.setAttribute('aria-label', collapsed ? 'Show map panels' : 'Hide map panels');
      if (africaFeatures.length) drawMap();
    });
    const fullscreen = root.querySelector('[data-map-fullscreen]');
    if (fullscreen) {
      if (!root.requestFullscreen) fullscreen.hidden = true;
      else fullscreen.addEventListener('click', async () => {
        try { if (document.fullscreenElement === root) await document.exitFullscreen(); else await root.requestFullscreen(); }
        catch (_) { setText('[data-map-search-status]', 'Full screen is not available in this browser.'); }
      });
      document.addEventListener('fullscreenchange', () => { const active = document.fullscreenElement === root; fullscreen.setAttribute('aria-pressed', String(active)); fullscreen.setAttribute('aria-label', active ? 'Exit full screen' : 'View map full screen'); svg.style.touchAction = active ? 'none' : 'pan-y'; });
    }

    const search = root.querySelector('[data-map-search]');
    const results = root.querySelector('[data-map-search-results]');
    const searchStatus = root.querySelector('[data-map-search-status]');
    let matches = []; let activeResult = -1;
    function closeSearch() { if (results) results.hidden = true; search?.setAttribute('aria-expanded', 'false'); search?.removeAttribute('aria-activedescendant'); }
    function renderSearch() {
      if (!search || !results) return;
      matches = matchCountries(searchRecords(), search.value); activeResult = -1; results.replaceChildren();
      results.hidden = false; search.setAttribute('aria-expanded', 'true');
      if (searchStatus) searchStatus.textContent = matches.length ? `${matches.length} ${matches.length === 1 ? 'country' : 'countries'} found. Use the arrow keys and Enter to select.` : 'No countries found. Try a country name or ISO code.';
      matches.forEach((record, index) => {
        const option = document.createElement('button'); option.type = 'button'; option.className = 'dashboard-map-search-option'; option.id = `dashboard-map-result-${index}`; option.setAttribute('role', 'option'); option.setAttribute('aria-selected', 'false');
        const name = document.createElement('span'); name.textContent = record.name;
        const amount = document.createElement('strong'); amount.textContent = formatValue(record.count || 0);
        option.append(name, amount);
        option.addEventListener('pointerdown', (event) => event.preventDefault());
        option.addEventListener('click', () => { search.value = record.name; closeSearch(); if (searchStatus) searchStatus.textContent = `${record.name} selected.`; void chooseCountry(record.code); });
        results.append(option);
      });
    }
    search?.addEventListener('input', renderSearch);
    search?.addEventListener('focus', renderSearch);
    search?.addEventListener('blur', () => setTimeout(closeSearch, 0));
    search?.addEventListener('keydown', (event) => {
      if (event.key === 'Escape') { event.preventDefault(); event.stopPropagation(); closeSearch(); if (searchStatus) searchStatus.textContent = ''; return; }
      if (event.key === 'ArrowDown' || event.key === 'ArrowUp') {
        event.preventDefault(); if (results.hidden) renderSearch();
        activeResult = Math.max(0, Math.min(matches.length - 1, activeResult + (event.key === 'ArrowDown' ? 1 : -1)));
        [...results.children].forEach((option, index) => option.setAttribute('aria-selected', String(index === activeResult)));
        if (matches[activeResult]) { search.setAttribute('aria-activedescendant', `dashboard-map-result-${activeResult}`); results.children[activeResult].scrollIntoView({ block: 'nearest' }); }
      } else if (event.key === 'Enter') {
        event.preventDefault(); const record = matches[activeResult < 0 ? 0 : activeResult];
        if (record) { search.value = record.name; closeSearch(); if (searchStatus) searchStatus.textContent = `${record.name} selected.`; void chooseCountry(record.code); }
      }
    });
    root.addEventListener('click', (event) => { if (search && results && !search.contains(event.target) && !results.contains(event.target)) closeSearch(); });

    let drag = null;
    svg.style.touchAction = 'pan-y'; svg.setAttribute('tabindex', '0');
    svg.addEventListener('pointerdown', (event) => {
      if (event.button !== 0 || !africaFeatures.length || event.pointerType === 'touch' && document.fullscreenElement !== root) return;
      drag = { id: event.pointerId, x: event.clientX, y: event.clientY, bounds: [...currentBounds], moved: false };
    });
    svg.addEventListener('pointermove', (event) => {
      if (!drag || drag.id !== event.pointerId) return;
      const dx = event.clientX - drag.x; const dy = event.clientY - drag.y;
      if (!drag.moved && Math.hypot(dx, dy) < 5) return;
      if (!drag.moved) { svg.setPointerCapture(event.pointerId); void ensureWorld(); }
      drag.moved = true; svg.classList.add('map-is-panning'); tooltip.hidden = true;
      const rectangle = svg.getBoundingClientRect();
      svg.querySelector('[data-map-camera]')?.setAttribute('transform', `translate(${dx * WIDTH / rectangle.width} ${dy * mapHeight / rectangle.height})`);
    });
    function finishDrag(event) {
      if (!drag || drag.id !== event.pointerId) return;
      const finished = drag; drag = null; svg.classList.remove('map-is-panning');
      if (svg.hasPointerCapture(event.pointerId)) svg.releasePointerCapture(event.pointerId);
      if (finished.moved) {
        const rectangle = svg.getBoundingClientRect(); const inverse = projection(finished.bounds, WIDTH, mapHeight).invert;
        const start = inverse([0, 0]); const end = inverse([(event.clientX - finished.x) * WIDTH / rectangle.width, (event.clientY - finished.y) * mapHeight / rectangle.height]);
        currentBounds = panBounds(finished.bounds, start[0] - end[0], start[1] - end[1]); suppressClickUntil = Date.now() + 250; drawMap();
      }
    }
    svg.addEventListener('pointerup', finishDrag); svg.addEventListener('pointercancel', finishDrag);
    svg.addEventListener('wheel', (event) => { if (!event.ctrlKey && !event.metaKey) return; event.preventDefault(); applyZoom(event.deltaY < 0 ? 'in' : 'out'); }, { passive: false });
    svg.addEventListener('keydown', (event) => {
      if (event.target !== svg) return;
      if (event.key === '+' || event.key === '=') { event.preventDefault(); applyZoom('in'); }
      else if (event.key === '-') { event.preventDefault(); applyZoom('out'); }
      else if (['ArrowLeft', 'ArrowRight', 'ArrowUp', 'ArrowDown'].includes(event.key)) {
        event.preventDefault(); const x = (currentBounds[2] - currentBounds[0]) * 0.15; const y = (currentBounds[3] - currentBounds[1]) * 0.15;
        currentBounds = panBounds(currentBounds, event.key === 'ArrowLeft' ? -x : event.key === 'ArrowRight' ? x : 0, event.key === 'ArrowUp' ? y : event.key === 'ArrowDown' ? -y : 0); void ensureWorld(); drawMap();
      }
    });

    updateLegend();
    const referenceUrl = root.dataset.countryReferenceUrl;
    if (referenceUrl) fetch(referenceUrl, { credentials: 'same-origin' }).then((response) => { if (!response.ok) throw new Error('References unavailable'); return response.json(); }).then((records) => { if (Array.isArray(records)) references = records; if (search && document.activeElement === search) renderSearch(); }).catch(() => { /* Country names from the loaded map and inventory remain searchable. */ });
    try {
      const response = await fetch(root.dataset.shapeUrl, { credentials: 'same-origin' });
      if (!response.ok) throw new Error('Country boundaries unavailable');
      const shape = await response.json();
      if (!Array.isArray(shape.features) || !shape.features.length) throw new Error('Invalid boundary data');
      africaFeatures = shape.features.filter((item) => item.geometry && ['Polygon', 'MultiPolygon'].includes(item.geometry.type));
      drawMap(); status.hidden = true; updateSelection(selectedCode, selectionLocation);
      if (typeof ResizeObserver !== 'undefined') {
        let lastWidth = svg.clientWidth; let lastHeight = svg.clientHeight;
        const observer = new ResizeObserver(() => { if (svg.clientWidth !== lastWidth || svg.clientHeight !== lastHeight) { lastWidth = svg.clientWidth; lastHeight = svg.clientHeight; drawMap(); } }); observer.observe(svg);
      }
    } catch (_) { status.textContent = 'The map is temporarily unavailable. Origin counts remain available in the country list.'; updateSelection('GHA'); }
  }

  if (typeof document !== 'undefined') document.addEventListener('DOMContentLoaded', initializeMap);
  if (typeof module !== 'undefined' && module.exports) module.exports = { projection, geometryPath, countryColor, colorIndex, metricValue, legendBins, normalizeSearch, matchCountries, visiblePosition, zoomBounds, panBounds, placeCallout, boxesOverlap };
})();
