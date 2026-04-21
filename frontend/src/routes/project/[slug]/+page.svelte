<script lang="ts">
  import { onMount, tick } from 'svelte';
  import { page } from '$app/state';
  import { sendMessage, generateSessionId, markdownToHtml, parseMarkdownTables, tableToCsv, hasNumericData, detectChartType, getAvailableTypes, parseChartHint } from '$lib';
  import type { ToolCall } from '$lib/api';
  import type { ParsedTable } from '$lib/table-parser';
  import type { ChartType } from '$lib/chart-detect';
  import EChartView from '$lib/echart.svelte';
  import TracePanel from '$lib/trace-panel.svelte';
  import DashboardPanel from '$lib/dashboard-panel.svelte';

  // Project context
  const projectSlug = $derived(page.params.slug || '');
  let projectInfo = $state<any>(null);

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
    qualityScore?: number;
    showTrace?: boolean;
    activeTab?: 'insight' | 'analysis' | 'data' | 'query' | 'graph';
    reasoningUsed?: string;
    analysisUsed?: string;
    proposedLearnings?: string[];
    proposedLearningsWithScores?: {fact: string; score: number}[];
    autoSavedLearnings?: string[];
    autoSavedWithScores?: {fact: string; score: number}[];
    learningsSaved?: boolean;
  }

  let messages = $state<ChatMessage[]>([]);
  let inputText = $state('');
  let isStreaming = $state(false);
  let sessionId = $state('');
  let sessionStartTime = $state('');
  let messagesEl: HTMLDivElement;
  let textareaEl: HTMLTextAreaElement;
  let copiedIndex = $state(-1);

  // Proactive insights
  let insights = $state<{id: number; insight: string; severity: string; tables: string[]; created_at: string}[]>([]);

  async function loadInsights() {
    try {
      const res = await fetch(`/api/projects/${projectSlug}/insights`, { headers: _headers() });
      if (res.ok) { const d = await res.json(); insights = d.insights || []; }
    } catch {}
  }

  async function dismissInsight(id: number) {
    await fetch(`/api/projects/${projectSlug}/insights/${id}/dismiss`, { method: 'POST', headers: _headers() });
    insights = insights.filter(i => i.id !== id);
  }

  function trackPreference(action: string, value: string) {
    fetch(`/api/projects/${projectSlug}/track-preference`, {
      method: 'POST', headers: { ..._headers(), 'Content-Type': 'application/json' },
      body: JSON.stringify({ action, value })
    }).catch(() => {});
  }

  // Sidebar — persisted in localStorage, default open
  let sidebarOpen = $state(typeof localStorage !== 'undefined' ? localStorage.getItem('dash_sidebar') !== 'closed' : true);
  let pastSessions = $state<{session_id: string; created_at: string; updated_at: string; first_message?: string}[]>([]);

  function toggleSidebar() {
    sidebarOpen = !sidebarOpen;
    localStorage.setItem('dash_sidebar', sidebarOpen ? 'open' : 'closed');
    if (sidebarOpen) loadSessions();
  }

  function _headers(): Record<string, string> {
    const t = typeof localStorage !== 'undefined' ? localStorage.getItem('dash_token') : null;
    return t ? { Authorization: `Bearer ${t}` } : {};
  }

  async function loadSessions() {
    try {
      const res = await fetch(`/api/sessions?project=${projectSlug}`, { headers: _headers() });
      if (res.ok) { const d = await res.json(); pastSessions = d.sessions || []; }
    } catch {}
  }

  async function registerSession(msg: string) {
    try {
      await fetch(`/api/sessions/register?session_id=${encodeURIComponent(sessionId)}&project=${encodeURIComponent(projectSlug)}&message=${encodeURIComponent(msg)}`, {
        method: 'POST', headers: _headers()
      });
    } catch {}
  }

  async function switchSession(sid: string) {
    sessionId = sid;
    localStorage.setItem(`dash_session_${projectSlug}`, sid);
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
      const now = new Date();
      const diff = now.getTime() - d.getTime();
      if (diff < 3600000) return Math.floor(diff / 60000) + 'm ago';
      if (diff < 86400000) return Math.floor(diff / 3600000) + 'h ago';
      return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
    } catch { return ''; }
  }

  let dynamicSuggestions = $state<string[]>([]);
  let projectTables = $state<{name: string; columns: string[]; rows: number}[]>([]);

  // Chat stats for empty state
  let sessionCount = $state(0);
  let avgScore = $state(0);
  let memoryCount = $state(0);

  async function loadChatStats() {
    sessionCount = pastSessions.length;
    // Fetch average quality score
    try {
      const r = await fetch(`/api/projects/${projectSlug}/scores/latest?session_id=all`, { headers: _headers() });
      if (r.ok) { const d = await r.json(); avgScore = d.score || 0; }
    } catch {}
    // Fetch memory count from consolidation status
    try {
      const r = await fetch(`/api/projects/${projectSlug}/consolidation-status`, { headers: _headers() });
      if (r.ok) { const d = await r.json(); memoryCount = d.memory_count || 0; }
    } catch {}
  }

  async function loadDynamicSuggestions() {
    try {
      const res = await fetch(`/api/projects/${projectSlug}/stats`, { headers: _headers() });
      if (!res.ok) return;
      const data = await res.json();
      const tables = data.tables || [];
      if (tables.length === 0) {
        dynamicSuggestions = ["What tables do I have?", "Help me understand my data"];
        return;
      }

      // Fetch column details for each table
      const tableDetails: {name: string; columns: string[]; rows: number}[] = [];
      for (const t of tables.slice(0, 8)) {
        try {
          const ir = await fetch(`/api/tables/${t.name}/inspect?project=${projectSlug}`, { headers: _headers() });
          if (ir.ok) {
            const id = await ir.json();
            tableDetails.push({ name: t.name, columns: (id.columns || []).map((c: any) => c.name), rows: t.rows || 0 });
          } else {
            tableDetails.push({ name: t.name, columns: [], rows: t.rows || 0 });
          }
        } catch {
          tableDetails.push({ name: t.name, columns: [], rows: t.rows || 0 });
        }
      }
      projectTables = tableDetails;

      // Generate smart, varied suggestions from actual data
      const suggestions: string[] = [];
      const templates = [
        (t: string, cols: string[]) => {
          const numCol = cols.find(c => /amount|price|revenue|total|cost|value|salary|qty|quantity|count/i.test(c));
          return numCol ? `What is the total ${numCol.replace(/_/g, ' ')} in ${t.replace(/_/g, ' ')}?` : null;
        },
        (t: string, cols: string[]) => {
          const dateCol = cols.find(c => /date|created|updated|time|month|year/i.test(c));
          return dateCol ? `Show ${t.replace(/_/g, ' ')} trends over time` : null;
        },
        (t: string, cols: string[]) => {
          const catCol = cols.find(c => /status|type|category|plan|region|country|department|segment/i.test(c));
          return catCol ? `Break down ${t.replace(/_/g, ' ')} by ${catCol.replace(/_/g, ' ')}` : null;
        },
        (t: string, _cols: string[]) => `Show me the top 10 records in ${t.replace(/_/g, ' ')}`,
        (t: string, _cols: string[]) => `Summarize the ${t.replace(/_/g, ' ')} data`,
      ];

      for (const td of tableDetails) {
        for (const tmpl of templates) {
          const s = tmpl(td.name, td.columns);
          if (s && suggestions.length < 6) suggestions.push(s);
          if (suggestions.length >= 6) break;
        }
        if (suggestions.length >= 6) break;
      }

      // Add relationship question if multiple tables
      if (tableDetails.length > 1 && suggestions.length < 6) {
        suggestions.push(`How do ${tableDetails[0].name.replace(/_/g, ' ')} and ${tableDetails[1].name.replace(/_/g, ' ')} relate?`);
      }

      if (suggestions.length === 0) {
        suggestions.push("What tables do I have?", "Give me an overview of my data");
      }

      dynamicSuggestions = suggestions.slice(0, 6);
    } catch {}
  }

  function getTimestamp(): string {
    return new Date().toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit', hour12: true });
  }

  function getSuggestions(content: string): string[] {
    // Generate follow-ups based on response content + actual project tables
    const lower = content.toLowerCase();
    const suggestions: string[] = [];

    // Content-aware follow-ups
    if (lower.includes('table') || lower.includes('column')) {
      for (const t of projectTables.slice(0, 2)) {
        suggestions.push(`Show me sample data from ${t.name.replace(/_/g, ' ')}`);
      }
    }
    if (lower.includes('trend') || lower.includes('growth') || lower.includes('month')) {
      suggestions.push("Compare this to the previous period");
      suggestions.push("What's driving this trend?");
    }
    if (lower.includes('top') || lower.includes('highest') || lower.includes('largest')) {
      suggestions.push("Show the bottom performers too");
      suggestions.push("What percentage of total do they represent?");
    }

    // Table-aware generic follow-ups
    if (suggestions.length < 3) {
      for (const t of projectTables.slice(0, 3)) {
        const numCol = t.columns.find(c => /amount|price|revenue|total|cost|value/i.test(c));
        const catCol = t.columns.find(c => /status|type|category|plan|region/i.test(c));
        if (numCol && catCol && suggestions.length < 3) {
          suggestions.push(`Break down ${numCol.replace(/_/g, ' ')} by ${catCol.replace(/_/g, ' ')} in ${t.name.replace(/_/g, ' ')}`);
        }
      }
    }

    // Fallback
    if (suggestions.length === 0) {
      suggestions.push("Tell me more about this", "Can you visualize this?", "What else can you find?");
    }

    return suggestions.slice(0, 3);
  }

  function getTotalDuration(tools: ToolCall[]): string {
    let total = 0;
    for (const t of tools) {
      if (t.duration) {
        total += parseFloat(t.duration);
      }
    }
    return total > 0 ? total.toFixed(1) + 's' : '';
  }

  function getAgentMode(tools: ToolCall[]): 'deep' | 'fast' {
    const names = tools.map(t => t.name.toLowerCase());
    if (names.some(n => n === 'think' || n === 'analyze')) return 'deep';
    // Also detect deep by number of SQL queries or total steps
    const sqlCount = names.filter(n => n.includes('sql') || n.includes('query')).length;
    if (sqlCount >= 2 || tools.length >= 7) return 'deep';
    return 'fast';
  }

  const DEEP_KEYWORDS = /\b(why|compare|explain|suggest|recommend|correlate|analyze|break down|what should|how can|investigate|diagnose|root cause)\b/i;

  function isComplexQuery(text: string): boolean {
    if (DEEP_KEYWORDS.test(text)) return true;
    if ((text.match(/\band\b/gi) || []).length >= 2) return true;
    if (text.split('?').length > 2) return true;
    return false;
  }

  onMount(async () => {
    // Load project info
    try {
      const res = await fetch(`/api/projects/${projectSlug}`, { headers: _headers() });
      if (res.ok) projectInfo = await res.json();
    } catch {}

    const savedSession = localStorage.getItem(`dash_session_${projectSlug}`);
    if (savedSession) {
      sessionId = savedSession;
      // Restore messages from saved session
      try {
        const res = await fetch(`/api/sessions/${savedSession}/messages`, { headers: _headers() });
        if (res.ok) {
          const data = await res.json();
          const loaded = data.messages || [];
          if (loaded.length > 0) {
            messages = loaded.map((m: any) => ({
              role: m.role,
              content: m.content,
              timestamp: '',
              status: m.role === 'assistant' ? 'done' : undefined,
              toolCalls: [],
              workflowExpanded: false,
              activeTab: 'insight',
            }));
          }
        }
      } catch {}
    } else {
      sessionId = generateSessionId();
    }
    localStorage.setItem(`dash_session_${projectSlug}`, sessionId);
    sessionStartTime = getTimestamp();
    textareaEl?.focus();
    loadDynamicSuggestions();
    loadSessions().then(() => loadChatStats());
    loadWorkflows();
  });

  function newChat() {
    messages = [];
    sessionId = generateSessionId();
    localStorage.setItem(`dash_session_${projectSlug}`, sessionId);
    sessionStartTime = getTimestamp();
    textareaEl?.focus();
    loadSessions();
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

  async function send(text?: string) {
    const msg = (text || inputText).trim();
    if (!msg || isStreaming) return;
    inputText = '';
    if (textareaEl) textareaEl.style.height = 'auto';

    messages = [...messages, { role: 'user', content: msg, timestamp: getTimestamp() }];
    isStreaming = true;
    registerSession(msg);
    await scrollToBottom();

    messages = [...messages, { role: 'assistant', content: '', timestamp: '', status: 'streaming', toolCalls: [], workflowExpanded: true, reasoningUsed: reasoningMode, analysisUsed: analysisType }];
    await scrollToBottom();

    await sendMessage(
      msg, sessionId,
      (token) => {
        const last = messages[messages.length - 1];
        if (last?.role === 'assistant') {
          messages = [...messages.slice(0, -1), { ...last, content: last.content + token }];
        }
        scrollToBottom();
      },
      () => {
        const last = messages[messages.length - 1];
        if (last?.role === 'assistant') {
          // Detect [DASHBOARD:id] tag from agent
          const dashMatch = last.content.match(/\[DASHBOARD:(\d+)\]/);
          if (dashMatch) {
            activeDashboardId = parseInt(dashMatch[1]);
            dashboardPanelOpen = true;
          }
          messages = [...messages.slice(0, -1), {
            ...last, timestamp: getTimestamp(), status: 'done',
            suggestions: getSuggestions(last.content), workflowExpanded: false
          }];
        }
        isStreaming = false;
        scrollToBottom();
        textareaEl?.focus();
        loadSessions();
        // Extract context memory + smart follow-ups (background)
        const lastUserMsg = messages.length >= 2 ? messages[messages.length - 2]?.content : '';
        const lastAssistantMsg = messages[messages.length - 1]?.content || '';
        if (lastUserMsg && lastAssistantMsg) {
          // Context extraction — auto-save high confidence, propose low confidence
          fetch(`/api/projects/${projectSlug}/extract-context`, {
            method: 'POST', headers: { ..._headers(), 'Content-Type': 'application/json' },
            body: JSON.stringify({ question: lastUserMsg, answer: lastAssistantMsg })
          }).then(r => r.json()).then(d => {
            const last = messages[messages.length - 1];
            if (!last || last.role !== 'assistant') return;
            const autoSaved = d.auto_saved_with_scores || d.auto_saved?.map((f: string) => ({fact: f, score: 90})) || [];
            const needsApproval = d.facts_with_scores || d.facts?.map((f: string) => ({fact: f, score: 40})) || [];
            if (autoSaved.length > 0 || needsApproval.length > 0) {
              messages = [...messages.slice(0, -1), {
                ...last,
                proposedLearnings: needsApproval.length > 0 ? d.facts : undefined,
                proposedLearningsWithScores: needsApproval.length > 0 ? needsApproval : undefined,
                autoSavedLearnings: autoSaved.length > 0 ? d.auto_saved : undefined,
                autoSavedWithScores: autoSaved.length > 0 ? autoSaved : undefined,
              }];
            }
          }).catch(() => {});

          // Smart follow-ups (delayed slightly to avoid race with extract-context)
          setTimeout(() => {
            fetch(`/api/projects/${projectSlug}/suggest-followups`, {
              method: 'POST', headers: { ..._headers(), 'Content-Type': 'application/json' },
              body: JSON.stringify({ question: lastUserMsg, answer: lastAssistantMsg })
            }).then(r => r.json()).then(d => {
              if (d.suggestions?.length) {
                const last = messages[messages.length - 1];
                if (last?.role === 'assistant') {
                  messages = [...messages.slice(0, -1), { ...last, suggestions: d.suggestions }];
                }
              }
            }).catch(() => {});
          }, 1000);
        }

        // Fetch quality score after a delay (background scoring takes a moment)
        setTimeout(async () => {
          try {
            const res = await fetch(`/api/projects/${projectSlug}/scores/latest?session_id=${sessionId}`, { headers: _headers() });
            if (res.ok) {
              const d = await res.json();
              if (d.score) {
                const last = messages[messages.length - 1];
                if (last?.role === 'assistant') {
                  messages = [...messages.slice(0, -1), { ...last, qualityScore: d.score }];
                }
              }
            }
          } catch {}
          // Load proactive insights (generated in background after quality scoring)
          loadInsights();
        }, 5000);
      },
      (error) => {
        const last = messages[messages.length - 1];
        if (last?.role === 'assistant') {
          messages = [...messages.slice(0, -1), { ...last, content: `Error: ${error}`, timestamp: getTimestamp(), status: 'error' }];
        }
        isStreaming = false;
        scrollToBottom();
      },
      (tool: ToolCall) => {
        const last = messages[messages.length - 1];
        if (last?.role === 'assistant') {
          const existing = last.toolCalls || [];
          const idx = existing.findIndex(t => t.name === tool.name && t.status === 'running');
          let updated: ToolCall[];
          if (idx >= 0 && tool.status === 'done') {
            updated = [...existing];
            updated[idx] = { ...updated[idx], status: 'done', duration: tool.duration };
          } else if (tool.status === 'running') {
            updated = [...existing, tool];
          } else {
            updated = existing;
          }
          // Capture SQL queries
          const sqls = last.sqlQueries || [];
          if (tool.sqlQuery && !sqls.includes(tool.sqlQuery)) {
            sqls.push(tool.sqlQuery);
          }
          messages = [...messages.slice(0, -1), { ...last, toolCalls: updated, sqlQueries: sqls }];
        }
        scrollToBottom();
      },
      projectSlug,
      reasoningMode,
      analysisType
    );
  }

  function handleKeydown(e: KeyboardEvent) {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); send(); }
  }

  function renderStars(score: number | undefined): string {
    if (!score) return '';
    return '★'.repeat(score) + '☆'.repeat(5 - score);
  }

  function autoResize() {
    if (textareaEl) {
      textareaEl.style.height = 'auto';
      textareaEl.style.height = Math.min(textareaEl.scrollHeight, 120) + 'px';
    }
  }

  let pinned = $state<Record<number, boolean>>({});
  let abortController: AbortController | null = null;

  // Dashboard side panel
  let dashboardPanelOpen = $state(false);
  let activeDashboardId = $state<number | null>(null);

  // Slide Agent panel
  let slidesPanelOpen = $state(false);
  let slidesData = $state<any[]>([]);
  let slidesThinking = $state<any>(null);
  let slidesLoading = $state(false);
  let slidesProgress = $state('');
  let currentSlide = $state(0);

  async function generateSlides() {
    if (messages.length < 2 || slidesLoading) return;
    slidesLoading = true;
    slidesProgress = 'Analyzing conversation...';
    slidesPanelOpen = true;
    slidesData = [];
    currentSlide = 0;

    try {
      const res = await fetch('/api/export/slides-agent', {
        method: 'POST',
        headers: { ..._headers(), 'Content-Type': 'application/json' },
        body: JSON.stringify({
          messages: messages.map(m => ({ role: m.role, content: m.content })),
          title: projectInfo?.agent_name + ' Analysis',
          agent_name: projectInfo?.agent_name || 'Agent'
        })
      });

      if (res.ok) {
        const data = await res.json();
        slidesThinking = data.thinking;
        slidesData = data.slides || [];
        slidesProgress = 'Done';
      } else {
        slidesProgress = 'Failed to generate slides';
      }
    } catch (e) {
      slidesProgress = 'Error generating slides';
    }
    slidesLoading = false;
  }

  $effect(() => {
    const slide = slidesData[currentSlide];
    if (slide?.chart) {
      setTimeout(() => {
        const el = document.getElementById(`slide-chart-${currentSlide}`);
        const echarts = (window as any).echarts;
        if (!el || !echarts) return;
        const existing = echarts.getInstanceByDom(el);
        if (existing) existing.dispose();
        const chart = echarts.init(el);
        const type = slide.chart.type || 'bar';
        const option: any = {
          tooltip: { trigger: 'axis' },
          title: { text: slide.chart.title || '', left: 'center', textStyle: { fontSize: 13 } },
          xAxis: { type: 'category', data: slide.chart.labels || [], axisLabel: { fontSize: 10 } },
          yAxis: { type: 'value' },
          series: [{ type, data: slide.chart.values || [], itemStyle: { color: '#D24726', borderRadius: type === 'bar' ? [4,4,0,0] : undefined }, smooth: type === 'line' }],
          grid: { left: '10%', right: '5%', bottom: '15%', top: '15%' }
        };
        if (type === 'pie') {
          delete option.xAxis; delete option.yAxis;
          option.series = [{ type: 'pie', radius: ['35%','60%'], data: (slide.chart.labels||[]).map((l:string,i:number) => ({name:l, value:(slide.chart.values||[])[i]})) }];
        }
        chart.setOption(option);
      }, 150);
    }
  });

  // Dashboard pin modal
  let showPinModal = $state(false);
  let pinModalData = $state<{msgIndex: number; tables: any[]; content: string} | null>(null);
  let userDashboards = $state<any[]>([]);
  let selectedDashId = $state<number | null>(null);
  let newDashNameForPin = $state('');
  let pinWidgetTitle = $state('');

  async function openPinModal(msgIndex: number, tables: any[], content: string) {
    pinModalData = { msgIndex, tables, content };
    pinWidgetTitle = tables?.[0]?.headers?.join(' / ') || content.slice(0, 50);
    showPinModal = true;
    // Load all dashboards for this project
    try {
      const res = await fetch(`/api/projects/${projectSlug}/dashboards`, { headers: _headers() });
      if (res.ok) { const d = await res.json(); userDashboards = d.dashboards || []; }
    } catch {}
    selectedDashId = userDashboards.length > 0 ? userDashboards[0].id : null;
  }

  async function confirmPin() {
    if (!pinModalData) return;
    const { msgIndex, tables, content } = pinModalData;
    let dashId = selectedDashId;

    // Create new dashboard if needed
    if (!dashId && newDashNameForPin.trim()) {
      try {
        const res = await fetch(`/api/projects/${projectSlug}/dashboards?name=${encodeURIComponent(newDashNameForPin.trim())}`, { method: 'POST', headers: _headers() });
        if (res.ok) { const d = await res.json(); dashId = d.id; }
      } catch {}
    }
    if (!dashId) return;

    // Build widget
    const hasTable = tables?.length > 0 && tables[0].headers?.length > 0;
    const widget = hasTable
      ? { type: 'chart', title: pinWidgetTitle, chartType: 'bar', headers: tables[0].headers, rows: tables[0].rows }
      : { type: 'text', title: pinWidgetTitle, content, full: true };

    await fetch(`/api/projects/${projectSlug}/dashboards/${dashId}/widgets`, {
      method: 'POST', headers: { ..._headers(), 'Content-Type': 'application/json' },
      body: JSON.stringify(widget),
    });
    pinned = { ...pinned, [msgIndex]: true };
    activeDashboardId = dashId;
    dashboardPanelOpen = true;
    showPinModal = false;
    pinModalData = null;
    newDashNameForPin = '';
  }

  // Workflows
  let workflows = $state<{id: number; name: string; description?: string; steps: any[]}[]>([]);
  let workflowPickerOpen = $state(false);

  // Reasoning mode: auto (default), fast, deep
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

  async function loadWorkflows() {
    try {
      const res = await fetch(`/api/workflows?project=${projectSlug}`, { headers: _headers() });
      if (res.ok) {
        const d = await res.json();
        workflows = d.workflows || [];
      }
    } catch {}
  }

  async function runWorkflow(wf: {id: number; name: string; steps: any[]}) {
    workflowPickerOpen = false;
    // Execute each step as a chat message
    const steps = wf.steps || [];
    if (steps.length === 0) {
      send(`Run the "${wf.name}" workflow`);
      return;
    }
    // Send first step, then queue the rest
    for (const step of steps) {
      const stepMsg = typeof step === 'string' ? step : (step.question || step.prompt || step.query || JSON.stringify(step));
      await send(stepMsg);
      // Wait for response to finish
      await new Promise<void>((resolve) => {
        const check = () => {
          if (!isStreaming) resolve();
          else setTimeout(check, 500);
        };
        setTimeout(check, 1000);
      });
    }
  }

  function stopStreaming() {
    if (abortController) {
      abortController.abort();
      abortController = null;
      isStreaming = false;
      const last = messages[messages.length - 1];
      if (last?.role === 'assistant') {
        messages = [...messages.slice(0, -1), { ...last, status: 'done', timestamp: getTimestamp() }];
      }
      textareaEl?.focus();
    }
  }

  function parseClarify(content: string): string[] | null {
    const match = content.match(/\[CLARIFY:\s*(.+?)\]/);
    if (match) return match[1].split('|').map(s => s.trim());
    return null;
  }

  function parseAssumptions(content: string): string[] | null {
    const match = content.match(/\[ASSUMPTIONS:\s*(.+?)\]/s);
    if (match) return match[1].split(/[,;]|\n/).map(s => s.trim()).filter(s => s);
    return null;
  }

  async function pinToDashboard(msgIndex: number, tables: any[], content: string) {
    try {
      // Get or create dashboard
      const listRes = await fetch(`/api/projects/${projectSlug}/dashboards`, { headers: _headers() });
      let dashId: number;
      if (listRes.ok) {
        const data = await listRes.json();
        if (data.dashboards?.length > 0) {
          dashId = data.dashboards[0].id;
        } else {
          const createRes = await fetch(`/api/projects/${projectSlug}/dashboards?name=Dashboard`, { method: 'POST', headers: _headers() });
          const cd = await createRes.json();
          dashId = cd.id;
        }
      } else return;

      // Build widget
      const hasTable = tables && tables.length > 0 && tables[0].headers?.length > 0;
      const widget = hasTable
        ? { type: 'chart', title: tables[0].headers.join(' / '), chartType: 'bar', headers: tables[0].headers, rows: tables[0].rows }
        : { type: 'text', title: content.slice(0, 50) + '...', content, full: true };

      await fetch(`/api/projects/${projectSlug}/dashboards/${dashId}/widgets`, {
        method: 'POST', headers: { ..._headers(), 'Content-Type': 'application/json' },
        body: JSON.stringify(widget),
      });
      pinned = { ...pinned, [msgIndex]: true };
      setTimeout(() => { pinned = { ...pinned, [msgIndex]: false }; }, 2000);
    } catch {}
  }
