/**
 * NFLComp Application Controller
 * High-performance, dependency-free vanilla JavaScript SPA.
 * Manages data loading, sorting, filtering, tab navigation, SVG charts, modals, and exports.
 */

// Global State
const STATE = {
  summary: null,
  leaderboard: [],
  strategies: [],
  upcomingBets: [],
  openPositions: [],
  ledger: [],
  kalshiTrades: [],
  researchExperiments: [],
  strategyLab: null,
  registry: [],
  irregularities: [],
  auditChecks: [],
  crossValidation: null,
  bettingMarkets: null,
  forwardTesting: null,
  executionReport: null,
  autonomousResearch: null,
  publicResearch: null,
  empiricalStudies: null,
  riskAnalytics: null,
  currentTab: 'research',
  historyPage: 1,
  historyPageSize: 50,
  leaderSortField: 'total_pnl',
  leaderSortAsc: false,
};

// ================= INITIALIZATION =================
document.addEventListener('DOMContentLoaded', () => {
  initNavigation();
  loadAllData();
});

function initNavigation() {
  const tabs = document.querySelectorAll('.nav-tab');
  tabs.forEach(tab => {
    tab.addEventListener('click', () => {
      const target = tab.getAttribute('data-tab');
      switchTab(target);
    });
  });

  // Handle URL hash routing
  if (window.location.hash) {
    const hashTab = window.location.hash.replace('#', '');
    if (document.getElementById(`view-${hashTab}`)) {
      switchTab(hashTab);
    }
  }
}

function switchTab(tabId) {
  STATE.currentTab = tabId;
  window.location.hash = tabId;

  document.querySelectorAll('.nav-tab').forEach(t => {
    t.classList.toggle('active', t.getAttribute('data-tab') === tabId);
  });

  document.querySelectorAll('.view-section').forEach(sec => {
    sec.classList.toggle('active', sec.id === `view-${tabId}`);
  });

  window.scrollTo({ top: 0, behavior: 'smooth' });

  // Re-render chart if switching to performance
  if (tabId === 'performance') {
    renderPerformanceCharts();
  } else if (tabId === 'dashboard') {
    renderDashboardEquityChart();
  }
}

// ================= DATA LOADING =================
async function loadAllData() {
  try {
    const [
      summaryRes,
      leaderRes,
      stratRes,
      upcomingRes,
      openPosRes,
      ledgerRes,
      kalshiRes,
      expRes,
      strategyLabRes,
      regRes,
      irrRes,
      auditRes,
      cvRes,
      bmRes,
      ftRes,
      execRes,
      arRes,
      pubRes,
      studiesRes,
      riskRes
    ] = await Promise.all([
      fetch('data/summary.json').then(r => r.json()),
      fetch('data/leaderboard.json').then(r => r.json()),
      fetch('data/strategies.json').then(r => r.json()),
      fetch('data/upcoming_bets.json').then(r => r.json()),
      fetch('data/open_positions.json').then(r => r.json()),
      fetch('data/bets_ledger.json').then(r => r.json()),
      fetch('data/kalshi_trades.json').then(r => r.json()),
      fetch('data/research_experiments.json').then(r => r.json()),
      fetch('data/strategy_lab.json').then(r => r.json()),
      fetch('data/registry.json').then(r => r.json()),
      fetch('data/irregularities.json').then(r => r.json()),
      fetch('data/audit_checks.json').then(r => r.json()),
      fetch('data/cross_validation.json').then(r => r.json()).catch(() => null),
      fetch('data/betting_markets.json').then(r => r.json()).catch(() => null),
      fetch('data/forward_testing.json').then(r => r.json()).catch(() => null),
      fetch('data/execution_report.json').then(r => r.json()).catch(() => null),
      fetch('data/autonomous_research.json').then(r => r.json()).catch(() => null),
      fetch('data/public_strategy_research.json').then(r => r.json()).catch(() => null),
      fetch('data/empirical_studies.json').then(r => r.json()).catch(() => null),
      fetch('data/risk_analytics.json').then(r => r.json()).catch(() => null)
    ]);

    STATE.summary = summaryRes;
    STATE.leaderboard = leaderRes;
    STATE.strategies = stratRes;
    STATE.upcomingBets = upcomingRes;
    STATE.openPositions = openPosRes;
    STATE.ledger = ledgerRes;
    STATE.kalshiTrades = kalshiRes;
    STATE.researchExperiments = expRes;
    STATE.strategyLab = strategyLabRes;
    STATE.registry = regRes;
    STATE.irregularities = irrRes;
    STATE.auditChecks = auditRes;
    STATE.crossValidation = cvRes;
    STATE.bettingMarkets = bmRes;
    STATE.forwardTesting = ftRes;
    STATE.executionReport = execRes;
    STATE.autonomousResearch = arRes;
    STATE.publicResearch = pubRes;
    STATE.empiricalStudies = studiesRes;
    STATE.riskAnalytics = riskRes;
    STATE.marketTypes = (STATE.bettingMarkets && Array.isArray(STATE.bettingMarkets.taxonomy))
      ? STATE.bettingMarkets.taxonomy.length : null;

    populateStrategyBetFilters();
    renderKPIs();
    renderPublishedClaims();
    renderDashboard();
    renderLeaderboard();
    renderStrategies();
    renderUpcomingBets();
    renderOpenPositions();
    renderHistoryTable();
    renderPerformanceCharts();
    renderResearchLab();
    renderKalshiDesk();
    renderRegistry();
    renderVerification();
    renderEmpiricalStudies();
    renderRiskAnalytics();
    setupFilters();

  } catch (err) {
    console.error('Error loading competition datasets:', err);
  }
}

// ================= RENDER FUNCTIONS =================

function renderKPIs() {
  if (!STATE.summary) return;
  const s = STATE.summary;
  document.getElementById('kpi-games').textContent = s.total_games_tracked.toLocaleString();
  document.getElementById('kpi-strategies').textContent = s.total_strategies;
  document.getElementById('kpi-bets').textContent = s.total_simulated_bets.toLocaleString();
  
  const pnlEl = document.getElementById('kpi-pnl');
  pnlEl.textContent = (s.total_simulated_pnl >= 0 ? '+' : '') + '$' + s.total_simulated_pnl.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  pnlEl.className = s.total_simulated_pnl >= 0 ? 'kpi-value kpi-val-green' : 'kpi-value kpi-val-red';

  document.getElementById('kpi-upcoming').textContent = s.total_upcoming_bets;
  if (s.top_performing_strategy) {
    document.getElementById('kpi-top-strat').textContent = s.top_performing_strategy;
    document.getElementById('kpi-top-roi').textContent = `ROI: +${s.top_roi}% (+$${s.top_pnl.toLocaleString()})`;
  }
}

/**
 * Bind the numbers written in prose to the loaded data.
 *
 * The static HTML carries the value that was true when the data was exported
 * (the audit fails if it drifts), and this keeps a live page correct even if it
 * is served against a newer data directory.
 */
function renderPublishedClaims() {
  const s = STATE.summary;
  if (!s) return;
  const set = (id, value) => {
    const el = document.getElementById(id);
    if (el) el.textContent = value;
  };
  const personas = s.total_strategies.toLocaleString();
  ['claim-personas', 'claim-personas-dash', 'claim-personas-cta', 'claim-personas-heading']
    .forEach((id) => set(id, personas));
  set('claim-upcoming', s.total_upcoming_bets.toLocaleString());
  if (Array.isArray(STATE.ledger) && STATE.ledger.length) {
    const published = STATE.ledger.length;
    set('claim-history', published >= 1000 ? `${Math.round(published / 1000)}k` : published.toLocaleString());
  }
  if (Array.isArray(STATE.registry)) set('claim-registry', STATE.registry.length.toLocaleString());
  if (Array.isArray(STATE.upcomingBets) && STATE.upcomingBets.length) {
    const week = STATE.upcomingBets.filter(b => b.season === s.current_season && b.week === s.current_week);
    set('claim-week-signals', week.length.toLocaleString());
    set('claim-week-games', new Set(week.map(b => b.game_id)).size.toLocaleString());
  }
  if (s.season_span) {
    const span = s.season_span.replace('-', '\u2013');
    set('claim-season-span', span);
    set('claim-methodology-span', span);
  }
  if (Array.isArray(STATE.auditChecks) && STATE.auditChecks.length) {
    const passed = STATE.auditChecks.filter(c => c.passed).length.toLocaleString();
    ['claim-audit-checks', 'claim-audit-checks-methodology', 'claim-footer-checks'].forEach((id) => set(id, passed));
  }
  set('claim-games-completed', Number(s.completed_games).toLocaleString());
  set('claim-ledger-title', Number(s.total_simulated_bets).toLocaleString());
  set('claim-methodology-games', Number(s.total_games_tracked).toLocaleString());
  set('claim-kalshi-title', Number(s.total_kalshi_trades).toLocaleString());
  set('claim-kalshi-card', Number(s.total_kalshi_trades).toLocaleString());
  set('claim-footer-personas', Number(s.total_strategies).toLocaleString());
  set('claim-footer-bets', (Array.isArray(STATE.ledger) ? STATE.ledger.length : 0).toLocaleString());
  set('claim-footer-sources-link', (Array.isArray(STATE.registry) ? STATE.registry.length : 0).toLocaleString());
  if (Array.isArray(STATE.openPositions)) set('claim-open-positions', STATE.openPositions.length.toLocaleString());
  if (STATE.marketTypes) set('claim-market-types', STATE.marketTypes.toLocaleString());
  if (Array.isArray(STATE.researchExperiments)) {
    set('claim-experiments-title', STATE.researchExperiments.length.toLocaleString());
  }
  const studies = STATE.empiricalStudies;
  if (studies) set('claim-studies-count', (studies.studies || []).length.toLocaleString());
  const risk = STATE.riskAnalytics;
  if (risk) {
    if (risk.policy) set('claim-risk-floor', Number(risk.policy.minimum_settled_bets).toLocaleString());
    const calibration = risk.calibration || {};
    if (calibration.brier_score !== undefined) set('claim-risk-brier', Number(calibration.brier_score).toFixed(4));
    if (calibration.expected_calibration_error_pct_points !== undefined) {
      set('claim-risk-ece', Number(calibration.expected_calibration_error_pct_points).toFixed(2));
    }
  }
}

