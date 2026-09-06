# BossAI Video Agent GitHub Growth Measurement

Use the repository's local read-only traffic report to separate discovery from Pilot conversion.

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/github-traffic-report.ps1
```

Save a local snapshot without committing it:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/github-traffic-report.ps1 `
  -SavePath .bossai-local/github-traffic/video-agent-YYYY-MM-DD.json
```

The report reads the authenticated GitHub account's repository Traffic API and returns:

- rolling 14-day Views / Unique Visitors;
- rolling 14-day Clones / Unique Cloners;
- top referrers and popular paths;
- point-in-time Stars / Forks / Open Issues;
- `v0.1.0-pilot` installer asset download count.

Interpret these separately:

- **low Views** → discovery problem;
- **Views but low Clones** → repository value proposition / trust problem;
- **Clones but low installer downloads** → Pilot install friction or insufficient product proof;
- **installer downloads but no Pilot Feedback** → onboarding / feedback conversion problem.

GitHub Traffic values are rolling 14-day windows. Release asset download counts are cumulative, but they do not prove that a download came from an external user or that installation/use succeeded.

The script does not publish content, modify releases, create Issues, send telemetry, read customer media, or store GitHub credentials. Local snapshots are written only when `-SavePath` is supplied and `.bossai-local/` is gitignored.
