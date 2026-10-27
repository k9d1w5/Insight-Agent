/* app.js - IT 인사이트 리포트 대시보드 */

const LOGO_OVERRIDES = {
  'McKinsey & Company': 'images/logos/mckinsey.png',
  'IITP 주간기술동향':   'images/logos/iitp.png',
  'IITP ICT Brief':     'images/logos/iitp.png',
};

function getLogoHtml(source, logoDomain, cssClass = 'source-logo') {
  const localPath = LOGO_OVERRIDES[source];
  const src = localPath
    ? localPath
    : logoDomain
      ? `https://www.google.com/s2/favicons?sz=64&domain_url=${esc(logoDomain)}`
      : null;
  if (!src) return '';
  return `<img class="${cssClass}" src="${src}" alt="${esc(source)}" onerror="this.style.display='none'">`;
}

const CAT_COLORS = {
  '글로벌 컨설팅': '#7c3aed',
  '국내 연구기관': '#0891b2',
  '한국 대기업':   '#0284c7',
  '플랫폼 테크':   '#059669',
  'IT 미디어':     '#d97706',
};

let allArticles  = [];
let allSources   = [];
let trendChart   = null;
let currentCat   = 'all';
let currentDate  = 'all';
let currentView  = 'card';

// ── 다크 모드 ────────────────────────────────────────────
(function initTheme() {
  try {
    const saved = localStorage.getItem('theme') || 'light';
    document.documentElement.setAttribute('data-theme', saved);
    const btn = document.getElementById('theme-toggle');
    if (btn) btn.textContent = saved === 'dark' ? '☀️' : '🌙';
  } catch {}
})();

document.getElementById('theme-toggle')?.addEventListener('click', () => {
  const html = document.documentElement;
  const next = html.getAttribute('data-theme') === 'dark' ? 'light' : 'dark';
  html.setAttribute('data-theme', next);
  document.getElementById('theme-toggle').textContent = next === 'dark' ? '☀️' : '🌙';
  try { localStorage.setItem('theme', next); } catch {}
  if (trendChart) updateChartTheme();
  if (allArticles.length) renderWordCloud(allArticles);
});

function updateChartTheme() {
  const isDark = document.documentElement.getAttribute('data-theme') === 'dark';
  const gridColor  = isDark ? 'rgba(255,255,255,.06)' : '#f1f5f9';
  const tickColor  = isDark ? '#8b949e' : '#64748b';
  if (!trendChart) return;
  trendChart.options.scales.x.ticks.color = tickColor;
  trendChart.options.scales.y.ticks.color = tickColor;
  trendChart.options.scales.y.grid.color  = gridColor;
  trendChart.options.plugins.legend.labels.color = tickColor;
  trendChart.update();
}

// ── 맨 위로 버튼 ─────────────────────────────────────────
const scrollTopBtn = document.getElementById('scroll-top-btn');
window.addEventListener('scroll', () => {
  scrollTopBtn?.classList.toggle('visible', window.scrollY > 300);
}, { passive: true });
scrollTopBtn?.addEventListener('click', () => {
  window.scrollTo({ top: 0, behavior: 'smooth' });
});

// ── 토스트 ──────────────────────────────────────────────
function showToast(msg, icon = '✅') {
  const container = document.getElementById('toast-container');
  if (!container) return;
  const el = document.createElement('div');
  el.className = 'toast';
  el.textContent = icon + ' ' + msg;
  container.appendChild(el);
  requestAnimationFrame(() => { requestAnimationFrame(() => { el.classList.add('show'); }); });
  setTimeout(() => {
    el.classList.remove('show');
    setTimeout(() => el.remove(), 250);
  }, 2200);
}

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

// ── 날짜 필터 헬퍼 ──────────────────────────────────────
function filterByDate(articles, range) {
  if (range === 'all') return articles;
  const now   = new Date();
  const today = now.toISOString().slice(0, 10);
  const yest  = new Date(now.getTime() - 86400000).toISOString().slice(0, 10);
  const weekAgo = new Date(now.getTime() - 6 * 86400000).toISOString().slice(0, 10);
  return articles.filter(a => {
    const d = (a.published || '').slice(0, 10);
    if (range === 'today')     return d === today;
    if (range === 'yesterday') return d === yest;
    if (range === 'week')      return d >= weekAgo;
    return true;
  });
}