function renderDashboard() {
  // Top 5 Leaders in Dashboard Table
  const tbody = document.getElementById('dash-leader-body');
  if (!tbody) return;
  tbody.innerHTML = '';
  const top5 = STATE.leaderboard.slice(0, 5);
  top5.forEach((s, idx) => {
    const tr = document.createElement('tr');
    tr.className = 'clickable-row';
    tr.onclick = () => openStrategyModal(s.id);
    const pnlClass = s.total_pnl >= 0 ? 'color: var(--accent-green);' : 'color: var(--accent-red);';
    tr.innerHTML = `
      <td><strong>#${idx + 1}</strong></td>
      <td><span style="color: var(--accent-cyan); font-family: var(--font-mono); font-weight:700;">${s.username}</span></td>
      <td><span class="tag-category">${s.category}</span></td>
      <td>${s.win_rate}%</td>
      <td style="${pnlClass} font-family: var(--font-mono); font-weight:700;">${s.total_pnl >= 0 ? '+' : ''}$${s.total_pnl.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</td>
      <td><strong>${s.roi > 0 ? '+' : ''}${s.roi}%</strong></td>
    `;
    tbody.appendChild(tr);
  });

  // Active Week 2 Slate Pulse - dynamic from upcoming bets
  const slateBody = document.getElementById('dash-slate-body');
  if (!slateBody) return;
  slateBody.innerHTML = '';
  
  // Group upcoming bets by matchup
  const matchupMap = {};
  STATE.upcomingBets.filter(u => u.week === 2).forEach(u => {
    if (!matchupMap[u.matchup]) {
      matchupMap[u.matchup] = { count: 0, gameday: u.gameday, gametime: u.gametime, spread: null, total: null };
    }
    matchupMap[u.matchup].count += 1;
    if (u.market === 'SPREAD' && !matchupMap[u.matchup].spread) matchupMap[u.matchup].spread = u.selection;
    if (u.market === 'TOTAL' && !matchupMap[u.matchup].total) matchupMap[u.matchup].total = u.selection;
  });

  const sortedMatchups = Object.entries(matchupMap).sort((a,b) => b[1].count - a[1].count).slice(0, 8);

  if (sortedMatchups.length === 0) {
    const tr = document.createElement('tr');
    tr.innerHTML = '<td colspan="5" class="empty-state">No verified upcoming market snapshot is available.</td>';
    slateBody.appendChild(tr);
  } else {
    sortedMatchups.forEach(([matchup, info]) => {
      const tr = document.createElement('tr');
      tr.innerHTML = `
        <td><strong>${matchup}</strong></td>
        <td style="color: var(--text-secondary); font-size: 0.78rem;">${info.gameday} ${info.gametime || ''}</td>
        <td><code>${info.spread || '—'}</code></td>
        <td><code>${info.total || '—'}</code></td>
        <td><span class="badge badge-ready">${info.count} signals</span></td>
      `;
      slateBody.appendChild(tr);
    });
  }

  renderDashboardEquityChart();
}

function renderDashboardEquityChart() {
  const container = document.getElementById('dash-equity-chart');
  if (!container || STATE.leaderboard.length === 0) return;
  
  const topStrats = STATE.leaderboard.slice(0, 4);
  const colors = ['#3b82f6', '#10b981', '#06b6d4', '#f59e0b'];
  
  container.innerHTML = generateMultiLineChartSVG(topStrats, colors, 900, 280);
}

// ================= LEADERBOARD =================
function renderLeaderboard() {
  const tbody = document.getElementById('main-leaderboard-body');
  if (!tbody) return;
  tbody.innerHTML = '';

  const searchVal = (document.getElementById('leader-search')?.value || '').toLowerCase();
  const catFilter = document.getElementById('leader-cat-filter')?.value || 'ALL';

  let list = [...STATE.leaderboard];

  if (catFilter !== 'ALL') {
    list = list.filter(s => s.category === catFilter);
  }

  if (searchVal) {
    list = list.filter(s => s.username.toLowerCase().includes(searchVal) || s.name.toLowerCase().includes(searchVal) || s.id.toLowerCase().includes(searchVal));
  }

  // Sort
  list.sort((a, b) => {
    let valA = a[STATE.leaderSortField];
    let valB = b[STATE.leaderSortField];
    if (typeof valA === 'string') {
      return STATE.leaderSortAsc ? valA.localeCompare(valB) : valB.localeCompare(valA);
    }
    return STATE.leaderSortAsc ? valA - valB : valB - valA;
  });

  list.forEach((s, idx) => {
    const tr = document.createElement('tr');
    tr.className = 'clickable-row';
    tr.onclick = () => openStrategyModal(s.id);
    const pnlClass = s.total_pnl >= 0 ? 'color: var(--accent-green);' : 'color: var(--accent-red);';
    tr.innerHTML = `
      <td><strong>${idx + 1}</strong></td>
      <td>
        <div style="font-weight:700; color:var(--accent-cyan); font-family:var(--font-mono);">${s.username}</div>
        <div style="font-size:0.75rem; color:var(--text-secondary);">${s.name}</div>
      </td>
      <td><span class="tag-category">${s.category}</span></td>
      <td><span class="tag-version">${s.version}</span></td>
      <td style="${pnlClass} font-family:var(--font-mono); font-weight:700;">${s.total_pnl >= 0 ? '+' : ''}$${s.total_pnl.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</td>
      <td><strong>${s.roi > 0 ? '+' : ''}${s.roi}%</strong></td>
      <td>${s.win_rate}%</td>
      <td style="font-family:var(--font-mono);">${s.total_bets.toLocaleString()}</td>
      <td style="color:var(--accent-red); font-family:var(--font-mono);">$${s.max_drawdown.toLocaleString('en-US', { minimumFractionDigits: 2 })}</td>
      <td style="font-family:var(--font-mono); font-weight:600;">$${s.current_bankroll.toLocaleString('en-US', { minimumFractionDigits: 2 })}</td>
      <td><span class="badge ${s.status === 'ACTIVE' ? 'badge-win' : 'badge-watching'}">${s.status}</span></td>
    `;
    tbody.appendChild(tr);
  });
}

// ================= STRATEGIES CATALOG =================
function renderStrategies() {
  const grid = document.getElementById('strategies-card-grid');
  if (!grid) return;
  grid.innerHTML = '';

  const searchVal = (document.getElementById('strat-search')?.value || '').toLowerCase();
  const catFilter = document.getElementById('strat-cat-filter')?.value || 'ALL';

  let list = [...STATE.strategies];

  if (catFilter !== 'ALL') {
    list = list.filter(s => s.category === catFilter);
  }

  if (searchVal) {
    list = list.filter(s => s.username.toLowerCase().includes(searchVal) || s.name.toLowerCase().includes(searchVal) || s.hypothesis.toLowerCase().includes(searchVal));
  }

  // Find matching performance
  const perfMap = {};
  STATE.leaderboard.forEach(p => { perfMap[p.id] = p; });

  list.forEach(strat => {
    const perf = perfMap[strat.id] || { total_pnl: 0, roi: 0, win_rate: 0, total_bets: 0, max_drawdown: 0 };
    const card = document.createElement('div');
    card.className = 'strategy-card';
    const pnlClass = perf.total_pnl >= 0 ? 'color: var(--accent-green);' : 'color: var(--accent-red);';
    card.innerHTML = `
      <div>
        <div class="strat-card-header">
          <span class="strat-username">${strat.username}</span>
          <span class="tag-version">${strat.version}</span>
        </div>
        <div class="strat-name">${strat.name}</div>
        <div style="margin-bottom: 8px;"><span class="tag-category">${strat.category}</span></div>
        <p class="strat-hypothesis">${strat.hypothesis.substring(0, 180)}...</p>
      </div>

      <div>
        <div class="strat-metrics-row">
          <div class="strat-metric-box">
            <span class="strat-metric-lbl">Total PnL</span>
            <span class="strat-metric-val" style="${pnlClass}">${perf.total_pnl >= 0 ? '+' : ''}$${perf.total_pnl.toLocaleString('en-US', { maximumFractionDigits: 0 })}</span>
          </div>
          <div class="strat-metric-box">
            <span class="strat-metric-lbl">ROI</span>
            <span class="strat-metric-val">${perf.roi > 0 ? '+' : ''}${perf.roi}%</span>
          </div>
          <div class="strat-metric-box">
            <span class="strat-metric-lbl">Win Rate</span>
            <span class="strat-metric-val">${perf.win_rate}%</span>
          </div>
          <div class="strat-metric-box">
            <span class="strat-metric-lbl">Bets</span>
            <span class="strat-metric-val">${perf.total_bets}</span>
          </div>
        </div>

        <button class="btn btn-sm strategy-review-btn" onclick="openStrategyModal('${strat.id}')">Review strategy, placed bets & next trades →</button>
      </div>
    `;
    grid.appendChild(card);
  });
}

