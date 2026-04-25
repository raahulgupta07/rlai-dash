<script lang="ts">
  import { onMount } from 'svelte';

  /* ─── state ─── */
  let activeTab = $state('users');
  let loading = $state(false);

  /* ─── auth helper ─── */
  function _h(): Record<string, string> {
    const t = typeof localStorage !== 'undefined' ? localStorage.getItem('dash_token') : null;
    return t ? { Authorization: `Bearer ${t}` } : {};
  }

  /* ─── tabs ─── */
  const tabs = [
    { id: 'users',    label: 'USERS' },
    { id: 'projects', label: 'PROJECTS' },
    { id: 'logs',     label: 'LOGS' },
    { id: 'schemas',  label: 'SCHEMAS' },
    { id: 'chatLogs', label: 'CHAT LOGS' },
    { id: 'health',   label: 'HEALTH' },
    { id: 'stats',    label: 'STATS' },
    { id: 'integrations', label: 'INTEGRATIONS' },
    { id: 'architecture', label: 'ARCHITECTURE' },
  ];

  /* ─── USERS state ─── */
  let users = $state<any[]>([]);
  let expandedUserId = $state<string | null>(null);
  let userDetail = $state<any>(null);
  let loadingUserDetail = $state(false);

  // Create user
  let showCreateUser = $state(false);
  let newUsername = $state('');
  let newPassword = $state('');
  let newEmail = $state('');

  // Reset password
  let resetUser = $state('');
  let resetPass = $state('');
  let resetMsg = $state('');

  /* ─── PROJECTS state ─── */
  let projects = $state<any[]>([]);
  let expandedProjectSlug = $state<string | null>(null);
  let projectDetail = $state<any>(null);
  let loadingProjectDetail = $state(false);

  /* ─── LOGS state ─── */
  let logs = $state<any[]>([]);
  let logFilterAction = $state('');
  let logFilterUser = $state('');
  let logFilterProject = $state('');

  /* ─── SCHEMAS state ─── */
  let schemas = $state<any[]>([]);
  let expandedSchema = $state<string | null>(null);

  /* ─── CHAT LOGS state ─── */
  let chatLogs = $state<any[]>([]);
  let chatFilterUser = $state('');
  let chatFilterProject = $state('');
  let expandedChat = $state<string | null>(null);

  /* ─── HEALTH state ─── */
  let health = $state<any>(null);

  /* ─── STATS state ─── */
  let stats = $state<any>(null);

  /* ─── ARCHITECTURE state ─── */
  let arch = $state<any>(null);
  let archFlowEl: HTMLDivElement;
  let archChart: any = null;

  async function loadArchitecture() {
    try { const r = await fetch('/api/architecture', { headers: _h() }); if (r.ok) arch = await r.json(); } catch {}
    // Render flow chart after data loads
    setTimeout(() => renderArchFlow(), 300);
  }

  async function renderArchFlow() {
    if (!archFlowEl || !arch) return;
    const echarts = await import('echarts/core');
    const { GraphChart } = await import('echarts/charts');
    const { TooltipComponent, TitleComponent } = await import('echarts/components');
    const { CanvasRenderer } = await import('echarts/renderers');
    echarts.use([GraphChart, TooltipComponent, TitleComponent, CanvasRenderer]);

    if (archChart) archChart.dispose();
    archChart = echarts.init(archFlowEl);

    const cats = [
      { name: 'Network',   itemStyle: { color: '#3b82f6' } },
      { name: 'Agent',     itemStyle: { color: '#22c55e' } },
      { name: 'Data',      itemStyle: { color: '#f59e0b' } },
      { name: 'ML',        itemStyle: { color: '#a855f7' } },
      { name: 'Knowledge', itemStyle: { color: '#06b6d4' } },
      { name: 'Security',  itemStyle: { color: '#ef4444' } },
      { name: 'Learning',  itemStyle: { color: '#ec4899' } },
      { name: 'Export',    itemStyle: { color: '#84cc16' } },
    ];

    const m = arch.metrics || {};
    const md = arch.models || {};
    const w = arch.infra?.workers || 8;
    const rl = arch.infra?.rate_limit || '500/min';

    // Helper for tooltip
    const tt = (title: string, lines: string[]) => `<div style="font-size:12px;font-weight:700;margin-bottom:4px;color:#0f0;">${title}</div>` + lines.map(l => `<div style="font-size:11px;line-height:1.5;">${l}</div>`).join('');

    const nodes: any[] = [
      // ─── NETWORK LAYER ───
      { name: 'Users', x: 400, y: 20, symbolSize: 45, symbol: 'roundRect', category: 0,
        tooltip: { formatter: () => tt('USERS', [`${m.users || 0} registered`, `${m.chats || 0} chat sessions`]) } },
      { name: 'Caddy', x: 400, y: 90, symbolSize: 35, symbol: 'diamond', category: 5,
        tooltip: { formatter: () => tt('CADDY — REVERSE PROXY', ['Auto-SSL/TLS certificates', 'HSTS, X-Frame-Options, XSS', `Rate limit: ${rl}`, 'Body max: 250MB', 'Timeout: 300s']) } },
      { name: `FastAPI`, x: 400, y: 160, symbolSize: 50, symbol: 'roundRect', category: 0,
        tooltip: { formatter: () => tt(`FASTAPI — ${w} WORKERS`, ['Auth middleware + token cache', 'SSE streaming + rate limiter', `Model: ${md.chat}`, 'NullPool → PgBouncer']) } },
      { name: 'PgBouncer', x: 620, y: 110, symbolSize: 28, category: 0,
        tooltip: { formatter: () => tt('PGBOUNCER', ['Transaction pooling mode', 'Max 200 DB connections', 'NullPool (no double-pool)', 'SCRAM-SHA-256 auth']) } },
      { name: 'PostgreSQL', x: 770, y: 110, symbolSize: 50, symbol: 'roundRect', category: 3,
        tooltip: { formatter: () => tt('POSTGRESQL 18 + PGVECTOR', [`${m.projects || 0} project schemas`, '35+ system tables', 'Schema isolation per project', 'Statement timeout: 120s', 'pgvector for embeddings']) } },

      // ─── ROUTING ───
      { name: 'Router', x: 230, y: 240, symbolSize: 35, symbol: 'diamond', category: 5,
        tooltip: { formatter: () => tt('SMART ROUTER — 2 TIER', ['Tier 1: Keyword scoring (7 signals, $0, <1ms)', 'Tier 2: Router Agent + Brain ($0.001, <1.5s)', '', '"revenue by month" → Analyst', '"predict sales" → Data Scientist', '"what does report say" → Researcher']) } },

      // ─── AGENT LAYER ───
      { name: 'Leader', x: 400, y: 310, symbolSize: 45, symbol: 'roundRect', category: 1,
        tooltip: { formatter: () => tt('LEADER AGENT', ['Coordinates team of 4 specialists', 'Synthesizes responses', 'Decomposes complex questions', `Model: ${md.chat}`]) } },
      { name: 'Analyst', x: 180, y: 400, symbolSize: 42, symbol: 'roundRect', category: 1,
        tooltip: { formatter: () => tt('ANALYST — 31 TOOLS', ['SQL queries (read-only)', 'Self-correction (3 retries)', 'Auto-visualize charts', 'search_all for context first', `Model: ${md.chat}`]) } },
      { name: 'Researcher', x: 340, y: 400, symbolSize: 36, symbol: 'roundRect', category: 1,
        tooltip: { formatter: () => tt('RESEARCHER — DOC RAG', ['PPTX/PDF/DOCX analysis', 'Multi-signal search', 'Grounded facts (LangExtract)', 'Knowledge graph context', `Model: ${md.chat}`]) } },
      { name: 'Data Scientist', x: 510, y: 400, symbolSize: 42, symbol: 'roundRect', category: 4,
        tooltip: { formatter: () => tt('DATA SCIENTIST — 6 ML TOOLS', ['NO SQL access (forces ML usage)', 'predict: AutoARIMA → LLM fallback', 'feature_importance: LightGBM + SHAP', 'detect_anomalies: IsolationForest', 'classify: GradientBoosting', 'cluster: K-Means / decompose', `Model: ${md.chat}`]) } },
      { name: 'Engineer', x: 670, y: 400, symbolSize: 36, symbol: 'roundRect', category: 1,
        tooltip: { formatter: () => tt('ENGINEER', ['Create views + dashboards', 'Schema management', 'Auto-VIEW at 3+ query uses', `Model: ${md.chat}`]) } },
      { name: 'Specialists', x: 180, y: 490, symbolSize: 28, category: 1,
        tooltip: { formatter: () => tt('10 SPECIALIST AGENTS', (arch.agents?.specialists || []).map((s: string) => `› ${s}`)) } },

      // ─── KNOWLEDGE LAYER ───
      { name: '13 Layers', x: 80, y: 310, symbolSize: 42, symbol: 'roundRect', category: 4,
        tooltip: { formatter: () => tt('13 CONTEXT LAYERS', ['1. Proven query patterns', '2. Approved responses', '3. Anti-patterns', '4. Agent memories', '5. Column annotations', '6. JOIN strategies', '7. User preferences', '8. Self-correction strategies', '9. Evolved instructions', '10. DB rules', '11. Grounded facts', '12. Knowledge graph', '13. Company brain']) } },
      { name: 'PgVector KB', x: 30, y: 400, symbolSize: 28, category: 4,
        tooltip: { formatter: () => tt('PGVECTOR KNOWLEDGE BASE', [`Embedding: ${md.embedding}`, 'Hybrid search (semantic + keyword)', 'Contextual retrieval (-49% failures)', '1536 dimensions']) } },
      { name: `Brain`, x: 30, y: 470, symbolSize: 28, category: 4,
        tooltip: { formatter: () => tt(`COMPANY BRAIN — ${m.brain_entries || 0} ENTRIES`, ['Formulas, glossary, aliases', 'Patterns, org structure', '3 scopes: global/project/personal', 'Cohere reranking']) } },
      { name: `KG`, x: 110, y: 470, symbolSize: 28, category: 4,
        tooltip: { formatter: () => tt(`KNOWLEDGE GRAPH — ${m.kg_triples || 0} TRIPLES`, ['SPO triple extraction', 'Entity standardization (fuzzy match)', 'Cross-source inference', 'Community detection (BFS)']) } },
      { name: 'Reranker', x: 30, y: 540, symbolSize: 22, category: 4,
        tooltip: { formatter: () => tt('COHERE RERANKING CASCADE', (arch.knowledge?.rerank_cascade || []).map((r: string, i: number) => `${i+1}. ${r}`)) } },

      // ─── ML LAYER ───
      { name: 'ML Worker', x: 770, y: 310, symbolSize: 38, symbol: 'roundRect', category: 4,
        tooltip: { formatter: () => tt('ML WORKER — ISOLATED CONTAINER', [`${m.ml_models || 0} active models`, '1GB RAM cap', 'Heavy jobs > 1000 rows', '5-min timeout per job', '100K row limit', 'Auto-retrain every 24h']) } },
      { name: 'AutoARIMA', x: 560, y: 490, symbolSize: 24, category: 4,
        tooltip: { formatter: () => tt('FORECAST', ['statsforecast/AutoARIMA', `LLM fallback: ${md.deep}`, 'Pre-trained ($0) or LLM ($0.02)', 'Includes historical data']) } },
      { name: 'LightGBM', x: 630, y: 490, symbolSize: 24, category: 4,
        tooltip: { formatter: () => tt('FEATURE IMPORTANCE', ['LightGBM + GridSearchCV', 'SHAP per-row explanations', 'Auto-tuned hyperparameters', 'R², RMSE, MAE, 5-fold CV']) } },
      { name: 'IsolForest', x: 700, y: 490, symbolSize: 24, category: 4,
        tooltip: { formatter: () => tt('ANOMALY DETECTION', ['sklearn/IsolationForest', 'Pre-trained on upload', 'Severity: high/medium/low', 'Creates SQL view for queries']) } },
      { name: 'K-Means', x: 770, y: 490, symbolSize: 24, category: 4,
        tooltip: { formatter: () => tt('CLUSTER + CLASSIFY + DECOMPOSE', ['K-Means (auto-K via silhouette)', 'GradientBoosting (GridSearchCV)', 'Seasonal decomposition', 'F1, Precision, Recall']) } },
      { name: 'Preprocessing', x: 660, y: 550, symbolSize: 22, category: 4,
        tooltip: { formatter: () => tt('ML PREPROCESSING (shared)', ['SimpleImputer (median/mode)', 'Temporal: month, quarter, weekday', 'Label encoding (< 50 categories)', 'No more dropna() data loss']) } },

      // ─── BACKGROUND + LEARNING ───
      { name: '11 Background', x: 400, y: 530, symbolSize: 35, symbol: 'roundRect', category: 6,
        tooltip: { formatter: () => tt('11 BACKGROUND AGENTS — EVERY CHAT', ['Judge: Quality score (1-5)', 'Rule Suggester: Extract rules', 'KG Extractor: 3-10 triples', 'Auto-Memory: Save facts', 'Meta Learner: Track corrections', 'Auto Evolver: Every 20 chats', 'User Prefs + Episodic Memory', 'Proactive Insights + Follow-ups']) } },
      { name: 'Self-Learning', x: 250, y: 590, symbolSize: 35, symbol: 'roundRect', category: 6,
        tooltip: { formatter: () => tt('SELF-LEARNING LOOP', [`${m.memories || 0} memories`, `${m.feedback || 0} feedback entries`, `Avg quality: ${m.quality_avg || 0}★`, 'Auto-evolve every 20 chats', 'ML retrain every 24h', 'Self-correction: 3 attempts']) } },

      // ─── DATA PIPELINE ───
      { name: 'Upload', x: 770, y: 20, symbolSize: 38, symbol: 'roundRect', category: 3,
        tooltip: { formatter: () => tt('DATA INGESTION — 18 FORMATS', ['CSV, Excel, JSON, SQL, PPTX, DOCX', 'PDF, MD, TXT, images (JPG/PNG/etc)', 'Excel: 5-layer pipeline', 'Vision OCR + contextual enrichment', 'Encoding detection (chardet)']) } },
      { name: 'Training', x: 770, y: 210, symbolSize: 35, symbol: 'roundRect', category: 3,
        tooltip: { formatter: () => tt('TRAINING PIPELINE — 14 STEPS', ['1. Drift check', '2. Deep analysis (Codex)', '3. Q&A generation', '4. Persona creation', '5. Workflows', '6. Relationships', '7. Knowledge index', '8. Brain fill (7 sub-steps)', '9. Domain knowledge (6 sub-steps)', '10-14. Seed, enrich, facts, KG, ML']) } },
      { name: 'Connectors', x: 620, y: 20, symbolSize: 28, category: 3,
        tooltip: { formatter: () => tt('DATA CONNECTORS', (arch.pipeline?.connectors || []).map((c: string) => `› ${c}`).concat(['', 'Live query on remote DBs', 'SSE streaming sync', 'Change detection'])) } },

      // ─── EXPORT ───
      { name: 'Export', x: 530, y: 590, symbolSize: 30, symbol: 'roundRect', category: 7,
        tooltip: { formatter: () => tt('EXPORT', (arch.pipeline?.export || []).map((e: string) => `› ${e}`).concat(['', 'Conversation-to-report', '8 PPTX design themes', 'Excel: 4 sheets + charts'])) } },

      // ─── OUTPUT ───
      { name: 'SSE Stream', x: 400, y: 640, symbolSize: 32, symbol: 'roundRect', category: 0,
        tooltip: { formatter: () => tt('SSE STREAM → BROWSER', ['ToolCallStarted → Completed', 'Content streaming (5-min timeout)', 'ML cards with badges', 'KPI cards, charts, tables', 'SOURCES tab, inline charts']) } },

      // ─── AI MODELS (right side) ───
      { name: `Chat Model`, x: 140, y: 160, symbolSize: 25, category: 0,
        tooltip: { formatter: () => tt('CHAT MODEL', [`${md.chat}`, 'Chat agents, SQL, vision, Q&A', 'Dashboard generation']) } },
      { name: `Deep Model`, x: 140, y: 210, symbolSize: 25, category: 6,
        tooltip: { formatter: () => tt('DEEP MODEL', [`${md.deep}`, 'Analysis, relationships, domain', 'ML predictions, auto-evolve']) } },
      { name: `Lite Model`, x: 140, y: 260, symbolSize: 25, category: 3,
        tooltip: { formatter: () => tt('LITE MODEL', [`${md.lite}`, 'Scoring, routing, extraction', 'Meta-learning, mining']) } },
    ];

    const links: any[] = [
      // Main request flow (thick, animated)
      { source: 'Users', target: 'Caddy', lineStyle: { width: 3 } },
      { source: 'Caddy', target: 'FastAPI', lineStyle: { width: 3 } },
      { source: 'FastAPI', target: 'Router', lineStyle: { width: 2.5 } },
      { source: 'Router', target: 'Leader', lineStyle: { width: 2.5 } },

      // DB connections
      { source: 'FastAPI', target: 'PgBouncer', lineStyle: { width: 2, type: 'dashed' } },
      { source: 'PgBouncer', target: 'PostgreSQL', lineStyle: { width: 2, type: 'dashed' } },

      // Agent delegation
      { source: 'Leader', target: 'Analyst' },
      { source: 'Leader', target: 'Researcher' },
      { source: 'Leader', target: 'Data Scientist' },
      { source: 'Leader', target: 'Engineer' },
      { source: 'Analyst', target: 'Specialists', lineStyle: { type: 'dashed' } },

      // Knowledge connections
      { source: 'Analyst', target: '13 Layers', lineStyle: { color: '#06b6d4' } },
      { source: 'Researcher', target: '13 Layers', lineStyle: { color: '#06b6d4' } },
      { source: '13 Layers', target: 'PgVector KB', lineStyle: { color: '#06b6d4' } },
      { source: '13 Layers', target: 'Brain', lineStyle: { color: '#06b6d4' } },
      { source: '13 Layers', target: 'KG', lineStyle: { color: '#06b6d4' } },
      { source: 'PgVector KB', target: 'Reranker', lineStyle: { color: '#06b6d4', type: 'dashed' } },
      { source: 'Brain', target: 'Reranker', lineStyle: { color: '#06b6d4', type: 'dashed' } },

      // ML connections
      { source: 'Data Scientist', target: 'AutoARIMA', lineStyle: { color: '#a855f7' } },
      { source: 'Data Scientist', target: 'LightGBM', lineStyle: { color: '#a855f7' } },
      { source: 'Data Scientist', target: 'IsolForest', lineStyle: { color: '#a855f7' } },
      { source: 'Data Scientist', target: 'K-Means', lineStyle: { color: '#a855f7' } },
      { source: 'AutoARIMA', target: 'Preprocessing', lineStyle: { color: '#a855f7', type: 'dashed' } },
      { source: 'LightGBM', target: 'Preprocessing', lineStyle: { color: '#a855f7', type: 'dashed' } },
      { source: 'Data Scientist', target: 'ML Worker', lineStyle: { color: '#a855f7' } },
      { source: 'ML Worker', target: 'PostgreSQL', lineStyle: { color: '#a855f7', type: 'dashed' } },

      // Background + learning loop
      { source: 'Leader', target: '11 Background', lineStyle: { color: '#ec4899' } },
      { source: '11 Background', target: 'Self-Learning', lineStyle: { color: '#ec4899' } },
      { source: 'Self-Learning', target: '13 Layers', lineStyle: { color: '#ec4899', type: 'dashed' } },

      // Data pipeline
      { source: 'Connectors', target: 'Upload', lineStyle: { color: '#f59e0b' } },
      { source: 'Upload', target: 'FastAPI', lineStyle: { color: '#f59e0b' } },
      { source: 'Upload', target: 'Training', lineStyle: { color: '#f59e0b' } },
      { source: 'Training', target: 'PostgreSQL', lineStyle: { color: '#f59e0b', type: 'dashed' } },

      // Export + output
      { source: 'Engineer', target: 'Export', lineStyle: { color: '#84cc16' } },
      { source: 'Leader', target: 'SSE Stream', lineStyle: { width: 2.5 } },
      { source: 'SSE Stream', target: 'Users', lineStyle: { width: 2.5, type: 'dashed' } },

      // Model connections
      { source: 'Chat Model', target: 'FastAPI', lineStyle: { type: 'dotted', color: '#666' } },
      { source: 'Deep Model', target: 'FastAPI', lineStyle: { type: 'dotted', color: '#666' } },
      { source: 'Lite Model', target: 'FastAPI', lineStyle: { type: 'dotted', color: '#666' } },
    ];

    archChart.setOption({
      backgroundColor: 'transparent',
      tooltip: { trigger: 'item', backgroundColor: '#0a0a0a', borderColor: '#333', borderWidth: 1, padding: 12,
        textStyle: { color: '#ddd', fontSize: 11, fontFamily: 'var(--font-family-display)' },
        extraCssText: 'max-width: 320px; white-space: normal;' },
      legend: { data: cats.map(c => c.name), bottom: 4, textStyle: { color: '#888', fontSize: 9, fontFamily: 'var(--font-family-display)' }, itemWidth: 10, itemHeight: 10, itemGap: 14 },
      animationDuration: 1500,
      animationEasingUpdate: 'quinticInOut',
      series: [{
        type: 'graph',
        layout: 'none',
        roam: true,
        zoom: 1.05,
        scaleLimit: { min: 0.5, max: 3 },
        categories: cats,
        nodes: nodes.map(n => ({
          ...n,
          label: { show: true, fontSize: 9, color: '#ddd', fontWeight: 'bold',
            fontFamily: 'var(--font-family-display)',
            formatter: (p: any) => p.name, position: 'inside', lineHeight: 12 },
          itemStyle: { borderWidth: 2, borderColor: '#222', shadowBlur: 8, shadowColor: 'rgba(0,0,0,0.5)' },
        })),
        links: links.map(l => ({
          ...l,
          lineStyle: { color: l.lineStyle?.color || '#444', width: l.lineStyle?.width || 1.5, curveness: 0.15, type: l.lineStyle?.type || 'solid', opacity: 0.7 },
          symbol: ['none', 'arrow'], symbolSize: [0, 8],
        })),
        emphasis: {
          focus: 'adjacency',
          lineStyle: { width: 4, opacity: 1 },
          itemStyle: { borderWidth: 3, borderColor: '#fff', shadowBlur: 15, shadowColor: 'rgba(255,255,255,0.3)' },
          label: { fontSize: 11 },
        },
      }],
    });

    window.addEventListener('resize', () => archChart?.resize());
  }

  /* ─── INTEGRATIONS state ─── */
  let spAdminConfig = $state<any>({});
  let spAdminSaving = $state(false);
  let spAdminMsg = $state('');
  let spAdminClientId = $state('');
  let spAdminClientSecret = $state('');
  let spAdminTenantId = $state('');
  let spAllSources = $state<any[]>([]);

  let gdAdminClientId = $state('');
  let gdAdminClientSecret = $state('');
  let gdAdminConfig = $state<any>({});
  let gdAdminSaving = $state(false);
  let gdAdminMsg = $state('');
  let dbAllSources = $state<any[]>([]);

  // DB connector form (admin can connect to any project)
  let dbAdminStep = $state<'idle' | 'form' | 'tables'>('idle');
  let dbAdminType = $state('postgresql');
  let dbAdminHost = $state('');
  let dbAdminPort = $state('5432');
  let dbAdminUser = $state('');
  let dbAdminPass = $state('');
  let dbAdminName = $state('');
  let dbAdminProject = $state('');
  let dbAdminTesting = $state(false);
  let dbAdminTestResult = $state<any>(null);
  let dbAdminTables = $state<any[]>([]);
  let dbAdminSelectedTables = $state<string[]>([]);
  let dbAdminConnecting = $state(false);
  let dbAdminMsg2 = $state('');

  async function dbAdminTest() {
    dbAdminTesting = true; dbAdminTestResult = null;
    try {
      const r = await fetch('/api/connectors/test', {
        method: 'POST', headers: { ..._h(), 'Content-Type': 'application/json' },
        body: JSON.stringify({ host: dbAdminHost, port: parseInt(dbAdminPort), username: dbAdminUser, password: dbAdminPass, database: dbAdminName, db_type: dbAdminType })
      });
      dbAdminTestResult = await r.json();
      if (dbAdminTestResult.tables) { dbAdminTables = dbAdminTestResult.tables; dbAdminStep = 'tables'; }
    } catch { dbAdminTestResult = { error: 'Connection failed' }; }
    dbAdminTesting = false;
  }
  async function dbAdminConnect() {
    if (!dbAdminProject) { dbAdminMsg2 = 'Select a project first'; return; }
    dbAdminConnecting = true; dbAdminMsg2 = '';
    try {
      const r = await fetch('/api/connectors/connect', {
        method: 'POST', headers: { ..._h(), 'Content-Type': 'application/json' },
        body: JSON.stringify({
          project_slug: dbAdminProject, host: dbAdminHost, port: parseInt(dbAdminPort),
          username: dbAdminUser, password: dbAdminPass, database: dbAdminName,
          db_type: dbAdminType, selected_tables: dbAdminSelectedTables, sync_schedule: 'manual',
        })
      });
      if (r.ok) {
        dbAdminMsg2 = `Connected ${dbAdminSelectedTables.length} tables to ${dbAdminProject}!`;
        dbAdminStep = 'idle'; dbAdminHost = ''; dbAdminUser = ''; dbAdminPass = ''; dbAdminName = '';
        dbAdminSelectedTables = []; dbAdminTables = [];
        tabLoaded['integrations'] = false; await loadIntegrations();
      } else { const d = await r.json(); dbAdminMsg2 = d.detail || 'Failed'; }
    } catch { dbAdminMsg2 = 'Failed'; }
    dbAdminConnecting = false;
  }

  /* ─── tab switch loader ─── */
  let tabLoaded = $state<Record<string, boolean>>({});
  let tabData = $state<Record<string, any>>({});

  async function switchTab(id: string) {
    activeTab = id;
    if (tabLoaded[id]) return;
    tabLoaded[id] = true;
    loading = true;
    try {
      if (id === 'users')    await loadUsers();
      if (id === 'projects') await loadProjects();
      if (id === 'logs')     await loadLogs();
      if (id === 'schemas')  await loadSchemas();
      if (id === 'chatLogs') await loadChatLogs();
      if (id === 'health')   await loadHealth();
      if (id === 'stats')    await loadStats();
      if (id === 'integrations') await loadIntegrations();
      if (id === 'architecture') await loadArchitecture();
    } catch {}
    loading = false;
  }

  onMount(() => { switchTab('users'); });

  /* ═══════════════════════════════════════════════════════════ */
  /*  DATA LOADERS                                              */
  /* ═══════════════════════════════════════════════════════════ */

  async function loadUsers() {
    try {
      const res = await fetch('/api/auth/users', { headers: _h() });
      if (res.ok) { const d = await res.json(); users = d.users || []; }
    } catch {}
  }

  async function toggleUserDetail(userId: string) {
    if (expandedUserId === userId) { expandedUserId = null; userDetail = null; return; }
    expandedUserId = userId;
    userDetail = null;
    loadingUserDetail = true;
    try {
      const res = await fetch(`/api/auth/admin/user/${userId}/detail`, { headers: _h() });
      if (res.ok) userDetail = await res.json();
    } catch {}
    loadingUserDetail = false;
  }

  async function createUser() {
    if (!newUsername || !newPassword) return;
    try {
      const params = new URLSearchParams({ username: newUsername, password: newPassword, email: newEmail });
      const res = await fetch(`/api/auth/users/create?${params}`, { method: 'POST', headers: _h() });
      if (res.ok) { showCreateUser = false; newUsername = ''; newPassword = ''; newEmail = ''; tabLoaded['users'] = false; await loadUsers(); }
      else { const d = await res.json(); alert(d.detail || 'Failed'); }
    } catch {}
  }

  async function deleteUser(username: string) {
    if (!confirm(`Delete "${username}" and ALL their projects/data?`)) return;
    try { await fetch(`/api/auth/users/${username}`, { method: 'DELETE', headers: _h() }); expandedUserId = null; await loadUsers(); } catch {}
  }

  async function resetUserPassword() {
    if (!resetUser || !resetPass) return;
    resetMsg = '';
    try {
      const res = await fetch(`/api/auth/users/${resetUser}/reset-password?new_password=${encodeURIComponent(resetPass)}`, { method: 'POST', headers: _h() });
      resetMsg = res.ok ? 'Password reset!' : 'Failed';
      resetPass = '';
    } catch { resetMsg = 'Failed'; }
  }

  async function loadProjects() {
    try {
      const res = await fetch('/api/auth/admin/projects', { headers: _h() });
      if (res.ok) { const d = await res.json(); projects = d.projects || d || []; }
    } catch {}
  }

  async function toggleProjectDetail(slug: string) {
    if (expandedProjectSlug === slug) { expandedProjectSlug = null; projectDetail = null; return; }
    expandedProjectSlug = slug;
    projectDetail = null;
    loadingProjectDetail = true;
    try {
      const res = await fetch(`/api/projects/${slug}/detail`, { headers: _h() });
      if (res.ok) projectDetail = await res.json();
    } catch {}
    loadingProjectDetail = false;
  }

  async function loadLogs() {
    try {
      const res = await fetch('/api/auth/admin/audit-log', { headers: _h() });
      if (res.ok) { const d = await res.json(); logs = d.logs || d.entries || d || []; }
    } catch {}
  }

  async function loadSchemas() {
    try {
      const res = await fetch('/api/auth/admin/schemas', { headers: _h() });
      if (res.ok) { const d = await res.json(); schemas = d.schemas || d || []; }
    } catch {}
  }

  async function loadChatLogs() {
    try {
      let url = '/api/auth/admin/chat-logs?limit=50';
      if (chatFilterUser) url += `&user=${encodeURIComponent(chatFilterUser)}`;
      if (chatFilterProject) url += `&project=${encodeURIComponent(chatFilterProject)}`;
      const res = await fetch(url, { headers: _h() });
      if (res.ok) { const d = await res.json(); chatLogs = d.sessions || d.logs || d || []; }
    } catch {}
  }

  async function loadHealth() {
    try {
      const res = await fetch('/api/auth/admin/health', { headers: _h() });
      if (res.ok) health = await res.json();
    } catch {}
  }

  async function loadStats() {
    try {
      const res = await fetch('/api/auth/admin/stats', { headers: _h() });
      if (res.ok) stats = await res.json();
    } catch {}
  }

  async function loadIntegrations() {
    try {
      const res = await fetch('/api/sharepoint/admin/config', { headers: _h() });
      if (res.ok) {
        const d = await res.json();
        spAdminConfig = d;
        spAdminClientId = d.client_id || '';
        spAdminClientSecret = '';
        spAdminTenantId = d.tenant_id || '';
        spAllSources = d.sources || [];
      }
    } catch {}
    try {
      const res = await fetch('/api/gdrive/admin/config', { headers: _h() });
      if (res.ok) {
        const d = await res.json();
        gdAdminConfig = d;
        gdAdminClientId = d.client_id || '';
        gdAdminClientSecret = '';
      }
    } catch {}
    try {
      const res = await fetch('/api/connectors/admin/sources', { headers: _h() });
      if (res.ok) {
        const d = await res.json();
        dbAllSources = d.sources || d || [];
      }
    } catch {}
    // Load projects for DB connector project picker
    if (!projects.length) await loadProjects();
  }

  async function saveSharePointConfig() {
    spAdminSaving = true; spAdminMsg = '';
    try {
      const res = await fetch('/api/sharepoint/admin/config', {
        method: 'POST', headers: { ..._h(), 'Content-Type': 'application/json' },
        body: JSON.stringify({
          client_id: spAdminClientId,
          client_secret: spAdminClientSecret,
          tenant_id: spAdminTenantId,
        })
      });
      if (res.ok) {
        spAdminMsg = 'Saved! Restart Docker for changes to take effect.';
        spAdminClientSecret = '';
      } else {
        const d = await res.json();
        spAdminMsg = d.detail || 'Failed to save';
      }
    } catch { spAdminMsg = 'Failed to save'; }
    spAdminSaving = false;
  }

  async function saveGDriveConfig() {
    gdAdminSaving = true; gdAdminMsg = '';
    try {
      const res = await fetch('/api/gdrive/admin/config', {
        method: 'POST', headers: { ..._h(), 'Content-Type': 'application/json' },
        body: JSON.stringify({
          client_id: gdAdminClientId,
          client_secret: gdAdminClientSecret,
        })
      });
      if (res.ok) {
        gdAdminMsg = 'Saved! Restart Docker for changes to take effect.';
        gdAdminClientSecret = '';
      } else {
        const d = await res.json();
        gdAdminMsg = d.detail || 'Failed to save';
      }
    } catch { gdAdminMsg = 'Failed to save'; }
    gdAdminSaving = false;
  }

  /* ─── helpers ─── */
  function fmtDate(d: string | null | undefined): string {
    if (!d) return '-';
    try { return new Date(d).toLocaleString('en-US', { month: 'short', day: 'numeric', year: 'numeric', hour: '2-digit', minute: '2-digit' }); }
    catch { return d.slice(0, 19); }
  }

  function filteredLogs() {
    let out = logs;
    if (logFilterAction) out = out.filter((l: any) => (l.action || l.event || '').toLowerCase().includes(logFilterAction.toLowerCase()));
    if (logFilterUser)   out = out.filter((l: any) => (l.username || l.user || l.user_id || '').toLowerCase().includes(logFilterUser.toLowerCase()));
    if (logFilterProject) out = out.filter((l: any) => (l.project || l.slug || l.project_slug || '').toLowerCase().includes(logFilterProject.toLowerCase()));
    return out;
  }
