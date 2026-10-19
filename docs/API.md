# Personal Life OS — REST API Reference (`/api/v1`)

All endpoints are served locally at `http://localhost:8000/api/v1`.
Interactive OpenAPI / Swagger documentation is also available at `http://localhost:8000/docs`.

---

## 1. Authentication & Scopes

You can authenticate using either:
1. **Browser Session Cookie** (`plos_session`, set automatically on `/api/v1/auth/login`), or
2. **Personal API Token Header**:
   ```http
   Authorization: Bearer plos_your_personal_token_here
   ```

### Supported Token Scopes
- `read:all`, `write:all`
- `read:habits`, `write:habits`
- `read:finance`, `write:finance`
- `read:screen_time`, `write:screen_time`
- `read:activities`, `write:activities`
- `read:goals`, `write:goals`
- `read:journal`, `write:journal`
- `read:wellbeing`, `write:wellbeing`
- `read:analytics`
- `write:imports`, `read:exports`

---

## 2. Core Endpoints Summary

| Method | Path | Required Scope | Description |
|--------|------|----------------|-------------|
| `GET` | `/api/v1/health` | Public | Local server health & initialization status |
| `GET` | `/api/v1/me` | Authenticated | Current user profile & preferences |
| `PATCH` | `/api/v1/me/preferences` | `write:all` | Update timezone, currency, theme, targets |
| `GET` | `/api/v1/dashboard` | `read:analytics` | Overview KPIs, comparisons, 14d charts |
| `POST` | `/api/v1/nlq` | `read:all` | Execute deterministic local natural-language query |
| `GET` | `/api/v1/habits` | `read:habits` | List habits with streaks & 30d completion rates |
| `POST` | `/api/v1/habits` | `write:habits` | Create a new habit |
| `POST` | `/api/v1/habits/{id}/entries` | `write:habits` | Log or update a habit completion entry |
| `GET` | `/api/v1/transactions` | `read:finance` | List financial transactions with filters |
| `POST` | `/api/v1/transactions` | `write:finance` | Record an expense, income, or account transfer |
| `GET` | `/api/v1/finance/summary` | `read:finance` | Consolidated exact Decimal financial summary |
| `GET` | `/api/v1/screen-time` | `read:screen_time` | List screen-time sessions |
| `POST` | `/api/v1/screen-time` | `write:screen_time` | Log a screen-time session |
| `GET` | `/api/v1/activities` | `read:activities` | List activity & focus sessions with overlap flags |
| `POST` | `/api/v1/activities/timer/start` | `write:activities` | Start persistent SQLite-backed focus timer |
| `POST` | `/api/v1/activities/timer/pause` | `write:activities` | Pause active focus timer |
| `POST` | `/api/v1/activities/timer/resume` | `write:activities` | Resume paused focus timer |
| `POST` | `/api/v1/activities/timer/stop` | `write:activities` | Stop and save active focus timer |
| `GET` | `/api/v1/goals` | `read:goals` | List goals, milestones, and deadline pace |
| `POST` | `/api/v1/goals/{id}/progress` | `write:goals` | Log quantitative progress toward a goal |
| `GET` | `/api/v1/wellbeing` | `read:wellbeing` | List daily sleep, mood, energy, and exercise logs |
| `POST` | `/api/v1/wellbeing` | `write:wellbeing` | Upsert daily wellbeing record |
| `GET` | `/api/v1/journal` | `read:journal` | List private journal entries and daily reviews |
| `POST` | `/api/v1/journal` | `write:journal` | Create journal reflection or 7-question review |
| `GET` | `/api/v1/insights` | `read:analytics` | Generate deterministic cross-domain insights |
| `GET` | `/api/v1/timeline` | `read:all` | Unified chronological event stream |
| `GET` | `/api/v1/constellation` | `read:all` | Personal Data Constellation graph nodes & edges |
| `GET` | `/api/v1/rhythm` | `read:all` | Personal Rhythm 7×24 weekday-vs-hour heatmap |
| `GET` | `/api/v1/wrapped` | `read:all` | Monthly, annual, or custom Life Wrapped report |
| `GET` | `/api/v1/export` | `read:exports` | Export dataset as JSON or CSV |
| `POST` | `/api/v1/backups` | `write:all` | Create verified online SQLite backup + manifest |

---

## 3. Code Examples

### curl
```bash
curl -X POST "http://localhost:8000/api/v1/transactions" \
  -H "Authorization: Bearer plos_your_token_here" \
  -H "Content-Type: application/json" \
  -d '{
    "amount": "350.00",
    "currency": "INR",
    "transaction_type": "expense",
    "category": "Food & Dining",
    "merchant": "Local Cafe",
    "payment_method": "UPI"
  }'
```

### Python (`httpx`)
```python
import httpx

TOKEN = "plos_your_token_here"
headers = {"Authorization": f"Bearer {TOKEN}"}

with httpx.Client(base_url="http://localhost:8000/api/v1", headers=headers) as client:
    # 1. Log a screen-time session
    r = client.post(
        "/screen-time",
        json={
            "app_name": "VS Code",
            "device": "desktop",
            "duration_minutes": 120,
            "category": "work",
            "productivity_type": "productive",
            "data_source": "api",
        },
    )
    print(r.status_code, r.json())

    # 2. Query natural-language analytics locally
    nlq = client.post("/nlq", json={"query": "How much did I spend on Food & Dining this month?"})
    print(nlq.json()["answer"])
```

### JavaScript (`fetch`)
```javascript
const res = await fetch("http://localhost:8000/api/v1/dashboard", {
  headers: {
    Authorization: "Bearer plos_your_token_here",
  },
});
const dashboard = await res.json();
console.log("Today's Focus Minutes:", dashboard.metrics.focus_time_today.minutes);
```

### Windows PowerShell (`Invoke-RestMethod`)
```powershell
$Headers = @{
    "Authorization" = "Bearer plos_your_token_here"
    "Content-Type"  = "application/json"
}

$Body = @{
    query = "Which habits have the highest streak?"
} | ConvertTo-Json

$Result = Invoke-RestMethod -Method Post -Uri "http://localhost:8000/api/v1/nlq" -Headers $Headers -Body $Body
Write-Output $Result.answer
```

