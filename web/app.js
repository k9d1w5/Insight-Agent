/* app.js - IT 인사이트 리포트 대시보드 */

// 로컬 로고 오버라이드 (images/logos/ 폴더에 파일 저장 필요)
const LOGO_OVERRIDES = {
  'McKinsey & Company':  'images/logos/mckinsey.png',
  'IITP 주간기술동향':    'images/logos/iitp.png',
  'IITP ICT Brief':      'images/logos/iitp.png',
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

let allArticles = [];
let allSources  = [];
let trendChart  = null;
let currentCat  = 'all';

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
  renderArticles(allArticles);
  renderWordCloud(allArticles);
}

// ── 마크다운 → HTML (섹션 인식 렌더러) ──────────────────
function fmt(text) {
  return text
    .replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;')
    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');
}

function markdownToHtml(md) {
  const lines  = md.split('\n');
  const out    = [];
  let paraLines   = [];
  let inUl        = false;
  let inOl        = false;
  let inTrendCard = false;
  let trendBuf    = [];

  function flushPara() {
    if (!paraLines.length) return;
    out.push('<p>' + paraLines.map(fmt).join('<br>') + '</p>');
    paraLines = [];
  }
  function closeUl()   { if (inUl)  { out.push('</ul>');  inUl  = false; } }
  function closeOl()   { if (inOl)  { out.push('</ol>');  inOl  = false; } }
  function closeTrend() {
    if (inTrendCard) {
      out.push('<div class="trend-body">' + trendBuf.join('\n') + '</div></div>');
      trendBuf = []; inTrendCard = false;
    }
  }

  for (let i = 0; i < lines.length; i++) {
    const raw  = lines[i];
    const line = raw.trim();

    // — H1 —
    if (line.startsWith('# ')) {
      flushPara(); closeUl(); closeOl(); closeTrend();
      out.push(`<h1 class="rpt-h1">${fmt(line.slice(2))}</h1>`);
      continue;
    }

    // — H2 —
    if (line.startsWith('## ')) {
      flushPara(); closeUl(); closeOl(); closeTrend();
      const title = line.slice(3).trim();
      if (title.includes('Executive Summary') || title.includes('🔍')) {
        out.push('<div class="rpt-executive">');
        out.push(`<div class="rpt-exec-label"><span class="rpt-exec-icon">🔍</span>Executive Summary</div>`);
        out.push('<div class="rpt-exec-body">');
        // collect until next ## or ---
        let j = i + 1;
        while (j < lines.length && !lines[j].trim().startsWith('## ') && lines[j].trim() !== '---') {
          const t = lines[j].trim();
          if (t) out.push('<p>' + fmt(t) + '</p>');
          j++;
        }
        out.push('</div></div>');
        i = j - 1;
      } else {
        out.push(`<h2 class="rpt-h2">${fmt(title)}</h2>`);
      }
      continue;
    }

    // — H3 (트렌드 카드 or 기관 헤더) —
    if (line.startsWith('### ')) {
      flushPara(); closeUl(); closeOl(); closeTrend();
      const title = line.slice(4).trim();
      const medal = title.startsWith('🥇') ? 'gold'
                  : title.startsWith('🥈') ? 'silver'
                  : title.startsWith('🥉') ? 'bronze' : null;
      if (medal) {
        inTrendCard = true;
        trendBuf = [];
        out.push(`<div class="trend-card trend-${medal}">`);
        out.push(`<div class="trend-header"><span class="trend-medal">${title.slice(0,2)}</span><span class="trend-title">${fmt(title.slice(2).replace(/^\s*\[?\s*/,'').replace(/\s*\]?\s*$/,''))}</span></div>`);
      } else {
        out.push(`<h3 class="rpt-h3">${fmt(title)}</h3>`);
      }
      continue;
    }

    // — HR —
    if (line === '---') {
      flushPara(); closeUl(); closeOl(); closeTrend();
      out.push('<div class="rpt-divider"></div>');
      continue;
    }

    // — 순서있는 목록 —
    const olM = line.match(/^(\d+)\.\s+(.+)$/);
    if (olM) {
      flushPara(); closeUl();
      if (!inOl) { out.push('<ol class="rpt-action-list">'); inOl = true; }
      if (inTrendCard) {
        trendBuf.push(`<li>${fmt(olM[2])}</li>`);
      } else {
        out.push(`<li>${fmt(olM[2])}</li>`);
      }
      continue;
    }

    // — 순서없는 목록 —
    if (line.startsWith('- ')) {
      flushPara(); closeOl();
      if (!inUl) { if (inTrendCard) trendBuf.push('<ul>'); else out.push('<ul>'); inUl = true; }
      const item = `<li>${fmt(line.slice(2))}</li>`;
      if (inTrendCard) trendBuf.push(item); else out.push(item);
      continue;
    }

    // — 빈 줄 —
    if (!line) {
      if (inUl) { closeUl(); if (inTrendCard) trendBuf.push('</ul>'); }
      if (inOl) { closeOl(); if (inTrendCard) trendBuf.push('</ol>'); }
      flushPara();
      continue;
    }

    // — 일반 텍스트 —
    if (inTrendCard) {
      trendBuf.push('<p>' + fmt(line) + '</p>');
    } else {
      closeUl(); closeOl();
      paraLines.push(line);
    }
  }

  flushPara(); closeUl(); closeOl(); closeTrend();
  return out.join('\n');
}

