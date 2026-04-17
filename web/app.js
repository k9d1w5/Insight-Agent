/* app.js - IT 인사이트 리포트 대시보드 */

const CAT_COLORS = {
  '글로벌 컨설팅': '#7c3aed',
  '국내 연구기관': '#0891b2',
  '한국 대기업':   '#0284c7',
  '플랫폼 테크':   '#059669',
  'IT 미디어':     '#d97706',
};

let allArticles = [];
let allSources  = [];

// ── 데이터 로드 ──────────────────────────────────────────
async function loadReport(file = 'data/reports/latest.json') {
  try {
    const res = await fetch(file + '?t=' + Date.now());
    if (!res.ok) throw new Error('not found');
    return await res.json();
  } catch {
    return null;
  }
}

async function loadIndex() {
  try {
    const res = await fetch('data/reports/index.json?t=' + Date.now());
    if (!res.ok) return null;
    return await res.json();
  } catch {
    return null;
  }
}

async function loadSources() {
  try {
    const res = await fetch('data/sources.json?t=' + Date.now());
    if (!res.ok) return null;
    return await res.json();
  } catch {
    return null;
  }
}

// ── 렌더링 ───────────────────────────────────────────────
function renderReport(data) {
  document.getElementById('report-date').textContent = data.date || '-';
  document.getElementById('stat-articles').textContent = data.total_articles ?? '-';
  const sources = [...new Set((data.articles || []).map(a => a.source))];
  document.getElementById('stat-sources').textContent = sources.length;
  document.getElementById('stat-categories').textContent = Object.keys(data.categories || {}).length;
  document.getElementById('final-report').innerHTML = markdownToHtml(data.final_report || '리포트가 없습니다.');

  // 실제 데이터면 샘플 배너 숨김
  const notice = document.getElementById('demo-notice');
  if (notice) {
    const today = new Date().toISOString().slice(0, 10);
    const isRealData = data.articles && data.articles.length > 0 &&
      data.articles.some(a => a.url && !a.url.includes('mckinsey.com/capabilities'));
    if (isRealData || data.date === today) notice.style.display = 'none';
  }
  allArticles = data.articles || [];
  renderArticles(allArticles);
}

function renderArticles(articles) {
  const grid = document.getElementById('articles-grid');
  const countBadge = document.getElementById('article-count');
  grid.innerHTML = '';
  if (countBadge) countBadge.textContent = `${articles.length}개 아티클`;

  if (!articles.length) {
    grid.innerHTML = '<p style="color:var(--text-sm);padding:20px;font-size:13px">해당 카테고리의 아티클이 없습니다.</p>';
    return;
  }

  articles.forEach(a => {
    const color = CAT_COLORS[a.category] || '#2563eb';
    const card = document.createElement('div');
    card.className = 'article-card';

    const dateStr = a.published ? a.published.slice(0, 10) : '';
    const hasLink = !!a.url;

    const titleHtml = hasLink
      ? `<a href="${esc(a.url)}" target="_blank" rel="noopener">${esc(a.title)}</a>`
      : esc(a.title);

    const logoHtml = a.logo_domain
      ? `<img class="source-logo" src="https://www.google.com/s2/favicons?sz=32&domain_url=${esc(a.logo_domain)}" alt="" onerror="this.style.display='none'">`
      : '';

    card.innerHTML = `
      <div class="article-card-top" style="background:${color}"></div>
      <div class="article-card-body">
        <div class="article-meta">
          <span class="cat-badge" style="background:${color}">${esc(a.category)}</span>
          ${logoHtml}
          <span class="source-chip">${esc(a.source)}</span>
          ${dateStr ? `<span class="article-date">${dateStr}</span>` : ''}
        </div>
        <div class="article-title">${titleHtml}</div>
        ${a.summary ? `<div class="article-original">${esc(a.summary.slice(0, 200))}</div>` : ''}
        ${a.ai_summary ? `
          <div class="article-ai-box">
            <div class="ai-label">AI 요약</div>
            <div class="article-ai-text">${esc(a.ai_summary)}</div>
          </div>` : ''}
        ${hasLink ? `
          <div class="article-link-row">
            <a class="article-link" href="${esc(a.url)}" target="_blank" rel="noopener">원문 보기 →</a>
          </div>` : ''}
      </div>
    `;
    grid.appendChild(card);
  });
}

