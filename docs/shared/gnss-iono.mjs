/**
 * SWIFT-ION research-only, first-order *uncorrected* GNSS L1 ionospheric bias.
 * TLE is the newest SWIFT-TEC snapshot (never a time-series archive).
 * SGP4 -> receiver elevation/azimuth -> 350-km thin-shell pierce points ->
 * VTEC(x_ipp) -> slant pseudorange delays -> position/clock least squares.
 * The returned displacement is NOT observed GNSS accuracy or receiver error.
 */
import {spatial} from './forecast.js';
const RAD = Math.PI / 180;
export const L1_FREQUENCY_HZ = 1575.42e6;
export const METERS_PER_TECU = 40.3e16 / (L1_FREQUENCY_HZ * L1_FREQUENCY_HZ);
export const EARTH_KM = 6371;
export const SHELL_KM = 350;
export const MAX_TLE_AGE_HOURS = 72;
export const ELEVATION_MASK_DEG = 10;
export const GNSS_GROUPS = Object.freeze({
  gps: ['gps'],
  gpsqzss: ['gps', 'qzss'],
  all: ['gps', 'qzss', 'galileo', 'glonass', 'beidou'],
});

export function tleEpochMs(line1) {
  if (typeof line1 !== 'string' || !line1.startsWith('1 ') || line1.length < 32) return NaN;
  const yy = Number(line1.slice(18, 20));
  const day = Number(line1.slice(20, 32));
  if (!Number.isFinite(yy) || !Number.isFinite(day) || day < 1 || day > 366.999999) return NaN;
  return Date.UTC(yy >= 57 ? 1900 + yy : 2000 + yy, 0, 1) + (day - 1) * 86400000;
}

export function prepareSatellites(snapshot, satLib) {
  if (!satLib?.twoline2satrec || !satLib?.propagate || !satLib?.eciToEcf || !satLib?.gstime)
    throw Error('SGP4 (satellite.js) がありません');
  if (snapshot?.schema !== 'swift-ion-latest-gnss-v1' || !Array.isArray(snapshot.satellites))
    throw Error('GNSS最新TLEの形式が異なります');
  const sats = [];
  for (const r of snapshot.satellites) {
    if (!GNSS_GROUPS.all.includes(r.system) || typeof r.line1 !== 'string' || typeof r.line2 !== 'string') continue;
    const epoch = tleEpochMs(r.line1);
    if (!Number.isFinite(epoch)) continue;
    // Only GPS has a matching YUMA almanac health source in the upstream dataset.
    if (r.system === 'gps' && r.health != null && Number(r.health) !== 0) continue;
    try {
      sats.push({ ...r, epoch_ms: epoch, satrec: satLib.twoline2satrec(r.line1, r.line2) });
    } catch (_) { /* malformed TLE */ }
  }
  return sats;
}

export function propagateSnapshot(sats, satLib, at, group = 'gps', maxAgeHours = MAX_TLE_AGE_HOURS) {
  // Accept a legacy named preset or an explicit list of individually selected systems.
  // An empty list means no selected satellites, not an implicit GPS fallback.
  const selected = Array.isArray(group) ? group : (GNSS_GROUPS[group] || GNSS_GROUPS.gps);
  const allowed = selected.filter(x => GNSS_GROUPS.all.includes(x));
  if (!allowed.length) return [];
  const date = new Date(at);
  const out = [];
  if (!Number.isFinite(date.getTime())) return out;
  const gmst = satLib.gstime(date);
  for (const s of sats) {
    if (!allowed.includes(s.system) || Math.abs(date.getTime() - s.epoch_ms) > maxAgeHours * 3600000) continue;
    try {
      const state = satLib.propagate(s.satrec, date);
      if (!state?.position || !Number.isFinite(state.position.x)) continue;
      const xyz = satLib.eciToEcf(state.position, gmst);
      if ([xyz.x, xyz.y, xyz.z].every(Number.isFinite))
        out.push({ x: xyz.x, y: xyz.y, z: xyz.z, system: s.system, norad: s.norad });
    } catch (_) { /* bad SGP4 propagation */ }
  }
  return out;
}

/** Gauss-Jordan inverse of the (up to 8x8) normal matrix; null on rank deficiency. */
export function invertMatrix(matrix) {
  const n = matrix?.length;
  if (!Number.isInteger(n) || n < 4 || n > 8 || matrix.some(row => !Array.isArray(row) || row.length !== n)) return null;
  if (matrix.some(row => row.some(v => !Number.isFinite(v)))) return null;
  const a = matrix.map((row, i) => [...row, ...Array.from({ length: n }, (_, j) => i === j ? 1 : 0)]);
  for (let k = 0; k < n; k++) {
    let best = k;
    for (let j = k + 1; j < n; j++) if (Math.abs(a[j][k]) > Math.abs(a[best][k])) best = j;
    if (Math.abs(a[best][k]) < 1e-8) return null;
    [a[k], a[best]] = [a[best], a[k]];
    const pivot = a[k][k];
    for (let j = 0; j < n * 2; j++) a[k][j] /= pivot;
    for (let i = 0; i < n; i++) {
      if (i === k) continue;
      const factor = a[i][k];
      for (let j = 0; j < n * 2; j++) a[i][j] -= factor * a[k][j];
    }
  }
  const inverse = a.map(row => row.slice(n));
  return inverse.every(row => row.every(Number.isFinite)) ? inverse : null;
}
export const invert4 = invertMatrix; // compatible with the previous single-system implementation

/**
 * Weighted least squares of ionosphere-only pseudorange perturbations.
 * For multi-GNSS, estimate one intersystem clock bias per extra constellation;
 * treating separate constellation clocks as one would generate false position bias.
 * All measurements are assigned equal nominal weight (research demonstration).
 */