// ================= BET REVIEW HELPERS =================
function populateStrategyBetFilters() {
  const options = [...STATE.strategies]
    .sort((a, b) => a.username.localeCompare(b.username))
    .map(s => `<option value="${s.id}">${s.username} — ${s.name}</option>`)
    .join('');

  ['upcoming-strategy-filter', 'history-strategy-filter'].forEach(id => {
    const select = document.getElementById(id);
    if (select) select.insertAdjacentHTML('beforeend', options);
  });
}

function openStrategyBetReview(stratId, destination = 'history') {
  closeModal();
  const filter = document.getElementById(`${destination}-strategy-filter`);
  if (filter) filter.value = stratId;
  if (destination === 'history') {
    STATE.historyPage = 1;
    renderHistoryTable();
  } else {
    renderUpcomingBets();
  }
  switchTab(destination);
}

function formatBetDate(bet, upcoming = false) {
  const date = bet.gameday || (bet.bet_timestamp || '').slice(0, 10);
  const time = upcoming ? bet.gametime : (bet.bet_timestamp || '').slice(11, 16);
  return `${date || '—'}${time ? ` ${time}` : ''}`;
}

// ================= UPCOMING BETS =================
function getStatusBadgeClass(status) {
  const map = {
    'WATCHING': 'badge-watching',
    'QUALIFIED': 'badge-qualified',
    'READY': 'badge-ready',
    'READY_TO_BET': 'badge-ready',
    'PRICE_TOO_HIGH': 'badge-loss',
    'WAITING': 'badge-waiting',
    'EXECUTED': 'badge-win',
    'CANCELLED': 'badge-loss',
    'EXPIRED': 'badge-loss'
  };
  return map[status] || 'badge-watching';
}

function renderUpcomingBets() {
  const tbody = document.getElementById('upcoming-bets-body');
  if (!tbody) return;
  tbody.innerHTML = '';

  const strategyFilter = document.getElementById('upcoming-strategy-filter')?.value || 'ALL';
  const statusFilter = document.getElementById('upcoming-status-filter')?.value || 'ALL';
  const marketFilter = document.getElementById('upcoming-market-filter')?.value || 'ALL';

  let list = [...STATE.upcomingBets];

  if (strategyFilter !== 'ALL') {
    list = list.filter(u => u.strategy_id === strategyFilter);
  }

  if (statusFilter !== 'ALL') {
    list = list.filter(u => u.status === statusFilter);
  }

  if (marketFilter !== 'ALL') {
    list = list.filter(u => u.market === marketFilter);
  }

  if (list.length === 0) {
    tbody.innerHTML = '<tr><td colspan="11" class="empty-state">No upcoming trades match these filters.</td></tr>';
    return;
  }

  list.forEach(bet => {
    const tr = document.createElement('tr');
    tr.className = 'clickable-row';
    tr.title = 'Open this strategy';
    tr.onclick = () => openStrategyModal(bet.strategy_id);
    const badgeClass = getStatusBadgeClass(bet.status);
    tr.innerHTML = `
      <td><span class="badge ${badgeClass}">${bet.status.replaceAll('_', ' ')}</span></td>
      <td><span style="color:var(--accent-cyan); font-weight:700; font-family:var(--font-mono);">${bet.username}</span></td>
      <td>Week ${bet.week} (${bet.gameday})</td>
      <td><strong>${bet.matchup}</strong></td>
      <td><span class="tag-category">${bet.market}</span></td>
      <td><code style="font-weight:700;">${bet.selection}</code></td>
      <td style="font-family:var(--font-mono);">${bet.current_price}</td>
      <td style="font-family:var(--font-mono);">${(bet.model_prob * 100).toFixed(1)}%</td>
      <td style="color:var(--accent-green); font-family:var(--font-mono); font-weight:700;">+${(bet.estimated_edge * 100).toFixed(1)}%</td>
      <td style="font-family:var(--font-mono);">$${bet.stake.toFixed(2)}</td>
      <td style="font-size:0.75rem; color:var(--text-secondary);">${bet.market_source}</td>
    `;
    tbody.appendChild(tr);
  });
}

// ================= LIVE OPEN POSITIONS =================
function renderOpenPositions() {
  const tbody = document.getElementById('open-positions-body');
  if (!tbody) return;
  tbody.innerHTML = '';

  const positions = STATE.openPositions;
  document.getElementById('open-pos-count').textContent = `${positions.length} Active Week 2 Positions`;

  positions.forEach(pos => {
    const tr = document.createElement('tr');
    tr.innerHTML = `
      <td><span style="color:var(--accent-cyan); font-family:var(--font-mono); font-weight:700;">${pos.username}</span></td>
      <td><strong>${pos.matchup}</strong></td>
      <td><code>${pos.selection}</code></td>
      <td style="font-family:var(--font-mono);">${pos.current_price}</td>
      <td style="font-family:var(--font-mono);">$${pos.stake.toFixed(2)}</td>
      <td><span class="badge badge-ready">READY TO BET</span></td>
    `;
    tbody.appendChild(tr);
  });
}

// ================= HISTORY / LEDGER =================
function renderHistoryTable() {
  const tbody = document.getElementById('history-table-body');
  if (!tbody) return;
  tbody.innerHTML = '';

  const searchVal = (document.getElementById('history-search')?.value || '').toLowerCase();
  const strategyFilter = document.getElementById('history-strategy-filter')?.value || 'ALL';
  const seasonFilter = document.getElementById('history-season-filter')?.value || 'ALL';
  const resFilter = document.getElementById('history-res-filter')?.value || 'ALL';

  let list = [...STATE.ledger];

  if (strategyFilter !== 'ALL') {
    list = list.filter(b => b.strategy_id === strategyFilter);
  }

  if (seasonFilter !== 'ALL') {
    list = list.filter(b => String(b.season) === seasonFilter);
  }

  if (resFilter !== 'ALL') {
    list = list.filter(b => b.result === resFilter);
  }

  if (searchVal) {
    list = list.filter(b => b.matchup.toLowerCase().includes(searchVal) || b.username.toLowerCase().includes(searchVal) || b.bet_id.toLowerCase().includes(searchVal));
  }

  // Always review the newest placed bets first.
  list.sort((a, b) => String(b.bet_timestamp || b.gameday || '').localeCompare(String(a.bet_timestamp || a.gameday || '')) || b.bet_id.localeCompare(a.bet_id));

  // Pagination
  const totalItems = list.length;
  const totalPages = Math.ceil(totalItems / STATE.historyPageSize) || 1;
  if (STATE.historyPage > totalPages) STATE.historyPage = totalPages;

  const startIdx = (STATE.historyPage - 1) * STATE.historyPageSize;
  const pageItems = list.slice(startIdx, startIdx + STATE.historyPageSize);

  document.getElementById('history-page-info').textContent = `Showing ${totalItems > 0 ? startIdx + 1 : 0} to ${Math.min(startIdx + STATE.historyPageSize, totalItems)} of ${totalItems.toLocaleString()} bets`;

  if (pageItems.length === 0) {
    tbody.innerHTML = '<tr><td colspan="13" class="empty-state">No placed bets match these filters.</td></tr>';
    return;
  }

  pageItems.forEach(b => {
    const tr = document.createElement('tr');
    tr.className = 'clickable-row';
    tr.title = 'Open this strategy';
    tr.onclick = () => openStrategyModal(b.strategy_id);
    const badgeClass = b.result === 'WIN' ? 'badge-win' : (b.result === 'LOSS' ? 'badge-loss' : 'badge-push');
    const pnlClass = b.pnl > 0 ? 'color: var(--accent-green);' : (b.pnl < 0 ? 'color: var(--accent-red);' : '');
    tr.innerHTML = `
      <td style="font-size:0.72rem; font-family:var(--font-mono); color:var(--text-secondary);">${b.bet_id}</td>
      <td>'${String(b.season).slice(2)} W${b.week}</td>
      <td><span style="color:var(--accent-cyan); font-weight:700; font-family:var(--font-mono);">${b.username}</span></td>
      <td><strong>${b.matchup}</strong></td>
      <td><span class="tag-category">${b.market}</span></td>
      <td><code style="font-weight:700;">${b.selection}</code></td>
      <td style="font-family:var(--font-mono);">${b.price}</td>
      <td style="font-family:var(--font-mono);">${(b.model_prob * 100).toFixed(1)}%</td>
      <td style="color:var(--accent-green); font-family:var(--font-mono);">+${(b.edge * 100).toFixed(1)}%</td>
      <td style="font-family:var(--font-mono);">$${b.stake.toFixed(0)}</td>
      <td style="font-size:0.78rem;">${b.actual_score}</td>
      <td><span class="badge ${badgeClass}">${b.result}</span></td>
      <td style="${pnlClass} font-family:var(--font-mono); font-weight:700;">${b.pnl >= 0 ? '+' : ''}$${b.pnl.toFixed(2)}</td>
    `;
    tbody.appendChild(tr);
  });
}

