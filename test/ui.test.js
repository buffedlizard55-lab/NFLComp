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

  // 4. Check registry.json
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
