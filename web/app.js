/* app.js - IT 인사이트 리포트 대시보드 */

const CAT_COLORS = {
  '글로벌 컨설팅': '#7c3aed',
  '국내 연구기관': '#0891b2',
  '한국 대기업':   '#0284c7',
  '플랫폼 테크':   '#059669',
  'IT 미디어':     '#d97706',
};

let allArticles  = [];
let allSources   = [];
let trendChart   = null;  // Chart.js 인스턴스 (재생성 방지)
let currentCat   = 'all';

// ── 데이터 로드 ──────────────────────────────────────────
async function loadReport(file = 'data/reports/latest.json') {
  try {
    const res = await fetch(file + '?t=' + Date.now());
    if (!res.ok) throw new Error('not found');
    return await res.json();
  } catch { return null; }
}

async function loadIndex() {
  try {
    const res = await fetch('data/reports/index.json?t=' + Date.now());
    if (!res.ok) return null;
    return await res.json();
  } catch { return null; }
}

async function loadSources() {
  try {
    const res = await fetch('data/sources.json?t=' + Date.now());
    if (!res.ok) return null;
    return await res.json();
  } catch { return null; }
}

// ── 메인 렌더 ─────────────────────────────────────────────
function renderReport(data) {
  document.getElementById('report-date').textContent = data.date || '-';
  document.getElementById('stat-articles').textContent = data.total_articles ?? '-';
  const uniqueSrc = [...new Set((data.articles || []).map(a => a.source))];
  document.getElementById('stat-sources').textContent = uniqueSrc.length;
  document.getElementById('stat-categories').textContent = Object.keys(data.categories || {}).length;
  document.getElementById('final-report').innerHTML =
    markdownToHtml(data.final_report || '리포트가 없습니다.');

  // 수집 기간 표시
  const periodEl = document.getElementById('article-period');
  if (periodEl && data.articles?.length) {
    const dates = data.articles.map(a => a.published?.slice(0, 10)).filter(Boolean).sort();
    if (dates.length) {
      const [oldest, newest] = [dates[0], dates[dates.length - 1]];
      periodEl.textContent = oldest === newest
        ? `${newest} 기준`
        : `${oldest} ~ ${newest} (1주일치)`;
    }
  }

  // 샘플 배너 판별
  const notice = document.getElementById('demo-notice');
  if (notice) {
    const today = new Date().toISOString().slice(0, 10);
    const isReal = data.articles?.some(a => a.url && !a.url.includes('mckinsey.com/capabilities'));
    if (isReal || data.date === today) notice.style.display = 'none';
  }

  allArticles = data.articles || [];
  renderArticles(allArticles);
  renderWordCloud(allArticles);
}

// ── ① 주간 트렌드 차트 ──────────────────────────────────
async function renderTrendChart() {
  const index   = await loadIndex();
  const canvas  = document.getElementById('trend-chart');
  const emptyEl = document.getElementById('chart-empty');
  if (!canvas) return;

  if (!index?.reports?.length) {
    canvas.style.display = 'none';
    emptyEl?.classList.remove('hidden');
    return;
  }

  // 최대 7일치, 오래된 날짜 → 최신 순
  const last7    = index.reports.slice(0, 7).reverse();
  const labels   = last7.map(r => r.date.slice(5).replace('-', '/'));  // "04/17"
  const cats     = ['글로벌 컨설팅', '한국 대기업', '플랫폼 테크', 'IT 미디어', '국내 연구기관'];

  const datasets = cats.map(cat => ({
    label: cat,
    data: last7.map(r => (r.categories || {})[cat] || 0),
    backgroundColor: CAT_COLORS[cat] + 'cc',  // 약간 투명
    borderColor: CAT_COLORS[cat],
    borderWidth: 1,
    borderRadius: 4,
    borderSkipped: false,
  }));

  // 기존 차트 파괴 후 재생성
  if (trendChart) { trendChart.destroy(); trendChart = null; }

  trendChart = new Chart(canvas.getContext('2d'), {
    type: 'bar',
    data: { labels, datasets },
    options: {
      responsive: true,
      maintainAspectRatio: true,
      plugins: {
        legend: {
          position: 'bottom',
          labels: { font: { size: 11, family: 'Inter' }, padding: 16 },
        },
        tooltip: {
          mode: 'index',
          callbacks: {
            title: ctx => `${ctx[0].label} 수집 현황`,
            label: ctx => ` ${ctx.dataset.label}: ${ctx.parsed.y}개`,
          },
        },
      },
      scales: {
        x: {
          stacked: true,
          grid: { display: false },
          ticks: { font: { size: 11 } },
        },
        y: {
          stacked: true,
          beginAtZero: true,
          grid: { color: '#f1f5f9' },
          ticks: { font: { size: 11 }, stepSize: 5 },
        },
      },
    },
  });
}