function prevHistoryPage() {
  if (STATE.historyPage > 1) {
    STATE.historyPage--;
    renderHistoryTable();
  }
}

function nextHistoryPage() {
  const searchVal = (document.getElementById('history-search')?.value || '').toLowerCase();
  const strategyFilter = document.getElementById('history-strategy-filter')?.value || 'ALL';
  const seasonFilter = document.getElementById('history-season-filter')?.value || 'ALL';
  const resFilter = document.getElementById('history-res-filter')?.value || 'ALL';
  let list = STATE.ledger;
  if (strategyFilter !== 'ALL') list = list.filter(b => b.strategy_id === strategyFilter);
  if (seasonFilter !== 'ALL') list = list.filter(b => String(b.season) === seasonFilter);
  if (resFilter !== 'ALL') list = list.filter(b => b.result === resFilter);
  if (searchVal) list = list.filter(b => b.matchup.toLowerCase().includes(searchVal) || b.username.toLowerCase().includes(searchVal) || b.bet_id.toLowerCase().includes(searchVal));

  const totalPages = Math.ceil(list.length / STATE.historyPageSize);
  if (STATE.historyPage < totalPages) {
    STATE.historyPage++;
    renderHistoryTable();
  }
}

// ================= PERFORMANCE CHARTS =================
function renderPerformanceCharts() {
  const equityContainer = document.getElementById('perf-equity-chart');
  const catContainer = document.getElementById('perf-category-chart');
  const marketContainer = document.getElementById('perf-market-chart');
  const seasonContainer = document.getElementById('perf-season-chart');

  if (!equityContainer || STATE.leaderboard.length === 0) return;

  // 1. Top 5 Equity Chart
  const top5 = STATE.leaderboard.slice(0, 5);
  const colors = ['#3b82f6', '#10b981', '#06b6d4', '#f59e0b', '#8b5cf6'];
  equityContainer.innerHTML = generateMultiLineChartSVG(top5, colors, 600, 260);

  // 2. Category Bar Chart
  const catPnl = {};
  STATE.leaderboard.forEach(s => {
    catPnl[s.category] = (catPnl[s.category] || 0) + s.total_pnl;
  });
  catContainer.innerHTML = generateBarChartSVG(catPnl, 600, 260);

  // 3. Market Bar Chart - expanded to 7 market types
  const mktPnl = {
    'SPREAD': 0,
    'TOTAL': 0,
    'TEAM_TOTAL': 0,
    'PLAYER_PROP': 0,
    'ALT_SPREAD': 0,
    'KALSHI_SPREAD': 0,
    'KALSHI_TOTAL': 0,
    'KALSHI_LIVE': 0
  };
  STATE.ledger.forEach(b => {
    mktPnl[b.market] = (mktPnl[b.market] || 0) + b.pnl;
  });
  // Remove zero entries for cleaner chart
  Object.keys(mktPnl).forEach(k => { if (Math.abs(mktPnl[k]) < 1) delete mktPnl[k]; });
  marketContainer.innerHTML = generateBarChartSVG(mktPnl, 600, 260);

  // 4. Season Performance Chart
  const seasonPnl = {};
  STATE.ledger.forEach(b => {
    seasonPnl[b.season] = (seasonPnl[b.season] || 0) + b.pnl;
  });
  seasonContainer.innerHTML = generateBarChartSVG(seasonPnl, 600, 260);
}

// SVG Multi-Line Chart Generator
function generateMultiLineChartSVG(strategies, colors, width = 600, height = 260) {
  const padding = { top: 20, right: 140, bottom: 30, left: 60 };
  const w = width - padding.left - padding.right;
  const h = height - padding.top - padding.bottom;

  let minVal = 0;
  let maxVal = 1000;
  let maxLen = 0;

  strategies.forEach(s => {
    const curve = s.equity_curve || [];
    if (curve.length > maxLen) maxLen = curve.length;
    curve.forEach(pt => {
      const pnl = pt.pnl !== undefined ? pt.pnl : (pt.bankroll - s.initial_bankroll);
      if (pnl < minVal) minVal = pnl;
      if (pnl > maxVal) maxVal = pnl;
    });
  });

  const range = (maxVal - minVal) || 1;

  let pathsSvg = '';
  let legendSvg = '';

  strategies.forEach((s, i) => {
    const curve = s.equity_curve || [];
    if (curve.length === 0) return;
    const col = colors[i % colors.length];

    const pts = curve.map((pt, idx) => {
      const pnl = pt.pnl !== undefined ? pt.pnl : (pt.bankroll - s.initial_bankroll);
      const x = padding.left + (idx / (curve.length - 1 || 1)) * w;
      const y = padding.top + h - ((pnl - minVal) / range) * h;
      return `${x.toFixed(1)},${y.toFixed(1)}`;
    }).join(' ');

    pathsSvg += `<polyline fill="none" stroke="${col}" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" points="${pts}" />`;
    legendSvg += `
      <g transform="translate(${width - padding.right + 10}, ${padding.top + i * 20})">
        <rect width="12" height="12" rx="2" fill="${col}" />
        <text x="18" y="10" fill="#9ca3af" font-size="10" font-family="monospace">${s.username.substring(0, 15)}</text>
      </g>
    `;
  });

  // Zero line
  const zeroY = padding.top + h - ((0 - minVal) / range) * h;
  const zeroLine = `<line x1="${padding.left}" y1="${zeroY}" x2="${padding.left + w}" y2="${zeroY}" stroke="#4b5563" stroke-dasharray="3,3" />`;

  return `
    <svg class="chart-svg" viewBox="0 0 ${width} ${height}">
      ${zeroLine}
      <line x1="${padding.left}" y1="${padding.top}" x2="${padding.left}" y2="${padding.top + h}" class="chart-axis" />
      <line x1="${padding.left}" y1="${padding.top + h}" x2="${padding.left + w}" y2="${padding.top + h}" class="chart-axis" />
      <text x="${padding.left - 8}" y="${padding.top + 10}" text-anchor="end" class="chart-label">$${(maxVal / 1000).toFixed(0)}k</text>
      <text x="${padding.left - 8}" y="${zeroY + 4}" text-anchor="end" class="chart-label">$0</text>
      <text x="${padding.left - 8}" y="${padding.top + h}" text-anchor="end" class="chart-label">$${(minVal / 1000).toFixed(0)}k</text>
      <text x="${padding.left}" y="${height - 8}" class="chart-label">2010</text>
      <text x="${padding.left + w / 2}" y="${height - 8}" class="chart-label">2020</text>
      <text x="${padding.left + w}" y="${height - 8}" text-anchor="end" class="chart-label">2026 Live</text>
      ${pathsSvg}
      ${legendSvg}
    </svg>
  `;
}

// SVG Bar Chart Generator
function generateBarChartSVG(dataObj, width = 600, height = 260) {
  const keys = Object.keys(dataObj);
  const padding = { top: 20, right: 20, bottom: 50, left: 70 };
  const w = width - padding.left - padding.right;
  const h = height - padding.top - padding.bottom;

  let maxVal = 100;
  let minVal = 0;
  keys.forEach(k => {
    if (dataObj[k] > maxVal) maxVal = dataObj[k];
    if (dataObj[k] < minVal) minVal = dataObj[k];
  });

  const range = (maxVal - minVal) || 1;
  const barWidth = Math.min(40, (w / keys.length) * 0.7);

  let barsSvg = '';
  keys.forEach((k, i) => {
    const val = dataObj[k];
    const x = padding.left + (i + 0.5) * (w / keys.length) - barWidth / 2;
    const isPos = val >= 0;
    const col = isPos ? '#10b981' : '#ef4444';
    
    const zeroY = padding.top + h - ((0 - minVal) / range) * h;
    const barH = (Math.abs(val) / range) * h;
    const y = isPos ? zeroY - barH : zeroY;

    barsSvg += `
      <rect x="${x}" y="${y}" width="${barWidth}" height="${Math.max(2, barH)}" rx="2" fill="${col}" opacity="0.85" />
      <text x="${x + barWidth / 2}" y="${height - 30}" text-anchor="middle" class="chart-label" transform="rotate(-15, ${x + barWidth / 2}, ${height - 30})">${k.substring(0, 10)}</text>
      <text x="${x + barWidth / 2}" y="${isPos ? y - 4 : y + barH + 10}" text-anchor="middle" fill="${col}" font-size="9" font-family="monospace">${val >= 0 ? '+' : ''}$${(val / 1000).toFixed(0)}k</text>
    `;
  });

  const zeroY = padding.top + h - ((0 - minVal) / range) * h;
  return `
    <svg class="chart-svg" viewBox="0 0 ${width} ${height}">
      <line x1="${padding.left}" y1="${zeroY}" x2="${padding.left + w}" y2="${zeroY}" stroke="#4b5563" />
      <line x1="${padding.left}" y1="${padding.top}" x2="${padding.left}" y2="${padding.top + h}" class="chart-axis" />
      ${barsSvg}
    </svg>
  `;
}

