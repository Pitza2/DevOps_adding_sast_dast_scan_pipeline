# vuln-flask-app

A minimal intentionally vulnerable Flask web app for the P8 DevSecOps assignment.
Do not deploy this anywhere public.

## Intentional vulnerabilities

| Vulnerability | Location | Bandit rule | Severity |
|---|---|---|---|
| Hardcoded secret key | `app.py:10` | B105 | Medium |
| Hardcoded password | `app.py:13` | B105 | Medium |
| SQL injection via string concat | `app.py:68` | B608 | High |
| `eval()` on user input | `app.py:93` | B307 | Medium |
| Flask debug mode enabled | `app.py:104` | B201 | High |

## Run locally

```bash
pip install -r requirements.txt
python app.py
```

App runs at http://localhost:5000

## Run with Docker

```bash
docker build -t vuln-flask-app .
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
