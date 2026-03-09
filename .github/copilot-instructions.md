# Cookie Checker Web App - Project Setup

Full-stack web application with React Vite frontend and FastAPI backend for cookie checking and account info extraction.

## Setup Checklist

- [x] Scaffold the React Vite frontend
- [x] Scaffold the FastAPI backend
- [x] Install frontend dependencies
- [x] Install backend dependencies
- [x] Create development tasks
- [x] Verify project structure
- [x] Update README.md with complete documentation

## Project Structure

```
.
├── frontend/          # React + Vite app
│   ├── src/
│   │   ├── components/
│   │   │   ├── Header.tsx
│   │   │   ├── CookieForm.tsx
│   │   │   └── CookieDisplay.tsx
│   │   ├── App.tsx
│   │   ├── main.tsx
│   │   └── index.css
│   ├── index.html
│   ├── vite.config.ts
│   ├── tsconfig.json
│   └── package.json
├── backend/           # FastAPI server
│   ├── main.py
│   ├── requirements.txt
│   ├── .env
│   └── venv/          # Python virtual environment
├── .github/           # GitHub configs
├── .vscode/
│   └── tasks.json     # Development tasks
└── README.md          # Project documentation
```

## Getting Started

### Frontend Development
1. Run the "Start Frontend Dev Server" task from VS Code (Ctrl+Shift+D)
2. Frontend will be available at http://localhost:5173

### Backend Development
1. Backend dependencies should be installed (pip install in progress)
2. Run the "Start Backend Dev Server" task from VS Code
3. Backend API will be available at http://localhost:8000
4. API documentation at http://localhost:8000/docs

## Key Features

- Cookie parser supporting Netscape and JSON formats
- Automatic format detection
- Cookie display with full properties
- Copy to clipboard and download functionality
- Responsive design
- CORS enabled for development

## Next Steps

1. Ensure backend dependencies finish installing
2. Start both frontend and backend dev servers
3. Open http://localhost:5173 in your browser
4. Test cookie parsing functionality