// ================= RESEARCH LAB =================
function renderResearchLab() {
  const policy = document.getElementById('strategy-lab-policy');
  const candidateContainer = document.getElementById('strategy-candidates-container');
  const lab = STATE.strategyLab;

  if (policy && lab) {
    policy.innerHTML = `
      <div><span>Source snapshot</span><strong>${lab.source.loaded_games.toLocaleString()} games</strong><small>SHA-256 ${lab.source.sha256.slice(0, 12)}…</small></div>
      <div><span>Development</span><strong>${lab.policy.development_window}</strong><small>rule formation</small></div>
      <div><span>Validation</span><strong>${lab.policy.validation_window}</strong><small>first confirmation</small></div>
      <div><span>Untouched holdout</span><strong>${lab.policy.untouched_holdout_window}</strong><small>promotion gate</small></div>
    `;
  }

  if (candidateContainer && lab) {
    candidateContainer.innerHTML = lab.candidates.map(candidate => {
      const windows = Object.entries(candidate.windows).map(([name, result]) => `
        <tr>
          <td>${name}</td>
          <td>${result.seasons}</td>
          <td>${result.bets}</td>
          <td>${result.wins}-${result.losses}-${result.pushes}</td>
          <td>${result.win_rate_pct === null ? '—' : `${result.win_rate_pct.toFixed(2)}%`}</td>
          <td class="${result.roi_pct > 0 ? 'positive-value' : 'negative-value'}">${result.roi_pct > 0 ? '+' : ''}${result.roi_pct.toFixed(2)}%</td>
        </tr>`).join('');
      return `
        <article class="strategy-candidate-card">
          <div class="candidate-heading">
            <div><span class="eyebrow">${candidate.market} · ${candidate.strategy_id}</span><h3>${candidate.name}</h3></div>
            <span class="badge ${candidate.status === 'HOLDOUT_PASSED' ? 'badge-qualified' : 'badge-loss'}">${candidate.status.replaceAll('_', ' ')}</span>
          </div>
          <p><strong>Hypothesis:</strong> ${candidate.hypothesis}</p>
          <p><strong>Fixed rule:</strong> ${candidate.rule}</p>
          <div class="table-responsive compact-table">
            <table><thead><tr><th>Window</th><th>Seasons</th><th>Bets</th><th>W-L-P</th><th>Win rate</th><th>ROI</th></tr></thead><tbody>${windows}</tbody></table>
          </div>
          <div class="candidate-next"><strong>Next:</strong> ${candidate.next_step}</div>
          <small>No performance claim is published. Flat-stake historical output authorizes paper testing only.</small>
        </article>`;
    }).join('');
  }

  const container = document.getElementById('research-experiments-container');
  if (!container) return;
  container.innerHTML = '';

  STATE.researchExperiments.forEach(exp => {
    const box = document.createElement('div');
    box.style.cssText = 'background-color: var(--bg-input); border: 1px solid var(--border-color); border-radius: var(--radius); padding: 16px; margin-bottom: 16px;';
    
    let findingsHtml = '';
    if (exp.findings) {
      findingsHtml = '<ul style="margin: 8px 0 8px 20px; font-size: 0.82rem; color: var(--text-secondary);">';
      for (const [k, v] of Object.entries(exp.findings)) {
        findingsHtml += `<li><code>${k}</code>: ${JSON.stringify(v)}</li>`;
      }
      findingsHtml += '</ul>';
    }

    box.innerHTML = `
      <div style="display:flex; justify-content:space-between; align-items:flex-start; margin-bottom:6px;">
        <h4 style="color:var(--accent-cyan); font-size:1.05rem;">${exp.title}</h4>
        <span class="badge badge-win">${exp.status}</span>
      </div>
      <p style="font-size:0.83rem; color:var(--text-primary); margin-bottom:6px;"><strong>Hypothesis:</strong> ${exp.hypothesis}</p>
      <p style="font-size:0.78rem; color:var(--text-muted); margin-bottom:6px;"><strong>Sample Size:</strong> ${exp.sample_size} • <strong>Method:</strong> ${exp.methodology}</p>
      ${findingsHtml}
      <p style="font-size:0.82rem; color:#34d399; margin-top:6px;"><strong>Conclusion:</strong> ${exp.conclusion}</p>
      <p style="font-size:0.78rem; color:var(--accent-purple); margin-top:4px;"><strong>Action Taken:</strong> ${exp.action_taken}</p>
    `;
    container.appendChild(box);
  });
}

// ================= KALSHI DESK =================
function renderKalshiDesk() {
  const tbody = document.getElementById('kalshi-trades-body');
  if (!tbody) return;
  tbody.innerHTML = '';

  const sampleTrades = STATE.kalshiTrades.slice(0, 15);
  sampleTrades.forEach(t => {
    const tr = document.createElement('tr');
    const pnlClass = t.pnl >= 0 ? 'color: var(--accent-green);' : 'color: var(--accent-red);';
    tr.innerHTML = `
      <td><code>${t.contract}</code></td>
      <td><span class="badge ${t.side === 'YES' ? 'badge-win' : 'badge-loss'}">${t.side}</span></td>
      <td style="font-family:var(--font-mono);">${t.simulated_fill}¢</td>
      <td style="font-family:var(--font-mono);">${t.order_size}</td>
      <td style="font-family:var(--font-mono);">${t.settlement}¢</td>
      <td style="${pnlClass} font-family:var(--font-mono); font-weight:700;">${t.pnl >= 0 ? '+' : ''}$${t.pnl.toFixed(2)}</td>
    `;
    tbody.appendChild(tr);
  });
}

// ================= REGISTRY =================
function renderRegistry() {
  const tbody = document.getElementById('registry-table-body');
  if (!tbody) return;
  tbody.innerHTML = '';

  STATE.registry.forEach(src => {
    const tr = document.createElement('tr');
    const badgeClass = src.status === 'VERIFIED_PRIMARY' ? 'badge-win' : (src.status === 'SECONDARY' ? 'badge-qualified' : 'badge-loss');
    tr.innerHTML = `
      <td>
        <div style="font-weight:700; color:var(--text-primary);"><a href="${src.url}" target="_blank" style="color:var(--accent-cyan); text-decoration:none;">${src.name} ↗</a></div>
        <div style="font-size:0.75rem; color:var(--text-muted);">${src.provenance}</div>
      </td>
      <td style="font-size:0.8rem;">${src.data_type}</td>
      <td style="font-size:0.78rem; color:var(--text-secondary);">${src.cost_classification}</td>
      <td><span style="color:var(--accent-green); font-weight:700;">${src.reliability_rating}</span></td>
      <td style="font-size:0.8rem;">${src.historical_depth}</td>
      <td style="font-size:0.78rem; color:var(--text-muted);">${src.last_verification_date}</td>
      <td><span class="badge ${badgeClass}">${src.status.replace('_', ' ')}</span></td>
    `;
    tbody.appendChild(tr);
  });
}

// ================= VERIFICATION =================
function renderVerification() {
  const auditContainer = document.getElementById('audit-checks-container');
  if (auditContainer) {
    auditContainer.innerHTML = '';
    STATE.auditChecks.forEach(chk => {
      const box = document.createElement('div');
      box.style.cssText = 'background-color: var(--bg-input); border: 1px solid var(--border-color); border-radius: var(--radius); padding: 10px; font-size: 0.8rem;';
      box.innerHTML = `
        <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:4px;">
          <strong style="color:var(--text-primary);">${chk.name}</strong>
          <span class="badge ${chk.passed ? 'badge-win' : 'badge-loss'}">${chk.passed ? 'PASSED' : 'FAILED'}</span>
        </div>
        <div style="color:var(--text-muted); font-size:0.72rem;">${chk.category} • ${chk.details}</div>
      `;
      auditContainer.appendChild(box);
    });
  }

  const irrBody = document.getElementById('irregularities-table-body');
  if (irrBody) {
    irrBody.innerHTML = '';
    STATE.irregularities.forEach(irr => {
      const tr = document.createElement('tr');
      tr.innerHTML = `
        <td><code style="font-size:0.75rem;">${irr.id}</code></td>
        <td><strong>${irr.title}</strong></td>
        <td><span class="tag-category">${irr.category}</span></td>
        <td><span class="badge ${irr.severity === 'HIGH' ? 'badge-loss' : 'badge-waiting'}">${irr.severity}</span></td>
        <td style="font-size:0.8rem; color:var(--text-secondary);">${irr.description}</td>
        <td style="font-size:0.8rem; color:var(--accent-green);">${irr.resolution}</td>
      `;
      irrBody.appendChild(tr);
    });
  }
}

