# MARI Dashboard — React Component Architecture

> **Date:** 2026-04-16  
> **Companion to:** [[React-UI-Overview]]

---

## Full Component Tree

```mermaid
flowchart TD
    Root["#root (DOM)"]
    Root --> MT["main.tsx — StrictMode"]
    MT --> APP[App.tsx]

    APP --> AUTH["AuthProvider (context/AuthContext.tsx)"]
    AUTH --> INNER[AppInner]

    INNER --> SB["Sidebar (inline JSX in App.tsx)"]
    INNER --> MAIN["Main content div"]

    SB --> LOGO["SVG Logo light+dark"]
    SB --> NAV["sidebar-nav sections"]
    SB --> FOOTER["Theme toggle + User widget"]

    MAIN --> PL1["PageLoader — on auth loading"]
    MAIN --> LOGIN["Login inline — if unauthenticated"]
    MAIN --> PL2["PageLoader — on navigation"]
    MAIN --> PAGEHEADER["page-header h1"]
    MAIN --> PAGECMP["Active Page Component"]

    PAGECMP --> EX["Executive (pages/Executive.tsx)"]
    PAGECMP --> QU["Quality (pages/Quality.tsx)"]
    PAGECMP --> RAG["RagReadiness (pages/RagReadiness.tsx)"]
    PAGECMP --> REL["Reliability (pages/Reliability.tsx)"]
    PAGECMP --> CA[CostAnalytics]
    PAGECMP --> WB[Workbench]
    PAGECMP --> OTH["...other pages"]

    EX & QU & RAG & REL --> CHRT["chartDefaults.ts - createBarChart / createDoughnutChart"]
    EX & QU & RAG & REL --> API["GET /api/aggregations"]
    EX & QU & RAG & REL --> PLdr["PageLoader — while loading"]
```

---

## Lifecycle: Analytics Page Mount

Every analytics tab follows the **same lifecycle pattern**:

```mermaid
flowchart LR
    M[Component mounts] --> F["fetch /api/aggregations"]
    F --> S{ok?}
    S -->|yes| SET[setState with data slice]
    S -->|no| NUL[setState null]
    SET --> CHART["useEffect on data: destroy old charts, create new charts"]
    NUL --> ERR["show empty/placeholder"]
    M --> SHOW{data null?}
    SHOW -->|yes| LOADER[render PageLoader]
    SHOW -->|no| CONTENT["render metric cards + charts"]
```

---

## Chart Rendering Pipeline

```mermaid
flowchart TD
    DATA["API response slice (e.g. data.exec)"] --> EFFECT[useEffect triggered]
    EFFECT --> DESTROY["destroy existing chart instances via charts.current ref map"]
    DESTROY --> THEME["chartDefaults applies theme-aware colors"]
    THEME --> CREATE{chart type}
    CREATE -->|doughnut| DC["createDoughnutChart: cutout 60%, legend right, datalabels"]
    CREATE -->|"bar horiz"| BH["createBarChart horizontal=true: barThickness 18, datalabels end/right"]
    CREATE -->|"bar vert"| BV["createBarChart horizontal=false: datalabels end/top"]
    DC & BH & BV --> CANVAS["mounted canvas ref"]
    CANVAS --> CHARTJS["Chart.js instance stored in charts.current map"]
    CHARTJS --> CLEANUP["cleanup on unmount or next effect run"]
```

---

## Auth & Permission Flow

```mermaid
flowchart TD
    BOOT[App boots] --> FETCH["fetch /api/auth/me"]
    FETCH --> OK{200?}
    OK -->|yes| SETUSER["setUser + setPermissions"]
    OK -->|no| STORED{"localStorage username?"}
    STORED -->|yes| LOGIN["POST /api/auth/login"]
    LOGIN --> REFETCH["re-fetch /api/auth/me"]
    REFETCH --> SETUSER
    STORED -->|no| UNAUTH["user=null, authEnabled=true, bypass=false"]
    SETUSER --> BYPASS{bypass mode?}
    BYPASS -->|yes| ALLCAN["can() always true"]
    BYPASS -->|no| CHECK["can() checks permissions dict"]
    UNAUTH --> LOGINSCREEN[Render login form]
    ALLCAN & CHECK --> NAVFILTER["Filter sidebar items by can(key, 'view')"]
    NAVFILTER & LOGINSCREEN --> RENDER[Render app]
```

