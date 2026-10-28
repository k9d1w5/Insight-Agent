const WEEKDAYS = ['일', '월', '화', '수', '목', '금', '토'];
const state = { data: null, byId: {}, sort: 'score', topic: 'all', query: '' };
const $ = (id) => document.getElementById(id);

function esc(s) {
  return String(s ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
}
function safeUrl(u) {
  return /^https?:\/\//i.test(u || '') ? u : '';
}
function parseDay(s) {
  const [y, m, d] = s.split('-').map(Number);
  return new Date(y, m - 1, d);
}
function fmtDay(s) {
  const d = parseDay(s);
  return `${d.getMonth() + 1}월 ${d.getDate()}일 (${WEEKDAYS[d.getDay()]})`;
}

function growthPill(g) {
  if (g === null || g === undefined) return '<span class="pill flat">표본 적음</span>';
  if (g === 'new') return '<span class="pill new">신규</span>';
  if (g > 0) return `<span class="pill up">▲ ${g}%</span>`;
  if (g < 0) return `<span class="pill down">▼ ${Math.abs(g)}%</span>`;
  return '<span class="pill flat">보합</span>';
}
function growthValue(g) {
  if (g === 'new') return 1000;
  return typeof g === 'number' ? g : -1000;
}

function bars(series, { height = 40, gap = 3 } = {}) {
  const max = Math.max(1, ...series);
  const w = 10;
  const rects = series.map((v, i) => {
    const h = Math.max(1.5, (v / max) * height);
    const last = i === series.length - 1;
    return `<rect x="${i * w + gap / 2}" y="${height - h}" width="${w - gap}" height="${h}" rx="1.5" fill="${last ? 'var(--accent)' : 'var(--bar)'}"/>`;
  }).join('');
  return `<svg viewBox="0 0 ${series.length * w} ${height}" preserveAspectRatio="none" aria-hidden="true">${rects}</svg>`;
}

function chart(series, labels) {
  const W = 480, H = 120, pad = 18;
  const max = Math.max(1, ...series);
  const bw = W / series.length;
  const parts = series.map((v, i) => {
    const h = (v / max) * (H - pad);
    const x = i * bw + bw * 0.18;
    const last = i === series.length - 1;
    const label = i % 2 === series.length % 2 || last ? `<text x="${x + bw * 0.32}" y="${H + 14}" text-anchor="middle">${labels[i]}</text>` : '';
    const val = v ? `<text x="${x + bw * 0.32}" y="${H - h - 5}" text-anchor="middle" style="fill:${last ? 'var(--accent)' : 'var(--text-3)'};font-weight:${last ? 700 : 400}">${v}</text>` : '';
    return `<rect x="${x}" y="${H - h}" width="${bw * 0.64}" height="${Math.max(h, 1.5)}" rx="3" fill="${last ? 'var(--accent)' : 'var(--bar)'}"/>${val}${label}`;
  }).join('');
  return `<svg viewBox="0 0 ${W} ${H + 18}" role="img" aria-label="최근 12주 주간 건수">${parts}</svg>`;
}

function logo(a) {
  if (!a.logo_domain) return '';
  return `<img src="https://www.google.com/s2/favicons?sz=64&domain_url=${encodeURIComponent(a.logo_domain)}" alt="" loading="lazy" onerror="this.remove()">`;
}

function itemHtml(a, { tags = true } = {}) {
  const url = safeUrl(a.url);
  const title = url ? `<a href="${esc(url)}" target="_blank" rel="noopener">${esc(a.title)}</a>` : esc(a.title);
  const tagHtml = tags && a.topics.length
    ? `<div class="item-tags">${a.topics.slice(0, 3).map((t) => state.byId[t]
      ? `<button class="tag" data-open="${t}">${esc(state.byId[t].name)}</button>` : '').join('')}</div>`
    : '';
  const copy = url
    ? `<button class="copy-btn" data-copy="${esc(url)}" aria-label="링크 복사"><svg viewBox="0 0 24 24"><rect x="9" y="9" width="12" height="12" rx="2"/><path d="M5 15V5a2 2 0 0 1 2-2h10"/></svg></button>`
    : '';
  return `<article class="item">
    <div class="item-logo">${logo(a)}</div>
    <div class="item-main">
      <div class="item-src"><span>${esc(a.source)}</span></div>
      <div class="item-title">${title}</div>
      ${a.summary ? `<div class="item-sum">${esc(a.summary)}</div>` : ''}
      ${tagHtml}
    </div>
    ${copy}
  </article>`;
}

function renderHero(d) {
  $('hero-eyebrow').textContent = `${fmtDay(d.week_start).replace(/ \(.\)/, '')} – ${fmtDay(d.date).replace(/ \(.\)/, '')} · IT 트렌드 브리핑`;
  $('hero-date').textContent = fmtDay(d.date).replace(/\((.)\)/, '$1요일');
  const lead = state.byId[d.top[0]];
  $('hero-sub').innerHTML = `이번 주 <b>${d.week_total}건</b>을 <b>${d.source_count}곳</b>에서 모았습니다.`
    + (lead ? ` 가장 주목할 토픽은 <b>${esc(lead.name)}</b>입니다.` : '');
  $('footer-meta').textContent = `${d.generated_at} 생성 · 누적 ${d.history_days}일`;
}

function renderTrends(d) {
  $('trend-grid').innerHTML = d.top.map((id, i) => {
    const t = state.byId[id];
    const head = t.articles[0];
    return `<button class="trend-card" data-open="${t.id}">
      <div class="trend-top"><span class="rank">0${i + 1}</span>${growthPill(t.growth_pct)}</div>
      <div>
        <div class="trend-name">${esc(t.name)}</div>
        <div class="trend-meta">이번 주 ${t.count}건 · 출처 ${t.spread}곳</div>
      </div>
      <div class="trend-spark">${bars(t.series, { height: 52 })}</div>
      <div class="kw">${t.keywords.slice(0, 4).map((k) => `<span>${esc(k)}</span>`).join('')}</div>
      ${head ? `<div class="trend-head"><div class="trend-head-title">${esc(head.title)}</div><div class="trend-head-src">${esc(head.source)}${t.count > 1 ? ` 외 ${t.count - 1}건` : ''}</div></div>` : ''}
    </button>`;
  }).join('');

  if (d.new_keywords?.length) {
    $('newkw-list').innerHTML = d.new_keywords.map((k) => `<span>${esc(k)}</span>`).join('');
    $('newkw').classList.remove('hidden');
  }
}

function renderTopics() {
  const topics = [...state.data.topics];
  if (state.sort === 'count') topics.sort((a, b) => b.count - a.count);
  if (state.sort === 'growth') topics.sort((a, b) => growthValue(b.growth_pct) - growthValue(a.growth_pct) || b.count - a.count);
  const max = Math.max(1, ...topics.map((t) => t.count));
  $('topic-table').innerHTML = topics.map((t) => `
    <button class="topic-row${t.count ? '' : ' muted'}" data-open="${t.id}">
      <span class="topic-name">${esc(t.name)}<small>${t.count}건</small></span>
      <span class="topic-bar"><span class="topic-bar-track"><span class="topic-bar-fill" style="width:${(t.count / max) * 100}%"></span></span><span class="topic-bar-num">${t.count}</span></span>
      <span class="topic-growth">${t.count ? growthPill(t.growth_pct) : ''}</span>
      <span class="topic-spark">${bars(t.series, { height: 26, gap: 4 })}</span>
      <svg class="chev" viewBox="0 0 24 24" aria-hidden="true"><path d="m9 6 6 6-6 6"/></svg>
    </button>`).join('');
}

function renderChips() {
  const topics = state.data.topics.filter((t) => t.count).sort((a, b) => b.count - a.count);
  $('feed-chips').innerHTML = [`<button class="chip${state.topic === 'all' ? ' active' : ''}" data-topic="all">전체<small>${state.data.feed.length}</small></button>`]
    .concat(topics.map((t) => `<button class="chip${state.topic === t.id ? ' active' : ''}" data-topic="${t.id}">${esc(t.name)}<small>${t.count}</small></button>`))
    .join('');
}

function renderFeed() {
  const q = state.query.trim().toLowerCase();
  const items = state.data.feed.filter((a) =>
    (state.topic === 'all' || a.topics.includes(state.topic))
    && (!q || `${a.title} ${a.summary} ${a.source}`.toLowerCase().includes(q)));
  $('feed-count').textContent = `${items.length}건`;
  if (!items.length) {
    $('feed-list').innerHTML = '<div class="empty">조건에 맞는 아티클이 없습니다.</div>';
    return;
  }
  const ref = parseDay(state.data.date);
  const groups = new Map();
  items.forEach((a) => {
    if (!groups.has(a.date)) groups.set(a.date, []);
    groups.get(a.date).push(a);
  });
  $('feed-list').innerHTML = [...groups].map(([day, list]) => {
    const diff = Math.round((ref - parseDay(day)) / 86400000);
    const label = diff === 0 ? '오늘' : diff === 1 ? '어제' : fmtDay(day);
    return `<div class="day-group"><div class="day-label">${label} · ${list.length}</div><div class="day-list">${list.map((a) => itemHtml(a)).join('')}</div></div>`;
  }).join('');
}

function openTopic(id, { push = true } = {}) {
  const t = state.byId[id];
  if (!t) return;
  const g = t.growth_pct;
  const gText = g === null ? '–' : g === 'new' ? '신규' : `${g > 0 ? '+' : ''}${g}%`;
  const gCls = g === 'new' ? 'new' : typeof g === 'number' ? (g > 0 ? 'up' : g < 0 ? 'down' : '') : '';
  $('drawer-title').textContent = t.name;
  $('drawer-body').innerHTML = `
    <div class="stats">
      <div class="stat"><div class="stat-label">이번 주</div><div class="stat-val">${t.count}건</div></div>
      <div class="stat"><div class="stat-label">4주 평균</div><div class="stat-val">${t.baseline_avg}건</div></div>
      <div class="stat"><div class="stat-label">증감</div><div class="stat-val ${gCls}">${gText}</div></div>
    </div>
    <div class="d-section"><div class="d-title">최근 12주 추이</div><div class="chart">${chart(t.series, state.data.series_labels)}</div></div>
    ${t.keywords.length ? `<div class="d-section"><div class="d-title">자주 나온 키워드</div><div class="kw">${t.keywords.map((k) => `<span>${esc(k)}</span>`).join('')}</div></div>` : ''}
    ${t.sources.length ? `<div class="d-section"><div class="d-title">다룬 출처 ${t.sources.length}곳</div><div class="kw">${t.sources.map((s) => `<span>${esc(s)}</span>`).join('')}</div></div>` : ''}
    <div class="d-section"><div class="d-title">이번 주 아티클</div>
      ${t.articles.length ? `<div class="d-list">${t.articles.map((a) => itemHtml(a, { tags: false })).join('')}</div>` : '<div class="empty">이번 주에는 다룬 아티클이 없습니다.</div>'}
    </div>`;
  $('drawer-body').scrollTop = 0;
  const backdrop = $('drawer-backdrop');
  backdrop.hidden = false;
  requestAnimationFrame(() => {
    backdrop.classList.add('open');
    $('drawer').classList.add('open');
  });
  $('drawer').setAttribute('aria-hidden', 'false');
  document.body.style.overflow = 'hidden';
  $('drawer-close').focus({ preventScroll: true });
  if (push) history.replaceState(null, '', `#t=${id}`);
}

function closeTopic() {
  const backdrop = $('drawer-backdrop');
  backdrop.classList.remove('open');
  $('drawer').classList.remove('open');
  $('drawer').setAttribute('aria-hidden', 'true');
  document.body.style.overflow = '';
  setTimeout(() => { backdrop.hidden = true; }, 250);
  if (location.hash.startsWith('#t=')) history.replaceState(null, '', location.pathname);
}

let toastTimer;
function toast(msg) {
  const el = $('toast');
  el.textContent = msg;
  el.classList.add('show');
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => el.classList.remove('show'), 1800);
}