async function renderArchive() {
  const index = await loadIndex();
  const list = document.getElementById('archive-list');
  if (!index || !index.reports || index.reports.length <= 1) return;

  const past = index.reports.slice(1);
  list.innerHTML = past.map(r => {
    const d = new Date(r.date);
    const day = d.getDate();
    const month = d.toLocaleDateString('ko-KR', { month: 'long' });
    const cats = Object.entries(r.categories || {})
      .map(([k, v]) => `<span class="archive-cat-chip">${k} ${v}</span>`).join('');
    return `
      <div class="archive-item" data-file="data/reports/${r.file}">
        <div><div class="archive-date-num">${day}</div><div class="archive-date-month">${month}</div></div>
        <div class="archive-divider"></div>
        <div class="archive-info">
          <div class="archive-date-full">${r.date}</div>
          <div class="archive-cats">${cats}</div>
        </div>
        <div class="archive-count">아티클 ${r.total_articles}개</div>
        <div class="archive-arrow">›</div>
      </div>`;
  }).join('');

  list.querySelectorAll('.archive-item').forEach(el => {
    el.addEventListener('click', async () => {
      showLoading();
      const data = await loadReport(el.dataset.file);
      if (data) { renderReport(data); showContent(); window.scrollTo({ top: 0, behavior: 'smooth' }); }
    });
  });
}

