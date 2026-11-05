const assert = require('node:assert/strict');
const { readFileSync } = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const { projection, geometryPath, countryColor, visiblePosition, zoomBounds, placeCallout, boxesOverlap, colorIndex, metricValue, legendBins, normalizeSearch, matchCountries, panBounds } = require('../dashboard_map.js');

const VIEWS = {
  westAfrica: [-26, -2, 18, 29],
  africa: [-20, -37, 54, 39],
  ghana: [-4.7, 3.7, 2.8, 12.4],
};

test('map projection centers each regional view and preserves geographic orientation', () => {
  for (const bounds of Object.values(VIEWS)) {
    const project = projection(bounds);
    const center = [(bounds[0] + bounds[2]) / 2, (bounds[1] + bounds[3]) / 2];
    assert.deepEqual(project(center), [400, 250]);
    assert.ok(project([center[0] + 1, center[1]])[0] > 400, 'east appears to the right');
    assert.ok(project([center[0], center[1] + 1])[1] < 250, 'north appears above');
    const longitudeDistance = project([center[0] + 1, center[1]])[0] - 400;
    const latitudeDistance = 250 - project([center[0], center[1] + 1])[1];
    assert.ok(Math.abs(longitudeDistance / latitudeDistance - Math.cos(center[1] * Math.PI / 180)) < 1e-12);
  }
});

test('polygon paths preserve an outer boundary and its inner hole', () => {
  const geometry = {
    type: 'Polygon',
    coordinates: [
      [[0, 0], [4, 0], [4, 4], [0, 0]],
      [[1, 1], [2, 1], [2, 2], [1, 1]],
    ],
  };
  const result = geometryPath(geometry, (coordinate) => coordinate);
  assert.equal(result, 'M0.00,0.00L4.00,0.00L4.00,4.00L0.00,0.00ZM1.00,1.00L2.00,1.00L2.00,2.00L1.00,1.00Z');
});

test('multipolygon paths preserve separate land masses and close every boundary', () => {
  const geometry = {
    type: 'MultiPolygon',
    coordinates: [
      [[[0, 0], [1, 0], [0, 1], [0, 0]]],
      [[[4, 4], [5, 4], [4, 5], [4, 4]]],
    ],
  };
  const result = geometryPath(geometry, (coordinate) => coordinate);
  assert.equal((result.match(/M/g) || []).length, 2);
  assert.equal((result.match(/Z/g) || []).length, 2);
  assert.ok(result.includes('M4.00,4.00'));
});

test('vendored Ghana boundary and representative location render inside all supplied views', () => {
  const africa = JSON.parse(readFileSync(path.join(__dirname, '../../data/africa.geojson'), 'utf8'));
  const ghana = africa.features.find((feature) => feature.properties.iso_a3 === 'GHA');
  assert.ok(ghana, 'real boundary asset includes Ghana');
  assert.equal(ghana.properties.iso_a2, 'GH');
  const point = [ghana.properties.longitude, ghana.properties.latitude];
  for (const [name, bounds] of Object.entries(VIEWS)) {
    const project = projection(bounds);
    assert.ok(visiblePosition(project(point)), `Ghana representative point is visible in ${name}`);
    const result = geometryPath(ghana.geometry, project);
    assert.ok(result.startsWith('M'));
    assert.ok(result.endsWith('Z'));
    assert.ok(!/NaN|Infinity|undefined/.test(result));
  }
});

test('country shading distinguishes zero records from all three populated ranges', () => {
  assert.equal(countryColor(0, 100, true), 'var(--map-empty-west, #34353b)');
  assert.equal(countryColor(0, 100, false), 'var(--map-empty-other, #282a30)');
  assert.equal(countryColor(1, 100, true), 'var(--map-scale-low, #ffd1b8)');
  assert.equal(countryColor(33, 100, true), 'var(--map-scale-low, #ffd1b8)');
  assert.equal(countryColor(34, 100, true), 'var(--map-scale-medium, #ff9d66)');
  assert.equal(countryColor(66, 100, true), 'var(--map-scale-medium, #ff9d66)');
  assert.equal(countryColor(67, 100, true), 'var(--map-scale-high, #ff5c00)');
  assert.equal(countryColor(100, 100, true), 'var(--map-scale-high, #ff5c00)');
  assert.equal(countryColor(0, 0, true), 'var(--map-empty-west, #34353b)');
  assert.equal(countryColor(1, 1, true), 'var(--map-scale-high, #ff5c00)');
});

test('only finite points inside the usable map frame receive labels and markers', () => {
  assert.equal(visiblePosition([400, 250]), true);
  assert.equal(visiblePosition([-1, 250]), false);
  assert.equal(visiblePosition([400, 501]), false);
  assert.equal(visiblePosition([NaN, 250]), false);
  assert.equal(visiblePosition([400, Infinity]), false);
});


