# vuln-flask-app

A minimal intentionally vulnerable Flask web app for the P8 DevSecOps assignment.
**Do not deploy this anywhere public.**

## Intentional vulnerabilities

| Vulnerability | Location | Tool | Rule | Severity |
|---|---|---|---|---|
| SQL injection via string concat | `app.py:87` | Semgrep + ZAP | `tainted-sql-string` / CWE-89 | High |
| `eval()` on user input | `app.py:116` | Semgrep | `eval-injection` / B307 | High |
| Flask debug mode + public host | `app.py:131` | Semgrep | `debug-enabled` / B201 | High |
| Hardcoded secret key | `app.py:10` | Semgrep | B105 | Medium |
| Hardcoded password | `app.py:13` | Semgrep | B105 | Medium |
| Container runs as root | `Dockerfile:12` | Semgrep | `missing-user` | Medium |
| Missing CSRF tokens | `app.py` templates | ZAP | CWE-352 | Medium |
| No CSP header | all responses | ZAP | CWE-693 | Medium |
| Missing clickjacking header | all responses | ZAP | CWE-1021 | Medium |
| HTTP only (no TLS) | server config | ZAP | CWE-311 | Medium |
| Session cookie missing SameSite | login response | ZAP | CWE-1275 | Low |
| Server version leakage | all responses | ZAP | CWE-497 | Low |
| Missing X-Content-Type-Options | all responses | ZAP | CWE-693 | Low |

## Run locally

```bash
pip install -r requirements.txt
python app.py
```

App runs at http://localhost:5000

## Run with Docker

```bash
docker build -t vuln-flask-app ./app
docker run -p 5000:5000 vuln-flask-app
```

## Routes

| Route | Method | Description |
|---|---|---|
| `/` | GET, POST | Login form |
| `/dashboard` | GET | Dashboard (requires login) |
| `/calc` | GET, POST | Calculator (eval injection) |
| `/logout` | GET | Clears session |

## Default credentials

- `admin` / `password123`
- `alice` / `alice456`

Or use SQL injection on the login form: `' OR '1'='1`

---

## CI/CD Security Pipeline

The pipeline runs two security jobs in parallel on every push and pull request to `main`.

```
push / PR
    ├── semgrep-oss/scan   (SAST — static analysis of source code)
    └── zap/automation-scan (DAST — dynamic attack against running app)
```

### SAST — Semgrep (`.github/workflows/SAST.yml`)

Semgrep runs inside its own Docker container and scans the `app/` directory against its `auto` ruleset, which pulls in rules for Flask, Python security, and Dockerfile hardening.

```yaml
jobs:
  semgrep:
    name: semgrep-oss/scan
    runs-on: ubuntu-latest
    container:
      image: semgrep/semgrep
    if: (github.actor != 'dependabot[bot]')
    steps:
      - uses: actions/checkout@v4
      - run: semgrep scan --config auto --error app/
```

The `--error` flag makes the job fail if any finding is detected, blocking the PR from merging.

**What Semgrep found in this app:**

| Rule ID | Finding | Severity |
|---|---|---|
| `flask.tainted-sql-string` | User input concatenated into raw SQL at `app.py:87` | Blocking |
| `flask.eval-injection` | `eval()` called on form input at `app.py:116` | Blocking |
| `flask.debug-enabled` | `debug=True` with `host="0.0.0.0"` at `app.py:131` | Blocking |
| `flask.render-template-string` | Templates constructed with string formatting | Blocking |
| `dockerfile.missing-user` | Container has no non-root USER directive | Blocking |
| `python.lang.eval-detected` | General `eval()` usage flagged | Blocking |

Semgrep catches these because it analyses the source code directly and can trace data flow (e.g. from `request.form` through to `eval()`). ZAP cannot see any of this without first authenticating and reaching the `/calc` route.

### DAST — OWASP ZAP (`.github/workflows/DAST.yml`)

ZAP builds and starts the Flask app in Docker, then runs a full authenticated scan using the Automation Framework config at `.github/zap.yml`.

```yaml
jobs:
  zap:
    name: zap/automation-scan
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Build and start Flask app
        run: |
          docker build -t vuln-flask-app ./app
          docker run -d --name flask-app --network=host vuln-flask-app

      - name: Wait for app to be ready
        run: |
          for i in {1..10}; do
            curl -s http://localhost:5000 && break
            sleep 3
          done

      - name: ZAP Automation Framework Scan
        uses: zaproxy/action-af@v0.3.0
        with:
          plan: ".github/zap.yml"

      - name: Print ZAP Summary
        if: always()
        run: |
          if [ -f zap-summary.md ]; then
            cat zap-summary.md >> $GITHUB_STEP_SUMMARY
            cat zap-summary.md
          else
            echo "ZAP summary file not found."
          fi
```

