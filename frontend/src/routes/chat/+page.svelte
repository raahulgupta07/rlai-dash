<script lang="ts">
  import { onMount, tick } from 'svelte';
  import { generateSessionId, markdownToHtml, parseMarkdownTables, tableToCsv, hasNumericData, detectChartType, getAvailableTypes } from '$lib';
  import type { ToolCall } from '$lib/api';
  import type { ParsedTable } from '$lib/table-parser';
  import type { ChartType } from '$lib/chart-detect';
  import EChartView from '$lib/echart.svelte';
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
    activeTab?: 'analysis' | 'data' | 'query' | 'graph';
    qualityScore?: number;
    showTrace?: boolean;
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
        body: formData
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

  function autoResize() {
    if (textareaEl) {
      textareaEl.style.height = 'auto';
      textareaEl.style.height = Math.min(textareaEl.scrollHeight, 120) + 'px';
    }
  }

  let abortController: AbortController | null = null;

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
                      {@const currentTab = msg.activeTab || 'analysis'}

                      <div class="response-tabs">
                        <button class="response-tab" class:response-tab-active={currentTab === 'analysis'} onclick={() => { messages = [...messages.slice(0, i), { ...msg, activeTab: 'analysis' }, ...messages.slice(i + 1)]; }}>Analysis</button>
                        <button class="response-tab" class:response-tab-active={currentTab === 'data'} class:response-tab-dim={!hasTables} onclick={() => { if (hasTables) messages = [...messages.slice(0, i), { ...msg, activeTab: 'data' }, ...messages.slice(i + 1)]; }}>Data{#if hasTables}<span class="tab-badge">{tables[0].rows.length}</span>{/if}</button>
                        <button class="response-tab" class:response-tab-active={currentTab === 'query'} class:response-tab-dim={!hasQueries} onclick={() => { if (hasQueries) messages = [...messages.slice(0, i), { ...msg, activeTab: 'query' }, ...messages.slice(i + 1)]; }}>Query{#if hasQueries}<span class="tab-badge">{msg.sqlQueries?.length}</span>{/if}</button>
                        <button class="response-tab" class:response-tab-active={currentTab === 'graph'} class:response-tab-dim={!hasChartData} onclick={() => { if (hasChartData) messages = [...messages.slice(0, i), { ...msg, activeTab: 'graph', chartType: msg.chartType || detectChartType(tables[0]) }, ...messages.slice(i + 1)]; }}>Graph</button>
                      </div>

                      <!-- TAB: Analysis -->
                      {#if currentTab === 'analysis'}
                        <div class="bubble-assistant">
                          <div class="prose-chat">
                            {@html markdownToHtml(msg.content)}
                          </div>
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
                              <thead><tr><th style="width: 36px; text-align: center; color: var(--color-on-surface-dim);">#</th>{#each tables[0].headers as h}<th>{h}</th>{/each}</tr></thead>
                              <tbody>{#each tables[0].rows as row, ri}<tr><td style="text-align: center; color: var(--color-on-surface-dim); font-size: 10px;">{ri + 1}</td>{#each row as cell}<td>{cell}</td>{/each}</tr>{/each}</tbody>
                            </table>
                          </div>
                          <div class="flex gap-2 mt-3">
                            <button class="feedback-btn" onclick={() => {
                              const csv = tableToCsv(tables[0]);
                              const blob = new Blob([csv], { type: 'text/csv' });
                              const url = URL.createObjectURL(blob); const a = document.createElement('a'); a.href = url; a.download = `dash-export-${Date.now()}.csv`; a.click(); URL.revokeObjectURL(url);
                            }} style="font-size: 10px; font-weight: 700; text-transform: uppercase; padding: 4px 10px;">DOWNLOAD CSV</button>
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
                            <div class="cli-line" style="margin-bottom: 4px;"><span class="cli-dim">-- query {si + 1}</span></div>
                            <pre style="margin: 0; font-family: 'Space Grotesk', monospace; font-size: 12px; color: #e0e0e0; white-space: pre-wrap; word-break: break-all; line-height: 1.5;">{sql}</pre>
                          {/each}
                          <div style="margin-top: 12px; border-top: 1px solid #333; padding-top: 8px;">
                            <button class="feedback-btn" onclick={() => { navigator.clipboard.writeText((msg.sqlQueries || []).join('\n\n')); }} style="font-size: 10px; font-weight: 700; text-transform: uppercase; padding: 4px 10px; color: #00fc40;">COPY SQL</button>
                          </div>
                        </div>

                      <!-- TAB: Graph -->
                      {:else if currentTab === 'graph' && hasChartData}
                        <div class="bubble-assistant" style="padding: 12px;">
                          <div class="flex gap-0 mb-2">
                            {#each getAvailableTypes(tables[0]) as ct}
                              <button class="chart-type-btn" class:chart-type-btn-active={(msg.chartType || detectChartType(tables[0])) === ct} onclick={() => { messages = [...messages.slice(0, i), { ...msg, chartType: ct }, ...messages.slice(i + 1)]; }}>{ct.toUpperCase()}</button>
                            {/each}
                          </div>
                          <div style="background: var(--color-surface-bright); padding: 8px; border: 2px solid var(--color-on-surface);">
                            <EChartView headers={tables[0].headers} rows={tables[0].rows} chartType={msg.chartType || detectChartType(tables[0])} />
                          </div>
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
          <button class="send-btn" onclick={() => send()} disabled={!inputText.trim()} title="Send" style="height: 34px; width: 34px; padding: 0;">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><line x1="22" y1="2" x2="11" y2="13"/><polygon points="22 2 15 22 11 13 2 9 22 2"/></svg>
          </button>
        {/if}
      </div>

      <div style="text-align: center; margin-top: 4px; font-size: 9px; color: var(--color-on-surface-dim); text-transform: uppercase; letter-spacing: 0.1em;">
        DASH AGENT CAN MAKE MISTAKES. VERIFY CRITICAL INFORMATION.
      </div>
    </div>
  </div>
</div>
</div>
