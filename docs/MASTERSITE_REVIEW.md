# MasterSite review

**Reviewed:** 2026-09-21 UTC from `https://buffedlizard55-lab.github.io/MasterSite/`.

## Verified directory facts

The directory rendered 49 verified sites, including a Sports Data & Scoreboards category and a Markets & Trading Research category. The directory itself is an index, not an NFL data feed; each project must be verified independently before it can supply a signal.

## Potentially useful projects

| Project | Decision | Reason |
|---|---|---|
| `KalshiPaperSim` | Research / execution-method reference | Describes captured Kalshi quotes, order-book depth, candlesticks, fee calculations, replay, and paper fills. It is not evidence for an NFL price unless the specific contract snapshot exists. |
| `SFWeather` | Candidate weather source | Potential NWS-backed forecast/observation pipeline. Use only with a timestamped stadium mapping and retained forecast payload. |
| NFL Injury Report | Candidate injury source | Relevant to injury and availability research. Requires independent official/team confirmation and timestamped reports. |
| NFL Scoreboard | Discovery-only | The directory describes an ESPN scoreboard integration. It is not treated as an official source and must be cross-checked before settlement. |
| Sports Pred | Discovery-only | Useful for finding public claims; claims are hypotheses until rules, data, and out-of-sample results are reproduced. |

## Rejected or not directly reusable

- NBA, NCAA, MLB, FDA, Gold, TheLeap, and other non-NFL projects are not used as NFL facts.
- A directory description is not a source observation and cannot establish an odds price, fill, injury, result, or profitable edge.
- Kalshi projects are not imported as historical NFL prices; only retained timestamped contract/order-book evidence could support a Kalshi paper fill.

The corresponding source records are in `data/registry.json`. Any future collector must store the raw payload, retrieval timestamp, availability timestamp, source hash, and verification status before it can be promoted from discovery to model input.