// ================= MODAL DEEP DIVE =================
function openStrategyModal(stratId) {
  const strat = STATE.strategies.find(s => s.id === stratId);
  const perf = STATE.leaderboard.find(p => p.id === stratId);
  if (!strat) return;

  const modal = document.getElementById('strat-modal');
  const content = document.getElementById('modal-strat-content');

  const pnlClass = perf && perf.total_pnl >= 0 ? 'color: var(--accent-green);' : 'color: var(--accent-red);';
  const placedBets = STATE.ledger
    .filter(b => b.strategy_id === stratId)
    .sort((a, b) => String(b.bet_timestamp || b.gameday || '').localeCompare(String(a.bet_timestamp || a.gameday || '')) || b.bet_id.localeCompare(a.bet_id));
  const upcomingBets = STATE.upcomingBets
    .filter(b => b.strategy_id === stratId)
    .sort((a, b) => `${a.gameday || ''}T${a.gametime || ''}`.localeCompare(`${b.gameday || ''}T${b.gametime || ''}`));
  const recentPlaced = placedBets.slice(0, 8);
  const nextTrades = upcomingBets.slice(0, 8);
  const placedStake = placedBets.reduce((sum, b) => sum + Number(b.stake || 0), 0);
  const upcomingStake = upcomingBets.reduce((sum, b) => sum + Number(b.stake || 0), 0);

  const placedRows = recentPlaced.map(b => `
    <tr>
      <td>${formatBetDate(b)}</td>
      <td><strong>${b.matchup}</strong></td>
      <td><span class="tag-category">${b.market}</span></td>
      <td><code>${b.selection}</code> <span class="price-muted">${b.price}</span></td>
      <td>$${Number(b.stake).toFixed(2)}</td>
      <td><span class="badge ${b.result === 'WIN' ? 'badge-win' : (b.result === 'LOSS' ? 'badge-loss' : 'badge-push')}">${b.result}</span></td>
      <td class="${b.pnl >= 0 ? 'positive-value' : 'negative-value'}">${b.pnl >= 0 ? '+' : ''}$${Number(b.pnl).toFixed(2)}</td>
    </tr>`).join('') || '<tr><td colspan="7" class="empty-state">No placed bets recorded for this strategy.</td></tr>';

  const upcomingRows = nextTrades.map(b => `
    <tr>
      <td>${formatBetDate(b, true)}</td>
      <td><strong>${b.matchup}</strong></td>
      <td><span class="tag-category">${b.market}</span></td>
      <td><code>${b.selection}</code> <span class="price-muted">${b.current_price}</span></td>
      <td class="positive-value">+${(Number(b.estimated_edge) * 100).toFixed(1)}%</td>
      <td>$${Number(b.stake).toFixed(2)}</td>
      <td><span class="badge ${b.status === 'READY_TO_BET' ? 'badge-ready' : (b.status === 'QUALIFIED' ? 'badge-qualified' : 'badge-watching')}">${b.status.replaceAll('_', ' ')}</span></td>
    </tr>`).join('') || '<tr><td colspan="7" class="empty-state">No upcoming trades proposed by this strategy.</td></tr>';

  content.innerHTML = `
    <div style="display:flex; justify-content:space-between; align-items:flex-start; margin-bottom:12px;">
      <div>
        <h2 style="color:var(--accent-cyan); font-family:var(--font-mono); font-size:1.4rem;">${strat.username}</h2>
        <h3 style="font-size:1.1rem; color:var(--text-primary);">${strat.name}</h3>
      </div>
      <span class="tag-version" style="font-size:0.9rem; padding:4px 10px;">Version: ${strat.version}</span>
    </div>

    <div style="display:grid; grid-template-columns: repeat(4, 1fr); gap:12px; background-color:var(--bg-input); padding:12px; border-radius:var(--radius); margin-bottom:16px;">
      <div>
        <span class="strat-metric-lbl">Total PnL</span>
        <div style="${pnlClass} font-size:1.2rem; font-weight:700; font-family:var(--font-mono);">${perf ? (perf.total_pnl >= 0 ? '+' : '') + '$' + perf.total_pnl.toLocaleString('en-US', {minimumFractionDigits:2}) : '$0.00'}</div>
      </div>
      <div>
        <span class="strat-metric-lbl">ROI</span>
        <div style="font-size:1.2rem; font-weight:700; font-family:var(--font-mono);">${perf ? perf.roi : 0}%</div>
      </div>
      <div>
        <span class="strat-metric-lbl">Win Rate</span>
        <div style="font-size:1.2rem; font-weight:700; font-family:var(--font-mono);">${perf ? perf.win_rate : 0}%</div>
      </div>
      <div>
        <span class="strat-metric-lbl">Total Bets</span>
        <div style="font-size:1.2rem; font-weight:700; font-family:var(--font-mono);">${perf ? perf.total_bets.toLocaleString() : 0}</div>
      </div>
    </div>

    <div style="margin-bottom:14px;">
      <h4 style="color:var(--text-secondary); text-transform:uppercase; font-size:0.75rem; margin-bottom:4px;">1. Research Hypothesis</h4>
      <p style="font-size:0.85rem; line-height:1.5; background-color:var(--bg-card); padding:10px; border-radius:var(--radius); border-left:3px solid var(--accent-cyan);">${strat.hypothesis}</p>
    </div>

    <div style="margin-bottom:14px;">
      <h4 style="color:var(--text-secondary); text-transform:uppercase; font-size:0.75rem; margin-bottom:4px;">2. Data Dependencies</h4>
      <p style="font-size:0.85rem; color:var(--text-primary);"><code>${(strat.data_sources || []).join(', ')}</code></p>
    </div>

    <div style="display:grid; grid-template-columns: 1fr 1fr; gap:12px; margin-bottom:14px;">
      <div style="background-color:var(--bg-card); padding:10px; border-radius:var(--radius);">
        <h4 style="color:var(--text-secondary); text-transform:uppercase; font-size:0.75rem; margin-bottom:4px;">3. Entry Rule</h4>
        <p style="font-size:0.82rem;">${strat.entry_rule}</p>
      </div>
      <div style="background-color:var(--bg-card); padding:10px; border-radius:var(--radius);">
        <h4 style="color:var(--text-secondary); text-transform:uppercase; font-size:0.75rem; margin-bottom:4px;">4. Pricing & Edge Rule</h4>
        <p style="font-size:0.82rem;">${strat.price_rule}</p>
      </div>
    </div>

    <div style="margin-bottom:14px;">
      <h4 style="color:var(--accent-red); text-transform:uppercase; font-size:0.75rem; margin-bottom:4px;">5. Post-Hoc Failure Analysis</h4>
      <p style="font-size:0.83rem; color:var(--text-secondary);">${strat.failure_analysis || 'No major failure clusters identified.'}</p>
    </div>

    <div style="margin-bottom:18px;">
      <h4 style="color:var(--accent-yellow); text-transform:uppercase; font-size:0.75rem; margin-bottom:4px;">6. Known Limitations</h4>
      <p style="font-size:0.83rem; color:var(--text-secondary);">${strat.limitations || 'None documented.'}</p>
    </div>

    <section class="strategy-bet-review" aria-label="Bets for ${strat.username}">
      <div class="bet-review-heading">
        <div>
          <span class="eyebrow">Strategy activity</span>
          <h3>Placed bets & upcoming trades</h3>
          <p>Review what this strategy executed and what it currently wants to place.</p>
        </div>
        <div class="bet-review-actions">
          <button class="btn btn-sm" onclick="openStrategyBetReview('${strat.id}', 'history')">All placed bets →</button>
          <button class="btn btn-sm btn-primary" onclick="openStrategyBetReview('${strat.id}', 'upcoming')">All upcoming trades →</button>
        </div>
      </div>

      <div class="activity-summary-grid">
        <div class="activity-summary"><span>Placed bets</span><strong>${placedBets.length.toLocaleString()}</strong><small>$${placedStake.toLocaleString('en-US', { maximumFractionDigits: 0 })} risked</small></div>
        <div class="activity-summary"><span>Upcoming trades</span><strong>${upcomingBets.length.toLocaleString()}</strong><small>$${upcomingStake.toLocaleString('en-US', { maximumFractionDigits: 0 })} proposed</small></div>
        <div class="activity-summary"><span>Ready now</span><strong>${upcomingBets.filter(b => b.status === 'READY_TO_BET').length}</strong><small>passed execution gates</small></div>
      </div>

      <div class="bet-review-block">
        <div class="bet-review-title"><span>Recently placed</span><small>Newest first</small></div>
        <div class="table-responsive compact-table">
          <table>
            <thead><tr><th>Placed</th><th>Matchup</th><th>Market</th><th>Selection / Price</th><th>Stake</th><th>Result</th><th>PnL</th></tr></thead>
            <tbody>${placedRows}</tbody>
          </table>
        </div>
      </div>

      <div class="bet-review-block">
        <div class="bet-review-title"><span>Upcoming trade intentions</span><small>Earliest game first</small></div>
        <div class="table-responsive compact-table">
          <table>
            <thead><tr><th>Game time</th><th>Matchup</th><th>Market</th><th>Selection / Price</th><th>Edge</th><th>Stake</th><th>Status</th></tr></thead>
            <tbody>${upcomingRows}</tbody>
          </table>
        </div>
      </div>
    </section>
  `;

  modal.classList.add('open');
}

function closeModal() {
  document.getElementById('strat-modal').classList.remove('open');
}