// ── 아티클 렌더 ──────────────────────────────────────────
function getSortedArticles(articles) {
  const s = document.getElementById('sort-select')?.value || 'score';
  return [...articles].sort((a, b) => {
    if (s === 'score')  return (b.importance_score || 0) - (a.importance_score || 0);
    if (s === 'date')   return (b.published || '').localeCompare(a.published || '');
    if (s === 'source') return (a.source || '').localeCompare(b.source || '');
    return 0;
  });
}

function renderArticles(articles) {
  const grid = document.getElementById('articles-grid');
  const badge = document.getElementById('article-count');
  grid.innerHTML = '';
  if (badge) badge.textContent = `${articles.length}개 아티클`;

  if (!articles.length) {
    grid.innerHTML = '<p style="color:var(--text-sm);padding:20px;font-size:13px">해당 카테고리의 아티클이 없습니다.</p>';
    return;
  }

  getSortedArticles(articles).forEach(a => {
    const color = CAT_COLORS[a.category] || '#2563eb';
    const card  = document.createElement('div');
    card.className = 'article-card';
    const dateStr = a.published ? a.published.slice(0, 10) : '';
    const hasLink = !!a.url;
    const score   = a.importance_score || 0;
    const scoreBadge = score > 0
      ? `<span class="score-badge score-${score>=8?'high':score>=5?'mid':'low'}">${score>=8?'🔥':score>=5?'⭐':'·'} ${score}/10</span>`
      : '';
    const displayTitle = a.title_ko || a.title || '';
    const titleHtml = hasLink
      ? `<a href="${esc(a.url)}" target="_blank" rel="noopener">${esc(displayTitle)}</a>`
      : esc(displayTitle);
    const origTitleHtml = (a.title_ko && a.title_ko !== a.title)
      ? `<div class="article-orig-title">🌐 ${esc(a.title)}</div>` : '';
    const logoHtml = getLogoHtml(a.source, a.logo_domain, 'source-logo');

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
        ${a.summary ? `<div class="article-original">${esc(a.summary.slice(0,200))}</div>` : ''}
        ${a.ai_summary ? `<div class="article-ai-box"><div class="ai-label">AI 요약</div><div class="article-ai-text">${esc(a.ai_summary)}</div></div>` : ''}
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
    const d = new Date(r.date);
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
  const last7  = index.reports.slice(0, 7).reverse();
  const labels = last7.map(r => r.date.slice(5).replace('-', '/'));
  const cats   = ['글로벌 컨설팅','한국 대기업','플랫폼 테크','IT 미디어','국내 연구기관'];
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
        legend: { position: 'bottom', labels: { font: { size: 11, family: 'Inter' }, padding: 16 } },
        tooltip: {
          mode: 'index',
          callbacks: {
            title: ctx => `${ctx[0].label} 수집 현황`,
            label: ctx => ` ${ctx.dataset.label}: ${ctx.parsed.y}개`,
          },
        },
      },
      scales: {
        x: { stacked: true, grid: { display: false }, ticks: { font: { size: 11 } } },
        y: { stacked: true, beginAtZero: true, grid: { color: '#f1f5f9' }, ticks: { font: { size: 11 }, stepSize: 5 } },
      },
    },
  });
}

