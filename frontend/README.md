# CourseCompass — Frontend Application

The CourseCompass frontend is a modern single-page application built with **React 19**, **TypeScript**, **Vite**, and **Tailwind CSS v4**. It implements an editorial warm-canvas design system inspired by modern AI interfaces.

---

## 1. Directory Structure

```text
frontend/src/
├── components/
│   ├── ui/                 # Reusable UI primitives (buttons, inputs, dropdowns, dialogs)
│   ├── app-sidebar.tsx     # Session history sidebar with delete & switch capabilities
│   ├── chat-header.tsx     # Navigation header with session title and user controls
│   ├── chat-input.tsx      # Textarea with auto-expansion & Enter-to-submit keyboard handlers
│   ├── chat-window.tsx     # Primary chat container orchestrating messages, citations, & API calls
│   ├── layout.tsx          # Master layout with collapsible sidebar and responsive shell
│   └── message-scroller.tsx# Markdown renderer with code highlighting and source accordion
├── hooks/                  # Custom React hooks
├── lib/
│   ├── authContext.tsx     # Authentication context provider managing JWT tokens in localStorage
│   └── utils.ts            # Utility functions (cn / clsx class merging)
├── pages/
│   ├── Login.tsx           # Student login screen
│   ├── Register.tsx        # New student registration with academic profile fields
│   └── Profile.tsx         # Student profile viewer (CGPA, Term, Program details)
├── App.tsx                 # Route declarations via react-router-dom
├── index.css               # Global styles, Tailwind v4 setup, and font imports
└── main.tsx                # React DOM entrypoint and AuthProvider wrapper
```

---

## 2. Key Features

1. **Guest & Authenticated Modes**:
   - Guests can immediately start asking questions without registering.
   - Registered students log in to access persistent conversation history, automatic session titling, and personalized advising based on their CGPA and current semester.
2. **Rich Markdown & Source Citations**:
   - Renders GitHub-flavored markdown, tables, bullet points, and code blocks.
   - Displays expandable source citations identifying exact PDF document names (Syllabus vs. Instruction Plan) and section titles.
3. **Session Management**:
   - Sidebar lists all historical chat sessions.
   - Instant switching between sessions via `/chat/:id` deep links.
   - Deletion of individual sessions with confirmation.
4. **Editorial Design System**:
   - Styled with Tailwind CSS v4, Cormorant Garamond / Copernicus display serif typography, and warm cream canvas background (`#faf9f5`).

---

## 3. Getting Started

### 3.1 Install Dependencies
```bash
cd frontend
npm install
```

### 3.2 Development Server
Start Vite development server:
```bash
npm run dev
```
The application will launch at `http://localhost:5173`.

> [!NOTE]
> The Vite development server automatically proxies all `/api/*` requests to the backend at `http://127.0.0.1:8000`. Ensure your FastAPI backend is running before testing chat requests.

### 3.3 Production Build
Compile TypeScript and generate production assets:
```bash
npm run build
```
The optimized bundle will be generated in `frontend/dist/`.

### 3.4 Preview Production Build
```bash
npm run preview
```

### 3.5 Linting
```bash
npm run lint
```