function bindEvents() {
  document.addEventListener('click', (e) => {
    const copy = e.target.closest('[data-copy]');
    if (copy) {
      e.preventDefault();
      navigator.clipboard?.writeText(copy.dataset.copy).then(() => toast('링크를 복사했습니다'), () => toast('복사하지 못했습니다'));
      return;
    }
    const open = e.target.closest('[data-open]');
    if (open) { e.preventDefault(); openTopic(open.dataset.open); return; }
    const chip = e.target.closest('[data-topic]');
    if (chip) { state.topic = chip.dataset.topic; renderChips(); renderFeed(); return; }
    const seg = e.target.closest('[data-sort]');
    if (seg) {
      state.sort = seg.dataset.sort;
      document.querySelectorAll('.seg-btn').forEach((b) => {
        const on = b === seg;
        b.classList.toggle('active', on);
        b.setAttribute('aria-selected', on);
      });
      renderTopics();
    }
  });
  $('drawer-close').addEventListener('click', closeTopic);
  $('drawer-backdrop').addEventListener('click', closeTopic);
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape' && $('drawer').classList.contains('open')) closeTopic();
    if (e.key === '/' && document.activeElement !== $('search')) { e.preventDefault(); $('search').focus(); }
  });
  let t;
  $('search').addEventListener('input', (e) => {
    clearTimeout(t);
    t = setTimeout(() => { state.query = e.target.value; renderFeed(); }, 120);
  });
  $('theme-btn').addEventListener('click', () => {
    const root = document.documentElement;
    const dark = root.dataset.theme ? root.dataset.theme === 'dark' : matchMedia('(prefers-color-scheme: dark)').matches;
    root.dataset.theme = dark ? 'light' : 'dark';
    try { localStorage.setItem('v2-theme', root.dataset.theme); } catch {}
  });
  const bar = document.querySelector('.topbar');
  addEventListener('scroll', () => bar.classList.toggle('scrolled', scrollY > 8), { passive: true });
}

async function init() {
  bindEvents();
  try {
    const res = await fetch(`/data/trends.json?t=${Date.now()}`);
    if (!res.ok) throw new Error(res.status);
    state.data = await res.json();
  } catch {
    $('hero-date').textContent = '데이터를 불러오지 못했습니다';
    $('hero-sub').textContent = '잠시 후 새로고침해 주세요.';
    $('trend-grid').innerHTML = '';
    return;
  }
  state.data.topics.forEach((t) => { state.byId[t.id] = t; });
  renderHero(state.data);
  renderTrends(state.data);
  renderTopics();
  renderChips();
  renderFeed();
  const m = location.hash.match(/^#t=([\w-]+)/);
  if (m) openTopic(m[1], { push: false });
}

init();