// ── 워드클라우드 (강화된 불용어) ─────────────────────────
const KO_STOPWORDS = new Set([
  // 동사·형용사 활용형
  '있는','있다','있어','있고','없는','없다','없어','이다','이어',
  '하는','하다','하여','하고','한다','했다','하면','하지','해서','해야','하기','하기도',
  '됩니다','됩니','됐다','된다','되는','되어','되고','되면','되지','되기',
  '통한','위한','관한','이루는','이뤄지는','갖는','갖춘','지닌',
  // 지시·접속 표현
  '이는','이런','이렇게','이처럼','이러한','이같은','이같이',
  '그런','그렇게','그처럼','그러한','그같은','그래서','그러나','그리고','그러므로',
  '하며','하면서','하지만','하더라도','하더니','하였다','하였으며',
  '있으며','있어서','있도록','있었다','없었다','없으며',
  '되었다','되었으며','됩니다','되었습니다',
  // 의존명사·불완전명사
  '것','등','수','점','때','간','내','전','후','중','각','차','측','위',
  '상','하','좌','우','셈','터','바','듯','뿐','채','만큼','정도',
  // 접속사·부사
  '및','또','혹은','또는','그리고','하지만','그러나','그래서','따라서','그러므로',
  '더욱','특히','또한','이미','이제','매우','바로','즉','먼저','이후','앞으로',
  '최근','현재','이번','지난','올해','내년','더','많이','빠르게','지속적으로',
  '본격적으로','급속도로','전반적으로','다양하게','적극적으로',
  // 일반 대명사·지시어
  '우리','저희','이들','그들','여기','거기','이런','저런','이러한','그러한',
  '이를','이에','이와','이로','이후',
  // 너무 광범위한 명사
  '부분','내용','방식','방법','측면','경우','상황','결과','효과','필요','가능',
  '중요','다양한','새로운','기존','주요','대표적','해당','관련','통해','위해',
  '통한','기반','중심','강화','확대','추진','제공','개선','향상','증가','성장',
  '목표','전략','계획','노력','투자','역량','성과','활동','움직임','흐름',
  // 영어 불용어
  'the','and','for','with','this','that','from','are','its','was',
  'new','how','all','can','has','not','our','will','their','more',
  'been','have','they','but','what','you','about','into','which',
  'when','where','who','very','just','also','even','than','then',
  'said','says','use','used','using','one','two','get','got','per',
]);

// 한국어 조사 제거 (긴 것 먼저)
const KO_PARTICLES = [
  '에서의','으로의','로부터','로서의','에서부터','이라는','라는','이라고','라고',
  '에서','에게','한테','부터','까지','처럼','만큼','보다','으로','이며',
  '이고','이나','이랑','이다','로서','에서','에는','에도','에만',
  '에서','에게','에도','에만','에서','에만','에서','에게','에도',
  '로','를','을','은','는','이','가','와','과','의','도','만','에',
];

