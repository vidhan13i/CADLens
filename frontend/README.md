# CADLens — Frontend (React 19 + Vite)

> Interactive drawing canvas, AS9102 inspection sidebar, and balloon management interface for CADLens.

## 🚀 Tech Stack

- **Framework:** React 19 + Vite 8
- **Icons:** Lucide React
- **HTTP Client:** Axios
- **PDF Rendering:** react-pdf & pdfjs-dist
- **Styling:** CSS variables, Glassmorphism dark-mode system (`App.css`)

---

## 🏗️ Component Architecture

```
frontend/src/
├── main.jsx                   # Application entry point
├── App.jsx                    # Root state machine (Upload / Annotate view, selection & batch export)
├── App.css                    # Glassmorphism dark theme & AS9102 characteristic styling
├── api.js                     # Centralized API base URL config (VITE_API_URL)
└── components/
    ├── DrawingCanvas.jsx      # Interactive HTML5 canvas with zoom, pan, balloons, pinned leader lines, and drag physics
    ├── BalloonList.jsx        # Sidebar inspector — AS9102 Form 3 field editor, designator badges, tool selector, multi-select checkboxes
    └── Toolbar.jsx            # Action toolbar — zoom controls, mode toggle (Auto/Manual), export all / selected, new upload
```

---

## 🌟 Key Features

1. **Interactive Inspection Canvas (`DrawingCanvas.jsx`):**
   - Renders 300 DPI high-resolution engineering drawings.
   - Pinned leader lines: moving a balloon badge keeps the leader line tip firmly pinned to the measured CAD feature.
   - Window-level mouse event listeners ensure fluid drag-and-drop even when cursor exits the canvas bounds.
   - Click-to-inspect: clicking any balloon directly highlights and smooth-scrolls to the corresponding sidebar entry.

2. **AS9102 Form 3 Inspection Editor (`BalloonList.jsx`):**
   - Editable fields: Nominal Value, Upper Tolerance, Lower Tolerance, Units (`mm`, `°`, `in`).
   - Automated Limit Calculation: Computes Upper Limit ($Max$) and Lower Limit ($Min$) in real-time.
   - Characteristic Classification: Designate dimensions as *Standard*, *Critical*, *Major*, *Reference*, or *Basic*.
   - Inspection Tool Assignment: Assign measurement methods (*Caliper*, *Micrometer*, *CMM*, *Height Gauge*, *Thread Gauge*, *Bore Gauge*, *Optical Comparator*, etc.).
   - Multi-Select Checkboxes & Filter: Easily select a subset of characteristics or "Select All".

3. **Selective & Full Excel Export (`Toolbar.jsx` & `App.jsx`):**
   - One-click **Export XLSX** for all detected characteristics.
   - **Export Selected** button triggers targeted generation for only checked balloons via `POST /export/:id/selected`.

---

## 🛠️ Local Development Setup

### 1. Prerequisites
Ensure you have **Node.js ≥ 18** installed.

### 2. Configure Environment
Copy the example `.env` file:

```bash
cp .env.example .env
```

Ensure `.env` points to your running FastAPI backend:
```env
VITE_API_URL=http://localhost:8000
```

### 3. Install Dependencies & Start Server
```bash
npm install
npm run dev
```

The application will start at **http://localhost:5173**.

---

## 📦 Scripts

- `npm run dev` — Starts the Vite development server with HMR.
- `npm run build` — Compiles production-ready bundle into `dist/`.
- `npm run preview` — Locally preview the production build.
- `npm run lint` — Runs ESLint code quality checks.
