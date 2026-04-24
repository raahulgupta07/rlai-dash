<script lang="ts">
  import { onMount, tick } from 'svelte';
  import { generateSessionId, markdownToHtml, parseMarkdownTables, tableToCsv, hasNumericData, detectChartType, getAvailableTypes, parseChartHint } from '$lib';
  import type { ToolCall } from '$lib/api';
  import type { ParsedTable } from '$lib/table-parser';
  import type { ChartType } from '$lib/chart-detect';
  import EChartView from '$lib/echart.svelte';
  import * as echarts from 'echarts/core';
  import { BarChart, LineChart, PieChart, ScatterChart } from 'echarts/charts';
  import { TitleComponent, TooltipComponent, LegendComponent, GridComponent } from 'echarts/components';
  import { CanvasRenderer } from 'echarts/renderers';
  echarts.use([BarChart, LineChart, PieChart, ScatterChart, TitleComponent, TooltipComponent, LegendComponent, GridComponent, CanvasRenderer]);
  import TracePanel from '$lib/trace-panel.svelte';

  interface ProjectBrief {
    slug: string;
    name: string;
    agent_name: string;
    owned: boolean;
  }

  interface RoutingInfo {
    routed_to: string;
    slug: string;
    reason: string;
  }

  interface ChatMessage {
    role: 'user' | 'assistant';
    content: string;
    timestamp: string;
    status?: 'streaming' | 'done' | 'error';
    suggestions?: string[];
    toolCalls?: ToolCall[];
    workflowExpanded?: boolean;
    sqlQueries?: string[];
    showSql?: boolean;
    showChart?: boolean;
    chartType?: ChartType;
    routing?: RoutingInfo;
    activeTab?: 'analysis' | 'data' | 'query' | 'chart' | 'sources';
    qualityScore?: number;
    showTrace?: boolean;
    proposedLearnings?: string[];
    proposedLearningsWithScores?: {fact: string; score: number}[];
    autoSavedLearnings?: string[];
    autoSavedWithScores?: {fact: string; score: number}[];
    learningsSaved?: boolean;
    dataTableIndex?: number;
    reasoningUsed?: string;
    analysisUsed?: string;
  }

  let messages = $state<ChatMessage[]>([]);
  let inputText = $state('');
  let isStreaming = $state(false);
  let sessionId = $state('');
  let sessionStartTime = $state('');
  let messagesEl: HTMLDivElement;
  let textareaEl: HTMLTextAreaElement;
  let copiedIndex = $state(-1);

  // Mode selector
  let projects = $state<ProjectBrief[]>([]);
  let selectedMode = $state('auto'); // 'auto' or project slug
  let dropdownOpen = $state(false);

  // Workflows
  let allWorkflows = $state<{project: string; name: string; description?: string; steps: any[]}[]>([]);
  let workflowPickerOpen = $state(false);

  // Reasoning mode
  let reasoningMode = $state<'auto' | 'fast' | 'deep'>('auto');
  let reasoningDropdownOpen = $state(false);

  // Analysis type selector
  let analysisType = $state('auto');
  let analysisDropdownOpen = $state(false);
  const analysisTypes = [
    { value: 'auto', label: 'AUTO', desc: 'Auto-detect analysis type', icon: 'M12 1v4M12 19v4M4.22 4.22l2.83 2.83M16.95 16.95l2.83 2.83M1 12h4M19 12h4M4.22 19.78l2.83-2.83M16.95 7.05l2.83-2.83' },
    { value: 'descriptive', label: 'Descriptive', desc: 'Summarize what happened', icon: 'M4 6h16M4 12h16M4 18h10' },
    { value: 'diagnostic', label: 'Diagnostic', desc: 'Why did it happen?', icon: 'M9 12l2 2 4-4M21 12a9 9 0 1 1-18 0 9 9 0 0 1 18 0z' },
    { value: 'comparative', label: 'Comparative', desc: 'Compare groups or periods', icon: 'M18 20V10M12 20V4M6 20v-6' },
    { value: 'trend', label: 'Trend', desc: 'Patterns over time', icon: 'M3 17l6-6 4 4 8-8' },
    { value: 'predictive', label: 'Predictive', desc: 'Forecast future outcomes', icon: 'M13 2L3 14h9l-1 8 10-12h-9l1-8' },
    { value: 'prescriptive', label: 'Prescriptive', desc: 'Recommend actions', icon: 'M9 5H7a2 2 0 0 0-2 2v12a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V7a2 2 0 0 0-2-2h-2M9 5a2 2 0 0 0 2 2h2a2 2 0 0 0 2-2M9 5a2 2 0 0 1 2-2h2a2 2 0 0 1 2 2' },
    { value: 'anomaly', label: 'Anomaly', desc: 'Find outliers and oddities', icon: 'M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0zM12 9v4M12 17h.01' },
    { value: 'root_cause', label: 'Root Cause', desc: 'Drill into why', icon: 'M12 22c5.523 0 10-4.477 10-10S17.523 2 12 2 2 6.477 2 12s4.477 10 10 10zM12 6v6l4 2' },
    { value: 'pareto', label: 'Pareto', desc: '80/20 analysis', icon: 'M3 3v18h18M7 16h2V8H7v8zM11 16h2V6h-2v10zM15 16h2v-4h-2v4zM19 16h2v-2h-2v2z' },
    { value: 'scenario', label: 'Scenario', desc: 'What-if simulations', icon: 'M16 3h5v5M4 20L21 3M21 16v5h-5M15 15l6 6M4 4l5 5' },
  ];

  async function loadAllWorkflows() {
    const wfs: {project: string; name: string; description?: string; steps: any[]}[] = [];
    for (const p of projects) {
      try {
        const res = await fetch(`/api/workflows?project=${p.slug}`, { headers: _headers() });
        if (res.ok) {
          const d = await res.json();
          for (const w of (d.workflows || [])) {
            wfs.push({ ...w, project: p.agent_name || p.name });
          }
        }
      } catch {}
    }
    allWorkflows = wfs;
  }

  async function runWorkflowChat(wf: {name: string; steps: any[]}) {
    workflowPickerOpen = false;
    const steps = wf.steps || [];
    if (steps.length === 0) {
      send(`Run the "${wf.name}" workflow`);
      return;
    }
    for (const step of steps) {
      const stepMsg = typeof step === 'string' ? step : (step.question || step.prompt || step.query || JSON.stringify(step));
      await send(stepMsg);
      await new Promise<void>((resolve) => {
        const check = () => { if (!isStreaming) resolve(); else setTimeout(check, 500); };
        setTimeout(check, 1000);
      });
    }
  }

  // Sidebar — persisted in localStorage, default open
  let sidebarOpen = $state(typeof localStorage !== 'undefined' ? localStorage.getItem('dash_sidebar') !== 'closed' : true);
  let pastSessions = $state<{session_id: string; created_at: string; updated_at: string}[]>([]);

  function toggleSidebar() {
    sidebarOpen = !sidebarOpen;
    localStorage.setItem('dash_sidebar', sidebarOpen ? 'open' : 'closed');
    if (sidebarOpen) loadSessions();
  }

  async function loadSessions() {
    try {
      // Load ALL user sessions across all agents
      const res = await fetch('/api/sessions', { headers: _headers() });
      if (res.ok) { const d = await res.json(); pastSessions = d.sessions || []; }
    } catch {}
  }

  async function registerSession(msg: string) {
    try {
      const proj = selectedMode !== 'auto' ? selectedMode : '';
      await fetch(`/api/sessions/register?session_id=${encodeURIComponent(sessionId)}&message=${encodeURIComponent(msg)}${proj ? `&project=${encodeURIComponent(proj)}` : ''}`, {
        method: 'POST', headers: _headers()
      });
    } catch {}
  }

  async function switchSession(sid: string) {
    sessionId = sid;
    localStorage.setItem('dash_super_session', sid);
    messages = [];
    sessionStartTime = getTimestamp();

    // Load messages from this session
    try {
      const res = await fetch(`/api/sessions/${sid}/messages`, { headers: _headers() });
      if (res.ok) {
        const data = await res.json();
        const loaded = data.messages || [];
        messages = loaded.map((m: any) => ({
          role: m.role,
          content: m.content,
          timestamp: '',
          status: m.role === 'assistant' ? 'done' : undefined,
          toolCalls: [],
          workflowExpanded: false,
        }));
        scrollToBottom();
      }
    } catch {}
    textareaEl?.focus();
  }

  function formatSessionTime(ts: string | null): string {
    if (!ts) return '';
    try {
      const d = new Date(ts);
      if (isNaN(d.getTime())) return '';
      const now = new Date();
      const diff = now.getTime() - d.getTime();
      if (diff < 3600000) return Math.floor(diff / 60000) + 'm ago';
      if (diff < 86400000) return Math.floor(diff / 3600000) + 'h ago';
      return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
    } catch { return ''; }
  }

  function _headers(): Record<string, string> {
    const t = typeof localStorage !== 'undefined' ? localStorage.getItem('dash_token') : null;
    return t ? { Authorization: `Bearer ${t}` } : {};
  }

  function getSelectedLabel(): string {
    if (selectedMode === 'auto') return 'AUTO';
    const p = projects.find(p => p.slug === selectedMode);
    return p ? p.agent_name : 'AUTO';
  }

  async function loadProjects() {
    try {
      const res = await fetch('/api/user-projects-brief', { headers: _headers() });
      if (res.ok) {
        const d = await res.json();
        projects = d.projects || [];
        // Load workflows after projects
        loadAllWorkflows();
      }
    } catch {}
  }

  function getTimestamp(): string {
    return new Date().toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit', hour12: true });
  }

  function getTotalDuration(tools: ToolCall[]): string {
    let total = 0;
    for (const t of tools) {
      if (t.duration) total += parseFloat(t.duration);
    }
    return total > 0 ? total.toFixed(1) + 's' : '';
  }

  function getAgentMode(tools: ToolCall[]): 'deep' | 'fast' {
    const names = tools.map(t => t.name.toLowerCase());
    if (names.some(n => n === 'think' || n === 'analyze')) return 'deep';
    const sqlCount = names.filter(n => n.includes('sql') || n.includes('query')).length;
    if (sqlCount >= 2 || tools.length >= 7) return 'deep';
    return 'fast';
  }

  function getSuggestions(content: string): string[] {
    const lower = content.toLowerCase();
    if (lower.includes('mrr') || lower.includes('revenue')) return ["Break down MRR by plan tier", "Show MRR trend over last 6 months", "What's our net revenue retention?"];
    if (lower.includes('churn') || lower.includes('cancel')) return ["What are the top cancellation reasons?", "Which customers are at risk?", "Compare churn rates across plans"];
    return ["Show me a summary of all my data", "What trends do you see?", "Create a report"];
  }

  onMount(async () => {
    sessionId = localStorage.getItem('dash_super_session') || generateSessionId();
    localStorage.setItem('dash_super_session', sessionId);
    sessionStartTime = getTimestamp();
    textareaEl?.focus();
    loadProjects();
    loadSessions();
  });

  function newChat() {
    messages = [];
    sessionId = generateSessionId();
    localStorage.setItem('dash_super_session', sessionId);
    sessionStartTime = getTimestamp();
    textareaEl?.focus();
  }

  function toggleWorkflow(index: number) {
    const msg = messages[index];
    if (msg) {
      messages = [
        ...messages.slice(0, index),
        { ...msg, workflowExpanded: !msg.workflowExpanded },
        ...messages.slice(index + 1)
      ];
    }
  }

  async function scrollToBottom() {
    await tick();
    if (messagesEl) messagesEl.scrollTop = messagesEl.scrollHeight;
  }

  async function copyMessage(index: number) {
    const msg = messages[index];
    if (msg) {
      await navigator.clipboard.writeText(msg.content);
      copiedIndex = index;
      setTimeout(() => { copiedIndex = -1; }, 2000);
    }
  }

  const DEEP_KEYWORDS = /\b(why|compare|explain|suggest|recommend|correlate|analyze|break down|what should|how can|investigate|diagnose|root cause)\b/i;

  function isComplexQuery(text: string): boolean {
    if (DEEP_KEYWORDS.test(text)) return true;
    if ((text.match(/\band\b/gi) || []).length >= 2) return true;
    if (text.split('?').length > 2) return true;
    return false;
  }

  async function send(text?: string) {
    const msg = (text || inputText).trim();
    if (!msg || isStreaming) return;
    inputText = '';
    if (textareaEl) textareaEl.style.height = 'auto';

    messages = [...messages, { role: 'user', content: msg, timestamp: getTimestamp() }];
    isStreaming = true;
    registerSession(msg);
    await scrollToBottom();

    messages = [...messages, { role: 'assistant', content: '', timestamp: '', status: 'streaming', toolCalls: [], workflowExpanded: true }];
    await scrollToBottom();

    try {
      abortController = new AbortController();
      const formData = new FormData();
      formData.append('message', msg);
      formData.append('stream', 'true');
      formData.append('session_id', sessionId);
      formData.append('mode', selectedMode);
      formData.append('reasoning', reasoningMode);
      formData.append('analysis_type', analysisType);

      const response = await fetch('/api/super-chat', {
        method: 'POST',
        headers: _headers(),
        body: formData,
        signal: abortController.signal
      });

      if (!response.ok) {
        const errText = await response.text();
        const last = messages[messages.length - 1];
        if (last?.role === 'assistant') {
          messages = [...messages.slice(0, -1), { ...last, content: `Error: ${errText}`, timestamp: getTimestamp(), status: 'error' }];
        }
        isStreaming = false;
        return;
      }

      const reader = response.body?.getReader();
      if (!reader) { isStreaming = false; return; }

      const decoder = new TextDecoder();
      let buffer = '';
      let currentEvent = '';
      const toolTimers: Record<string, number> = {};

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        buffer = lines.pop() || '';

        for (const line of lines) {
          if (line.startsWith('event: ')) {
            currentEvent = line.slice(7).trim();
            continue;
          }
          if (!line.startsWith('data: ')) continue;
          const raw = line.slice(6).trim();
          if (raw === '[DONE]') continue;

          try {
            const data = JSON.parse(raw);

            switch (currentEvent) {
              case 'Routing': {
                // Routing info from auto-router
                const last = messages[messages.length - 1];
                if (last?.role === 'assistant') {
                  messages = [...messages.slice(0, -1), { ...last, routing: data as RoutingInfo }];
                }
                break;
              }

              case 'ToolCallStarted': {
                const tool = data.tool;
                if (tool) {
                  const last = messages[messages.length - 1];
                  if (last?.role === 'assistant') {
                    const name = tool.tool_name || 'unknown';
                    toolTimers[name] = Date.now();
                    const existing = last.toolCalls || [];
                    messages = [...messages.slice(0, -1), { ...last, toolCalls: [...existing, { name, status: 'running', args: tool.tool_args }] }];
                  }
                }
                break;
              }

              case 'ToolCallCompleted': {
                const tool = data.tool;
                if (tool) {
                  const last = messages[messages.length - 1];
                  if (last?.role === 'assistant') {
                    const name = tool.tool_name || 'unknown';
                    const start = toolTimers[name];
                    const duration = start ? ((Date.now() - start) / 1000).toFixed(2) + 's' : undefined;
                    const sqlQuery = (name === 'run_sql_query' || name === 'run_sql')
                      ? (tool.tool_args?.query || tool.tool_args?.sql || undefined) : undefined;
                    const existing = last.toolCalls || [];
                    const idx = existing.findIndex(t => t.name === name && t.status === 'running');
                    let updated: ToolCall[];
                    if (idx >= 0) {
                      updated = [...existing];
                      updated[idx] = { ...updated[idx], status: 'done', duration };
                    } else {
                      updated = existing;
                    }
                    const sqls = last.sqlQueries || [];
                    if (sqlQuery && !sqls.includes(sqlQuery)) sqls.push(sqlQuery);
                    messages = [...messages.slice(0, -1), { ...last, toolCalls: updated, sqlQueries: sqls }];
                  }
                }
                break;
              }

              case 'TeamToolCallStarted': {
                const tool = data.tool;
                if (tool) {
                  const last = messages[messages.length - 1];
                  if (last?.role === 'assistant') {
                    const name = tool.tool_name || 'unknown';
                    toolTimers[`team_${name}`] = Date.now();
                    const existing = last.toolCalls || [];
                    messages = [...messages.slice(0, -1), { ...last, toolCalls: [...existing, { name, status: 'running', args: tool.tool_args }] }];
                  }
                }
                break;
              }

              case 'TeamToolCallCompleted': {
                const tool = data.tool;
                if (tool) {
                  const last = messages[messages.length - 1];
                  if (last?.role === 'assistant') {
                    const name = tool.tool_name || 'unknown';
                    const start = toolTimers[`team_${name}`];
                    const duration = start ? ((Date.now() - start) / 1000).toFixed(2) + 's' : undefined;
                    const existing = last.toolCalls || [];
                    const idx = existing.findIndex(t => t.name === name && t.status === 'running');
                    let updated: ToolCall[];
                    if (idx >= 0) {
                      updated = [...existing];
                      updated[idx] = { ...updated[idx], status: 'done', duration };
                    } else {
                      updated = existing;
                    }
                    messages = [...messages.slice(0, -1), { ...last, toolCalls: updated }];
                  }
                }
                break;
              }

              case 'RunStarted': {
                if (data.agent_name) {
                  const last = messages[messages.length - 1];
                  if (last?.role === 'assistant') {
                    const existing = last.toolCalls || [];
                    messages = [...messages.slice(0, -1), { ...last, toolCalls: [...existing, { name: `${data.agent_name} agent`, status: 'running' }] }];
                  }
                }
                break;
              }

              case 'RunCompleted': {
                if (data.agent_name) {
                  const last = messages[messages.length - 1];
                  if (last?.role === 'assistant') {
                    const existing = last.toolCalls || [];
                    const idx = existing.findIndex(t => t.name === `${data.agent_name} agent` && t.status === 'running');
                    if (idx >= 0) {
                      const updated = [...existing];
                      updated[idx] = { ...updated[idx], status: 'done' };
                      messages = [...messages.slice(0, -1), { ...last, toolCalls: updated }];
                    }
                  }
                }
                break;
              }

              case 'TeamRunContent':
              case 'RunContent': {
                if (data.content && typeof data.content === 'string') {
                  const last = messages[messages.length - 1];
                  if (last?.role === 'assistant') {
                    messages = [...messages.slice(0, -1), { ...last, content: last.content + data.content }];
                  }
                  scrollToBottom();
                }
                break;
              }
            }
          } catch {}
        }
      }

      // Done
      const last = messages[messages.length - 1];
      if (last?.role === 'assistant') {
        messages = [...messages.slice(0, -1), {
          ...last, timestamp: getTimestamp(), status: 'done',
          suggestions: getSuggestions(last.content), workflowExpanded: false
        }];
      }
      isStreaming = false;
      scrollToBottom();
      textareaEl?.focus();
      loadSessions();

      // Post-response: learning extraction + smart follow-ups + quality score
      const routedSlug = messages[messages.length - 1]?.routing?.slug || (selectedMode !== 'auto' ? selectedMode : projects[0]?.slug);
      const lastUserMsg = msg;
      const lastAssistantMsg = messages[messages.length - 1]?.content || '';
      if (routedSlug && lastUserMsg && lastAssistantMsg) {
        // Context extraction — auto-save high confidence, propose low confidence
        fetch(`/api/projects/${routedSlug}/extract-context`, {
          method: 'POST', headers: { ..._headers(), 'Content-Type': 'application/json' },
          body: JSON.stringify({ question: lastUserMsg, answer: lastAssistantMsg })
        }).then(r => r.json()).then(d => {
          const cur = messages[messages.length - 1];
          if (!cur || cur.role !== 'assistant') return;
          const autoSaved = d.auto_saved_with_scores || d.auto_saved?.map((f: string) => ({fact: f, score: 90})) || [];
          const needsApproval = d.facts_with_scores || d.facts?.map((f: string) => ({fact: f, score: 40})) || [];
          if (autoSaved.length > 0 || needsApproval.length > 0) {
            messages = [...messages.slice(0, -1), {
              ...cur,
              proposedLearnings: needsApproval.length > 0 ? d.facts : undefined,
              proposedLearningsWithScores: needsApproval.length > 0 ? needsApproval : undefined,
              autoSavedLearnings: autoSaved.length > 0 ? d.auto_saved : undefined,
              autoSavedWithScores: autoSaved.length > 0 ? autoSaved : undefined,
            }];
          }
        }).catch(() => {});

        // Smart follow-ups
        fetch(`/api/projects/${routedSlug}/suggest-followups`, {
          method: 'POST', headers: { ..._headers(), 'Content-Type': 'application/json' },
          body: JSON.stringify({ question: lastUserMsg, answer: lastAssistantMsg })
        }).then(r => r.json()).then(d => {
          if (d.suggestions?.length) {
            const cur = messages[messages.length - 1];
            if (cur?.role === 'assistant') {
              messages = [...messages.slice(0, -1), { ...cur, suggestions: d.suggestions }];
            }
          }
        }).catch(() => {});

        // Quality score (delayed)
        setTimeout(async () => {
          try {
            const res = await fetch(`/api/projects/${routedSlug}/scores/latest?session_id=${sessionId}`, { headers: _headers() });
            if (res.ok) {
              const d = await res.json();
              if (d.score) {
                const cur = messages[messages.length - 1];
                if (cur?.role === 'assistant') {
                  messages = [...messages.slice(0, -1), { ...cur, qualityScore: d.score }];
                }
              }
            }
          } catch {}
        }, 5000);
      }
    } catch (err) {
      const last = messages[messages.length - 1];
      if (last?.role === 'assistant') {
        messages = [...messages.slice(0, -1), { ...last, content: `Error: ${err instanceof Error ? err.message : 'Connection failed'}`, timestamp: getTimestamp(), status: 'error' }];
      }
      isStreaming = false;
      scrollToBottom();
    }
  }

  function handleKeydown(e: KeyboardEvent) {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); send(); }
  }

  function renderStars(score: number | undefined): string {
    if (!score) return '';
    return '★'.repeat(score) + '☆'.repeat(5 - score);
  }

  function parseClarify(content: string): string[] | null {
    const match = content.match(/\[CLARIFY:\s*(.+?)\]/);
    if (match) return match[1].split('|').map(s => s.trim());
    return null;
  }

  /** Generate a human-readable caption for a chart from table data */
  function generateChartCaption(tbl: {headers: string[]; rows: string[][]}): string {
    if (!tbl.headers.length || !tbl.rows.length) return '';
    const label = tbl.headers[0] || 'Category';
    let numIdx = -1;
    let numHeader = '';
    for (let c = 1; c < tbl.headers.length; c++) {
      const vals = tbl.rows.map(r => parseFloat((r[c] || '').replace(/[$,%,]/g, '')));
      if (vals.filter(v => !isNaN(v)).length >= tbl.rows.length * 0.5) {
        numIdx = c; numHeader = tbl.headers[c]; break;
      }
    }
    if (numIdx < 0) return `${tbl.rows.length} items by ${label}.`;
    const values = tbl.rows.map(r => ({
      label: (r[0] || '').replace(/\*\*/g, ''),
      val: parseFloat((r[numIdx] || '').replace(/[$,%,]/g, ''))
    })).filter(v => !isNaN(v.val));
    if (values.length === 0) return '';
    const sorted = [...values].sort((a, b) => b.val - a.val);
    const top = sorted[0]; const bottom = sorted[sorted.length - 1];
    const total = values.reduce((s, v) => s + v.val, 0);
    const avg = total / values.length;
    const fmt = (n: number) => n >= 1e6 ? (n/1e6).toFixed(1) + 'M' : n >= 1e3 ? (n/1e3).toFixed(1) + 'K' : n % 1 === 0 ? n.toLocaleString() : n.toFixed(1);
    let caption = `Highest ${numHeader}: ${top.label} (${fmt(top.val)})`;
    if (sorted.length > 1 && top.label !== bottom.label) caption += `. Lowest: ${bottom.label} (${fmt(bottom.val)})`;
    if (sorted.length >= 3) caption += `. Average: ${fmt(avg)}`;
    if (values.length >= 4) {
      let ups = 0, downs = 0;
      for (let i = 1; i < values.length; i++) { if (values[i].val > values[i-1].val) ups++; else if (values[i].val < values[i-1].val) downs++; }
      if (ups > values.length * 0.7) caption += '. Trend: increasing ▲';
      else if (downs > values.length * 0.7) caption += '. Trend: decreasing ▼';
    }
    return caption + '.';
  }

  /** Format a table cell: render markdown bold, [UP/DOWN/FLAT] badges, trend arrows, percentages */
  function formatCell(cell: string): string {
    if (!cell || typeof cell !== 'string') return cell || '';
    let s = cell.trim();

    // [UP:+3.7] / [DOWN:-2.0] / [FLAT:-0.3] → colored badge
    const dirMatch = s.match(/^\[?(UP|DOWN|FLAT):?\s*([+-]?[\d.]+)\]?$/i);
    if (dirMatch) {
      const dir = dirMatch[1].toUpperCase();
      const val = dirMatch[2];
      if (dir === 'UP') return `<span style="color:#16a34a;font-weight:700;">▲ +${val.replace(/^\+/,'')}</span>`;
      if (dir === 'DOWN') return `<span style="color:#dc2626;font-weight:700;">▼ ${val.startsWith('-') ? val : '-' + val}</span>`;
      return `<span style="color:#a3a3a3;font-weight:700;">━ ${val}</span>`;
    }

    // Trend arrows: ▲ / ▼ / ━ or ↑ / ↓ / → with optional number
    if (/^[▲↑]/.test(s)) return `<span style="color:#16a34a;font-weight:700;">${s}</span>`;
    if (/^[▼↓]/.test(s)) return `<span style="color:#dc2626;font-weight:700;">${s}</span>`;
    if (/^[━→]/.test(s)) return `<span style="color:#a3a3a3;font-weight:700;">${s}</span>`;

    // **bold** markdown → <strong>
    s = s.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');

    // Percentage coloring: positive green, negative red
    const pctMatch = s.match(/^([+-]?\d+\.?\d*)%$/);
    if (pctMatch) {
      const v = parseFloat(pctMatch[1]);
      if (v > 50) return `<span style="color:#16a34a;font-weight:600;">${s}</span>`;
      if (v < 20) return `<span style="color:#dc2626;font-weight:600;">${s}</span>`;
    }

    return s;
  }

  function autoResize() {
    if (textareaEl) {
      textareaEl.style.height = 'auto';
      textareaEl.style.height = Math.min(textareaEl.scrollHeight, 120) + 'px';
    }
  }

  let abortController: AbortController | null = null;

  // Slide Agent (presentation) state
  let slidesPanelOpen = $state(false);
  let slidesData = $state<any[]>([]);
  let slidesThinking = $state<any>(null);
  let slidesLoading = $state(false);
  let slidesProgress = $state('');
  let currentSlide = $state(0);
  let showSaveModal = $state(false);
  let showWorkflowSaveModal = $state(false);
  let wfSaveName = $state('');
  let wfSaveDesc = $state('');
  let wfSaveSteps = $state<{question: string; checked: boolean}[]>([]);

  function openWorkflowSave() {
    const userMsgs = messages.filter(m => m.role === 'user');
    wfSaveSteps = userMsgs.map(m => ({ question: m.content, checked: true }));
    wfSaveName = '';
    wfSaveDesc = '';
    showWorkflowSaveModal = true;
  }

  async function confirmWorkflowSave() {
    const steps = wfSaveSteps.filter(s => s.checked).map(s => ({ type: 'query', title: s.question.slice(0, 60), question: s.question }));
    if (!wfSaveName.trim() || steps.length === 0) return;
    const slug = selectedMode !== 'auto' ? selectedMode : (messages.find(m => m.routing?.slug)?.routing?.slug || '');
    if (!slug) return;
    try {
      await fetch(`/api/projects/${slug}/workflows-db`, {
        method: 'POST', headers: { ..._headers(), 'Content-Type': 'application/json' },
        body: JSON.stringify({ name: wfSaveName.trim(), description: wfSaveDesc.trim(), steps, source: 'user' })
      });
      showWorkflowSaveModal = false;
      loadAllWorkflows();
    } catch {}
  }
  let saveTitle = $state('');
  let pptxSteps = $state<{label: string; status: 'pending'|'active'|'done'|'error'}[]>([]);
  let pptxGenerating = $state(false);
  let pptxSavedVersion = $state(0);

  // PIN modal
  let showPinModal = $state(false);
  let pinModalData = $state<{msgIndex: number; tables: any[]; content: string} | null>(null);
  let pinDashboards = $state<any[]>([]);
  let pinSelectedDash = $state<number | null>(null);
  let pinNewDashName = $state('');
  let pinWidgetTitle = $state('');
  let pinProjectSlug = $state('');

  async function openPinModal(msgIndex: number, tables: any[], content: string, projectSlug: string) {
    pinModalData = { msgIndex, tables, content };
    pinWidgetTitle = tables?.[0]?.headers?.join(' / ') || content.slice(0, 50);
    pinProjectSlug = projectSlug || '';
    showPinModal = true;
    pinDashboards = [];
    if (pinProjectSlug) {
      try {
        const res = await fetch(`/api/projects/${pinProjectSlug}/dashboards`, { headers: _headers() });
        if (res.ok) { const d = await res.json(); pinDashboards = d.dashboards || []; }
      } catch {}
    }
    pinSelectedDash = pinDashboards.length > 0 ? pinDashboards[0].id : null;
  }

  async function confirmPin() {
    if (!pinModalData || !pinProjectSlug) return;
    const { tables, content } = pinModalData;
    let dashId = pinSelectedDash;
    if (!dashId && pinNewDashName.trim()) {
      try {
        const res = await fetch(`/api/projects/${pinProjectSlug}/dashboards?name=${encodeURIComponent(pinNewDashName.trim())}`, { method: 'POST', headers: _headers() });
        if (res.ok) { const d = await res.json(); dashId = d.id; }
      } catch {}
    }
    if (!dashId) return;
    const hasTable = tables?.length > 0 && tables[0].headers?.length > 0;
    const widget = hasTable
      ? { type: 'chart', title: pinWidgetTitle, chartType: 'bar', headers: tables[0].headers, rows: tables[0].rows }
      : { type: 'text', title: pinWidgetTitle, content, full: true };
    await fetch(`/api/projects/${pinProjectSlug}/dashboards/${dashId}/widgets`, {
      method: 'POST', headers: { ..._headers(), 'Content-Type': 'application/json' },
      body: JSON.stringify(widget),
    });
    showPinModal = false;
    pinModalData = null;
    pinNewDashName = '';
  }

  async function generateSlides() {
    if (messages.length < 2 || slidesLoading) return;
    slidesLoading = true;
    pptxGenerating = true;
    slidesPanelOpen = true;
    slidesData = [];
    slidesThinking = null;
    currentSlide = 0;
    pptxSavedVersion = 0;

    const agentName = selectedMode !== 'auto' ? getSelectedLabel() : 'Dash Agent';

    pptxSteps = [
      { label: `Reading conversation (${messages.filter(m => m.role === 'user').length} questions)`, status: 'active' },
      { label: 'Analyzing narrative and key insights', status: 'pending' },
      { label: 'Planning slide structure', status: 'pending' },
      { label: 'Generating slide content', status: 'pending' },
    ];

    const updateStep = (idx: number, status: 'done'|'active'|'error', label?: string) => {
      pptxSteps = pptxSteps.map((s, i) => {
        if (i === idx) return { ...s, status, label: label || s.label };
        if (i < idx && s.status !== 'error') return { ...s, status: 'done' };
        return s;
      });
    };

    try {
      await new Promise(r => setTimeout(r, 300));
      updateStep(0, 'done');
      updateStep(1, 'active');
      await new Promise(r => setTimeout(r, 200));
      updateStep(2, 'active');

      const res = await fetch('/api/export/slides-agent', {
        method: 'POST',
        headers: { ..._headers(), 'Content-Type': 'application/json' },
        body: JSON.stringify({
          messages: messages.map(m => ({ role: m.role, content: m.content })),
          title: agentName + ' Analysis',
          agent_name: agentName
        })
      });

      if (res.ok) {
        const data = await res.json();
        slidesThinking = data.thinking;
        slidesData = data.slides || [];
        updateStep(1, 'done');
        updateStep(2, 'done', `Planned ${slidesData.length} slides`);
        updateStep(3, 'done');
      } else {
        updateStep(2, 'error', 'Failed to generate slides');
      }
    } catch (e) {
      const failIdx = pptxSteps.findIndex(s => s.status === 'active');
      if (failIdx >= 0) pptxSteps = pptxSteps.map((s, i) => i === failIdx ? { ...s, status: 'error' as const, label: 'Error' } : s);
    }
    slidesLoading = false;
    pptxGenerating = false;
    if (slidesData.length > 0) {
      setTimeout(() => { pptxSteps = []; }, 1500);
    }
  }

  async function savePresentation() {
    if (slidesData.length === 0) return;
    const agentName = selectedMode !== 'auto' ? getSelectedLabel() : 'Dash Agent';
    saveTitle = agentName + ' Analysis';
    showSaveModal = true;
  }

  async function confirmSave() {
    if (!saveTitle.trim()) return;
    const projSlug = selectedMode !== 'auto' ? selectedMode : 'dash_agent';
    try {
      const res = await fetch('/api/export/presentations', {
        method: 'POST',
        headers: { ..._headers(), 'Content-Type': 'application/json' },
        body: JSON.stringify({
          project_slug: projSlug,
          title: saveTitle.trim(),
          thinking: slidesThinking,
          slides: slidesData,
          source_messages: messages.map(m => ({ role: m.role, content: m.content }))
        })
      });
      if (res.ok) {
        const d = await res.json();
        showSaveModal = false;
        slidesProgress = `Saved as v${d.version}`;
        setTimeout(() => slidesProgress = '', 3000);
      }
    } catch {}
  }

  async function downloadPptx() {
    if (messages.length < 2 || pptxGenerating) return;
    pptxGenerating = true;
    slidesPanelOpen = true;
    slidesData = [];
    slidesThinking = null;
    pptxSavedVersion = 0;
    const agentName = selectedMode !== 'auto' ? getSelectedLabel() : 'Dash Agent';
    const agentTitle = agentName + ' Analysis';
    const projSlug = selectedMode !== 'auto' ? selectedMode : 'dash_agent';

    pptxSteps = [
      { label: `Reading conversation (${messages.filter(m => m.role === 'user').length} questions)`, status: 'active' },
      { label: 'Analyzing narrative and key insights', status: 'pending' },
      { label: 'Planning slides', status: 'pending' },
      { label: 'Generating slide content', status: 'pending' },
      { label: 'Creating PowerPoint file', status: 'pending' },
      { label: 'Saving to presentations', status: 'pending' },
      { label: 'Downloading PPTX', status: 'pending' },
    ];

    const updateStep = (idx: number, status: 'done'|'active'|'error', label?: string) => {
      pptxSteps = pptxSteps.map((s, i) => {
        if (i === idx) return { ...s, status, label: label || s.label };
        if (i < idx && s.status !== 'error') return { ...s, status: 'done' };
        return s;
      });
    };

    try {
      await new Promise(r => setTimeout(r, 300));
      updateStep(0, 'done');
      updateStep(1, 'active');

      await new Promise(r => setTimeout(r, 200));
      updateStep(2, 'active');
      const agentRes = await fetch('/api/export/slides-agent', {
        method: 'POST',
        headers: { ..._headers(), 'Content-Type': 'application/json' },
        body: JSON.stringify({
          messages: messages.map(m => ({ role: m.role, content: m.content })),
          title: agentTitle,
          agent_name: agentName
        })
      });

      if (!agentRes.ok) { updateStep(2, 'error', 'Failed to analyze conversation'); pptxGenerating = false; return; }
      const agentData = await agentRes.json();
      slidesThinking = agentData.thinking;
      slidesData = agentData.slides || [];
      updateStep(1, 'done');
      updateStep(2, 'done', `Planning ${slidesData.length} slides`);
      updateStep(3, 'done');
      updateStep(4, 'active');

      await new Promise(r => setTimeout(r, 300));
      updateStep(5, 'active');
      const saveRes = await fetch('/api/export/presentations', {
        method: 'POST',
        headers: { ..._headers(), 'Content-Type': 'application/json' },
        body: JSON.stringify({
          project_slug: projSlug,
          title: agentTitle,
          thinking: slidesThinking,
          slides: slidesData,
          source_messages: messages.map(m => ({ role: m.role, content: m.content }))
        })
      });

      let presId = 0;
      if (saveRes.ok) {
        const d = await saveRes.json();
        presId = d.id;
        pptxSavedVersion = d.version;
        updateStep(5, 'done', `Saved as "${agentTitle} v${d.version}"`);
      } else {
        updateStep(5, 'error', 'Save failed');
      }

      updateStep(4, 'done');
      updateStep(6, 'active');
      if (presId) {
        const pptxRes = await fetch(`/api/export/presentations/${presId}/pptx`, {
          method: 'POST', headers: _headers()
        });
        if (pptxRes.ok) {
          const blob = await pptxRes.blob();
          const url = URL.createObjectURL(blob);
          const a = document.createElement('a');
          a.href = url;
          a.download = `${agentName}-v${pptxSavedVersion}.pptx`;
          a.click();
          URL.revokeObjectURL(url);
          updateStep(6, 'done', `Downloaded ${agentName}-v${pptxSavedVersion}.pptx`);
        } else {
          updateStep(6, 'error', 'Download failed');
        }
      }
    } catch (e) {
      const failIdx = pptxSteps.findIndex(s => s.status === 'active');
      if (failIdx >= 0) pptxSteps = pptxSteps.map((s, i) => i === failIdx ? { ...s, status: 'error' as const, label: 'Failed' } : s);
    }
    pptxGenerating = false;
  }

  function downloadHTML() {
    if (slidesData.length === 0) return;
    const agentName = selectedMode !== 'auto' ? getSelectedLabel() : 'Dash Agent';
    const title = agentName + ' Analysis';
    const date = new Date().toLocaleDateString('en-US', {month: 'long', day: 'numeric', year: 'numeric'});
    const narrative = slidesThinking?.narrative || '';
    const keyInsight = slidesThinking?.key_insight || '';

    let slidesHTML = '';
    for (let i = 0; i < slidesData.length; i++) {
      const s = slidesData[i];
      const layout = s.layout || 'bullets';
      const sTitle = s.title || '';
      const bullets = (s.bullets || []).map((b: string, bi: number) => `<div style="font-size:16px;color:#333;padding:10px 14px;border-left:4px solid #D24726;margin-bottom:8px;background:#fafaf8;"><span style="font-weight:800;color:#D24726;">${bi+1}.</span> ${b}</div>`).join('');
      const actionLine = s.action_line ? `<div style="margin-top:20px;padding:12px 16px;border-top:2px solid #1a1a1a;font-size:13px;font-weight:700;">${s.action_line}</div>` : '';
      const topic = s.topic || 'ANALYSIS';

      let content = '';
      if (layout === 'cover') {
        content = `<div style="display:flex;flex-direction:column;align-items:center;justify-content:center;height:100%;text-align:center;">
          <div style="font-size:42px;font-weight:900;color:#1a1a1a;max-width:700px;">${sTitle}</div>
          <div style="width:80px;height:3px;background:linear-gradient(90deg,#D24726,#F0A030);margin:24px auto;"></div>
          ${s.bullets?.[0] ? `<div style="font-size:18px;color:#666;">${s.bullets[0]}</div>` : ''}
          <div style="font-size:12px;color:#999;margin-top:40px;text-transform:uppercase;letter-spacing:0.1em;">${agentName} &middot; ${date}</div>
          <div style="font-size:10px;color:#bbb;margin-top:8px;letter-spacing:0.15em;">POWERED BY RLAI DASH</div>
        </div>`;
      } else if (layout === 'kpi' && s.kpis?.length) {
        const kpis = s.kpis.map((k: any) => `<div style="flex:1;text-align:center;padding:24px;border:2px solid #e0e0d8;">
          <div style="font-size:42px;font-weight:900;">${k.value}</div>
          <div style="font-size:11px;color:#888;text-transform:uppercase;margin-top:6px;">${k.label}</div>
          ${k.change ? `<div style="font-size:16px;font-weight:700;color:${k.change?.startsWith('+') ? '#00873c' : '#d32f2f'};margin-top:4px;">${k.change}</div>` : ''}
        </div>`).join('');
        content = `<div style="font-size:22px;font-weight:800;margin-bottom:20px;">${sTitle}</div>
          <div style="width:100%;height:2px;background:#1a1a1a;margin-bottom:24px;"></div>
          <div style="display:flex;gap:16px;margin:20px 0;">${kpis}</div>${bullets}${actionLine}`;
      } else if (s.chart) {
        const chartId = 'chart_' + i;
        const chartType = s.chart.type === 'horizontal_bar' ? 'bar' : (s.chart.type || 'bar');
        const labels = JSON.stringify(s.chart.labels || []);
        const values = JSON.stringify(s.chart.values || []);
        let chartOpt = '';
        if (chartType === 'pie') {
          chartOpt = `{tooltip:{trigger:'item',formatter:'{b}: {c} ({d}%)'},series:[{type:'pie',radius:['35%','60%'],data:${labels}.map((l,i)=>({name:l,value:${values}[i]})),label:{fontSize:11},itemStyle:{borderRadius:4,borderColor:'#fff',borderWidth:2}}]}`;
        } else {
          chartOpt = `{tooltip:{trigger:'axis'},xAxis:{type:'category',data:${labels},axisLabel:{fontSize:10,rotate:${labels}.length>5?25:0}},yAxis:{type:'value'},series:[{type:'${chartType}',data:${values},itemStyle:{color:'#D24726',borderRadius:[4,4,0,0]}${chartType==='line'?',smooth:true,areaStyle:{opacity:0.08}':''}}],grid:{left:'10%',right:'5%',bottom:'15%',top:'12%'}}`;
        }
        content = `<div style="font-size:22px;font-weight:800;margin-bottom:20px;">${sTitle}</div>
          <div style="width:100%;height:2px;background:#1a1a1a;margin-bottom:20px;"></div>
          <div style="display:flex;gap:24px;">
            <div style="flex:3;"><div style="font-size:10px;font-weight:700;text-transform:uppercase;color:#888;margin-bottom:8px;">${s.chart.title || 'EXHIBIT'}</div><div id="${chartId}" style="width:100%;height:300px;"></div><div style="font-size:9px;color:#aaa;margin-top:4px;">Source: Project data</div></div>
            <div style="flex:2;border-left:2px solid #e0e0d8;padding-left:16px;"><div style="font-size:10px;font-weight:700;text-transform:uppercase;color:#888;margin-bottom:12px;">KEY TAKEAWAYS</div>${bullets}</div>
          </div>${actionLine}
          <script>echarts.init(document.getElementById('${chartId}')).setOption(${chartOpt});<\/script>`;
      } else if (s.table) {
        const headers = (s.table.headers||[]).map((h: string) => `<th style="padding:8px 12px;text-align:left;font-size:10px;text-transform:uppercase;letter-spacing:1px;color:#666;border-bottom:2px solid #1a1a1a;">${h}</th>`).join('');
        const rows = (s.table.rows||[]).slice(0,12).map((r: string[], ri: number) => `<tr style="background:${ri%2===0?'#fafaf8':'#fff'};">${r.map((c: string) => `<td style="padding:7px 12px;font-size:12px;border-bottom:1px solid #eee;">${c}</td>`).join('')}</tr>`).join('');
        content = `<div style="font-size:22px;font-weight:800;margin-bottom:20px;">${sTitle}</div>
          <div style="width:100%;height:2px;background:#1a1a1a;margin-bottom:20px;"></div>
          <table style="width:100%;border-collapse:collapse;"><thead><tr>${headers}</tr></thead><tbody>${rows}</tbody></table>${bullets}${actionLine}`;
      } else if (layout === 'recommendations') {
        const cards = (s.bullets||[]).map((b: string, bi: number) => `<div style="padding:16px;border:2px solid #e0e0d8;background:#fff;"><div style="font-size:10px;font-weight:900;color:#D24726;text-transform:uppercase;margin-bottom:6px;">PRIORITY ${bi+1}</div><div style="font-size:14px;color:#333;">${b}</div></div>`).join('');
        content = `<div style="font-size:22px;font-weight:800;margin-bottom:20px;">${sTitle}</div>
          <div style="width:100%;height:2px;background:#1a1a1a;margin-bottom:20px;"></div>
          <div style="display:grid;grid-template-columns:1fr 1fr;gap:12px;">${cards}</div>${actionLine}`;
      } else if (layout === 'comparison' && s.comparison) {
        const left = (s.comparison.left?.items||[]).map((i: string) => `<div style="font-size:13px;color:#444;padding:4px 0;">${i}</div>`).join('');
        const right = (s.comparison.right?.items||[]).map((i: string) => `<div style="font-size:13px;color:#444;padding:4px 0;">${i}</div>`).join('');
        content = `<div style="font-size:22px;font-weight:800;margin-bottom:20px;">${sTitle}</div>
          <div style="width:100%;height:2px;background:#1a1a1a;margin-bottom:20px;"></div>
          <div style="display:flex;gap:16px;">
            <div style="flex:1;border:2px solid #e0e0d8;padding:16px;"><div style="font-size:14px;font-weight:900;margin-bottom:12px;padding-bottom:8px;border-bottom:2px solid #D24726;">${s.comparison.left?.title||'A'}</div>${left}</div>
            <div style="display:flex;align-items:center;font-size:20px;color:#ccc;font-weight:900;">vs</div>
            <div style="flex:1;border:2px solid #e0e0d8;padding:16px;"><div style="font-size:14px;font-weight:900;margin-bottom:12px;padding-bottom:8px;border-bottom:2px solid #00873c;">${s.comparison.right?.title||'B'}</div>${right}</div>
          </div>${actionLine}`;
      } else {
        content = `<div style="font-size:22px;font-weight:800;margin-bottom:20px;">${sTitle}</div>
          <div style="width:100%;height:2px;background:#1a1a1a;margin-bottom:20px;"></div>${bullets}${actionLine}`;
      }

      slidesHTML += `<div class="slide" style="page-break-after:always;padding:40px 50px;min-height:${layout==='cover'?'100vh':'auto'};">
        ${layout !== 'cover' ? `<div style="font-size:9px;font-weight:700;text-transform:uppercase;letter-spacing:0.15em;color:#888;margin-bottom:16px;display:flex;justify-content:space-between;"><span>${topic}</span><span>${i+1} / ${slidesData.length}</span></div>` : ''}
        ${content}
      </div>`;
    }

    const html = `<!DOCTYPE html><html><head><meta charset="utf-8"><title>${title}</title>
<script src="https://cdn.jsdelivr.net/npm/echarts@5/dist/echarts.min.js"><\/script>
<style>*{margin:0;padding:0;box-sizing:border-box;}body{font-family:'Helvetica Neue',Arial,sans-serif;background:#fff;}
.slide{border-bottom:1px solid #eee;} @media print{.slide{page-break-after:always;border:none;} .no-print{display:none!important;}}</style>
</head><body>
<div class="no-print" style="position:fixed;top:0;left:0;right:0;background:#1a1a1a;color:#fff;padding:8px 20px;display:flex;justify-content:space-between;align-items:center;z-index:100;">
  <span style="font-size:12px;font-weight:700;">${title}</span>
  <button onclick="window.print()" style="font-size:10px;padding:4px 12px;background:none;border:1px solid #555;color:#fff;cursor:pointer;">PRINT / SAVE AS PDF</button>
</div>
<div style="padding-top:40px;">${slidesHTML}</div>
</body></html>`;

    const blob = new Blob([html], { type: 'text/html' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `${agentName}-slides.html`;
    a.click();
    URL.revokeObjectURL(url);
  }

  $effect(() => {
    const slide = slidesData[currentSlide];
    if (slide?.chart) {
      setTimeout(() => {
        const el = document.getElementById(`slide-chart-${currentSlide}`);
        if (!el) return;
        const existing = echarts.getInstanceByDom(el);
        if (existing) existing.dispose();
        const chart = echarts.init(el);
        const type = slide.chart.type === 'horizontal_bar' ? 'bar' : (slide.chart.type || 'bar');
        const isHorizontal = slide.chart.type === 'horizontal_bar';
        const option: any = {
          tooltip: { trigger: 'axis' },
          title: { text: slide.chart.title || '', left: 'center', textStyle: { fontSize: 12, fontWeight: 700 } },
          xAxis: isHorizontal
            ? { type: 'value', axisLabel: { fontSize: 10 } }
            : { type: 'category', data: slide.chart.labels || [], axisLabel: { fontSize: 10, rotate: (slide.chart.labels?.length || 0) > 5 ? 25 : 0 } },
          yAxis: isHorizontal
            ? { type: 'category', data: slide.chart.labels || [], axisLabel: { fontSize: 10 } }
            : { type: 'value', axisLabel: { fontSize: 10 } },
          series: [{ type: 'bar', data: slide.chart.values || [], itemStyle: { color: '#D24726', borderRadius: [4,4,0,0] }, smooth: type === 'line', areaStyle: type === 'line' ? { opacity: 0.08 } : undefined }],
          grid: { left: isHorizontal ? '25%' : '10%', right: '5%', bottom: '12%', top: '15%' }
        };
        if (type === 'line') {
          option.series[0].type = 'line';
        }
        if (type === 'pie') {
          delete option.xAxis; delete option.yAxis; delete option.grid;
          option.series = [{ type: 'pie', radius: ['35%','60%'], data: (slide.chart.labels||[]).map((l:string,i:number) => ({name:l, value:(slide.chart.values||[])[i]})), label: { fontSize: 10 }, itemStyle: { borderRadius: 4, borderColor: '#fff', borderWidth: 2 } }];
          option.tooltip = { trigger: 'item', formatter: '{b}: {c} ({d}%)' };
        }
        chart.setOption(option);
      }, 200);
    }
  });

  function stopStreaming() {
    if (abortController) {
      abortController.abort();
      abortController = null;
    }
    isStreaming = false;
    const last = messages[messages.length - 1];
    if (last?.role === 'assistant') {
      messages = [...messages.slice(0, -1), { ...last, status: 'done', timestamp: getTimestamp() }];
    }
    textareaEl?.focus();
  }

  function selectMode(mode: string) {
    selectedMode = mode;
    dropdownOpen = false;
    textareaEl?.focus();
  }

  // Close dropdown on click outside
  function handleWindowClick(e: MouseEvent) {
    const target = e.target as HTMLElement;
    if (!target.closest('.mode-selector')) {
      dropdownOpen = false;
      workflowPickerOpen = false;
      reasoningDropdownOpen = false;
      analysisDropdownOpen = false;
    }
  }
</script>

<svelte:window onclick={handleWindowClick} />

<div class="flex h-full">
  <!-- Sidebar -->
  {#if sidebarOpen}
    <div class="chat-sidebar">
      <div class="flex items-center justify-between p-3" style="border-bottom: 2px solid var(--color-on-surface);">
        <span style="font-size: 11px; font-weight: 900; text-transform: uppercase; letter-spacing: 0.08em;">CHAT HISTORY</span>
        <button onclick={toggleSidebar} style="background: none; border: none; cursor: pointer; font-size: 16px; font-weight: 900; color: var(--color-on-surface); font-family: var(--font-family-display);" title="Hide sidebar">&laquo;</button>
      </div>
      <div style="padding: 8px;">
        <button class="sidebar-new-btn" onclick={() => { newChat(); }}>+ NEW CHAT</button>
      </div>
      <div class="sidebar-sessions">
        {#each pastSessions as s, si}
          <button class="sidebar-session" class:sidebar-session-active={s.session_id === sessionId} onclick={() => switchSession(s.session_id)}>
            <div style="font-size: 11px; font-weight: {s.session_id === sessionId ? 900 : 400}; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">
              {s.first_message || `Chat ${pastSessions.length - si}`}
            </div>
            <div class="flex items-center gap-2" style="font-size: 9px; color: var(--color-on-surface-dim);">
              {#if s.agent_name}
                <span style="font-weight: 700;">{s.agent_name}</span>
                <span>&middot;</span>
              {/if}
              <span>{formatSessionTime(s.updated_at || s.created_at)}</span>
            </div>
          </button>
        {/each}
        {#if pastSessions.length === 0}
          <div style="padding: 12px; font-size: 11px; color: var(--color-on-surface-dim); text-align: center;">No sessions yet</div>
        {/if}
      </div>
    </div>
  {/if}

  <!-- Main chat -->
  <div class="flex flex-col" style="flex: 1; min-width: 0;">

  {#if !sidebarOpen}
    <button onclick={toggleSidebar} class="sidebar-toggle-btn" title="Show chat history">&raquo;</button>
  {/if}

  <div class="flex-1 overflow-y-auto" bind:this={messagesEl} style="padding: 20px 20px 16px 20px;">
    <div style="max-width: 820px; margin: 0 auto;">

      {#if sessionStartTime}
        <div class="flex justify-center mb-6 animate-fade-up">
          <div class="tag-label" style="font-size: 10px; padding: 4px 14px; letter-spacing: 0.12em;">
            DASH AGENT &middot; {sessionStartTime}
          </div>
        </div>
      {/if}

      {#if messages.length === 0}
        <div class="flex flex-col items-center animate-fade-up" style="padding-top: 60px;">
          <div style="text-align: center; margin-bottom: 40px;">
            <div style="font-size: 42px; font-weight: 900; letter-spacing: -0.02em; color: var(--color-on-surface); line-height: 1;">DASH AGENT</div>
            <div style="font-size: 11px; letter-spacing: 0.15em; color: var(--color-on-surface-dim); margin-top: 10px; text-transform: uppercase;">
              Ask anything across all your agents
            </div>
            {#if selectedMode === 'auto'}
              <div style="font-size: 10px; color: var(--color-secondary); margin-top: 6px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.1em;">
                Powered by Reinforcement Learning &middot; {projects.length} agent{projects.length !== 1 ? 's' : ''} available
              </div>
            {:else}
              {@const pinned = projects.find(p => p.slug === selectedMode)}
              <div style="font-size: 10px; color: var(--color-primary); margin-top: 6px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.1em;">
                Pinned to: {pinned?.agent_name || selectedMode}
              </div>
            {/if}
          </div>
          <div class="flex flex-wrap justify-center gap-2" style="max-width: 650px;">
            {#each projects.slice(0, 6) as proj}
              <button class="prompt-card" onclick={() => { selectedMode = proj.slug; send(`What data do you have? Give me a quick overview.`); }} disabled={isStreaming}>
                Ask {proj.agent_name}: "What data do you have?"
              </button>
            {/each}
            {#if projects.length === 0}
              <div style="font-size: 12px; color: var(--color-on-surface-dim); text-transform: uppercase;">No projects yet. Create one in Projects.</div>
            {/if}
          </div>
        </div>
      {:else}
        <div class="flex flex-col gap-5">
          {#each messages as msg, i}
            {#if msg.role === 'user'}
              <div class="animate-fade-up">
                <div class="flex items-start justify-end gap-3">
                  <div class="bubble-user">{msg.content}</div>
                  <div class="avatar-user">
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/></svg>
                  </div>
                </div>
                <div style="text-align: right; font-size: 10px; color: var(--color-on-surface-dim); margin-top: 4px; padding-right: 40px; letter-spacing: 0.05em; text-transform: uppercase;">
                  {msg.timestamp} &middot; READ
                </div>
              </div>
            {:else}
              <div class="animate-fade-up">
                <div class="flex items-start gap-3">
                  <div class="avatar-agent">
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="11" width="18" height="10" rx="0"/><path d="M12 2v4"/><circle cx="12" cy="7" r="1"/><path d="M7 15h0M17 15h0M9 18h6"/></svg>
                  </div>
                  <div style="flex: 1; min-width: 0;">
                    <!-- CLI Terminal: always shown for assistant messages -->
                    {#if msg.status === 'done' && !msg.workflowExpanded && msg.toolCalls && msg.toolCalls.length > 0}
                      <!-- Collapsed CLI bar (has tools, click to expand) -->
                      <button class="cli-terminal" style="cursor: pointer; width: 100%; text-align: left;" onclick={() => toggleWorkflow(i)}>
                        <div class="cli-line">
                          <span class="cli-prompt">$</span>
                          <span class="cli-command">dash route</span>
                          <span class="cli-output">--agent {msg.routing?.routed_to || 'agent'}</span>
                          <span class="cli-success" style="margin-left: auto;">&#10003; {msg.toolCalls.length} steps {getTotalDuration(msg.toolCalls) ? '· ' + getTotalDuration(msg.toolCalls) : ''}{msg.qualityScore ? ' · ' + renderStars(msg.qualityScore) : ''}</span>
                        </div>
                      </button>
                    {:else if msg.status === 'done' && (!msg.toolCalls || msg.toolCalls.length === 0)}
                      <!-- No tools used — show minimal CLI with routing -->
                      <div class="cli-terminal">
                        <div class="cli-line">
                          <span class="cli-prompt">$</span>
                          <span class="cli-command">dash route</span>
                          <span class="cli-output">--mode {selectedMode === 'auto' ? 'auto' : 'pinned'}</span>
                        </div>
                        {#if msg.routing}
                          <div class="cli-line">
                            <span class="cli-info">&gt;</span>
                            <span class="cli-info">matched: {msg.routing.routed_to}</span>
                            <span class="cli-dim">({msg.routing.reason})</span>
                          </div>
                        {/if}
                        <div class="cli-line">
                          <span class="cli-prompt">$</span>
                          <span class="cli-success">done</span>
                          <span class="cli-dim">· direct response</span>
                        </div>
                      </div>
                    {:else}
                      <!-- Expanded / streaming CLI terminal -->
                      <div class="cli-terminal" onclick={() => msg.status === 'done' && toggleWorkflow(i)} style="{msg.status === 'done' ? 'cursor: pointer;' : ''}">
                        <!-- Route command -->
                        <div class="cli-line">
                          <span class="cli-prompt">$</span>
                          <span class="cli-command">dash route</span>
                          <span class="cli-output">--mode {selectedMode === 'auto' ? 'auto' : 'pinned'}</span>
                        </div>

                        {#if msg.routing}
                          <div class="cli-line">
                            <span class="cli-info">&gt;</span>
                            <span class="cli-info">matched: {msg.routing.routed_to}</span>
                            <span class="cli-dim">({msg.routing.reason})</span>
                          </div>
                        {:else if msg.status === 'streaming'}
                          <div class="cli-line">
                            <span class="cli-info">&gt;</span>
                            <span class="cli-output">scanning agents</span>
                            <span class="cli-spinner"><span></span><span></span><span></span></span>
                          </div>
                        {/if}

                        <!-- Tool calls -->
                        {#if msg.toolCalls && msg.toolCalls.length > 0}
                          <div class="cli-line" style="margin-top: 4px;">
                            <span class="cli-prompt">$</span>
                            <span class="cli-command">dash exec</span>
                          </div>
                          {#each msg.toolCalls as tool}
                            <div class="cli-line">
                              <span style="color: #555;">&gt;</span>
                              {#if tool.status === 'done'}
                                <span class="cli-check">&#10003;</span>
                              {:else}
                                <span class="cli-spinner"><span></span><span></span><span></span></span>
                              {/if}
                              <span class="cli-command">{tool.name}</span>
                              {#if tool.duration}
                                <span class="cli-duration">{tool.duration}</span>
                              {/if}
                            </div>
                          {/each}
                        {:else if msg.status === 'streaming' && !msg.routing}
                          <div class="cli-line">
                            <span style="color: #555;">&gt;</span>
                            <span class="cli-output">connecting</span>
                            <span class="cli-spinner"><span></span><span></span><span></span></span>
                          </div>
                        {/if}

                        <!-- Done / cursor -->
                        {#if msg.status === 'done'}
                          <div class="cli-line" style="margin-top: 4px;">
                            <span class="cli-prompt">$</span>
                            <span class="cli-success">done</span>
                            <span class="cli-dim">· {msg.toolCalls && msg.toolCalls.length > 0 ? msg.toolCalls.length + ' steps' : 'direct response'} {getTotalDuration(msg.toolCalls || []) ? '· ' + getTotalDuration(msg.toolCalls || []) : ''}</span>
                          </div>
                        {:else if msg.status === 'streaming'}
                          <div class="cli-line" style="margin-top: 2px;">
                            <span class="cli-cursor"></span>
                          </div>
                        {/if}
                      </div>
                    {/if}

                    <!-- Response Tabs: Analysis / Data / Query / Graph -->
                    {#if msg.status === 'done' && msg.content}
                      {@const tables = parseMarkdownTables(msg.content)}
                      {@const hasTables = tables.length > 0 && tables[0].headers?.length > 0}
                      {@const hasChartData = hasTables && hasNumericData(tables[0])}
                      {@const hasQueries = msg.sqlQueries && msg.sqlQueries.length > 0}
                      {@const totalTableRows = tables.reduce((sum: number, t: any) => sum + (t.rows?.length || 0), 0)}
                      {@const currentTab = msg.activeTab || 'analysis'}

                      <div class="response-tabs">
                        <button class="response-tab" class:response-tab-active={currentTab === 'analysis'} onclick={() => { messages = [...messages.slice(0, i), { ...msg, activeTab: 'analysis' }, ...messages.slice(i + 1)]; }}>Analysis</button>
                        <button class="response-tab" class:response-tab-active={currentTab === 'data'} class:response-tab-dim={!hasTables} onclick={() => { if (hasTables) messages = [...messages.slice(0, i), { ...msg, activeTab: 'data' }, ...messages.slice(i + 1)]; }}>Data{#if hasTables}<span class="tab-badge">{totalTableRows}</span>{/if}</button>
                        <button class="response-tab" class:response-tab-active={currentTab === 'query'} class:response-tab-dim={!hasQueries} onclick={() => { if (hasQueries) messages = [...messages.slice(0, i), { ...msg, activeTab: 'query' }, ...messages.slice(i + 1)]; }}>Query{#if hasQueries}<span class="tab-badge">{msg.sqlQueries?.length}</span>{/if}</button>
                        <button class="response-tab" class:response-tab-active={currentTab === 'chart'} class:response-tab-dim={!hasChartData} onclick={() => { if (hasChartData) messages = [...messages.slice(0, i), { ...msg, activeTab: 'chart', chartType: msg.chartType || detectChartType(tables[0]) }, ...messages.slice(i + 1)]; }}>Chart</button>
                        <button class="response-tab" class:response-tab-active={currentTab === 'sources'} onclick={() => { messages = [...messages.slice(0, i), { ...msg, activeTab: 'sources' }, ...messages.slice(i + 1)]; }}>Sources</button>
                      </div>

                      {#if currentTab === 'analysis'}
                        {@const insightAnalysisMatch = msg.content.match(/\[ANALYSIS:([^\]]+)\]/)}
                        {@const insightAnalysisTypes = insightAnalysisMatch ? insightAnalysisMatch[1].split(',').map((t: string) => t.trim()) : []}
                        {@const modeMatch = msg.content.match(/\[MODE:(\w+)\]/)}
                        {@const actualMode = modeMatch ? modeMatch[1] : 'auto'}
                        {@const analysisContent = msg.content
                          .replace(/\[ANALYSIS:[^\]]+\]/g, '')
                          .replace(/\[MODE:\w+\]/g, '')
                          .replace(/\[CHART:[^\]]+\]/g, '')
                          .replace(/\[CHART_CONFIG:[^\]]+\]/g, '')
                          .replace(/\[DASHBOARD:\d+\]/g, '')
                          .replace(/\[CLARIFY:[^\]]+\]/g, '')
                          .replace(/\[KPI:[^\]]+\]/g, '')
                          .replace(/\[CONFIDENCE:[^\]]+\]/g, '')
                          .replace(/\[IMPACT:[^\]]+\]/g, '')
                          .replace(/\[RELATED:[^\]]+\]/g, '')
                          .replace(/---\s*\n\s*SOURCES:[\s\S]*$/, '')
                          .replace(/```sql[\s\S]*?```/g, '')
                          .trim()}
                        <div class="bubble-assistant">
                          <div style="margin-bottom: 10px; display: flex; gap: 4px; flex-wrap: wrap;">
                            <span style="font-size: 8px; font-weight: 900; padding: 2px 8px; background: {actualMode === 'fast' ? '#00fc40' : actualMode === 'deep' ? '#007518' : '#383832'}; color: {actualMode === 'fast' ? '#383832' : 'white'}; text-transform: uppercase; letter-spacing: 0.06em;">{actualMode}</span>
                          {#if insightAnalysisTypes.length > 0}
                              {#each insightAnalysisTypes as atype}
                                <span style="font-size: 8px; font-weight: 900; padding: 2px 8px; background: var(--color-secondary); color: white; text-transform: uppercase;">{atype}</span>
                              {/each}
                          {/if}
                          </div>
                          <!-- KPI Metric Cards -->
                          {#if msg.content}
                            {@const kpiMatches = msg.content.match(/\[KPI:([^\]]+)\]/g) || []}
                            {#if kpiMatches.length > 0}
                              <div style="display: flex; gap: 10px; margin-bottom: 14px; flex-wrap: wrap;">
                                {#each kpiMatches as kpi}
                                  {@const parts = kpi.replace('[KPI:', '').replace(']', '').split('|')}
                                  <div style="flex: 1; min-width: 100px; max-width: 160px; border: 2px solid var(--color-on-surface); padding: 10px; text-align: center; background: var(--color-surface-bright);">
                                    <div style="font-size: 22px; font-weight: 900; color: var(--color-on-surface);">{parts[0]}</div>
                                    <div style="font-size: 9px; text-transform: uppercase; color: var(--color-on-surface-dim); font-weight: 700; margin-top: 2px;">{parts[1] || ''}</div>
                                    {#if parts[2]}
                                      <div style="font-size: 10px; margin-top: 4px; color: {parts[2]?.includes('-') ? '#e74c3c' : parts[2]?.includes('+') ? '#00fc40' : '#ff9d00'}; font-weight: 700;">{parts[2]}</div>
                                    {/if}
                                  </div>
                                {/each}
                              </div>
                            {/if}
                          {/if}
                          <!-- Confidence Bar -->
                          {#if msg.content}
                            {@const confMatch2 = msg.content.match(/\[CONFIDENCE:(\w+(?:\s+\w+)?)\]/)}
                            {#if confMatch2}
                              {@const confLevel = confMatch2[1]}
                              {@const confWidth = confLevel === 'VERY HIGH' ? 100 : confLevel === 'HIGH' ? 80 : confLevel === 'MEDIUM' ? 50 : 30}
                              <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 8px;">
                                <span style="font-size: 8px; font-weight: 700; text-transform: uppercase; color: var(--color-on-surface-dim);">CONFIDENCE</span>
                                <div style="flex: 1; max-width: 120px; height: 6px; background: var(--color-surface-dim); border: 1px solid #555;">
                                  <div style="width: {confWidth}%; height: 100%; background: {confWidth >= 80 ? '#00fc40' : confWidth >= 50 ? '#ff9d00' : '#e74c3c'};"></div>
                                </div>
                                <span style="font-size: 8px; font-weight: 700; color: {confWidth >= 80 ? '#00fc40' : confWidth >= 50 ? '#ff9d00' : '#e74c3c'};">{confLevel}</span>
                              </div>
                            {/if}
                          {/if}
                          <div class="prose-chat">
                            {@html markdownToHtml(analysisContent)
                              .replace(/\[UP:([^\]]+)\]/g, '<span style="color: #007518; font-weight: 900;">&#9650; $1</span>')
                              .replace(/\[DOWN:([^\]]+)\]/g, '<span style="color: #be2d06; font-weight: 900;">&#9660; $1</span>')
                              .replace(/\[FLAT:([^\]]+)\]/g, '<span style="color: #ff9d00; font-weight: 900;">&#9679; $1</span>')
                              .replace(/\[RISK:HIGH\]/g, '<span style="font-size:8px;font-weight:900;padding:1px 6px;background:#be2d06;color:white;">&#9888; HIGH</span>')
                              .replace(/\[RISK:MEDIUM\]/g, '<span style="font-size:8px;font-weight:900;padding:1px 6px;background:#ff9d00;color:#383832;">&#9888; MEDIUM</span>')
                              .replace(/\[RISK:LOW\]/g, '<span style="font-size:8px;font-weight:900;padding:1px 6px;background:#007518;color:white;">&#10003; LOW</span>')
                            }
                          </div>

                          <!-- Inline Charts -->
                          {#if hasTables && tables.length > 0}
                            {@const chartHint = parseChartHint(msg.content)}
                            {@const inlineCharts = tables.filter((t: any) => hasNumericData(t)).slice(0, 3)}
                            {#if inlineCharts.length > 0}
                              <div style="margin-top: 14px; display: flex; flex-direction: column; gap: 10px;">
                                {#each inlineCharts as tbl, ci}
                                  <div style="border: 2px solid var(--color-on-surface); background: var(--color-surface-bright);">
                                    <div style="padding: 6px 12px; background: var(--color-on-surface); color: var(--color-surface); font-size: 9px; font-weight: 900; text-transform: uppercase; letter-spacing: 0.08em; display: flex; justify-content: space-between; align-items: center;">
                                      <span>{chartHint?.title || tbl.headers.slice(0, 3).join(' vs ')}</span>
                                      <span style="color: #00fc40; font-size: 8px;">{tbl.rows.length} ROWS</span>
                                    </div>
                                    <div style="padding: 8px;">
                                      <EChartView headers={tbl.headers} rows={tbl.rows} chartType={chartHint?.type || detectChartType(tbl)} />
                                    </div>
                                    {#if generateChartCaption(tbl)}
                                      <div style="padding: 6px 12px; font-size: 11px; color: var(--color-on-surface-dim); border-top: 1px solid #e5e5e0; line-height: 1.5;">
                                        {generateChartCaption(tbl)}
                                      </div>
                                    {/if}
                                  </div>
                                {/each}
                              </div>
                            {/if}
                          {/if}

                          <!-- Impact Summary -->
                          {#if msg.content}
                            {@const impactMatch = msg.content.match(/\[IMPACT:([^\]]+)\]/)}
                            {#if impactMatch}
                              {@const impParts = impactMatch[1].split('|')}
                              <div class="ink-border" style="padding: 12px 16px; margin-top: 12px; background: var(--color-surface-bright);">
                                <div style="font-size: 9px; font-weight: 900; text-transform: uppercase; color: var(--color-on-surface-dim); margin-bottom: 6px;">IMPACT SUMMARY</div>
                                <div style="font-size: 12px; color: var(--color-on-surface); margin-bottom: 8px;">
                                  If addressed: could recover <strong style="color: #007518; font-size: 14px;">{impParts[1] || '?'}</strong> out of <strong>{impParts[2] || '?'}</strong> <span style="color: var(--color-on-surface-dim);">({impParts[0] || '?'})</span>
                                </div>
                                <div style="height: 10px; background: var(--color-surface-dim); border: 2px solid var(--color-on-surface);">
                                  <div style="width: {parseInt(impParts[0]) || 0}%; height: 100%; background: #00fc40;"></div>
                                </div>
                              </div>
                            {/if}
                          {/if}

                          <!-- Clarifying Questions -->
                          {#if parseClarify(msg.content)}
                            <div class="flex flex-wrap gap-2 mt-3" style="padding-top: 8px; border-top: 1px dashed var(--color-on-surface);">
                              <span style="font-size: 9px; font-weight: 900; text-transform: uppercase; color: var(--color-on-surface-dim); width: 100%;">DID YOU MEAN:</span>
                              {#each parseClarify(msg.content) || [] as option}
                                <button class="suggestion-btn" onclick={() => send(option)} disabled={isStreaming}>{option}</button>
                              {/each}
                            </div>
                          {/if}

                          <!-- Related Questions -->
                          {#if msg.content}
                            {@const relatedMatches = msg.content.match(/\[RELATED:([^\]]+)\]/g) || []}
                            {#if relatedMatches.length > 0}
                              <div style="margin-top: 12px; padding-top: 10px; border-top: 1px dashed var(--color-surface-dim);">
                                <div style="font-size: 9px; font-weight: 900; text-transform: uppercase; color: var(--color-on-surface-dim); margin-bottom: 6px;">RELATED QUESTIONS</div>
                                <div style="display: flex; flex-wrap: wrap; gap: 6px;">
                                  {#each relatedMatches as rq}
                                    <button class="suggestion-btn" onclick={() => send(rq.replace('[RELATED:', '').replace(']', ''))} disabled={isStreaming}>
                                      {rq.replace('[RELATED:', '').replace(']', '')}
                                    </button>
                                  {/each}
                                </div>
                              </div>
                            {/if}
                          {/if}

                          <!-- Feedback bar -->
                          <div class="flex items-center justify-between" style="margin-top: 12px; padding-top: 10px; border-top: 1px solid var(--color-on-surface); opacity: 0.6;">
                            <div class="flex items-center gap-2" style="font-size: 10px; text-transform: uppercase; letter-spacing: 0.1em; font-weight: 700;">
                              HELPFUL?
                              <button class="feedback-btn" title="Helpful" onclick={async () => {
                                const rSlug = msg.routing?.slug || (selectedMode !== 'auto' ? selectedMode : projects[0]?.slug);
                                if (!rSlug) return;
                                const q = i > 0 ? messages[i-1]?.content : '';
                                await fetch(`/api/projects/${rSlug}/feedback`, { method: 'POST', headers: { ..._headers(), 'Content-Type': 'application/json' }, body: JSON.stringify({ question: q, answer: msg.content, rating: 'up' }) });
                                if (msg.sqlQueries?.length) { for (const sql of msg.sqlQueries) { await fetch(`/api/projects/${rSlug}/save-query-pattern`, { method: 'POST', headers: { ..._headers(), 'Content-Type': 'application/json' }, body: JSON.stringify({ question: q, sql }) }); } }
                              }}><svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M14 9V5a3 3 0 0 0-3-3l-4 9v11h11.28a2 2 0 0 0 2-1.7l1.38-9a2 2 0 0 0-2-2.3zM7 22H4a2 2 0 0 1-2-2v-7a2 2 0 0 1 2-2h3"/></svg></button>
                              <button class="feedback-btn" title="Not helpful" onclick={async () => {
                                const rSlug = msg.routing?.slug || (selectedMode !== 'auto' ? selectedMode : projects[0]?.slug);
                                if (!rSlug) return;
                                const q = i > 0 ? messages[i-1]?.content : '';
                                await fetch(`/api/projects/${rSlug}/feedback`, { method: 'POST', headers: { ..._headers(), 'Content-Type': 'application/json' }, body: JSON.stringify({ question: q, answer: msg.content, rating: 'down' }) });
                              }}><svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M10 15v4a3 3 0 0 0 3 3l4-9V2H5.72a2 2 0 0 0-2 1.7l-1.38 9a2 2 0 0 0 2 2.3zm7-13h2.67A2.31 2.31 0 0 1 22 4v7a2.31 2.31 0 0 1-2.33 2H17"/></svg></button>
                            </div>
                            <div class="flex items-center gap-2">
                              <button class="feedback-btn flex items-center gap-1" onclick={() => copyMessage(i)} style="font-size: 10px; text-transform: uppercase; letter-spacing: 0.1em; font-weight: 700;">
                                <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="9" y="9" width="13" height="13" rx="0"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/></svg>
                                {copiedIndex === i ? 'COPIED' : 'COPY'}
                              </button>
                              {#if hasTables}
                                <button class="feedback-btn flex items-center gap-1" onclick={() => {
                                  const csv = tableToCsv(tables[0]);
                                  const blob = new Blob([csv], { type: 'text/csv' });
                                  const url = URL.createObjectURL(blob); const a = document.createElement('a'); a.href = url; a.download = `dash-export-${Date.now()}.csv`; a.click(); URL.revokeObjectURL(url);
                                }} style="font-size: 10px; text-transform: uppercase; letter-spacing: 0.1em; font-weight: 700;">CSV</button>
                              {/if}
                              <button class="feedback-btn flex items-center gap-1" onclick={() => {
                                const fact = prompt('Save a fact the agent should remember:', '');
                                const slug = msg.routing?.slug || (selectedMode !== 'auto' ? selectedMode : projects[0]?.slug);
                                if (fact && slug) { fetch(`/api/projects/${slug}/memories`, { method: 'POST', headers: { ..._headers(), 'Content-Type': 'application/json' }, body: JSON.stringify({ fact, scope: 'project' }) }); }
                              }} style="font-size: 10px; text-transform: uppercase; letter-spacing: 0.1em; font-weight: 700;">
                                <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 2v10M12 12l4-4M12 12l-4-4M5 17h14M5 21h14"/></svg>
                                SAVE
                              </button>
                              <button class="feedback-btn flex items-center gap-1" onclick={() => {
                                const slug = msg.routing?.slug || (selectedMode !== 'auto' ? selectedMode : '');
                                if (slug) openPinModal(i, tables, msg.content, slug);
                              }} disabled={!msg.routing?.slug && selectedMode === 'auto'} style="font-size: 10px; text-transform: uppercase; letter-spacing: 0.1em; font-weight: 700; {(!msg.routing?.slug && selectedMode === 'auto') ? 'opacity: 0.4;' : ''}">PIN</button>
                              <button class="feedback-btn flex items-center gap-1" onclick={async () => {
                                try {
                                  const res = await fetch('/api/export/pdf', { method: 'POST', headers: { ..._headers(), 'Content-Type': 'application/json' }, body: JSON.stringify({ content: msg.content, title: 'Dash Agent Report' }) });
                                  if (res.ok) { const blob = await res.blob(); const url = URL.createObjectURL(blob); const a = document.createElement('a'); a.href = url; a.download = `dash-report-${Date.now()}.pdf`; a.click(); URL.revokeObjectURL(url); }
                                } catch {}
                              }} style="font-size: 10px; text-transform: uppercase; letter-spacing: 0.1em; font-weight: 700;">PDF</button>
                            </div>
                          </div>
                        </div>

                      <!-- TAB: Data (multi-table with sub-tabs) -->
                      {:else if currentTab === 'data' && hasTables}
                        {@const dataIdx = msg.dataTableIndex || 0}
                        {@const activeTable = tables[dataIdx] || tables[0]}
                        <div class="bubble-assistant">
                          {#if tables.length > 1}
                            <div style="display: flex; gap: 4px; margin-bottom: 10px; flex-wrap: wrap;">
                              {#each tables as _t, ti}
                                <button
                                  style="font-size: 9px; font-weight: 900; padding: 3px 10px; text-transform: uppercase; letter-spacing: 0.05em; border: 2px solid {dataIdx === ti ? 'var(--color-on-surface)' : 'var(--color-on-surface-dim)'}; background: {dataIdx === ti ? 'var(--color-on-surface)' : 'transparent'}; color: {dataIdx === ti ? 'var(--color-surface)' : 'var(--color-on-surface-dim)'}; cursor: pointer;"
                                  onclick={() => { messages = [...messages.slice(0, i), { ...msg, dataTableIndex: ti }, ...messages.slice(i + 1)]; }}
                                >Table {ti + 1}</button>
                              {/each}
                            </div>
                          {/if}
                          <div style="font-size: 10px; font-weight: 900; text-transform: uppercase; letter-spacing: 0.1em; margin-bottom: 8px; color: var(--color-on-surface-dim);">
                            {activeTable.rows.length} ROWS &middot; {activeTable.headers.length} COLUMNS{#if tables.length > 1} &middot; TABLE {dataIdx + 1} OF {tables.length}{/if}
                          </div>
                          <div style="overflow-x: auto;">
                            <table class="data-table">
                              <thead>
                                <tr>
                                  <th style="width: 36px; text-align: center; color: var(--color-on-surface-dim);">#</th>
                                  {#each activeTable.headers as h}
                                    <th>{h.replace(/\*\*/g, '')}</th>
                                  {/each}
                                </tr>
                              </thead>
                              <tbody>
                                {#each activeTable.rows as row, ri}
                                  <tr>
                                    <td style="text-align: center; color: var(--color-on-surface-dim); font-size: 10px;">{ri + 1}</td>
                                    {#each row as cell}
                                      <td>{@html formatCell(cell)}</td>
                                    {/each}
                                  </tr>
                                {/each}
                              </tbody>
                            </table>
                          </div>
                          <div class="flex gap-2 mt-3">
                            <button class="feedback-btn" onclick={() => {
                              const csv = tableToCsv(activeTable);
                              const blob = new Blob([csv], { type: 'text/csv' });
                              const url = URL.createObjectURL(blob); const a = document.createElement('a'); a.href = url; a.download = `dash-export-table${dataIdx + 1}-${Date.now()}.csv`; a.click(); URL.revokeObjectURL(url);
                            }} style="font-size: 10px; font-weight: 700; text-transform: uppercase; padding: 4px 10px;">DOWNLOAD CSV</button>
                            <button class="feedback-btn flex items-center gap-1" onclick={() => {
                              const slug = msg.routing?.slug || (selectedMode !== 'auto' ? selectedMode : '');
                              if (slug) openPinModal(i, tables, msg.content, slug);
                            }} style="font-size: 10px; font-weight: 700; text-transform: uppercase; padding: 4px 10px;">PIN TO DASHBOARD</button>
                          </div>
                        </div>

                      <!-- TAB: Query (separate cards) -->
                      {:else if currentTab === 'query' && hasQueries}
                        <div style="display: flex; flex-direction: column; gap: 10px;">
                          {#each msg.sqlQueries || [] as sql, si}
                            <div class="ink-border" style="background: #1a1a1a; padding: 14px; border-color: #333;">
                              <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px;">
                                <span style="font-size: 10px; font-weight: 900; text-transform: uppercase; letter-spacing: 0.1em; color: #00fc40;">Query {si + 1}</span>
                                <button class="feedback-btn" onclick={() => { navigator.clipboard.writeText(sql); }} style="font-size: 9px; font-weight: 700; text-transform: uppercase; padding: 3px 8px; color: #00fc40; border: 1px solid #333;">COPY</button>
                              </div>
                              <pre style="margin: 0; font-family: 'Space Grotesk', monospace; font-size: 12px; color: #e0e0e0; white-space: pre-wrap; word-break: break-all; line-height: 1.5; background: #111; padding: 10px; border: 1px solid #282828;"><code>{sql}</code></pre>
                            </div>
                          {/each}
                        </div>

                      <!-- TAB: Chart (multi-chart with sub-tabs) -->
                      {:else if currentTab === 'chart' && hasChartData}
                        {@const chartHint2 = parseChartHint(msg.content)}
                        {@const chartTables = tables.filter((t: any) => hasNumericData(t))}
                        {@const chartIdx = msg.dataTableIndex || 0}
                        {@const activeChartTable = chartTables[chartIdx] || chartTables[0]}
                        <div class="bubble-assistant" style="padding: 12px;">
                          {#if chartTables.length > 1}
                            <div style="display: flex; gap: 4px; margin-bottom: 10px; flex-wrap: wrap;">
                              {#each chartTables as _ct, ci}
                                <button
                                  style="font-size: 9px; font-weight: 900; padding: 3px 10px; text-transform: uppercase; letter-spacing: 0.05em; border: 2px solid {chartIdx === ci ? 'var(--color-on-surface)' : 'var(--color-on-surface-dim)'}; background: {chartIdx === ci ? 'var(--color-on-surface)' : 'transparent'}; color: {chartIdx === ci ? 'var(--color-surface)' : 'var(--color-on-surface-dim)'}; cursor: pointer;"
                                  onclick={() => { messages = [...messages.slice(0, i), { ...msg, dataTableIndex: ci, chartType: undefined }, ...messages.slice(i + 1)]; }}
                                >Chart {ci + 1}</button>
                              {/each}
                            </div>
                          {/if}
                          {#if chartHint2?.title}
                            <div style="font-size: 12px; font-weight: 900; text-transform: uppercase; letter-spacing: 0.05em; margin-bottom: 8px; color: var(--color-on-surface);">{chartHint2.title}</div>
                          {/if}
                          <div class="flex gap-0 mb-2">
                            {#each getAvailableTypes(activeChartTable) as ct}
                              <button class="chart-type-btn" class:chart-type-btn-active={(msg.chartType || chartHint2?.type || detectChartType(activeChartTable)) === ct} onclick={() => { messages = [...messages.slice(0, i), { ...msg, chartType: ct }, ...messages.slice(i + 1)]; }}>{ct.toUpperCase()}</button>
                            {/each}
                          </div>
                          <div style="background: var(--color-surface-bright); padding: 8px; border: 2px solid var(--color-on-surface);">
                            <EChartView headers={activeChartTable.headers} rows={activeChartTable.rows} chartType={msg.chartType || chartHint2?.type || detectChartType(activeChartTable)} />
                          </div>
                          <div class="flex gap-2 mt-3">
                            <button class="feedback-btn flex items-center gap-1" onclick={() => {
                              const slug = msg.routing?.slug || (selectedMode !== 'auto' ? selectedMode : '');
                              if (slug) openPinModal(i, tables, msg.content, slug);
                            }} style="font-size: 10px; font-weight: 700; text-transform: uppercase; padding: 4px 10px;">PIN TO DASHBOARD</button>
                          </div>
                        </div>

                      <!-- TAB: Sources -->
                      {:else if currentTab === 'sources'}
                        {@const sqlTableNames = (() => {
                          const names = new Set<string>();
                          for (const sql of (msg.sqlQueries || [])) {
                            const fromMatches = sql.match(/(?:FROM|JOIN)\s+([a-z_][a-z0-9_]*(?:\.[a-z_][a-z0-9_]*)?)/gi) || [];
                            for (const m of fromMatches) {
                              const t = m.replace(/^(?:FROM|JOIN)\s+/i, '').replace(/^[a-z_]+\./i, '').trim();
                              if (t && !['select','where','and','or','on','as','group','order','limit','having','union','case','when','then','else','end','not','in','is','null','like','between','exists','all','any','inner','outer','left','right','cross','natural','using','lateral','with','recursive','distinct','count','sum','avg','max','min','coalesce','cast','extract','date_trunc','to_char','row_number','rank','dense_rank','lag','lead','over','partition'].includes(t.toLowerCase())) names.add(t);
                            }
                          }
                          return [...names];
                        })()}
                        {@const confMatch3 = msg.content.match(/\[CONFIDENCE:(\w+[^\]]*)\]/)}
                        {@const confidence = confMatch3 ? confMatch3[1].trim() : (msg.qualityScore ? (msg.qualityScore >= 4 ? 'HIGH' : msg.qualityScore >= 3 ? 'MEDIUM' : 'LOW') : '')}
                        {@const confColor = confidence.includes('VERY HIGH') ? '#16a34a' : confidence === 'HIGH' ? '#16a34a' : confidence === 'MEDIUM' ? '#d97706' : confidence === 'LOW' ? '#dc2626' : '#888'}
                        {@const confPct = confidence.includes('VERY HIGH') ? 95 : confidence === 'HIGH' ? 85 : confidence === 'MEDIUM' ? 60 : confidence === 'LOW' ? 30 : 0}
                        {@const srcAgentName = msg.routing?.routed_to || 'Agent'}
                        {@const srcAnalysisType = msg.analysisUsed || msg.content.match(/\[ANALYSIS:([^\]]+)\]/)?.[1] || ''}
                        {@const srcToolCalls = (msg.toolCalls || []).filter((t: any) => (t.name || '') !== 'transfer_to_team_member')}
                        {@const srcTotalDuration = (() => { let s = 0; for (const t of srcToolCalls) { if (t.duration) s += parseFloat(t.duration); } return s > 0 ? s.toFixed(1) + 's' : ''; })()}
                        <div style="display: flex; flex-direction: column; gap: 12px;">
                          <!-- Metric cards -->
                          <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(120px, 1fr)); gap: 8px;">
                            <div style="padding: 12px 14px; border: 2px solid var(--color-on-surface); border-bottom-width: 3px; background: var(--color-surface-bright);">
                              <div style="font-size: 9px; font-weight: 900; text-transform: uppercase; letter-spacing: 0.1em; color: var(--color-on-surface-dim); margin-bottom: 6px;">AGENT</div>
                              <div style="font-size: 15px; font-weight: 900; text-transform: uppercase;">{srcAgentName}</div>
                            </div>
                            <div style="padding: 12px 14px; border: 2px solid var(--color-on-surface); border-bottom-width: 3px; background: var(--color-surface-bright);">
                              <div style="font-size: 9px; font-weight: 900; text-transform: uppercase; letter-spacing: 0.1em; color: var(--color-on-surface-dim); margin-bottom: 6px;">MODE</div>
                              <div style="font-size: 15px; font-weight: 900; text-transform: uppercase;">{msg.reasoningUsed || 'AUTO'}</div>
                            </div>
                            {#if msg.sqlQueries?.length}
                              <div style="padding: 12px 14px; border: 2px solid var(--color-on-surface); border-bottom-width: 3px; background: var(--color-surface-bright);">
                                <div style="font-size: 9px; font-weight: 900; text-transform: uppercase; letter-spacing: 0.1em; color: var(--color-on-surface-dim); margin-bottom: 6px;">QUERIES</div>
                                <div style="font-size: 15px; font-weight: 900;">{msg.sqlQueries.length}</div>
                              </div>
                            {/if}
                            {#if confidence}
                              <div style="padding: 12px 14px; border: 2px solid {confColor}; border-bottom-width: 3px; background: {confColor}08;">
                                <div style="font-size: 9px; font-weight: 900; text-transform: uppercase; letter-spacing: 0.1em; color: var(--color-on-surface-dim); margin-bottom: 6px;">CONFIDENCE</div>
                                <div style="font-size: 15px; font-weight: 900; color: {confColor};">{confidence}</div>
                                <div style="height: 4px; background: #e5e5e0; margin-top: 6px;"><div style="height: 100%; width: {confPct}%; background: {confColor};"></div></div>
                              </div>
                            {/if}
                          </div>
                          <!-- Data sources -->
                          {#if sqlTableNames.length}
                            <div style="border: 2px solid var(--color-on-surface); background: var(--color-surface-bright);">
                              <div style="padding: 8px 14px; background: var(--color-on-surface); color: var(--color-surface); font-size: 10px; font-weight: 900; text-transform: uppercase; letter-spacing: 0.08em;">DATA SOURCES &middot; {sqlTableNames.length} {sqlTableNames.length === 1 ? 'TABLE' : 'TABLES'}</div>
                              <div style="padding: 10px 14px; display: flex; flex-wrap: wrap; gap: 6px;">
                                {#each sqlTableNames as tbl}
                                  <span style="padding: 5px 12px; background: #1a1a1a; color: #00fc40; font-size: 11px; font-weight: 700; font-family: 'Space Grotesk', monospace; border: 1px solid #333;">{tbl}</span>
                                {/each}
                              </div>
                            </div>
                          {/if}
                          <!-- Execution log -->
                          {#if srcToolCalls.length}
                            <div style="border: 2px solid var(--color-on-surface); background: var(--color-surface-bright);">
                              <div style="padding: 8px 14px; background: var(--color-on-surface); color: var(--color-surface); font-size: 10px; font-weight: 900; text-transform: uppercase; letter-spacing: 0.08em; display: flex; justify-content: space-between;">
                                <span>EXECUTION LOG &middot; {srcToolCalls.length} STEPS</span>
                                {#if srcTotalDuration}<span style="color: #00fc40;">{srcTotalDuration} total</span>{/if}
                              </div>
                              {#each srcToolCalls as tc, ti}
                                <div style="padding: 6px 14px; border-bottom: 1px solid #f0f0ea; display: flex; align-items: center; gap: 10px; font-size: 12px;">
                                  <span style="font-size: 10px; color: var(--color-on-surface-dim); font-weight: 700; min-width: 18px;">{ti+1}</span>
                                  <span style="width: 8px; height: 8px; background: {tc.status === 'done' ? '#16a34a' : tc.status === 'error' ? '#dc2626' : '#d97706'}; flex-shrink: 0;"></span>
                                  <span style="font-weight: 700; font-family: 'Space Grotesk', monospace; flex: 1;">{tc.name}</span>
                                  {#if tc.duration}<span style="font-size: 10px; color: var(--color-on-surface-dim); font-family: 'Space Grotesk', monospace;">{tc.duration}</span>{/if}
                                </div>
                              {/each}
                            </div>
                          {/if}
                          <!-- SQL Queries -->
                          {#if msg.sqlQueries?.length}
                            <div style="border: 2px solid var(--color-on-surface); background: #1a1a1a;">
                              <div style="padding: 8px 14px; background: var(--color-on-surface); color: var(--color-surface); font-size: 10px; font-weight: 900; text-transform: uppercase; letter-spacing: 0.08em;">SQL QUERIES</div>
                              {#each msg.sqlQueries as sql, si}
                                <div style="padding: 10px 14px; border-bottom: 1px solid #333;">
                                  <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px;">
                                    <span style="font-size: 9px; font-weight: 900; color: #00fc40; text-transform: uppercase;">Query {si+1}</span>
                                    <button style="font-size: 9px; font-weight: 700; text-transform: uppercase; padding: 2px 8px; color: #888; border: 1px solid #444; background: transparent; cursor: pointer;" onclick={() => navigator.clipboard.writeText(sql)}>COPY</button>
                                  </div>
                                  <pre style="margin: 0; font-family: 'Space Grotesk', monospace; font-size: 11px; color: #e0e0e0; white-space: pre-wrap; word-break: break-all; line-height: 1.5;">{sql}</pre>
                                </div>
                              {/each}
                            </div>
                          {/if}
                        </div>
                      {/if}

                    <!-- Still streaming -->
                    {:else}
                      <div class="bubble-assistant">
                        {#if msg.content}
                          <div class="prose-chat">{@html markdownToHtml(msg.content)}</div>
                          {#if msg.status === 'streaming'}
                            <div class="flex items-center gap-2" style="margin-top: 8px;"><svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="var(--color-primary)" stroke-width="2" style="animation: headerFloat 2s ease-in-out infinite; flex-shrink: 0;"><rect x="3" y="11" width="18" height="10"/><path d="M12 2v4"/><circle cx="12" cy="7" r="1"/></svg><div class="typing-indicator"><span></span><span></span><span></span></div></div>
                          {/if}
                        {:else if msg.status === 'streaming'}
                          <div class="flex items-center gap-2"><svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="var(--color-primary)" stroke-width="2" style="animation: headerFloat 2s ease-in-out infinite;"><rect x="3" y="11" width="18" height="10"/><path d="M12 2v4"/><circle cx="12" cy="7" r="1"/></svg><div class="typing-indicator"><span></span><span></span><span></span></div></div>
                        {/if}
                      </div>
                    {/if}

                    <!-- Trace toggle -->
                    {#if msg.status === 'done'}
                      <button class="cli-terminal" style="cursor: pointer; width: 100%; text-align: left; margin-top: 8px; padding: 6px 14px;" onclick={() => { messages = [...messages.slice(0, i), { ...msg, showTrace: !msg.showTrace }, ...messages.slice(i + 1)]; }}>
                        <div class="cli-line">
                          <span class="cli-prompt">$</span>
                          <span class="cli-command">trace</span>
                          <span class="cli-dim" style="margin-left: auto;">{msg.showTrace ? '▲' : '▼'}</span>
                        </div>
                      </button>
                      {#if msg.showTrace}
                        <TracePanel toolCalls={msg.toolCalls || []} agentName={msg.routing?.routed_to || 'Agent'} qualityScore={msg.qualityScore} />
                      {/if}
                    {/if}

                    {#if msg.timestamp}
                      <div style="font-size: 10px; color: var(--color-on-surface-dim); margin-top: 4px; letter-spacing: 0.05em; text-transform: uppercase;">
                        {msg.timestamp} &middot; {msg.routing?.routed_to || 'Agent'}
                      </div>
                    {/if}

                    <!-- Auto-saved learnings (high confidence) -->
                    {#if msg.status === 'done' && msg.autoSavedLearnings && msg.autoSavedLearnings.length > 0}
                      <div class="learning-card" style="opacity: 0.7; border-color: var(--color-primary);">
                        <div class="learning-card-header" style="color: var(--color-primary);">
                          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="20 6 9 17 4 12"/></svg>
                          Auto-saved {msg.autoSavedLearnings.length} {msg.autoSavedLearnings.length === 1 ? 'learning' : 'learnings'} to memory.
                        </div>
                        <div class="learning-card-facts">
                          {#each (msg.autoSavedWithScores || msg.autoSavedLearnings.map(f => ({fact: f, score: 90}))) as item}
                            <div class="learning-fact" style="opacity: 0.7; display: flex; align-items: center; gap: 8px;">
                              <span style="flex: 1;">{item.fact}</span>
                              <span style="font-size: 9px; font-weight: 900; padding: 1px 6px; background: var(--color-primary); color: white; flex-shrink: 0;">{item.score}%</span>
                            </div>
                          {/each}
                        </div>
                      </div>
                    {/if}

                    <!-- Learning approval card (low confidence) -->
                    {#if msg.status === 'done' && msg.proposedLearnings && msg.proposedLearnings.length > 0 && !msg.learningsSaved}
                      {@const routedSlug = msg.routing?.slug || (selectedMode !== 'auto' ? selectedMode : projects[0]?.slug)}
                      {#if routedSlug}
                        <div class="learning-card">
                          <div class="learning-card-header">
                            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 2v10M12 12l4-4M12 12l-4-4M5 17h14M5 21h14"/></svg>
                            Approve {msg.proposedLearnings.length} {msg.proposedLearnings.length === 1 ? 'learning' : 'learnings'}?
                          </div>
                          <div class="learning-card-facts">
                            {#each (msg.proposedLearningsWithScores || msg.proposedLearnings.map(f => ({fact: f, score: 40}))) as item}
                              <div class="learning-fact" style="display: flex; align-items: center; gap: 8px;">
                                <span style="flex: 1;">{item.fact}</span>
                                <span style="font-size: 9px; font-weight: 900; padding: 1px 6px; background: var(--color-warning); color: var(--color-on-surface); flex-shrink: 0;">{item.score}%</span>
                              </div>
                            {/each}
                          </div>
                          <div class="flex gap-2 mt-2">
                            <button class="learning-approve-btn" onclick={async () => {
                              await fetch(`/api/projects/${routedSlug}/approve-learnings`, {
                                method: 'POST', headers: { ..._headers(), 'Content-Type': 'application/json' },
                                body: JSON.stringify({ facts: msg.proposedLearnings, scope: 'project' })
                              });
                              messages = [...messages.slice(0, i), { ...msg, learningsSaved: true }, ...messages.slice(i + 1)];
                            }}>SAVE TO MEMORY</button>
                            <button class="learning-dismiss-btn" onclick={() => {
                              messages = [...messages.slice(0, i), { ...msg, proposedLearnings: [], learningsSaved: true }, ...messages.slice(i + 1)];
                            }}>DISMISS</button>
                          </div>
                        </div>
                      {/if}
                    {/if}
                    {#if msg.status === 'done' && msg.learningsSaved && msg.proposedLearnings && msg.proposedLearnings.length > 0}
                      <div class="learning-card" style="opacity: 0.7;">
                        <div class="learning-card-header" style="color: var(--color-primary);">
                          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="20 6 9 17 4 12"/></svg>
                          Saved to project memory.
                        </div>
                      </div>
                    {/if}

                    {#if msg.status === 'done' && msg.suggestions && i === messages.length - 1}
                      <div class="flex flex-wrap gap-2 mt-3">
                        {#each msg.suggestions as suggestion}
                          <button class="suggestion-btn" onclick={() => send(suggestion)} disabled={isStreaming}>{suggestion}</button>
                        {/each}
                      </div>
                    {/if}
                  </div>
                </div>
              </div>
            {/if}
          {/each}
        </div>
      {/if}
    </div>
  </div>

  <!-- Input bar with mode selector -->
  <div class="input-bar shrink-0">
    <div style="max-width: 1100px; margin: 0 auto; padding: 12px 20px;">
      <div class="flex gap-1 items-stretch">
        <!-- Workflow selector — PURPLE -->
        <div class="mode-selector">
          <button class="mode-selector-btn" style="background: #7c3aed22; color: #7c3aed; border-color: #7c3aed; height: 34px; padding: 0 6px; font-size: 9px;" onclick={() => { if (allWorkflows.length === 0 && projects.length > 0) loadAllWorkflows(); workflowPickerOpen = !workflowPickerOpen; }} disabled={isStreaming} title="Workflow">
            <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="6" cy="6" r="2"/><circle cx="18" cy="6" r="2"/><circle cx="6" cy="18" r="2"/><circle cx="18" cy="18" r="2"/><path d="M8 6h8M6 8v8M18 8v8M8 18h8"/></svg>
            <span style="font-size: 9px;">Flow</span>
            <span class="mode-arrow" style="font-size: 7px;">&#9660;</span>
          </button>
          {#if workflowPickerOpen}
            <div class="mode-dropdown" style="min-width: 280px;">
              <!-- Save current chat as workflow -->
              {#if messages.filter(m => m.role === 'user').length >= 1}
                <button class="mode-dropdown-item" onclick={() => { workflowPickerOpen = false; openWorkflowSave(); }} style="border-bottom: 2px solid var(--color-on-surface-dim);">
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#7c3aed" stroke-width="2"><path d="M12 5v14M5 12h14"/></svg>
                  <div>
                    <div style="font-weight: 900; color: #7c3aed;">SAVE CURRENT AS WORKFLOW</div>
                    <span class="mode-dropdown-label">{messages.filter(m => m.role === 'user').length} steps from this chat</span>
                  </div>
                </button>
              {/if}
              {#if allWorkflows.length === 0}
                <div style="padding: 14px; font-size: 11px; color: var(--color-on-surface-dim); text-align: center;">No workflows yet. Train your projects to auto-generate workflows.</div>
              {:else}
                {#each allWorkflows as wf}
                  <button class="mode-dropdown-item" onclick={() => runWorkflowChat(wf)}>
                    <div>
                      <div style="font-weight: 900;">{wf.name}</div>
                      <span class="mode-dropdown-label">{wf.project} &middot; {wf.steps?.length || 0} steps</span>
                    </div>
                  </button>
                {/each}
              {/if}
            </div>
          {/if}
        </div>

        <!-- Reasoning mode selector -->
        <div class="mode-selector">
          <button class="mode-selector-btn" style="height: 34px; margin-right: 0; padding: 0 6px; font-size: 9px; {reasoningMode === 'deep' ? 'background: #007518; color: white; border-color: #007518;' : reasoningMode === 'fast' ? 'background: #00fc40; color: #383832; border-color: #00fc40;' : 'background: #00751822; color: #007518; border-color: #007518;'}" onclick={() => reasoningDropdownOpen = !reasoningDropdownOpen} title={reasoningMode === 'fast' ? 'Fast mode' : reasoningMode === 'deep' ? 'Deep mode' : 'Auto mode'}>
            {#if reasoningMode === 'fast'}
              <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"/></svg>
              <span style="font-size: 9px;">Fast</span>
            {:else if reasoningMode === 'deep'}
              <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><circle cx="12" cy="12" r="10"/><path d="M12 6v6l4 2"/></svg>
              <span style="font-size: 9px;">Deep</span>
            {:else}
              <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="3"/><path d="M12 1v4M12 19v4M4.22 4.22l2.83 2.83M16.95 16.95l2.83 2.83M1 12h4M19 12h4M4.22 19.78l2.83-2.83M16.95 7.05l2.83-2.83"/></svg>
              <span style="font-size: 9px;">Auto</span>
            {/if}
            <span class="mode-arrow" style="font-size: 7px;">&#9660;</span>
          </button>
          {#if reasoningDropdownOpen}
            <div class="mode-dropdown">
              <button class="mode-dropdown-item" class:mode-dropdown-item-active={reasoningMode === 'auto'} onclick={() => { reasoningMode = 'auto'; reasoningDropdownOpen = false; }}>
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="3"/><path d="M12 1v4M12 19v4M4.22 4.22l2.83 2.83M16.95 16.95l2.83 2.83M1 12h4M19 12h4M4.22 19.78l2.83-2.83M16.95 7.05l2.83-2.83"/></svg>
                <div>
                  <div>AUTO</div>
                  <span class="mode-dropdown-label">Auto-detects complexity</span>
                </div>
              </button>
              <button class="mode-dropdown-item" class:mode-dropdown-item-active={reasoningMode === 'fast'} onclick={() => { reasoningMode = 'fast'; reasoningDropdownOpen = false; }}>
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"/></svg>
                <div>
                  <div>FAST</div>
                  <span class="mode-dropdown-label">Direct SQL, quick answers</span>
                </div>
              </button>
              <button class="mode-dropdown-item" class:mode-dropdown-item-active={reasoningMode === 'deep'} onclick={() => { reasoningMode = 'deep'; reasoningDropdownOpen = false; }}>
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><path d="M12 6v6l4 2"/></svg>
                <div>
                  <div>DEEP</div>
                  <span class="mode-dropdown-label">Step-by-step reasoning, thorough analysis</span>
                </div>
              </button>
            </div>
          {/if}
        </div>

        <!-- Analysis type selector -->
        <div class="mode-selector">
          <button class="mode-selector-btn" style="height: 34px; margin-right: 0; padding: 0 6px; font-size: 9px; {analysisType !== 'auto' ? 'background: var(--color-secondary); color: white; border-color: var(--color-secondary);' : ''}" onclick={() => analysisDropdownOpen = !analysisDropdownOpen} title={analysisType === 'auto' ? 'Analysis type' : analysisTypes.find(a => a.value === analysisType)?.label || 'Analysis'}>
            <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="{analysisTypes.find(a => a.value === analysisType)?.icon || analysisTypes[0].icon}"/></svg>
            <span style="font-size: 9px;">{analysisType === 'auto' ? 'Type' : (analysisTypes.find(a => a.value === analysisType)?.label || '').slice(0, 5)}</span>
            <span class="mode-arrow" style="font-size: 7px;">&#9660;</span>
          </button>
          {#if analysisDropdownOpen}
            <div class="mode-dropdown" style="min-width: 220px;">
              {#each analysisTypes as at, ai}
                {#if ai === 1}
                  <div class="mode-dropdown-divider">ANALYSIS TYPES</div>
                {/if}
                <button class="mode-dropdown-item" class:mode-dropdown-item-active={analysisType === at.value} onclick={() => { analysisType = at.value; analysisDropdownOpen = false; }}>
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="{at.icon}"/></svg>
                  <div>
                    <div>{at.label.toUpperCase()}</div>
                    <span class="mode-dropdown-label">{at.desc}</span>
                  </div>
                </button>
              {/each}
            </div>
          {/if}
        </div>

        <!-- Mode selector (project routing) -->
        <div class="mode-selector">
          <button class="mode-selector-btn" style="height: 34px; margin-right: 0; padding: 0 6px; font-size: 9px; max-width: 130px; {selectedMode !== 'auto' ? 'background: var(--color-warning); color: var(--color-on-surface); border-color: var(--color-warning);' : ''}" onclick={() => dropdownOpen = !dropdownOpen} title={selectedMode === 'auto' ? 'All Agents' : getSelectedLabel()}>
            {#if selectedMode === 'auto'}
              <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="6" cy="6" r="2"/><circle cx="18" cy="6" r="2"/><circle cx="6" cy="18" r="2"/><circle cx="18" cy="18" r="2"/><path d="M8 6h8M6 8v8M18 8v8M8 18h8"/></svg>
            {:else}
              <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="11" width="18" height="10" rx="0"/><path d="M12 2v4"/><circle cx="12" cy="7" r="1"/></svg>
            {/if}
            <span style="overflow: hidden; text-overflow: ellipsis; white-space: nowrap; max-width: 70px; font-size: 9px;">{selectedMode === 'auto' ? `${projects.length} Agents` : getSelectedLabel()}</span>
            <span class="mode-arrow" style="font-size: 7px;">&#9660;</span>
          </button>

          {#if dropdownOpen}
            <div class="mode-dropdown">
              <button class="mode-dropdown-item" class:mode-dropdown-item-active={selectedMode === 'auto'} onclick={() => selectMode('auto')}>
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><path d="M12 6v6l4 2"/></svg>
                <div>
                  <div>AUTO</div>
                  <span class="mode-dropdown-label">Routes to the best agent automatically</span>
                </div>
              </button>

              {#if projects.length > 0}
                <div class="mode-dropdown-divider">YOUR AGENTS</div>
              {/if}

              {#each projects.filter(p => p.owned) as proj}
                <button class="mode-dropdown-item" class:mode-dropdown-item-active={selectedMode === proj.slug} onclick={() => selectMode(proj.slug)}>
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="11" width="18" height="10" rx="0"/><path d="M12 2v4"/><circle cx="12" cy="7" r="1"/></svg>
                  <div>
                    <div>{proj.agent_name}</div>
                    <span class="mode-dropdown-label">{proj.name}</span>
                  </div>
                </button>
              {/each}

              {#if projects.filter(p => !p.owned).length > 0}
                <div class="mode-dropdown-divider">SHARED WITH ME</div>
                {#each projects.filter(p => !p.owned) as proj}
                  <button class="mode-dropdown-item" class:mode-dropdown-item-active={selectedMode === proj.slug} onclick={() => selectMode(proj.slug)}>
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="11" width="18" height="10" rx="0"/><path d="M12 2v4"/><circle cx="12" cy="7" r="1"/></svg>
                    <div>
                      <div>{proj.agent_name}</div>
                      <span class="mode-dropdown-label">{proj.name} (shared)</span>
                    </div>
                  </button>
                {/each}
              {/if}
            </div>
          {/if}
        </div>

        <!-- Text input -->
        <div style="flex: 1;">
          <textarea bind:this={textareaEl} bind:value={inputText} onkeydown={handleKeydown} oninput={autoResize} placeholder="Ask anything across your agents..." rows="1" disabled={isStreaming} style="height: 34px; min-height: 34px; font-size: 12px;"></textarea>
        </div>

        <!-- Send / Stop button -->
        {#if isStreaming}
          <button onclick={stopStreaming} title="Stop" style="height: 34px; width: 34px; padding: 0; border: 2px solid var(--color-error); background: none; cursor: pointer; display: flex; align-items: center; justify-content: center;">
            <svg width="12" height="12" viewBox="0 0 24 24" fill="var(--color-error)"><rect x="4" y="4" width="16" height="16" rx="2"/></svg>
          </button>
        {:else}
          <button class="send-btn" onclick={() => send()} disabled={!inputText.trim()} title="Send" style="height: 34px; width: 34px; padding: 0; display: flex; align-items: center; justify-content: center;">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><line x1="22" y1="2" x2="11" y2="13"/><polygon points="22 2 15 22 11 13 2 9 22 2"/></svg>
          </button>
        {/if}

        <!-- Presentation button -->
        <button onclick={generateSlides} disabled={messages.length < 2 || slidesLoading || pptxGenerating} title="Create Presentation" style="height: 34px; width: 34px; padding: 0; border: 2px solid {messages.length >= 2 ? '#D24726' : '#ccc'}; background: {messages.length >= 2 ? '#D2472610' : 'none'}; cursor: {messages.length >= 2 ? 'pointer' : 'default'}; display: flex; align-items: center; justify-content: center; flex-shrink: 0;">
          <svg width="18" height="18" viewBox="0 0 24 24"><defs><linearGradient id="pptGrad2" x1="0" y1="0" x2="1" y2="1"><stop offset="0%" stop-color="#D24726"/><stop offset="50%" stop-color="#E5682A"/><stop offset="100%" stop-color="#F0A030"/></linearGradient></defs><rect x="2" y="2" width="20" height="20" rx="4" fill="url(#pptGrad2)"/><text x="12" y="16" text-anchor="middle" fill="white" font-size="13" font-weight="900" font-family="Arial">P</text></svg>
        </button>
        <!-- Excel Export button -->
        <button onclick={async () => {
          if (messages.length < 2) return;
          const res = await fetch('/api/export/excel-from-chat', {
            method: 'POST', headers: { ..._headers(), 'Content-Type': 'application/json' },
            body: JSON.stringify({ messages: messages.map(m => ({ role: m.role, content: m.content })), title: (selectedMode !== 'auto' ? getSelectedLabel() : 'Dash Agent') + ' Analysis', agent_name: selectedMode !== 'auto' ? getSelectedLabel() : 'Dash Agent' })
          });
          if (res.ok) { const blob = await res.blob(); const url = URL.createObjectURL(blob); const a = document.createElement('a'); a.href = url; a.download = 'dash-analysis.xlsx'; a.click(); URL.revokeObjectURL(url); }
        }} disabled={messages.length < 2} title="Export to Excel" style="height: 34px; width: 34px; padding: 0; border: 2px solid {messages.length >= 2 ? '#217346' : '#ccc'}; background: {messages.length >= 2 ? '#21734610' : 'none'}; cursor: {messages.length >= 2 ? 'pointer' : 'default'}; display: flex; align-items: center; justify-content: center; flex-shrink: 0;">
          <svg width="18" height="18" viewBox="0 0 24 24">
            <rect x="2" y="2" width="20" height="20" rx="4" fill="#217346"/>
            <text x="12" y="16" text-anchor="middle" fill="white" font-size="13" font-weight="900" font-family="Arial">X</text>
          </svg>
        </button>
      </div>

      <div style="text-align: center; margin-top: 4px; font-size: 9px; color: var(--color-on-surface-dim); text-transform: uppercase; letter-spacing: 0.1em;">
        DASH AGENT CAN MAKE MISTAKES. VERIFY CRITICAL INFORMATION.
      </div>
    </div>
  </div>
</div>

<!-- PIN to Dashboard Modal -->
{#if showPinModal}
<!-- svelte-ignore a11y_no_static_element_interactions -->
<div style="position: fixed; inset: 0; background: rgba(0,0,0,0.5); z-index: 200; display: flex; align-items: center; justify-content: center;" onclick={(e) => { if (e.target === e.currentTarget) showPinModal = false; }}>
  <div style="background: var(--color-surface); border: 3px solid var(--color-on-surface); width: 400px; box-shadow: 6px 6px 0 rgba(0,0,0,0.3);">
    <div style="padding: 10px 16px; background: #1a1a1a; color: #fff; font-size: 11px; font-weight: 900; text-transform: uppercase; letter-spacing: 0.1em; display: flex; justify-content: space-between; align-items: center;">
      <span>PIN TO DASHBOARD</span>
      <button onclick={() => showPinModal = false} style="background: none; border: none; color: #fff; cursor: pointer; font-size: 14px;">✕</button>
    </div>
    <div style="padding: 16px;">
      <!-- Project info -->
      <div style="font-size: 9px; font-weight: 700; text-transform: uppercase; margin-bottom: 3px;">PROJECT</div>
      <div style="padding: 6px 10px; border: 2px solid var(--color-on-surface); background: var(--color-surface-dim); font-size: 12px; margin-bottom: 12px; font-weight: 700;">{pinProjectSlug}</div>

      <!-- Widget title -->
      <div style="font-size: 9px; font-weight: 700; text-transform: uppercase; margin-bottom: 3px;">WIDGET TITLE</div>
      <input type="text" bind:value={pinWidgetTitle} style="width: 100%; border: 2px solid var(--color-on-surface); padding: 6px 10px; font-family: var(--font-family-display); font-size: 12px; background: var(--color-surface); margin-bottom: 12px;" />

      <!-- Select dashboard -->
      <div style="font-size: 9px; font-weight: 700; text-transform: uppercase; margin-bottom: 6px;">SELECT DASHBOARD</div>
      {#if pinDashboards.length > 0}
        <div style="display: flex; flex-direction: column; gap: 4px; margin-bottom: 12px; max-height: 120px; overflow-y: auto;">
          {#each pinDashboards as d}
            <button style="text-align: left; padding: 6px 10px; border: 2px solid {pinSelectedDash === d.id ? 'var(--color-primary)' : 'var(--color-on-surface)'}; background: {pinSelectedDash === d.id ? 'var(--color-primary-container)' : 'var(--color-surface-bright)'}; cursor: pointer; font-family: var(--font-family-display);" onclick={() => { pinSelectedDash = d.id; pinNewDashName = ''; }}>
              <div style="font-size: 11px; font-weight: 900; text-transform: uppercase;">{d.name}</div>
            </button>
          {/each}
        </div>
      {/if}

      <div style="font-size: 9px; font-weight: 700; text-transform: uppercase; margin-bottom: 3px;">OR CREATE NEW</div>
      <input type="text" bind:value={pinNewDashName} placeholder="New dashboard name..." onfocus={() => { pinSelectedDash = null; }} style="width: 100%; border: 2px solid var(--color-on-surface); padding: 6px 10px; font-family: var(--font-family-display); font-size: 12px; background: var(--color-surface); margin-bottom: 16px;" />

      <div style="display: flex; gap: 8px; justify-content: flex-end;">
        <button onclick={() => showPinModal = false} style="padding: 8px 16px; font-size: 11px; font-weight: 900; border: 2px solid var(--color-on-surface); background: none; cursor: pointer; font-family: var(--font-family-display); text-transform: uppercase;">CANCEL</button>
        <button onclick={confirmPin} disabled={!pinSelectedDash && !pinNewDashName.trim()} style="padding: 8px 16px; font-size: 11px; font-weight: 900; border: 2px solid var(--color-on-surface); background: var(--color-on-surface); color: var(--color-surface); cursor: pointer; font-family: var(--font-family-display); text-transform: uppercase;">PIN</button>
      </div>
    </div>
  </div>
</div>
{/if}

<!-- Save Workflow Modal -->
{#if showWorkflowSaveModal}
<!-- svelte-ignore a11y_no_static_element_interactions -->
<div style="position: fixed; inset: 0; background: rgba(0,0,0,0.5); z-index: 200; display: flex; align-items: center; justify-content: center;" onclick={(e) => { if (e.target === e.currentTarget) showWorkflowSaveModal = false; }}>
  <div style="background: var(--color-surface); border: 3px solid var(--color-on-surface); width: 450px; max-height: 80vh; overflow-y: auto; box-shadow: 6px 6px 0 rgba(0,0,0,0.3);">
    <div style="padding: 10px 16px; background: #7c3aed; color: #fff; font-size: 11px; font-weight: 900; text-transform: uppercase; letter-spacing: 0.1em; display: flex; justify-content: space-between; align-items: center;">
      <span>SAVE AS WORKFLOW</span>
      <button onclick={() => showWorkflowSaveModal = false} style="background: none; border: none; color: #fff; cursor: pointer; font-size: 14px;">✕</button>
    </div>
    <div style="padding: 16px;">
      <div style="font-size: 9px; font-weight: 900; text-transform: uppercase; letter-spacing: 0.08em; color: var(--color-on-surface-dim); margin-bottom: 4px;">WORKFLOW NAME</div>
      <input type="text" bind:value={wfSaveName} placeholder="e.g. Monthly Revenue Deep Dive" style="width: 100%; padding: 8px 12px; border: 2px solid var(--color-on-surface); font-family: var(--font-family-display); font-size: 13px; background: var(--color-surface-dim); margin-bottom: 12px;" />
      <div style="font-size: 9px; font-weight: 900; text-transform: uppercase; letter-spacing: 0.08em; color: var(--color-on-surface-dim); margin-bottom: 4px;">DESCRIPTION</div>
      <input type="text" bind:value={wfSaveDesc} placeholder="What this workflow analyzes..." style="width: 100%; padding: 8px 12px; border: 2px solid var(--color-on-surface); font-family: var(--font-family-display); font-size: 12px; background: var(--color-surface-dim); margin-bottom: 12px;" />
      <div style="font-size: 9px; font-weight: 900; text-transform: uppercase; letter-spacing: 0.08em; color: var(--color-on-surface-dim); margin-bottom: 6px;">STEPS (uncheck to exclude)</div>
      <div style="display: flex; flex-direction: column; gap: 4px; margin-bottom: 16px;">
        {#each wfSaveSteps as step, si}
          <label style="display: flex; align-items: flex-start; gap: 8px; padding: 6px 8px; background: {step.checked ? '#f3e8ff' : 'var(--color-surface-dim)'}; border: 1px solid {step.checked ? '#7c3aed' : 'var(--color-on-surface-dim)'}; cursor: pointer;">
            <input type="checkbox" bind:checked={step.checked} style="margin-top: 2px;" />
            <div>
              <div style="font-size: 9px; font-weight: 900; color: #7c3aed;">STEP {si + 1}</div>
              <div style="font-size: 11px; color: var(--color-on-surface);">{step.question}</div>
            </div>
          </label>
        {/each}
      </div>
      <div style="display: flex; gap: 8px; justify-content: flex-end;">
        <button onclick={() => showWorkflowSaveModal = false} style="padding: 8px 16px; font-size: 11px; font-weight: 900; border: 2px solid var(--color-on-surface); background: none; cursor: pointer; font-family: var(--font-family-display); text-transform: uppercase;">CANCEL</button>
        <button onclick={confirmWorkflowSave} disabled={!wfSaveName.trim() || wfSaveSteps.filter(s => s.checked).length === 0} style="padding: 8px 16px; font-size: 11px; font-weight: 900; border: 2px solid #7c3aed; background: #7c3aed; color: #fff; cursor: pointer; font-family: var(--font-family-display); text-transform: uppercase;">SAVE WORKFLOW</button>
      </div>
    </div>
  </div>
</div>
{/if}

<!-- Save Presentation Modal -->
{#if showSaveModal}
<div style="position: fixed; inset: 0; background: rgba(0,0,0,0.5); z-index: 200; display: flex; align-items: center; justify-content: center;" onclick={(e) => { if (e.target === e.currentTarget) showSaveModal = false; }}>
  <div style="background: var(--color-surface); border: 3px solid var(--color-on-surface); width: 400px; box-shadow: 6px 6px 0 rgba(0,0,0,0.3);">
    <div style="padding: 10px 16px; background: #1a1a1a; color: #fff; font-size: 11px; font-weight: 900; text-transform: uppercase; letter-spacing: 0.1em; display: flex; justify-content: space-between; align-items: center;">
      <span>SAVE PRESENTATION</span>
      <button onclick={() => showSaveModal = false} style="background: none; border: none; color: #fff; cursor: pointer; font-size: 14px;">&#10005;</button>
    </div>
    <div style="padding: 20px;">
      <div style="font-size: 9px; font-weight: 900; text-transform: uppercase; letter-spacing: 0.08em; color: var(--color-on-surface-dim); margin-bottom: 6px;">PRESENTATION NAME</div>
      <input type="text" bind:value={saveTitle} style="width: 100%; padding: 8px 12px; border: 2px solid var(--color-on-surface); font-family: var(--font-family-display); font-size: 13px; background: var(--color-surface-dim);" />
      <div style="font-size: 10px; color: var(--color-on-surface-dim); margin-top: 6px;">Same name = new version (v1, v2, v3...)</div>
      <div style="display: flex; gap: 8px; margin-top: 16px; justify-content: flex-end;">
        <button onclick={() => showSaveModal = false} style="padding: 8px 16px; font-size: 11px; font-weight: 900; border: 2px solid var(--color-on-surface); background: none; cursor: pointer; font-family: var(--font-family-display); text-transform: uppercase;">CANCEL</button>
        <button onclick={confirmSave} style="padding: 8px 16px; font-size: 11px; font-weight: 900; border: 2px solid var(--color-on-surface); background: var(--color-on-surface); color: var(--color-surface); cursor: pointer; font-family: var(--font-family-display); text-transform: uppercase;">SAVE</button>
      </div>
    </div>
  </div>
</div>
{/if}

<!-- Slide Panel -->
{#if slidesPanelOpen}
<div style="position: fixed; top: 0; right: 0; width: 55%; height: 100vh; background: #fff; border-left: 3px solid #1a1a1a; z-index: 90; display: flex; flex-direction: column; box-shadow: -4px 0 30px rgba(0,0,0,0.15);">
  <!-- Header -->
  <div style="padding: 8px 16px; background: #1a1a1a; color: #fff; display: flex; align-items: center; justify-content: space-between;">
    <div style="display: flex; align-items: center; gap: 8px;">
      <svg width="18" height="18" viewBox="0 0 24 24"><defs><linearGradient id="pg" x1="0" y1="0" x2="1" y2="1"><stop offset="0%" stop-color="#D24726"/><stop offset="100%" stop-color="#F0A030"/></linearGradient></defs><rect x="2" y="2" width="20" height="20" rx="3" fill="url(#pg)"/><text x="12" y="16" text-anchor="middle" fill="#fff" font-size="12" font-weight="900" font-family="Arial">P</text></svg>
      <span style="font-size: 11px; font-weight: 700; letter-spacing: 0.1em;">PRESENTATION</span>
      {#if slidesData.length > 0}
        <span style="font-size: 10px; opacity: 0.6;">{currentSlide + 1} / {slidesData.length}</span>
      {/if}
    </div>
    <div style="display: flex; gap: 8px; align-items: center;">
      <button onclick={savePresentation} disabled={slidesData.length === 0} style="font-size: 9px; padding: 3px 8px; background: none; border: 1px solid #555; color: #fff; cursor: pointer; text-transform: uppercase;">SAVE</button>
      <button onclick={downloadHTML} disabled={slidesData.length === 0} style="font-size: 9px; padding: 3px 8px; background: none; border: 1px solid #555; color: #fff; cursor: pointer; text-transform: uppercase;">HTML</button>
      <button onclick={downloadPptx} disabled={slidesData.length === 0} style="font-size: 9px; padding: 3px 8px; background: none; border: 1px solid #555; color: #fff; cursor: pointer; text-transform: uppercase;">PPTX</button>
      <button onclick={() => { downloadHTML(); }} style="font-size: 9px; padding: 3px 8px; background: none; border: 1px solid #555; color: #fff; cursor: pointer; text-transform: uppercase;">PDF</button>
      <button onclick={() => slidesPanelOpen = false} style="background: none; border: none; cursor: pointer; color: #fff; font-size: 16px;">&#10005;</button>
    </div>
  </div>

  <!-- Loading / PPTX Generation Steps -->
  {#if slidesLoading || pptxGenerating}
    <div style="flex: 1; display: flex; flex-direction: column; background: #1a1a1a; color: #e0e0e0; padding: 24px; font-family: 'SF Mono', 'Menlo', monospace;">
      <!-- Header -->
      <div style="display: flex; align-items: center; gap: 10px; margin-bottom: 20px;">
        <svg width="24" height="24" viewBox="0 0 24 24"><defs><linearGradient id="pg2" x1="0" y1="0" x2="1" y2="1"><stop offset="0%" stop-color="#D24726"/><stop offset="100%" stop-color="#F0A030"/></linearGradient></defs><rect x="2" y="2" width="20" height="20" rx="3" fill="url(#pg2)"/><text x="12" y="16" text-anchor="middle" fill="#fff" font-size="12" font-weight="900" font-family="Arial">P</text></svg>
        <span style="font-size: 13px; font-weight: 700; color: #fff; text-transform: uppercase; letter-spacing: 0.1em;">
          {pptxGenerating ? (pptxSteps.every(s => s.status === 'done') ? 'PRESENTATION READY' : 'GENERATING PRESENTATION') : 'CREATING SLIDES'}
        </span>
      </div>

      <!-- Progress bar -->
      {#if pptxSteps.length > 0}
        {@const doneCount = pptxSteps.filter(s => s.status === 'done').length}
        {@const pct = Math.round((doneCount / pptxSteps.length) * 100)}
        <div style="display: flex; align-items: center; gap: 10px; margin-bottom: 20px;">
          <div style="flex: 1; height: 4px; background: #333;">
            <div style="height: 100%; background: linear-gradient(90deg, #D24726, #F0A030); width: {pct}%; transition: width 0.5s;"></div>
          </div>
          <span style="font-size: 12px; font-weight: 700; color: #D24726;">{pct}%</span>
        </div>

        <!-- Steps -->
        <div style="flex: 1;">
          {#each pptxSteps as step}
            <div style="display: flex; align-items: center; gap: 8px; padding: 5px 0; font-size: 12px;">
              {#if step.status === 'done'}
                <span style="color: #00fc40;">&#10003;</span>
              {:else if step.status === 'active'}
                <span style="color: #F0A030;">&#9679;</span>
              {:else if step.status === 'error'}
                <span style="color: #ff4444;">&#10007;</span>
              {:else}
                <span style="color: #555;">&#9675;</span>
              {/if}
              <span style="color: {step.status === 'done' ? '#00fc40' : step.status === 'active' ? '#fff' : step.status === 'error' ? '#ff4444' : '#555'};">{step.label}</span>
            </div>
          {/each}
        </div>

        <!-- After complete -->
        {#if pptxSteps.every(s => s.status === 'done') && pptxSavedVersion > 0}
          <div style="margin-top: 16px; padding: 10px 14px; border: 1px solid #333; background: #222; font-size: 11px; color: #aaa;">
            Saved to <span style="color: #D24726; font-weight: 700;">PRESENTATIONS</span> tab as v{pptxSavedVersion}
          </div>
          <div style="display: flex; gap: 8px; margin-top: 12px;">
            <button onclick={() => { pptxSteps = []; currentSlide = 0; }} style="flex: 1; padding: 8px; font-size: 11px; font-weight: 900; background: #D24726; color: #fff; border: none; cursor: pointer; text-transform: uppercase;">OPEN SLIDES</button>
            <button onclick={() => { slidesPanelOpen = false; pptxSteps = []; }} style="flex: 1; padding: 8px; font-size: 11px; font-weight: 900; background: none; border: 1px solid #555; color: #aaa; cursor: pointer; text-transform: uppercase;">CLOSE</button>
          </div>
        {/if}

      {:else}
        <!-- Simple loading for generateSlides -->
        <div style="flex: 1; display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 12px;">
          <div style="font-size: 13px; color: #aaa;">{slidesProgress}</div>
          <div style="width: 200px; height: 3px; background: #333;">
            <div style="height: 100%; background: linear-gradient(90deg, #D24726, #F0A030); width: {slidesProgress.includes('Analyz') ? '30' : slidesProgress.includes('Structur') ? '60' : slidesProgress.includes('Done') ? '100' : '15'}%; transition: width 0.8s;"></div>
          </div>
        </div>
      {/if}
    </div>

  {:else if slidesData.length > 0}
    <!-- Narrative bar -->
    {#if slidesThinking}
      <div style="padding: 6px 16px; background: #f5f5f0; border-bottom: 1px solid #e0e0d8; font-size: 10px; color: #555; line-height: 1.4;">
        <strong style="color: #1a1a1a;">NARRATIVE:</strong> {slidesThinking.narrative || ''}
        {#if slidesThinking.key_insight} &middot; <strong style="color: #D24726;">KEY INSIGHT:</strong> {slidesThinking.key_insight}{/if}
      </div>
    {/if}

    <!-- Slide content -->
    <div style="flex: 1; overflow-y: auto; background: #fafaf8;" class="slide-render-area">
      {#if slidesData[currentSlide]}
        {@const slide = slidesData[currentSlide]}

        <!-- Topic bar -->
        <div style="padding: 6px 24px; background: #f0f0eb; border-bottom: 1px solid #ddd; font-size: 9px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.15em; color: #888; display: flex; justify-content: space-between;">
          <span>{slide.topic || 'ANALYSIS'}</span>
          <span>{currentSlide + 1} / {slidesData.length}</span>
        </div>

        <div style="padding: 24px 28px;">

          {#if slide.layout === 'cover'}
            <!-- COVER SLIDE -->
            <div style="display: flex; flex-direction: column; align-items: center; justify-content: center; min-height: 380px; text-align: center;">
              <div style="font-size: 32px; font-weight: 900; color: #1a1a1a; line-height: 1.2; max-width: 500px;">{slide.title}</div>
              <div style="width: 60px; height: 3px; background: linear-gradient(90deg, #D24726, #F0A030); margin: 20px auto;"></div>
              {#if slide.bullets?.length}
                <div style="font-size: 15px; color: #666; margin-top: 8px;">{slide.bullets[0]}</div>
              {/if}
              <div style="font-size: 11px; color: #999; margin-top: 30px; text-transform: uppercase; letter-spacing: 0.1em;">{selectedMode !== 'auto' ? getSelectedLabel() : 'Dash Agent'} &middot; {new Date().toLocaleDateString('en-US', {month: 'long', day: 'numeric', year: 'numeric'})}</div>
              <div style="font-size: 9px; color: #bbb; margin-top: 8px; letter-spacing: 0.15em;">POWERED BY RLAI DASH</div>
            </div>

          {:else if slide.layout === 'kpi' && slide.kpis?.length}
            <!-- KPI SLIDE -->
            <div style="font-size: 18px; font-weight: 800; color: #1a1a1a; line-height: 1.3; margin-bottom: 20px;">{slide.title}</div>
            <div style="width: 100%; height: 2px; background: #1a1a1a; margin-bottom: 24px;"></div>
            <div style="display: flex; gap: 16px; justify-content: center; margin: 20px 0;">
              {#each slide.kpis as kpi}
                <div style="flex: 1; text-align: center; padding: 20px; border: 2px solid #e0e0d8;">
                  <div style="font-size: 36px; font-weight: 900; color: #1a1a1a;">{kpi.value}</div>
                  <div style="font-size: 11px; color: #888; text-transform: uppercase; letter-spacing: 0.08em; margin-top: 6px;">{kpi.label}</div>
                  {#if kpi.change}
                    <div style="font-size: 14px; font-weight: 700; color: {kpi.change?.startsWith('+') || kpi.change?.startsWith('\u25B2') ? '#00873c' : '#d32f2f'}; margin-top: 4px;">{kpi.change}</div>
                  {/if}
                </div>
              {/each}
            </div>
            {#each (slide.bullets || []) as b, bi}
              <div style="font-size: 13px; color: #444; padding: 6px 0; border-bottom: 1px solid #eee;">{bi + 1}. {b}</div>
            {/each}
            {#if slide.action_line}
              <div style="margin-top: 20px; padding: 10px 14px; border-top: 2px solid #1a1a1a; font-size: 12px; font-weight: 700; color: #1a1a1a;">{slide.action_line}</div>
            {/if}

          {:else if slide.layout === 'exhibit' || slide.chart}
            <!-- EXHIBIT SLIDE (chart + takeaways) -->
            <div style="font-size: 18px; font-weight: 800; color: #1a1a1a; line-height: 1.3; margin-bottom: 20px;">{slide.title}</div>
            <div style="width: 100%; height: 2px; background: #1a1a1a; margin-bottom: 20px;"></div>
            <div style="display: flex; gap: 24px;">
              <div style="flex: 3;">
                {#if slide.chart}
                  <div style="font-size: 10px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.1em; color: #888; margin-bottom: 8px;">{slide.chart.title || 'EXHIBIT'}</div>
                  <div id="slide-chart-{currentSlide}" style="width: 100%; height: 260px;"></div>
                  <div style="font-size: 9px; color: #aaa; margin-top: 4px;">Source: Project data</div>
                {/if}
              </div>
              <div style="flex: 2; border-left: 2px solid #e0e0d8; padding-left: 16px;">
                <div style="font-size: 10px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.1em; color: #888; margin-bottom: 12px;">KEY TAKEAWAYS</div>
                {#each (slide.bullets || []) as b, bi}
                  <div style="font-size: 12px; color: #333; margin-bottom: 10px; padding-bottom: 10px; border-bottom: 1px solid #eee;">
                    <span style="font-weight: 800; color: #D24726;">{bi + 1}.</span> {b}
                  </div>
                {/each}
              </div>
            </div>
            {#if slide.action_line}
              <div style="margin-top: 16px; padding: 10px 14px; border-top: 2px solid #1a1a1a; font-size: 12px; font-weight: 700; color: #1a1a1a;">{slide.action_line}</div>
            {/if}

          {:else if slide.layout === 'data' || slide.table}
            <!-- DATA SLIDE (table) -->
            <div style="font-size: 18px; font-weight: 800; color: #1a1a1a; line-height: 1.3; margin-bottom: 20px;">{slide.title}</div>
            <div style="width: 100%; height: 2px; background: #1a1a1a; margin-bottom: 20px;"></div>
            {#if slide.table}
              <table style="width: 100%; border-collapse: collapse;">
                <thead>
                  <tr style="border-bottom: 2px solid #1a1a1a;">
                    {#each (slide.table.headers || []) as h}
                      <th style="padding: 8px 12px; text-align: left; font-size: 10px; text-transform: uppercase; letter-spacing: 0.08em; color: #666; font-weight: 700;">{h}</th>
                    {/each}
                  </tr>
                </thead>
                <tbody>
                  {#each (slide.table.rows || []).slice(0, 10) as row, ri}
                    <tr style="border-bottom: 1px solid #eee; background: {ri % 2 === 0 ? '#fafaf8' : '#fff'};">
                      {#each row as cell}
                        <td style="padding: 7px 12px; font-size: 12px; color: #333;">{cell}</td>
                      {/each}
                    </tr>
                  {/each}
                </tbody>
              </table>
            {/if}
            {#each (slide.bullets || []) as b}
              <div style="font-size: 12px; color: #555; margin-top: 6px;">· {b}</div>
            {/each}
            {#if slide.action_line}
              <div style="margin-top: 16px; padding: 10px 14px; border-top: 2px solid #1a1a1a; font-size: 12px; font-weight: 700; color: #1a1a1a;">{slide.action_line}</div>
            {/if}

          {:else if slide.layout === 'comparison' && slide.comparison}
            <!-- COMPARISON SLIDE -->
            <div style="font-size: 18px; font-weight: 800; color: #1a1a1a; line-height: 1.3; margin-bottom: 20px;">{slide.title}</div>
            <div style="width: 100%; height: 2px; background: #1a1a1a; margin-bottom: 20px;"></div>
            <div style="display: flex; gap: 16px;">
              <div style="flex: 1; border: 2px solid #e0e0d8; padding: 16px;">
                <div style="font-size: 14px; font-weight: 900; color: #1a1a1a; margin-bottom: 12px; padding-bottom: 8px; border-bottom: 2px solid #D24726;">{slide.comparison.left?.title || 'A'}</div>
                {#each (slide.comparison.left?.items || []) as item}
                  <div style="font-size: 12px; color: #444; padding: 4px 0;">{item}</div>
                {/each}
              </div>
              <div style="display: flex; align-items: center; font-size: 20px; color: #ccc; font-weight: 900;">vs</div>
              <div style="flex: 1; border: 2px solid #e0e0d8; padding: 16px;">
                <div style="font-size: 14px; font-weight: 900; color: #1a1a1a; margin-bottom: 12px; padding-bottom: 8px; border-bottom: 2px solid #00873c;">{slide.comparison.right?.title || 'B'}</div>
                {#each (slide.comparison.right?.items || []) as item}
                  <div style="font-size: 12px; color: #444; padding: 4px 0;">{item}</div>
                {/each}
              </div>
            </div>
            {#if slide.action_line}
              <div style="margin-top: 16px; padding: 10px 14px; border-top: 2px solid #1a1a1a; font-size: 12px; font-weight: 700; color: #1a1a1a;">{slide.action_line}</div>
            {/if}

          {:else if slide.layout === 'recommendations'}
            <!-- RECOMMENDATIONS SLIDE -->
            <div style="font-size: 18px; font-weight: 800; color: #1a1a1a; line-height: 1.3; margin-bottom: 20px;">{slide.title}</div>
            <div style="width: 100%; height: 2px; background: #1a1a1a; margin-bottom: 20px;"></div>
            <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 12px;">
              {#each (slide.bullets || []) as b, bi}
                <div style="padding: 14px; border: 2px solid #e0e0d8; background: #fff;">
                  <div style="font-size: 10px; font-weight: 900; color: #D24726; text-transform: uppercase; letter-spacing: 0.08em; margin-bottom: 6px;">PRIORITY {bi + 1}</div>
                  <div style="font-size: 13px; color: #333; line-height: 1.4;">{b}</div>
                </div>
              {/each}
            </div>
            {#if slide.action_line}
              <div style="margin-top: 16px; padding: 10px 14px; border-top: 2px solid #1a1a1a; font-size: 12px; font-weight: 700; color: #1a1a1a;">{slide.action_line}</div>
            {/if}

          {:else}
            <!-- GENERIC BULLETS -->
            <div style="font-size: 18px; font-weight: 800; color: #1a1a1a; line-height: 1.3; margin-bottom: 20px;">{slide.title}</div>
            <div style="width: 100%; height: 2px; background: #1a1a1a; margin-bottom: 20px;"></div>
            {#each (slide.bullets || []) as b, bi}
              <div style="font-size: 14px; color: #333; padding: 10px 14px; border-left: 3px solid #D24726; margin-bottom: 8px; background: #fafaf8;">
                <span style="font-weight: 800; color: #D24726;">{bi + 1}.</span> {b}
              </div>
            {/each}
            {#if slide.action_line}
              <div style="margin-top: 16px; padding: 10px 14px; border-top: 2px solid #1a1a1a; font-size: 12px; font-weight: 700; color: #1a1a1a;">{slide.action_line}</div>
            {/if}
          {/if}

        </div>
      {/if}
    </div>

    <!-- Thumbnail navigation -->
    <div style="padding: 8px 16px; border-top: 2px solid #1a1a1a; background: #f5f5f0; display: flex; align-items: center; justify-content: space-between;">
      <button onclick={() => currentSlide = Math.max(0, currentSlide - 1)} disabled={currentSlide === 0} style="font-size: 9px; font-weight: 900; padding: 4px 10px; border: 1px solid #ccc; background: #fff; cursor: pointer;">&#8592; PREV</button>
      <div style="display: flex; gap: 3px; align-items: center;">
        {#each slidesData as s, si}
          <button onclick={() => currentSlide = si} style="width: 28px; height: 18px; border: {si === currentSlide ? '2px solid #D24726' : '1px solid #ccc'}; background: {si === currentSlide ? '#FFF3E0' : '#fff'}; cursor: pointer; padding: 0; font-size: 7px; font-weight: 700; color: {si === currentSlide ? '#D24726' : '#999'};">{si + 1}</button>
        {/each}
      </div>
      <button onclick={() => currentSlide = Math.min(slidesData.length - 1, currentSlide + 1)} disabled={currentSlide >= slidesData.length - 1} style="font-size: 9px; font-weight: 900; padding: 4px 10px; border: 1px solid #ccc; background: #fff; cursor: pointer;">NEXT &#8594;</button>
    </div>

  {:else}
    <div style="flex: 1; display: flex; align-items: center; justify-content: center; color: #999; font-size: 12px;">No slides generated</div>
  {/if}
</div>
{/if}
</div>

<style>
@media print {
  :global(nav), :global(.input-bar), :global(.nav-btn),
  :global([style*="CHAT HISTORY"]), :global(header) {
    display: none !important;
  }
  :global(body) {
    overflow: visible !important;
    background: white !important;
  }
  .slide-render-area {
    overflow: visible !important;
    height: auto !important;
  }
}
</style>
