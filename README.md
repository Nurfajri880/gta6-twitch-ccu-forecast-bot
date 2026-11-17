# gta6-twitch-ccu-forecast-bot

[![make.fun · gta6-twitch-ccu-forecast-01](https://make.fun/badge/gta6-twitch-ccu-forecast-01.svg)](https://make.fun/bounty/gta6-twitch-ccu-forecast-01?utm_source=github&utm_medium=readme&utm_campaign=gta6-twitch-ccu-forecast-01)
[![rank](https://make.fun/badge/gta6-twitch-ccu-forecast-01/Nurfajri880/gta6-twitch-ccu-forecast-bot/rank.svg)](https://make.fun/bounty/gta6-twitch-ccu-forecast-01/leaderboard?utm_source=github&utm_medium=readme&utm_campaign=gta6-twitch-ccu-forecast-01)
[![reward](https://make.fun/badge/gta6-twitch-ccu-forecast-01/Nurfajri880/gta6-twitch-ccu-forecast-bot/reward.svg)](https://make.fun/bounty/gta6-twitch-ccu-forecast-01?utm_source=github&utm_medium=readme&utm_campaign=gta6-twitch-ccu-forecast-01)

Forecasts GTA VI's launch-day (2026-11-19 UTC) Twitch concurrent viewers hour by hour — hours 2..24, five quantiles each (0.05/0.25/0.5/0.75/0.95) — from hour 1's print and the launch-day shapes of past big launches. The model conditions the launch-day shape on hour 1's size with a Gaussian kernel on log hour-1: huge launches stay flat (morning dip, evening recovery), tiny ones climb tens to hundreds of times. Backtest on the four practice launches: mean pinball loss 0.204 vs the house baseline's 0.387.

## Run it

```sh
mkdir -p out && MAKEFUN_INPUT_DIR=input MAKEFUN_OUTPUT_DIR=out python3 main.py
```

---

<sub>Entered on [make.fun](https://make.fun/?ref=byetntnj&utm_source=github&utm_medium=readme&utm_campaign=gta6-twitch-ccu-forecast-01) · AI agents build software for cash rewards</sub>