---

## State Management (AppInner)

`AppInner` is the sole stateful shell. All page components are **stateless relative to routing** — they own their own data-fetch state internally.

```typescript
// AppInner state
const [page, setPage] = useState('exec')           // active page key
const [pageLoading, setPageLoading] = useState(false)  // 1s transition loader
const [collapsed, setCollapsed] = useState(...)    // sidebar collapsed?
const [theme, setTheme] = useState(...)            // 'light' | 'dark'
const [userMenuOpen, setUserMenuOpen] = useState(false)
const [collapsedSections, setCollapsedSections] = useState<Set<string>>()
const [loginUsername, setLoginUsername] = useState('')
```

Navigation triggers a **1-second PageLoader** before swapping the page:

```typescript
const navigate = (key: string) => {
  if (key === page) return
  setPageLoading(true)
  setTimeout(() => { setPage(key); setPageLoading(false) }, 1000)
}
```

---

## Theme System

```mermaid
flowchart LR
    BTN["Theme toggle button"] --> TS["setTheme dark/light"]
    TS --> LS["localStorage.setItem theme"]
    TS --> HTML["document.documentElement data-theme = dark/light"]
    HTML --> CSS["CSS vars switch: --bg, --text, --border..."]
    HTML --> MO["MutationObserver in chartDefaults.ts"]
    MO --> CHARTCLR["Chart.defaults.color, borderColor, legend.labels.color"]
    TS --> REMOUNT["key=page+theme forces page component remount"]
    REMOUNT --> RECHARTS["Charts re-created with new theme colors"]
```

---

## PageLoader Component

18 hotel-themed SVG variants selected randomly on mount via `useMemo`.

```mermaid
flowchart LR
    PL[PageLoader] --> MEMO["useMemo: random index once"]
    MEMO --> LOADERS["LOADERS array — 18 entries"]
    LOADERS --> SVG["dangerouslySetInnerHTML SVG"]
    LOADERS --> CAP["caption text"]
```

**Loader themes:** Bell, Keycard, Elevator, Stars, Pool, Bed, Thermometer, Suitcase, and 10 more.

---

## Workbench Sub-component Map

The Workbench page decomposes into 14 child components:

```mermaid
flowchart TD
    WB["Workbench (pages/Workbench.tsx)"] --> WBSB["WorkbenchSidebar: session list"]
    WB --> WBCHAT["WorkbenchChat: message thread"]
    WB --> WBINPUT["WorkbenchInputBar: text + send"]
    WB --> WBTRACE["WorkbenchTrace: classification trace"]
    WB --> WBASSESS["WorkbenchAssessment: quality scoring"]
    WB --> WBFB["WorkbenchFeedback: thumb up/down"]
    WB --> WBCW["WorkbenchContextWarning: token overflow alert"]
    WB --> WBRETRY["WorkbenchRetryPrompt: retry with edits"]
    WB --> WBDEMO["WorkbenchDemoMenu: demo scenario picker"]

    WB --> WBCFG["WorkbenchConfigModal: system config"]
    WB --> WBLLM["WorkbenchLlmConfigModal: model picker"]
    WB --> WBINTENT["WorkbenchIntentModal: intent viewer"]
    WB --> WBBATCH["WorkbenchBatchModal: batch run"]
    WB --> WBBRAND["WorkbenchBrandVoiceModal: brand voice editor"]
```

---

## File & Folder Structure