export function solveIonoAt(cube, frame, satellites, latDeg, lonDeg, elevMask = ELEVATION_MASK_DEG) {
  if (!satellites?.length || !frame || !Number.isFinite(latDeg) || !Number.isFinite(lonDeg)) return null;
  const lat = latDeg * RAD, lon = lonDeg * RAD;
  const cl = Math.cos(lat), sl = Math.sin(lat), co = Math.cos(lon), so = Math.sin(lon);
  const ux = cl * co, uy = cl * so, uz = sl;
  const rx = EARTH_KM * ux, ry = EARTH_KM * uy, rz = EARTH_KM * uz;
  const ex = -so, ey = co;
  const nx = -sl * co, ny = -sl * so, nz = cl;
  const shell = EARTH_KM + SHELL_KM;
  const minimumUp = Math.sin(elevMask * RAD);
  const observed = [];
  let totalDelay = 0;
  for (const sat of satellites) {
    const dx = sat.x - rx, dy = sat.y - ry, dz = sat.z - rz, dist = Math.hypot(dx, dy, dz);
    if (!(dist > 1)) continue;
    const x = dx / dist, y = dy / dist, z = dz / dist;
    const up = x * ux + y * uy + z * uz;
    if (up < minimumUp) continue;
    const east = x * ex + y * ey, north = x * nx + y * ny + z * nz;
    // Intersect straight ray with a spherical thin-shell ionosphere.
    const p = EARTH_KM * up;
    const ray = -p + Math.sqrt(p * p + shell * shell - EARTH_KM * EARTH_KM);
    const xx = rx + ray * x, yy = ry + ray * y, zz = rz + ray * z;
    const vtec = spatial(cube, frame, Math.atan2(zz, Math.hypot(xx, yy)) / RAD,
      Math.atan2(yy, xx) / RAD);
    if (vtec == null || !Number.isFinite(vtec) || vtec < 0) continue;
    const mapping = 1 / Math.sqrt(1 - Math.pow(EARTH_KM / shell, 2) * (1 - up * up));
    // L1-equivalent diagnostic for all systems; not each constellation's actual carrier.
    const delay = METERS_PER_TECU * vtec * mapping;
    totalDelay += delay;
    observed.push({ geom: [-east, -north, -up, 1], system: sat.system || 'gps', delay });
  }
  if (observed.length < 4) return null;
  const systems = [...new Set(observed.map(x => x.system))];
  const reference = systems.includes('gps') ? 'gps' : systems[0];
  const otherSystems = systems.filter(x => x !== reference);
  const n = 4 + otherSystems.length;
  if (observed.length < n) return null;
  const normal = Array.from({ length: n }, () => Array(n).fill(0)), rhs = Array(n).fill(0);
  for (const o of observed) {
    const row = [...o.geom, ...otherSystems.map(sys => sys === o.system ? 1 : 0)];
    for (let i = 0; i < n; i++) {
      rhs[i] += row[i] * o.delay;
      for (let j = 0; j < n; j++) normal[i][j] += row[i] * row[j];
    }
  }
  const inverse = invertMatrix(normal);
  if (!inverse) return null;
  const solution = inverse.map(row => row.reduce((sum, v, i) => sum + v * rhs[i], 0));
  const pdop = Math.sqrt(Math.max(0, inverse[0][0] + inverse[1][1] + inverse[2][2]));
  // ENU-position components; signed Up is retained for debugging, map uses magnitude.
  const [east_m, north_m, up_m] = solution;
  const horizontal_m = Math.hypot(east_m, north_m);
  const vertical_m = Math.abs(up_m);
  const bias = Math.hypot(east_m, north_m, up_m);
  const hdop = Math.sqrt(Math.max(0, inverse[0][0] + inverse[1][1]));
  const vdop = Math.sqrt(Math.max(0, inverse[2][2]));
  if (![pdop,hdop,vdop,bias,horizontal_m,vertical_m].every(Number.isFinite) || pdop > 50) return null;
  return { iono_bias_m: bias, iono_horizontal_m: horizontal_m, iono_vertical_m: vertical_m,
    east_m, north_m, up_m, pdop, hdop, vdop, visible: observed.length,
    systems: systems.length, mean_slant_delay_m: totalDelay / observed.length };
}

/** Calculate current frame only, in browser RAM. No DOP/position time series saved. */
export function buildGnssGrid(cube, frame, satPositions,
  { latStep = 6, lonStep = 6, elevMask = ELEVATION_MASK_DEG } = {}) {
  if (![latStep, lonStep].every(x => Number.isInteger(x) && x >= 2 && x <= 30))
    throw Error('格子間隔は2–30度の整数にしてください');
  const latitudes = [], longitudes = [];
  for (let lat = -72; lat <= 72; lat += latStep) latitudes.push(lat);
  for (let lon = -180; lon < 180; lon += lonStep) longitudes.push(lon);
  const bias = [], biasH = [], biasV = [], dop = [], hdop = [], vdop = [], counts = [];
  let validCount = 0;
  for (const lat of latitudes) for (const lon of longitudes) {
    const found = solveIonoAt(cube, frame, satPositions, lat, lon, elevMask);
    bias.push(found?.iono_bias_m ?? null);
    biasH.push(found?.iono_horizontal_m ?? null);
    biasV.push(found?.iono_vertical_m ?? null);
    dop.push(found?.pdop ?? null);
    hdop.push(found?.hdop ?? null);
    vdop.push(found?.vdop ?? null);
    counts.push(found?.visible ?? 0);
    if (found) validCount++;
  }
  return { latitudes, longitudes, nx: longitudes.length, ny: latitudes.length,
    bias, biasH, biasV, dop, hdop, vdop, counts, validCount, positions: satPositions.length, scale: 1 };
}