</script>

<div style="padding: 16px; overflow-y: auto; height: 100%;">
<div style="width: 100%; display: flex; flex-direction: column; flex: 1; min-height: 0;">

<!-- ═══ TABS ═══ -->
<div style="display: flex; flex-direction: column; flex: 1; min-height: 0;">
<div class="dash-tabs" style="flex-shrink: 0; flex-wrap: wrap;">
  {#each tabs as tab}
    <button
      class="dash-tab"
      class:dash-tab-active={activeTab === tab.id}
      onclick={() => switchTab(tab.id)}
      style="cursor: pointer;"
    >
      {tab.label}
    </button>
  {/each}
</div>

<div class="dash-panel">

<!-- ═══════════════════════════════════════════════════════════ -->
<!-- USERS TAB                                                  -->
<!-- ═══════════════════════════════════════════════════════════ -->
{#if activeTab === 'users'}
  <div class="cli-terminal" style="margin-bottom: 16px; padding: 8px 14px;">
    <div class="cli-line">
      <span class="cli-prompt">$</span>
      <span class="cli-command">dash admin --users</span>
      <span style="margin-left: auto; font-size: 11px; opacity: 0.6;">{users.length} users</span>
    </div>
  </div>

  <div class="flex items-center justify-between mb-4">
    <div style="font-size: 18px; font-weight: 900; text-transform: uppercase;">Users</div>
    <button class="send-btn" style="font-size: 10px; padding: 6px 14px;" onclick={() => showCreateUser = true}>+ CREATE USER</button>
  </div>

  {#if loading && users.length === 0}
    <div style="font-size: 12px; color: var(--color-on-surface-dim);">Loading...</div>
  {:else}
    <table class="data-table" style="width: 100%;">
      <thead><tr>
        <th>USER</th>
        <th>EMAIL</th>
        <th>ROLE</th>
        <th>DEPT</th>
        <th style="text-align: right;">PROJECTS</th>
        <th>STATUS</th>
        <th>AUTH</th>
        <th style="text-align: right;">ACTIONS</th>
      </tr></thead>
      <tbody>
        {#each users as u}
          <tr style="cursor: pointer; {u.is_active === false ? 'opacity: 0.5;' : ''}" onclick={() => toggleUserDetail(u.id || u.username)}>
            <td>
              <div class="flex items-center gap-2">
                <div style="background: var(--color-primary-container); width: 24px; height: 24px; display: flex; align-items: center; justify-content: center; font-weight: 900; font-size: 10px; border: 1px solid var(--color-on-surface); flex-shrink: 0;">{u.username.charAt(0).toUpperCase()}</div>
                <div>
                  <div style="font-weight: 900;">{u.first_name && u.last_name ? `${u.first_name} ${u.last_name}` : u.username}</div>
                  {#if u.first_name}<div style="font-size: 9px; color: var(--color-on-surface-dim);">@{u.username}</div>{/if}
                </div>
              </div>
            </td>
            <td style="font-size: 11px; color: var(--color-on-surface-dim);">{u.email || '-'}</td>
            <td>
              {#if u.is_super}<span class="tag-label" style="font-size: 8px; background: var(--color-error);">SUPER ADMIN</span>
              {:else}<span class="tag-label" style="font-size: 8px;">USER</span>{/if}
            </td>
            <td style="font-size: 11px; color: var(--color-on-surface-dim);">{u.department || '-'}</td>
            <td style="text-align: right; font-weight: 900;">{u.project_count || 0}</td>
            <td>
              {#if u.is_active !== false}
                <span style="color: var(--color-primary); font-size: 10px; font-weight: 700;">ACTIVE</span>
              {:else}
                <span style="color: var(--color-error); font-size: 10px; font-weight: 700;">DISABLED</span>
              {/if}
            </td>
            <td style="font-size: 10px; color: var(--color-on-surface-dim);">{u.auth_provider || 'local'}</td>
            <td style="text-align: right;" onclick={(e: MouseEvent) => e.stopPropagation()}>
              {#if !u.is_super}
                <div class="flex gap-1 justify-end">
                  <button class="feedback-btn" style="font-size: 9px; font-weight: 700; text-transform: uppercase; padding: 2px 6px;" onclick={() => { resetUser = u.username; resetPass = ''; resetMsg = ''; }}>PW</button>
                  <button class="feedback-btn" style="font-size: 9px; font-weight: 700; text-transform: uppercase; padding: 2px 6px;" onclick={async () => {
                    await fetch(`/api/auth/users/${u.username}/toggle-active`, { method: 'POST', headers: _h() });
                    await loadUsers();
                  }}>{u.is_active !== false ? 'DISABLE' : 'ENABLE'}</button>
                  <button class="feedback-btn" style="font-size: 9px; font-weight: 700; text-transform: uppercase; padding: 2px 6px; color: var(--color-error); border-color: var(--color-error);" onclick={() => deleteUser(u.username)}>DEL</button>
                </div>
              {/if}
            </td>
          </tr>

          <!-- Expanded user detail row -->
          {#if expandedUserId === (u.id || u.username)}
            <tr>
              <td colspan="8" style="padding: 0; border: none;">
                <div class="ink-border" style="margin: 8px 0 12px 0; padding: 16px; background: var(--color-surface-bright);">
                  {#if loadingUserDetail}
                    <div style="font-size: 12px; color: var(--color-on-surface-dim);">Loading user detail...</div>
                  {:else if userDetail}
                    <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 16px;">
                      <!-- Owned projects -->
                      <div>
                        <div style="font-size: 9px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.08em; margin-bottom: 8px; border-bottom: 1px solid var(--color-on-surface); padding-bottom: 4px;">Owned Projects</div>
                        {#if userDetail.owned_projects?.length}
                          {#each userDetail.owned_projects as p}
                            <div style="font-size: 12px; margin-bottom: 4px; font-weight: 700;">{p.agent_name || p.name || p.slug} <span style="font-weight: 400; color: var(--color-on-surface-dim); font-size: 10px;">{p.slug}</span></div>
                          {/each}
                        {:else}<div style="font-size: 11px; color: var(--color-on-surface-dim);">None</div>{/if}
                      </div>
                      <!-- Shared projects -->
                      <div>
                        <div style="font-size: 9px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.08em; margin-bottom: 8px; border-bottom: 1px solid var(--color-on-surface); padding-bottom: 4px;">Shared With User</div>
                        {#if userDetail.shared_projects?.length}
                          {#each userDetail.shared_projects as p}
                            <div style="font-size: 12px; margin-bottom: 4px; font-weight: 700;">{p.agent_name || p.name || p.slug} <span class="tag-label" style="font-size: 7px;">{p.role || 'viewer'}</span></div>
                          {/each}
                        {:else}<div style="font-size: 11px; color: var(--color-on-surface-dim);">None</div>{/if}
                      </div>
                      <!-- Recent activity -->
                      <div>
                        <div style="font-size: 9px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.08em; margin-bottom: 8px; border-bottom: 1px solid var(--color-on-surface); padding-bottom: 4px;">Recent Activity</div>
                        {#if userDetail.recent_activity?.length}
                          {#each userDetail.recent_activity.slice(0, 5) as a}
                            <div style="font-size: 11px; margin-bottom: 3px;">
                              <span style="font-weight: 700;">{a.action || a.event}</span>
                              <span style="color: var(--color-on-surface-dim); margin-left: 6px;">{fmtDate(a.created_at || a.timestamp)}</span>
                            </div>
                          {/each}
                        {:else}<div style="font-size: 11px; color: var(--color-on-surface-dim);">No recent activity</div>{/if}
                      </div>
                      <!-- Feedback stats -->
                      <div>
                        <div style="font-size: 9px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.08em; margin-bottom: 8px; border-bottom: 1px solid var(--color-on-surface); padding-bottom: 4px;">Feedback Stats</div>
                        <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 8px;">
                          <div class="ink-border" style="padding: 8px; text-align: center; background: var(--color-surface);">
                            <div style="font-size: 20px; font-weight: 900;">{userDetail.feedback?.good ?? userDetail.feedback_good ?? 0}</div>
                            <div style="font-size: 9px; text-transform: uppercase; color: var(--color-primary);">Good</div>
                          </div>
                          <div class="ink-border" style="padding: 8px; text-align: center; background: var(--color-surface);">
                            <div style="font-size: 20px; font-weight: 900;">{userDetail.feedback?.bad ?? userDetail.feedback_bad ?? 0}</div>
                            <div style="font-size: 9px; text-transform: uppercase; color: var(--color-error);">Bad</div>
                          </div>
                        </div>
                      </div>
                    </div>
                  {:else}
                    <div style="font-size: 12px; color: var(--color-on-surface-dim);">No detail available.</div>
                  {/if}
                </div>
              </td>
            </tr>
          {/if}
        {/each}
      </tbody>
    </table>

    {#if resetUser}
      <div class="ink-border p-3 mt-3" style="background: var(--color-surface);">
        <div style="font-size: 11px; font-weight: 900; text-transform: uppercase; margin-bottom: 6px;">Reset password: {resetUser}</div>
        <div class="flex gap-2 items-end">
          <input type="password" bind:value={resetPass} placeholder="New password" style="flex: 1; border: 2px solid var(--color-on-surface); padding: 6px 10px; font-family: var(--font-family-display); font-size: 12px; background: var(--color-surface-dim);" />
          <button class="send-btn" onclick={resetUserPassword} style="padding: 6px 12px; font-size: 10px; cursor: pointer;">RESET</button>
          <button class="feedback-btn" onclick={() => resetUser = ''} style="padding: 4px 8px; font-size: 10px; cursor: pointer;">CANCEL</button>
        </div>
        {#if resetMsg}<div style="font-size: 11px; margin-top: 6px; color: {resetMsg.includes('reset') ? 'var(--color-primary)' : 'var(--color-error)'};">{resetMsg}</div>{/if}
      </div>
    {/if}
  {/if}

<!-- ═══════════════════════════════════════════════════════════ -->
<!-- PROJECTS TAB                                               -->
<!-- ═══════════════════════════════════════════════════════════ -->
{:else if activeTab === 'projects'}
  <div class="cli-terminal" style="margin-bottom: 16px; padding: 8px 14px;">
    <div class="cli-line">
      <span class="cli-prompt">$</span>
      <span class="cli-command">dash admin --projects</span>
      <span style="margin-left: auto; font-size: 11px; opacity: 0.6;">{projects.length} projects</span>
    </div>
  </div>

  {#if loading && projects.length === 0}
    <div style="font-size: 12px; color: var(--color-on-surface-dim);">Loading...</div>
  {:else if projects.length === 0}
    <div style="font-size: 12px; color: var(--color-on-surface-dim);">No projects found.</div>
  {:else}
    <table class="data-table" style="width: 100%;">
      <thead><tr>
        <th>PROJECT</th>
        <th>OWNER</th>
        <th style="text-align: right;">TABLES</th>
        <th style="text-align: right;">ROWS</th>
        <th>SCHEMA</th>
        <th>TRAINED</th>
        <th>HEALTH</th>
      </tr></thead>
      <tbody>
        {#each projects as p}
          <tr style="cursor: pointer;" onclick={() => toggleProjectDetail(p.slug)}>
            <td>
              <div style="font-weight: 900;">{p.agent_name || p.name || p.slug}</div>
              <div style="font-size: 9px; color: var(--color-on-surface-dim);">{p.slug}</div>
            </td>
            <td style="font-size: 11px;">{p.owner || p.username || '-'}</td>
            <td style="text-align: right; font-weight: 900;">{p.tables ?? p.table_count ?? 0}</td>
            <td style="text-align: right;">{(p.rows ?? p.total_rows ?? 0).toLocaleString()}</td>
            <td><span style="font-family: var(--font-family-display); font-size: 10px;">{p.schema_name || p.schema || '-'}</span></td>
            <td style="font-size: 10px; color: var(--color-on-surface-dim);">{fmtDate(p.last_trained || p.trained_at)}</td>
            <td>
              {#if p.health === 'good' || p.health === 'healthy' || p.brain_health?.status === 'good'}
                <span style="color: var(--color-primary); font-size: 10px; font-weight: 700;">GOOD</span>
              {:else if p.health === 'warning' || p.brain_health?.status === 'warning'}
                <span style="color: orange; font-size: 10px; font-weight: 700;">WARN</span>
              {:else if p.health}
                <span style="color: var(--color-error); font-size: 10px; font-weight: 700;">{String(p.health).toUpperCase()}</span>
              {:else}
                <span style="font-size: 10px; color: var(--color-on-surface-dim);">-</span>
              {/if}
            </td>
          </tr>

          <!-- Expanded project detail row -->
          {#if expandedProjectSlug === p.slug}
            <tr>
              <td colspan="7" style="padding: 0; border: none;">
                <div class="ink-border" style="margin: 8px 0 12px 0; padding: 16px; background: var(--color-surface-bright);">
                  {#if loadingProjectDetail}
                    <div style="font-size: 12px; color: var(--color-on-surface-dim);">Loading project detail...</div>
                  {:else if projectDetail}
                    <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 16px;">
                      <!-- Brain layers -->
                      <div>
                        <div style="font-size: 9px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.08em; margin-bottom: 8px; border-bottom: 1px solid var(--color-on-surface); padding-bottom: 4px;">Brain Layers</div>
                        <div style="display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 6px;">
                          {#each [
                            { label: 'Vectors', value: projectDetail.knowledge_vectors ?? 0 },
                            { label: 'Learnings', value: projectDetail.learnings ?? 0 },
                            { label: 'Patterns', value: projectDetail.patterns ?? projectDetail.query_patterns ?? 0 },
                          ] as m}
                            <div class="ink-border" style="padding: 6px; text-align: center; background: var(--color-surface);">
                              <div style="font-size: 16px; font-weight: 900;">{m.value}</div>
                              <div style="font-size: 8px; text-transform: uppercase;">{m.label}</div>
                            </div>
                          {/each}
                        </div>
                      </div>
                      <!-- Shared users -->
                      <div>
                        <div style="font-size: 9px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.08em; margin-bottom: 8px; border-bottom: 1px solid var(--color-on-surface); padding-bottom: 4px;">Shared Users</div>
                        {#if projectDetail.shared_users?.length}
                          {#each projectDetail.shared_users as su}
                            <div style="font-size: 12px; margin-bottom: 3px;">{su.username || su} <span class="tag-label" style="font-size: 7px;">{su.role || 'viewer'}</span></div>
                          {/each}
                        {:else}<div style="font-size: 11px; color: var(--color-on-surface-dim);">Not shared</div>{/if}
                      </div>
                      <!-- Tables list -->
                      <div>
                        <div style="font-size: 9px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.08em; margin-bottom: 8px; border-bottom: 1px solid var(--color-on-surface); padding-bottom: 4px;">Tables</div>
                        {#if projectDetail.tables?.length}
                          {#each projectDetail.tables as t}
                            <div style="font-size: 11px; margin-bottom: 3px; font-weight: 700;">{t.name || t} <span style="font-weight: 400; color: var(--color-on-surface-dim);">{t.rows != null ? `${t.rows.toLocaleString()} rows` : ''} {t.columns != null ? `${t.columns} cols` : ''}</span></div>
                          {/each}
                        {:else}<div style="font-size: 11px; color: var(--color-on-surface-dim);">No tables</div>{/if}
                      </div>
                      <!-- Recent chats -->
                      <div>
                        <div style="font-size: 9px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.08em; margin-bottom: 8px; border-bottom: 1px solid var(--color-on-surface); padding-bottom: 4px;">Recent Chats</div>
                        {#if projectDetail.recent_chats?.length}
                          {#each projectDetail.recent_chats.slice(0, 5) as c}
                            <div style="font-size: 11px; margin-bottom: 3px;">{c.message || c.first_message || c.session_id?.slice(0, 12)} <span style="color: var(--color-on-surface-dim);">{fmtDate(c.created_at)}</span></div>
                          {/each}
                        {:else}<div style="font-size: 11px; color: var(--color-on-surface-dim);">No recent chats</div>{/if}
                      </div>
                    </div>
                  {:else}
                    <div style="font-size: 12px; color: var(--color-on-surface-dim);">No detail available.</div>
                  {/if}
                </div>
              </td>
            </tr>
          {/if}
        {/each}
      </tbody>
    </table>
  {/if}

<!-- ═══════════════════════════════════════════════════════════ -->
<!-- LOGS TAB                                                   -->
<!-- ═══════════════════════════════════════════════════════════ -->
{:else if activeTab === 'logs'}
  <div class="cli-terminal" style="margin-bottom: 16px; padding: 8px 14px;">
    <div class="cli-line">
      <span class="cli-prompt">$</span>
      <span class="cli-command">dash admin --audit-log</span>
      <span style="margin-left: auto; font-size: 11px; opacity: 0.6;">{filteredLogs().length} entries</span>
    </div>
  </div>

  <!-- Filters -->
  <div class="flex gap-3 mb-4 items-center" style="flex-wrap: wrap;">
    <div>
      <div style="font-size: 8px; font-weight: 700; text-transform: uppercase; margin-bottom: 2px;">Action</div>
      <input type="text" bind:value={logFilterAction} placeholder="Filter action..." style="border: 2px solid var(--color-on-surface); padding: 4px 8px; font-family: var(--font-family-display); font-size: 11px; background: var(--color-surface); width: 140px;" />
    </div>
    <div>
      <div style="font-size: 8px; font-weight: 700; text-transform: uppercase; margin-bottom: 2px;">User</div>
      <input type="text" bind:value={logFilterUser} placeholder="Filter user..." style="border: 2px solid var(--color-on-surface); padding: 4px 8px; font-family: var(--font-family-display); font-size: 11px; background: var(--color-surface); width: 140px;" />
    </div>
    <div>
      <div style="font-size: 8px; font-weight: 700; text-transform: uppercase; margin-bottom: 2px;">Project</div>
      <input type="text" bind:value={logFilterProject} placeholder="Filter project..." style="border: 2px solid var(--color-on-surface); padding: 4px 8px; font-family: var(--font-family-display); font-size: 11px; background: var(--color-surface); width: 140px;" />
    </div>
    <button class="feedback-btn" style="font-size: 9px; font-weight: 700; text-transform: uppercase; padding: 4px 10px; cursor: pointer; align-self: flex-end;" onclick={() => { tabLoaded['logs'] = false; loadLogs(); }}>REFRESH</button>
  </div>

  {#if filteredLogs().length === 0}
    <div style="font-size: 12px; color: var(--color-on-surface-dim);">No log entries found.</div>
  {:else}
    <table class="data-table" style="width: 100%;">
      <thead><tr>
        <th>ACTION</th>
        <th>USER</th>
        <th>PROJECT</th>
        <th>DETAIL</th>
        <th>TIME</th>
      </tr></thead>
      <tbody>
        {#each filteredLogs() as l}
          <tr>
            <td><span class="tag-label" style="font-size: 8px;">{l.action || l.event || '-'}</span></td>
            <td style="font-size: 11px;">{l.username || l.user || l.user_id || '-'}</td>
            <td style="font-size: 11px;">{l.project || l.slug || l.project_slug || '-'}</td>
            <td style="font-size: 10px; color: var(--color-on-surface-dim); max-width: 300px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">{l.detail || l.details || l.message || '-'}</td>
            <td style="font-size: 10px; color: var(--color-on-surface-dim);">{fmtDate(l.created_at || l.timestamp)}</td>
          </tr>
        {/each}
      </tbody>
    </table>
  {/if}

<!-- ═══════════════════════════════════════════════════════════ -->
<!-- SCHEMAS TAB                                                -->
<!-- ═══════════════════════════════════════════════════════════ -->
{:else if activeTab === 'schemas'}
  <div class="cli-terminal" style="margin-bottom: 16px; padding: 8px 14px;">
    <div class="cli-line">
      <span class="cli-prompt">$</span>
      <span class="cli-command">dash admin --schemas</span>
      <span style="margin-left: auto; font-size: 11px; opacity: 0.6;">{schemas.length} schemas</span>
    </div>
  </div>

  {#if loading && schemas.length === 0}
    <div style="font-size: 12px; color: var(--color-on-surface-dim);">Loading...</div>
  {:else if schemas.length === 0}
    <div style="font-size: 12px; color: var(--color-on-surface-dim);">No schemas found.</div>
  {:else}
    <table class="data-table" style="width: 100%;">
      <thead><tr>
        <th>SCHEMA</th>
        <th style="text-align: right;">TABLES</th>
        <th>OWNER</th>
      </tr></thead>
      <tbody>
        {#each schemas as s}
          <tr style="cursor: pointer;" onclick={() => expandedSchema = expandedSchema === (s.name || s.schema_name) ? null : (s.name || s.schema_name)}>
            <td style="font-weight: 900; font-family: var(--font-family-display);">{s.name || s.schema_name}</td>
            <td style="text-align: right; font-weight: 900;">{s.tables?.length ?? s.table_count ?? 0}</td>
            <td style="font-size: 11px; color: var(--color-on-surface-dim);">{s.owner || s.username || '-'}</td>
          </tr>

          <!-- Expanded schema detail -->
          {#if expandedSchema === (s.name || s.schema_name)}
            <tr>
              <td colspan="3" style="padding: 0; border: none;">
                <div class="ink-border" style="margin: 8px 0 12px 0; padding: 16px; background: var(--color-surface-bright);">
                  {#if s.tables?.length}
                    <table class="data-table" style="width: 100%;">
                      <thead><tr>
                        <th>TABLE</th>
                        <th style="text-align: right;">ROWS</th>
                        <th>COLUMNS</th>
                      </tr></thead>
                      <tbody>
                        {#each s.tables as t}
                          <tr>
                            <td style="font-weight: 700;">{t.name || t.table_name}</td>
                            <td style="text-align: right;">{(t.rows ?? t.row_count ?? 0).toLocaleString()}</td>
                            <td style="font-size: 10px; color: var(--color-on-surface-dim);">
                              {#if t.columns?.length}
                                {t.columns.map((c: any) => typeof c === 'string' ? c : c.name || c.column_name).join(', ')}
                              {:else}
                                {t.column_count ?? '-'}
                              {/if}
                            </td>
                          </tr>
                        {/each}
                      </tbody>
                    </table>
                  {:else}
                    <div style="font-size: 11px; color: var(--color-on-surface-dim);">No tables in schema.</div>
                  {/if}
                </div>
              </td>
            </tr>
          {/if}
        {/each}
      </tbody>
    </table>
  {/if}

<!-- ═══════════════════════════════════════════════════════════ -->
<!-- CHAT LOGS TAB                                              -->
<!-- ═══════════════════════════════════════════════════════════ -->
{:else if activeTab === 'chatLogs'}
  <div class="cli-terminal" style="margin-bottom: 16px; padding: 8px 14px;">
    <div class="cli-line">
      <span class="cli-prompt">$</span>
      <span class="cli-command">dash admin --chat-logs</span>
      <span style="margin-left: auto; font-size: 11px; opacity: 0.6;">{chatLogs.length} sessions</span>
    </div>
  </div>

  <!-- Filters -->
  <div class="flex gap-3 mb-4 items-center" style="flex-wrap: wrap;">
    <div>
      <div style="font-size: 8px; font-weight: 700; text-transform: uppercase; margin-bottom: 2px;">User</div>
      <input type="text" bind:value={chatFilterUser} placeholder="Filter user..." style="border: 2px solid var(--color-on-surface); padding: 4px 8px; font-family: var(--font-family-display); font-size: 11px; background: var(--color-surface); width: 140px;" />
    </div>
    <div>
      <div style="font-size: 8px; font-weight: 700; text-transform: uppercase; margin-bottom: 2px;">Project</div>
      <input type="text" bind:value={chatFilterProject} placeholder="Filter project..." style="border: 2px solid var(--color-on-surface); padding: 4px 8px; font-family: var(--font-family-display); font-size: 11px; background: var(--color-surface); width: 140px;" />
    </div>
    <button class="send-btn" style="font-size: 9px; padding: 4px 10px; align-self: flex-end; cursor: pointer;" onclick={() => { tabLoaded['chatLogs'] = false; loadChatLogs(); }}>SEARCH</button>
  </div>

  {#if loading && chatLogs.length === 0}
    <div style="font-size: 12px; color: var(--color-on-surface-dim);">Loading...</div>
  {:else if chatLogs.length === 0}
    <div style="font-size: 12px; color: var(--color-on-surface-dim);">No chat sessions found.</div>
  {:else}
    <table class="data-table" style="width: 100%;">
      <thead><tr>
        <th>SESSION</th>
        <th>USER</th>
        <th>PROJECT</th>
        <th>FIRST MESSAGE</th>
        <th>CREATED</th>
      </tr></thead>
      <tbody>
        {#each chatLogs as c}
          <tr style="cursor: pointer;" onclick={() => expandedChat = expandedChat === c.session_id ? null : c.session_id}>
            <td style="font-family: var(--font-family-display); font-size: 10px;">{c.session_id?.slice(0, 12) || '-'}...</td>
            <td style="font-size: 11px;">{c.user_id || c.username || 'anonymous'}</td>
            <td style="font-size: 11px;">{c.project || c.project_slug || c.slug || '-'}</td>
            <td style="font-size: 11px; max-width: 300px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">{c.first_message || c.message || '-'}</td>
            <td style="font-size: 10px; color: var(--color-on-surface-dim);">{fmtDate(c.created_at)}</td>
          </tr>

          <!-- Expanded chat detail -->
          {#if expandedChat === c.session_id}
            <tr>
              <td colspan="5" style="padding: 0; border: none;">
                <div class="ink-border" style="margin: 8px 0 12px 0; padding: 16px; background: var(--color-surface-bright);">
                  {#if c.messages?.length}
                    <div style="font-size: 9px; font-weight: 700; text-transform: uppercase; margin-bottom: 8px; border-bottom: 1px solid var(--color-on-surface); padding-bottom: 4px;">Messages ({c.messages.length})</div>
                    {#each c.messages.slice(0, 10) as msg}
                      <div style="font-size: 11px; margin-bottom: 6px; padding-left: 12px; border-left: 2px solid {msg.role === 'user' ? 'var(--color-primary)' : 'var(--color-on-surface-dim)'};">
                        <span style="font-weight: 700; text-transform: uppercase; font-size: 9px;">{msg.role || 'user'}</span>
                        <span style="color: var(--color-on-surface-dim); margin-left: 4px; font-size: 9px;">{fmtDate(msg.created_at)}</span>
                        <div style="margin-top: 2px;">{(msg.content || msg.message || '').slice(0, 200)}{(msg.content || msg.message || '').length > 200 ? '...' : ''}</div>
                      </div>
                    {/each}
                  {:else}
                    <div style="display: grid; grid-template-columns: 120px 1fr; gap: 4px 12px; font-size: 11px;">
                      <span style="font-weight: 700; text-transform: uppercase; font-size: 9px;">Session ID</span><span style="font-family: var(--font-family-display); font-size: 10px;">{c.session_id}</span>
                      <span style="font-weight: 700; text-transform: uppercase; font-size: 9px;">User</span><span>{c.user_id || c.username || 'anonymous'}</span>
                      <span style="font-weight: 700; text-transform: uppercase; font-size: 9px;">Project</span><span>{c.project || c.project_slug || '-'}</span>
                      <span style="font-weight: 700; text-transform: uppercase; font-size: 9px;">Created</span><span>{fmtDate(c.created_at)}</span>
                      {#if c.updated_at}<span style="font-weight: 700; text-transform: uppercase; font-size: 9px;">Last Active</span><span>{fmtDate(c.updated_at)}</span>{/if}
                      {#if c.message_count != null}<span style="font-weight: 700; text-transform: uppercase; font-size: 9px;">Messages</span><span>{c.message_count}</span>{/if}
                    </div>
                  {/if}
                </div>
              </td>
            </tr>
          {/if}
        {/each}
      </tbody>
    </table>
  {/if}

<!-- ═══════════════════════════════════════════════════════════ -->
<!-- HEALTH TAB                                                 -->
<!-- ═══════════════════════════════════════════════════════════ -->
{:else if activeTab === 'health'}
  <div class="cli-terminal" style="margin-bottom: 16px; padding: 8px 14px;">
    <div class="cli-line">
      <span class="cli-prompt">$</span>
      <span class="cli-command">dash admin --health</span>
      <span style="margin-left: auto; font-size: 11px; opacity: 0.6;">system check</span>
    </div>
  </div>

  <div class="flex items-center justify-between mb-4">
    <div style="font-size: 18px; font-weight: 900; text-transform: uppercase;">System Health</div>
    <button class="feedback-btn" style="font-size: 9px; font-weight: 700; text-transform: uppercase; padding: 4px 10px; cursor: pointer;" onclick={() => { tabLoaded['health'] = false; loading = true; loadHealth().then(() => { tabLoaded['health'] = true; loading = false; }); }}>REFRESH</button>
  </div>

  {#if loading && !health}
    <div style="font-size: 12px; color: var(--color-on-surface-dim);">Checking health...</div>
  {:else if health}
    <!-- Overall status -->
    <div class="ink-border" style="padding: 16px; margin-bottom: 16px; background: var(--color-surface-bright); text-align: center;">
      <div style="font-size: 10px; text-transform: uppercase; letter-spacing: 0.1em; color: var(--color-on-surface-dim); margin-bottom: 4px;">Overall Status</div>
      <div style="font-size: 24px; font-weight: 900; text-transform: uppercase; color: {(health.status === 'ok' || health.status === 'healthy') ? 'var(--color-primary)' : 'var(--color-error)'};">
        {health.status || 'UNKNOWN'}
      </div>
    </div>

    <!-- Service cards -->
    <div style="display: grid; grid-template-columns: repeat(auto-fill, minmax(200px, 1fr)); gap: 12px;">
      {#if health.services}
        {#each Object.entries(health.services) as [name, svc]}
          <div class="ink-border" style="padding: 14px; background: var(--color-surface-bright);">
            <div class="flex items-center gap-2 mb-2">
              <span style="font-size: 14px; color: {(svc as any).status === 'ok' || (svc as any).status === 'healthy' || (svc as any).status === 'connected' || (svc as any).up === true ? 'var(--color-primary)' : 'var(--color-error)'};">●</span>
              <span style="font-weight: 900; text-transform: uppercase; font-size: 11px;">{name}</span>
            </div>
            <div style="font-size: 11px; color: var(--color-on-surface-dim);">
              {#if typeof svc === 'object' && svc !== null}
                {(svc as any).status || ((svc as any).up ? 'UP' : 'DOWN')}
                {#if (svc as any).latency != null}<br/>Latency: {(svc as any).latency}ms{/if}
                {#if (svc as any).version}<br/>v{(svc as any).version}{/if}
              {:else}
                {svc}
              {/if}
            </div>
          </div>
        {/each}
      {:else}
        <!-- Fallback: render health object keys as cards -->
        {#each Object.entries(health).filter(([k]) => k !== 'status') as [key, val]}
          <div class="ink-border" style="padding: 14px; background: var(--color-surface-bright);">
            <div class="flex items-center gap-2 mb-2">
              <span style="font-size: 14px; color: var(--color-primary);">●</span>
              <span style="font-weight: 900; text-transform: uppercase; font-size: 11px;">{key}</span>
            </div>
            <div style="font-size: 11px; color: var(--color-on-surface-dim);">
              {#if typeof val === 'object' && val !== null}
                {JSON.stringify(val)}
              {:else}
                {val}
              {/if}
            </div>
          </div>
        {/each}
      {/if}
    </div>
  {:else}
    <div style="font-size: 12px; color: var(--color-on-surface-dim);">Health data unavailable.</div>
  {/if}

<!-- ═══════════════════════════════════════════════════════════ -->
<!-- STATS TAB                                                  -->
<!-- ═══════════════════════════════════════════════════════════ -->
{:else if activeTab === 'stats'}
  <div class="cli-terminal" style="margin-bottom: 16px; padding: 8px 14px;">
    <div class="cli-line">
      <span class="cli-prompt">$</span>
      <span class="cli-command">dash admin --stats</span>
      <span style="margin-left: auto; font-size: 11px; opacity: 0.6;">platform metrics</span>
    </div>
  </div>

  <div class="flex items-center justify-between mb-4">
    <div style="font-size: 18px; font-weight: 900; text-transform: uppercase;">Platform Stats</div>
    <button class="feedback-btn" style="font-size: 9px; font-weight: 700; text-transform: uppercase; padding: 4px 10px; cursor: pointer;" onclick={() => { tabLoaded['stats'] = false; loading = true; loadStats().then(() => { tabLoaded['stats'] = true; loading = false; }); }}>REFRESH</button>
  </div>

  {#if loading && !stats}
    <div style="font-size: 12px; color: var(--color-on-surface-dim);">Loading stats...</div>
  {:else if stats}
    <div style="display: grid; grid-template-columns: repeat(auto-fill, minmax(160px, 1fr)); gap: 12px;">
      {#each [
        { label: 'USERS', value: stats.users ?? stats.stats?.users ?? stats.user_count ?? '-' },
        { label: 'PROJECTS', value: stats.projects ?? stats.stats?.projects ?? stats.project_count ?? '-' },
        { label: 'SESSIONS', value: stats.sessions ?? stats.stats?.sessions ?? stats.session_count ?? '-' },
        { label: 'FEEDBACK', value: stats.feedback ?? stats.stats?.feedback ?? stats.feedback_count ?? '-' },
        { label: 'TRAINING RUNS', value: stats.training_runs ?? stats.stats?.training_runs ?? '-' },
        { label: 'DB SIZE', value: stats.db_size ?? stats.stats?.db_size ?? '-' },
        { label: 'TABLES', value: stats.tables ?? stats.stats?.table_count ?? stats.table_count ?? '-' },
        { label: 'TOTAL ROWS', value: typeof (stats.total_rows ?? stats.stats?.total_rows) === 'number' ? (stats.total_rows ?? stats.stats?.total_rows).toLocaleString() : (stats.total_rows ?? stats.stats?.total_rows ?? '-') },
        { label: 'KNOWLEDGE', value: stats.knowledge_vectors ?? stats.stats?.knowledge_vectors ?? '-' },
        { label: 'MEMORIES', value: stats.memories ?? stats.stats?.memories ?? stats.memory_count ?? '-' },
        { label: 'LEARNINGS', value: stats.learnings ?? stats.stats?.learnings ?? '-' },
        { label: 'PATTERNS', value: stats.patterns ?? stats.stats?.patterns ?? stats.query_patterns ?? '-' },
      ] as card}
        <div class="ink-border" style="padding: 16px; background: var(--color-surface-bright); text-align: center;">
          <div style="font-size: 9px; text-transform: uppercase; letter-spacing: 0.1em; color: var(--color-on-surface-dim); font-weight: 700;">{card.label}</div>
          <div style="font-size: 24px; font-weight: 900; margin-top: 4px;">{card.value}</div>
        </div>
      {/each}
    </div>

    <!-- Extra stats rendered as key-value if the API returns more -->
    {#if stats.extra || stats.details}
      <div style="margin-top: 20px;">
        <div style="font-size: 9px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.08em; margin-bottom: 8px; border-bottom: 1px solid var(--color-on-surface); padding-bottom: 4px;">Additional Metrics</div>
        <div style="display: grid; grid-template-columns: 200px 1fr; gap: 4px 16px; font-size: 12px;">
          {#each Object.entries(stats.extra || stats.details || {}) as [k, v]}
            <span style="font-weight: 700; text-transform: uppercase; font-size: 10px;">{k.replace(/_/g, ' ')}</span>
            <span>{v}</span>
          {/each}
        </div>
      </div>
    {/if}
  {:else}
    <div style="font-size: 12px; color: var(--color-on-surface-dim);">Stats unavailable.</div>
  {/if}

{:else if activeTab === 'integrations'}
  <div class="cli-terminal" style="margin-bottom: 16px; padding: 8px 14px;">
    <div class="cli-line">
      <span class="cli-prompt">$</span>
      <span class="cli-command">dash admin --integrations</span>
      <span style="margin-left: auto; font-size: 11px; opacity: 0.6;">external connectors</span>
    </div>
  </div>

  <!-- SharePoint Configuration -->
  <div style="font-size: 18px; font-weight: 900; text-transform: uppercase; margin-bottom: 16px;">SharePoint Connector</div>

  <div class="ink-border" style="padding: 16px; background: var(--color-surface-bright); margin-bottom: 16px;">
    <div style="font-size: 11px; font-weight: 900; text-transform: uppercase; margin-bottom: 12px;">AZURE APP REGISTRATION</div>
    <div style="font-size: 10px; color: var(--color-on-surface-dim); margin-bottom: 16px; line-height: 1.6;">
      1. Go to <strong>Azure Portal</strong> &rarr; App Registrations &rarr; New Registration<br>
      2. Name: <code style="background: #222; color: #0f0; padding: 1px 4px; font-size: 9px;">Dash SharePoint Connector</code><br>
      3. Redirect URI: <code style="background: #222; color: #0f0; padding: 1px 4px; font-size: 9px;">https://your-domain/api/sharepoint/callback</code><br>
      4. API Permissions &rarr; Add: <strong>Sites.Read.All</strong>, <strong>Files.Read.All</strong>, <strong>User.Read</strong>, <strong>offline_access</strong><br>
      5. Certificates &amp; Secrets &rarr; New Client Secret &rarr; Copy value below
    </div>

    <div style="display: flex; flex-direction: column; gap: 10px; max-width: 500px;">
      <div>
        <div style="font-size: 9px; font-weight: 700; text-transform: uppercase; margin-bottom: 3px;">CLIENT ID (Application ID)</div>
        <input type="text" bind:value={spAdminClientId} placeholder="xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx" style="width: 100%; border: 2px solid var(--color-on-surface); padding: 6px 10px; font-family: var(--font-family-display); font-size: 11px; background: var(--color-surface);" />
      </div>
      <div>
        <div style="font-size: 9px; font-weight: 700; text-transform: uppercase; margin-bottom: 3px;">CLIENT SECRET</div>
        <input type="password" bind:value={spAdminClientSecret} placeholder="{spAdminConfig.has_secret ? '••••••••  (already set, leave blank to keep)' : 'paste secret value here'}" style="width: 100%; border: 2px solid var(--color-on-surface); padding: 6px 10px; font-family: var(--font-family-display); font-size: 11px; background: var(--color-surface);" />
      </div>
      <div>
        <div style="font-size: 9px; font-weight: 700; text-transform: uppercase; margin-bottom: 3px;">TENANT ID (Directory ID)</div>
        <input type="text" bind:value={spAdminTenantId} placeholder="xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx" style="width: 100%; border: 2px solid var(--color-on-surface); padding: 6px 10px; font-family: var(--font-family-display); font-size: 11px; background: var(--color-surface);" />
      </div>

      <div style="display: flex; align-items: center; gap: 12px; margin-top: 4px;">
        <button class="send-btn" style="padding: 8px 20px; font-size: 11px;" disabled={spAdminSaving || !spAdminClientId || !spAdminTenantId} onclick={saveSharePointConfig}>
          {spAdminSaving ? 'SAVING...' : 'SAVE CONFIGURATION'}
        </button>
        {#if spAdminConfig.configured}
          <span style="font-size: 10px; color: #00fc40; font-weight: 700;">&#10003; CONFIGURED</span>
        {:else}
          <span style="font-size: 10px; color: var(--color-on-surface-dim);">NOT CONFIGURED</span>
        {/if}
      </div>
      {#if spAdminMsg}
        <div style="font-size: 10px; color: {spAdminMsg.includes('Saved') ? '#00fc40' : '#e74c3c'}; font-weight: 700;">{spAdminMsg}</div>
      {/if}
    </div>
  </div>

  <!-- Connected Sources across all projects -->
  {#if spAllSources.length > 0}
    <div style="font-size: 11px; font-weight: 900; text-transform: uppercase; letter-spacing: 0.08em; margin-bottom: 8px;">ALL CONNECTED SOURCES ({spAllSources.length})</div>
    <div style="overflow-x: auto;">
      <table style="width: 100%; font-size: 11px; border-collapse: collapse;">
        <thead>
          <tr style="border-bottom: 2px solid var(--color-on-surface); text-align: left;">
            <th style="padding: 6px 8px; font-size: 9px; font-weight: 700; text-transform: uppercase;">PROJECT</th>
            <th style="padding: 6px 8px; font-size: 9px; font-weight: 700; text-transform: uppercase;">SITE</th>
            <th style="padding: 6px 8px; font-size: 9px; font-weight: 700; text-transform: uppercase;">FOLDER</th>
            <th style="padding: 6px 8px; font-size: 9px; font-weight: 700; text-transform: uppercase;">FILES</th>
            <th style="padding: 6px 8px; font-size: 9px; font-weight: 700; text-transform: uppercase;">LAST SYNC</th>
            <th style="padding: 6px 8px; font-size: 9px; font-weight: 700; text-transform: uppercase;">STATUS</th>
          </tr>
        </thead>
        <tbody>
          {#each spAllSources as src}
            <tr style="border-bottom: 1px solid var(--color-surface-dim);">
              <td style="padding: 6px 8px; font-weight: 700;">{src.project_slug}</td>
              <td style="padding: 6px 8px;">{src.site_name || '-'}</td>
              <td style="padding: 6px 8px; font-size: 10px; color: var(--color-on-surface-dim);">{src.folder_path || '/'}</td>
              <td style="padding: 6px 8px;">{src.files_synced}</td>
              <td style="padding: 6px 8px; font-size: 10px;">{src.last_sync_at ? fmtDate(src.last_sync_at) : '-'}</td>
              <td style="padding: 6px 8px;">
                <span style="font-size: 9px; font-weight: 700; padding: 1px 6px; background: {src.status === 'active' ? '#00fc40' : '#888'}; color: #1a1a1a;">{src.status?.toUpperCase()}</span>
              </td>
            </tr>
          {/each}
        </tbody>
      </table>
    </div>
  {:else}
    <div style="font-size: 11px; color: var(--color-on-surface-dim);">No SharePoint sources connected yet. Users can connect from their project Settings &rarr; SOURCES tab.</div>
  {/if}

  <!-- Google Drive Configuration -->
  <div style="font-size: 18px; font-weight: 900; text-transform: uppercase; margin-top: 30px; margin-bottom: 16px;">Google Drive Connector</div>

  <div class="ink-border" style="padding: 16px; background: var(--color-surface-bright); margin-bottom: 16px;">
    <div style="font-size: 11px; font-weight: 900; text-transform: uppercase; margin-bottom: 12px;">GOOGLE OAUTH SETUP</div>
    <div style="font-size: 10px; color: var(--color-on-surface-dim); margin-bottom: 16px; line-height: 1.6;">
      1. Go to <strong>Google Cloud Console</strong> &rarr; APIs &amp; Services &rarr; Credentials &rarr; Create OAuth Client ID
    </div>

    <div style="display: flex; flex-direction: column; gap: 10px; max-width: 500px;">
      <div>
        <div style="font-size: 9px; font-weight: 700; text-transform: uppercase; margin-bottom: 3px;">GOOGLE_CLIENT_ID</div>
        <input type="text" bind:value={gdAdminClientId} placeholder="xxxxxxxxxxxx-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx.apps.googleusercontent.com" style="width: 100%; border: 2px solid var(--color-on-surface); padding: 6px 10px; font-family: var(--font-family-display); font-size: 11px; background: var(--color-surface);" />
      </div>
      <div>
        <div style="font-size: 9px; font-weight: 700; text-transform: uppercase; margin-bottom: 3px;">GOOGLE_CLIENT_SECRET</div>
        <input type="password" bind:value={gdAdminClientSecret} placeholder="{gdAdminConfig.has_secret ? '••••••••  (already set, leave blank to keep)' : 'paste client secret here'}" style="width: 100%; border: 2px solid var(--color-on-surface); padding: 6px 10px; font-family: var(--font-family-display); font-size: 11px; background: var(--color-surface);" />
      </div>

      <div style="display: flex; align-items: center; gap: 12px; margin-top: 4px;">
        <button class="send-btn" style="padding: 8px 20px; font-size: 11px;" disabled={gdAdminSaving || !gdAdminClientId} onclick={saveGDriveConfig}>
          {gdAdminSaving ? 'SAVING...' : 'SAVE CONFIGURATION'}
        </button>
        {#if gdAdminConfig.configured}
          <span style="font-size: 10px; color: #00fc40; font-weight: 700;">&#10003; CONFIGURED</span>
        {:else}
          <span style="font-size: 10px; color: var(--color-on-surface-dim);">NOT CONFIGURED</span>
        {/if}
      </div>
      {#if gdAdminMsg}
        <div style="font-size: 10px; color: {gdAdminMsg.includes('Saved') ? '#00fc40' : '#e74c3c'}; font-weight: 700;">{gdAdminMsg}</div>
      {/if}
    </div>
  </div>

  <!-- Database Connectors -->
  <div style="font-size: 18px; font-weight: 900; text-transform: uppercase; margin-top: 30px; margin-bottom: 16px;">Database Connectors</div>

  {#if dbAdminStep === 'idle'}
    <!-- DB type picker -->
    <div style="display: flex; gap: 10px; margin-bottom: 16px; flex-wrap: wrap;">
      {#each [['postgresql', 'PG', '#336791', '5432'], ['mysql', 'MY', '#00758f', '3306'], ['fabric', 'FB', '#0078d4', '1433']] as [type, icon, color, port]}
        <button class="ink-border" style="padding: 14px 20px; background: var(--color-surface-bright); cursor: pointer; text-align: center; border-width: 2px; min-width: 140px;"
          onclick={() => { dbAdminType = type; dbAdminPort = port; dbAdminStep = 'form'; }}>
          <div style="width: 32px; height: 32px; background: {color}; display: flex; align-items: center; justify-content: center; font-weight: 900; color: white; font-size: 10px; margin: 0 auto 6px;">{icon}</div>
          <div style="font-size: 11px; font-weight: 900;">{type === 'fabric' ? 'Microsoft Fabric' : type === 'postgresql' ? 'PostgreSQL' : 'MySQL'}</div>
        </button>
      {/each}
    </div>

  {:else if dbAdminStep === 'form'}
    <!-- Connection form -->
    <div class="ink-border" style="padding: 16px; background: var(--color-surface-bright); max-width: 500px; margin-bottom: 16px;">
      <div style="font-size: 11px; font-weight: 900; text-transform: uppercase; margin-bottom: 10px;">CONNECT {dbAdminType.toUpperCase()}</div>
      <div style="display: flex; flex-direction: column; gap: 8px;">
        <div>
          <div style="font-size: 9px; font-weight: 700; text-transform: uppercase; margin-bottom: 2px;">HOST</div>
          <input type="text" bind:value={dbAdminHost} placeholder={dbAdminType === 'fabric' ? 'workspace.datawarehouse.fabric.microsoft.com' : 'db.company.com'} style="width: 100%; border: 2px solid var(--color-on-surface); padding: 6px 10px; font-family: var(--font-family-display); font-size: 11px; background: var(--color-surface);" />
        </div>
        <div style="display: flex; gap: 8px;">
          <div style="flex: 1;">
            <div style="font-size: 9px; font-weight: 700; text-transform: uppercase; margin-bottom: 2px;">PORT</div>
            <input type="text" bind:value={dbAdminPort} style="width: 100%; border: 2px solid var(--color-on-surface); padding: 6px 10px; font-family: var(--font-family-display); font-size: 11px; background: var(--color-surface);" />
          </div>
          <div style="flex: 2;">
            <div style="font-size: 9px; font-weight: 700; text-transform: uppercase; margin-bottom: 2px;">DATABASE</div>
            <input type="text" bind:value={dbAdminName} placeholder="analytics" style="width: 100%; border: 2px solid var(--color-on-surface); padding: 6px 10px; font-family: var(--font-family-display); font-size: 11px; background: var(--color-surface);" />
          </div>
        </div>
        <div style="display: flex; gap: 8px;">
          <div style="flex: 1;">
            <div style="font-size: 9px; font-weight: 700; text-transform: uppercase; margin-bottom: 2px;">USERNAME</div>
            <input type="text" bind:value={dbAdminUser} style="width: 100%; border: 2px solid var(--color-on-surface); padding: 6px 10px; font-family: var(--font-family-display); font-size: 11px; background: var(--color-surface);" />
          </div>
          <div style="flex: 1;">
            <div style="font-size: 9px; font-weight: 700; text-transform: uppercase; margin-bottom: 2px;">PASSWORD</div>
            <input type="password" bind:value={dbAdminPass} style="width: 100%; border: 2px solid var(--color-on-surface); padding: 6px 10px; font-family: var(--font-family-display); font-size: 11px; background: var(--color-surface);" />
          </div>
        </div>
        <div style="display: flex; gap: 8px; margin-top: 4px;">
          <button class="feedback-btn" style="font-size: 9px; padding: 4px 10px;" onclick={() => dbAdminStep = 'idle'}>CANCEL</button>
          <button class="send-btn" style="font-size: 10px; padding: 6px 16px;" disabled={dbAdminTesting || !dbAdminHost || !dbAdminName || !dbAdminUser} onclick={dbAdminTest}>
            {dbAdminTesting ? 'TESTING...' : 'TEST CONNECTION'}
          </button>
        </div>
        {#if dbAdminTestResult}
          <div style="font-size: 10px; color: {dbAdminTestResult.error ? '#e74c3c' : '#00fc40'}; font-weight: 700;">
            {dbAdminTestResult.error || `Connected! ${dbAdminTestResult.tables?.length || 0} tables found`}
          </div>
        {/if}
      </div>
    </div>

  {:else if dbAdminStep === 'tables'}
    <!-- Table selection + project picker -->
    <div class="ink-border" style="padding: 16px; background: var(--color-surface-bright); max-width: 500px; margin-bottom: 16px;">
      <div style="font-size: 11px; font-weight: 900; text-transform: uppercase; margin-bottom: 10px;">SELECT TABLES & PROJECT</div>

      <!-- Project selector -->
      <div style="margin-bottom: 12px;">
        <div style="font-size: 9px; font-weight: 700; text-transform: uppercase; margin-bottom: 2px;">ASSIGN TO PROJECT</div>
        <select bind:value={dbAdminProject} style="width: 100%; border: 2px solid var(--color-on-surface); padding: 6px 10px; font-family: var(--font-family-display); font-size: 11px; background: var(--color-surface);">
          <option value="">-- select project --</option>
          {#each projects as p}
            <option value={p.slug || p.project_slug}>{p.name || p.agent_name || p.slug || p.project_slug}</option>
          {/each}
        </select>
      </div>

      <!-- Table checkboxes -->
      <div style="margin-bottom: 8px;">
        <label style="font-size: 10px; cursor: pointer;">
          <input type="checkbox" checked={dbAdminSelectedTables.length === dbAdminTables.length}
            onchange={() => { dbAdminSelectedTables = dbAdminSelectedTables.length === dbAdminTables.length ? [] : [...dbAdminTables]; }} />
          Select All ({dbAdminTables.length})
        </label>
      </div>
      <div style="max-height: 250px; overflow-y: auto; border: 1px solid var(--color-surface-dim); padding: 6px;">
        {#each dbAdminTables as tbl}
          <label style="display: flex; align-items: center; gap: 6px; padding: 2px 0; font-size: 11px; cursor: pointer;">
            <input type="checkbox" checked={dbAdminSelectedTables.includes(tbl)}
              onchange={() => {
                if (dbAdminSelectedTables.includes(tbl)) dbAdminSelectedTables = dbAdminSelectedTables.filter(t => t !== tbl);
                else dbAdminSelectedTables = [...dbAdminSelectedTables, tbl];
              }} />
            {tbl}
          </label>
        {/each}
      </div>
      <div style="display: flex; gap: 8px; margin-top: 10px;">
        <button class="feedback-btn" style="font-size: 9px; padding: 4px 10px;" onclick={() => dbAdminStep = 'form'}>BACK</button>
        <button class="send-btn" style="font-size: 10px; padding: 6px 16px;" disabled={dbAdminConnecting || dbAdminSelectedTables.length === 0 || !dbAdminProject} onclick={dbAdminConnect}>
          {dbAdminConnecting ? 'CONNECTING...' : `CONNECT ${dbAdminSelectedTables.length} TABLES`}
        </button>
      </div>
      {#if dbAdminMsg2}
        <div style="font-size: 10px; color: {dbAdminMsg2.includes('!') ? '#00fc40' : '#e74c3c'}; font-weight: 700; margin-top: 6px;">{dbAdminMsg2}</div>
      {/if}
    </div>
  {/if}

  <!-- All connected DB sources -->
  {#if dbAllSources.length > 0}
    <div style="font-size: 11px; font-weight: 900; text-transform: uppercase; letter-spacing: 0.08em; margin-bottom: 8px; margin-top: 16px;">ALL DATABASE SOURCES ({dbAllSources.length})</div>
    <div style="overflow-x: auto;">
      <table style="width: 100%; font-size: 11px; border-collapse: collapse;">
        <thead>
          <tr style="border-bottom: 2px solid var(--color-on-surface); text-align: left;">
            <th style="padding: 6px 8px; font-size: 9px; font-weight: 700; text-transform: uppercase;">PROJECT</th>
            <th style="padding: 6px 8px; font-size: 9px; font-weight: 700; text-transform: uppercase;">TYPE</th>
            <th style="padding: 6px 8px; font-size: 9px; font-weight: 700; text-transform: uppercase;">HOST</th>
            <th style="padding: 6px 8px; font-size: 9px; font-weight: 700; text-transform: uppercase;">DATABASE</th>
            <th style="padding: 6px 8px; font-size: 9px; font-weight: 700; text-transform: uppercase;">TABLES</th>
            <th style="padding: 6px 8px; font-size: 9px; font-weight: 700; text-transform: uppercase;">LAST SYNC</th>
            <th style="padding: 6px 8px; font-size: 9px; font-weight: 700; text-transform: uppercase;">STATUS</th>
          </tr>
        </thead>
        <tbody>
          {#each dbAllSources as src}
            <tr style="border-bottom: 1px solid var(--color-surface-dim);">
              <td style="padding: 6px 8px; font-weight: 700;">{src.project_slug || src.project || '-'}</td>
              <td style="padding: 6px 8px;">
                <span style="font-size: 9px; font-weight: 700; padding: 1px 6px; background: var(--color-surface-dim); color: var(--color-on-surface);">{(src.type || src.db_type || '-').toUpperCase()}</span>
              </td>
              <td style="padding: 6px 8px; font-size: 10px; color: var(--color-on-surface-dim); font-family: var(--font-family-display);">{src.host || '-'}</td>
              <td style="padding: 6px 8px;">{src.database || src.db_name || '-'}</td>
              <td style="padding: 6px 8px; font-weight: 900;">{src.tables ?? src.table_count ?? '-'}</td>
              <td style="padding: 6px 8px; font-size: 10px;">{src.last_sync_at || src.last_sync ? fmtDate(src.last_sync_at || src.last_sync) : '-'}</td>
              <td style="padding: 6px 8px;">
                <span style="font-size: 9px; font-weight: 700; padding: 1px 6px; background: {src.status === 'active' || src.status === 'connected' ? '#00fc40' : '#888'}; color: #1a1a1a;">{(src.status || 'unknown').toUpperCase()}</span>
              </td>
            </tr>
          {/each}
        </tbody>
      </table>
    </div>
  {/if}

  <!-- Future: Other integrations -->
  <div style="margin-top: 30px; border-top: 1px solid var(--color-surface-dim); padding-top: 16px;">
    <div style="font-size: 11px; font-weight: 900; text-transform: uppercase; margin-bottom: 8px;">COMING SOON</div>
    <div style="display: flex; gap: 12px; flex-wrap: wrap;">
      <div class="ink-border" style="padding: 12px 16px; background: var(--color-surface-bright); opacity: 0.5; min-width: 150px; text-align: center;">
        <div style="font-size: 12px; font-weight: 900;">Snowflake</div>
        <div style="font-size: 9px; color: var(--color-on-surface-dim);">Cloud data warehouse</div>
      </div>
      <div class="ink-border" style="padding: 12px 16px; background: var(--color-surface-bright); opacity: 0.5; min-width: 150px; text-align: center;">
        <div style="font-size: 12px; font-weight: 900;">BigQuery</div>
        <div style="font-size: 9px; color: var(--color-on-surface-dim);">Google analytics warehouse</div>
      </div>
      <div class="ink-border" style="padding: 12px 16px; background: var(--color-surface-bright); opacity: 0.5; min-width: 150px; text-align: center;">
        <div style="font-size: 12px; font-weight: 900;">OneDrive</div>
        <div style="font-size: 9px; color: var(--color-on-surface-dim);">File sync</div>
      </div>
    </div>
  </div>

{:else if activeTab === 'architecture'}
  <div class="cli-terminal" style="margin-bottom: 16px; padding: 8px 14px;">
    <div class="cli-line">
      <span class="cli-prompt">$</span>
      <span class="cli-command">dash system --architecture</span>
      <span style="margin-left: auto; font-size: 11px; opacity: 0.6;">full system blueprint</span>
    </div>
  </div>

  {#if arch}
  <!-- INTERACTIVE FLOW DIAGRAM -->
  <div class="ink-border" style="padding: 0; background: #0a0a0a; margin-bottom: 16px; position: relative;">
    <div style="padding: 6px 12px; background: var(--color-on-surface); color: var(--color-surface); font-size: 9px; font-weight: 900; text-transform: uppercase; letter-spacing: 0.08em;">
      SYSTEM FLOW — drag to pan, scroll to zoom, hover for details
    </div>
    <div bind:this={archFlowEl} style="width: 100%; height: 500px;"></div>
  </div>

  <!-- SYSTEM OVERVIEW -->
  <div class="ink-border" style="padding: 16px; background: #111; color: #0f0; font-family: var(--font-family-display); font-size: 11px; margin-bottom: 16px; line-height: 1.8; white-space: pre;">
<span style="color: #fbbf24; font-weight: 900;">DASH — SELF-LEARNING DATA NOTEBOOK</span>
<span style="float: right; color: #00fc40;">LIVE ● UPTIME: {arch.ml_retrain?.last_run ? 'Active' : 'Starting'}</span>

Multi-tenant │ {arch.agents?.total} Agents │ {arch.ml?.tools?.length} ML Models │ {arch.knowledge?.layers} Context Layers

<span style="color: #888;">┌─── NETWORK LAYER ───────────────────────────────────────────────────┐</span>
<span style="color: #888;">│</span> User → <span style="color: #60a5fa;">{arch.infra?.proxy}</span> → <span style="color: #60a5fa;">FastAPI ({arch.infra?.workers}w)</span> → <span style="color: #60a5fa;">{arch.infra?.pooler?.split('(')[0]}</span>
<span style="color: #888;">│</span>      → <span style="color: #60a5fa;">{arch.infra?.db}</span>
<span style="color: #888;">│</span> Rate: <span style="color: #fbbf24;">{arch.infra?.rate_limit}</span> │ Auth: <span style="color: #fbbf24;">SCRAM-SHA-256 + Token</span>
<span style="color: #888;">└─────────────────────────────────────────────────────────────────────┘</span>
  </div>

  <!-- ROUTING + AGENTS -->
  <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 12px; margin-bottom: 16px;">
    <div class="ink-border" style="padding: 14px; background: var(--color-surface-bright);">
      <div style="font-size: 10px; font-weight: 900; text-transform: uppercase; margin-bottom: 10px; letter-spacing: 0.08em;">ROUTING</div>
      <div style="font-size: 10px; line-height: 1.8; color: var(--color-on-surface-dim);">
        <div><span style="color: #00fc40; font-weight: 700;">Tier 1:</span> Keyword scoring (7 signals, $0, &lt;1ms)</div>
        <div><span style="color: #fbbf24; font-weight: 700;">Tier 2:</span> Router Agent + Brain lookup ($0.001, &lt;1.5s)</div>
        <div style="margin-top: 6px; font-size: 9px; border-top: 1px solid var(--color-on-surface); padding-top: 6px;">
          "revenue by month" → <span style="color: #60a5fa;">Analyst</span><br>
          "predict sales" → <span style="color: #a78bfa;">Data Scientist</span><br>
          "what does report say" → <span style="color: #34d399;">Researcher</span><br>
          "create view" → <span style="color: #fbbf24;">Engineer</span>
        </div>
      </div>
    </div>

    <div class="ink-border" style="padding: 14px; background: var(--color-surface-bright);">
      <div style="font-size: 10px; font-weight: 900; text-transform: uppercase; margin-bottom: 10px; letter-spacing: 0.08em;">AGENT TEAMS ({arch.agents?.total} total)</div>
      <div style="font-size: 9px; line-height: 1.7; color: var(--color-on-surface-dim);">
        <div style="font-weight: 700; color: var(--color-on-surface); margin-bottom: 2px;">CHAT ({arch.agents?.chat_team?.length})</div>
        {#each arch.agents?.chat_team || [] as a}<div style="padding-left: 8px;">› {a}</div>{/each}
        <div style="font-weight: 700; color: var(--color-on-surface); margin-top: 6px; margin-bottom: 2px;">SPECIALISTS ({arch.agents?.specialists?.length})</div>
        <div style="padding-left: 8px;">{(arch.agents?.specialists || []).join(', ')}</div>
        <div style="font-weight: 700; color: var(--color-on-surface); margin-top: 6px; margin-bottom: 2px;">BACKGROUND ({arch.agents?.background?.length})</div>
        <div style="padding-left: 8px;">{(arch.agents?.background || []).join(', ')}</div>
        <div style="font-weight: 700; color: var(--color-on-surface); margin-top: 6px; margin-bottom: 2px;">UPLOAD ({arch.agents?.upload?.length})</div>
        <div style="padding-left: 8px;">{(arch.agents?.upload || []).join(', ')}</div>
      </div>
    </div>
  </div>

  <!-- ML INTELLIGENCE -->
  <div class="ink-border" style="padding: 14px; background: var(--color-surface-bright); margin-bottom: 16px;">
    <div style="font-size: 10px; font-weight: 900; text-transform: uppercase; margin-bottom: 12px; letter-spacing: 0.08em;">ML INTELLIGENCE ({arch.ml?.tools?.length} tools)</div>
    <div style="display: grid; grid-template-columns: repeat(3, 1fr); gap: 8px; margin-bottom: 12px;">
      {#each arch.ml?.tools || [] as tool}
        <div style="border: 1px solid var(--color-on-surface); padding: 8px; font-size: 9px;">
          <div style="font-weight: 900; text-transform: uppercase; color: {tool.type?.includes('LLM') ? '#a78bfa' : '#00fc40'}; margin-bottom: 4px;">{tool.name}</div>
          <div style="color: var(--color-on-surface-dim);">{tool.algorithm}</div>
          <div style="margin-top: 4px;">
            <span style="font-size: 8px; padding: 1px 4px; background: {tool.type?.includes('LLM') ? '#6b21a8' : '#007518'}; color: white; font-weight: 700;">{tool.type}</span>
            <span style="margin-left: 6px; color: var(--color-on-surface-dim);">{tool.cost}</span>
          </div>
        </div>
      {/each}
    </div>
    <div style="display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 12px; font-size: 9px; color: var(--color-on-surface-dim);">
      <div>
        <div style="font-weight: 700; color: var(--color-on-surface); margin-bottom: 4px;">PREPROCESSING</div>
        {#each arch.ml?.preprocessing || [] as p}<div>› {p}</div>{/each}
      </div>
      <div>
        <div style="font-weight: 700; color: var(--color-on-surface); margin-bottom: 4px;">EVALUATION</div>
        {#each arch.ml?.evaluation || [] as e}<div>› {e}</div>{/each}
      </div>
      <div>
        <div style="font-weight: 700; color: var(--color-on-surface); margin-bottom: 4px;">ML WORKER</div>
        <div>Row limit: {arch.ml?.worker?.row_limit?.toLocaleString()}</div>
        <div>Timeout: {arch.ml?.worker?.timeout_sec}s</div>
        <div>Retrain: {arch.ml?.worker?.retrain_interval}</div>
      </div>
    </div>
  </div>

  <!-- KNOWLEDGE + AI MODELS -->
  <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 12px; margin-bottom: 16px;">
    <div class="ink-border" style="padding: 14px; background: var(--color-surface-bright);">
      <div style="font-size: 10px; font-weight: 900; text-transform: uppercase; margin-bottom: 10px; letter-spacing: 0.08em;">KNOWLEDGE ({arch.knowledge?.layers} layers)</div>
      <div style="font-size: 9px; line-height: 1.7; color: var(--color-on-surface-dim);">
        <div>Search: {arch.knowledge?.search}</div>
        <div style="margin-top: 6px; font-weight: 700; color: var(--color-on-surface);">EMBEDDING CASCADE</div>
        {#each arch.knowledge?.embedding_cascade || [] as e, i}<div>{i+1}. {e}</div>{/each}
        <div style="margin-top: 6px; font-weight: 700; color: var(--color-on-surface);">RERANK CASCADE</div>
        {#each arch.knowledge?.rerank_cascade || [] as r, i}<div>{i+1}. {r}</div>{/each}
      </div>
    </div>

    <div class="ink-border" style="padding: 14px; background: var(--color-surface-bright);">
      <div style="font-size: 10px; font-weight: 900; text-transform: uppercase; margin-bottom: 10px; letter-spacing: 0.08em;">AI MODELS (from env)</div>
      <div style="font-size: 9px; line-height: 1.8; color: var(--color-on-surface-dim);">
        <div><span style="color: #00fc40; font-weight: 700;">CHAT:</span> <code style="background: #222; color: #0f0; padding: 1px 4px; font-size: 8px;">{arch.models?.chat}</code></div>
        <div><span style="color: #fbbf24; font-weight: 700;">DEEP:</span> <code style="background: #222; color: #0f0; padding: 1px 4px; font-size: 8px;">{arch.models?.deep}</code></div>
        <div><span style="color: #60a5fa; font-weight: 700;">LITE:</span> <code style="background: #222; color: #0f0; padding: 1px 4px; font-size: 8px;">{arch.models?.lite}</code></div>
        <div><span style="color: #a78bfa; font-weight: 700;">EMBED:</span> <code style="background: #222; color: #0f0; padding: 1px 4px; font-size: 8px;">{arch.models?.embedding}</code></div>
        <div style="margin-top: 8px; color: var(--color-on-surface);">Provider: <span style="font-weight: 700;">{arch.models?.provider}</span> — single API key</div>
      </div>
    </div>
  </div>

  <!-- DATA PIPELINE + SECURITY -->
  <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 12px; margin-bottom: 16px;">
    <div class="ink-border" style="padding: 14px; background: var(--color-surface-bright);">
      <div style="font-size: 10px; font-weight: 900; text-transform: uppercase; margin-bottom: 10px; letter-spacing: 0.08em;">DATA PIPELINE</div>
      <div style="font-size: 9px; line-height: 1.7; color: var(--color-on-surface-dim);">
        <div style="font-weight: 700; color: var(--color-on-surface);">INGESTION ({arch.pipeline?.formats} formats)</div>
        <div>{(arch.pipeline?.format_list || []).join(', ')}</div>
        <div style="margin-top: 6px; font-weight: 700; color: var(--color-on-surface);">TRAINING ({arch.pipeline?.training_steps} steps)</div>
        <div>Drift → Analysis → Q&A → Persona → Workflows → Relationships → KB Index → Brain → Domain → Seed → Enrich → Facts → KG → ML</div>
        <div style="margin-top: 6px; font-weight: 700; color: var(--color-on-surface);">CONNECTORS</div>
        <div>{(arch.pipeline?.connectors || []).join(' │ ')}</div>
        <div style="margin-top: 6px; font-weight: 700; color: var(--color-on-surface);">EXPORT</div>
        <div>{(arch.pipeline?.export || []).join(' │ ')}</div>
      </div>
    </div>

    <div class="ink-border" style="padding: 14px; background: var(--color-surface-bright);">
      <div style="font-size: 10px; font-weight: 900; text-transform: uppercase; margin-bottom: 10px; letter-spacing: 0.08em;">SECURITY</div>
      <div style="font-size: 9px; line-height: 1.6; color: var(--color-on-surface-dim);">
        {#each Object.entries(arch.security || {}) as [category, items]}
          <div style="font-weight: 700; color: var(--color-on-surface); text-transform: uppercase; margin-top: 6px; margin-bottom: 2px;">{category}</div>
          {#each items as item}<div style="padding-left: 8px;">› {item}</div>{/each}
        {/each}
      </div>
    </div>
  </div>

  <!-- SELF-LEARNING -->
  <div class="ink-border" style="padding: 14px; background: var(--color-surface-bright); margin-bottom: 16px;">
    <div style="font-size: 10px; font-weight: 900; text-transform: uppercase; margin-bottom: 10px; letter-spacing: 0.08em;">SELF-LEARNING LOOP</div>
    <div style="display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 16px; font-size: 9px; color: var(--color-on-surface-dim);">
      <div>
        <div style="font-weight: 700; color: #00fc40; margin-bottom: 4px;">EVERY CHAT</div>
        <div>11 background agents run:</div>
        <div>Quality score │ Extract rules │ KG triples</div>
        <div>Auto-memory │ User prefs │ Episodic</div>
        <div>Query plans │ Follow-ups │ Insights</div>
      </div>
      <div>
        <div style="font-weight: 700; color: #fbbf24; margin-bottom: 4px;">PERIODIC</div>
        <div>Every 20 chats: Auto-evolve instructions</div>
        <div>Every 24 hours: Retrain all ML models</div>
        <div>On upload: Full 14-step training</div>
        <div>Last retrain: {arch.ml_retrain?.last_run || 'Never'}</div>
      </div>
      <div>
        <div style="font-weight: 700; color: #60a5fa; margin-bottom: 4px;">FEEDBACK LOOP</div>
        <div>&#128077; → Proven pattern + auto-VIEW (3+ uses)</div>
        <div>&#128078; → Anti-pattern (agent avoids next time)</div>
        <div>Self-correction: 3 attempts with diagnosis</div>
        <div>Meta-learning tracks strategy success rates</div>
      </div>
    </div>
  </div>

  <!-- INFRASTRUCTURE -->
  <div class="ink-border" style="padding: 14px; background: var(--color-surface-bright); margin-bottom: 16px;">
    <div style="font-size: 10px; font-weight: 900; text-transform: uppercase; margin-bottom: 10px; letter-spacing: 0.08em;">INFRASTRUCTURE</div>
    <div style="display: flex; gap: 8px; flex-wrap: wrap; margin-bottom: 12px;">
      {#each arch.infra?.containers || [] as c}
        <div style="border: 1px solid var(--color-on-surface); padding: 6px 12px; font-size: 9px; font-weight: 700;">{c}</div>
      {/each}
    </div>
  </div>

  <!-- LIVE METRICS -->
  <div class="ink-border" style="padding: 14px; background: var(--color-surface-bright);">
    <div style="font-size: 10px; font-weight: 900; text-transform: uppercase; margin-bottom: 12px; letter-spacing: 0.08em;">LIVE METRICS</div>
    <div style="display: grid; grid-template-columns: repeat(5, 1fr); gap: 8px;">
      {#each [
        { v: arch.metrics?.projects, l: 'Projects' },
        { v: arch.metrics?.users, l: 'Users' },
        { v: arch.metrics?.chats, l: 'Chats' },
        { v: arch.metrics?.ml_models, l: 'ML Models' },
        { v: arch.metrics?.experiments, l: 'Experiments' },
        { v: arch.metrics?.brain_entries, l: 'Brain Entries' },
        { v: arch.metrics?.memories, l: 'Memories' },
        { v: arch.metrics?.feedback, l: 'Feedback' },
        { v: arch.metrics?.kg_triples, l: 'KG Triples' },
        { v: arch.metrics?.quality_avg ? arch.metrics.quality_avg + '★' : '—', l: 'Avg Quality' },
      ] as m}
        <div style="text-align: center; border: 1px solid var(--color-on-surface); padding: 8px 4px;">
          <div style="font-size: 18px; font-weight: 900;">{m.v ?? 0}</div>
          <div style="font-size: 8px; text-transform: uppercase; color: var(--color-on-surface-dim); letter-spacing: 0.05em;">{m.l}</div>
        </div>
      {/each}
    </div>
  </div>

  {:else}
    <div style="font-size: 12px; color: var(--color-on-surface-dim);">Loading architecture...</div>
  {/if}

{/if}

</div>
</div>
</div>
</div>

<!-- Create User Modal -->
{#if showCreateUser}
<!-- svelte-ignore a11y_no_static_element_interactions -->
<div style="position: fixed; inset: 0; background: rgba(0,0,0,0.6); z-index: 200; display: flex; align-items: center; justify-content: center;" onclick={(e: MouseEvent) => { if (e.target === e.currentTarget) showCreateUser = false; }}>
  <div class="ink-border stamp-shadow" style="background: var(--color-surface); width: 400px;">
    <div class="dark-title-bar flex items-center justify-between" style="padding: 8px 14px; font-size: 11px;">
      <span>CREATE USER</span>
      <button onclick={() => showCreateUser = false} style="background: none; border: none; color: var(--color-surface); cursor: pointer; font-weight: 900;">&#10005;</button>
    </div>
    <div style="padding: 16px;">
      <div style="margin-bottom: 10px;">
        <div style="font-size: 9px; font-weight: 700; text-transform: uppercase; margin-bottom: 3px;">USERNAME *</div>
        <input type="text" bind:value={newUsername} placeholder="username" style="width: 100%; border: 2px solid var(--color-on-surface); padding: 6px 10px; font-family: var(--font-family-display); font-size: 12px; background: var(--color-surface);" />
      </div>
      <div style="margin-bottom: 10px;">
        <div style="font-size: 9px; font-weight: 700; text-transform: uppercase; margin-bottom: 3px;">PASSWORD *</div>
        <input type="password" bind:value={newPassword} placeholder="min 4 characters" style="width: 100%; border: 2px solid var(--color-on-surface); padding: 6px 10px; font-family: var(--font-family-display); font-size: 12px; background: var(--color-surface);" />
      </div>
      <div style="margin-bottom: 12px;">
        <div style="font-size: 9px; font-weight: 700; text-transform: uppercase; margin-bottom: 3px;">EMAIL</div>
        <input type="email" bind:value={newEmail} placeholder="user@company.com" style="width: 100%; border: 2px solid var(--color-on-surface); padding: 6px 10px; font-family: var(--font-family-display); font-size: 12px; background: var(--color-surface);" />
      </div>
      <button class="send-btn" onclick={createUser} disabled={!newUsername || !newPassword} style="width: 100%; padding: 8px; font-size: 11px; justify-content: center; display: flex;">CREATE USER</button>
    </div>
  </div>
</div>
{/if}