// ================= SIMULATOR SANDBOX =================
function runSandboxOrderSim() {
  const probInput = parseFloat(document.getElementById('sim-model-prob').value) / 100.0;
  const oddsInput = document.getElementById('sim-market-odds').value.trim();
  const gameSelect = document.getElementById('sim-game-select').value;
  const resBox = document.getElementById('sim-result-box');

  let impliedProb = 0.5238;
  let decOdds = 1.909;

  if (oddsInput.includes('¢')) {
    const cents = parseFloat(oddsInput.replace('¢', ''));
    impliedProb = cents / 100.0;
  } else {
    const num = parseFloat(oddsInput);
    if (num > 0) {
      decOdds = 1.0 + num / 100.0;
      impliedProb = 100.0 / (num + 100.0);
    } else {
      decOdds = 1.0 + 100.0 / Math.abs(num);
      impliedProb = Math.abs(num) / (Math.abs(num) + 100.0);
    }
  }

  const edge = probInput - impliedProb;
  const kellyPct = Math.max(0, (probInput * (decOdds - 1) - (1 - probInput)) / (decOdds - 1)) * 0.25;
  const recStake = Math.round(kellyPct * 10000);

  resBox.style.display = 'block';
  resBox.innerHTML = `
    <div style="font-weight:700; color:var(--accent-cyan); margin-bottom:4px;">SIMULATION EXECUTION RESULT</div>
    <div>Selected Matchup: <strong>${gameSelect}</strong></div>
    <div>Model Probability: <strong>${(probInput * 100).toFixed(1)}%</strong> | Market Implied: <strong>${(impliedProb * 100).toFixed(1)}%</strong></div>
    <div style="color:${edge > 0 ? 'var(--accent-green)' : 'var(--accent-red)'}; font-weight:700;">Calculated Edge: ${(edge * 100).toFixed(2)}%</div>
    <div>Recommended Quarter-Kelly Stake: <strong>$${recStake}</strong> (${(kellyPct * 100).toFixed(2)}% of $10,000 bankroll)</div>
    <div>Simulated Execution Slippage: <strong>0.5¢ / 0.0 pts</strong> • Market Liquidity: <strong>Available</strong></div>
  `;
}

// ================= EXPORT TOOLS =================
function exportLedgerCSV() {
  if (STATE.ledger.length === 0) return;
  const headers = ['bet_id', 'season', 'week', 'matchup', 'market', 'selection', 'price', 'model_prob', 'edge', 'stake', 'result', 'pnl'];
  let csv = headers.join(',') + '\n';
  STATE.ledger.forEach(b => {
    csv += [
      b.bet_id,
      b.season,
      b.week,
      `"${b.matchup}"`,
      b.market,
      `"${b.selection}"`,
      `"${b.price}"`,
      b.model_prob,
      b.edge,
      b.stake,
      b.result,
      b.pnl
    ].join(',') + '\n';
  });

  downloadFile(csv, 'nflcomp_simulated_bet_ledger.csv', 'text/csv');
}

function exportLedgerJSON() {
  const str = JSON.stringify(STATE.ledger, null, 2);
  downloadFile(str, 'nflcomp_simulated_bet_ledger.json', 'application/json');
}

function downloadFile(content, fileName, contentType) {
  const blob = new Blob([content], { type: contentType });
  const a = document.createElement('a');
  a.href = URL.createObjectURL(blob);
  a.download = fileName;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
}

// ================= EMPIRICAL STUDIES (derived vs declared) =================
const fmtNum = (value, digits = 2) => (value === null || value === undefined
  ? '—' : Number(value).toLocaleString('en-US', { minimumFractionDigits: digits, maximumFractionDigits: digits }));
const fmtPct = (value, digits = 2) => (value === null || value === undefined
  ? '—' : `${value >= 0 ? '+' : ''}${Number(value).toFixed(digits)}%`);
const valueClass = (value) => (value === null || value === undefined
  ? 'num-neutral' : (value > 0 ? 'num-positive' : (value < 0 ? 'num-negative' : 'num-neutral')));

// Each finding reports whichever measurement the study actually took. Nothing is
// inferred: a study without a rate column shows its means, and a bucket with no
// settled market price shows "n/a" instead of a fabricated PnL.
function studyMeasurement(finding) {
  const rateKey = Object.keys(finding).find(key => /_rate_pct$/.test(key));
  if (rateKey) {
    const ciKey = Object.keys(finding).find(key => key.endsWith('_ci95_pct'));
    const ci = ciKey ? finding[ciKey] : null;
    const label = rateKey.replace(/_pct$/, '').replaceAll('_', ' ');
    return `${label} ${fmtNum(finding[rateKey])}%` + (ci ? `<br><small class="muted">95% CI ${fmtNum(ci[0])}–${fmtNum(ci[1])}%</small>` : '');
  }
  if (finding.mean_total_points !== undefined) {
    return `mean total ${fmtNum(finding.mean_total_points)} pts`;
  }
  return '—';
}

function studyBucketLabel(name, finding) {
  const rangeKey = Object.keys(finding).find(key => /_range$/.test(key));
  if (rangeKey) return `${finding[rangeKey]} mph`;
  return name.replaceAll('_', ' ');
}

function renderEmpiricalStudies() {
  const report = STATE.empiricalStudies;
  const listEl = document.getElementById('empirical-studies-list');
  const detailBody = document.getElementById('empirical-studies-body');
  const declaredBody = document.getElementById('declared-assumptions-body');
  const countEl = document.getElementById('claim-studies-count');
  const studies = (report && report.studies) || [];

  if (countEl && report) countEl.textContent = studies.length.toLocaleString();

  if (listEl && report) {
    listEl.innerHTML = studies.map(study => {
      const findings = Object.entries(study.findings || {});
      const totalSample = findings.reduce((sum, [, f]) => sum + (f.sample || 0), 0);
      const strategies = (study.strategy_ids || []).map(id => `<code>${id}</code>`).join(' ');
      return `
        <article class="study-card">
          <div class="candidate-heading">
            <div>
              <span class="eyebrow">${study.market} · ${study.id} · ${study.seasons}</span>
              <h3>${study.title}</h3>
            </div>
            <span class="tag tag-derived">${study.evidence_class.replaceAll('_', ' ')}</span>
          </div>
          <p><strong>Result:</strong> ${study.headline}</p>
          <p><strong>Method:</strong> ${study.method}</p>
          <p class="muted"><strong>Snapshot columns used:</strong> ${(study.snapshot_columns || []).map(c => `<code>${c}</code>`).join(' ')}
            · ${findings.length} bucket(s), ${totalSample.toLocaleString()} observations</p>
          <p class="muted"><strong>Limitation:</strong> ${study.limitations}</p>
          <p class="muted"><strong>Speaks to:</strong> ${strategies || 'no catalogued persona yet'}</p>
        </article>`;
    }).join('');
  }

  if (detailBody && report) {
    detailBody.innerHTML = studies.map(study => Object.entries(study.findings || {}).map(([name, finding], index) => `
      <tr>
        <td>${index === 0 ? `<strong>${study.title}</strong><br><code>${study.id}</code>` : ''}</td>
        <td>${studyBucketLabel(name, finding)}</td>
        <td>${(finding.sample || 0).toLocaleString()}</td>
        <td>${studyMeasurement(finding)}</td>
        <td class="${valueClass(finding.flat_stake_pnl_usd)}">${finding.flat_stake_pnl_usd === undefined
          ? 'n/a — no settled price in the snapshot' : fmtMoney(finding.flat_stake_pnl_usd)}</td>
      </tr>`).join('')).join('');
  }

  if (declaredBody && report) {
    const rows = (report.declared_assumptions || []).map(entry => `
      <tr>
        <td><code>${entry.experiment_id}</code></td>
        <td>${entry.title || '—'}</td>
        <td><span class="tag tag-declared">${entry.evidence_class.replaceAll('_', ' ')}</span></td>
        <td>${entry.reason}</td>
      </tr>`).join('');
    const crossChecks = (report.cross_checks || []).map(check => `
      <tr>
        <td><code>${check.experiment_id}</code></td>
        <td>${check.metric}</td>
        <td><span class="tag ${check.agrees ? 'tag-derived' : 'tag-disputed'}">${check.agrees ? 'AGREES WITH SNAPSHOT' : 'DISPUTED BY SNAPSHOT'}</span></td>
        <td>dossier ${check.declared_in_dossier} vs snapshot ${check.re_derived_from_snapshot}${check.difference_pct_points === null ? '' : ` (${check.difference_pct_points > 0 ? '+' : ''}${check.difference_pct_points} pts)`}<br><small class="muted">${check.resolution}</small></td>
      </tr>`).join('');
    declaredBody.innerHTML = rows + crossChecks;
  }
}