</script>

<svelte:window onclick={(e) => { const t = (e.target as HTMLElement); if (!t.closest('.mode-selector')) { workflowPickerOpen = false; reasoningDropdownOpen = false; analysisDropdownOpen = false; } }} />

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
            <div style="font-size: 9px; color: var(--color-on-surface-dim);">{formatSessionTime(s.updated_at || s.created_at)}</div>
          </button>
        {/each}
        {#if pastSessions.length === 0}
          <div style="padding: 12px; font-size: 11px; color: var(--color-on-surface-dim); text-align: center;">No sessions yet</div>
        {/if}
      </div>
    </div>
  {/if}

  <!-- Main chat -->
  <div class="flex flex-col" style="flex: 1; min-width: 0; position: relative;">

  <!-- Sidebar toggle (show when sidebar is closed) -->
  {#if !sidebarOpen}
    <button onclick={toggleSidebar} class="sidebar-toggle-btn" title="Show chat history">&raquo;</button>
  {/if}

  <!-- Dashboard panel toggle -->
  <button class="panel-toggle-btn" class:panel-active={dashboardPanelOpen} onclick={() => { dashboardPanelOpen = !dashboardPanelOpen; if (!dashboardPanelOpen) activeDashboardId = null; }} title="Toggle dashboard panel">
    <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="3" width="18" height="18" rx="0"/><line x1="9" y1="3" x2="9" y2="21"/><line x1="9" y1="9" x2="21" y2="9"/></svg>
    DASH
  </button>

  <div class="flex-1 overflow-y-auto" bind:this={messagesEl} style="padding: 20px 20px 16px 20px;">
    <div style="max-width: 820px; margin: 0 auto;">

      {#if messages.length > 0}
        <div class="flex justify-center mb-2 animate-fade-up">
          <div style="font-size: 14px; font-weight: 900; text-transform: uppercase; letter-spacing: 0.08em; color: var(--color-on-surface);">
            {projectInfo?.agent_name?.toUpperCase() || 'AGENT'}
          </div>
        </div>
      {/if}
      {#if sessionStartTime}
        <div class="flex justify-center mb-6 animate-fade-up">
          <div class="tag-label" style="font-size: 10px; padding: 4px 14px; letter-spacing: 0.12em;">
            {projectInfo?.agent_name?.toUpperCase() || 'AGENT'} · {sessionStartTime}
          </div>
        </div>
      {/if}

      {#if messages.length === 0}
        <div class="flex flex-col items-center animate-fade-up" style="padding-top: 60px;">
          <div style="text-align: center; margin-bottom: 40px;">
            <div style="font-size: 42px; font-weight: 900; letter-spacing: -0.02em; color: var(--color-on-surface); line-height: 1;">{projectInfo?.agent_name?.toUpperCase() || 'AGENT'}</div>
            <div style="font-size: 11px; letter-spacing: 0.15em; color: var(--color-on-surface-dim); margin-top: 10px; text-transform: uppercase;">
              {projectInfo?.agent_role || 'Ask me anything about your data'}
            </div>
          </div>
          <!-- Analytics stats -->
          <div style="display: flex; gap: 12px; justify-content: center; margin-bottom: 20px;">
            <div class="ink-border" style="padding: 8px 16px; text-align: center; background: var(--color-surface-bright);">
              <div style="font-size: 18px; font-weight: 900; color: var(--color-primary);">{sessionCount}</div>
              <div style="font-size: 8px; text-transform: uppercase; letter-spacing: 0.1em; color: var(--color-on-surface-dim); font-family: var(--font-family-display);">SESSIONS</div>
            </div>
            <div class="ink-border" style="padding: 8px 16px; text-align: center; background: var(--color-surface-bright);">
              <div style="font-size: 18px; font-weight: 900; color: var(--color-primary);">{avgScore > 0 ? avgScore.toFixed(1) : '--'}</div>
              <div style="font-size: 8px; text-transform: uppercase; letter-spacing: 0.1em; color: var(--color-on-surface-dim); font-family: var(--font-family-display);">AVG QUALITY</div>
            </div>
            <div class="ink-border" style="padding: 8px 16px; text-align: center; background: var(--color-surface-bright);">
              <div style="font-size: 18px; font-weight: 900; color: var(--color-primary);">{memoryCount}</div>
              <div style="font-size: 8px; text-transform: uppercase; letter-spacing: 0.1em; color: var(--color-on-surface-dim); font-family: var(--font-family-display);">MEMORIES</div>
            </div>
          </div>
          <div class="flex flex-wrap justify-center gap-2" style="max-width: 650px;">
            {#each dynamicSuggestions as prompt}
              <button class="prompt-card" onclick={() => send(prompt)} disabled={isStreaming}>{prompt}</button>
            {/each}
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
                          <span class="cli-command">dash exec</span>
                          <span class="cli-output">--agent {projectInfo?.agent_name || 'agent'}{(() => { const m = msg.content?.match(/\[MODE:(\w+)\]/); return m ? ' --' + m[1] : msg.reasoningUsed ? ' --' + msg.reasoningUsed : ''; })()}</span>
                          <span class="cli-success" style="margin-left: auto;">&#10003; {msg.toolCalls.length} steps {getTotalDuration(msg.toolCalls) ? '· ' + getTotalDuration(msg.toolCalls) : ''}{msg.qualityScore ? ' · ' + renderStars(msg.qualityScore) : ''}</span>
                        </div>
                      </button>
                    {:else if msg.status === 'done' && (!msg.toolCalls || msg.toolCalls.length === 0)}
                      <!-- No tools used — show minimal CLI -->
                      <div class="cli-terminal">
                        <div class="cli-line">
                          <span class="cli-prompt">$</span>
                          <span class="cli-command">dash exec</span>
                          <span class="cli-output">--agent {projectInfo?.agent_name || 'agent'}{(() => { const m = msg.content?.match(/\[MODE:(\w+)\]/); return m ? ' --' + m[1] : msg.reasoningUsed ? ' --' + msg.reasoningUsed : ''; })()}</span>
                          <span class="cli-success" style="margin-left: auto;">&#10003; direct response{msg.qualityScore ? ' · ' + renderStars(msg.qualityScore) : ''}</span>
                        </div>
                      </div>
                    {:else}
                      <!-- Expanded / streaming CLI terminal -->
                      <div class="cli-terminal" onclick={() => msg.status === 'done' && toggleWorkflow(i)} style="{msg.status === 'done' ? 'cursor: pointer;' : ''}">
                        <div class="cli-line">
                          <span class="cli-prompt">$</span>
                          <span class="cli-command">dash exec</span>
                          <span class="cli-output">--agent {projectInfo?.agent_name || 'agent'}</span>
                        </div>

                        <!-- Tool calls -->
                        {#if msg.toolCalls && msg.toolCalls.length > 0}
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
                        {:else if msg.status === 'streaming'}
                          <div class="cli-line">
                            <span style="color: #555;">&gt;</span>
                            <span class="cli-output">connecting</span>
                            <span class="cli-spinner"><span></span><span></span><span></span></span>
                          </div>
                        {/if}

                        <!-- Done / cursor -->
                        {#if msg.status === 'done' && msg.toolCalls && msg.toolCalls.length > 0}
                          <div class="cli-line" style="margin-top: 4px;">
                            <span class="cli-prompt">$</span>
                            <span class="cli-success">done</span>
                            <span class="cli-dim">· {msg.toolCalls.length} steps {getTotalDuration(msg.toolCalls) ? '· ' + getTotalDuration(msg.toolCalls) : ''}{msg.qualityScore ? ' · ' + renderStars(msg.qualityScore) : ''}</span>
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
                      {@const chartHint = parseChartHint(msg.content)}
                      {@const currentTab = msg.activeTab || 'insight'}

                      <div class="response-tabs">
                        <button class="response-tab" class:response-tab-active={currentTab === 'insight'} onclick={() => { trackPreference('tab_click', 'insight'); messages = [...messages.slice(0, i), { ...msg, activeTab: 'insight' }, ...messages.slice(i + 1)]; }}>Insight</button>
                        <button class="response-tab" class:response-tab-active={currentTab === 'analysis'} onclick={() => { trackPreference('tab_click', 'analysis'); messages = [...messages.slice(0, i), { ...msg, activeTab: 'analysis' }, ...messages.slice(i + 1)]; }}>Analysis</button>
                        <button class="response-tab" class:response-tab-active={currentTab === 'data'} class:response-tab-dim={!hasTables} onclick={() => { if (hasTables) { trackPreference('tab_click', 'data'); messages = [...messages.slice(0, i), { ...msg, activeTab: 'data' }, ...messages.slice(i + 1)]; } }}>Data{#if hasTables}<span class="tab-badge">{tables[0].rows.length}</span>{/if}</button>
                        <button class="response-tab" class:response-tab-active={currentTab === 'query'} class:response-tab-dim={!hasQueries} onclick={() => { if (hasQueries) { trackPreference('tab_click', 'query'); messages = [...messages.slice(0, i), { ...msg, activeTab: 'query' }, ...messages.slice(i + 1)]; } }}>Query{#if hasQueries}<span class="tab-badge">{msg.sqlQueries?.length}</span>{/if}</button>
                        <button class="response-tab" class:response-tab-active={currentTab === 'graph'} class:response-tab-dim={!hasChartData} onclick={() => { if (hasChartData) { trackPreference('tab_click', 'graph'); messages = [...messages.slice(0, i), { ...msg, activeTab: 'graph', chartType: msg.chartType || chartHint?.type || detectChartType(tables[0]) }, ...messages.slice(i + 1)]; } }}>Graph</button>
                      </div>

                      <!-- TAB: Insight -->
                      {#if currentTab === 'insight'}
                        {@const insightAnalysisMatch = msg.content.match(/\[ANALYSIS:([^\]]+)\]/)}
                        {@const insightAnalysisTypes = insightAnalysisMatch ? insightAnalysisMatch[1].split(',').map((t: string) => t.trim()) : []}
                        {@const modeMatch = msg.content.match(/\[MODE:(\w+)\]/)}
                        {@const actualMode = modeMatch ? modeMatch[1] : msg.reasoningUsed || 'auto'}
                        {@const insightContent = msg.content
                          .replace(/\[ANALYSIS:[^\]]+\]/g, '')
                          .replace(/\[MODE:\w+\]/g, '')
                          .replace(/\[CHART:[^\]]+\]/g, '')
                          .replace(/\[DASHBOARD:\d+\]/g, '')
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
                          <div class="prose-chat">
                            {@html markdownToHtml(insightContent)
                              .replace(/\[UP:([^\]]+)\]/g, '<span style="color: #007518; font-weight: 900;">▲ $1</span>')
                              .replace(/\[DOWN:([^\]]+)\]/g, '<span style="color: #be2d06; font-weight: 900;">▼ $1</span>')
                              .replace(/\[FLAT:([^\]]+)\]/g, '<span style="color: #ff9d00; font-weight: 900;">● $1</span>')
                              .replace(/\[RISK:HIGH\]/g, '<span style="font-size:8px;font-weight:900;padding:1px 6px;background:#be2d06;color:white;">⚠ HIGH</span>')
                              .replace(/\[RISK:MEDIUM\]/g, '<span style="font-size:8px;font-weight:900;padding:1px 6px;background:#ff9d00;color:#383832;">⚠ MEDIUM</span>')
                              .replace(/\[RISK:LOW\]/g, '<span style="font-size:8px;font-weight:900;padding:1px 6px;background:#007518;color:white;">✓ LOW</span>')
                            }
                          </div>

                          <!-- Feedback bar -->
                          <div class="flex items-center justify-between" style="margin-top: 12px; padding-top: 10px; border-top: 1px solid var(--color-on-surface); opacity: 0.6;">
                            <div class="flex items-center gap-2" style="font-size: 10px; text-transform: uppercase; letter-spacing: 0.1em; font-weight: 700;">
                              HELPFUL?
                              <button class="feedback-btn" title="Helpful" onclick={async () => {
                                const q = i > 0 ? messages[i-1]?.content : '';
                                await fetch(`/api/projects/${projectSlug}/feedback`, { method: 'POST', headers: { ..._headers(), 'Content-Type': 'application/json' }, body: JSON.stringify({ question: q, answer: msg.content, rating: 'up' }) });
                                if (msg.sqlQueries?.length) { for (const sql of msg.sqlQueries) { await fetch(`/api/projects/${projectSlug}/save-query-pattern`, { method: 'POST', headers: { ..._headers(), 'Content-Type': 'application/json' }, body: JSON.stringify({ question: q, sql }) }); } }
                              }}><svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M14 9V5a3 3 0 0 0-3-3l-4 9v11h11.28a2 2 0 0 0 2-1.7l1.38-9a2 2 0 0 0-2-2.3zM7 22H4a2 2 0 0 1-2-2v-7a2 2 0 0 1 2-2h3"/></svg></button>
                              <button class="feedback-btn" title="Not helpful" onclick={async () => {
                                const q = i > 0 ? messages[i-1]?.content : '';
                                await fetch(`/api/projects/${projectSlug}/feedback`, { method: 'POST', headers: { ..._headers(), 'Content-Type': 'application/json' }, body: JSON.stringify({ question: q, answer: msg.content, rating: 'down' }) });
                              }}><svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M10 15v4a3 3 0 0 0 3 3l4-9V2H5.72a2 2 0 0 0-2 1.7l-1.38 9a2 2 0 0 0 2 2.3zm7-13h2.67A2.31 2.31 0 0 1 22 4v7a2.31 2.31 0 0 1-2.33 2H17"/></svg></button>
                            </div>
                            <div class="flex items-center gap-2">
                              <button class="feedback-btn flex items-center gap-1" onclick={() => copyMessage(i)} style="font-size: 10px; text-transform: uppercase; letter-spacing: 0.1em; font-weight: 700;">
                                <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="9" y="9" width="13" height="13" rx="0"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/></svg>
                                {copiedIndex === i ? 'COPIED' : 'COPY'}
                              </button>
                              <button class="feedback-btn flex items-center gap-1" onclick={() => {
                                const fact = prompt('Save a fact the agent should remember:', '');
                                if (fact) { fetch(`/api/projects/${projectSlug}/memories`, { method: 'POST', headers: { ..._headers(), 'Content-Type': 'application/json' }, body: JSON.stringify({ fact, scope: 'project' }) }); }
                              }} style="font-size: 10px; text-transform: uppercase; letter-spacing: 0.1em; font-weight: 700;">
                                <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 2v10M12 12l4-4M12 12l-4-4M5 17h14M5 21h14"/></svg>
                                SAVE
                              </button>
                              {#if hasTables}
                                <button class="feedback-btn flex items-center gap-1" onclick={() => {
                                  const csv = tableToCsv(tables[0]);
                                  const blob = new Blob([csv], { type: 'text/csv' });
                                  const url = URL.createObjectURL(blob);
                                  const a = document.createElement('a'); a.href = url; a.download = `dash-export-${Date.now()}.csv`; a.click(); URL.revokeObjectURL(url);
                                }} style="font-size: 10px; text-transform: uppercase; letter-spacing: 0.1em; font-weight: 700;">
                                  <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>
                                  CSV
                                </button>
                              {/if}
                              <button class="feedback-btn flex items-center gap-1" onclick={() => openPinModal(i, tables, msg.content)} style="font-size: 10px; text-transform: uppercase; letter-spacing: 0.1em; font-weight: 700;">
                                <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 2v10M12 12l4-4M12 12l-4-4M5 17h14M5 21h14"/></svg>
                                {pinned[i] ? 'PINNED' : 'PIN'}
                              </button>
                              <button class="feedback-btn flex items-center gap-1" onclick={async () => {
                                try {
                                  const res = await fetch('/api/export/pdf', { method: 'POST', headers: { ..._headers(), 'Content-Type': 'application/json' }, body: JSON.stringify({ content: msg.content, title: projectInfo?.agent_name || 'Report' }) });
                                  if (res.ok) { const blob = await res.blob(); const url = URL.createObjectURL(blob); const a = document.createElement('a'); a.href = url; a.download = `dash-report-${Date.now()}.pdf`; a.click(); URL.revokeObjectURL(url); }
                                } catch {}
                              }} style="font-size: 10px; text-transform: uppercase; letter-spacing: 0.1em; font-weight: 700;">
                                <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/></svg>
                                PDF
                              </button>
                            </div>
                          </div>
                        </div>

                      <!-- TAB: Analysis -->
                      {:else if currentTab === 'analysis'}
                        <div class="bubble-assistant">
                          <div class="prose-chat">
                            {@html markdownToHtml(msg.content.replace(/\[DASHBOARD:\d+\]/g, '').replace(/\[CHART:[^\]]+\]/g, '').replace(/\[ANALYSIS:[^\]]+\]/g, '').replace(/\[MODE:\w+\]/g, '').replace(/\[(UP|DOWN|FLAT|RISK):[^\]]*\]/g, ''))}
                          </div>

                          <!-- Clarifying Questions -->
                          {#if parseClarify(msg.content)}
                            <div class="flex flex-wrap gap-2 mt-3" style="padding-top: 8px; border-top: 1px dashed var(--color-on-surface);">
                              <span style="font-size: 9px; font-weight: 900; text-transform: uppercase; color: var(--color-on-surface-dim); width: 100%;">DID YOU MEAN:</span>
                              {#each parseClarify(msg.content) || [] as option}
                                <button class="suggestion-btn" onclick={() => send(option)} disabled={isStreaming}>{option}</button>
                              {/each}
                            </div>
                          {/if}

                          <!-- Feedback bar -->
                          <div class="flex items-center justify-between" style="margin-top: 12px; padding-top: 10px; border-top: 1px solid var(--color-on-surface); opacity: 0.6;">
                            <div class="flex items-center gap-2" style="font-size: 10px; text-transform: uppercase; letter-spacing: 0.1em; font-weight: 700;">
                              HELPFUL?
                              <button class="feedback-btn" title="Helpful" onclick={async () => {
                                const q = i > 0 ? messages[i-1]?.content : '';
                                await fetch(`/api/projects/${projectSlug}/feedback`, { method: 'POST', headers: { ..._headers(), 'Content-Type': 'application/json' }, body: JSON.stringify({ question: q, answer: msg.content, rating: 'up' }) });
                                if (msg.sqlQueries?.length) { for (const sql of msg.sqlQueries) { await fetch(`/api/projects/${projectSlug}/save-query-pattern`, { method: 'POST', headers: { ..._headers(), 'Content-Type': 'application/json' }, body: JSON.stringify({ question: q, sql }) }); } }
                              }}><svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M14 9V5a3 3 0 0 0-3-3l-4 9v11h11.28a2 2 0 0 0 2-1.7l1.38-9a2 2 0 0 0-2-2.3zM7 22H4a2 2 0 0 1-2-2v-7a2 2 0 0 1 2-2h3"/></svg></button>
                              <button class="feedback-btn" title="Not helpful" onclick={async () => {
                                const q = i > 0 ? messages[i-1]?.content : '';
                                await fetch(`/api/projects/${projectSlug}/feedback`, { method: 'POST', headers: { ..._headers(), 'Content-Type': 'application/json' }, body: JSON.stringify({ question: q, answer: msg.content, rating: 'down' }) });
                              }}><svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M10 15v4a3 3 0 0 0 3 3l4-9V2H5.72a2 2 0 0 0-2 1.7l-1.38 9a2 2 0 0 0 2 2.3zm7-13h2.67A2.31 2.31 0 0 1 22 4v7a2.31 2.31 0 0 1-2.33 2H17"/></svg></button>
                            </div>
                            <div class="flex items-center gap-2">
                              <button class="feedback-btn flex items-center gap-1" onclick={() => copyMessage(i)} style="font-size: 10px; text-transform: uppercase; letter-spacing: 0.1em; font-weight: 700;">
                                <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="9" y="9" width="13" height="13" rx="0"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/></svg>
                                {copiedIndex === i ? 'COPIED' : 'COPY'}
                              </button>
                              <button class="feedback-btn flex items-center gap-1" onclick={() => {
                                const fact = prompt('Save a fact the agent should remember:', '');
                                if (fact) { fetch(`/api/projects/${projectSlug}/memories`, { method: 'POST', headers: { ..._headers(), 'Content-Type': 'application/json' }, body: JSON.stringify({ fact, scope: 'project' }) }); }
                              }} style="font-size: 10px; text-transform: uppercase; letter-spacing: 0.1em; font-weight: 700;">
                                <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 2v10M12 12l4-4M12 12l-4-4M5 17h14M5 21h14"/></svg>
                                SAVE
                              </button>
                              {#if hasTables}
                                <button class="feedback-btn flex items-center gap-1" onclick={() => {
                                  const csv = tableToCsv(tables[0]);
                                  const blob = new Blob([csv], { type: 'text/csv' });
                                  const url = URL.createObjectURL(blob);
                                  const a = document.createElement('a'); a.href = url; a.download = `dash-export-${Date.now()}.csv`; a.click(); URL.revokeObjectURL(url);
                                }} style="font-size: 10px; text-transform: uppercase; letter-spacing: 0.1em; font-weight: 700;">
                                  <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>
                                  CSV
                                </button>
                              {/if}
                              <button class="feedback-btn flex items-center gap-1" onclick={() => openPinModal(i, tables, msg.content)} style="font-size: 10px; text-transform: uppercase; letter-spacing: 0.1em; font-weight: 700;">
                                <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 2v10M12 12l4-4M12 12l-4-4M5 17h14M5 21h14"/></svg>
                                {pinned[i] ? 'PINNED' : 'PIN'}
                              </button>
                              <button class="feedback-btn flex items-center gap-1" onclick={async () => {
                                try {
                                  const res = await fetch('/api/export/pdf', { method: 'POST', headers: { ..._headers(), 'Content-Type': 'application/json' }, body: JSON.stringify({ content: msg.content, title: projectInfo?.agent_name || 'Report' }) });
                                  if (res.ok) { const blob = await res.blob(); const url = URL.createObjectURL(blob); const a = document.createElement('a'); a.href = url; a.download = `dash-report-${Date.now()}.pdf`; a.click(); URL.revokeObjectURL(url); }
                                } catch {}
                              }} style="font-size: 10px; text-transform: uppercase; letter-spacing: 0.1em; font-weight: 700;">
                                <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/></svg>
                                PDF
                              </button>
                            </div>
                          </div>
                        </div>

                      <!-- TAB: Data -->
                      {:else if currentTab === 'data' && hasTables}
                        <div class="bubble-assistant">
                          <div style="font-size: 10px; font-weight: 900; text-transform: uppercase; letter-spacing: 0.1em; margin-bottom: 8px; color: var(--color-on-surface-dim);">
                            {tables[0].rows.length} ROWS &middot; {tables[0].headers.length} COLUMNS
                          </div>
                          <div style="overflow-x: auto;">
                            <table class="data-table">
                              <thead>
                                <tr>
                                  <th style="width: 36px; text-align: center; color: var(--color-on-surface-dim);">#</th>
                                  {#each tables[0].headers as h}
                                    <th>{h}</th>
                                  {/each}
                                </tr>
                              </thead>
                              <tbody>
                                {#each tables[0].rows as row, ri}
                                  <tr>
                                    <td style="text-align: center; color: var(--color-on-surface-dim); font-size: 10px;">{ri + 1}</td>
                                    {#each row as cell}
                                      <td>{cell}</td>
                                    {/each}
                                  </tr>
                                {/each}
                              </tbody>
                            </table>
                          </div>
                          <div class="flex gap-2 mt-3">
                            <button class="feedback-btn flex items-center gap-1" onclick={() => {
                              const csv = tableToCsv(tables[0]);
                              const blob = new Blob([csv], { type: 'text/csv' });
                              const url = URL.createObjectURL(blob); const a = document.createElement('a'); a.href = url; a.download = `dash-export-${Date.now()}.csv`; a.click(); URL.revokeObjectURL(url);
                            }} style="font-size: 10px; font-weight: 700; text-transform: uppercase; padding: 4px 10px;">DOWNLOAD CSV</button>
                            <button class="feedback-btn flex items-center gap-1" onclick={() => openPinModal(i, tables, msg.content)} style="font-size: 10px; font-weight: 700; text-transform: uppercase; padding: 4px 10px;">{pinned[i] ? 'PINNED' : 'PIN TO DASHBOARD'}</button>
                          </div>
                        </div>

                      <!-- TAB: Query -->
                      {:else if currentTab === 'query' && hasQueries}
                        <div class="cli-terminal" style="padding: 14px;">
                          <div class="cli-line" style="margin-bottom: 10px;">
                            <span class="cli-prompt">$</span>
                            <span class="cli-command">cat query.sql</span>
                            <span class="cli-dim" style="margin-left: auto;">{msg.sqlQueries?.length} {(msg.sqlQueries?.length || 0) === 1 ? 'query' : 'queries'}</span>
                          </div>
                          {#each msg.sqlQueries || [] as sql, si}
                            {#if si > 0}<div style="border-top: 1px solid #333; margin: 12px 0;"></div>{/if}
                            <div class="cli-line" style="margin-bottom: 4px;">
                              <span class="cli-dim">-- query {si + 1}</span>
                            </div>
                            <pre style="margin: 0; font-family: 'Space Grotesk', monospace; font-size: 12px; color: #e0e0e0; white-space: pre-wrap; word-break: break-all; line-height: 1.5;">{sql}</pre>
                          {/each}
                          <div style="margin-top: 12px; border-top: 1px solid #333; padding-top: 8px;">
                            <button class="feedback-btn" onclick={() => {
                              const allSql = (msg.sqlQueries || []).join('\n\n');
                              navigator.clipboard.writeText(allSql);
                            }} style="font-size: 10px; font-weight: 700; text-transform: uppercase; padding: 4px 10px; color: #00fc40;">COPY SQL</button>
                          </div>
                        </div>

                      <!-- TAB: Graph -->
                      {:else if currentTab === 'graph' && hasChartData}
                        <div class="bubble-assistant" style="padding: 12px;">
                          {#if chartHint?.title}
                            <div style="font-size: 12px; font-weight: 900; text-transform: uppercase; letter-spacing: 0.05em; margin-bottom: 8px; color: var(--color-on-surface);">{chartHint.title}</div>
                          {/if}
                          <div class="flex gap-0 mb-2">
                            {#each getAvailableTypes(tables[0]) as ct}
                              <button
                                class="chart-type-btn"
                                class:chart-type-btn-active={(msg.chartType || chartHint?.type || detectChartType(tables[0])) === ct}
                                onclick={() => { trackPreference('chart_type', ct); messages = [...messages.slice(0, i), { ...msg, chartType: ct }, ...messages.slice(i + 1)]; }}
                              >{ct.toUpperCase()}</button>
                            {/each}
                          </div>
                          <div style="background: var(--color-surface-bright); padding: 8px; border: 2px solid var(--color-on-surface);">
                            <EChartView headers={tables[0].headers} rows={tables[0].rows} chartType={msg.chartType || chartHint?.type || detectChartType(tables[0])} />
                          </div>
                          <div class="flex gap-2 mt-3">
                            <button class="feedback-btn flex items-center gap-1" onclick={() => openPinModal(i, tables, msg.content)} style="font-size: 10px; font-weight: 700; text-transform: uppercase; padding: 4px 10px;">{pinned[i] ? 'PINNED' : 'PIN TO DASHBOARD'}</button>
                          </div>
                        </div>
                      {/if}

                    <!-- Still streaming — show content normally -->
                    {:else}
                      <div class="bubble-assistant">
                        {#if msg.content}
                          <div class="prose-chat">
                            {@html markdownToHtml(msg.content)}
                          </div>
                          {#if msg.status === 'streaming'}
                            <div class="flex items-center gap-2" style="margin-top: 8px;"><svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="var(--color-primary)" stroke-width="2" style="animation: headerFloat 2s ease-in-out infinite; flex-shrink: 0;"><rect x="3" y="11" width="18" height="10"/><path d="M12 2v4"/><circle cx="12" cy="7" r="1"/></svg><div class="typing-indicator"><span></span><span></span><span></span></div></div>
                          {/if}
                        {:else if msg.status === 'streaming'}
                          <div class="flex items-center gap-2"><svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="var(--color-primary)" stroke-width="2" style="animation: headerFloat 2s ease-in-out infinite;"><rect x="3" y="11" width="18" height="10"/><path d="M12 2v4"/><circle cx="12" cy="7" r="1"/></svg><div class="typing-indicator"><span></span><span></span><span></span></div></div>
                        {/if}
                      </div>
                    {/if}

                    <!-- Trace toggle (always available when done) -->
                    {#if msg.status === 'done'}
                      <button class="cli-terminal" style="cursor: pointer; width: 100%; text-align: left; margin-top: 8px; padding: 6px 14px;" onclick={() => { messages = [...messages.slice(0, i), { ...msg, showTrace: !msg.showTrace }, ...messages.slice(i + 1)]; }}>
                        <div class="cli-line">
                          <span class="cli-prompt">$</span>
                          <span class="cli-command">trace</span>
                          <span class="cli-dim" style="margin-left: auto;">{msg.showTrace ? '▲' : '▼'}</span>
                        </div>
                      </button>
                      {#if msg.showTrace}
                        <TracePanel toolCalls={msg.toolCalls || []} agentName={projectInfo?.agent_name || 'Agent'} qualityScore={msg.qualityScore} />
                      {/if}
                    {/if}

                    {#if msg.timestamp}
                      <div style="font-size: 10px; color: var(--color-on-surface-dim); margin-top: 4px; letter-spacing: 0.05em; text-transform: uppercase;">
                        {msg.timestamp} &middot; Agent
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

                    <!-- Learning approval card (low confidence — needs user approval) -->
                    {#if msg.status === 'done' && msg.proposedLearnings && msg.proposedLearnings.length > 0 && !msg.learningsSaved}
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
                            await fetch(`/api/projects/${projectSlug}/approve-learnings`, {
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

  <!-- Proactive Insight Cards -->
  {#if insights.length > 0}
    <div style="max-width: 1100px; margin: 0 auto; padding: 4px 20px;">
      <div style="display: flex; flex-direction: column; gap: 3px;">
        {#each insights as ins}
          <div style="display: flex; align-items: center; gap: 8px; padding: 5px 10px; border-left: 3px solid {ins.severity === 'critical' ? 'var(--color-error)' : ins.severity === 'warning' ? '#c59000' : 'var(--color-primary)'}; background: {ins.severity === 'critical' ? '#fde8e4' : ins.severity === 'warning' ? '#fff8e1' : '#e8f5e9'};">
            <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="{ins.severity === 'critical' ? 'var(--color-error)' : ins.severity === 'warning' ? '#c59000' : 'var(--color-primary)'}" stroke-width="2.5" style="flex-shrink: 0;"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>
            <span style="flex: 1; font-size: 10px; font-family: var(--font-family-display); overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">{ins.insight}</span>
            <button onclick={() => send(`Investigate: ${ins.insight}`)} style="font-size: 8px; font-weight: 900; text-transform: uppercase; padding: 2px 6px; border: 1px solid var(--color-on-surface); background: var(--color-surface); cursor: pointer; white-space: nowrap; font-family: var(--font-family-display);" disabled={isStreaming}>ASK</button>
            <button onclick={() => dismissInsight(ins.id)} style="background: none; border: none; cursor: pointer; font-size: 12px; color: var(--color-on-surface-dim); padding: 0; line-height: 1;">&times;</button>
          </div>
        {/each}
      </div>
    </div>
  {/if}

  <div class="input-bar shrink-0">
    <div style="max-width: 1100px; margin: 0 auto; padding: 12px 20px;">
      <div class="flex gap-1 items-stretch">
        <!-- Workflow picker — PURPLE -->
        <div class="mode-selector">
          <button class="mode-selector-btn" style="background: #7c3aed22; color: #7c3aed; border-color: #7c3aed; height: 34px; margin-right: 0; padding: 0 6px; font-size: 9px;" onclick={() => { if (workflows.length === 0) loadWorkflows(); workflowPickerOpen = !workflowPickerOpen; }} disabled={isStreaming} title="Workflow">
            <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="6" cy="6" r="2"/><circle cx="18" cy="6" r="2"/><circle cx="6" cy="18" r="2"/><circle cx="18" cy="18" r="2"/><path d="M8 6h8M6 8v8M18 8v8M8 18h8"/></svg>
            <span style="font-size: 9px;">Flow</span>
            <span class="mode-arrow" style="font-size: 7px;">&#9660;</span>
          </button>
          {#if workflowPickerOpen}
            <div class="mode-dropdown" style="min-width: 280px;">
              {#if workflows.length === 0}
                <div style="padding: 14px; font-size: 11px; color: var(--color-on-surface-dim); text-align: center;">No workflows yet. Train your project to auto-generate workflows.</div>
              {:else}
                {#each workflows as wf}
                  <button class="mode-dropdown-item" onclick={() => runWorkflow(wf)}>
                    <div>
                      <div style="font-weight: 900;">{wf.name}</div>
                      {#if wf.description}
                        <span class="mode-dropdown-label">{wf.description}</span>
                      {/if}
                      <span class="mode-dropdown-label">{wf.steps?.length || 0} steps</span>
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

        <!-- Text input -->
        <div style="flex: 1;">
          <textarea bind:this={textareaEl} bind:value={inputText} onkeydown={handleKeydown} oninput={autoResize} placeholder="Ask {projectInfo?.agent_name || 'Agent'} a question..." rows="1" disabled={isStreaming} style="height: 34px; min-height: 34px; font-size: 12px;"></textarea>
        </div>

        <!-- Send / Stop button -->
        {#if isStreaming}
          <button onclick={stopStreaming} title="Stop" style="height: 34px; width: 34px; padding: 0; border: 2px solid var(--color-error); background: none; cursor: pointer; display: flex; align-items: center; justify-content: center;">
            <svg width="12" height="12" viewBox="0 0 24 24" fill="var(--color-error)"><rect x="4" y="4" width="16" height="16" rx="2"/></svg>
          </button>
        {:else}
          <button class="send-btn" onclick={() => send()} disabled={!inputText.trim()} title="Send" style="height: 34px; width: 34px; padding: 0;">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><line x1="22" y1="2" x2="11" y2="13"/><polygon points="22 2 15 22 11 13 2 9 22 2"/></svg>
          </button>
        {/if}
        <!-- Slide Agent button -->
        <button onclick={generateSlides} disabled={messages.length < 2 || slidesLoading} title="Create Presentation" style="height: 34px; width: 34px; padding: 0; border: 2px solid {messages.length >= 2 ? '#D24726' : '#ccc'}; background: {messages.length >= 2 ? '#D2472610' : 'none'}; cursor: {messages.length >= 2 ? 'pointer' : 'default'}; display: flex; align-items: center; justify-content: center; flex-shrink: 0;">
          <svg width="18" height="18" viewBox="0 0 24 24">
            <defs>
              <linearGradient id="pptGrad" x1="0" y1="0" x2="1" y2="1">
                <stop offset="0%" stop-color="#D24726"/>
                <stop offset="50%" stop-color="#E5682A"/>
                <stop offset="100%" stop-color="#F0A030"/>
              </linearGradient>
            </defs>
            <rect x="2" y="2" width="20" height="20" rx="4" fill="url(#pptGrad)"/>
            <text x="12" y="16" text-anchor="middle" fill="white" font-size="13" font-weight="900" font-family="Arial">P</text>
          </svg>
        </button>
      </div>
    </div>
    <div style="text-align: center; font-size: 9px; color: var(--color-on-surface-dim); padding: 0 20px 8px; text-transform: uppercase; letter-spacing: 0.1em;">
      <button onclick={async () => {
        if (messages.length < 2) return;
        const res = await fetch('/api/export/report-from-chat', {
          method: 'POST', headers: { ..._headers(), 'Content-Type': 'application/json' },
          body: JSON.stringify({ messages: messages.map(m => ({ role: m.role, content: m.content })), title: projectInfo?.agent_name + ' Report' })
        });
        if (res.ok) { const blob = await res.blob(); const url = URL.createObjectURL(blob); const a = document.createElement('a'); a.href = url; a.download = `report-${Date.now()}.pdf`; a.click(); URL.revokeObjectURL(url); }
      }} style="background: none; border: none; cursor: pointer; font-size: 9px; color: var(--color-on-surface-dim); font-family: var(--font-family-display); text-transform: uppercase; letter-spacing: 0.1em; text-decoration: underline;">GENERATE REPORT</button>
      <button onclick={async () => {
        const res = await fetch('/api/export/pptx-from-chat', {
          method: 'POST', headers: { ..._headers(), 'Content-Type': 'application/json' },
          body: JSON.stringify({ messages: messages.map(m => ({ role: m.role, content: m.content })), title: projectInfo?.agent_name + ' Analysis' })
        });
        if (res.ok) { const blob = await res.blob(); const url = URL.createObjectURL(blob); const a = document.createElement('a'); a.href = url; a.download = `${projectInfo?.agent_name || 'analysis'}-${Date.now()}.pptx`; a.click(); URL.revokeObjectURL(url); }
      }} style="background: none; border: none; cursor: pointer; font-size: 9px; color: var(--color-on-surface-dim); font-family: var(--font-family-display); text-transform: uppercase; letter-spacing: 0.1em; text-decoration: underline; margin-left: 6px;">CREATE PPTX</button>
      <button onclick={async () => {
        const res = await fetch('/api/export/slides-from-chat', {
          method: 'POST', headers: { ..._headers(), 'Content-Type': 'application/json' },
          body: JSON.stringify({ messages: messages.map(m => ({ role: m.role, content: m.content })), title: projectInfo?.agent_name + ' Analysis', agent_name: projectInfo?.agent_name || 'Agent' })
        });
        if (res.ok) { const blob = await res.blob(); const url = URL.createObjectURL(blob); window.open(url, '_blank'); }
      }} style="background: none; border: none; cursor: pointer; font-size: 9px; color: var(--color-primary); font-family: var(--font-family-display); text-transform: uppercase; letter-spacing: 0.1em; text-decoration: underline; margin-left: 6px; font-weight: 900;">PRESENT</button>
      <span style="margin-left: 8px;">{projectInfo?.agent_name?.toUpperCase() || 'AGENT'} CAN MAKE MISTAKES.</span>
    </div>
  </div>
</div>

  <!-- Slide Panel -->
  {#if slidesPanelOpen}
  <div style="position: fixed; top: 0; right: 0; width: 50%; height: 100vh; background: var(--color-surface); border-left: 3px solid var(--color-on-surface); z-index: 90; display: flex; flex-direction: column; box-shadow: -4px 0 20px rgba(0,0,0,0.2);">
    <!-- Header -->
    <div style="padding: 12px 16px; border-bottom: 2px solid var(--color-on-surface); display: flex; align-items: center; justify-content: space-between; background: var(--color-surface-bright);">
      <div style="display: flex; align-items: center; gap: 8px;">
        <svg width="20" height="20" viewBox="0 0 24 24"><rect x="2" y="2" width="20" height="20" rx="4" fill="#D24726"/><text x="12" y="16" text-anchor="middle" fill="white" font-size="12" font-weight="900" font-family="Arial">P</text></svg>
        <span style="font-size: 12px; font-weight: 900; text-transform: uppercase; letter-spacing: 0.05em;">PRESENTATION</span>
        {#if slidesData.length > 0}
          <span style="font-size: 10px; color: var(--color-on-surface-dim);">{currentSlide + 1} / {slidesData.length}</span>
        {/if}
      </div>
      <div style="display: flex; gap: 6px; align-items: center;">
        {#if slidesData.length > 0}
          <button onclick={() => { const w = window.open('', '_blank'); if (w) { w.document.write('<html><head><title>Slides</title><script src="https://cdn.jsdelivr.net/npm/echarts@5/dist/echarts.min.js"><\/script></head><body>' + document.querySelector('.slide-render-area')?.innerHTML + '</body></html>'); w.document.close(); }}} style="font-size: 9px; font-weight: 900; padding: 4px 8px; border: 1px solid var(--color-on-surface); background: none; cursor: pointer; text-transform: uppercase;">Fullscreen</button>
        {/if}
        <button onclick={() => slidesPanelOpen = false} style="background: none; border: none; cursor: pointer; font-size: 18px; font-weight: 900; color: var(--color-on-surface);">&#x2715;</button>
      </div>
    </div>

    <!-- Loading state -->
    {#if slidesLoading}
      <div style="flex: 1; display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 16px;">
        <svg width="24" height="24" viewBox="0 0 24 24"><rect x="2" y="2" width="20" height="20" rx="4" fill="#D24726"/><text x="12" y="16" text-anchor="middle" fill="white" font-size="12" font-weight="900" font-family="Arial">P</text></svg>
        <div style="font-size: 12px; font-weight: 900; text-transform: uppercase;">{slidesProgress}</div>
        <div style="width: 200px; height: 4px; background: var(--color-surface-dim); border: 1px solid var(--color-on-surface-dim);">
          <div style="height: 100%; background: #D24726; width: {slidesProgress.includes('Analyz') ? '33' : slidesProgress.includes('Structur') ? '66' : slidesProgress.includes('Done') ? '100' : '15'}%; transition: width 0.5s;"></div>
        </div>
      </div>

    <!-- Thinking summary + slides -->
    {:else if slidesThinking && slidesData.length > 0}
      <div style="flex: 1; overflow-y: auto;" class="slide-render-area">
        <!-- Thinking bar -->
        <div style="padding: 8px 16px; background: #FFF8E1; border-bottom: 1px solid #FFE082; font-size: 10px;">
          <strong>NARRATIVE:</strong> {slidesThinking.narrative || ''}
          {#if slidesThinking.key_insight} &middot; <strong>KEY INSIGHT:</strong> {slidesThinking.key_insight}{/if}
        </div>

        <!-- Current slide -->
        {#if slidesData[currentSlide]}
          {@const slide = slidesData[currentSlide]}
          <div style="padding: 30px; min-height: 400px;">
            <!-- Title -->
            <h2 style="font-size: 24px; font-weight: 900; margin-bottom: 16px; color: #1a1a1a;">{slide.title || ''}</h2>

            {#if slide.layout === 'title'}
              <div style="display: flex; flex-direction: column; align-items: center; justify-content: center; height: 300px;">
                <div style="font-size: 36px; font-weight: 900; text-align: center;">{slide.title}</div>
                <div style="font-size: 16px; color: #666; margin-top: 12px; text-align: center;">{slide.bullets?.join(' · ') || ''}</div>
              </div>

            {:else if slide.layout === 'kpi' && slide.kpi}
              <div style="display: flex; align-items: center; justify-content: center; height: 200px; gap: 40px;">
                <div style="text-align: center;">
                  <div style="font-size: 56px; font-weight: 900;">{slide.kpi.value}</div>
                  <div style="font-size: 14px; color: #666; margin-top: 4px;">{slide.kpi.label}</div>
                  {#if slide.kpi.change}
                    <div style="font-size: 20px; font-weight: 700; color: {slide.kpi.change?.startsWith('+') ? '#00c853' : '#ff1744'}; margin-top: 4px;">{slide.kpi.change}</div>
                  {/if}
                </div>
              </div>
              {#each (slide.bullets || []) as b}
                <div style="font-size: 13px; color: #555; padding: 6px 12px; border-left: 3px solid #D24726; margin-bottom: 6px; background: #fafaf8;">&middot; {b}</div>
              {/each}

            {:else if slide.chart}
              <div style="display: flex; gap: 20px;">
                <div id="slide-chart-{currentSlide}" style="flex: 1; height: 280px;"></div>
                <div style="flex: 0 0 200px;">
                  {#each (slide.bullets || []) as b}
                    <div style="font-size: 12px; color: #333; padding: 8px; border-left: 3px solid #D24726; margin-bottom: 8px; background: #fafaf8;">{b}</div>
                  {/each}
                </div>
              </div>

            {:else if slide.table}
              <div style="overflow-x: auto;">
                <table style="width: 100%; border-collapse: collapse; font-size: 12px;">
                  <thead>
                    <tr>
                      {#each (slide.table.headers || []) as h}
                        <th style="padding: 8px 12px; text-align: left; border-bottom: 2px solid #1a1a1a; font-size: 10px; text-transform: uppercase; letter-spacing: 1px; color: #666;">{h}</th>
                      {/each}
                    </tr>
                  </thead>
                  <tbody>
                    {#each (slide.table.rows || []).slice(0, 10) as row, ri}
                      <tr style="background: {ri % 2 === 0 ? '#fafaf8' : '#fff'};">
                        {#each row as cell}
                          <td style="padding: 6px 12px; border-bottom: 1px solid #eee;">{cell}</td>
                        {/each}
                      </tr>
                    {/each}
                  </tbody>
                </table>
              </div>
              {#each (slide.bullets || []) as b}
                <div style="font-size: 12px; color: #555; margin-top: 8px;">&middot; {b}</div>
              {/each}

            {:else}
              <!-- bullets/summary layout -->
              {#each (slide.bullets || []) as b}
                <div style="font-size: 14px; color: #333; padding: 10px 14px; border-left: 4px solid #D24726; margin-bottom: 8px; background: #fafaf8;">{b}</div>
              {/each}
            {/if}

            <!-- So what -->
            {#if slide.so_what}
              <div style="margin-top: 20px; padding: 10px 14px; background: #E3F2FD; border-left: 4px solid #1976D2; font-size: 12px; font-weight: 700; color: #1565C0;">
                SO WHAT: {slide.so_what}
              </div>
            {/if}
          </div>
        {/if}
      </div>

      <!-- Navigation -->
      <div style="padding: 10px 16px; border-top: 2px solid var(--color-on-surface); display: flex; align-items: center; justify-content: space-between; background: var(--color-surface-bright);">
        <button onclick={() => currentSlide = Math.max(0, currentSlide - 1)} disabled={currentSlide === 0} style="font-size: 10px; font-weight: 900; padding: 4px 12px; border: 1px solid var(--color-on-surface); background: none; cursor: pointer;">&#x2190; PREV</button>
        <div style="display: flex; gap: 4px;">
          {#each slidesData as _, si}
            <button onclick={() => currentSlide = si} style="width: 8px; height: 8px; border-radius: 50%; border: 1px solid #999; background: {si === currentSlide ? '#D24726' : 'none'}; cursor: pointer; padding: 0;"></button>
          {/each}
        </div>
        <button onclick={() => currentSlide = Math.min(slidesData.length - 1, currentSlide + 1)} disabled={currentSlide >= slidesData.length - 1} style="font-size: 10px; font-weight: 900; padding: 4px 12px; border: 1px solid var(--color-on-surface); background: none; cursor: pointer;">NEXT &#x2192;</button>
      </div>

    {:else}
      <div style="flex: 1; display: flex; align-items: center; justify-content: center; color: var(--color-on-surface-dim); font-size: 12px;">No slides generated</div>
    {/if}
  </div>
  {/if}

  <!-- Dashboard Side Panel -->
  {#if dashboardPanelOpen}
    <DashboardPanel
      dashboardId={activeDashboardId}
      projectSlug={projectSlug}
      onClose={() => { dashboardPanelOpen = false; activeDashboardId = null; }}
      onSelectDashboard={(id) => { activeDashboardId = id || null; }}
    />
  {/if}
</div>

<!-- Pin to Dashboard Modal -->
{#if showPinModal}
  <!-- svelte-ignore a11y_no_static_element_interactions -->
  <div style="position: fixed; inset: 0; background: rgba(0,0,0,0.5); z-index: 200; display: flex; align-items: center; justify-content: center;" onclick={(e) => { if (e.target === e.currentTarget) showPinModal = false; }}>
    <div class="ink-border stamp-shadow" style="background: var(--color-surface); width: 400px;">
      <div class="dark-title-bar" style="padding: 8px 14px; font-size: 11px;">PIN TO DASHBOARD</div>
      <div style="padding: 16px;">

        <!-- Widget title -->
        <div style="font-size: 9px; font-weight: 700; text-transform: uppercase; margin-bottom: 3px;">WIDGET TITLE</div>
        <input type="text" bind:value={pinWidgetTitle} style="width: 100%; border: 2px solid var(--color-on-surface); padding: 6px 10px; font-family: var(--font-family-display); font-size: 12px; background: var(--color-surface); margin-bottom: 12px;" />

        <!-- Select dashboard -->
        <div style="font-size: 9px; font-weight: 700; text-transform: uppercase; margin-bottom: 6px;">SELECT DASHBOARD</div>
        {#if userDashboards.length > 0}
          <div style="display: flex; flex-direction: column; gap: 4px; margin-bottom: 12px; max-height: 150px; overflow-y: auto;">
            {#each userDashboards as d}
              <button
                style="text-align: left; padding: 8px 12px; border: 2px solid {selectedDashId === d.id ? 'var(--color-primary)' : 'var(--color-on-surface)'}; background: {selectedDashId === d.id ? 'var(--color-primary-container)' : 'var(--color-surface-bright)'}; cursor: pointer; font-family: var(--font-family-display);"
                onclick={() => { selectedDashId = d.id; newDashNameForPin = ''; }}
              >
                <div style="font-size: 11px; font-weight: 900; text-transform: uppercase;">{d.name}</div>
                <div style="font-size: 9px; color: var(--color-on-surface-dim);">{d.widget_count} widgets</div>
              </button>
            {/each}
          </div>
        {/if}

        <!-- Or create new -->
        <div style="font-size: 9px; font-weight: 700; text-transform: uppercase; margin-bottom: 3px;">OR CREATE NEW DASHBOARD</div>
        <input type="text" bind:value={newDashNameForPin} placeholder="New dashboard name..." onfocus={() => { selectedDashId = null; }} style="width: 100%; border: 2px solid var(--color-on-surface); padding: 6px 10px; font-family: var(--font-family-display); font-size: 12px; background: var(--color-surface); margin-bottom: 16px;" />

        <div class="flex gap-2">
          <button class="send-btn" onclick={confirmPin} disabled={!selectedDashId && !newDashNameForPin.trim()} style="flex: 1; padding: 8px; font-size: 11px; justify-content: center; display: flex;">PIN</button>
          <button class="feedback-btn" onclick={() => showPinModal = false} style="flex: 1; padding: 8px; font-size: 11px; justify-content: center; display: flex; font-weight: 700;">CANCEL</button>
        </div>
      </div>
    </div>
  </div>
{/if}
