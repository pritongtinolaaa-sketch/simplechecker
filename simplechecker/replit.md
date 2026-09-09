# Cookie Checker Web App

A full-stack web application for parsing and analyzing Netflix cookies, generating auto-login tokens, and checking account info.

## Architecture

- **Frontend**: React 18 + Vite + TypeScript, runs on port 5000
- **Backend**: FastAPI (Python 3.12) + Uvicorn, runs on port 8000 (localhost)

## Project Structure

```
frontend/          # React + Vite application (port 5000)
  src/
    components/    # React components (CookieForm, CookiesList, Header, etc.)
    App.tsx        # Main app with cookie checking state management
    index.css      # All app styles (dark cyberpunk theme)
  vite.config.ts   # Vite config - host 0.0.0.0, port 5000, proxy /api -> :8000
backend/           # FastAPI application (port 8000)
  main.py          # All routes, cookie parsing, Netflix token generation
  requirements.txt # Python dependencies
  .env             # Environment config
```

## Key Features

- Cookie parsing (Netscape and JSON formats, auto-detection)
- Netflix NFTOKEN generation via GraphQL API
- Netflix account info extraction via Shakti API
- Direct access to the cookie checker without an application login

## Running Locally

- Frontend: `cd frontend && npm run dev`
- Backend: `cd backend && uvicorn main:app --host localhost --port 8000 --reload`

## Workflows

- **Start application** – Frontend dev server (webview, port 5000)
- **Backend** – FastAPI server (console, port 8000)