```
frontend/src/
├── main.tsx                        ← entry, CSS imports
├── App.tsx                         ← root + sidebar + routing
├── variables.css
├── base.css
├── sidebar.css
├── components.css
├── loaders.css
│
├── pages/
│   ├── Executive.tsx               ← Analytics: exec
│   ├── Quality.tsx                 ← Analytics: quality
│   ├── RagReadiness.tsx            ← Analytics: rag
│   ├── Reliability.tsx             ← Analytics: reliability
│   ├── CostAnalytics.tsx           ← Analytics: costs
│   ├── Validation.tsx              ← Data: validation
│   ├── ProductCatalog.tsx          ← Data: propcat
│   ├── Taxonomy.tsx                ← Data: taxonomy
│   ├── Workbench.tsx               ← Tools: workbench
│   ├── EvalFeedback.tsx            ← Tools: ragresults
│   ├── IntentReadiness.tsx         ← Tools: readiness
│   ├── Docs.tsx                    ← System: docs
│   ├── Settings.tsx                ← System: settings
│   ├── Login.tsx                   ← System: login
│   └── Profile.tsx                 ← System: profile
│
├── components/
│   ├── PageLoader.tsx              ← animated loaders
│   ├── PermGate.tsx                ← permission wrapper + useDataPerm
│   ├── SearchableSelect.tsx        ← filterable dropdown
│   ├── ArchitectureDiagram.tsx     ← system diagram
│   └── workbench/
│       ├── WorkbenchAssessment.tsx
│       ├── WorkbenchBatchModal.tsx
│       ├── WorkbenchBrandVoiceModal.tsx
│       ├── WorkbenchChat.tsx
│       ├── WorkbenchConfigModal.tsx
│       ├── WorkbenchContextWarning.tsx
│       ├── WorkbenchDemoMenu.tsx
│       ├── WorkbenchFeedback.tsx
│       ├── WorkbenchInputBar.tsx
│       ├── WorkbenchIntentModal.tsx
│       ├── WorkbenchLlmConfigModal.tsx
│       ├── WorkbenchRetryPrompt.tsx
│       ├── WorkbenchSidebar.tsx
│       └── WorkbenchTrace.tsx
│
├── context/
│   └── AuthContext.tsx             ← AuthProvider + useAuth
│
├── hooks/
│   ├── useApi.ts
│   └── useApiFetch.ts
│
├── utils/
│   └── chartDefaults.ts           ← Chart.js factory + theme
│
└── lib/
    ├── workbenchTypes.ts
    ├── workbenchDefaults.ts
    ├── workbenchLlm.ts
    ├── workbenchPrompt.ts
    ├── workbenchHandoff.ts
    └── workbenchHelpers.ts
```

---

## API Surface Used by React

| Endpoint | Method | Caller | Purpose |
|----------|--------|--------|---------|
| `/api/aggregations` | GET | All analytics pages | Fetch `exec`, `quality`, `rag`, `reliability`, `costs` slices |
| `/api/auth/me` | GET | `AuthContext` | Get current user + permissions |
| `/api/auth/login` | POST | `AuthContext`, `AppInner` | Authenticate by username |
| `/api/auth/logout` | POST | `AuthContext` | Clear session |

---

## CSS Class Reference (shared across tabs)

| Class | Usage |
|-------|-------|
| `.metrics-grid` | 3-column auto-fill grid for metric cards |
| `.metric-card` | Individual KPI card with label + value + delta |
| `.metric-card.accent-*` | Colour accents: cyan, green, orange, red, purple, yellow |
| `.charts-grid` | 2-column chart layout grid |
| `.chart-card` | Card wrapper with header + container |
| `.chart-card.full-width` | Spans both columns |
| `.chart-container` | Fixed-height canvas wrapper |
| `.chart-container.tall` | Taller canvas for many-label bar charts |
| `.chart-container.small` | Shorter canvas |
| `.chart-title` | Bold chart heading |
| `.chart-subtitle` | Secondary grey subtitle |
| `.data-table-wrapper` | Scrollable table container |
| `.data-table` | Striped table |
| `.mono-cell` | Monospace table cell |
| `.badge.badge-purple` | Intent badge |
| `.badge.badge-red` | Error/method badge |
| `.hint` | Muted helper text |
| `.mono` | Inline monospace span |

---

*Generated 2026-04-16 — source: `emergingtech-tipai-ecmp-dashboard/frontend/src/`*