function getFilteredArticles() {
  let arts = currentCat === 'all' ? allArticles : allArticles.filter(a => a.category === currentCat);
  return filterByDate(arts, currentDate);
}

// ── 메인 렌더 ─────────────────────────────────────────────
function renderReport(data) {
  document.getElementById('report-date').textContent = data.date || '-';
  document.getElementById('stat-articles').textContent = data.total_articles ?? '-';
  const uniqueSrc = [...new Set((data.articles || []).map(a => a.source))];
  document.getElementById('stat-sources').textContent  = uniqueSrc.length;
  document.getElementById('stat-categories').textContent = Object.keys(data.categories || {}).length;

  const periodEl = document.getElementById('article-period');
  if (periodEl && data.articles?.length) {
    const dates = data.articles.map(a => a.published?.slice(0, 10)).filter(Boolean).sort();
    if (dates.length) {
      const [oldest, newest] = [dates[0], dates[dates.length - 1]];
      periodEl.textContent = oldest === newest ? `${newest} 기준` : `${oldest} ~ ${newest} (1주일치)`;
    }
  }

  const notice = document.getElementById('demo-notice');
  if (notice) {
    const today = new Date().toISOString().slice(0, 10);
    const isReal = data.articles?.some(a => a.url && !a.url.includes('mckinsey.com/capabilities'));
    if (isReal || data.date === today) notice.style.display = 'none';
  }

  allArticles = data.articles || [];
  renderArticles(getFilteredArticles());
  renderWordCloud(allArticles);
}

// ── 아티클 렌더 ──────────────────────────────────────────
function getSortedArticles(articles) {
  const s = document.getElementById('sort-select')?.value || 'date';
  return [...articles].sort((a, b) => {
    if (s === 'date')   return (b.published || '').localeCompare(a.published || '');
    if (s === 'source') return (a.source || '').localeCompare(b.source || '');
    return 0;
  });
}

