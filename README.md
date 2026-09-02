# Cookie Checker Web App

A full-stack web application for extracting and analyzing cookies from browsers or files. Built with React (Vite) frontend and FastAPI backend.

## Features

- **Cookie Parser**: Support for multiple cookie formats:
  - Netscape format (browser dev tools export)
  - JSON format (array of cookie objects)
  - Auto-detection of format
  
- **Cookie Display**: 
  - Comprehensive table view with all cookie properties
  - Easy copy-to-clipboard functionality
  - Download as JSON
  - Raw JSON preview

- **Netflix Token Generation**:
  - Generate Netflix auto-login tokens (NFTOKEN) from cookies
  - Playwright integration to get full cookie headers automatically
  - Support for both complete and partial cookie inputs

- **Account Information**:
  - Extract Netflix account info (when cookies are available)
  - Display plan details, profiles, and membership information

- **Responsive Design**: Works on desktop and mobile devices

## Project Structure

```
.
├── frontend/          # React + Vite application
│   ├── src/
│   │   ├── components/
│   │   │   ├── Header.tsx
│   │   │   ├── CookieForm.tsx
│   │   │   ├── CookieDisplay.tsx
│   │   │   └── NetflixToken.tsx
│   │   ├── App.tsx
│   │   ├── main.tsx
│   │   └── index.css
│   ├── index.html
│   ├── vite.config.ts
│   ├── tsconfig.json
│   └── package.json
│
├── backend/           # FastAPI application
│   ├── main.py        # FastAPI app and endpoints
│   ├── requirements.txt
│   └── .env
│
├── .github/
│   └── copilot-instructions.md
│
└── README.md
```

## Prerequisites

- Node.js (v18 or higher)
- Python (v3.8 or higher)
- npm or yarn

## Installation

### Frontend Setup

```bash
cd frontend
npm install
```

### Backend Setup

```bash
cd backend
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```

## Development

### Frontend Development Server

```bash
cd frontend
npm run dev
```

The frontend will be available at `http://localhost:5173`

### Backend Development Server

```bash
cd backend
python main.py
```

Or with uvicorn directly:

```bash
cd backend
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

The backend API will be available at `http://localhost:8000`

## Access

The application opens directly to the cookie checker. No login, master key,
user-key management, browser session, or API-key header is required.

## API Endpoints

All endpoints below are available without an application login.

#### POST `/api/check-cookies`

Parse and extract cookies from provided text.

**Request:**
```json
{
  "cookies_text": "...",
  "format_type": "auto"  // "netscape", "json", or "auto"
}
```

**Response:**
```json
{
  "success": true,
  "cookies": [
    {
      "name": "cookie_name",
      "value": "cookie_value",
      "domain": ".example.com",
      "path": "/",
      "secure": true,
      "httponly": true,
      "samesite": "Strict",
      "expires": "2024-01-01"
    }
  ],
  "count": 1,
  "parsed_at": "2024-03-10T12:00:00",
  "errors": null
}
```

### POST `/api/upload-cookies`

Upload a file containing cookies.

**Parameters:**
- `file`: File upload (text or JSON)

**Response:** Same as `/api/check-cookies`

### POST `/api/generate-netflix-token`

Parse cookies and generate Netflix auto-login token (NFTOKEN).

**Request:**
```json
{
  "cookies_text": "...",
  "format_type": "auto",  // "netscape", "json", or "auto"
  "use_playwright": false  // Use Playwright to get full cookie header
}
```

**Response:**
```json
{
  "success": true,
  "nftoken": "eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9...",
  "error": null,
  "cookies": [...],
  "cookie_count": 5
}
```

**Notes:**
- If `use_playwright` is `true`, the endpoint will use Playwright to visit Netflix.com and collect the full cookie header
- Useful when you only have partial cookies (like just NetflixId)
- The generated token can be used for Netflix mobile/TV app authentication
- Requires NetflixId and SecureNetflixId cookies to be present

### GET `/api/stats`

Get API statistics and available endpoints.

**Response:**
```json
{
  "status": "running",
  "timestamp": "2024-03-10T12:00:00",
  "endpoints": [
    "POST /api/check-cookies",
    "POST /api/upload-cookies",
    "POST /api/generate-netflix-token",
    "GET /api/stats"
  ]
}
```

## Cookie Formats

### Netscape Format
Exported from browser DevTools or as tab-separated values:
```
.domain.com	TRUE	/	TRUE	expires	cookieName	cookieValue
```

### JSON Format
Standard JSON array of cookie objects:
```json
[
  {
    "name": "cookieName",
    "value": "cookieValue",
    "domain": ".domain.com",
    "path": "/",
    "secure": true,
    "httpOnly": true,
    "sameSite": "Strict",
    "expires": "2024-01-01"
  }
]
```

## Building for Production

### Frontend Build

```bash
cd frontend
npm run build
```

The built files will be in `frontend/dist/`

### Backend Deployment

For production, use a production WSGI server like Gunicorn:

```bash
pip install gunicorn
gunicorn -w 4 -b 0.0.0.0:8000 main:app
```

## Environment Variables

### Backend (.env)

```
FASTAPI_DEBUG=True
DEBUG=True
HOST=0.0.0.0
PORT=8000
```

## Technologies Used

### Frontend
- React 18
- Vite
- TypeScript
- Axios
- CSS3

### Backend
- FastAPI
- Pydantic
- Uvicorn
- Python 3.8+

## License

MIT

## Support

For issues, questions, or suggestions, please open an issue on GitHub.

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.