test('zoom focuses a selected origin while keeping the viewport within the selected region', () => {
  const base = VIEWS.westAfrica;
  assert.deepEqual(zoomBounds(base, 1, [-0.2, 5.6]), base);
  const zoomed = zoomBounds(base, 3, [-0.2, 5.6]);
  assert.ok(Math.abs((zoomed[2] - zoomed[0]) - (base[2] - base[0]) / 3) < 1e-10);
  assert.ok(Math.abs((zoomed[3] - zoomed[1]) - (base[3] - base[1]) / 3) < 1e-10);
  assert.ok(zoomed[0] >= base[0] && zoomed[1] >= base[1]);
  assert.ok(zoomed[2] <= base[2] && zoomed[3] <= base[3]);
  const position = projection(zoomed)([-0.2, 5.6]);
  assert.ok(Math.abs(position[0] - 400) < 1e-10);
  assert.ok(Math.abs(position[1] - 250) < 1e-10);
  assert.deepEqual(zoomBounds(base, 0), base);
  assert.deepEqual(zoomBounds(base, 100), zoomBounds(base, 3));
  const edge = zoomBounds(base, 3, [-100, 90]);
  assert.equal(edge[0], base[0]);
  assert.equal(edge[3], base[3]);
});

test('nearby location callouts choose separate readable positions and never overflow', () => {
  const occupied = [];
  const first = placeCallout([400, 250], 140, 32, occupied);
  assert.ok(first);
  occupied.push(first);
  const second = placeCallout([410, 252], 140, 32, occupied);
  assert.ok(second);
  assert.equal(boxesOverlap(first, second), false);
  const nearEdge = placeCallout([775, 200], 180, 40, occupied);
  assert.ok(nearEdge);
  assert.ok(nearEdge.x >= 26 && nearEdge.x + nearEdge.width <= 774);
  assert.equal(placeCallout([400, 250], 140, 32, [{x:0,y:0,width:800,height:500}]), null);
});

test('the mobile projection uses its tall drawing frame without distorting or clipping Ghana', () => {
  const height = 852;
  const project = projection(VIEWS.ghana, 800, height);
  const center = [(VIEWS.ghana[0] + VIEWS.ghana[2]) / 2, (VIEWS.ghana[1] + VIEWS.ghana[3]) / 2];
  assert.deepEqual(project(center), [400, height / 2]);
  for (const point of [[-0.22,5.55],[-1.63,6.69],[-0.84,9.4],[-1.25,5.11]]) {
    assert.equal(visiblePosition(project(point), 800, height), true);
  }
  const mobileCallout = placeCallout(project([-0.22,5.55]), 280, 66, [], 800, height);
  assert.ok(mobileCallout);
  assert.ok(mobileCallout.y + mobileCallout.height <= height - 32);
});


test('country share uses all mapped project records and fixed percentage thresholds', () => {
  assert.ok(Math.abs(metricValue(26,39,'percentage') - 66.6666666667) < 1e-8);
  assert.ok(Math.abs(metricValue(7,39,'percentage') - 17.9487179487) < 1e-8);
  assert.equal(metricValue(26,39,'count'),26);
  assert.equal(metricValue(3,0,'percentage'),0);
  assert.equal(colorIndex(0.5,100,'percentage'),0);
  assert.equal(colorIndex(9.9,100,'percentage'),0);
  assert.equal(colorIndex(10,100,'percentage'),1);
  assert.equal(colorIndex(39.9,100,'percentage'),1);
  assert.equal(colorIndex(40,100,'percentage'),2);
  assert.equal(countryColor(metricValue(7,39,'percentage'),26,false,'percentage'),'var(--map-scale-medium, #ff9d66)');
  assert.equal(legendBins(0,'percentage').length,3);
  assert.ok(legendBins(0).every(bin=>bin.hidden));
});

test('global country search handles accents, ISO codes and aliases without invented records', () => {
  const records=[
    {code:'GHA',iso_a2:'GH',name:'Ghana',count:26},
    {code:'CIV',iso_a2:'CI',name:'Côte d’Ivoire',aliases:['Ivory Coast'],count:4},
    {code:'GBR',iso_a2:'GB',name:'United Kingdom',count:0},
    {code:'COD',name:'Democratic Republic of the Congo',count:0},
    {code:'IND',iso_a2:'IN',name:'India',count:0},
  ];
  assert.equal(normalizeSearch('  Côte d’Ivoire  '),'cote d ivoire');
  for (const [query,code] of [['gh','GHA'],['cote','CIV'],['ivory','CIV'],['UK','GBR'],['DRC','COD'],['India','IND']]) {
    assert.equal(matchCountries(records,query)[0].code,code);
  }
  assert.equal(matchCountries(records,'India')[0].count,0);
  assert.deepEqual(matchCountries(records,'<script>'),[]);
  assert.ok(matchCountries(records,'',2).length<=2);
});

test('projection inversion and map dragging preserve scale and clamp to the world', () => {
  const project=projection(VIEWS.ghana,800,852);
  for (const point of [[-0.22,5.55],[-1.63,6.69],[0,0]]) {
    const restored=project.invert(project(point));
    assert.ok(Math.abs(restored[0]-point[0])<1e-10);
    assert.ok(Math.abs(restored[1]-point[1])<1e-10);
  }
  const moved=panBounds(VIEWS.ghana,8,3);
  assert.ok(Math.abs(moved[0]-(VIEWS.ghana[0]+8))<1e-10);
  assert.ok(Math.abs((moved[2]-moved[0])-(VIEWS.ghana[2]-VIEWS.ghana[0]))<1e-10);
  const clamped=panBounds(VIEWS.ghana,1000,1000);
  assert.equal(clamped[2],180);
  assert.equal(clamped[3],84);
  assert.deepEqual(panBounds([-180,-58,180,84],100,100),[-180,-58,180,84]);
  assert.ok(zoomBounds([-180,-58,180,84],12,[10,51],16)[2]-zoomBounds([-180,-58,180,84],12,[10,51],16)[0]<31);
});