function renderArticles(articles) {
  const grid  = document.getElementById('articles-grid');
  const badge = document.getElementById('article-count');
  grid.innerHTML = '';
  if (badge) badge.textContent = `${articles.length}개 아티클`;

  // 뷰 클래스
  grid.classList.toggle('list-view', currentView === 'list');

  if (!articles.length) {
    grid.innerHTML = '<p style="color:var(--text-sm);padding:20px;font-size:13px">해당 조건의 아티클이 없습니다.</p>';
    return;
  }

  const today = new Date().toISOString().slice(0, 10);

  getSortedArticles(articles).forEach(a => {
    const color = CAT_COLORS[a.category] || '#2563eb';
    const card  = document.createElement('div');
    card.className = 'article-card';
    const dateStr    = a.published ? a.published.slice(0, 10) : '';
    const isToday    = dateStr === today;
    const hasLink    = !!a.url;
    const displayTitle = a.title_ko || a.title || '';
    const titleHtml  = hasLink
      ? `<a href="${esc(a.url)}" target="_blank" rel="noopener">${esc(displayTitle)}</a>`
      : esc(displayTitle);
    const origTitleHtml = (a.title_ko && a.title_ko !== a.title)
      ? `<div class="article-orig-title">🌐 ${esc(a.title)}</div>` : '';
    const logoHtml   = getLogoHtml(a.source, a.logo_domain, 'source-logo');
    const newBadge   = isToday ? `<span class="new-badge">NEW</span>` : '';
    const copyBtn    = hasLink
      ? `<button class="copy-link-btn" data-url="${esc(a.url)}" title="링크 복사">🔗</button>` : '';

    card.innerHTML = `
      ${copyBtn}
      <div class="article-card-top" style="background:${color}"></div>
      <div class="article-card-body">
        <div class="article-meta">
          <span class="cat-badge" style="background:${color}">${esc(a.category)}</span>
          ${logoHtml}
          <span class="source-chip">${esc(a.source)}</span>
          ${newBadge}
          ${dateStr ? `<span class="article-date">${dateStr}</span>` : ''}
        </div>
        <div class="article-title">${titleHtml}</div>
        ${origTitleHtml}
        ${a.summary ? `<div class="article-original">${esc(a.summary.slice(0,200))}</div>` : ''}
        ${hasLink ? `<div class="article-link-row"><a class="article-link" href="${esc(a.url)}" target="_blank" rel="noopener">원문 보기 →</a></div>` : ''}
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
    const d    = new Date(r.date);
    const cats = Object.entries(r.categories || {})
      .map(([k,v]) => `<span class="archive-cat-chip">${k} ${v}</span>`).join('');
    return `<div class="archive-item" data-file="data/reports/${r.file}">
      <div><div class="archive-date-num">${d.getDate()}</div><div class="archive-date-month">${d.toLocaleDateString('ko-KR',{month:'long'})}</div></div>
      <div class="archive-divider"></div>
      <div class="archive-info"><div class="archive-date-full">${r.date}</div><div class="archive-cats">${cats}</div></div>
      <div class="archive-count">아티클 ${r.total_articles}개</div>
      <div class="archive-arrow">›</div>
    </div>`;
  }).join('');
  list.querySelectorAll('.archive-item').forEach(el => {
    el.addEventListener('click', async () => {
      showLoading();
      const data = await loadReport(el.dataset.file);
      if (data) { renderReport(data); showContent(); window.scrollTo({top:0,behavior:'smooth'}); }
    });
  });
}

// ── 주간 트렌드 차트 ──────────────────────────────────────
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
  const isDark   = document.documentElement.getAttribute('data-theme') === 'dark';
  const tickColor = isDark ? '#8b949e' : '#64748b';
  const gridColor = isDark ? 'rgba(255,255,255,.06)' : '#f1f5f9';
  const last7    = index.reports.slice(0, 7).reverse();
  const labels   = last7.map(r => r.date.slice(5).replace('-', '/'));
  const cats     = ['글로벌 컨설팅','한국 대기업','플랫폼 테크','IT 미디어','국내 연구기관'];
  const datasets = cats.map(cat => ({
    label: cat,
    data: last7.map(r => (r.categories || {})[cat] || 0),
    backgroundColor: CAT_COLORS[cat] + 'cc',
    borderColor: CAT_COLORS[cat],
    borderWidth: 1,
    borderRadius: 4,
    borderSkipped: false,
  }));
  if (trendChart) { trendChart.destroy(); trendChart = null; }
  trendChart = new Chart(canvas.getContext('2d'), {
    type: 'bar',
    data: { labels, datasets },
    options: {
      responsive: true,
      maintainAspectRatio: true,
      plugins: {
        legend: { position: 'bottom', labels: { font: { size: 11, family: 'Inter' }, padding: 16, color: tickColor } },
        tooltip: {
          mode: 'index',
          callbacks: {
            title: ctx => `${ctx[0].label} 수집 현황`,
            label: ctx => ` ${ctx.dataset.label}: ${ctx.parsed.y}개`,
          },
        },
      },
      scales: {
        x: { stacked: true, grid: { display: false }, ticks: { font: { size: 11 }, color: tickColor } },
        y: { stacked: true, beginAtZero: true, grid: { color: gridColor }, ticks: { font: { size: 11 }, stepSize: 5, color: tickColor } },
      },
    },
  });
}

// ── 워드클라우드 ─────────────────────────────────────────
const KO_STOPWORDS = new Set([
  '있는','있다','있어','있고','없는','없다','없어','이다','이어',
  '하는','하다','하여','하고','한다','했다','하면','하지','해서','해야','하기','하기도',
  '됩니다','됩니','됐다','된다','되는','되어','되고','되면','되지','되기',
  '통한','위한','관한','이루는','이뤄지는','갖는','갖춘','지닌',
  '이는','이런','이렇게','이처럼','이러한','이같은','이같이',
  '그런','그렇게','그처럼','그러한','그같은','그래서','그러나','그리고','그러므로',
  '하며','하면서','하지만','하더라도','하더니','하였다','하였으며',
  '있으며','있어서','있도록','있었다','없었다','없으며',
  '되었다','되었으며','됩니다','되었습니다',
  '것','등','수','점','때','간','내','전','후','중','각','차','측','위',
  '상','하','좌','우','셈','터','바','듯','뿐','채','만큼','정도',
  '및','또','혹은','또는','그리고','하지만','그러나','그래서','따라서','그러므로',
  '더욱','특히','또한','이미','이제','매우','바로','즉','먼저','이후','앞으로',
  '최근','현재','이번','지난','올해','내년','더','많이','빠르게','지속적으로',
  '본격적으로','급속도로','전반적으로','다양하게','적극적으로',
  '우리','저희','이들','그들','여기','거기','이런','저런','이러한','그러한',
  '이를','이에','이와','이로','이후',
  '부분','내용','방식','방법','측면','경우','상황','결과','효과','필요','가능',
  '중요','다양한','새로운','기존','주요','대표적','해당','관련','통해','위해',
  '통한','기반','중심','강화','확대','추진','제공','개선','향상','증가','성장',
  '목표','전략','계획','노력','투자','역량','성과','활동','움직임','흐름',
  'the','and','for','with','this','that','from','are','its','was',
  'new','how','all','can','has','not','our','will','their','more',
  'been','have','they','but','what','you','about','into','which',
  'when','where','who','very','just','also','even','than','then',
  'said','says','use','used','using','one','two','get','got','per',
]);

const KO_PARTICLES = [
  '에서의','으로의','로부터','로서의','에서부터','이라는','라는','이라고','라고',
  '에서','에게','한테','부터','까지','처럼','만큼','보다','으로','이며',
  '이고','이나','이랑','이다','로서','에는','에도','에만',
  '로','를','을','은','는','이','가','와','과','의','도','만','에',
];

function stripParticle(word) {
  if (!/^[가-힣]+$/.test(word)) return word;
  for (const p of KO_PARTICLES) {
    if (word.endsWith(p) && word.length - p.length >= 2) {
      return word.slice(0, word.length - p.length);
    }
  }
  return word;
}

function extractKeywords(articles) {
  const freq = {};
  articles.forEach(a => {
    [a.title_ko || a.title || ''].forEach(text => {
      text.replace(/[^\wㄱ-ㅎㅏ-ㅣ가-힣\s]/g, ' ')
        .split(/\s+/)
        .map(w => stripParticle(w.trim()))
        .filter(w => {
          if (w.length < 2 || w.length > 15) return false;
          if (/^\d+$/.test(w)) return false;
          if (/[다는고며서면여야지게]$/.test(w) && /[가-힣]{3,}/.test(w)) return false;
          const lower = w.toLowerCase();
          return !KO_STOPWORDS.has(w) && !KO_STOPWORDS.has(lower);
        })
        .forEach(w => { freq[w] = (freq[w] || 0) + 1; });
    });
  });
  return Object.entries(freq)
    .filter(([,c]) => c >= 2)
    .sort((a,b) => b[1] - a[1])
    .slice(0, 60)
    .map(([word, cnt]) => [word, cnt]);
}

function createCloudMask(width, height) {
  const mc = document.createElement('canvas');
  mc.width = width; mc.height = height;
  const ctx = mc.getContext('2d');
  ctx.fillStyle = '#000'; ctx.fillRect(0, 0, width, height);
  ctx.fillStyle = '#fff';
  const r = Math.min(width, height);
  [
    { x:.50, y:.58, r:.28 }, { x:.30, y:.65, r:.20 }, { x:.70, y:.65, r:.20 },
    { x:.40, y:.48, r:.22 }, { x:.62, y:.46, r:.22 }, { x:.50, y:.38, r:.20 },
    { x:.18, y:.70, r:.14 }, { x:.82, y:.70, r:.14 }, { x:.25, y:.58, r:.16 }, { x:.75, y:.58, r:.16 },
  ].forEach(c => {
    ctx.beginPath(); ctx.arc(c.x * width, c.y * height, c.r * r, 0, Math.PI * 2); ctx.fill();
  });
  return mc;
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
  const parent = canvas.parentElement;
  canvas.width  = Math.min(parent.offsetWidth - 48, 860);
  canvas.height = Math.round(canvas.width * 0.5);
  const isDark  = document.documentElement.getAttribute('data-theme') === 'dark';
  canvas.style.background = isDark ? '#1c2230' : '#f8fafc';
  const maxCnt   = words[0][1];
  const wordList = words.map(([w,cnt]) => [w, Math.round(12 + (cnt/maxCnt) * 48)]);
  const colors   = isDark
    ? ['#60a5fa','#a78bfa','#34d399','#fbbf24','#f87171','#38bdf8','#e879f9']
    : ['#2563eb','#7c3aed','#0891b2','#059669','#d97706','#dc2626','#0f1f3d'];
  const maskCanvas = createCloudMask(canvas.width, canvas.height);
  try {
    WordCloud(canvas, {
      list: wordList,
      gridSize: Math.round(6 * canvas.width / 600),
      weightFactor: 1,
      fontFamily: 'Inter, Apple SD Gothic Neo, sans-serif',
      color: () => colors[Math.floor(Math.random() * colors.length)],
      rotateRatio: .15, rotationSteps: 2,
      backgroundColor: isDark ? '#1c2230' : '#f8fafc',
      maskImage: maskCanvas,
      drawOutOfBound: false, shrinkToFit: true,
    });
  } catch {
    canvas.style.display = 'none';
    const div = document.createElement('div');
    div.className = 'tag-cloud-fallback';
    words.slice(0,40).forEach(([w,cnt]) => {
      const span = document.createElement('span');
      span.textContent = w;
      span.style.cssText = `font-size:${11+Math.round((cnt/maxCnt)*24)}px;color:${colors[Math.floor(Math.random()*colors.length)]};font-weight:${cnt>3?700:500}`;
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
  const sources = filterCat === 'all' ? sourcesData.sources : sourcesData.sources.filter(s => s.category === filterCat);
  if (totalEl) totalEl.textContent = sourcesData.total;
  grid.innerHTML = '';
  const groups = {};
  sources.forEach(s => { (groups[s.category] = groups[s.category] || []).push(s); });
  Object.entries(groups).forEach(([cat, items]) => {
    const color = CAT_COLORS[cat] || '#2563eb';
    const el = document.createElement('div');
    el.className = 'sources-group';
    el.innerHTML = `
      <div class="sources-group-title" style="border-left-color:${color}">
        <span class="sources-group-dot" style="background:${color}"></span>
        ${esc(cat)} <span class="sources-group-count">${items.length}개</span>
      </div>
      <div class="sources-group-grid">${items.map(s => {
        const typeLabel = {web:'WEB',pdf:'PDF',web_pdf:'WEB+PDF',rss:'RSS'}[s.type]||s.type.toUpperCase();
        const typeBg    = {web:'#eff6ff',pdf:'#fef3c7',web_pdf:'#f0fdf4',rss:'#fdf4ff'}[s.type]||'#f1f5f9';
        const typeColor = {web:'#1d4ed8',pdf:'#d97706',web_pdf:'#059669',rss:'#7c3aed'}[s.type]||'#475569';
        return `<div class="source-card" data-source-name="${esc(s.name_ko)}" data-source-cat="${esc(s.category)}">
          <div class="source-card-accent" style="background:${color}"></div>
          <div class="source-card-body">
            <div class="source-card-logo-wrap">
              ${getLogoHtml(s.name, s.logo_domain, 'source-card-logo')}
            </div>
            <div class="source-card-info">
              <div class="source-card-name">${esc(s.name_ko)}</div>
              <div class="source-card-en">${esc(s.name)}</div>
              <div class="source-card-desc">${esc(s.description)}</div>
              <button class="source-card-goto" data-source-name="${esc(s.name_ko)}" data-source-cat="${esc(s.category)}">
                📰 아티클 보기
              </button>
            </div>
            <div class="source-card-type" style="background:${typeBg};color:${typeColor}">${typeLabel}</div>
          </div>
          <a class="source-card-url" href="${esc(s.url)}" target="_blank" rel="noopener">${esc(s.url)}</a>
        </div>`;
      }).join('')}</div>`;
    grid.appendChild(el);
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
    mainEl.classList.add('hidden'); sourceEl.classList.remove('hidden');
    if (hero) hero.style.display = 'none';
    if (allSources) renderSources(allSources);
  } else {
    mainEl.classList.remove('hidden'); sourceEl.classList.add('hidden');
    if (hero) hero.style.display = '';
  }
}

// ── 소스별 바로가기: 리포트 탭 + 소스 이름으로 필터 ─────
function gotoSourceArticles(sourceName) {
  switchTab('report');
  currentCat  = 'all';
  currentDate = 'all';
  document.querySelectorAll('.filter-btn[data-cat]').forEach(b => b.classList.toggle('active', b.dataset.cat === 'all'));
  document.querySelectorAll('.date-filter-btn').forEach(b => b.classList.toggle('active', b.dataset.date === 'all'));
  const filtered = allArticles.filter(a => a.source === sourceName || (a.source && a.source.includes(sourceName)));
  renderArticles(filtered.length ? filtered : allArticles);
  document.getElementById('article-count').textContent = `${filtered.length}개 아티클 (${sourceName})`;
  window.scrollTo({ top: document.getElementById('articles-grid')?.offsetTop - 120 || 0, behavior: 'smooth' });
  showToast(`"${sourceName}" 아티클 ${filtered.length}개`);
}

// ── 이벤트 ───────────────────────────────────────────────
document.addEventListener('click', e => {
  // 카테고리 필터
  if (e.target.matches('.filter-btn[data-cat]')) {
    document.querySelectorAll('.filter-btn[data-cat]').forEach(b => b.classList.remove('active'));
    e.target.classList.add('active');
    currentCat = e.target.dataset.cat;
    renderArticles(getFilteredArticles());
    return;
  }
  // 소스 현황 카테고리 필터
  if (e.target.matches('.filter-btn[data-scat]')) {
    document.querySelectorAll('.filter-btn[data-scat]').forEach(b => b.classList.remove('active'));
    e.target.classList.add('active');
    renderSources(allSources, e.target.dataset.scat);
    return;
  }
  // 탭 전환
  if (e.target.matches('.nav-btn[data-tab]')) { switchTab(e.target.dataset.tab); return; }
  // 날짜 범위 필터
  if (e.target.matches('.date-filter-btn')) {
    document.querySelectorAll('.date-filter-btn').forEach(b => b.classList.remove('active'));
    e.target.classList.add('active');
    currentDate = e.target.dataset.date;
    renderArticles(getFilteredArticles());
    return;
  }
  // 뷰 전환
  if (e.target.matches('.view-btn')) {
    document.querySelectorAll('.view-btn').forEach(b => b.classList.remove('active'));
    e.target.classList.add('active');
    currentView = e.target.dataset.view;
    renderArticles(getFilteredArticles());
    try { localStorage.setItem('viewMode', currentView); } catch {}
    return;
  }
  // 링크 복사 버튼
  if (e.target.matches('.copy-link-btn') || e.target.closest('.copy-link-btn')) {
    e.preventDefault(); e.stopPropagation();
    const btn = e.target.closest('.copy-link-btn') || e.target;
    const url = btn.dataset.url;
    if (url) {
      navigator.clipboard?.writeText(url)
        .then(() => showToast('링크가 복사됐습니다', '🔗'))
        .catch(() => showToast('복사에 실패했습니다', '❌'));
    }
    return;
  }
  // 소스 현황 → 아티클 바로가기
  if (e.target.matches('.source-card-goto') || e.target.closest('.source-card-goto')) {
    e.preventDefault(); e.stopPropagation();
    const btn = e.target.closest('.source-card-goto') || e.target;
    gotoSourceArticles(btn.dataset.sourceName);
    return;
  }
});

document.addEventListener('change', e => {
  if (e.target.id === 'sort-select') renderArticles(getFilteredArticles());
});

// 저장된 뷰 모드 복원
try {
  const saved = localStorage.getItem('viewMode');
  if (saved) {
    currentView = saved;
    document.querySelectorAll('.view-btn').forEach(b => b.classList.toggle('active', b.dataset.view === saved));
  }
} catch {}

function esc(str) {
  return (str||'').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
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
  const sourcesData = await loadSources();
  if (sourcesData) allSources = sourcesData;
  showLoading();
  const data = await loadReport();
  if (!data) { showError(); return; }
  renderReport(data);
  await Promise.all([renderArchive(), renderTrendChart()]);
  showContent();
})();
