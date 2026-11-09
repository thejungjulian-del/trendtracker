# TrendTracker

My first trend tool: a small dashboard that captures clothing and social trends every day, so you can see what's rising instead of what's loud today. It pulls the day's trending searches from Google Trends for free, flags the fashion-related ones, and saves each capture as a dated snapshot so the Rising panel can compare against the day before. TikTok and Instagram finds go in by hand through a form.

## Run it

```
pip install -r requirements.txt
python3 app.py          # http://127.0.0.1:5005
python3 collector.py    # take one capture without opening the dashboard
```

No API keys needed. Snapshots go into a local `trends.db` that's created on first run. The Rising panel needs at least two capture days.

## Status

Shelved. TikTok's free Creative Center endpoint now needs a signed token, so that panel usually comes back empty, and Instagram has no public trending feed. Both are manual input. Google Trends is the only automatic source that works.

Portfolio: https://thejungjulian-del.github.io/portfolio/