// ── ② 아티클 렌더 (중요도 점수 표시) ────────────────────
function getSortedArticles(articles) {
  const sortVal = document.getElementById('sort-select')?.value || 'score';
  return [...articles].sort((a, b) => {
    if (sortVal === 'score')  return (b.importance_score || 0) - (a.importance_score || 0);
    if (sortVal === 'date')   return (b.published || '').localeCompare(a.published || '');
    if (sortVal === 'source') return (a.source || '').localeCompare(b.source || '');
    return 0;
  });
}

function renderArticles(articles) {
  const grid       = document.getElementById('articles-grid');
  const countBadge = document.getElementById('article-count');
  grid.innerHTML   = '';
  if (countBadge) countBadge.textContent = `${articles.length}개 아티클`;

  if (!articles.length) {
    grid.innerHTML = '<p style="color:var(--text-sm);padding:20px;font-size:13px">해당 카테고리의 아티클이 없습니다.</p>';
    return;
  }

  const sorted = getSortedArticles(articles);
  sorted.forEach(a => {
    const color   = CAT_COLORS[a.category] || '#2563eb';
    const card    = document.createElement('div');
    card.className = 'article-card';

    const dateStr = a.published ? a.published.slice(0, 10) : '';
    const hasLink = !!a.url;

    // ② 중요도 점수 뱃지
    const score = a.importance_score || 0;
    let scoreBadge = '';
    if (score > 0) {
      const level = score >= 8 ? 'high' : score >= 5 ? 'mid' : 'low';
      const stars = score >= 8 ? '🔥' : score >= 5 ? '⭐' : '·';
      scoreBadge = `<span class="score-badge score-${level}">${stars} ${score}/10</span>`;
    }

    // ⑤ 영문 번역 제목 처리
    const displayTitle = a.title_ko || a.title || '';
    const hasTranslation = !!(a.title_ko && a.title_ko !== a.title);
    const titleHtml = hasLink
      ? `<a href="${esc(a.url)}" target="_blank" rel="noopener">${esc(displayTitle)}</a>`
      : esc(displayTitle);
    const origTitleHtml = hasTranslation
      ? `<div class="article-orig-title">🌐 ${esc(a.title)}</div>`
      : '';

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
          ${scoreBadge}
          ${dateStr ? `<span class="article-date">${dateStr}</span>` : ''}
        </div>
        <div class="article-title">${titleHtml}</div>
        ${origTitleHtml}
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
      </div>`;
    grid.appendChild(card);
  });
}

async function renderArchive() {
  const index = await loadIndex();
  const list  = document.getElementById('archive-list');
  if (!index?.reports?.length || index.reports.length <= 1) return;

  const past = index.reports.slice(1);
  list.innerHTML = past.map(r => {
    const d     = new Date(r.date);
    const day   = d.getDate();
    const month = d.toLocaleDateString('ko-KR', { month: 'long' });
    const cats  = Object.entries(r.categories || {})
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

// ── ③ 워드클라우드 ───────────────────────────────────────
const KO_STOPWORDS = new Set([
  '있는','있다','있어','이다','이어','하는','하다','하여','하고','한다',
  '됩니다','됐다','위한','위해','통해','대한','관련','기반','중심',
  '이번','지난','올해','최근','현재','이를','이에','이후','이와',
  '기술','서비스','사업','기업','시장','도입','활용','제공','강화',
  '확대','추진','발표','출시','개발','구축','운영','지원','분석',
  'the','and','for','with','this','that','from','are','its','was',
  'new','how','all','can','has','not','our','will','their','more',
]);

function extractKeywords(articles) {
  const freq = {};
  articles.forEach(a => {
    [a.title_ko || a.title || '', a.ai_summary || '', a.summary || ''].forEach(text => {
      text.replace(/[^\w가-힣\s]/g, ' ').split(/\s+/)
        .map(w => w.trim())
        .filter(w => w.length >= 2 && w.length <= 12 && !/^\d+$/.test(w))
        .forEach(w => {
          const k = w.toLowerCase();
          if (!KO_STOPWORDS.has(k) && !KO_STOPWORDS.has(w)) freq[w] = (freq[w] || 0) + 1;
        });
    });
  });
  return Object.entries(freq)
    .filter(([, c]) => c >= 2)
    .sort((a, b) => b[1] - a[1])
    .slice(0, 60)
    .map(([word, cnt]) => [word, cnt]);
}

function renderWordCloud(articles) {
  const canvas  = document.getElementById('wordcloud-canvas');
  const emptyEl = document.getElementById('wordcloud-empty');
  if (!canvas) return;

  const words = extractKeywords(articles);
  if (!words.length) {
    canvas.style.display = 'none';
    if (emptyEl) { emptyEl.classList.remove('hidden'); emptyEl.textContent = '키워드 데이터가 없습니다.'; }
    return;
  }

  const parent  = canvas.parentElement;
  canvas.width  = Math.min(parent.offsetWidth - 48, 900);
  canvas.height = 280;

  const maxCnt  = words[0][1];
  const wordList = words.map(([w, cnt]) => [w, Math.round(13 + (cnt / maxCnt) * 50)]);
  const colors   = ['#2563eb', '#7c3aed', '#0891b2', '#059669', '#d97706', '#dc2626', '#0f1f3d'];

  try {
    WordCloud(canvas, {
      list: wordList,
      gridSize: Math.round(8 * canvas.width / 600),
      weightFactor: 1,
      fontFamily: 'Inter, Apple SD Gothic Neo, sans-serif',
      color: () => colors[Math.floor(Math.random() * colors.length)],
      rotateRatio: 0.2,
      rotationSteps: 2,
      backgroundColor: '#f8fafc',
      drawOutOfBound: false,
      shrinkToFit: true,
    });
  } catch {
    // 폴백: CSS 태그 클라우드
    canvas.style.display = 'none';
    const div = document.createElement('div');
    div.className = 'tag-cloud-fallback';
    words.slice(0, 40).forEach(([w, cnt]) => {
      const size  = 11 + Math.round((cnt / maxCnt) * 24);
      const color = colors[Math.floor(Math.random() * colors.length)];
      const span  = document.createElement('span');
      span.textContent = w;
      span.style.cssText = `font-size:${size}px;color:${color};font-weight:${cnt > 3 ? 700 : 500}`;
      div.appendChild(span);
    });
    canvas.parentElement.appendChild(div);
  }
}

// ── 소스 현황 탭 ─────────────────────────────────────────
function renderSources(sourcesData, filterCat = 'all') {
  const grid    = document.getElementById('sources-grid');
  const totalEl = document.getElementById('sources-total');
  if (!grid || !sourcesData) return;

  const sources = filterCat === 'all'
    ? sourcesData.sources
    : sourcesData.sources.filter(s => s.category === filterCat);

  if (totalEl) totalEl.textContent = sourcesData.total;
  grid.innerHTML = '';

  const groups = {};
  sources.forEach(s => {
    if (!groups[s.category]) groups[s.category] = [];
    groups[s.category].push(s);
  });

  Object.entries(groups).forEach(([cat, items]) => {
    const color   = CAT_COLORS[cat] || '#2563eb';
    const groupEl = document.createElement('div');
    groupEl.className = 'sources-group';
    groupEl.innerHTML = `
      <div class="sources-group-title" style="border-left-color:${color}">
        <span class="sources-group-dot" style="background:${color}"></span>
        ${esc(cat)} <span class="sources-group-count">${items.length}개</span>
      </div>
      <div class="sources-group-grid">
        ${items.map(s => {
          const logoUrl   = `https://www.google.com/s2/favicons?sz=64&domain_url=${esc(s.logo_domain)}`;
          const typeLabel = { web:'WEB', pdf:'PDF', web_pdf:'WEB+PDF', rss:'RSS' }[s.type] || s.type.toUpperCase();
          const typeBg    = { web:'#eff6ff', pdf:'#fef3c7', web_pdf:'#f0fdf4', rss:'#fdf4ff' }[s.type] || '#f1f5f9';
          const typeColor = { web:'#1d4ed8', pdf:'#d97706', web_pdf:'#059669', rss:'#7c3aed' }[s.type] || '#475569';
          return `
          <a class="source-card" href="${esc(s.url)}" target="_blank" rel="noopener">
            <div class="source-card-accent" style="background:${color}"></div>
            <div class="source-card-body">
              <div class="source-card-logo-wrap">
                <img class="source-card-logo" src="${logoUrl}" alt="${esc(s.name_ko)}"
                     onerror="this.src='data:image/svg+xml,<svg xmlns=%22http://www.w3.org/2000/svg%22 viewBox=%220 0 32 32%22><rect width=%2232%22 height=%2232%22 rx=%224%22 fill=%22%23e2e8f0%22/></svg>'">
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
      </div>`;
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
    if (allSources) renderSources(allSources);
  } else {
    mainEl.classList.remove('hidden');
    sourceEl.classList.add('hidden');
    if (hero) hero.style.display = '';
  }
}

// ── 이벤트 위임 ──────────────────────────────────────────
document.addEventListener('click', e => {
  // 아티클 필터
  if (e.target.matches('.filter-btn[data-cat]')) {
    document.querySelectorAll('.filter-btn[data-cat]').forEach(b => b.classList.remove('active'));
    e.target.classList.add('active');
    currentCat = e.target.dataset.cat;
    const filtered = currentCat === 'all'
      ? allArticles
      : allArticles.filter(a => a.category === currentCat);
    renderArticles(filtered);
    return;
  }
  // 소스 필터
  if (e.target.matches('.filter-btn[data-scat]')) {
    document.querySelectorAll('.filter-btn[data-scat]').forEach(b => b.classList.remove('active'));
    e.target.classList.add('active');
    renderSources(allSources, e.target.dataset.scat);
    return;
  }
  // 탭
  if (e.target.matches('.nav-btn[data-tab]')) {
    switchTab(e.target.dataset.tab);
  }
});

// 정렬 변경
document.addEventListener('change', e => {
  if (e.target.id === 'sort-select') {
    const filtered = currentCat === 'all'
      ? allArticles
      : allArticles.filter(a => a.category === currentCat);
    renderArticles(filtered);
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
  return (str || '').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
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
  const [sourcesData] = await Promise.all([loadSources()]);
  if (sourcesData) allSources = sourcesData;

  showLoading();
  const data = await loadReport();
  if (!data) { showError(); return; }

  renderReport(data);
  await Promise.all([renderArchive(), renderTrendChart()]);
  showContent();
})();
