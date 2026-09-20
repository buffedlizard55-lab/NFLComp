# Mathematical & Quantitative Methodology — NFLComp

This manual describes the statistical models, execution logic, probability calculations, and bankroll management rules implemented across the NFLComp engine.

---

## 1. FiveThirtyEight Margin-of-Victory Elo Engine

The platform implements the Elo rating model with margin-of-victory multiplier and dynamic quarterback value adjustments:

### Rating Formula
For team ratings $R_{home}$ and $R_{away}$, with a home-field advantage bonus $H = 48.0$:

$$R_{home, adj} = R_{home} + H$$

The win expectation for the home team is:

$$P(Home) = \frac{1}{1 + 10^{(R_{away} - R_{home, adj}) / 400}}$$

The expected point spread $\hat{S}_{home}$ (points by which home is expected to win) is modeled linearly:

$$\hat{S}_{home} = \frac{R_{home, adj} - R_{away}}{25.0}$$

### Margin of Victory K-Multiplier
The post-game rating adjustment uses:

$$K = 20.0 \times \frac{\ln(|M| + 1)}{2.2 / ((\Delta R \times 0.001) + 2.2)}$$

where $M$ is the actual point differential ($Score_{home} - Score_{away}$) and $\Delta R = R_{winner} - R_{loser}$.

---

## 2. Bivariate Poisson Scoring Grid

To price point spreads, totals, and Kalshi bracket contracts without Gaussian normality assumptions, the engine uses bivariate Poisson distributions for team scoring:

$$P(X = x, Y = y) = \frac{\lambda_1^x e^{-\lambda_1}}{x!} \times \frac{\lambda_2^y e^{-\lambda_2}}{y!}$$

where $\lambda_1$ (Home Expected Points) and $\lambda_2$ (Away Expected Points) are calibrated from:

$$\lambda_1 = \text{LeagueAvg} \times \left(\frac{\text{OffRating}_{home}}{\text{LeagueAvg}}\right) \times \left(\frac{\text{DefRating}_{away}}{\text{LeagueAvg}}\right) \times 1.08$$

$$\lambda_2 = \text{LeagueAvg} \times \left(\frac{\text{OffRating}_{away}}{\text{LeagueAvg}}\right) \times \left(\frac{\text{DefRating}_{home}}{\text{LeagueAvg}}\right) \times 0.92$$

Spreads and totals are derived by integrating over the joint discrete probability matrix $M_{x, y}$ for $0 \le x, y \le 70$.

---

## 3. Wind & Cold Temperature Scoring Attenuation

Wind drag alters football aerodynamics, reducing passing velocity and field goal range non-linearly:

$$\text{ExpectedTotal}_{adj} = \text{BaseTotal} - \Delta_{wind} - \Delta_{temp}$$

where:
$$\Delta_{wind} = \begin{cases} 0 & \text{if } W < 12.0 \text{ mph} \\ (W - 12.0) \times 0.35 & \text{if } 12.0 \le W < 20.0 \text{ mph} \\ 2.8 + (W - 20.0) \times 0.65 & \text{if } W \ge 20.0 \text{ mph} \end{cases}$$

$$\Delta_{temp} = \begin{cases} 0 & \text{if } T \ge 32^\circ\text{F} \\ \frac{32.0 - T}{10.0} \times 0.8 & \text{if } T < 32^\circ\text{F} \end{cases}$$

---

## 4. Staking & Bankroll Sizing (Quarter-Kelly)

To maximize geometric growth rate while controlling risk of ruin, strategies employ Quarter-Kelly sizing:

$$f^* = \frac{1}{4} \times \frac{b \cdot p - q}{b}$$

where:
- $p$ = Model estimated win probability
- $q = 1 - p$
- $b$ = Decimal odds $- 1$ (e.g. $b = 0.909$ for $-110$ American odds)
- Max single-bet cap: $5.0\%$ of current virtual bankroll ($f^* \le 0.05$)
- Minimum edge threshold: $\ge 2.5\%$ positive edge.
