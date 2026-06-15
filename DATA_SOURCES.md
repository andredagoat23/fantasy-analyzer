# Data Sources - Fantasy Analyzer v1

## 1. Sleeper API
- URL: https://api.sleeper.app/v1/players/nfl
- Docs: https://docs.sleeper.com
- Auth required: No 
- What it gives me: It gives you a JSON of all the players in the NFL
- Columns I'll use: Name, Position, team, age, bye week, status (active/injured)
- Rate limit / gotcha: It says you dont need to call it more than once a day

## 2. nflreadpy
- Install: pip3 install nflreadpy
- Docs: https://github.com/nflverse/nflreadpy
- Auth required: 
- What it gives me: play by play data for whatever seasons I want
- Functions I'll use: A lot of them
- Rate limit / gotcha: probably like 60ish seconds

## 3. Fantasy Football Calculator (FFC) ADP API
- URL: https://fantasyfootballcalculator.com/api/v1/adp/ppr?teams=10&year=2026
- Docs: https://help.fantasyfootballcalculator.com/article/42-adp-rest-api
- Auth required: No Auth but attribution requested
- What it gives me: ADP of every player drafted and other draft analytics
- Columns I'll use: adp, times drafted, highest and lowest drafted, etc...
- Rate limit / gotcha: probably around a minute

## 4. FantasyPros ECR (Expert Consensus Rankings)
- URL: https://www.fantasypros.com/nfl/rankings/consensus-cheatsheets.php
- Auth required: None (I think)
- What it gives me: ADP from experts
- How I get it into Python: Download and save in predictable place
- Update cadence: Redownload periodically due to no free API
- Notes: Names slightly different so youll need to flag that
- Columns Availible: Rank, Player Name, Pos, Strength of Schedule, ECR vs ADP