function stripParticle(word) {
  // 한글로만 구성된 단어에만 적용
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
    [a.title_ko || a.title || '', a.ai_summary || ''].forEach(text => {
      text.replace(/[^\wㄱ-ㅎㅏ-ㅣ가-힣\s]/g, ' ')
        .split(/\s+/)
        .map(w => stripParticle(w.trim()))   // 조사 제거
        .filter(w => {
          if (w.length < 2 || w.length > 15) return false;
          if (/^\d+$/.test(w)) return false;
          // 동사 어미로 끝나는 것 제외
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

// 구름 모양 마스크 캔버스 생성
function createCloudMask(width, height) {
  const mc  = document.createElement('canvas');
  mc.width  = width;
  mc.height = height;
  const ctx = mc.getContext('2d');

  ctx.fillStyle = '#000';
  ctx.fillRect(0, 0, width, height);
  ctx.fillStyle = '#fff';

  // 구름 = 여러 원을 겹쳐서 표현
  const cx = width / 2, cy = height / 2;
  const r  = Math.min(width, height);
  const circles = [
    { x: 0.50, y: 0.58, r: 0.28 },
    { x: 0.30, y: 0.65, r: 0.20 },
    { x: 0.70, y: 0.65, r: 0.20 },
    { x: 0.40, y: 0.48, r: 0.22 },
    { x: 0.62, y: 0.46, r: 0.22 },
    { x: 0.50, y: 0.38, r: 0.20 },
    { x: 0.18, y: 0.70, r: 0.14 },
    { x: 0.82, y: 0.70, r: 0.14 },
    { x: 0.25, y: 0.58, r: 0.16 },
    { x: 0.75, y: 0.58, r: 0.16 },
  ];
  circles.forEach(c => {
    ctx.beginPath();
    ctx.arc(c.x * width, c.y * height, c.r * r, 0, Math.PI * 2);
    ctx.fill();
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
  canvas.height = Math.round(canvas.width * 0.5);  // 구름 비율
  const maxCnt   = words[0][1];
  const wordList = words.map(([w,cnt]) => [w, Math.round(12 + (cnt/maxCnt) * 48)]);
  const colors   = ['#2563eb','#7c3aed','#0891b2','#059669','#d97706','#dc2626','#0f1f3d'];
  const maskCanvas = createCloudMask(canvas.width, canvas.height);
  try {
    WordCloud(canvas, {
      list: wordList,
      gridSize: Math.round(6 * canvas.width / 600),
      weightFactor: 1,
      fontFamily: 'Inter, Apple SD Gothic Neo, sans-serif',
      color: () => colors[Math.floor(Math.random() * colors.length)],
      rotateRatio: 0.15, rotationSteps: 2,
      backgroundColor: '#f8fafc',
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
        return `<a class="source-card" href="${esc(s.url)}" target="_blank" rel="noopener">
          <div class="source-card-accent" style="background:${color}"></div>
          <div class="source-card-body">
            <div class="source-card-logo-wrap">
              ${getLogoHtml(s.name, s.logo_domain, 'source-card-logo')}
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

// ── 이벤트 ───────────────────────────────────────────────
document.addEventListener('click', e => {
  if (e.target.matches('.filter-btn[data-cat]')) {
    document.querySelectorAll('.filter-btn[data-cat]').forEach(b => b.classList.remove('active'));
    e.target.classList.add('active');
    currentCat = e.target.dataset.cat;
    renderArticles(currentCat === 'all' ? allArticles : allArticles.filter(a => a.category === currentCat));
    return;
  }
  if (e.target.matches('.filter-btn[data-scat]')) {
    document.querySelectorAll('.filter-btn[data-scat]').forEach(b => b.classList.remove('active'));
    e.target.classList.add('active');
    renderSources(allSources, e.target.dataset.scat);
    return;
  }
  if (e.target.matches('.nav-btn[data-tab]')) switchTab(e.target.dataset.tab);
});
document.addEventListener('change', e => {
  if (e.target.id === 'sort-select') {
    renderArticles(currentCat === 'all' ? allArticles : allArticles.filter(a => a.category === currentCat));
  }
});

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
