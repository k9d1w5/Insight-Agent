/* app.js - IT 인사이트 리포트 대시보드 */

const CAT_COLORS = {
  '글로벌 컨설팅': '#7c3aed',
  '한국 대기업':   '#0284c7',
  '플랫폼 테크':   '#059669',
  'IT 미디어':     '#d97706',
};

let allArticles = [];

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

// ── 렌더링 ───────────────────────────────────────────────
function renderReport(data) {
  document.getElementById('report-date').textContent = data.date || '-';
  document.getElementById('stat-articles').textContent = data.total_articles ?? '-';
  const sources = [...new Set((data.articles || []).map(a => a.source))];
  document.getElementById('stat-sources').textContent = sources.length;
  document.getElementById('stat-categories').textContent = Object.keys(data.categories || {}).length;
  document.getElementById('final-report').innerHTML = markdownToHtml(data.final_report || '리포트가 없습니다.');
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

// ── 필터 ────────────────────────────────────────────────
document.addEventListener('click', e => {
  if (!e.target.matches('.filter-btn')) return;
  document.querySelectorAll('.filter-btn').forEach(b => b.classList.remove('active'));
  e.target.classList.add('active');
  const cat = e.target.dataset.cat;
  renderArticles(cat === 'all' ? allArticles : allArticles.filter(a => a.category === cat));
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
  showLoading();
  const data = await loadReport();
  if (!data) { showError(); return; }
  renderReport(data);
  await renderArchive();
  showContent();
})();
