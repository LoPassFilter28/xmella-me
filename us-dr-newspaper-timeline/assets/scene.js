import * as THREE from './vendor/three.module.js';

/**
 * A landscape of the surviving newspaper record, with one equally spaced station
 * per calendar year. Each stack is an aggregate: its height is log(1 + count).
 * A sheet is NOT an article. Zero records always means zero sheets.
 * Text, exact counts and navigation remain in the accessible HTML surrounding it.
 */
export async function createTimelineScene({ canvas, years, year = 1820, theme = 'light', onFallback = () => {} }) {
  const noop = { setYear() {}, setTheme() {}, dispose() {} };
  const reduced = window.matchMedia('(prefers-reduced-motion: reduce)');
  if (reduced.matches || (navigator.deviceMemory && navigator.deviceMemory <= 2) || navigator.connection?.saveData) {
    canvas.dataset.mode = 'static';
    onFallback();
    return noop;
  }

  const countByYear = new Map(years.map(item => [Number(item.year), Math.max(0, Number(item.count) || 0)]));
  const first = Math.min(...countByYear.keys());
  const last = Math.max(...countByYear.keys());
  const clampYear = value => Math.min(last, Math.max(first, Number(value) || first));
  const STEP = 1.62;
  const RADIUS = 11;
  const CAPACITY = 1000;
  const PAPER = 0xF7F1E3;
  const WALNUT = 0x4A2E20;
  const TERRA = 0xB8602F;
  let renderer;
  try {
    renderer = new THREE.WebGLRenderer({ canvas, alpha: true, antialias: false, powerPreference: 'low-power' });
    renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 1.5));
    renderer.setClearColor(0x000000, 0);
    renderer.outputColorSpace = THREE.SRGBColorSpace;
  } catch {
    canvas.dataset.mode = 'static';
    onFallback();
    return noop;
  }

  const scene = new THREE.Scene();
  const camera = new THREE.PerspectiveCamera(35, 1, 0.1, 130);
  const geometry = new THREE.BoxGeometry(1.16, 0.035, 2.36);
  // White is only a neutral multiplier: the instance colors supply the palette.
  const material = new THREE.MeshBasicMaterial({ color: 0xffffff });
  const sheets = new THREE.InstancedMesh(geometry, material, CAPACITY);
  sheets.instanceMatrix.setUsage(THREE.DynamicDrawUsage);
  sheets.frustumCulled = false;
  scene.add(sheets);

  // A quiet ruled floor preserves year spacing even where the record disappears.
  const rulesGeometry = new THREE.BufferGeometry();
  const rulePositions = new Float32Array((RADIUS * 2 + 1) * 6);
  rulesGeometry.setAttribute('position', new THREE.BufferAttribute(rulePositions, 3).setUsage(THREE.DynamicDrawUsage));
  const ruleMaterial = new THREE.LineBasicMaterial({ color: PAPER, transparent: true, opacity: 0.15 });
  const rules = new THREE.LineSegments(rulesGeometry, ruleMaterial);
  rules.frustumCulled = false;
  scene.add(rules);
  const spineGeometry = new THREE.BufferGeometry();
  const spinePositions = new Float32Array(RADIUS * 2 * 6);
  spineGeometry.setAttribute('position', new THREE.BufferAttribute(spinePositions, 3).setUsage(THREE.DynamicDrawUsage));
  const spineMaterial = new THREE.LineBasicMaterial({ color: TERRA, transparent: true, opacity: 0.8 });
  const spine = new THREE.LineSegments(spineGeometry, spineMaterial);
  spine.frustumCulled = false;
  scene.add(spine);

  const dummy = new THREE.Object3D();
  const color = new THREE.Color();
  const paperColor = new THREE.Color(PAPER);
  const accentColor = new THREE.Color(TERRA);
  const darkColor = new THREE.Color(WALNUT);
  let selected = clampYear(year);
  let focus = selected;
  let paintedCenter = NaN;
  let paintedSelection = NaN;
  let frame = 0;
  let disposed = false;
  let previousTime = 0;
  let width = 0;
  let height = 0;
  let frameSamples = [];
  let hasRendered = false;

  function fillWindow(center) {
    const low = Math.max(first, center - RADIUS);
    const high = Math.min(last, center + RADIUS);
    const marks = [];
    const baseline = [];
    let index = 0;
    for (let current = low; current <= high; current++) {
      const x = (current - first) * STEP;
      marks.push(x, -0.04, -2.6, x, -0.04, 3.2);
      // The spine tracks time continuously, never implying continuous coverage.
      if (current < high) baseline.push(x, -0.04, 2.9, x + STEP, -0.04, 2.9);
      const count = countByYear.get(current) || 0;
      if (!count) continue;
      const density = Math.log1p(count);
      const layers = Math.min(40, Math.max(1, Math.round(density * 6)));
      const stackHeight = 0.13 + density * 0.66;
      for (let layer = 0; layer < layers && index < CAPACITY; layer++) {
        const progress = layers === 1 ? 0 : layer / (layers - 1);
        // The fan opens with increasing density; it does not rotate for decoration.
        const fan = progress * Math.min(0.14, density * 0.024);
        dummy.position.set(x + progress * 0.12, 0.08 + progress * stackHeight, progress * -0.34);
        dummy.rotation.set(0, fan, -0.035 - progress * 0.035);
        dummy.scale.set(1, 1, 1);
        dummy.updateMatrix();
        sheets.setMatrixAt(index, dummy.matrix);
        const active = current === Math.round(selected);
        color.copy(active || layer === 0 ? accentColor : paperColor);
        const distance = Math.abs(current - center);
        color.lerp(darkColor, Math.min(0.80, distance * 0.055));
        sheets.setColorAt(index, color);
        index++;
      }
    }
    sheets.count = index;
    sheets.instanceMatrix.needsUpdate = true;
    if (sheets.instanceColor) sheets.instanceColor.needsUpdate = true;
    // Reuse GPU buffers while moving, rather than allocating one per year.
    rulePositions.set(marks);
    spinePositions.set(baseline);
    rulesGeometry.setDrawRange(0, marks.length / 3);
    spineGeometry.setDrawRange(0, baseline.length / 3);
    rulesGeometry.attributes.position.needsUpdate = true;
    spineGeometry.attributes.position.needsUpdate = true;
    paintedCenter = center;
    paintedSelection = Math.round(selected);
    canvas.dataset.sheets = String(index);
    canvas.dataset.year = String(Math.round(selected));
    canvas.dataset.count = String(countByYear.get(Math.round(selected)) || 0);
  }

  function placeCamera() {
    const x = (focus - first) * STEP;
    const narrow = width < 600;
    // More height on a phone leaves the exact year/count in the HTML foreground.
    camera.position.set(x + (narrow ? 3.7 : 5.5), narrow ? 8.4 : 7.8, narrow ? 15.8 : 14.6);
    camera.lookAt(x + (narrow ? 0.0 : 0.9), 1.15, -0.15);
  }

  function render(now, initial = false) {
    frame = 0;
    if (disposed || (document.hidden && !initial)) return;
    const start = performance.now();
    const elapsed = previousTime ? Math.min(64, now - previousTime) : 16;
    previousTime = now;
    const delta = selected - focus;
    focus += delta * (1 - Math.exp(-elapsed / 115));
    if (Math.abs(delta) < 0.003) focus = selected;
    const center = Math.round(focus);
    if (center !== paintedCenter || paintedSelection !== Math.round(selected)) fillWindow(center);
    placeCamera();
    try {
      renderer.render(scene, camera);
      canvas.dataset.drawcalls = String(renderer.info.render.calls);
      canvas.dataset.mode = 'three';
      hasRendered = true;
    } catch {
      fail();
      return;
    }
    // Only sustained expensive rendering triggers a fallback; idle time is ignored.
    frameSamples.push(performance.now() - start);
    if (frameSamples.length > 30) frameSamples.shift();
    if (frameSamples.length === 30 && frameSamples.reduce((a, b) => a + b, 0) / 30 > 38) {
      fail();
      return;
    }
    if (focus !== selected) frame = requestAnimationFrame(render);
  }

  function invalidate() {
    if (!disposed && !document.hidden && !frame) frame = requestAnimationFrame(render);
  }

  function resize() {
    if (disposed) return;
    const box = canvas.getBoundingClientRect();
    const nextWidth = Math.max(1, Math.round(box.width));
    const nextHeight = Math.max(1, Math.round(box.height));
    if (nextWidth === width && nextHeight === height && hasRendered) return;
    width = nextWidth;
    height = nextHeight;
    renderer.setSize(width, height, false);
    camera.aspect = width / height;
    camera.updateProjectionMatrix();
    invalidate();
  }

  function setTheme(nextTheme) {
    theme = nextTheme;
    paperColor.set(theme === 'dark' ? 0xF3E7D3 : PAPER);
    accentColor.set(theme === 'dark' ? 0xE59A63 : TERRA);
    darkColor.set(theme === 'dark' ? 0x170C04 : WALNUT);
    ruleMaterial.color.copy(paperColor);
    spineMaterial.color.copy(accentColor);
    paintedCenter = NaN;
    invalidate();
  }

  function visibilityChanged() {
    previousTime = 0;
    if (document.hidden) {
      cancelAnimationFrame(frame);
      frame = 0;
    } else invalidate();
  }

  function contextLost(event) {
    event.preventDefault();
    fail();
  }

  function motionChanged(event) {
    if (event.matches) fail();
  }

  function dispose() {
    if (disposed) return;
    disposed = true;
    cancelAnimationFrame(frame);
    frame = 0;
    canvas.dataset.mode = 'static';
    observer.disconnect();
    document.removeEventListener('visibilitychange', visibilityChanged);
    canvas.removeEventListener('webglcontextlost', contextLost);
    reduced.removeEventListener('change', motionChanged);
    geometry.dispose();
    material.dispose();
    rulesGeometry.dispose();
    ruleMaterial.dispose();
    spineGeometry.dispose();
    spineMaterial.dispose();
    // Clear the final frame too; the host also hides the inactive canvas.
    try { renderer.clear(); } catch { /* The context may already be lost. */ }
    renderer.dispose();
  }

  function fail() {
    dispose();
    canvas.dataset.mode = 'static';
    onFallback();
  }

  const observer = new ResizeObserver(resize);
  observer.observe(canvas);
  document.addEventListener('visibilitychange', visibilityChanged);
  canvas.addEventListener('webglcontextlost', contextLost);
  reduced.addEventListener('change', motionChanged);
  canvas.setAttribute('aria-hidden', 'true');
  setTheme(theme);
  resize();
  // The caller uses mode="three" as a readiness contract. Complete the first
  // draw before resolving, including if the tab hides while the module loads.
  cancelAnimationFrame(frame);
  frame = 0;
  render(performance.now(), true);
  if (disposed) return noop;

  return {
    setYear(nextYear) {
      if (disposed) return;
      selected = clampYear(nextYear);
      invalidate();
    },
    setTheme,
    dispose
  };
}