// ================= RISK, CALIBRATION & CAPITAL SUFFICIENCY =================
function fmtMoney(value) {
  if (value === null || value === undefined) return '—';
  const sign = value < 0 ? '-' : '+';
  return `${sign}$${Math.abs(value).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

function stakeVersusQuarterKelly(persona) {
  if (persona.history_implies_no_positive_stake) return 'no positive Kelly size';
  const implied = persona.implied_quarter_kelly_stake_pct;
  const actual = persona.actual_stake_pct_of_initial_bankroll;
  if (implied === null || implied === undefined || !implied) return '—';
  return `${(actual / implied).toFixed(2)}× ¼-Kelly (${fmtNum(implied)}% implied)`;
}

function renderRiskAnalytics() {
  const report = STATE.riskAnalytics;
  if (!report) return;
  const policy = report.policy || {};
  const calibration = report.calibration || {};
  const summary = report.summary || {};
  const portfolio = report.portfolio || {};

  const cards = document.getElementById('risk-summary-cards');
  if (cards) {
    const cells = [
      ['Brier score', fmtNum(calibration.brier_score, 4),
        `${(calibration.settled_bets_with_model_probability || 0).toLocaleString()} settled bets carry a model probability; lower is better`],
      ['Expected calibration error', `${fmtNum(calibration.expected_calibration_error_pct_points, 2)} pts`,
        `Base win rate ${fmtNum((calibration.base_win_rate || 0) * 100)}% · log loss ${fmtNum(calibration.log_loss, 4)}`],
      ['Personas above the reporting floor', `${summary.personas_meeting_reporting_floor}/${summary.personas}`,
        `${policy.minimum_settled_bets} settled published bets minimum — below it no verdict is published`],
      ['Best annualised Sharpe', fmtNum(summary.best_sharpe_value, 3),
        `${summary.best_sharpe || '—'} (worst ${fmtNum(summary.worst_sharpe_value, 3)})`],
      ['Staking above implied ¼-Kelly', String(summary.personas_betting_above_implied_quarter_kelly),
        `${summary.personas_whose_history_implies_no_positive_stake} personas have a realised win rate consistent with no positive stake at all`],
      ['Published PnL concentration', `${fmtNum(portfolio.largest_abs_pnl_share_of_gross_movement_pct)}%`,
        `largest mover ${portfolio.largest_abs_pnl_persona || '—'} · Herfindahl ${fmtNum(portfolio.herfindahl_index_of_gross_pnl, 4)}`],
    ];
    cards.innerHTML = cells.map(([label, value, sub]) => `
      <div class="metric-card">
        <span class="metric-label">${label}</span>
        <span class="metric-value">${value}</span>
        <span class="metric-sub">${sub}</span>
      </div>`).join('');
  }

  const calibrationBody = document.getElementById('calibration-body');
  if (calibrationBody) {
    calibrationBody.innerHTML = (calibration.reliability_table || []).map(row => `
      <tr>
        <td>${row.decile}</td>
        <td>${row.range}</td>
        <td>${row.bets.toLocaleString()}</td>
        <td>${row.mean_model_prob === null ? '—' : `${(row.mean_model_prob * 100).toFixed(2)}%`}</td>
        <td>${row.observed_win_rate === null ? '—' : `${(row.observed_win_rate * 100).toFixed(2)}%`}</td>
        <td class="${valueClass(row.gap_pct_points)}">${row.gap_pct_points === null ? '—' : `${row.gap_pct_points > 0 ? '+' : ''}${row.gap_pct_points}`}</td>
      </tr>`).join('');
  }

  const byMarketBody = document.getElementById('calibration-market-body');
  if (byMarketBody) {
    byMarketBody.innerHTML = Object.entries(calibration.by_market || {}).map(([market, row]) => `
      <tr>
        <td><code>${market}</code></td>
        <td>${(row.settled_bets || 0).toLocaleString()}</td>
        <td>${fmtNum(row.brier_score, 4)}</td>
        <td>${fmtNum(row.log_loss, 4)}</td>
        <td>${fmtNum(row.expected_calibration_error_pct_points, 2)}</td>
        <td>${fmtNum((row.base_win_rate || 0) * 100)}%</td>
      </tr>`).join('');
  }

  const personaBody = document.getElementById('risk-personas-body');
  const personaNote = document.getElementById('risk-personas-note');
  if (personaBody) {
    const floor = policy.minimum_settled_bets || 0;
    const above = (report.personas || [])
      .filter(p => p.settled_bets >= floor)
      .sort((a, b) => b.settled_bets - a.settled_bets);
    const shown = above.slice(0, 30);
    if (personaNote) {
      personaNote.textContent = `Showing the ${shown.length} largest samples of ${above.length} personas at or above the `
        + `${floor}-settled-bet floor (of ${(report.personas || []).length} catalogued). `
        + 'A bootstrap interval that spans zero means the history is consistent with break-even.';
    }
    personaBody.innerHTML = shown.map(p => {
      const bootstrap = p.bootstrap || {};
      const ci = bootstrap.roi_pct_ci95 ? `${fmtNum(bootstrap.roi_pct_ci95[0])}% … ${fmtNum(bootstrap.roi_pct_ci95[1])}%` : '—';
      const spansZero = bootstrap.roi_pct_ci95 ? (bootstrap.roi_pct_ci95[0] <= 0 && bootstrap.roi_pct_ci95[1] >= 0) : false;
      return `
        <tr>
          <td><code>${p.username}</code><br><small class="muted">${p.strategy_id}</small></td>
          <td>${p.settled_bets.toLocaleString()}</td>
          <td>${p.win_rate === null ? '—' : `${(p.win_rate * 100).toFixed(1)}%`}</td>
          <td class="${valueClass(p.sharpe_annualised)}">${fmtNum(p.sharpe_annualised, 3)}</td>
          <td class="${valueClass(p.sortino_annualised)}">${fmtNum(p.sortino_annualised, 3)}</td>
          <td>${fmtNum(p.profit_factor, 3)}</td>
          <td>${fmtNum(p.max_drawdown_stake_units)} <small class="muted">(${p.longest_drawdown_bets} bets)</small></td>
          <td>${p.longest_losing_streak}</td>
          <td class="${valueClass(p.observed_roi_pct)}">${fmtPct(p.observed_roi_pct)}</td>
          <td class="${spansZero ? 'num-neutral' : valueClass(bootstrap.roi_pct_median)}">${ci}${spansZero ? ' <small class="muted">(spans 0)</small>' : ''}</td>
          <td>${bootstrap.probability_of_drawdown_pct === undefined ? '—' : `${bootstrap.probability_of_drawdown_pct}%`}</td>
          <td>${stakeVersusQuarterKelly(p)}</td>
        </tr>`;
    }).join('');
  }

  const concentration = document.getElementById('portfolio-concentration');
  if (concentration) {
    const correlations = (portfolio.top5_season_pnl_correlations || []).map(c =>
      `<li><code>${c.first}</code> vs <code>${c.second}</code>: r = ${fmtNum(c.pearson_r_by_season_pnl, 3)} over ${c.seasons} seasons</li>`).join('');
    concentration.innerHTML = `
      <p>${portfolio.personas_with_published_pnl} personas have published-window PnL — ${portfolio.personas_positive} positive, ${portfolio.personas_negative} negative — for ${fmtMoney(portfolio.published_pnl_total_usd)} net. Gross movement is ${fmtMoney(portfolio.pnl_magnitude_total_usd)}, of which the largest single persona explains ${fmtNum(portfolio.largest_abs_pnl_share_of_gross_movement_pct)}%; the Herfindahl index of gross PnL is ${fmtNum(portfolio.herfindahl_index_of_gross_pnl, 4)}.</p>
      <p class="muted">Per-season PnL correlation between the five largest personas (a shared market factor would show up here as positive co-movement):</p>
      <ul>${correlations || '<li>Not enough overlapping seasons to compute a correlation.</li>'}</ul>
      <p class="muted">Policy warning: ${policy.warning || 'n/a'}</p>`;
  }
}

// ================= FILTER HOOKS =================
function setupFilters() {
  document.getElementById('leader-search')?.addEventListener('input', renderLeaderboard);
  document.getElementById('leader-cat-filter')?.addEventListener('change', renderLeaderboard);

  document.getElementById('strat-search')?.addEventListener('input', renderStrategies);
  document.getElementById('strat-cat-filter')?.addEventListener('change', renderStrategies);

  document.getElementById('upcoming-strategy-filter')?.addEventListener('change', renderUpcomingBets);
  document.getElementById('upcoming-status-filter')?.addEventListener('change', renderUpcomingBets);
  document.getElementById('upcoming-market-filter')?.addEventListener('change', renderUpcomingBets);

  document.getElementById('history-search')?.addEventListener('input', () => { STATE.historyPage = 1; renderHistoryTable(); });
  document.getElementById('history-strategy-filter')?.addEventListener('change', () => { STATE.historyPage = 1; renderHistoryTable(); });
  document.getElementById('history-season-filter')?.addEventListener('change', () => { STATE.historyPage = 1; renderHistoryTable(); });
  document.getElementById('history-res-filter')?.addEventListener('change', () => { STATE.historyPage = 1; renderHistoryTable(); });

  // Table sorting
  document.querySelectorAll('th.sortable').forEach(th => {
    th.addEventListener('click', () => {
      const field = th.getAttribute('data-sort');
      if (STATE.leaderSortField === field) {
        STATE.leaderSortAsc = !STATE.leaderSortAsc;
      } else {
        STATE.leaderSortField = field;
        STATE.leaderSortAsc = false;
      }

      document.querySelectorAll('th.sortable').forEach(t => t.classList.remove('sort-asc', 'sort-desc'));
      th.classList.add(STATE.leaderSortAsc ? 'sort-asc' : 'sort-desc');

      renderLeaderboard();
    });
  });
}