// ── 소스 현황 탭 ─────────────────────────────────────────
function renderSources(sourcesData, filterCat = 'all') {
  const grid = document.getElementById('sources-grid');
  const totalEl = document.getElementById('sources-total');
  if (!grid || !sourcesData) return;

  const sources = filterCat === 'all'
    ? sourcesData.sources
    : sourcesData.sources.filter(s => s.category === filterCat);

  if (totalEl) totalEl.textContent = sourcesData.total;
  grid.innerHTML = '';

  // 카테고리별로 그룹핑
  const groups = {};
  sources.forEach(s => {
    if (!groups[s.category]) groups[s.category] = [];
    groups[s.category].push(s);
  });

  Object.entries(groups).forEach(([cat, items]) => {
    const color = CAT_COLORS[cat] || '#2563eb';
    const groupEl = document.createElement('div');
    groupEl.className = 'sources-group';
    groupEl.innerHTML = `
      <div class="sources-group-title" style="border-left-color:${color}">
        <span class="sources-group-dot" style="background:${color}"></span>
        ${esc(cat)} <span class="sources-group-count">${items.length}개</span>
      </div>
      <div class="sources-group-grid">
        ${items.map(s => {
          const logoUrl = `https://www.google.com/s2/favicons?sz=64&domain_url=${esc(s.logo_domain)}`;
          const typeLabel = { web: 'WEB', pdf: 'PDF', web_pdf: 'WEB+PDF', rss: 'RSS' }[s.type] || s.type.toUpperCase();
          const typeBg = { web: '#eff6ff', pdf: '#fef3c7', web_pdf: '#f0fdf4', rss: '#fdf4ff' }[s.type] || '#f1f5f9';
          const typeColor = { web: '#1d4ed8', pdf: '#d97706', web_pdf: '#059669', rss: '#7c3aed' }[s.type] || '#475569';
          return `
          <a class="source-card" href="${esc(s.url)}" target="_blank" rel="noopener">
            <div class="source-card-accent" style="background:${color}"></div>
            <div class="source-card-body">
              <div class="source-card-logo-wrap">
                <img class="source-card-logo"
                     src="${logoUrl}"
                     alt="${esc(s.name_ko)}"
                     onerror="this.src='data:image/svg+xml,<svg xmlns=%22http://www.w3.org/2000/svg%22 viewBox=%220 0 32 32%22><rect width=%2232%22 height=%2232%22 rx=%224%22 fill=%22%23e2e8f0%22/><text x=%2216%22 y=%2221%22 text-anchor=%22middle%22 font-size=%2214%22 fill=%22%2394a3b8%22>📄</text></svg>'">
              </div>
              <div class="source-card-info">
                <div class="source-card-name">${esc(s.name_ko)}</div>
                <div class="source-card-en">${esc(s.name)}</div>
                <div class="source-card-desc">${esc(s.description)}</div>
              </div>
              <div class="source-card-type" style="background:${typeBg};color:${typeColor}">${typeLabel}</div>
            </div>
            <div class="source-card-url">${esc(s.url)}</div>
          </a>`;
        }).join('')}
      </div>
    `;
    grid.appendChild(groupEl);
  });
}

// ── 탭 전환 ──────────────────────────────────────────────
function switchTab(tabName) {
  const mainEl   = document.querySelector('main');
  const sourceEl = document.getElementById('tab-sources');
  const hero     = document.querySelector('.hero');

  document.querySelectorAll('.nav-btn').forEach(b => b.classList.remove('active'));
  document.querySelector(`.nav-btn[data-tab="${tabName}"]`)?.classList.add('active');

  if (tabName === 'sources') {
    mainEl.classList.add('hidden');
    sourceEl.classList.remove('hidden');
    if (hero) hero.style.display = 'none';
    // 소스 렌더
    if (allSources) renderSources(allSources);
  } else {
    mainEl.classList.remove('hidden');
    sourceEl.classList.add('hidden');
    if (hero) hero.style.display = '';
  }
}

// ── 필터 (아티클 + 소스 공용) ─────────────────────────────
document.addEventListener('click', e => {
  // 아티클 필터
  if (e.target.matches('.filter-btn[data-cat]')) {
    document.querySelectorAll('.filter-btn[data-cat]').forEach(b => b.classList.remove('active'));
    e.target.classList.add('active');
    const cat = e.target.dataset.cat;
    renderArticles(cat === 'all' ? allArticles : allArticles.filter(a => a.category === cat));
    return;
  }
  // 소스 필터
  if (e.target.matches('.filter-btn[data-scat]')) {
    document.querySelectorAll('.filter-btn[data-scat]').forEach(b => b.classList.remove('active'));
    e.target.classList.add('active');
    renderSources(allSources, e.target.dataset.scat);
    return;
  }
  // 탭 버튼
  if (e.target.matches('.nav-btn[data-tab]')) {
    switchTab(e.target.dataset.tab);
  }
});

// ── 마크다운 변환 ────────────────────────────────────────
function markdownToHtml(text) {
  return text
    .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
    .replace(/^# (.+)$/gm,   '<h1>$1</h1>')
    .replace(/^## (.+)$/gm,  '<h2>$1</h2>')
    .replace(/^### (.+)$/gm, '<h3>$1</h3>')
    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
    .replace(/^- (.+)$/gm,   '<li>$1</li>')
    .replace(/((?:<li>.*<\/li>\n?)+)/g, '<ul>$1</ul>')
    .replace(/^---$/gm, '<hr>')
    .replace(/\n{2,}/g, '<br><br>')
    .replace(/\n/g, '<br>');
}

function esc(str) {
  return (str || '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}

function showLoading() {
  document.getElementById('loading').classList.remove('hidden');
  document.getElementById('content').classList.add('hidden');
  document.getElementById('error').classList.add('hidden');
}
function showContent() {
  document.getElementById('loading').classList.add('hidden');
  document.getElementById('content').classList.remove('hidden');
  document.getElementById('error').classList.add('hidden');
}
function showError() {
  document.getElementById('loading').classList.add('hidden');
  document.getElementById('content').classList.add('hidden');
  document.getElementById('error').classList.remove('hidden');
}

(async function init() {
  // 소스 데이터는 항상 미리 로드
  const sourcesData = await loadSources();
  if (sourcesData) allSources = sourcesData;

  showLoading();
  const data = await loadReport();
  if (!data) { showError(); return; }
  renderReport(data);
  await renderArchive();
  showContent();
})();
