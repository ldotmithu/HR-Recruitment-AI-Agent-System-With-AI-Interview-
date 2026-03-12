# Dashboard Reset Commands

## Quick Reference

Use these terminal commands to manage your dashboard data:

---

## 🗑️ Clear All Candidates

Deletes **ALL** candidate records from the database:

```bash
curl -X POST "http://localhost:8000/reset-dashboard/"
```

**Response:**
```json
{
  "message": "Dashboard reset successfully. Deleted 15 candidates."
}
```

---

## 🧹 Clear Old Data

Delete candidates older than a specific number of days:

### Clear data older than 7 days
```bash
curl -X POST "http://localhost:8000/reset-dashboard/?days=7"
```

### Clear data older than 30 days
```bash
curl -X POST "http://localhost:8000/reset-dashboard/?days=30"
```

### Clear data older than 1 day (yesterday's data)
```bash
curl -X POST "http://localhost:8000/reset-dashboard/?days=1"
```

**Response:**
```json
{
  "message": "Dashboard reset successfully. Deleted 8 candidates."
}
```

---

## 📊 View Candidates

### Get all candidates
```bash
curl "http://localhost:8000/candidates/"
```

### Get only today's candidates
```bash
curl "http://localhost:8000/candidates/?days=1"
```

### Get last week's candidates
```bash
curl "http://localhost:8000/candidates/?days=7"
```

---

## 🔄 Workflow Examples

### Daily Cleanup Routine
```bash
# Clear data older than 7 days every morning
curl -X POST "http://localhost:8000/reset-dashboard/?days=7"
```

### Weekly Full Reset
```bash
# Clear everything every Monday
curl -X POST "http://localhost:8000/reset-dashboard/"
```

### Check Today's Progress
```bash
# View only today's candidates
curl "http://localhost:8000/candidates/?days=1"
```

---

## 🛠️ Advanced Usage

### Using PowerShell (Windows)
```powershell
# Clear all candidates
Invoke-RestMethod -Method POST -Uri "http://localhost:8000/reset-dashboard/"

# Clear old data
Invoke-RestMethod -Method POST -Uri "http://localhost:8000/reset-dashboard/?days=7"

# Get candidates
Invoke-RestMethod -Uri "http://localhost:8000/candidates/"
```

### Using Python
```python
import requests

# Clear all candidates
response = requests.post("http://localhost:8000/reset-dashboard/")
print(response.json())

# Clear candidates older than 7 days
response = requests.post("http://localhost:8000/reset-dashboard/", params={"days": 7})
print(response.json())

# Get today's candidates
response = requests.get("http://localhost:8000/candidates/", params={"days": 1})
candidates = response.json()
print(f"Found {len(candidates)} candidates today")
```

---

## 📝 Notes

- **No confirmation required** - Commands execute immediately
- **Permanent deletion** - There's no undo, so be careful
- **Server must be running** - Ensure backend is running at `http://localhost:8000`
- **Returns count** - Response tells you how many records were deleted

---

## ✅ Verification

After running a reset command, refresh your dashboard to see the changes:

1. Open `http://localhost:8501` in your browser
2. Press `Ctrl+R` or `F5` to reload the page
3. Verify the old data is gone

---

## 🆘 Troubleshooting

### Error: "Connection refused"
**Solution**: Make sure the backend server is running:
```bash
uvicorn backend.main_updated:app --reload --port 8000
```

### Error: "Reset Error: no such column: created_at"
**Solution**: The database migration didn't run. Restart the backend server.

### No candidates deleted (deleted: 0)
**Possible reasons**:
- Database is already empty
- The `days` parameter is too small (e.g., trying to delete data older than 30 days when all data is recent)
- The `created_at` column has NULL values (run the migration again)

---

## 🎯 Best Practices

1. **Daily cleanup**: Run `?days=7` every morning to keep the dashboard clean
2. **Before testing**: Clear all data to start fresh
3. **After hiring cycle**: Clear all data when starting a new recruitment round
4. **Check first**: Use `GET /candidates/` to see what will be deleted before running reset

---

**Quick Copy-Paste Commands:**

```bash
# Most common: Clear all data
curl -X POST "http://localhost:8000/reset-dashboard/"

# Second most common: Clear old data (7+ days)
curl -X POST "http://localhost:8000/reset-dashboard/?days=7"

# View today's candidates
curl "http://localhost:8000/candidates/?days=1"
```