The ZAP automation plan (`.github/zap.yml`) logs in as `admin` before scanning, so it reaches authenticated routes like `/dashboard` and `/calc`. It runs a spider pass followed by an active attack scan, then outputs both an HTML and a Markdown report.

**What ZAP found in this app:**

| Alert | Risk | How ZAP found it |
|---|---|---|
| SQL Injection | High | Injected `'` into login form fields; app returned HTTP 500 |
| Absence of Anti-CSRF Tokens | Medium | No token present in HTML form |
| Content Security Policy Not Set | Medium | CSP header absent from all responses |
| Missing Anti-clickjacking Header | Medium | No `X-Frame-Options` or CSP `frame-ancestors` |
| HTTP Only Site | Medium | No HTTPS listener detected |
| Cookie without SameSite Attribute | Low | Session cookie set without `SameSite` |
| Server Leaks Version via Header | Low | `Server: Werkzeug/3.0.3 Python/3.12.13` in every response |
| X-Content-Type-Options Missing | Low | Header absent from responses |

ZAP does not flag `eval()`, hardcoded secrets, or `debug=True` because those are source-level issues invisible to a black-box scanner. This is why Semgrep runs alongside it.

### Why both tools are needed

| Vulnerability | Semgrep (SAST) | ZAP (DAST) |
|---|---|---|
| SQL injection | ✅ traces data flow in source | ✅ confirms exploitable at runtime |
| `eval()` RCE | ✅ detects at source | ❌ never reached `/calc` unauthenticated |
| Hardcoded secrets | ✅ string literal analysis | ❌ not visible over HTTP |
| `debug=True` | ✅ flag in source | ❌ not detectable externally |
| Missing CSRF tokens | ❌ no DOM analysis | ✅ inspects rendered HTML |
| Missing security headers | ❌ no HTTP layer | ✅ checks every response |
| Runtime SQL error (HTTP 500) | ❌ static only | ✅ sees actual server response |

---

## Vulnerability Remediation Examples

### 1. SQL Injection → Parameterized query

**Before (vulnerable):**
```python
# app.py:87 — user input concatenated directly into SQL
query = "SELECT * FROM users WHERE username = '" + username + "' AND password = '" + password + "'"
conn = get_db()
cursor = conn.execute(query)
```

An attacker can bypass authentication with `username = ' OR '1'='1` or dump the database.

**After (fixed):**
```python
# Use parameterized query — the DB driver escapes all values safely
query = "SELECT * FROM users WHERE username = ? AND password = ?"
conn = get_db()
cursor = conn.execute(query, (username, password))
```

Semgrep rule `flask.tainted-sql-string` no longer fires. ZAP's SQL injection probe now returns 200 instead of 500.

### 2. Remote Code Execution via `eval()` → `ast.literal_eval`

**Before (vulnerable):**
```python
# app.py:116 — arbitrary Python executed server-side
result = eval(expr)
```

An attacker submitting `__import__('os').system('rm -rf /')` executes it directly on the server.

**After (fixed):**
```python
import ast

# ast.literal_eval only evaluates Python literals (numbers, strings, lists, dicts)
# It raises ValueError for anything executable
try:
    result = ast.literal_eval(expr)
except (ValueError, SyntaxError) as e:
    result = f"Error: invalid expression"
```

This limits the calculator to safe literal values like `2+2` (which `ast.literal_eval` does not evaluate — for a real calculator, use a safe math parser like `simpleeval`). Semgrep rules `eval-injection` and `eval-detected` no longer fire after this change.

---

## Running the scans locally

### Semgrep

```bash
# Install
pip install semgrep

# Run against the app directory
semgrep scan --config auto app/
```

### ZAP

Start the app first:
```bash
docker build -t vuln-flask-app ./app
docker run -d --name flask-app --network=host vuln-flask-app
```

Then run ZAP:
```bash
# Unauthenticated baseline (fast)
docker run --rm --network host \
  -v $(pwd):/zap/wrk:rw \
  ghcr.io/zaproxy/zaproxy:stable \
  zap-baseline.py -t http://localhost:5000 -r zap-report.html

# Full authenticated scan using the automation plan
docker run --rm --network host \
  -v $(pwd):/zap/wrk:rw \
  ghcr.io/zaproxy/zaproxy:stable \
  zap.sh -cmd -autorun /zap/wrk/.github/zap.yml
```

Reports are saved to the current directory as `zap-report.html` and `zap-summary.md`.
