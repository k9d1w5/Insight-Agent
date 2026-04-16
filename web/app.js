/* app.js - IT 인사이트 리포트 대시보드 */

const CAT_COLORS = {
  '글로벌 컨설팅': '#6d28d9',
  '한국 대기업':   '#0891b2',
  '플랫폼 테크':   '#059669',
  'IT 미디어':     '#d97706',
};

let allArticles = [];

// ── 데이터 로드 ──────────────────────────────────────────
async function loadReport(file = 'data/reports/latest.json') {
  try {
    const res = await fetch(file + '?t=' + Date.now());
    if (!res.ok) throw new Error('fetch failed');
    return await res.json();
  } catch (e) {
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
  // 날짜
  document.getElementById('report-date').textContent = data.date || '-';

  // 통계
  document.getElementById('stat-articles').textContent = data.total_articles ?? '-';
  const sources = [...new Set((data.articles || []).map(a => a.source))];
  document.getElementById('stat-sources').textContent = sources.length;
  const cats = Object.keys(data.categories || {});
  document.getElementById('stat-categories').textContent = cats.length;

  // 종합 리포트 (마크다운 간단 변환)
  const reportEl = document.getElementById('final-report');
  reportEl.innerHTML = markdownToHtml(data.final_report || '리포트가 없습니다.');

  // 아티클
  allArticles = data.articles || [];
  renderArticles(allArticles);
}

function renderArticles(articles) {
  const grid = document.getElementById('articles-grid');
  grid.innerHTML = '';

  if (!articles.length) {
    grid.innerHTML = '<p style="color:var(--muted);padding:20px">해당 카테고리의 아티클이 없습니다.</p>';
    return;
  }

  articles.forEach(a => {
    const color = CAT_COLORS[a.category] || '#2563eb';
    const card = document.createElement('div');
    card.className = 'article-card';
    card.style.setProperty('--cat-color', color);

    const titleEl = a.url
      ? `<a href="${a.url}" target="_blank" rel="noopener">${esc(a.title)}</a>`
      : esc(a.title);

    const dateStr = a.published ? a.published.slice(0, 10) : '';

    card.innerHTML = `
      <div class="article-meta">
        <span class="cat-badge">${esc(a.category)}</span>
        <span class="source-name">${esc(a.source)}</span>
        ${dateStr ? `<span class="article-date">${dateStr}</span>` : ''}
      </div>
      <div class="article-title">${titleEl}</div>
      ${a.summary ? `<div class="article-summary">${esc(a.summary.slice(0, 160))}${a.summary.length > 160 ? '...' : ''}</div>` : ''}
      ${a.ai_summary ? `<div class="article-ai">${esc(a.ai_summary)}</div>` : ''}
    `;
    grid.appendChild(card);
  });
}

async function renderArchive() {
  const index = await loadIndex();
  const list = document.getElementById('archive-list');

  if (!index || !index.reports || index.reports.length <= 1) {
    list.innerHTML = '<p style="color:var(--muted);font-size:13px">아직 과거 리포트가 없습니다.</p>';
    return;
  }

  // 오늘 제외한 과거 목록
  const past = index.reports.slice(1);
  list.innerHTML = past.map(r => `
    <a class="archive-item" href="#" data-file="data/reports/${r.file}">
      <span class="archive-date">${r.date}</span>
      <span class="archive-count">아티클 ${r.total_articles}개</span>
      <span class="archive-arrow">→</span>
    </a>
  `).join('');

  list.querySelectorAll('.archive-item').forEach(el => {
    el.addEventListener('click', async e => {
      e.preventDefault();
      showLoading();
      const data = await loadReport(el.dataset.file);
      if (data) {
        renderReport(data);
        showContent();
        window.scrollTo({ top: 0, behavior: 'smooth' });
      }
    });
  });
}

// ── 필터 ────────────────────────────────────────────────
document.addEventListener('click', e => {
  if (!e.target.matches('.filter-btn')) return;
  document.querySelectorAll('.filter-btn').forEach(b => b.classList.remove('active'));
  e.target.classList.add('active');

  const cat = e.target.dataset.cat;
  const filtered = cat === 'all' ? allArticles : allArticles.filter(a => a.category === cat);
  renderArticles(filtered);
});

// ── 유틸 ────────────────────────────────────────────────
function esc(str) {
  return (str || '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
}

function markdownToHtml(text) {
  return text
    .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
    .replace(/^# (.+)$/gm, '<h1>$1</h1>')
    .replace(/^## (.+)$/gm, '<h2>$1</h2>')
    .replace(/^### (.+)$/gm, '<h3>$1</h3>')
    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
    .replace(/\*(.+?)\*/g, '<em>$1</em>')
    .replace(/^- (.+)$/gm, '<li>$1</li>')
    .replace(/(<li>.*<\/li>\n?)+/g, s => `<ul>${s}</ul>`)
    .replace(/\n{2,}/g, '<br><br>')
    .replace(/\n/g, '<br>');
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

// ── 초기화 ───────────────────────────────────────────────
(async function init() {
  showLoading();

  const data = await loadReport();
  if (!data) {
    showError();
    return;
  }

  renderReport(data);
  await renderArchive();
  showContent();
})();
