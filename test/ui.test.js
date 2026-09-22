/**
 * NFLComp UI & Data Contract Test Suite
 * Validates:
 * - JSON schema validity of all published competition data
 * - Leaderboard ranking and numeric fields
 * - Upcoming bets status flags
 * - Registry completeness
 * - Static file presence for GitHub Pages
 */

const fs = require('fs');
const path = require('path');
const assert = require('assert');

function runTests() {
  console.log('Running NFLComp UI & Data Test Suite...');

  // 1. Check summary.json
  const summaryPath = path.join(__dirname, '..', 'data', 'summary.json');
  assert.ok(fs.existsSync(summaryPath), 'data/summary.json must exist');
  const summary = JSON.parse(fs.readFileSync(summaryPath, 'utf8'));
  assert.strictEqual(summary.current_season, 2026);
  assert.strictEqual(summary.current_week, 2);
  assert.ok(summary.total_strategies >= 20, 'At least 20 strategies tracked');
  assert.ok(summary.total_simulated_bets > 40000, 'Over 40k bets in backtest/forward test');
  console.log('✓ summary.json validated');

  // 2. Check leaderboard.json
  const leaderboardPath = path.join(__dirname, '..', 'data', 'leaderboard.json');
  assert.ok(fs.existsSync(leaderboardPath), 'data/leaderboard.json must exist');
  const leaderboard = JSON.parse(fs.readFileSync(leaderboardPath, 'utf8'));
  assert.ok(leaderboard.length >= 20, 'Leaderboard must contain all strategy personas');
  for (const s of leaderboard) {
    assert.ok(s.id, 'Strategy must have id');
    assert.ok(s.username.startsWith('@'), 'Username must start with @');
    assert.strictEqual(typeof s.total_pnl, 'number');
    assert.strictEqual(typeof s.roi, 'number');
    assert.strictEqual(typeof s.win_rate, 'number');
    assert.ok(Array.isArray(s.equity_curve), 'Strategy must have equity curve');
  }
  console.log(`✓ leaderboard.json validated (${leaderboard.length} strategies)`);

  // 3. Check upcoming_bets.json
  const upcomingPath = path.join(__dirname, '..', 'data', 'upcoming_bets.json');
  assert.ok(fs.existsSync(upcomingPath), 'data/upcoming_bets.json must exist');
  const upcoming = JSON.parse(fs.readFileSync(upcomingPath, 'utf8'));
  assert.ok(upcoming.length > 0, 'Must have active upcoming signals');
  for (const u of upcoming) {
    assert.ok(u.bet_id, 'Upcoming bet must have bet_id');
    assert.ok(u.matchup, 'Must have matchup');
    assert.ok(['READY_TO_BET', 'QUALIFIED', 'WATCHING'].includes(u.status), 'Valid status');
  }
  console.log(`✓ upcoming_bets.json validated (${upcoming.length} upcoming signals)`);

  // 4. Check placed-bet ledger and strategy linkage
  const ledgerPath = path.join(__dirname, '..', 'data', 'bets_ledger.json');
  assert.ok(fs.existsSync(ledgerPath), 'data/bets_ledger.json must exist');
  const ledger = JSON.parse(fs.readFileSync(ledgerPath, 'utf8'));
  assert.ok(ledger.length > 0, 'Placed-bet ledger must not be empty');
  const strategyIds = new Set(leaderboard.map(s => s.id));
  for (const bet of ledger) {
    assert.ok(bet.strategy_id, 'Placed bet must have strategy_id');
    assert.ok(strategyIds.has(bet.strategy_id), `Placed bet strategy must appear on leaderboard: ${bet.strategy_id}`);
    assert.ok(bet.bet_timestamp, 'Placed bet must have a placement timestamp');
    assert.strictEqual(typeof bet.stake, 'number');
    assert.strictEqual(typeof bet.pnl, 'number');
  }
  for (const bet of upcoming) {
    assert.ok(bet.strategy_id, 'Upcoming trade must have strategy_id');
    assert.ok(strategyIds.has(bet.strategy_id), `Upcoming strategy must appear on leaderboard: ${bet.strategy_id}`);
  }
  console.log(`✓ bets_ledger.json validated (${ledger.length} placed bets linked to strategies)`);

  // 4b. Ledger hash chain + manifest reconciliation
  const manifestPath = path.join(__dirname, '..', 'data', 'ledger_manifest.json');
  assert.ok(fs.existsSync(manifestPath), 'data/ledger_manifest.json must exist');
  const manifest = JSON.parse(fs.readFileSync(manifestPath, 'utf8'));
  // Link continuity is checked here; the record hashes are re-derived by the
  // same implementation that wrote them, so no second serialiser can drift.
  let chainHead = null;
  let broken = 0;
  for (const bet of ledger) {
    assert.ok(bet.hash && bet.previous_hash, 'every published record must carry its chain fields');
    if (chainHead !== null && bet.previous_hash !== chainHead) broken += 1;
    chainHead = bet.hash;
  }
  assert.strictEqual(broken, 0, 'published ledger links must be continuous');
  assert.strictEqual(manifest.published_bets, ledger.length);
  assert.strictEqual(manifest.chain_head_hash, chainHead);
  assert.strictEqual(manifest.bets_outside_published_window, manifest.all_time_bets - ledger.length);
  assert.ok(Object.keys(manifest.source_files || {}).length > 0, 'manifest must cite source snapshots');
  const ledgerPnl = Math.round(ledger.reduce((sum, b) => sum + b.pnl, 0) * 100) / 100;
  assert.ok(Math.abs(manifest.published_pnl - ledgerPnl) <= 0.011 * ledger.length + 0.01,
    'manifest published PnL must re-derive from the published ledger');
  const { execFileSync } = require('child_process');
  const verify = execFileSync('python3', ['-m', 'engine.ledger', '--verify', ledgerPath],
    { cwd: path.join(__dirname, '..'), encoding: 'utf8' });
  assert.ok(verify.includes('chain OK'), `engine.ledger must re-derive the published chain: ${verify}`);
  console.log(`✓ ledger hash chain verified (${ledger.length} linked records, head ${chainHead.slice(0, 12)}…)`);

  // 4c. Published site claims must match the data
  const htmlClaims = fs.readFileSync(path.join(__dirname, '..', 'index.html'), 'utf8');
  const claimValue = (id) => {
    const match = htmlClaims.match(new RegExp(`id="${id}"[^>]*>([^<]+)<`));
    return match ? match[1].trim() : null;
  };
  const personas = String(summary.total_strategies);
  for (const id of ['claim-personas', 'claim-personas-dash', 'claim-personas-cta', 'claim-personas-heading']) {
    assert.strictEqual(claimValue(id), personas, `${id} must match summary.total_strategies`);
  }
  assert.strictEqual(claimValue('claim-upcoming'), String(summary.total_upcoming_bets));
  assert.strictEqual(claimValue('claim-history'), `${Math.round(ledger.length / 1000)}k`);
  assert.strictEqual(claimValue('claim-registry'), String(
    JSON.parse(fs.readFileSync(path.join(__dirname, '..', 'data', 'registry.json'), 'utf8')).length));
  const weekSlice = summary.current_week_slice;
  const weekSignals = upcoming.filter(b => b.season === weekSlice.season && b.week === weekSlice.week);
  assert.strictEqual(Number(claimValue('claim-week-games').replace(/,/g, '')),
    new Set(weekSignals.map(b => b.game_id)).size, 'current-week game count must match the signals');
  assert.strictEqual(Number(claimValue('claim-week-signals').replace(/,/g, '')), weekSignals.length);
  assert.strictEqual(claimValue('claim-season-span'), summary.season_span.replace('-', '\u2013'));
  const boundClaims = ['claim-personas', 'claim-personas-dash', 'claim-personas-cta',
    'claim-personas-heading', 'claim-upcoming', 'claim-history', 'claim-registry',
    'claim-week-games', 'claim-week-signals', 'claim-season-span'];
  for (const id of boundClaims) assert.ok(claimValue(id), `${id} must be bound in index.html`);
  console.log(`✓ index.html prose claims match the published data (${boundClaims.length} bound numbers)`);

  // 5. Check strategy review UI contracts
  const html = fs.readFileSync(path.join(__dirname, '..', 'index.html'), 'utf8');
  const appJs = fs.readFileSync(path.join(__dirname, '..', 'app.js'), 'utf8');
  assert.ok(html.includes('id="upcoming-strategy-filter"'), 'Upcoming view must expose a strategy filter');
  assert.ok(html.includes('id="history-strategy-filter"'), 'History view must expose a strategy filter');
  assert.ok(appJs.includes('Placed bets & upcoming trades'), 'Strategy modal must review placed and upcoming trades');
  assert.ok(appJs.includes("openStrategyBetReview('${strat.id}', 'history')"), 'Strategy modal must link to filtered history');
  assert.ok(appJs.includes("openStrategyBetReview('${strat.id}', 'upcoming')"), 'Strategy modal must link to filtered upcoming bets');
  assert.ok(appJs.includes('Always review the newest placed bets first.'), 'History must explicitly sort newest first');
  console.log('✓ strategy bet review UI contracts validated');

  // 6. Check reproducible strategy lab output
  const labPath = path.join(__dirname, '..', 'data', 'strategy_lab.json');
  assert.ok(fs.existsSync(labPath), 'data/strategy_lab.json must exist');
  const lab = JSON.parse(fs.readFileSync(labPath, 'utf8'));
  assert.strictEqual(lab.research_class, 'PAPER_TRADING_STRATEGY_LAB');
  assert.ok(lab.source.sha256, 'Strategy lab must identify its exact source snapshot');
  assert.strictEqual(lab.policy.untouched_holdout_window, '2023-2025');
  assert.ok(lab.candidates.length >= 2, 'Strategy lab must continuously test multiple candidates');
  for (const candidate of lab.candidates) {
    assert.ok(candidate.rule, 'Candidate must declare a fixed rule');
    assert.ok(candidate.windows.development, 'Candidate must have a development result');
    assert.ok(candidate.windows.validation, 'Candidate must have a validation result');
    assert.ok(candidate.windows.holdout, 'Candidate must have an untouched holdout result');
    assert.strictEqual(candidate.performance_claim, null, 'Historical candidate must not publish a future performance claim');
  }
  assert.ok(html.includes('id="strategy-candidates-container"'), 'Research view must display strategy candidates');
  assert.ok(html.includes('nav-tab nav-tab-focus active" data-tab="research"'), 'Strategy Lab must be the default primary view');
  console.log(`✓ strategy lab validated (${lab.candidates.length} reproducible candidates)`);

  // 7. Check registry.json
  const regPath = path.join(__dirname, '..', 'data', 'registry.json');
  assert.ok(fs.existsSync(regPath), 'data/registry.json must exist');
  const registry = JSON.parse(fs.readFileSync(regPath, 'utf8'));
  assert.ok(registry.length >= 10, 'Registry must have at least 10 sources');
  for (const r of registry) {
    assert.ok(r.name, 'Source must have name');
    assert.ok(r.url, 'Source must have url');
    assert.ok(r.reliability_rating, 'Must have reliability rating');
  }
  console.log(`✓ registry.json validated (${registry.length} data sources)`);

  // 5. Check irregularities.json
  const irrPath = path.join(__dirname, '..', 'data', 'irregularities.json');
  assert.ok(fs.existsSync(irrPath), 'data/irregularities.json must exist');
  const irr = JSON.parse(fs.readFileSync(irrPath, 'utf8'));
  assert.ok(irr.length >= 3, 'Must have documented irregularities');
  console.log(`✓ irregularities.json validated (${irr.length} irregularities tracked)`);

  // 6. Check research_experiments.json
  const expPath = path.join(__dirname, '..', 'data', 'research_experiments.json');
  assert.ok(fs.existsSync(expPath), 'data/research_experiments.json must exist');
  const experiments = JSON.parse(fs.readFileSync(expPath, 'utf8'));
  assert.ok(experiments.length >= 3, 'Must have research experiments');
  console.log(`✓ research_experiments.json validated (${experiments.length} experiments)`);

  // 7. Check kalshi_trades.json
  const kalshiPath = path.join(__dirname, '..', 'data', 'kalshi_trades.json');
  assert.ok(fs.existsSync(kalshiPath), 'data/kalshi_trades.json must exist');
  const kalshi = JSON.parse(fs.readFileSync(kalshiPath, 'utf8'));
  assert.ok(kalshi.length > 0, 'Must have simulated Kalshi trades');
  console.log(`✓ kalshi_trades.json validated (${kalshi.length} trades)`);

  console.log('\nALL UI & DATA CONTRACT TESTS PASSED SUCCESSFULLY! ✅');
}

runTests();
