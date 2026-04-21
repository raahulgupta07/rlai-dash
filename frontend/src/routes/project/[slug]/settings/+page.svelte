<script lang="ts">
  import { onMount, onDestroy } from 'svelte';
  import { page } from '$app/state';
  import KnowledgeGraph from '$lib/knowledge-graph.svelte';
  import EChartView from '$lib/echart.svelte';

  const slug = $derived(page.params.slug || '');
  let project = $state<any>(null);
  let detail = $state<any>(null);
  let loading = $state(true);
  let activeTab = $state('cockpit');

  // Upload
  let showUpload = $state(false);
  let uploading = $state(false);
  let selectedFile = $state<File | null>(null);
  let selectedFiles = $state<File[]>([]);
  let tableName = $state('');
  let uploadSteps = $state<any[]>([]);
  let uploadResult = $state<any>(null);
  let uploadResults = $state<any[]>([]);
  let uploadError = $state('');
  let fileInputEl: HTMLInputElement;

  // Doc upload
  let showDocUpload = $state(false);
  let docFile = $state<File | null>(null);
  let docUploading = $state(false);
  let docResult = $state<any>(null);
  let docFileInput: HTMLInputElement;

  // Inspect
  let showInspect = $state(false);
  let inspectTable = $state<any>(null);
  let inspectData = $state<any>(null);

  // Extra data
  let lineage = $state<any>(null);
  let training = $state<any>(null);
  let docs = $state<any[]>([]);
  let knowledgeFiles = $state<any[]>([]);
  let workflows = $state<any[]>([]);

  // Agents
  let agentsData = $state<any>(null);
  async function loadAgents() { try { const r = await fetch(`/api/projects/${slug}/agents`, { headers: _h() }); if (r.ok) agentsData = await r.json(); } catch {} }

  // Doc-to-workflow
  let docToWorkflowLoading = $state<string | null>(null);
  let docWorkflowPreview = $state<any>(null);
  let docWorkflowCreated = $state<Set<string>>(new Set());

  // Knowledge graph click detail
  let graphSelectedNode = $state<any>(null);

  // Dataset cards — expanded state + loaded data
  let expandedTables = $state<Record<string, boolean>>({});
  let tableInspectCache = $state<Record<string, any>>({});
  let tableMetaCache = $state<Record<string, any>>({});
  let tableRelationships = $state<any[]>([]);

  async function loadTableDetail(tblName: string) {
    if (tableInspectCache[tblName]) return;
    try {
      const r = await fetch(`/api/tables/${tblName}/inspect?project=${slug}`, { headers: _h() });
      if (r.ok) tableInspectCache = { ...tableInspectCache, [tblName]: await r.json() };
    } catch {}
    // Load metadata from knowledge file
    if (!tableMetaCache[tblName]) {
      try {
        const r = await fetch(`/api/knowledge-file-content/${tblName}.json?project=${slug}&subdir=tables`, { headers: _h() });
        if (r.ok) {
          const d = await r.json();
          if (d.type === 'json' && d.content) tableMetaCache = { ...tableMetaCache, [tblName]: d.content };
        }
      } catch {}
    }
  }

  function toggleTableExpand(tblName: string) {
    const isExpanding = !expandedTables[tblName];
    expandedTables = { ...expandedTables, [tblName]: isExpanding };
    if (isExpanding) loadTableDetail(tblName);
  }

  // loadRelationships is defined below with other loaders — tableRelationships is populated there

  // Self-Evolution features
  let insights = $state<any[]>([]);
  let userPreferences = $state<any>({});
  let metaLearnings = $state<any[]>([]);
  let consolidationStatus = $state<any>({memory_count: 0, eligible: false});
  let evolvedInstructions = $state<any>({current: null, history: []});
  let resourceRegistry = $state<any[]>([]);
  let registryOverall = $state(0);
  let evolutionHistory = $state<any[]>([]);
  let queryPlans = $state<any[]>([]);
  let evalHistory = $state<any[]>([]);
  let transferCandidates = $state<any[]>([]);
  let importPreview = $state<any>(null);
  let consolidating = $state(false);
  let evolving = $state(false);
  let selfEvaluating = $state(false);
  let mining = $state(false);
  let evalRegression = $state<string | null>(null);

  async function loadInsights() {
    try { const r = await fetch(`/api/projects/${slug}/insights`, { headers: _h() }); if (r.ok) { const d = await r.json(); insights = d.insights || []; } } catch {}
  }
  async function loadPreferences() {
    try { const r = await fetch(`/api/projects/${slug}/preferences`, { headers: _h() }); if (r.ok) { const d = await r.json(); userPreferences = d.preferences || {}; } } catch {}
  }
  async function loadMetaLearnings() {
    try { const r = await fetch(`/api/projects/${slug}/meta-learnings`, { headers: _h() }); if (r.ok) { const d = await r.json(); metaLearnings = d.strategies || []; } } catch {}
  }
  async function loadConsolidationStatus() {
    try { const r = await fetch(`/api/projects/${slug}/consolidation-status`, { headers: _h() }); if (r.ok) consolidationStatus = await r.json(); } catch {}
  }
  async function loadEvolvedInstructions() {
    try { const r = await fetch(`/api/projects/${slug}/evolved-instructions`, { headers: _h() }); if (r.ok) evolvedInstructions = await r.json(); } catch {}
  }
  async function loadResourceRegistry() {
    try { const r = await fetch(`/api/projects/${slug}/resource-registry`, { headers: _h() }); if (r.ok) { const d = await r.json(); resourceRegistry = d.resources || []; registryOverall = d.overall_health || 0; } } catch {}
  }
  async function loadEvolutionHistory() {
    try { const r = await fetch(`/api/projects/${slug}/evolution-history`, { headers: _h() }); if (r.ok) { const d = await r.json(); evolutionHistory = d.runs || []; } } catch {}
  }
  async function loadQueryPlans() {
    try { const r = await fetch(`/api/projects/${slug}/query-plans`, { headers: _h() }); if (r.ok) { const d = await r.json(); queryPlans = d.plans || []; } } catch {}
  }
  async function loadEvalHistory() {
    try { const r = await fetch(`/api/projects/${slug}/eval-history`, { headers: _h() }); if (r.ok) { const d = await r.json(); evalHistory = d.runs || []; } } catch {}
  }
  async function loadTransferCandidates() {
    try { const r = await fetch(`/api/projects/${slug}/transfer-candidates`, { headers: _h() }); if (r.ok) { const d = await r.json(); transferCandidates = d.projects || []; } } catch {}
  }

  // Rules
  let rules = $state<any[]>([]);
  let showAddRule = $state(false);
  let newRuleName = $state('');
  let newRuleDefinition = $state('');
  let newRuleType = $state('business_rule');
  let ruleSaving = $state(false);

  const tabs = [
    { id: 'cockpit', label: 'COCKPIT' },
    { id: 'datasets', label: 'DATASETS' },
    { id: 'knowledge', label: 'KNOWLEDGE' },
    { id: 'rules', label: 'RULES' },
    { id: 'training', label: 'TRAINING' },
    { id: 'docs', label: 'DOCS' },
    { id: 'queries', label: 'QUERIES' },
    { id: 'lineage', label: 'LINEAGE' },
    { id: 'agents', label: 'AGENTS' },
    { id: 'workflows', label: 'WORKFLOWS' },
    { id: 'schedules', label: 'SCHEDULES' },
    { id: 'evals', label: 'EVALS' },
    { id: 'users', label: 'USERS' },
    { id: 'config', label: 'CONFIG' },
  ];

  function _h(): Record<string, string> {
    const t = typeof localStorage !== 'undefined' ? localStorage.getItem('dash_token') : null;
    return t ? { Authorization: `Bearer ${t}` } : {};
  }

  function tv(id: string): string {
    if (!detail) return '...';
    switch (id) {
      case 'cockpit': return registryOverall ? `${registryOverall}%` : '—';
      case 'datasets': return String(detail.tables?.length || 0);
      case 'knowledge': return String(detail.knowledge_vectors || 0);
      case 'training': return String((training?.learnings || 0) + (training?.training_qa?.length || 0) + brainFeedback.length + brainPatterns.length + brainMemories.length);
      case 'evals': return String(brainEvals.length);
      case 'docs': return String(docs.length);
      case 'queries': return String(brainPatterns.length || knowledgeFiles.filter((f: any) => f.type === 'queries').length);
      case 'lineage': return String([...(lineage?.relationships || []), ...relationships].length);
      case 'rules': return String(rules.length);
      case 'agents': return String(agentsData?.agents?.length || 4);
      case 'workflows': return String(workflows.length);
      case 'schedules': return String(schedules.length);
      case 'users': return String(sharedUsers.length);
      case 'config': return '⚙';
      default: return '';
    }
  }

  function tabStatus(id: string): 'complete' | 'partial' | 'empty' {
    if (!detail) return 'empty';
    switch (id) {
      case 'cockpit': return registryOverall >= 70 ? 'complete' : registryOverall > 0 ? 'partial' : 'empty';
      case 'datasets': {
        const tables = detail.tables?.length || 0;
        if (tables === 0) return 'empty';
        const trained = knowledgeFiles.filter((f: any) => f.type === 'tables').length;
        return trained >= tables ? 'complete' : 'partial';
      }
      case 'knowledge': return (detail.knowledge_vectors || 0) > 10 ? 'complete' : (detail.knowledge_vectors || 0) > 0 ? 'partial' : 'empty';
      case 'training': {
        const total = (training?.learnings || 0) + (training?.training_qa?.length || 0) + brainFeedback.length + brainPatterns.length + brainMemories.length;
        return total > 10 ? 'complete' : total > 0 ? 'partial' : 'empty';
      }
      case 'evals': return brainEvals.length > 3 ? 'complete' : brainEvals.length > 0 ? 'partial' : 'empty';
      case 'docs': return docs.length > 0 ? 'complete' : 'empty';
      case 'queries': {
        const qCount = knowledgeFiles.filter((f: any) => f.type === 'queries').length;
        return qCount > 2 ? 'complete' : qCount > 0 ? 'partial' : 'empty';
      }
      case 'lineage': { const _lc = [...(lineage?.relationships || []), ...relationships].length; return _lc > 2 ? 'complete' : _lc > 0 ? 'partial' : 'empty'; }
      case 'rules': return rules.length > 3 ? 'complete' : rules.length > 0 ? 'partial' : 'empty';
      case 'agents': return evolvedInstructions.current ? 'complete' : 'partial';
      case 'workflows': return workflows.length > 2 ? 'complete' : workflows.length > 0 ? 'partial' : 'empty';
      case 'schedules': return schedules.length > 0 ? 'complete' : 'empty';
      case 'users': return sharedUsers.length > 0 ? 'complete' : 'empty';
      case 'config': return 'complete';
      default: return 'empty';
    }
  }

  function tabStatusColor(id: string): string {
    const s = tabStatus(id);
    if (s === 'complete') return '#00fc40';
    if (s === 'partial') return '#ff9d00';
    return '#6b6b60';
  }

  function tabStatusIcon(id: string): string {
    const s = tabStatus(id);
    if (s === 'complete') return '✓';
    if (s === 'partial') return '◐';
    return '○';
  }

  onMount(async () => {
    await Promise.all([loadDetail(), loadLineage(), loadTraining(), loadDocs(), loadKnowledgeFiles(), loadWorkflows(), loadRules(), loadSuggestedRules(), loadSchedules(), loadSharedUsers(), loadPersona(), loadBrainData(), loadTrainingRuns(), loadDriftAlerts(), loadRelationships(), loadInsights(), loadPreferences(), loadMetaLearnings(), loadConsolidationStatus(), loadEvolvedInstructions(), loadResourceRegistry(), loadEvolutionHistory(), loadQueryPlans(), loadEvalHistory(), loadTransferCandidates(), loadAgents()]);
    loading = false;
    // Auto-load first table details
    if (detail?.tables?.length) {
      loadTableDetail(detail.tables[0].name);
    }
  });

  onDestroy(() => { if (trainPollTimer) { clearInterval(trainPollTimer); trainPollTimer = null; } });

  async function loadDetail() {
    try {
      const [pRes, dRes] = await Promise.all([
        fetch(`/api/projects/${slug}`, { headers: _h() }),
        fetch(`/api/projects/${slug}/detail`, { headers: _h() }),
      ]);
      if (pRes.ok) {
        project = await pRes.json();
        editName = project.agent_name || '';
        editRole = project.agent_role || '';
        editPersonality = project.agent_personality || 'friendly';
      }
      if (dRes.ok) detail = await dRes.json();
    } catch {}
  }

  async function loadLineage() { try { const r = await fetch(`/api/lineage?project=${slug}`, { headers: _h() }); if (r.ok) lineage = await r.json(); } catch {} }
  async function loadTraining() { try { const r = await fetch(`/api/training?project=${slug}`, { headers: _h() }); if (r.ok) training = await r.json(); } catch {} }
  async function loadDocs() { try { const r = await fetch(`/api/docs?project=${slug}`, { headers: _h() }); if (r.ok) { const d = await r.json(); docs = d.docs || []; } } catch {} }
  async function loadKnowledgeFiles() { try { const r = await fetch(`/api/knowledge-files?project=${slug}`, { headers: _h() }); if (r.ok) { const d = await r.json(); knowledgeFiles = d.files || []; } } catch {} }
  async function loadWorkflows() { try { const r = await fetch(`/api/projects/${slug}/workflows-db`, { headers: _h() }); if (r.ok) { const d = await r.json(); workflows = d.workflows || []; } } catch {} }
  async function loadSchedules() { try { const r = await fetch(`/api/projects/${slug}/schedules`, { headers: _h() }); if (r.ok) { const d = await r.json(); schedules = d.schedules || []; } } catch {} }
  async function loadPersona() { try { const r = await fetch(`/api/projects/${slug}/persona`, { headers: _h() }); if (r.ok) { const d = await r.json(); persona = d.persona; editPersonaText = persona?.persona_prompt || ''; } } catch {} }
  async function loadTrainingRuns() { try { const r = await fetch(`/api/projects/${slug}/training-runs`, { headers: _h() }); if (r.ok) { const d = await r.json(); trainingRuns = d.runs || []; } } catch {} }
  async function loadDriftAlerts() { try { const r = await fetch(`/api/projects/${slug}/drift-alerts`, { headers: _h() }); if (r.ok) { const d = await r.json(); driftAlerts = d.drift_alerts || []; } } catch {} }
  async function loadRelationships() { try { const r = await fetch(`/api/projects/${slug}/relationships`, { headers: _h() }); if (r.ok) { const d = await r.json(); relationships = d.relationships || []; tableRelationships = d.relationships || []; } } catch {} }

  async function loadBrainData() {
    const h = _h();
    try { const r = await fetch(`/api/projects/${slug}/feedback`, { headers: h }); if (r.ok) { const d = await r.json(); brainFeedback = d.feedback || []; } } catch {}
    try { const r = await fetch(`/api/projects/${slug}/query-patterns`, { headers: h }); if (r.ok) { const d = await r.json(); brainPatterns = d.patterns || []; } } catch {}
    try { const r = await fetch(`/api/projects/${slug}/memories`, { headers: h }); if (r.ok) { const d = await r.json(); brainMemories = d.memories || []; } } catch {}
    try { const r = await fetch(`/api/projects/${slug}/annotations`, { headers: h }); if (r.ok) { const d = await r.json(); brainAnnotations = d.annotations || []; } } catch {}
    try { const r = await fetch(`/api/projects/${slug}/evals`, { headers: h }); if (r.ok) { const d = await r.json(); brainEvals = d.evals || []; } } catch {}
  }

  async function addSchedule() {
    if (!newSchedPrompt || schedSaving) return;
    schedSaving = true;
    try {
      const params = new URLSearchParams({ name: newSchedName || 'Report', prompt: newSchedPrompt, cron: newSchedCron });
      await fetch(`/api/projects/${slug}/schedules?${params}`, { method: 'POST', headers: _h() });
      newSchedName = ''; newSchedPrompt = ''; newSchedCron = 'weekly'; showAddSchedule = false;
      await loadSchedules();
    } catch {} finally { schedSaving = false; }
  }

  async function deleteSchedule(id: number) {
    try { await fetch(`/api/projects/${slug}/schedules/${id}`, { method: 'DELETE', headers: _h() }); await loadSchedules(); } catch {}
  }

  async function toggleSchedule(id: number, enabled: boolean) {
    try { await fetch(`/api/projects/${slug}/schedules/${id}?enabled=${!enabled}`, { method: 'PUT', headers: _h() }); await loadSchedules(); } catch {}
  }

  let runningSchedule = $state<number | null>(null);
  async function runScheduleNow(id: number) {
    runningSchedule = id;
    try { await fetch(`/api/projects/${slug}/schedules/${id}/run`, { method: 'POST', headers: _h() }); await loadSchedules(); } catch {} finally { runningSchedule = null; }
  }
  async function loadRules() { try { const r = await fetch(`/api/projects/${slug}/rules`, { headers: _h() }); if (r.ok) { const d = await r.json(); rules = d.rules || []; } } catch {} }

  async function addRule() {
    if (!newRuleName || !newRuleDefinition || ruleSaving) return;
    ruleSaving = true;
    try {
      const res = await fetch(`/api/projects/${slug}/rules?name=${encodeURIComponent(newRuleName)}&definition=${encodeURIComponent(newRuleDefinition)}&type=${encodeURIComponent(newRuleType)}`, {
        method: 'POST', headers: _h()
      });
      if (res.ok) {
        newRuleName = ''; newRuleDefinition = ''; newRuleType = 'business_rule'; showAddRule = false;
        await loadRules();
      }
    } catch {} finally { ruleSaving = false; }
  }

  async function deleteRule(ruleId: string) {
    try {
      await fetch(`/api/projects/${slug}/rules/${ruleId}`, { method: 'DELETE', headers: _h() });
      await loadRules();
    } catch {}
  }

  // Schedules
  let schedules = $state<any[]>([]);
  let showAddSchedule = $state(false);

  // Config edit
  let editName = $state('');
  let editRole = $state('');
  let editPersonality = $state('friendly');
  let persona = $state<any>(null);
  let editPersonaText = $state('');

  // Training runs + drift + relationships
  let trainingRuns = $state<any[]>([]);

  // Train ALL stepper
  let isTraining = $state(false);
  let trainSteps = $state<{name: string; status: 'pending'|'active'|'done'|'error'}[]>([]);
  let trainCurrentTable = $state('');
  let trainTableIndex = $state(0);
  let trainTotalTables = $state(0);
  let trainCurrentStepName = $state('');
  let trainPollTimer: ReturnType<typeof setInterval> | null = null;

  const TRAIN_STEP_MAP: Record<string, number> = {
    'starting': 0, 'drift_detection': 0, 'deep_analysis': 1,
    'qa_generation': 2, 'persona': 3, 'synthesis': 4,
    'relationships': 5, 'reindex': 6, 'brain_fill': 7,
    'domain_knowledge': 8, 'persona_enrich': 9, 'complete': 10, 'cancelled': 10
  };

  function mapBackendStep(backendStep: string): number {
    return TRAIN_STEP_MAP[backendStep] ?? 0;
  }

  function cLog(text: string) {
    window.dispatchEvent(new CustomEvent('dash-cli-log', { detail: { text } }));
  }

  function ts() {
    return new Date().toLocaleTimeString('en-US', {hour:'2-digit',minute:'2-digit',second:'2-digit',hour12:false});
  }

  async function stopTraining() {
    if (!isTraining) return;
    try {
      await fetch(`/api/projects/${slug}/stop-training`, { method: 'POST', headers: _h() });
      cLog(`${ts()} ── ⊘ training stopped by user`);
      if (trainPollTimer) { clearInterval(trainPollTimer); trainPollTimer = null; }
      isTraining = false;
      trainSteps = trainSteps.map(s => s.status === 'active' ? { ...s, status: 'error' as any } : s.status === 'pending' ? { ...s, status: 'error' as any } : s);
      trainCurrentTable = ''; trainTableIndex = 0; trainTotalTables = 0; trainCurrentStepName = '';
      await Promise.all([loadDetail(), loadBrainData(), loadTrainingRuns()]);
    } catch {}
  }

  async function startTrainAll() {
    isTraining = true;
    trainSteps = [
      { name: 'Drift Check', status: 'active' },
      { name: 'Deep Analysis', status: 'pending' },
      { name: 'Q&A Generation', status: 'pending' },
      { name: 'Persona', status: 'pending' },
      { name: 'Workflows + Synthesis', status: 'pending' },
      { name: 'Relationships', status: 'pending' },
      { name: 'Knowledge Index', status: 'pending' },
      { name: 'Brain Fill', status: 'pending' },
      { name: 'Domain Knowledge', status: 'pending' },
      { name: 'Persona Enrich', status: 'pending' },
    ];

    (window as any).__trainLogCount = 0;
    cLog(`${ts()} ── starting TRAIN ALL pipeline...`);

    // Fire retrain
    try {
      fetch(`/api/projects/${slug}/retrain`, { method: 'POST', headers: _h() });
    } catch {}

    // Poll training runs
    let trainLastUpdate = Date.now();
    let trainLastStep = '';
    trainPollTimer = setInterval(async () => {
      try {
        if (Date.now() - trainLastUpdate > 300000) { stopTraining(); return; }
        const r = await fetch(`/api/projects/${slug}/training-runs`, { headers: _h() });
        if (r.ok) {
          const d = await r.json();
          const runs = d.runs || [];
          if (runs.length > 0) {
            const latest = runs[0];
            const rawStep = latest.steps || '';
            // Parse enhanced format: "step_name|table_name|table_index|total_tables"
            let step = rawStep;
            if (rawStep.includes('|')) {
              const parts = rawStep.split('|');
              step = parts[0];
              trainCurrentTable = parts[1] || '';
              trainTableIndex = parseInt(parts[2] || '0', 10);
              trainTotalTables = parseInt(parts[3] || '0', 10);
              trainCurrentStepName = step.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase());
            } else {
              trainCurrentTable = '';
              trainTableIndex = 0;
              trainTotalTables = 0;
              trainCurrentStepName = '';
            }
            if (rawStep !== trainLastStep) { trainLastUpdate = Date.now(); trainLastStep = rawStep; }
            const activeIdx = mapBackendStep(step);

            trainSteps = trainSteps.map((s, i) => ({
              ...s,
              status: i < activeIdx ? 'done' : i === activeIdx ? 'active' : 'pending'
            }));

            // Display detailed logs from backend
            const logs = latest.logs || [];
            const loggedCount = (window as any).__trainLogCount || 0;
            if (logs.length > loggedCount) {
              for (let li = loggedCount; li < logs.length; li++) {
                const entry = logs[li];
                cLog(`${entry.ts || ts()} │  ${entry.msg}`);
              }
              (window as any).__trainLogCount = logs.length;
            }

            if (latest.status === 'done' || latest.status === 'failed') {
              trainSteps = trainSteps.map(s => ({ ...s, status: 'done' }));
              if (trainPollTimer) { clearInterval(trainPollTimer); trainPollTimer = null; }
              cLog(`${ts()} ── ✓ training complete`);
              isTraining = false;
              trainCurrentTable = ''; trainTableIndex = 0; trainTotalTables = 0; trainCurrentStepName = '';

              // Reload data immediately so UI updates
              await Promise.all([loadDetail(), loadRules(), loadSuggestedRules(), loadBrainData(), loadTrainingRuns(), loadWorkflows(), loadDocs()]);

              // Phase 2: Run self-evolution in background (non-blocking)
              cLog(`${ts()} ── starting self-evolution (background)...`);
              (async () => {
                try {
                  cLog(`${ts()} │  evolving instructions...`);
                  const er = await fetch(`/api/projects/${slug}/evolve-instructions`, { method: 'POST', headers: _h() });
                  const ed = await er.json();
                  if (ed.status === 'ok') cLog(`${ts()} │  ✓ instructions evolved to v${ed.version}`);
                } catch {}

                try {
                  cLog(`${ts()} │  mining conversation patterns...`);
                  const mr = await fetch(`/api/projects/${slug}/mine-patterns`, { method: 'POST', headers: _h() });
                  const md = await mr.json();
                  if (md.status === 'ok') cLog(`${ts()} │  ✓ discovered ${md.workflows_created} new workflows`);
                  else cLog(`${ts()} │  · ${md.detail || 'no patterns found'}`);
                } catch {}

                try {
                  cLog(`${ts()} │  refreshing resource registry...`);
                  const rr = await fetch(`/api/projects/${slug}/resource-registry/refresh`, { method: 'POST', headers: _h() });
                  const rd = await rr.json();
                  if (rd.overall_health !== undefined) cLog(`${ts()} │  ✓ overall health: ${rd.overall_health}/100`);
                } catch {}

                cLog(`${ts()} ── ✓ self-evolution complete`);
                await Promise.all([loadEvolvedInstructions(), loadResourceRegistry(), loadEvolutionHistory(), loadConsolidationStatus(), loadWorkflows()]);
              })();
            }
          }
        }
      } catch {}
    }, 2000);
  }
  let driftAlerts = $state<any[]>([]);
  let relationships = $state<any[]>([]);

  // Agent brain (DB-backed)
  let brainFeedback = $state<any[]>([]);
  let brainPatterns = $state<any[]>([]);
  let brainMemories = $state<any[]>([]);
  let brainAnnotations = $state<any[]>([]);
  let brainEvals = $state<any[]>([]);
  let newEvalQ = $state('');
  let newEvalSQL = $state('');
  let evalsRunning = $state(false);
  let newMemoryFact = $state('');
  let newMemoryScope = $state('project');

  // Train per table
  let trainingTable = $state('');
  let trainLog = $state<{text: string; done: boolean}[]>([]);

  async function trainTable(tableName: string) {
    trainingTable = tableName;

    // Append to existing log (don't replace)
    const appendLog = (line: {text: string; done: boolean}) => { trainLog = [...trainLog, line]; };
    const markAllDone = () => { trainLog = trainLog.map(l => ({ ...l, done: true })); };

    appendLog({ text: `$ dash train --table ${tableName}`, done: true });
    appendLog({ text: `> analyzing columns...`, done: false });
    await new Promise(r => setTimeout(r, 500));
    markAllDone();
    appendLog({ text: `> LLM deep analysis...`, done: false });

    try {
      const res = await fetch(`/api/projects/${slug}/retrain`, { method: 'POST', headers: _h() });
      if (res.ok) {
        await new Promise(r => setTimeout(r, 2000));
        markAllDone();
        appendLog({ text: `> generating smart descriptions`, done: true });
        appendLog({ text: `> discovering business rules`, done: true });
        appendLog({ text: `> LLM training Q&A...`, done: false });
        await new Promise(r => setTimeout(r, 2000));
        markAllDone();
        appendLog({ text: `> knowledge re-indexed`, done: true });
        appendLog({ text: `$ done · ${tableName} trained`, done: true });
        await loadDetail(); await loadKnowledgeFiles(); await loadRules(); await loadSuggestedRules();
        await new Promise(r => setTimeout(r, 3000));
        await loadDetail();
      }
    } catch {
      markAllDone();
      appendLog({ text: `> error during training`, done: true });
    }
    trainingTable = '';
  }

  // Shared users
  let sharedUsers = $state<any[]>([]);
  let shareUsername = $state('');
  let shareRole = $state('viewer');
  let shareError = $state('');

  async function loadSharedUsers() {
    try {
      const r = await fetch(`/api/projects/${slug}/shared-users`, { headers: _h() });
      if (r.ok) { const d = await r.json(); sharedUsers = d.users || []; }
    } catch {}
  }

  async function unshareUser(username: string) {
    try {
      await fetch(`/api/projects/${slug}/share/${username}`, { method: 'DELETE', headers: _h() });
      await loadSharedUsers();
    } catch {}
  }

  async function shareProject() {
    if (!shareUsername) return;
    shareError = '';
    try {
      const res = await fetch(`/api/projects/${slug}/share?username=${encodeURIComponent(shareUsername)}&role=${shareRole}`, { method: 'POST', headers: _h() });
      if (res.ok) {
        const d = await res.json();
        if (d.status === 'already_shared') { shareError = 'Already shared'; }
        else { shareUsername = ''; shareError = 'Shared!'; }
      } else {
        const e = await res.json();
        shareError = e.detail || 'Failed';
      }
    } catch { shareError = 'Error'; }
  }
  let newSchedName = $state('');
  let newSchedPrompt = $state('');
  let newSchedCron = $state('weekly');
  let schedSaving = $state(false);

  let suggestedRules = $state<any[]>([]);
  async function loadSuggestedRules() { try { const r = await fetch(`/api/projects/${slug}/suggested-rules`, { headers: _h() }); if (r.ok) { const d = await r.json(); suggestedRules = d.suggestions || []; } } catch {} }
  async function approveRule(id: number) { try { await fetch(`/api/projects/${slug}/suggested-rules/${id}/approve`, { method: 'POST', headers: _h() }); await loadSuggestedRules(); await loadRules(); } catch {} }
  async function rejectRule(id: number) { try { await fetch(`/api/projects/${slug}/suggested-rules/${id}/reject`, { method: 'POST', headers: _h() }); await loadSuggestedRules(); } catch {} }

  function maxR(): number { return detail?.tables ? Math.max(...detail.tables.map((t: any) => t.rows), 1) : 1; }
  function barW(r: number): string { return Math.max(5, (r / maxR()) * 100) + '%'; }
  let uploadFileType = $state('data');
  let uploadMatch = $state<any>(null);
  let uploadAction = $state('auto');

  async function deleteTable(tableName: string) {
    if (!confirm('Delete table "' + tableName + '" and all its data? This cannot be undone.')) return;
    try {
      const r = await fetch('/api/tables/' + tableName + '?project=' + slug, { method: 'DELETE', headers: _h() });
      if (r.ok) { cLog(ts() + ' │  ✓ table ' + tableName + ' deleted'); await loadDetail(); await loadKnowledgeFiles(); }
      else { const e = await r.json().catch(() => ({})); alert(e.detail || 'Delete failed'); }
    } catch {}
  }

  function setFile(f: File) {
    selectedFile = f;
    selectedFiles = [f];
    if (!tableName) tableName = f.name.replace(/\.[^.]+$/, '').toLowerCase().replace(/[^a-z0-9_]/g, '_');
    uploadResult = null; uploadResults = []; uploadError = ''; uploadSteps = [];
    // Detect file type from extension
    const ext = f.name.split('.').pop()?.toLowerCase() || '';
    if (ext === 'sql') uploadFileType = 'sql_patterns';
    else if (['md', 'txt', 'docx', 'pptx', 'pdf'].includes(ext)) uploadFileType = 'document';
    else uploadFileType = 'data';
    uploadMatch = null;
    uploadAction = 'auto';
  }

  function setFiles(files: FileList) {
    const arr = Array.from(files);
    if (arr.length === 0) return;
    selectedFiles = arr;
    selectedFile = arr[0];
    if (!tableName && arr.length === 1) tableName = arr[0].name.replace(/\.[^.]+$/, '').toLowerCase().replace(/[^a-z0-9_]/g, '_');
    uploadResult = null; uploadResults = []; uploadError = ''; uploadSteps = [];
    const ext = arr[0].name.split('.').pop()?.toLowerCase() || '';
    if (ext === 'sql') uploadFileType = 'sql_patterns';
    else if (['md', 'txt', 'docx', 'pptx', 'pdf'].includes(ext)) uploadFileType = 'document';
    else uploadFileType = 'data';
    uploadMatch = null;
    uploadAction = 'auto';
  }

  async function doUpload() {
    const filesToUpload = selectedFiles.length > 0 ? selectedFiles : (selectedFile ? [selectedFile] : []);
    if (filesToUpload.length === 0 || uploading) return;
    uploading = true; uploadError = ''; uploadResult = null; uploadResults = [];
    uploadSteps = ['Detecting', 'Parsing', 'Loading', 'Analyzing', 'Saving', 'Training'].map(l => ({ label: l, status: 'pending' }));
    uploadSteps = uploadSteps.map((s, i) => i === 0 ? { ...s, status: 'done' } : s);

    for (let fi = 0; fi < filesToUpload.length; fi++) {
      const currentFile = filesToUpload[fi];
      const fd = new FormData();
      fd.append('file', currentFile);
      // Only use custom table name for single file
      if (filesToUpload.length === 1 && tableName) fd.append('table_name', tableName);
      if (uploadAction !== 'auto') fd.append('action', uploadAction);

      if (filesToUpload.length > 1) cLog(`${ts()} │  uploading ${fi + 1}/${filesToUpload.length}: ${currentFile.name}`);

      try {
        // Route doc files to upload-doc endpoint, data files to upload endpoint
        const ext = currentFile.name.split('.').pop()?.toLowerCase() || '';
        const isDoc = ['pptx', 'docx', 'pdf', 'md', 'txt', 'sql', 'py'].includes(ext);
        const uploadUrl = isDoc
          ? `/api/upload-doc?project=${slug}`
          : `/api/upload?project=${slug}&action=${uploadAction}`;
        const res = await fetch(uploadUrl, { method: 'POST', body: fd, headers: _h() });
        if (!res.ok) {
          const e = await res.json().catch(() => ({ detail: 'Failed' }));
          if (res.status === 409 && e.detail?.match && filesToUpload.length === 1) {
            uploadMatch = e.detail.match;
            uploadError = `Table "${e.detail.match?.table}" already exists (${e.detail.match?.overlap_pct}% match). Choose an action below.`;
            uploadSteps = uploadSteps.map((s: any) => s.status === 'pending' ? { ...s, status: 'error' } : s);
            uploading = false;
            return;
          }
          const errMsg = typeof e.detail === 'string' ? e.detail : JSON.stringify(e.detail);
          cLog(`${ts()} │  ✗ ${currentFile.name}: ${errMsg}`);
          continue;
        }
        const result = await res.json();
        uploadResults = [...uploadResults, { file: currentFile.name, ...result }];
        uploadResult = result;

        // Log smart info to CLI
        const smart = result?.smart;
        if (smart) {
          cLog(`${ts()} │  file type: ${smart.file_type || result.file_type}`);
          if (smart.rows_appended) cLog(`${ts()} │  ✓ ${smart.rows_appended} rows appended`);
          if (smart.rows_upserted) cLog(`${ts()} │  ✓ ${smart.rows_upserted} rows updated`);
          if (smart.annotations) cLog(`${ts()} │  ✓ ${smart.annotations} annotations saved`);
          if (smart.rules) cLog(`${ts()} │  ✓ ${smart.rules} rules extracted`);
          if (smart.patterns_saved) cLog(`${ts()} │  ✓ ${smart.patterns_saved} SQL patterns saved`);
          if (smart.facts) cLog(`${ts()} │  ✓ ${smart.facts} facts extracted`);
        } else {
          cLog(`${ts()} │  ✓ ${currentFile.name} uploaded`);
        }
        if (result?.tables_extracted) cLog(`${ts()} │  ✓ ${result.tables_extracted} tables extracted from document`);
      } catch (e: any) {
        cLog(`${ts()} │  ✗ ${currentFile.name}: ${e.message}`);
      }
    }

    // Update steps
    for (let i = 1; i < uploadSteps.length; i++) {
      uploadSteps = uploadSteps.map((s: any, idx: number) => idx === i ? { ...s, status: 'done' } : s);
      await new Promise(r => setTimeout(r, 150));
    }

    await loadDetail(); await loadKnowledgeFiles(); await loadRules(); await loadBrainData(); await loadDocs();
    if (uploadResults.length === 0 && !uploadResult) {
      uploadError = 'All files failed to upload';
      uploadSteps = uploadSteps.map((s: any) => s.status === 'pending' ? { ...s, status: 'error' } : s);
    } else {
      // Auto-hide upload panel after success (with delay so user sees result)
      setTimeout(() => { showUpload = false; selectedFile = null; selectedFiles = []; }, 3000);
    }
    uploading = false;
  }

  async function uploadDoc() {
    if (!docFile || docUploading) return;
    docUploading = true; docResult = null;
    const fd = new FormData(); fd.append('file', docFile);
    try { const r = await fetch(`/api/upload-doc?project=${slug}`, { method: 'POST', body: fd, headers: _h() }); if (r.ok) { docResult = await r.json(); await loadDocs(); } } catch {}
    docUploading = false;
  }

  async function deleteDoc(name: string) { if (!confirm(`Delete "${name}"?`)) return; try { await fetch(`/api/docs/${name}?project=${slug}`, { method: 'DELETE', headers: _h() }); await loadDocs(); } catch {} }

  function logTabSwitch(tabId: string) {
    const now = new Date();
    const ts = `${now.toLocaleDateString('en-US', { month: 'short', day: '2-digit' })} ${now.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false })}`;

    const tabInfo: Record<string, () => string> = {
      datasets: () => `  ${ts} │  ${detail?.tables?.length || 0} tables loaded · ${detail?.tables?.reduce((s: number, t: any) => s + (t.rows || 0), 0).toLocaleString()} total rows`,
      knowledge: () => `  ${ts} │  ${detail?.knowledge_vectors || 0} vector embeddings · ${knowledgeFiles.length} metadata files`,
      rules: () => `  ${ts} │  ${rules.length} active rules · ${suggestedRules.length} pending suggestions`,
      training: () => `  ${ts} │  ${training?.learnings || 0} error learnings · ${training?.training_qa?.length || 0} Q&A pairs`,
      docs: () => `  ${ts} │  ${docs.length} documents uploaded`,
      queries: () => `  ${ts} │  ${knowledgeFiles.filter((f: any) => f.type === 'queries').length} saved SQL patterns`,
      lineage: () => `  ${ts} │  ${lineage?.relationships?.length || 0} FK relationships detected`,
      agents: () => `  ${ts} │  Leader + Analyst + Engineer · model: gpt-5.4-mini`,
      workflows: () => `  ${ts} │  ${workflows.length} saved workflows`,
      schedules: () => `  ${ts} │  ${schedules.length} schedules · ${schedules.filter((s: any) => s.enabled).length} active`,
      users: () => `  ${ts} │  ${sharedUsers.length} users with access`,
      config: () => `  ${ts} │  agent: ${project?.agent_name} · personality: ${project?.agent_personality}`,
    };

    window.dispatchEvent(new CustomEvent('dash-cli-log', { detail: { text: `  ${ts} ── accessing ${tabId.toUpperCase()} module` } }));

    const infoFn = tabInfo[tabId];
    if (infoFn) {
      const info = infoFn();
      window.dispatchEvent(new CustomEvent('dash-cli-log', { detail: { text: info } }));
    }
  }

  async function openInspect(tbl: any) {
    inspectTable = tbl; showInspect = true; inspectData = null;
    const now = new Date();
    const ts = `${now.toLocaleDateString('en-US', { month: 'short', day: '2-digit' })} ${now.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false })}`;
    window.dispatchEvent(new CustomEvent('dash-cli-log', { detail: { text: `  ${ts} ── inspecting table: ${tbl.name}` } }));
    try {
      const r = await fetch(`/api/tables/${tbl.name}/inspect?project=${slug}`, { headers: _h() });
      if (r.ok) {
        inspectData = await r.json();
        window.dispatchEvent(new CustomEvent('dash-cli-log', { detail: { text: `  ${ts} │  ✓ ${inspectData.columns?.length || 0} columns · ${inspectData.sample?.length || 0} sample rows loaded` } }));
      }
    } catch {}
  }
</script>

<div style="padding: 16px; overflow-y: auto; height: 100%;">
<div style="width: 100%; display: flex; flex-direction: column; flex: 1; min-height: 0;">

  <!-- Header -->
  <div class="flex items-center justify-between mb-4">
    <div class="flex items-center gap-3">
      <a href="/ui/projects" style="font-size: 11px; color: var(--color-on-surface-dim); text-decoration: none; text-transform: uppercase; cursor: pointer;">← PROJECTS</a>
      <span style="font-size: 18px; font-weight: 900; text-transform: uppercase;">{project?.agent_name || 'Agent'}</span>
    </div>
    <div class="flex items-center gap-2">
      {#if isTraining}
        <button class="send-btn" style="padding: 6px 14px; font-size: 10px; background: #d32f2f; color: white; border-color: #d32f2f;" onclick={stopTraining}>■ STOP TRAINING</button>
      {:else}
        <button class="send-btn" style="padding: 6px 14px; font-size: 10px; background: var(--color-on-surface); color: var(--color-primary-container); border-color: var(--color-on-surface);" onclick={() => { window.dispatchEvent(new CustomEvent('dash-train-all')); startTrainAll(); }}>TRAIN ALL</button>
      {/if}
      <a href="/ui/project/{slug}" class="send-btn" style="padding: 6px 14px; font-size: 10px; text-decoration: none; cursor: pointer;">← CHAT</a>
    </div>
  </div>

  {#if isTraining || trainSteps.some(s => s.status === 'done')}
  <div style="margin-bottom: 12px; padding: 10px 14px; border: 2px solid var(--color-on-surface); background: var(--color-surface-bright); font-family: var(--font-family-display);">
    <div style="display: flex; align-items: center; gap: 10px;">
      <div style="flex: 1; height: 4px; background: var(--color-surface-dim); border: 1px solid var(--color-on-surface-dim);">
        <div style="height: 100%; background: var(--color-primary); width: {trainSteps.length > 0 ? (trainTotalTables > 0 ? Math.min(100, Math.round((((trainTableIndex - 1) * trainSteps.length + trainSteps.filter(s => s.status === 'done').length) / (trainTotalTables * trainSteps.length)) * 100)) : Math.round((trainSteps.filter(s => s.status === 'done').length / trainSteps.length) * 100)) : 0}%; transition: width 0.5s ease;"></div>
      </div>
      <span style="font-size: 10px; font-weight: 900;">{trainSteps.length > 0 ? (trainTotalTables > 0 ? Math.min(100, Math.round((((trainTableIndex - 1) * trainSteps.length + trainSteps.filter(s => s.status === 'done').length) / (trainTotalTables * trainSteps.length)) * 100)) : Math.round((trainSteps.filter(s => s.status === 'done').length / trainSteps.length) * 100)) : 0}%</span>
      {#if trainSteps.find(s => s.status === 'active')}
        <span style="font-size: 9px; color: var(--color-warning); font-weight: 900;">● {trainTotalTables > 0 ? `Table ${trainTableIndex}/${trainTotalTables}: ${trainCurrentTable} · ` : ''}{trainSteps.find(s => s.status === 'active')?.name}</span>
      {/if}
    </div>
  </div>
  {/if}

{#if loading}
  <div style="text-align: center; padding: 40px; font-size: 12px; text-transform: uppercase; color: var(--color-on-surface-dim);">Loading...</div>
{:else}

  <div style="display: flex; flex-direction: column; flex: 1; min-height: 0;">
  <div class="dash-tabs" style="flex-shrink: 0;">
    {#each tabs as tab}
      <button class="dash-tab" class:dash-tab-active={activeTab === tab.id} onclick={() => { activeTab = tab.id; logTabSwitch(tab.id); if (tab.id === 'lineage' && detail?.tables) { for (const t of detail.tables) loadTableDetail(t.name); } }} style="cursor: pointer;">
        <span style="display: flex; align-items: center; gap: 4px;">{tab.label} <span style="color: {tabStatusColor(tab.id)}; font-size: 10px;">{tabStatusIcon(tab.id)}</span></span><span class="dash-tab-value">{tv(tab.id)}</span>
      </button>
    {/each}
  </div>

  <div class="dash-panel">

  <!-- ═══ COCKPIT ═══ -->
  {#if activeTab === 'cockpit'}

    <!-- Overall Health -->
    <div style="display: flex; align-items: center; gap: 16px; margin-bottom: 20px;">
      <div>
        <div style="font-size: 42px; font-weight: 900; color: {registryOverall >= 70 ? 'var(--color-primary)' : registryOverall >= 40 ? 'var(--color-warning)' : 'var(--color-error)'};">{registryOverall}</div>
        <div style="font-size: 9px; text-transform: uppercase; color: var(--color-on-surface-dim); letter-spacing: 0.1em;">/ 100 HEALTH</div>
      </div>
      <div style="flex: 1;">
        <div style="height: 12px; background: var(--color-surface-dim); border: 1px solid var(--color-on-surface);">
          <div style="height: 100%; background: {registryOverall >= 70 ? 'var(--color-primary)' : registryOverall >= 40 ? 'var(--color-warning)' : 'var(--color-error)'}; width: {registryOverall}%; transition: width 0.3s;"></div>
        </div>
        <div style="font-size: 10px; color: var(--color-on-surface-dim); margin-top: 4px;">
          {registryOverall >= 70 ? 'Agent is well-trained and learning' : registryOverall >= 40 ? 'Agent needs more training and feedback' : 'Agent needs training — click TRAIN ALL'}
          {#if trainingRuns.length > 0 && trainingRuns[0].finished_at}
            <span style="margin-left: 8px; color: var(--color-on-surface);">· Last trained: {new Date(trainingRuns[0].finished_at).toLocaleString('en-US', {month:'short', day:'numeric', hour:'2-digit', minute:'2-digit'})}</span>
          {/if}
        </div>
      </div>
      {#if isTraining}
        <button class="send-btn" onclick={stopTraining} style="font-size: 10px; padding: 6px 14px; background: var(--color-error); color: white; font-weight: 900;">■ STOP</button>
      {:else}
        <button class="send-btn" onclick={() => { startTrainAll(); }} style="font-size: 10px; padding: 6px 14px; background: var(--color-primary-container); color: var(--color-on-surface); font-weight: 900;">TRAIN ALL</button>
      {/if}
      <button class="feedback-btn" onclick={() => { loadResourceRegistry(); }} style="font-size: 9px; padding: 4px 10px; font-weight: 700;">REFRESH</button>
    </div>

    <!-- Train progress bar + stepper -->
    {#if isTraining && trainSteps.length > 0}
      {@const doneCount = trainSteps.filter(s => s.status === 'done').length}
      {@const activeStep = trainSteps.find(s => s.status === 'active')}
      {@const stepsPerTable = trainSteps.length}
      {@const pct = trainTotalTables > 0 ? Math.min(100, Math.round((((trainTableIndex - 1) * stepsPerTable + doneCount) / (trainTotalTables * stepsPerTable)) * 100)) : Math.round((doneCount / trainSteps.length) * 100)}
      <div class="ink-border" style="padding: 10px 14px; margin-bottom: 16px; background: var(--color-surface-bright);">
        <!-- Progress bar -->
        <div style="display: flex; align-items: center; gap: 10px; margin-bottom: 8px;">
          <div style="flex: 1; height: 6px; background: var(--color-surface-dim); border: 1px solid var(--color-on-surface-dim);">
            <div style="height: 100%; background: var(--color-primary); width: {pct}%; transition: width 0.5s ease;"></div>
          </div>
          <span style="font-size: 11px; font-weight: 900; min-width: 35px; text-align: right;">{pct}%</span>
        </div>
        <!-- Current step label -->
        {#if activeStep}
          <div style="font-size: 10px; color: var(--color-warning); font-weight: 900; margin-bottom: 6px;">● {trainTotalTables > 0 ? `Table ${trainTableIndex}/${trainTotalTables}: ${trainCurrentTable} · ${activeStep.name}` : activeStep.name}...</div>
        {/if}
        <!-- Step badges -->
        <div style="display: flex; flex-wrap: wrap; gap: 4px; align-items: center;">
        {#each trainSteps as step}
          <span style="font-size: 8px; font-weight: 900; padding: 1px 6px; border: 1px solid {step.status === 'done' ? 'var(--color-primary)' : step.status === 'active' ? 'var(--color-warning)' : step.status === 'error' ? 'var(--color-error)' : 'var(--color-on-surface-dim)'}; color: {step.status === 'done' ? 'var(--color-primary)' : step.status === 'active' ? 'var(--color-warning)' : step.status === 'error' ? 'var(--color-error)' : 'var(--color-on-surface-dim)'};">
            {step.status === 'done' ? '✓' : step.status === 'active' ? '●' : step.status === 'error' ? '✗' : '○'} {step.name}
          </span>
        {/each}
        </div>
        <!-- Table progress list -->
        {#if trainTotalTables > 0 && detail?.tables?.length > 0}
          <div style="margin-top: 8px; padding-top: 8px; border-top: 1px solid var(--color-on-surface-dim);">
            <div style="font-size: 8px; font-weight: 900; text-transform: uppercase; letter-spacing: 0.1em; color: var(--color-on-surface-dim); margin-bottom: 4px;">TABLE PROGRESS</div>
            {#each detail.tables as t, i}
              {@const tableNum = i + 1}
              {@const isDone = tableNum < trainTableIndex}
              {@const isActive = tableNum === trainTableIndex}
              {@const isPending = tableNum > trainTableIndex}
              <div style="font-size: 9px; font-weight: 700; font-family: var(--font-family-display); padding: 1px 0; color: {isDone ? 'var(--color-primary)' : isActive ? 'var(--color-warning)' : 'var(--color-on-surface-dim)'};">
                {isDone ? '✓' : isActive ? '●' : '○'} {t.name} · {isDone ? 'done' : isActive ? trainCurrentStepName : 'pending'}
              </div>
            {/each}
          </div>
        {/if}
      </div>
    {/if}

    <!-- Data Tables -->
    <div style="font-size: 13px; font-weight: 900; text-transform: uppercase; letter-spacing: 0.08em; margin-bottom: 8px;">DATA TABLES</div>
    {#if detail?.tables?.length > 0}
      <div style="overflow-x: auto; margin-bottom: 20px;">
        <table class="data-table" style="font-size: 11px; width: 100%;">
          <thead>
            <tr>
              <th style="text-align: left;">TABLE</th>
              <th>ROWS</th>
              <th>COLS</th>
              <th>TRAINED</th>
              <th>Q&A</th>
              <th>RULES</th>
              <th>HEALTH</th>
            </tr>
          </thead>
          <tbody>
            {#each detail.tables as t}
              {@const isTrained = knowledgeFiles.some((f) => f.type === 'tables' && f.name === t.name + '.json')}
              {@const qaCount = (training?.training_qa || []).filter((q) => q.source_table === t.name).length}
              {@const ruleCount = rules.filter((r) => r.name?.toLowerCase().includes(t.name?.toLowerCase())).length}
              {@const health = isTrained ? (qaCount > 0 ? 100 : 60) : 0}
              <tr>
                <td style="font-weight: 900;">{t.name}</td>
                <td style="text-align: center;">{(t.rows || 0).toLocaleString()}</td>
                <td style="text-align: center;">{t.columns || '—'}</td>
                <td style="text-align: center;">
                  {#if isTrained}
                    <span style="color: var(--color-primary); font-weight: 900;">✓</span>
                  {:else}
                    <span style="color: var(--color-on-surface-dim);">○</span>
                  {/if}
                </td>
                <td style="text-align: center;">{qaCount}</td>
                <td style="text-align: center;">{ruleCount}</td>
                <td style="text-align: center;">
                  <div style="display: inline-block; width: 50px; height: 6px; background: var(--color-surface-dim);">
                    <div style="height: 100%; width: {health}%; background: {health >= 70 ? 'var(--color-primary)' : health >= 40 ? 'var(--color-warning)' : 'var(--color-error)'};"></div>
                  </div>
                  <span style="font-size: 9px; margin-left: 4px;">{health}%</span>
                </td>
              </tr>
            {/each}
          </tbody>
          <tfoot>
            <tr style="font-weight: 900; border-top: 2px solid var(--color-on-surface);">
              <td>TOTAL</td>
              <td style="text-align: center;">{detail.tables.reduce((s, t) => s + (t.rows || 0), 0).toLocaleString()}</td>
              <td style="text-align: center;">{detail.tables.reduce((s, t) => s + (t.columns || 0), 0)}</td>
              <td style="text-align: center;">{knowledgeFiles.filter((f) => f.type === 'tables').length}/{detail.tables.length}</td>
              <td style="text-align: center;">{(training?.training_qa || []).length}</td>
              <td style="text-align: center;">{rules.length}</td>
              <td></td>
            </tr>
          </tfoot>
        </table>
      </div>
    {:else}
      <div style="font-size: 11px; color: var(--color-on-surface-dim); margin-bottom: 20px;">No tables yet. Upload data to get started.</div>
    {/if}

    <!-- Agent Brain Resources -->
    <div style="font-size: 13px; font-weight: 900; text-transform: uppercase; letter-spacing: 0.08em; margin-bottom: 8px;">AGENT BRAIN (9 Context Layers)</div>
    <div style="overflow-x: auto; margin-bottom: 20px;">
      <table class="data-table" style="font-size: 11px; width: 100%;">
        <thead>
          <tr><th style="text-align: left;">RESOURCE</th><th>COUNT</th><th>HEALTH</th><th style="text-align: left;">SOURCE TABLE</th></tr>
        </thead>
        <tbody>
          {#each resourceRegistry as res}
            <tr>
              <td style="font-weight: 700; text-transform: uppercase;">{res.type}</td>
              <td style="text-align: center; font-weight: 900;">{res.count}</td>
              <td style="text-align: center;">
                <div style="display: inline-block; width: 50px; height: 6px; background: var(--color-surface-dim);">
                  <div style="height: 100%; width: {res.health}%; background: {res.health >= 70 ? 'var(--color-primary)' : res.health >= 40 ? 'var(--color-warning)' : 'var(--color-error)'};"></div>
                </div>
                <span style="font-size: 9px; margin-left: 4px; color: {res.health >= 70 ? 'var(--color-primary)' : res.health >= 40 ? 'var(--color-warning)' : 'var(--color-error)'};">{res.health}%</span>
              </td>
              <td style="font-size: 10px; color: var(--color-on-surface-dim);">dash_{res.type === 'instruction' ? 'evolved_instructions' : res.type === 'pattern' ? 'query_patterns' : res.type + 's'}</td>
            </tr>
          {/each}
        </tbody>
        <tfoot>
          <tr style="font-weight: 900; border-top: 2px solid var(--color-on-surface);">
            <td>OVERALL</td>
            <td style="text-align: center;">{resourceRegistry.reduce((s, r) => s + r.count, 0)}</td>
            <td style="text-align: center;">
              <span style="font-weight: 900; color: {registryOverall >= 70 ? 'var(--color-primary)' : registryOverall >= 40 ? 'var(--color-warning)' : 'var(--color-error)'};">{registryOverall}%</span>
            </td>
            <td style="font-size: 10px; color: var(--color-on-surface-dim);">{resourceRegistry.filter(r => r.health > 0).length}/9 active</td>
          </tr>
        </tfoot>
      </table>
    </div>

    <!-- Training Pipeline Status -->
    <div style="font-size: 13px; font-weight: 900; text-transform: uppercase; letter-spacing: 0.08em; margin-bottom: 8px;">TRAINING PIPELINE</div>
    <div class="ink-border" style="padding: 12px 14px; background: var(--color-surface-bright); margin-bottom: 20px;">
      {#if trainingRuns.length > 0}
        {@const last = trainingRuns[0]}
        <div style="display: flex; flex-wrap: wrap; gap: 6px; margin-bottom: 8px;">
          {#each ['Analysis', 'Q&A', 'Persona', 'Workflows', 'Relationships', 'Knowledge Index'] as step}
            <span style="font-size: 9px; font-weight: 900; padding: 2px 8px; border: 1px solid {last.status === 'done' ? 'var(--color-primary)' : 'var(--color-on-surface-dim)'}; color: {last.status === 'done' ? 'var(--color-primary)' : 'var(--color-on-surface-dim)'}; text-transform: uppercase;">{last.status === 'done' ? '✓' : '○'} {step}</span>
          {/each}
        </div>
        <div style="font-size: 10px; color: var(--color-on-surface-dim);">
          Last trained: {last.started_at?.slice(0, 16)} · Status: <strong>{last.status}</strong> · {last.tables || 0} tables
          {#if last.finished_at} · Duration: {((new Date(last.finished_at).getTime() - new Date(last.started_at).getTime()) / 1000).toFixed(1)}s{/if}
        </div>
      {:else}
        <div style="font-size: 11px; color: var(--color-on-surface-dim);">Not trained yet. Click TRAIN ALL to start.</div>
      {/if}
    </div>

    <!-- Activity -->
    <div style="font-size: 13px; font-weight: 900; text-transform: uppercase; letter-spacing: 0.08em; margin-bottom: 8px;">ACTIVITY</div>
    <div style="display: grid; grid-template-columns: repeat(auto-fill, minmax(120px, 1fr)); gap: 8px; margin-bottom: 20px;">
      <div class="ink-border" style="padding: 8px 10px; text-align: center; background: var(--color-surface-bright);">
        <div style="font-size: 20px; font-weight: 900; color: var(--color-primary);">{brainFeedback.filter(f => f.rating === 'up').length}</div>
        <div style="font-size: 8px; text-transform: uppercase; color: var(--color-on-surface-dim);">GOOD FEEDBACK</div>
      </div>
      <div class="ink-border" style="padding: 8px 10px; text-align: center; background: var(--color-surface-bright);">
        <div style="font-size: 20px; font-weight: 900; color: var(--color-error);">{brainFeedback.filter(f => f.rating === 'down').length}</div>
        <div style="font-size: 8px; text-transform: uppercase; color: var(--color-on-surface-dim);">BAD FEEDBACK</div>
      </div>
      <div class="ink-border" style="padding: 8px 10px; text-align: center; background: var(--color-surface-bright);">
        <div style="font-size: 20px; font-weight: 900; color: var(--color-on-surface);">{insights.length}</div>
        <div style="font-size: 8px; text-transform: uppercase; color: var(--color-on-surface-dim);">INSIGHTS</div>
      </div>
      <div class="ink-border" style="padding: 8px 10px; text-align: center; background: var(--color-surface-bright);">
        <div style="font-size: 20px; font-weight: 900; color: var(--color-on-surface);">{driftAlerts.length}</div>
        <div style="font-size: 8px; text-transform: uppercase; color: var(--color-on-surface-dim);">DRIFT ALERTS</div>
      </div>
      <div class="ink-border" style="padding: 8px 10px; text-align: center; background: var(--color-surface-bright);">
        <div style="font-size: 20px; font-weight: 900; color: var(--color-on-surface);">{evolutionHistory.length}</div>
        <div style="font-size: 8px; text-transform: uppercase; color: var(--color-on-surface-dim);">EVOLUTIONS</div>
      </div>
    </div>

    <!-- Tab Completion Grid -->
    <div style="font-size: 13px; font-weight: 900; text-transform: uppercase; letter-spacing: 0.08em; margin-bottom: 8px;">TAB COMPLETION</div>
    <div style="display: grid; grid-template-columns: repeat(auto-fill, minmax(100px, 1fr)); gap: 6px;">
      {#each tabs.filter(t => t.id !== 'cockpit') as tab}
        <button class="ink-border" style="padding: 6px 8px; text-align: center; background: var(--color-surface-bright); cursor: pointer; font-family: var(--font-family-display); border-width: 1px;" onclick={() => { activeTab = tab.id; }}>
          <div style="font-size: 8px; font-weight: 900; text-transform: uppercase; color: var(--color-on-surface-dim);">{tab.label}</div>
          <div style="font-size: 14px; font-weight: 900; color: {tabStatusColor(tab.id)};">{tabStatusIcon(tab.id)}</div>
          <div style="font-size: 9px; color: var(--color-on-surface-dim);">{tv(tab.id)}</div>
        </button>
      {/each}
    </div>

  <!-- ═══ DATASETS ═══ -->
  {:else if activeTab === 'datasets'}
    <!-- CLI Header -->
    <div class="cli-terminal" style="margin-bottom: 16px; padding: 8px 14px;">
      <div class="cli-line">
        <span class="cli-prompt">$</span>
        <span class="cli-command">dash datasets</span>
        <span class="cli-output">--status</span>
        <span class="cli-dim" style="margin-left: auto;">{detail?.tables?.length || 0} tables · {docs.length} docs · {detail?.tables?.reduce((s: number, t: any) => s + (t.rows || 0), 0).toLocaleString()} rows</span>
      </div>
    </div>

    <div class="flex items-center justify-between mb-4">
      <div style="font-size: 18px; font-weight: 900; text-transform: uppercase;">Datasets</div>
      <div>
        <input type="file" accept=".csv,.xlsx,.xls,.json,.sql,.md,.txt,.py,.pptx,.docx,.pdf" multiple onchange={(e) => { const files = (e.target as HTMLInputElement).files; if (files && files.length > 0) { showUpload = true; files.length === 1 ? setFile(files[0]) : setFiles(files); } }} bind:this={fileInputEl} style="display: none;" />
        <button class="send-btn" onclick={() => fileInputEl?.click()} style="padding: 6px 14px; font-size: 10px; cursor: pointer;">↑ UPLOAD DATA</button>
      </div>
    </div>

    <!-- Upload progress (shows after file selected) -->
    {#if showUpload && (selectedFile || selectedFiles.length > 0)}
      <div class="ink-border" style="padding: 12px 16px; margin-bottom: 16px; background: var(--color-surface-bright);">
        <div class="flex items-center justify-between mb-2">
          {#if selectedFiles.length > 1}
            <div>
              <span style="font-weight: 900; font-size: 12px;">{selectedFiles.length} files selected</span>
              <span style="font-size: 10px; color: var(--color-on-surface-dim); margin-left: 6px;">({(selectedFiles.reduce((s, f) => s + f.size, 0) / 1024).toFixed(1)} KB)</span>
            </div>
          {:else if selectedFile}
            <div class="flex items-center gap-2">
              <span style="font-weight: 900; font-size: 12px;">{selectedFile.name}</span>
              <span style="font-size: 8px; font-weight: 900; padding: 1px 6px; background: {uploadFileType === 'data' ? 'var(--color-primary)' : uploadFileType === 'sql_patterns' ? 'var(--color-secondary)' : 'var(--color-warning)'}; color: white; text-transform: uppercase;">{uploadFileType === 'data' ? 'DATA' : uploadFileType === 'sql_patterns' ? 'SQL' : 'DOC'}</span>
              <span style="font-size: 10px; color: var(--color-on-surface-dim);">({(selectedFile.size / 1024).toFixed(1)} KB)</span>
            </div>
          {/if}
          <button onclick={() => { showUpload = false; selectedFile = null; selectedFiles = []; uploadSteps = []; uploadResult = null; uploadError = ''; }} style="background: none; border: none; cursor: pointer; font-size: 14px; color: var(--color-on-surface-dim);">&times;</button>
        </div>

        {#if selectedFile || selectedFiles.length > 0}
          {#if uploadFileType === 'data' && selectedFiles.length <= 1}
            <input type="text" bind:value={tableName} placeholder="Table name (auto-generated)" style="width: 100%; border: 1px solid var(--color-surface-dim); padding: 5px 10px; font-family: var(--font-family-display); font-size: 11px; background: var(--color-surface); margin-bottom: 8px;" />
          {/if}

          {#if uploadMatch}
            <div class="ink-border" style="margin-top: 10px; padding: 8px 12px; background: #fff3cd; border-color: var(--color-warning);">
              <div style="font-size: 10px; font-weight: 900; text-transform: uppercase; color: var(--color-warning); margin-bottom: 4px;">TABLE MATCH FOUND</div>
              <div style="font-size: 11px;">Table <strong>{uploadMatch.table}</strong> exists ({uploadMatch.overlap_pct}% overlap, {uploadMatch.existing_rows} rows)</div>
              <div style="display: flex; gap: 6px; margin-top: 8px;">
                <button class="feedback-btn" class:send-btn={uploadAction === 'append'} onclick={() => uploadAction = 'append'} style="font-size: 9px; padding: 3px 10px; font-weight: 900;">APPEND</button>
                <button class="feedback-btn" class:send-btn={uploadAction === 'upsert'} onclick={() => uploadAction = 'upsert'} style="font-size: 9px; padding: 3px 10px; font-weight: 900;">UPSERT</button>
                <button class="feedback-btn" class:send-btn={uploadAction === 'replace'} onclick={() => uploadAction = 'replace'} style="font-size: 9px; padding: 3px 10px; font-weight: 900;">REPLACE</button>
              </div>
            </div>
          {/if}

          {#if !uploadResult && uploadResults.length === 0}
            <button class="send-btn" onclick={doUpload} disabled={uploading} style="margin-top: 10px; padding: 8px 14px; font-size: 11px; width: 100%;">{uploading ? 'UPLOADING...' : selectedFiles.length > 1 ? `▶ UPLOAD ${selectedFiles.length} FILES` : '▶ UPLOAD'}</button>
          {/if}
        {/if}

        {#if uploadSteps.length > 0}
          <div style="margin-top: 10px; padding: 10px; background: var(--color-surface-dim); border-left: 3px solid var(--color-primary);">
            {#each uploadSteps as step}<div style="font-size: 11px; padding: 1px 0;">{#if step.status === 'done'}<span style="color: var(--color-primary);">✓</span>{:else if step.status === 'error'}<span style="color: var(--color-error);">✗</span>{:else}<span style="color: var(--color-on-surface-dim);">○</span>{/if} {step.label}</div>{/each}
            {#if uploadResult}
              <div style="margin-top: 6px; font-size: 11px; color: var(--color-primary); font-weight: 900;">
                {#if uploadResult.file_type === 'column_definition'}
                  ✓ Column definitions — {uploadResult.smart?.annotations} annotations, {uploadResult.smart?.memories} memories
                {:else if uploadResult.file_type === 'business_rules'}
                  ✓ Rules extracted — {uploadResult.smart?.rules} rules, {uploadResult.smart?.facts} facts
                {:else if uploadResult.file_type === 'sql_patterns'}
                  ✓ SQL patterns — {uploadResult.smart?.patterns_saved} saved
                {:else}
                  ✓ {uploadResult.table_name} — {uploadResult.rows} rows
                  {#if uploadResult.smart?.rows_appended > 0} ({uploadResult.smart.rows_appended} appended){/if}
                  {#if uploadResult.smart?.rows_upserted > 0} ({uploadResult.smart.rows_upserted} updated){/if}
                {/if}
              </div>
              {#if uploadResult?.tables_extracted}
                <div style="font-size: 11px; color: var(--color-primary);">
                  ✓ {uploadResult.tables_extracted} tables extracted from document
                </div>
              {/if}
            {/if}
            {#if uploadError}<div style="margin-top: 6px; font-size: 11px; color: var(--color-error);">{uploadError}</div>{/if}
          </div>
        {/if}
      </div>
    {/if}

    <!-- Documents list (non-data files) -->
    {#if docs.length > 0}
      <div style="margin-bottom: 16px;">
        <div style="font-size: 11px; font-weight: 900; text-transform: uppercase; letter-spacing: 0.08em; margin-bottom: 6px; color: var(--color-on-surface-dim);">DOCUMENTS ({docs.length})</div>
        {#each docs as d}
          <div class="flex items-center justify-between" style="padding: 4px 0; border-bottom: 1px solid var(--color-surface-dim); font-size: 11px;">
            <div class="flex items-center gap-2">
              <span style="font-size: 7px; font-weight: 900; padding: 1px 4px; background: {['.pptx','.pdf','.docx'].includes(d.type) ? 'var(--color-warning)' : ['.sql','.py'].includes(d.type) ? '#6366f1' : '#888'}; color: white; text-transform: uppercase; min-width: 26px; text-align: center;">{d.type.replace('.','')}</span>
              <span style="font-weight: 700;">{d.name}</span>
            </div>
            <div class="flex items-center gap-3">
              <span style="font-size: 9px; color: var(--color-on-surface-dim);">{(d.size / 1024).toFixed(1)} KB</span>
              <span style="font-size: 8px; font-weight: 900; color: var(--color-primary);">✓ INDEXED</span>
              <button class="feedback-btn" style="font-size: 7px; color: var(--color-error); border-color: var(--color-error); padding: 1px 5px; cursor: pointer;" onclick={() => deleteDoc(d.name)}>DEL</button>
            </div>
          </div>
        {/each}
      </div>
    {/if}

    <!-- Data Tables Summary -->
    {#if detail?.tables?.length > 0}
      <div style="margin-bottom: 16px;">
        <div style="font-size: 11px; font-weight: 900; text-transform: uppercase; letter-spacing: 0.08em; margin-bottom: 6px; color: var(--color-on-surface-dim);">DATA TABLES ({detail.tables.length})</div>
        <div style="overflow-x: auto;">
          <table class="data-table" style="font-size: 11px; width: 100%;">
            <thead>
              <tr>
                <th style="text-align: left;">TABLE</th>
                <th>ROWS</th>
                <th>COLS</th>
                <th>TRAINED</th>
                <th>Q&A</th>
                <th>HEALTH</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {#each detail.tables as t}
                {@const isTrained = knowledgeFiles.some((f: any) => f.type === 'tables' && f.name === t.name + '.json')}
                {@const qaCount = (training?.training_qa || []).filter((q: any) => q.source_table === t.name).length}
                {@const health = isTrained ? (qaCount > 0 ? 100 : 60) : 0}
                <tr style="cursor: pointer;" onclick={() => toggleTableExpand(t.name)}>
                  <td style="font-weight: 900;">{t.name}</td>
                  <td style="text-align: center;">{(t.rows || 0).toLocaleString()}</td>
                  <td style="text-align: center;">{t.columns || '—'}</td>
                  <td style="text-align: center;">
                    {#if isTrained}<span style="color: var(--color-primary); font-weight: 900;">✓</span>{:else}<span style="color: var(--color-on-surface-dim);">○</span>{/if}
                  </td>
                  <td style="text-align: center;">{qaCount}</td>
                  <td style="text-align: center;">
                    <div style="display: inline-flex; align-items: center; gap: 4px;">
                      <div style="width: 40px; height: 5px; background: var(--color-surface-dim);">
                        <div style="height: 100%; width: {health}%; background: {health >= 70 ? 'var(--color-primary)' : health >= 40 ? 'var(--color-warning)' : 'var(--color-error)'};"></div>
                      </div>
                      <span style="font-size: 9px;">{health}%</span>
                    </div>
                  </td>
                  <td style="text-align: center;">
                    <button class="feedback-btn" style="font-size: 7px; color: var(--color-error); border-color: var(--color-error); padding: 1px 5px; cursor: pointer;" onclick={(e) => { e.stopPropagation(); deleteTable(t.name); }}>DEL</button>
                  </td>
                </tr>
              {/each}
            </tbody>
          </table>
        </div>
      </div>
    {/if}

    <!-- Table Detail Cards -->
    {#if !detail?.tables?.length && docs.length === 0}
      <div style="font-size: 12px; color: var(--color-on-surface-dim);">No data yet. Click ↑ UPLOAD DATA to add files.</div>
    {:else if detail?.tables?.length > 0}
      <div class="flex flex-col gap-3">
        {#each detail.tables as t, ti}
          {@const isTrained = training?.training_qa?.some((qa: any) => qa.source_table === t.name) || knowledgeFiles.some((f: any) => f.type === 'tables' && f.name === t.name + '.json')}
          {@const isExpanded = expandedTables[t.name] ?? (ti === 0)}
          {@const meta = tableMetaCache[t.name]}
          {@const inspData = tableInspectCache[t.name]}
          {@const rels = tableRelationships.filter((r: any) => r.table1 === t.name || r.table2 === t.name)}

          <!-- Table Card Header (always visible) -->
          <div class="ink-border" style="overflow: hidden;">
            <!-- svelte-ignore a11y_no_static_element_interactions -->
            <div style="width: 100%; text-align: left; background: var(--color-on-surface); color: var(--color-surface); padding: 10px 16px; cursor: pointer; font-family: var(--font-family-display); display: flex; align-items: center; justify-content: space-between;" onclick={() => toggleTableExpand(t.name)}>
              <div class="flex items-center gap-3">
                <span style="font-size: 14px; font-weight: 900; text-transform: uppercase; letter-spacing: 0.05em;">{t.name}</span>
                {#if isTrained}
                  <span style="font-size: 8px; padding: 2px 6px; background: var(--color-primary); color: white; font-weight: 900; letter-spacing: 0.08em;">TRAINED</span>
                {:else}
                  <span style="font-size: 8px; padding: 2px 6px; background: var(--color-warning); color: var(--color-on-surface); font-weight: 900; letter-spacing: 0.08em;">UNTRAINED</span>
                {/if}
              </div>
              <div class="flex items-center gap-3" style="font-size: 11px;">
                <span>{t.rows?.toLocaleString()} rows</span>
                <span>{t.columns} cols</span>
                <button onclick={(e) => { e.stopPropagation(); deleteTable(t.name); }} style="background: var(--color-error); border: 1px solid var(--color-error); color: white; cursor: pointer; font-size: 8px; font-weight: 900; padding: 2px 8px; font-family: var(--font-family-display); text-transform: uppercase; letter-spacing: 0.06em;">DELETE</button>
                <span style="font-size: 14px;">{isExpanded ? '▲' : '▼'}</span>
              </div>
            </div>

            <!-- Expanded Content -->
            {#if isExpanded}
              <div style="padding: 16px;">

                <!-- Metadata Section -->
                {#if meta}
                  <div style="margin-bottom: 16px;">
                    <div style="font-size: 12px; color: var(--color-on-surface); line-height: 1.5; margin-bottom: 10px;">
                      {meta.table_description || ''}
                    </div>
                    <div style="display: grid; grid-template-columns: repeat(auto-fill, minmax(220px, 1fr)); gap: 8px;">
                      {#if meta.table_purpose}
                        <div style="padding: 8px 12px; background: var(--color-surface-dim); border: 1px solid var(--color-on-surface);">
                          <div style="font-size: 8px; font-weight: 900; text-transform: uppercase; letter-spacing: 0.1em; color: var(--color-on-surface-dim); margin-bottom: 2px;">PURPOSE</div>
                          <div style="font-size: 11px;">{meta.table_purpose}</div>
                        </div>
                      {/if}
                      {#if meta.grain}
                        <div style="padding: 8px 12px; background: var(--color-surface-dim); border: 1px solid var(--color-on-surface);">
                          <div style="font-size: 8px; font-weight: 900; text-transform: uppercase; letter-spacing: 0.1em; color: var(--color-on-surface-dim); margin-bottom: 2px;">GRAIN</div>
                          <div style="font-size: 11px;">{meta.grain}</div>
                        </div>
                      {/if}
                      {#if meta.primary_keys?.length}
                        <div style="padding: 8px 12px; background: var(--color-surface-dim); border: 1px solid var(--color-on-surface);">
                          <div style="font-size: 8px; font-weight: 900; text-transform: uppercase; letter-spacing: 0.1em; color: var(--color-on-surface-dim); margin-bottom: 2px;">PRIMARY KEYS</div>
                          <div style="font-size: 11px; font-weight: 700;">{meta.primary_keys.join(', ')}</div>
                        </div>
                      {/if}
                      {#if meta.freshness}
                        <div style="padding: 8px 12px; background: var(--color-surface-dim); border: 1px solid var(--color-on-surface);">
                          <div style="font-size: 8px; font-weight: 900; text-transform: uppercase; letter-spacing: 0.1em; color: var(--color-on-surface-dim); margin-bottom: 2px;">FRESHNESS</div>
                          <div style="font-size: 11px;">{meta.freshness}</div>
                        </div>
                      {/if}
                    </div>
                  </div>
                {/if}

                <!-- Columns Table -->
                <div style="margin-bottom: 16px;">
                  <div style="font-size: 10px; font-weight: 900; text-transform: uppercase; letter-spacing: 0.1em; margin-bottom: 6px;">COLUMNS ({inspData?.columns?.length || t.columns})</div>
                  {#if inspData?.columns?.length || meta?.table_columns?.length}
                    <div style="overflow-x: auto;">
                      <table class="data-table" style="font-size: 11px;">
                        <thead>
                          <tr>
                            <th style="padding: 5px 10px;">Name</th>
                            <th style="padding: 5px 10px;">Type</th>
                            <th style="padding: 5px 10px;">Null</th>
                            <th style="padding: 5px 10px;">Description</th>
                          </tr>
                        </thead>
                        <tbody>
                          {#each (inspData?.columns || []) as col}
                            {@const metaCol = meta?.table_columns?.find((c: any) => c.name === col.name)}
                            <tr>
                              <td style="padding: 4px 10px; font-weight: 700; font-family: var(--font-family-display);">{col.name}</td>
                              <td style="padding: 4px 10px; font-size: 10px; color: var(--color-on-surface-dim);">{col.type}</td>
                              <td style="padding: 4px 10px; font-size: 10px;">{col.nullable ? 'Yes' : 'No'}</td>
                              <td style="padding: 4px 10px; font-size: 10px; color: var(--color-on-surface-dim);">{metaCol?.description || ''}</td>
                            </tr>
                          {/each}
                        </tbody>
                      </table>
                    </div>
                  {:else}
                    <div style="font-size: 11px; color: var(--color-on-surface-dim);">Loading columns...</div>
                  {/if}
                </div>

                <!-- Sample Data -->
                {#if inspData?.sample?.length}
                  <div style="margin-bottom: 16px;">
                    <div style="font-size: 10px; font-weight: 900; text-transform: uppercase; letter-spacing: 0.1em; margin-bottom: 6px;">SAMPLE DATA (first {inspData.sample.length} rows)</div>
                    <div style="overflow-x: auto;">
                      <table class="data-table" style="font-size: 10px;">
                        <thead>
                          <tr>
                            <th style="padding: 4px 8px; width: 30px;">#</th>
                            {#each Object.keys(inspData.sample[0] || {}) as h}
                              <th style="padding: 4px 8px; white-space: nowrap;">{h}</th>
                            {/each}
                          </tr>
                        </thead>
                        <tbody>
                          {#each inspData.sample.slice(0, 5) as row, ri}
                            <tr>
                              <td style="padding: 3px 8px; color: var(--color-on-surface-dim);">{ri + 1}</td>
                              {#each Object.values(row) as val}
                                <td style="padding: 3px 8px; white-space: nowrap; max-width: 200px; overflow: hidden; text-overflow: ellipsis;">{val ?? ''}</td>
                              {/each}
                            </tr>
                          {/each}
                        </tbody>
                      </table>
                    </div>
                  </div>
                {/if}

                <!-- Data Quality + Relationships side by side -->
                <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 12px; margin-bottom: 16px;">
                  <!-- Data Quality -->
                  {#if meta?.data_quality_notes?.length}
                    <div>
                      <div style="font-size: 10px; font-weight: 900; text-transform: uppercase; letter-spacing: 0.1em; margin-bottom: 6px;">DATA QUALITY</div>
                      <div style="font-size: 11px; line-height: 1.6;">
                        {#each meta.data_quality_notes.slice(0, 4) as note}
                          <div style="display: flex; gap: 6px; margin-bottom: 3px;">
                            <span style="color: var(--color-warning); flex-shrink: 0;">●</span>
                            <span style="color: var(--color-on-surface-dim);">{note.length > 120 ? note.slice(0, 120) + '...' : note}</span>
                          </div>
                        {/each}
                      </div>
                    </div>
                  {/if}

                  <!-- Relationships -->
                  <div>
                    <div style="font-size: 10px; font-weight: 900; text-transform: uppercase; letter-spacing: 0.1em; margin-bottom: 6px;">RELATIONSHIPS</div>
                    {#if rels.length > 0}
                      {#each rels as rel}
                        <div style="display: flex; gap: 6px; margin-bottom: 3px; font-size: 11px;">
                          <span style="color: var(--color-primary); flex-shrink: 0;">→</span>
                          <span style="font-weight: 700;">{rel.table1 === t.name ? rel.table2 : rel.table1}</span>
                          <span style="color: var(--color-on-surface-dim);">({rel.join_type || rel.relationship || 'discovered'})</span>
                          {#if rel.confidence}
                            <span style="color: var(--color-on-surface-dim); font-size: 9px;">{rel.confidence}%</span>
                          {/if}
                        </div>
                      {/each}
                    {:else if meta?.foreign_keys?.length}
                      {#each meta.foreign_keys as fk}
                        <div style="display: flex; gap: 6px; margin-bottom: 3px; font-size: 11px;">
                          <span style="color: var(--color-primary); flex-shrink: 0;">→</span>
                          <span style="font-weight: 700;">{fk.references || fk}</span>
                          <span style="color: var(--color-on-surface-dim);">({fk.relationship || 'FK'})</span>
                        </div>
                      {/each}
                    {:else}
                      <div style="font-size: 11px; color: var(--color-on-surface-dim);">No relationships found</div>
                    {/if}
                  </div>
                </div>

                <!-- Usage Patterns -->
                {#if meta?.usage_patterns?.length || meta?.use_cases?.length}
                  <div style="margin-bottom: 16px;">
                    <div style="font-size: 10px; font-weight: 900; text-transform: uppercase; letter-spacing: 0.1em; margin-bottom: 6px;">USAGE PATTERNS</div>
                    {#each (meta.usage_patterns || meta.use_cases || []).slice(0, 4) as p}
                      <div style="font-size: 11px; color: var(--color-on-surface-dim); margin-bottom: 2px;">• {p}</div>
                    {/each}
                  </div>
                {/if}

                <!-- Actions -->
                <div class="flex gap-2" style="padding-top: 10px; border-top: 1px solid var(--color-surface-dim);">
                  <button class="feedback-btn" style="font-size: 9px; font-weight: 700; text-transform: uppercase; padding: 4px 10px; {trainingTable === t.name ? 'opacity: 0.5;' : ''}" onclick={() => trainTable(t.name)} disabled={!!trainingTable}>{isTrained ? 'RETRAIN' : 'TRAIN'}</button>
                  <button class="feedback-btn" style="font-size: 9px; font-weight: 700; text-transform: uppercase; padding: 4px 10px;" onclick={() => openInspect(t)}>FULL INSPECT</button>
                  {#if inspData?.sample?.length}
                    <button class="feedback-btn" style="font-size: 9px; font-weight: 700; text-transform: uppercase; padding: 4px 10px;" onclick={() => {
                      const headers = Object.keys(inspData.sample[0] || {});
                      const csv = [headers.join(','), ...inspData.sample.map((r: any) => headers.map(h => JSON.stringify(r[h] ?? '')).join(','))].join('\n');
                      const blob = new Blob([csv], { type: 'text/csv' });
                      const url = URL.createObjectURL(blob); const a = document.createElement('a'); a.href = url; a.download = `${t.name}.csv`; a.click(); URL.revokeObjectURL(url);
                    }}>EXPORT CSV</button>
                  {/if}
                </div>
              </div>
            {/if}
          </div>
        {/each}
      </div>
    {/if}


  <!-- ═══ KNOWLEDGE ═══ -->
  {:else if activeTab === 'knowledge'}
    <div class="cli-terminal" style="margin-bottom: 16px; padding: 8px 14px;">
      <div class="cli-line">
        <span class="cli-prompt">$</span>
        <span class="cli-command">dash knowledge</span>
        <span class="cli-output">--status</span>
        <span class="cli-success" style="margin-left: auto;">&#10003; {detail?.knowledge_vectors || 0} vectors</span>
      </div>
      <div class="cli-line">
        <span style="color: #555;">&gt;</span>
        <span class="cli-output">{knowledgeFiles.filter((f: any) => f.type === 'tables').length} table metadata · {knowledgeFiles.filter((f: any) => f.type === 'queries').length} query patterns · {knowledgeFiles.filter((f: any) => f.type === 'business').length} business rules</span>
      </div>
    </div>
    <div style="font-size: 18px; font-weight: 900; text-transform: uppercase; margin-bottom: 16px;">Knowledge</div>

    {#each knowledgeFiles.filter(f => f.type === 'tables') as f}
      {#await fetch(`/api/knowledge-file-content/${f.name}?project=${slug}&subdir=tables`, { headers: _h() }).then(r => r.json()) then data}
        {#if data.type === 'json' && data.content}
          <div class="ink-border mb-3" style="background: var(--color-surface);">
            <div class="dark-title-bar" style="padding: 6px 12px; font-size: 10px;">{data.content.table_name || f.name}</div>
            <div style="padding: 12px; font-size: 11px;">
              <div style="margin-bottom: 8px; color: var(--color-on-surface-dim);">{data.content.table_description || ''}</div>
              {#if data.content.table_columns?.length}
                <div class="tag-label mb-1" style="font-size: 8px;">COLUMNS</div>
                <table style="width: 100%; font-size: 11px; border-collapse: collapse; margin-bottom: 8px;">
                  <thead><tr style="border-bottom: 1px solid var(--color-on-surface);"><th style="text-align: left; padding: 3px 6px;">Name</th><th style="text-align: left; padding: 3px 6px;">Type</th><th style="text-align: left; padding: 3px 6px;">Description</th><th style="padding: 3px 6px; width: 40px;"></th></tr></thead>
                  <tbody>{#each data.content.table_columns as col}
                    {@const ann = brainAnnotations.find((a: any) => a.table_name === data.content.table_name && a.column_name === col.name)}
                    <tr style="border-bottom: 1px solid var(--color-surface-dim);">
                      <td style="padding: 2px 6px; font-weight: 700;">{col.name}</td>
                      <td style="padding: 2px 6px;">{col.type}</td>
                      <td style="padding: 2px 6px; color: var(--color-on-surface-dim);">
                        {#if ann}<span style="color: var(--color-primary); font-weight: 700;">{ann.annotation}</span>{:else}{col.description || ''}{/if}
                      </td>
                      <td style="padding: 2px 6px;">
                        <button class="feedback-btn" style="font-size: 8px; padding: 1px 4px;" onclick={() => {
                          const newVal = prompt('Business meaning for ' + col.name + ':', ann?.annotation || col.description || '');
                          if (newVal) { fetch(`/api/projects/${slug}/annotations`, { method: 'PUT', headers: { ..._h(), 'Content-Type': 'application/json' }, body: JSON.stringify({ table_name: data.content.table_name, column_name: col.name, annotation: newVal }) }).then(() => loadBrainData()); }
                        }}>EDIT</button>
                      </td>
                    </tr>
                  {/each}</tbody>
                </table>
              {/if}
              {#if data.content.use_cases?.length}
                <div class="tag-label mb-1" style="font-size: 8px;">USE CASES</div>
                <div style="margin-bottom: 8px;">{#each data.content.use_cases as uc}<div style="font-size: 10px; color: var(--color-on-surface-dim);">· {uc}</div>{/each}</div>
              {/if}
              {#if data.content.data_quality_notes?.length}
                <div class="tag-label mb-1" style="font-size: 8px;">DATA QUALITY</div>
                {#each data.content.data_quality_notes as n}<div style="font-size: 10px; color: var(--color-warning);">⚠ {n}</div>{/each}
              {/if}
            </div>
          </div>
        {/if}
      {/await}
    {/each}

    {#if knowledgeFiles.filter(f => f.type === 'business').length > 0}
      {#each knowledgeFiles.filter(f => f.type === 'business') as f}
        {#await fetch(`/api/knowledge-file-content/${f.name}?project=${slug}&subdir=business`, { headers: _h() }).then(r => r.json()) then data}
          {#if data.type === 'json' && data.content}
            <div class="ink-border mb-3" style="background: var(--color-surface);">
              <div class="dark-title-bar" style="padding: 6px 12px; font-size: 10px;">BUSINESS RULES</div>
              <div style="padding: 12px; font-size: 11px;">
                {#if data.content.metrics?.length}
                  {#each data.content.metrics as m}
                    <div style="margin-bottom: 6px;"><strong>{m.name}</strong>: {m.definition} <span style="color: var(--color-on-surface-dim);">({m.calculation})</span></div>
                  {/each}
                {/if}
              </div>
            </div>
          {/if}
        {/await}
      {/each}
    {/if}

    {#if knowledgeFiles.length === 0}
      <div style="font-size: 12px; color: var(--color-on-surface-dim);">Upload data to auto-generate knowledge.</div>
    {/if}

  <!-- ═══ RULES ═══ -->
  {:else if activeTab === 'rules'}
    <div class="cli-terminal" style="margin-bottom: 16px; padding: 8px 14px;">
      <div class="cli-line">
        <span class="cli-prompt">$</span>
        <span class="cli-command">dash rules</span>
        <span class="cli-output">--list</span>
        <span class="cli-dim" style="margin-left: auto;">{rules.length} active · {suggestedRules.length} pending</span>
      </div>
    </div>
    <div class="flex items-center justify-between mb-4">
      <div style="font-size: 18px; font-weight: 900; text-transform: uppercase;">Business Rules</div>
      <div class="flex gap-2">
        <button class="send-btn" style="font-size: 10px; padding: 6px 14px;" onclick={() => showAddRule = true}>+ ADD RULE</button>
        <button class="feedback-btn" style="font-size: 10px; padding: 6px 14px; font-weight: 700;" onclick={() => {
          const rule = prompt('Type a rule in plain English (e.g., "MRR excludes churned customers"):');
          if (rule) { fetch(`/api/projects/${slug}/nl-to-rule`, { method: 'POST', headers: { ..._h(), 'Content-Type': 'application/json' }, body: JSON.stringify({ rule }) }).then(() => { loadRules(); loadBrainData(); }); }
        }}>AI CONVERT</button>
      </div>
    </div>
    <div style="font-size: 11px; color: var(--color-on-surface-dim); margin-bottom: 16px;">
      Define business rules your agent must follow. Rules like "MRR = active subscriptions only" or "fiscal year starts April" are injected into the agent's instructions.
    </div>

    {#if showAddRule}
      <div class="ink-border stamp-shadow" style="background: var(--color-surface-bright); padding: 16px; margin-bottom: 16px;">
        <div style="font-size: 11px; font-weight: 900; text-transform: uppercase; margin-bottom: 10px;">NEW RULE</div>
        <div style="margin-bottom: 8px;">
          <div style="font-size: 9px; font-weight: 700; text-transform: uppercase; margin-bottom: 3px;">NAME</div>
          <input type="text" bind:value={newRuleName} placeholder="e.g., Revenue = MRR * 12" style="width: 100%; border: 2px solid var(--color-on-surface); padding: 6px 10px; font-family: var(--font-family-display); font-size: 12px; background: var(--color-surface);" />
        </div>
        <div style="margin-bottom: 8px;">
          <div style="font-size: 9px; font-weight: 700; text-transform: uppercase; margin-bottom: 3px;">TYPE</div>
          <select bind:value={newRuleType} style="border: 2px solid var(--color-on-surface); padding: 6px 10px; font-family: var(--font-family-display); font-size: 12px; background: var(--color-surface);">
            <option value="business_rule">Business Rule</option>
            <option value="metric">Metric Definition</option>
            <option value="gotcha">Common Gotcha</option>
            <option value="calculation">Calculation</option>
          </select>
        </div>
        <div style="margin-bottom: 12px;">
          <div style="font-size: 9px; font-weight: 700; text-transform: uppercase; margin-bottom: 3px;">DEFINITION</div>
          <textarea bind:value={newRuleDefinition} placeholder="Describe the rule the agent should follow..." rows="3" style="width: 100%; border: 2px solid var(--color-on-surface); padding: 6px 10px; font-family: var(--font-family-display); font-size: 12px; background: var(--color-surface); resize: vertical;"></textarea>
        </div>
        <div class="flex gap-2">
          <button class="send-btn" style="font-size: 10px; padding: 6px 14px;" onclick={addRule} disabled={ruleSaving || !newRuleName || !newRuleDefinition}>
            {ruleSaving ? 'SAVING...' : 'SAVE RULE'}
          </button>
          <button class="feedback-btn" style="font-size: 10px; padding: 6px 14px;" onclick={() => showAddRule = false}>CANCEL</button>
        </div>
      </div>
    {/if}

    {#if rules.length > 0}
      <div style="display: flex; flex-direction: column; gap: 8px;">
        {#each rules as rule}
          <div class="ink-border" style="background: var(--color-surface-bright); padding: 12px 16px;">
            <div class="flex items-center justify-between">
              <div>
                <span style="font-size: 13px; font-weight: 900;">{rule.name}</span>
                <span class="tag-label" style="font-size: 8px; margin-left: 8px;">{rule.type?.replace('_', ' ')}</span>
              </div>
              <button class="feedback-btn" style="font-size: 9px; padding: 3px 8px; color: var(--color-error);" onclick={() => deleteRule(rule.id)} title="Delete rule">
                <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="3 6 5 6 21 6"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/></svg>
              </button>
            </div>
            <div style="font-size: 12px; color: var(--color-on-surface-dim); margin-top: 6px;">{rule.definition}</div>
            {#if rule.created_at}
              <div style="font-size: 9px; color: var(--color-on-surface-dim); margin-top: 6px; text-transform: uppercase; letter-spacing: 0.08em;">
                {rule.source === 'user' ? 'USER-DEFINED' : 'AUTO-SUGGESTED'} &middot; {rule.created_at?.slice(0, 10)}
              </div>
            {/if}
          </div>
        {/each}
      </div>
    {:else}
      <div style="text-align: center; padding: 40px 20px; color: var(--color-on-surface-dim); font-size: 12px;">
        No rules defined yet. Add rules to make your agent smarter.
      </div>
    {/if}

    <!-- Suggested Rules (from Knowledge Harness) -->
    {#if suggestedRules.length > 0}
      <div style="margin-top: 24px; border-top: 2px solid var(--color-on-surface); padding-top: 16px;">
        <div style="font-size: 14px; font-weight: 900; text-transform: uppercase; margin-bottom: 8px;">
          AI-SUGGESTED RULES
          <span class="tag-label" style="font-size: 8px; margin-left: 6px; background: var(--color-warning); color: var(--color-on-surface);">{suggestedRules.length} PENDING</span>
        </div>
        <div style="font-size: 11px; color: var(--color-on-surface-dim); margin-bottom: 12px;">
          These rules were extracted from your conversations. Approve to add them to the agent's instructions.
        </div>
        <div style="display: flex; flex-direction: column; gap: 8px;">
          {#each suggestedRules as sr}
            <div class="ink-border" style="background: var(--color-surface); padding: 12px 16px; border-left: 3px solid var(--color-warning);">
              <div style="font-size: 13px; font-weight: 900;">{sr.name}</div>
              <div style="font-size: 12px; color: var(--color-on-surface-dim); margin-top: 4px;">{sr.definition}</div>
              <div class="flex gap-2 mt-2">
                <button class="send-btn" style="font-size: 9px; padding: 4px 12px;" onclick={() => approveRule(sr.id)}>APPROVE</button>
                <button class="feedback-btn" style="font-size: 9px; padding: 4px 12px;" onclick={() => rejectRule(sr.id)}>REJECT</button>
              </div>
            </div>
          {/each}
        </div>
      </div>
    {/if}

  <!-- ═══ TRAINING (Agent Brain) ═══ -->
  {:else if activeTab === 'training'}
    <!-- CLI Status -->
    <div class="cli-terminal" style="margin-bottom: 16px; padding: 10px 14px;">
      <div class="cli-line">
        <span class="cli-prompt">$</span>
        <span class="cli-command">dash brain</span>
        <span class="cli-output">--verbose</span>
      </div>
      <div class="cli-line"><span style="color: #555;">&gt;</span><span class="cli-check">&#10003;</span><span class="cli-output">error learnings: {training?.learnings || 0}</span></div>
      <div class="cli-line"><span style="color: #555;">&gt;</span><span class="cli-check">&#10003;</span><span class="cli-output">training Q&A: {training?.training_qa?.length || 0}</span></div>
      <div class="cli-line"><span style="color: #555;">&gt;</span><span class="cli-check">&#10003;</span><span class="cli-output">approved responses: {brainFeedback.filter(f => f.rating === 'up').length}</span></div>
      <div class="cli-line"><span style="color: #555;">&gt;</span><span class="cli-check">&#10003;</span><span class="cli-output">rejected patterns: {brainFeedback.filter(f => f.rating === 'down').length}</span></div>
      <div class="cli-line"><span style="color: #555;">&gt;</span><span class="cli-check">&#10003;</span><span class="cli-output">proven queries: {brainPatterns.length}</span></div>
      <div class="cli-line"><span style="color: #555;">&gt;</span><span class="cli-check">&#10003;</span><span class="cli-output">remembered facts: {brainMemories.length}</span></div>
    </div>

    <div class="flex items-center justify-between mb-4">
      <div style="font-size: 18px; font-weight: 900; text-transform: uppercase;">Agent Brain</div>
      <div class="flex gap-2">
        <button class="send-btn" style="font-size: 10px; padding: 6px 14px;" onclick={() => { window.dispatchEvent(new CustomEvent('dash-train-all')); }}>RETRAIN AGENT</button>
        <button class="feedback-btn" style="font-size: 10px; padding: 6px 14px; font-weight: 700;" onclick={async () => {
          try { const r = await fetch(`/api/projects/${slug}/quality-check`, { method: 'POST', headers: _h() }); if (r.ok) { const d = await r.json(); alert(`Checked ${d.tables_checked} tables. Found ${d.issues.length} issues.`); } } catch {}
        }}>QUALITY CHECK</button>
      </div>
    </div>

    <!-- Stats Grid -->
    <div style="display: grid; grid-template-columns: repeat(3, 1fr); gap: 8px; margin-bottom: 20px;">
      {#each [
        { label: 'ERROR LEARNINGS', value: training?.learnings || 0, color: 'var(--color-error)' },
        { label: 'TRAINING Q&A', value: training?.training_qa?.length || 0, color: 'var(--color-primary)' },
        { label: 'FEEDBACK', value: brainFeedback.length, color: 'var(--color-secondary)' },
        { label: 'PROVEN SQL', value: brainPatterns.length, color: 'var(--color-primary)' },
        { label: 'MEMORIES', value: brainMemories.length, color: 'var(--color-warning)' },
        { label: 'ANNOTATIONS', value: brainAnnotations.length, color: 'var(--color-secondary)' },
      ] as stat}
        <div class="ink-border" style="background: var(--color-surface-bright); padding: 10px; text-align: center;">
          <div style="font-size: 20px; font-weight: 900; color: {stat.color};">{stat.value}</div>
          <div style="font-size: 8px; text-transform: uppercase; color: var(--color-on-surface-dim); letter-spacing: 0.06em;">{stat.label}</div>
        </div>
      {/each}
    </div>

    <!-- Memories -->
    <!-- Training History -->
    {#if trainingRuns.length > 0}
      <div style="font-size: 13px; font-weight: 900; text-transform: uppercase; margin-bottom: 8px; margin-top: 16px;">TRAINING HISTORY</div>
      <div class="cli-terminal" style="padding: 10px 14px; margin-bottom: 16px;">
        {#each trainingRuns.slice(0, 5) as run}
          <div class="cli-line">
            <span style="color: {run.status === 'done' ? '#00fc40' : run.status === 'failed' ? '#ff6b6b' : '#ff9d00'};">
              {run.status === 'done' ? '✓' : run.status === 'failed' ? '✗' : '●'}
            </span>
            <span class="cli-output">{run.started_at?.slice(0, 16)} · {run.tables} table{run.tables !== 1 ? 's' : ''} · {run.status}</span>
            {#if run.finished_at && run.started_at}
              <span class="cli-dim" style="margin-left: auto;">{((new Date(run.finished_at).getTime() - new Date(run.started_at).getTime()) / 1000).toFixed(1)}s</span>
            {/if}
          </div>
          {#if run.error}
            <div class="cli-line" style="padding-left: 16px;"><span style="color: #ff6b6b; font-size: 10px;">{run.error.slice(0, 100)}</span></div>
          {/if}
        {/each}
      </div>
    {/if}

    <!-- Drift Alerts -->
    {#if driftAlerts.length > 0}
      <div style="font-size: 13px; font-weight: 900; text-transform: uppercase; margin-bottom: 8px;">DATA DRIFT ALERTS</div>
      <div style="display: flex; flex-direction: column; gap: 6px; margin-bottom: 16px;">
        {#each driftAlerts as da}
          <div class="ink-border" style="background: var(--color-surface-bright); padding: 10px 14px; border-left: 3px solid var(--color-warning);">
            <div style="font-size: 11px; font-weight: 900;">{da.table_name}</div>
            {#each da.alerts as alert}
              <div style="font-size: 10px; color: var(--color-warning); margin-top: 2px;">⚠ {alert}</div>
            {/each}
            <div style="font-size: 8px; color: var(--color-on-surface-dim); margin-top: 4px;">{da.created_at?.slice(0, 16)}</div>
          </div>
        {/each}
      </div>
    {/if}

    <div style="font-size: 13px; font-weight: 900; text-transform: uppercase; margin-bottom: 8px; margin-top: 16px;">AGENT MEMORIES</div>
    <div class="flex gap-2 items-end mb-3">
      <input type="text" bind:value={newMemoryFact} placeholder="Add a fact the agent should remember..." style="flex: 1; border: 2px solid var(--color-on-surface); padding: 5px 10px; font-family: var(--font-family-display); font-size: 11px; background: var(--color-surface);" />
      <select bind:value={newMemoryScope} style="border: 2px solid var(--color-on-surface); padding: 5px 8px; font-family: var(--font-family-display); font-size: 10px; background: var(--color-surface);">
        <option value="project">PROJECT</option>
        <option value="personal">PERSONAL</option>
        <option value="global">GLOBAL</option>
      </select>
      <button class="feedback-btn" style="font-size: 9px; font-weight: 700; padding: 5px 10px;" onclick={async () => {
        if (!newMemoryFact) return;
        await fetch(`/api/projects/${slug}/memories`, { method: 'POST', headers: { ..._h(), 'Content-Type': 'application/json' }, body: JSON.stringify({ fact: newMemoryFact, scope: newMemoryScope }) });
        newMemoryFact = ''; await loadBrainData();
      }}>+ ADD</button>
    </div>
    {#if brainMemories.length > 0}
      <div class="cli-terminal" style="padding: 10px 14px; margin-bottom: 16px;">
        {#each brainMemories as m}
          <div class="cli-line">
            <span style="color: #ff9d00;">&#9679;</span>
            <span class="cli-output">{m.fact}</span>
            <span class="cli-dim" style="margin-left: auto; font-size: 8px;">{m.scope}</span>
            <button onclick={async () => { await fetch(`/api/projects/${slug}/memories/${m.id}`, { method: 'DELETE', headers: _h() }); await loadBrainData(); }} style="background: none; border: none; color: #555; cursor: pointer; font-size: 10px; margin-left: 4px;">&#10005;</button>
          </div>
        {/each}
      </div>
    {:else}
      <div style="font-size: 11px; color: var(--color-on-surface-dim); margin-bottom: 16px;">No memories yet. Add facts or chat with the agent — it learns automatically.</div>
    {/if}

    <!-- Proven Query Patterns -->
    {#if brainPatterns.length > 0}
      <div style="font-size: 13px; font-weight: 900; text-transform: uppercase; margin-bottom: 8px;">PROVEN QUERIES ({brainPatterns.length})</div>
      <div style="display: flex; flex-direction: column; gap: 6px; margin-bottom: 16px;">
        {#each brainPatterns.slice(0, 8) as p}
          <div class="ink-border" style="background: var(--color-surface-bright); padding: 10px 14px;">
            <div class="flex items-center justify-between">
              <div style="font-size: 11px; font-weight: 900; color: var(--color-primary);">Q: {p.question}</div>
              <span style="font-size: 9px; color: var(--color-on-surface-dim);">used {p.uses}x</span>
            </div>
            <div class="cli-terminal" style="margin-top: 4px; padding: 6px 10px; font-size: 10px;">
              <code style="color: #e0e0e0;">{p.sql}</code>
            </div>
          </div>
        {/each}
      </div>
    {/if}

    <!-- Feedback -->
    {#if brainFeedback.length > 0}
      <div style="font-size: 13px; font-weight: 900; text-transform: uppercase; margin-bottom: 8px;">USER FEEDBACK ({brainFeedback.length})</div>
      <div style="display: flex; flex-direction: column; gap: 6px; margin-bottom: 16px;">
        {#each brainFeedback.slice(0, 8) as f}
          <div class="ink-border" style="background: var(--color-surface-bright); padding: 10px 14px; border-left: 3px solid {f.rating === 'up' ? 'var(--color-primary)' : 'var(--color-error)'};">
            <div class="flex items-center gap-2">
              <span style="font-size: 14px;">{f.rating === 'up' ? '👍' : '👎'}</span>
              <div style="font-size: 11px; font-weight: 700;">Q: {f.question}</div>
            </div>
            {#if f.answer}<div style="font-size: 10px; color: var(--color-on-surface-dim); margin-top: 2px;">{f.answer?.slice(0, 150)}...</div>{/if}
          </div>
        {/each}
      </div>
    {/if}

    <!-- Training Q&A Pairs -->
    {#if training?.training_qa && training.training_qa.length > 0}
      <div style="font-size: 13px; font-weight: 900; text-transform: uppercase; margin-bottom: 8px;">TRAINING Q&A PAIRS</div>
      <div style="display: flex; flex-direction: column; gap: 6px; margin-bottom: 16px;">
        {#each training.training_qa as qa}
          <div class="ink-border" style="background: var(--color-surface-bright); padding: 10px 14px;">
            <div style="font-size: 11px; font-weight: 900; color: var(--color-primary);">Q: {qa.question}</div>
            <div class="cli-terminal" style="margin-top: 4px; padding: 6px 10px; font-size: 10px;">
              <code style="color: #e0e0e0;">{qa.sql}</code>
            </div>
            {#if qa.source_table}
              <div style="font-size: 8px; color: var(--color-on-surface-dim); margin-top: 3px; text-transform: uppercase;">TABLE: {qa.source_table}</div>
            {/if}
          </div>
        {/each}
      </div>
    {/if}

    {#if !training?.training_qa?.length && !brainFeedback.filter(f => f.rating === 'up').length && !brainPatterns.length && !brainMemories.length}
      <div style="text-align: center; padding: 30px; color: var(--color-on-surface-dim); font-size: 12px;">
        No training data yet. Upload data or click RETRAIN AGENT. Chat with the agent and use thumbs up/down to teach it.
      </div>
    {/if}

    <!-- Self-Evolution Section Divider -->
    <div style="margin-top: 30px; border-top: 3px solid var(--color-on-surface); padding-top: 16px; margin-bottom: 16px;">
      <div style="font-size: 14px; font-weight: 900; text-transform: uppercase; letter-spacing: 0.1em; color: var(--color-primary);">SELF-EVOLUTION</div>
      <div style="font-size: 10px; color: var(--color-on-surface-dim); margin-top: 2px;">Auto-learned from your conversations. Updates after each chat.</div>
    </div>

    <!-- Self-Evolution: Proactive Insights -->
    <div style="margin-top: 12px; font-size: 11px; font-weight: 900; text-transform: uppercase; letter-spacing: 0.08em; margin-bottom: 8px;">PROACTIVE INSIGHTS</div>
    {#if insights.length > 0}
      {#each insights as ins}
        <div class="ink-border" style="padding: 8px 14px; margin-bottom: 6px; background: {ins.severity === 'critical' ? '#fde8e4' : ins.severity === 'warning' ? '#fff3cd' : 'var(--color-surface-bright)'}; display: flex; align-items: center; gap: 8px;">
          <span style="font-size: 8px; font-weight: 900; padding: 1px 6px; background: {ins.severity === 'critical' ? 'var(--color-error)' : ins.severity === 'warning' ? 'var(--color-warning)' : 'var(--color-primary)'}; color: white; text-transform: uppercase;">{ins.severity}</span>
          <span style="flex: 1; font-size: 11px;">{ins.insight}</span>
          <button class="feedback-btn" onclick={async () => { await fetch(`/api/projects/${slug}/insights/${ins.id}/dismiss`, { method: 'POST', headers: _h() }); insights = insights.filter(i => i.id !== ins.id); }} style="font-size: 9px; padding: 2px 8px;">DISMISS</button>
        </div>
      {/each}
    {:else}
      <div style="font-size: 10px; color: var(--color-on-surface-dim);">No anomalies detected yet. Chat with the agent to generate insights.</div>
    {/if}

    <!-- Self-Evolution: User Preferences -->
    <div style="margin-top: 20px; font-size: 11px; font-weight: 900; text-transform: uppercase; letter-spacing: 0.08em; margin-bottom: 8px;">USER PREFERENCES (auto-tracked)</div>
    {#if Object.keys(userPreferences).length > 0}
      <div style="display: flex; gap: 12px; flex-wrap: wrap;">
        {#if userPreferences.chart_type_counts}
          <div class="ink-border" style="padding: 10px 14px; background: var(--color-surface-bright); flex: 1; min-width: 200px;">
            <div style="font-size: 9px; font-weight: 900; text-transform: uppercase; color: var(--color-on-surface-dim); margin-bottom: 6px;">CHART TYPE CLICKS</div>
            {#each Object.entries(userPreferences.chart_type_counts) as [type, count]}
              <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 3px;">
                <span style="font-size: 11px; font-weight: 700; width: 60px; text-transform: uppercase;">{type}</span>
                <div style="flex: 1; height: 8px; background: var(--color-surface-dim);"><div style="height: 100%; background: var(--color-primary); width: {Math.min(100, Number(count) * 10)}%;"></div></div>
                <span style="font-size: 10px; font-weight: 900; width: 24px; text-align: right;">{count}</span>
              </div>
            {/each}
          </div>
        {/if}
        {#if userPreferences.tab_click_counts}
          <div class="ink-border" style="padding: 10px 14px; background: var(--color-surface-bright); flex: 1; min-width: 200px;">
            <div style="font-size: 9px; font-weight: 900; text-transform: uppercase; color: var(--color-on-surface-dim); margin-bottom: 6px;">TAB CLICKS</div>
            {#each Object.entries(userPreferences.tab_click_counts) as [tab, count]}
              <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 3px;">
                <span style="font-size: 11px; font-weight: 700; width: 60px; text-transform: uppercase;">{tab}</span>
                <div style="flex: 1; height: 8px; background: var(--color-surface-dim);"><div style="height: 100%; background: var(--color-secondary); width: {Math.min(100, Number(count) * 10)}%;"></div></div>
                <span style="font-size: 10px; font-weight: 900; width: 24px; text-align: right;">{count}</span>
              </div>
            {/each}
          </div>
        {/if}
      </div>
    {:else}
      <div style="font-size: 10px; color: var(--color-on-surface-dim);">No preferences tracked yet. Use the chat — click tabs and chart types to build your profile.</div>
    {/if}

    <!-- Self-Evolution: Meta-Learning -->
    <div style="margin-top: 20px; font-size: 11px; font-weight: 900; text-transform: uppercase; letter-spacing: 0.08em; margin-bottom: 8px;">SELF-CORRECTION STRATEGIES (auto-learned)</div>
    {#if metaLearnings.length > 0}
      <div style="overflow-x: auto;">
        <table class="data-table" style="font-size: 11px;">
          <thead><tr><th>ERROR TYPE</th><th>FIX STRATEGY</th><th>SUCCESS RATE</th><th>ATTEMPTS</th></tr></thead>
          <tbody>
            {#each metaLearnings as ml}
              <tr>
                <td><code style="font-size: 10px;">{ml.error_type}</code></td>
                <td><code style="font-size: 10px;">{ml.fix_strategy}</code></td>
                <td><span style="font-weight: 900; color: {ml.success_rate >= 70 ? 'var(--color-primary)' : ml.success_rate >= 40 ? 'var(--color-warning)' : 'var(--color-error)'};">{ml.success_rate}%</span></td>
                <td>{ml.count}</td>
              </tr>
            {/each}
          </tbody>
        </table>
      </div>
    {:else}
      <div style="font-size: 10px; color: var(--color-on-surface-dim);">No self-correction data yet. The agent learns fix strategies as it encounters and resolves errors.</div>
    {/if}

    <!-- Self-Evolution: Knowledge Consolidation -->
    <div style="margin-top: 20px; font-size: 11px; font-weight: 900; text-transform: uppercase; letter-spacing: 0.08em; margin-bottom: 8px;">KNOWLEDGE CONSOLIDATION</div>
    <div class="ink-border" style="padding: 12px 14px; background: var(--color-surface-bright); display: flex; align-items: center; gap: 12px;">
      <div style="flex: 1;">
        <div style="font-size: 12px;"><strong>{consolidationStatus.memory_count}</strong> memories</div>
        <div style="font-size: 10px; color: var(--color-on-surface-dim);">{consolidationStatus.eligible ? 'Ready to consolidate — compress into higher-level insights' : 'Need 30+ memories to consolidate'}</div>
      </div>
      <button class="send-btn" disabled={!consolidationStatus.eligible || consolidating} style="font-size: 10px; padding: 6px 14px;" onclick={async () => {
        consolidating = true;
        cLog(`${ts()} ── consolidating ${consolidationStatus.memory_count} memories...`);
        try {
          const r = await fetch(`/api/projects/${slug}/consolidate-knowledge`, { method: 'POST', headers: _h() });
          const d = await r.json();
          if (d.status === 'ok') { cLog(`${ts()} │  ✓ ${d.archived} memories → ${d.consolidated} insights`); loadConsolidationStatus(); loadBrainData(); }
          else cLog(`${ts()} │  ✗ ${d.detail || 'failed'}`);
        } catch {} finally { consolidating = false; }
      }}>{consolidating ? 'CONSOLIDATING...' : 'CONSOLIDATE'}</button>
    </div>

  <!-- ═══ DOCS ═══ -->
  {:else if activeTab === 'docs'}
    <div class="cli-terminal" style="margin-bottom: 16px; padding: 8px 14px;">
      <div class="cli-line">
        <span class="cli-prompt">$</span>
        <span class="cli-command">dash docs</span>
        <span class="cli-output">--list</span>
        <span class="cli-dim" style="margin-left: auto;">{docs.length} files · {(docs.reduce((s: number, d: any) => s + (d.size || 0), 0) / 1024).toFixed(1)} KB</span>
      </div>
    </div>
    <div class="flex items-center justify-between mb-4">
      <div style="font-size: 18px; font-weight: 900; text-transform: uppercase;">Documents</div>
      <button class="send-btn" onclick={() => { showDocUpload = true; docFile = null; docResult = null; }} style="padding: 6px 14px; font-size: 10px; cursor: pointer;">+ ADD DOC</button>
    </div>
    <div style="font-size: 11px; color: var(--color-on-surface-dim); margin-bottom: 12px;">Upload SQL, Python, or text files to give the agent business context.</div>
    {#if docs.length > 0}
      {#each docs as d}
        <div class="flex items-center justify-between py-2" style="border-bottom: 1px solid var(--color-surface-dim); font-size: 12px;">
          <div class="flex items-center gap-2"><span style="font-weight: 900;">{d.name}</span><span class="tag-label" style="font-size: 7px; padding: 1px 4px;">{d.type}</span></div>
          <div class="flex items-center gap-3">
            {#if ['.pptx', '.pdf', '.docx'].includes(d.type)}
              {#if docWorkflowCreated.has(d.name)}
                <span style="font-size: 8px; font-weight: 900; color: var(--color-primary); text-transform: uppercase; letter-spacing: 0.05em;">✓ WORKFLOW</span>
              {:else}
                <button class="feedback-btn" style="font-size: 8px; padding: 2px 8px; cursor: pointer; font-weight: 900; text-transform: uppercase;"
                  disabled={docToWorkflowLoading === d.name}
                  onclick={async () => {
                    docToWorkflowLoading = d.name;
                    try {
                      const r = await fetch(`/api/projects/${slug}/doc-to-workflow`, {
                        method: 'POST', headers: { ..._h(), 'Content-Type': 'application/json' },
                        body: JSON.stringify({ filename: d.name })
                      });
                      if (r.ok) {
                        const data = await r.json();
                        docWorkflowPreview = data.workflow;
                      } else {
                        const err = await r.json().catch(() => ({}));
                        alert(err.detail || 'Failed to extract workflow');
                      }
                    } catch { alert('Failed to extract workflow'); }
                    docToWorkflowLoading = null;
                  }}>{docToWorkflowLoading === d.name ? 'EXTRACTING...' : '→ WORKFLOW'}</button>
              {/if}
            {/if}
            <span style="color: var(--color-on-surface-dim); font-size: 10px;">{(d.size / 1024).toFixed(1)} KB</span>
            <button class="feedback-btn" style="font-size: 9px; color: var(--color-error); border-color: var(--color-error); padding: 2px 8px; cursor: pointer;" onclick={() => deleteDoc(d.name)}>DEL</button>
          </div>
        </div>
      {/each}
    {:else}<div style="font-size: 12px; color: var(--color-on-surface-dim);">No documents. Add SQL files or business docs for richer context.</div>{/if}

    <!-- Doc-to-Workflow Preview Modal -->
    {#if docWorkflowPreview}
      <div style="position: fixed; inset: 0; background: rgba(0,0,0,0.5); z-index: 999; display: flex; align-items: center; justify-content: center;"
        onclick={(e) => { if (e.target === e.currentTarget) docWorkflowPreview = null; }}>
        <div class="ink-border stamp-shadow" style="background: var(--color-surface); width: 560px; max-height: 80vh; overflow-y: auto;">
          <div class="dark-title-bar" style="padding: 8px 14px; font-size: 11px; display: flex; justify-content: space-between; align-items: center;">
            <span>WORKFLOW PREVIEW — {docWorkflowPreview.source_file || ''}</span>
            <button onclick={() => docWorkflowPreview = null} style="background: none; border: none; color: var(--color-primary-container); cursor: pointer; font-size: 14px;">&times;</button>
          </div>
          <div style="padding: 16px;">
            <div style="margin-bottom: 12px;">
              <label style="font-size: 9px; font-weight: 900; text-transform: uppercase; letter-spacing: 0.08em; display: block; margin-bottom: 4px;">Workflow Name</label>
              <input type="text" bind:value={docWorkflowPreview.name} style="width: 100%; padding: 6px 10px; font-size: 12px; border: 1px solid var(--color-surface-dim); font-family: var(--font-family-display); background: var(--color-surface-bright);" />
            </div>
            <div style="margin-bottom: 12px;">
              <label style="font-size: 9px; font-weight: 900; text-transform: uppercase; letter-spacing: 0.08em; display: block; margin-bottom: 4px;">Description</label>
              <input type="text" bind:value={docWorkflowPreview.description} style="width: 100%; padding: 6px 10px; font-size: 12px; border: 1px solid var(--color-surface-dim); font-family: var(--font-family-display); background: var(--color-surface-bright);" />
            </div>
            <div style="margin-bottom: 12px;">
              <label style="font-size: 9px; font-weight: 900; text-transform: uppercase; letter-spacing: 0.08em; display: block; margin-bottom: 8px;">Steps ({docWorkflowPreview.steps?.length || 0})</label>
              {#each docWorkflowPreview.steps || [] as step, i}
                <div class="flex items-center gap-2 mb-2" style="border-left: 2px solid var(--color-primary); padding-left: 8px;">
                  <span style="font-size: 10px; font-weight: 900; color: var(--color-on-surface-dim); min-width: 18px;">{i + 1}</span>
                  <input type="text" bind:value={step.question} style="flex: 1; padding: 5px 8px; font-size: 11px; border: 1px solid var(--color-surface-dim); font-family: var(--font-family-display); background: var(--color-surface-bright);" />
                  <button onclick={() => { docWorkflowPreview.steps = docWorkflowPreview.steps.filter((_: any, j: number) => j !== i); docWorkflowPreview = docWorkflowPreview; }}
                    style="background: none; border: none; cursor: pointer; font-size: 12px; color: var(--color-error); padding: 2px;">&times;</button>
                </div>
              {/each}
            </div>
            <div class="flex justify-end gap-2">
              <button class="feedback-btn" style="padding: 6px 14px; font-size: 10px; cursor: pointer;" onclick={() => docWorkflowPreview = null}>CANCEL</button>
              <button class="send-btn" style="padding: 6px 14px; font-size: 10px; cursor: pointer;"
                onclick={async () => {
                  const steps = (docWorkflowPreview.steps || []).map((s: any) => typeof s === 'string' ? s : s.question || s.title || String(s));
                  try {
                    const r = await fetch(`/api/projects/${slug}/workflows-db`, {
                      method: 'POST', headers: { ..._h(), 'Content-Type': 'application/json' },
                      body: JSON.stringify({ name: docWorkflowPreview.name, description: docWorkflowPreview.description, steps, source: 'document' })
                    });
                    if (r.ok) {
                      const sourceFile = docWorkflowPreview.source_file;
                      docWorkflowCreated = new Set([...docWorkflowCreated, sourceFile]);
                      docWorkflowPreview = null;
                      loadWorkflows();
                    } else {
                      const err = await r.json().catch(() => ({}));
                      alert(err.detail || 'Failed to save workflow');
                    }
                  } catch { alert('Failed to save workflow'); }
                }}>SAVE WORKFLOW</button>
            </div>
          </div>
        </div>
      </div>
    {/if}

  <!-- ═══ QUERIES ═══ -->
  {:else if activeTab === 'queries'}
    <div class="cli-terminal" style="margin-bottom: 16px; padding: 8px 14px;">
      <div class="cli-line">
        <span class="cli-prompt">$</span>
        <span class="cli-command">dash queries</span>
        <span class="cli-output">--all</span>
        <span class="cli-dim" style="margin-left: auto;">{brainPatterns.length} patterns · {queryPlans.length} join strategies</span>
      </div>
    </div>

    <!-- Proven Query Patterns from DB -->
    <div style="font-size: 18px; font-weight: 900; text-transform: uppercase; margin-bottom: 16px;">Query Patterns ({brainPatterns.length})</div>
    {#if brainPatterns.length > 0}
      <div style="overflow-x: auto; margin-bottom: 20px;">
        <table class="data-table" style="font-size: 11px; width: 100%;">
          <thead>
            <tr>
              <th style="text-align: left;">QUESTION</th>
              <th>TABLES</th>
              <th>USES</th>
              <th>SOURCE</th>
            </tr>
          </thead>
          <tbody>
            {#each brainPatterns as p}
              <tr>
                <td style="max-width: 400px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">{p.question || p.sql?.slice(0, 60)}</td>
                <td style="text-align: center; font-size: 10px;">{p.tables_used || '—'}</td>
                <td style="text-align: center;">{p.uses || 1}</td>
                <td style="text-align: center;">
                  <span style="font-size: 7px; font-weight: 900; padding: 1px 5px; background: {p.source === 'training' ? 'var(--color-warning)' : p.source === 'sql_file' ? '#6366f1' : 'var(--color-primary)'}; color: white; text-transform: uppercase;">{p.source || 'user'}</span>
                </td>
              </tr>
            {/each}
          </tbody>
        </table>
      </div>
    {:else}
      <div style="font-size: 12px; color: var(--color-on-surface-dim); margin-bottom: 20px;">No query patterns yet. Train the agent or chat to auto-generate SQL patterns.</div>
    {/if}

    <!-- File-based saved queries -->
    {#if knowledgeFiles.filter(f => f.type === 'queries').length > 0}
      <div style="font-size: 13px; font-weight: 900; text-transform: uppercase; letter-spacing: 0.08em; margin-bottom: 8px;">SAVED SQL FILES</div>
      {#each knowledgeFiles.filter(f => f.type === 'queries') as f}
        {#await fetch(`/api/knowledge-file-content/${f.name}?project=${slug}&subdir=queries`, { headers: _h() }).then(r => r.json()) then data}
          {#if data.content}
            <div class="ink-border mb-3" style="background: var(--color-surface);">
              <div class="dark-title-bar" style="padding: 6px 12px; font-size: 10px;">{f.name}</div>
              <pre style="padding: 12px; font-size: 11px; font-family: 'Space Grotesk', monospace; overflow-x: auto; background: var(--color-on-surface); color: var(--color-primary-container); margin: 0; white-space: pre-wrap;">{data.content}</pre>
            </div>
          {/if}
        {/await}
      {/each}
    {/if}

    <!-- Query Plan Memory -->
    {#if queryPlans.length > 0}
      <div style="margin-top: 16px; font-size: 13px; font-weight: 900; text-transform: uppercase; letter-spacing: 0.08em; margin-bottom: 8px;">PROVEN JOIN STRATEGIES</div>
      <div style="overflow-x: auto;">
        <table class="data-table" style="font-size: 10px;">
          <thead><tr><th>TABLES</th><th>JOIN STRATEGY</th><th>FILTERS</th><th>STATUS</th></tr></thead>
          <tbody>
            {#each queryPlans as plan}
              <tr>
                <td><code>{plan.tables?.join(', ')}</code></td>
                <td style="max-width: 250px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">{plan.join_strategy || '—'}</td>
                <td style="max-width: 200px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">{plan.filters || '—'}</td>
                <td><span style="font-size: 8px; font-weight: 900; padding: 1px 6px; background: {plan.success ? 'var(--color-primary)' : 'var(--color-error)'}; color: white;">{plan.success ? 'OK' : 'FAIL'}</span></td>
              </tr>
            {/each}
          </tbody>
        </table>
      </div>
    {/if}

  <!-- ═══ LINEAGE ═══ -->
  {:else if activeTab === 'lineage'}
    <div class="flex items-center justify-between mb-4">
      <div>
        <div style="font-size: 18px; font-weight: 900; text-transform: uppercase;">Knowledge Graph</div>
        <div style="font-size: 10px; color: var(--color-on-surface-dim); text-transform: uppercase; letter-spacing: 0.08em; margin-top: 2px;">
          {detail?.tables?.length || 0} tables · {[...(lineage?.relationships || []), ...relationships].length} relationships · {brainMemories.length} memories · {rules.length} rules
        </div>
      </div>
    </div>

    <!-- Knowledge Graph Visualization (Interactive ECharts) -->
    {#if detail?.tables?.length}
      {@const allRels = [...(lineage?.relationships || []), ...relationships]}
      {@const graphTables = (detail.tables || []).map((t: any) => ({ ...t, inspectData: tableInspectCache[t.name] }))}
      <div style="margin-bottom: 20px;">
        <KnowledgeGraph
          tables={graphTables}
          relationships={allRels}
          memories={brainMemories}
          rules={rules}
          onNodeClick={(node) => { graphSelectedNode = node; }}
        />
      </div>

      <!-- Node Detail Panel (shows when clicking a node) -->
      {#if graphSelectedNode}
        <div class="ink-border" style="background: var(--color-surface-bright); padding: 14px; margin-bottom: 16px; position: relative;">
          <button onclick={() => graphSelectedNode = null} style="position: absolute; top: 8px; right: 12px; background: none; border: none; cursor: pointer; font-size: 14px; font-weight: 900; color: var(--color-on-surface);">✕</button>
          {#if graphSelectedNode.type === 'table'}
            <div style="font-size: 8px; font-weight: 900; text-transform: uppercase; letter-spacing: 0.1em; color: var(--color-primary); margin-bottom: 4px;">TABLE</div>
            <div style="font-size: 16px; font-weight: 900; text-transform: uppercase;">{graphSelectedNode.name}</div>
            <div style="font-size: 11px; color: var(--color-on-surface-dim); margin-top: 4px;">{graphSelectedNode.rows} rows · {graphSelectedNode.columns} columns</div>
            {#if tableMetaCache[graphSelectedNode.name]?.table_description}
              <div style="font-size: 11px; margin-top: 8px; line-height: 1.5;">{tableMetaCache[graphSelectedNode.name].table_description}</div>
            {/if}
            {#if tableInspectCache[graphSelectedNode.name]?.columns}
              <div style="font-size: 9px; font-weight: 900; text-transform: uppercase; margin-top: 10px; margin-bottom: 4px;">COLUMNS</div>
              <div style="display: flex; flex-wrap: wrap; gap: 4px;">
                {#each tableInspectCache[graphSelectedNode.name].columns as col}
                  <span style="font-size: 10px; padding: 2px 8px; background: var(--color-surface-dim); border: 1px solid var(--color-on-surface); font-family: var(--font-family-display);">{col.name} <span style="color: var(--color-on-surface-dim);">({col.type})</span></span>
                {/each}
              </div>
            {/if}
          {:else if graphSelectedNode.type === 'memory'}
            <div style="font-size: 8px; font-weight: 900; text-transform: uppercase; letter-spacing: 0.1em; color: #ff9d00; margin-bottom: 4px;">MEMORY</div>
            <div style="font-size: 13px; font-weight: 700;">{graphSelectedNode.fact}</div>
            <div style="font-size: 10px; color: var(--color-on-surface-dim); margin-top: 4px;">Scope: {graphSelectedNode.scope || 'project'} · Source: {graphSelectedNode.source || 'user'}</div>
          {:else if graphSelectedNode.type === 'rule'}
            <div style="font-size: 8px; font-weight: 900; text-transform: uppercase; letter-spacing: 0.1em; color: #00b4d8; margin-bottom: 4px;">RULE</div>
            <div style="font-size: 13px; font-weight: 700;">{graphSelectedNode.name}</div>
            <div style="font-size: 11px; color: var(--color-on-surface-dim); margin-top: 4px;">{graphSelectedNode.definition}</div>
          {:else if graphSelectedNode.type === 'column'}
            <div style="font-size: 8px; font-weight: 900; text-transform: uppercase; letter-spacing: 0.1em; color: #555; margin-bottom: 4px;">COLUMN</div>
            <div style="font-size: 13px; font-weight: 700;">{graphSelectedNode.table}.{graphSelectedNode.name}</div>
            <div style="font-size: 11px; color: var(--color-on-surface-dim); margin-top: 4px;">Type: {graphSelectedNode.type} · Nullable: {graphSelectedNode.nullable ? 'Yes' : 'No'}</div>
          {/if}
        </div>
      {/if}
    {/if}

    <!-- CLI Terminal Header -->
    {@const fkRels = lineage?.relationships || []}
    {@const aiRels = relationships}
    {@const allRelsLineage = [...fkRels, ...aiRels]}
    <div style="font-size: 13px; font-weight: 900; text-transform: uppercase; margin-bottom: 8px;">Relationships</div>
    <div class="cli-terminal" style="margin-bottom: 16px; padding: 10px 14px;">
      <div class="cli-line">
        <span class="cli-prompt">$</span>
        <span class="cli-command">dash lineage</span>
        <span class="cli-output">--discover</span>
      </div>
      <div class="cli-line">
        <span style="color: #555;">&gt;</span>
        <span class="cli-dim">{fkRels.length} FK relationships (SQL introspection)</span>
      </div>
      <div class="cli-line">
        <span style="color: #555;">&gt;</span>
        <span class="cli-dim">{aiRels.length} AI-discovered relationships</span>
      </div>
      <div class="cli-line">
        <span style="color: #555;">&gt;</span>
        <span class="cli-check">&#10003;</span>
        <span class="cli-command">{allRelsLineage.length} total connections</span>
      </div>
    </div>

    <!-- Discovered Relationships Table -->
    {#if allRelsLineage.length > 0}
      <div style="font-size: 11px; font-weight: 900; text-transform: uppercase; letter-spacing: 0.08em; margin-bottom: 8px;">DISCOVERED RELATIONSHIPS ({allRelsLineage.length})</div>
      <div class="ink-border" style="overflow-x: auto; margin-bottom: 16px;">
        <table style="width: 100%; border-collapse: collapse; font-size: 11px; font-family: var(--font-family-display);">
          <thead>
            <tr style="border-bottom: 2px solid var(--color-on-surface); text-transform: uppercase; font-size: 9px; font-weight: 900; letter-spacing: 0.1em;">
              <th style="text-align: left; padding: 8px 12px;">FROM</th>
              <th style="text-align: left; padding: 8px 12px;">TO</th>
              <th style="text-align: left; padding: 8px 12px;">TYPE</th>
              <th style="text-align: left; padding: 8px 12px;">CONFIDENCE</th>
              <th style="text-align: left; padding: 8px 12px;">SOURCE</th>
            </tr>
          </thead>
          <tbody>
            {#each fkRels as rel}
              <tr style="border-bottom: 1px solid var(--color-surface-dim);">
                <td style="padding: 6px 12px; font-weight: 700;">{rel.from_table}{rel.from_column ? '.' + rel.from_column : ''}</td>
                <td style="padding: 6px 12px; font-weight: 700;">{rel.to_table}{rel.to_column ? '.' + rel.to_column : ''}</td>
                <td style="padding: 6px 12px; color: var(--color-on-surface-dim);">FK</td>
                <td style="padding: 6px 12px; color: var(--color-on-surface-dim);">{rel.confidence ? Math.round((rel.confidence || 0) * 100) + '%' : '100%'}</td>
                <td style="padding: 6px 12px;"><span style="font-size: 9px; font-weight: 900; padding: 1px 6px; background: var(--color-surface-dim); border: 1px solid var(--color-on-surface);">SQL</span></td>
              </tr>
            {/each}
            {#each aiRels as rel}
              <tr style="border-bottom: 1px solid var(--color-surface-dim);">
                <td style="padding: 6px 12px; font-weight: 700;">{rel.table1 || rel.from_table}</td>
                <td style="padding: 6px 12px; font-weight: 700;">{rel.table2 || rel.to_table}</td>
                <td style="padding: 6px 12px; color: var(--color-on-surface-dim);">{rel.join_type || rel.relationship || 'topic'}</td>
                <td style="padding: 6px 12px; color: var(--color-on-surface-dim);">{rel.confidence ? rel.confidence + '%' : '—'}</td>
                <td style="padding: 6px 12px;"><span style="font-size: 9px; font-weight: 900; padding: 1px 6px; background: #00fc40; color: #000; border: 1px solid #000;">AI</span></td>
              </tr>
            {/each}
          </tbody>
        </table>
      </div>
    {/if}

  <!-- ═══ AGENTS ═══ -->
  {:else if activeTab === 'agents'}
    <!-- CLI Status -->
    <div class="cli-terminal" style="margin-bottom: 16px; padding: 10px 14px;">
      <div class="cli-line">
        <span class="cli-prompt">$</span>
        <span class="cli-command">dash agents</span>
        <span class="cli-output">--status --verbose</span>
      </div>
      <div class="cli-line" style="margin-top: 4px;">
        <span class="cli-info">TEAM</span>
        <span class="cli-dim" style="margin-left: 8px;">{project?.agent_name || 'Agent'} · TeamMode.coordinate</span>
      </div>
      <div class="cli-line">
        <span class="cli-info">MODEL</span>
        <span class="cli-dim" style="margin-left: 8px;">openai/gpt-5.4-mini via OpenRouter</span>
      </div>
      <div class="cli-line">
        <span class="cli-info">SCHEMA</span>
        <span class="cli-dim" style="margin-left: 8px;">{project?.schema_name || slug}</span>
      </div>
      <div style="border-top: 1px solid #333; margin: 6px 0;"></div>
      {#each agentsData?.agents || [{name:'Leader',role:'routes requests',status:'active'},{name:'Analyst',role:'SQL · reasoning',status:'active'},{name:'Engineer',role:'views · computed data',status:'active'},{name:'Researcher',role:'document RAG · vision',status:'active'}] as agent}
        <div class="cli-line">
          <span style="color: #555;">&gt;</span>
          {#if agent.status === 'active'}
            <span class="cli-check">&#10003;</span>
          {:else}
            <span style="color: #888;">○</span>
          {/if}
          <span class="cli-command">{agent.name}</span>
          <span class="cli-dim">{agent.role}</span>
          {#if agent.status === 'standby'}
            <span style="font-size: 8px; color: #888; margin-left: 4px;">(standby)</span>
          {/if}
        </div>
      {/each}
      <div style="border-top: 1px solid #333; margin: 6px 0;"></div>
      <div class="cli-line">
        <span class="cli-info">REASONING</span>
      </div>
      {#each agentsData?.reasoning || [{mode:'FAST',description:'direct SQL → answer (simple questions)'},{mode:'DEEP',description:'think() + analyze() → multi-step reasoning (complex questions)'}] as r}
      <div class="cli-line">
        <span style="color: #555;">&gt;</span>
        <span style="color: #00fc40;">{r.mode}</span>
        <span class="cli-dim">{r.description}</span>
      </div>
      {/each}
      <div class="cli-line">
        <span class="cli-prompt">$</span>
        <span class="cli-success">all agents online</span>
      </div>
    </div>

    <!-- Agent Brain — 9 Context Layers -->
    <div style="margin-bottom: 20px;">
      <div style="font-size: 11px; font-weight: 900; text-transform: uppercase; letter-spacing: 0.08em; margin-bottom: 10px;">AGENT BRAIN — 9 CONTEXT LAYERS</div>
      <div style="display: grid; grid-template-columns: repeat(3, 1fr); gap: 8px;">
        <div class="ink-border" style="padding: 8px 10px; background: var(--color-surface-bright); text-align: center;">
          <div style="font-size: 8px; font-weight: 900; text-transform: uppercase; color: var(--color-on-surface-dim);">Proven Patterns</div>
          <div style="font-size: 20px; font-weight: 900; color: var(--color-primary);">{brainPatterns.length}</div>
          <div style="font-size: 8px; color: var(--color-on-surface-dim);">dash_query_patterns</div>
        </div>
        <div class="ink-border" style="padding: 8px 10px; background: var(--color-surface-bright); text-align: center;">
          <div style="font-size: 8px; font-weight: 900; text-transform: uppercase; color: var(--color-on-surface-dim);">Approved Responses</div>
          <div style="font-size: 20px; font-weight: 900; color: var(--color-primary);">{brainFeedback.filter(f => f.rating === 'up').length}</div>
          <div style="font-size: 8px; color: var(--color-on-surface-dim);">dash_feedback</div>
        </div>
        <div class="ink-border" style="padding: 8px 10px; background: var(--color-surface-bright); text-align: center;">
          <div style="font-size: 8px; font-weight: 900; text-transform: uppercase; color: var(--color-on-surface-dim);">Avoid Patterns</div>
          <div style="font-size: 20px; font-weight: 900; color: var(--color-primary);">{brainFeedback.filter(f => f.rating === 'down').length}</div>
          <div style="font-size: 8px; color: var(--color-on-surface-dim);">dash_feedback</div>
        </div>
        <div class="ink-border" style="padding: 8px 10px; background: var(--color-surface-bright); text-align: center;">
          <div style="font-size: 8px; font-weight: 900; text-transform: uppercase; color: var(--color-on-surface-dim);">Memories</div>
          <div style="font-size: 20px; font-weight: 900; color: var(--color-primary);">{brainMemories.length}</div>
          <div style="font-size: 8px; color: var(--color-on-surface-dim);">dash_memories</div>
        </div>
        <div class="ink-border" style="padding: 8px 10px; background: var(--color-surface-bright); text-align: center;">
          <div style="font-size: 8px; font-weight: 900; text-transform: uppercase; color: var(--color-on-surface-dim);">Annotations</div>
          <div style="font-size: 20px; font-weight: 900; color: var(--color-primary);">{detail?.knowledge_vectors || 0}</div>
          <div style="font-size: 8px; color: var(--color-on-surface-dim);">dash_annotations</div>
        </div>
        <div class="ink-border" style="padding: 8px 10px; background: var(--color-surface-bright); text-align: center;">
          <div style="font-size: 8px; font-weight: 900; text-transform: uppercase; color: var(--color-on-surface-dim);">Join Strategies</div>
          <div style="font-size: 20px; font-weight: 900; color: var(--color-primary);">{queryPlans.length}</div>
          <div style="font-size: 8px; color: var(--color-on-surface-dim);">dash_query_plans</div>
        </div>
        <div class="ink-border" style="padding: 8px 10px; background: var(--color-surface-bright); text-align: center;">
          <div style="font-size: 8px; font-weight: 900; text-transform: uppercase; color: var(--color-on-surface-dim);">User Preferences</div>
          <div style="font-size: 20px; font-weight: 900; color: var(--color-primary);">{Object.keys(userPreferences).length > 0 ? 'Active' : 'Inactive'}</div>
          <div style="font-size: 8px; color: var(--color-on-surface-dim);">dash_user_preferences</div>
        </div>
        <div class="ink-border" style="padding: 8px 10px; background: var(--color-surface-bright); text-align: center;">
          <div style="font-size: 8px; font-weight: 900; text-transform: uppercase; color: var(--color-on-surface-dim);">Self-Correction</div>
          <div style="font-size: 20px; font-weight: 900; color: var(--color-primary);">{metaLearnings.length}</div>
          <div style="font-size: 8px; color: var(--color-on-surface-dim);">dash_meta_learnings</div>
        </div>
        <div class="ink-border" style="padding: 8px 10px; background: var(--color-surface-bright); text-align: center;">
          <div style="font-size: 8px; font-weight: 900; text-transform: uppercase; color: var(--color-on-surface-dim);">Evolved Instructions</div>
          <div style="font-size: 20px; font-weight: 900; color: var(--color-primary);">{evolvedInstructions.current ? 'v' + evolvedInstructions.current.version : 'None'}</div>
          <div style="font-size: 8px; color: var(--color-on-surface-dim);">dash_evolved_instructions</div>
        </div>
      </div>
    </div>

    <div style="font-size: 18px; font-weight: 900; text-transform: uppercase; margin-bottom: 16px;">Agent Team</div>

    <!-- Team hierarchy -->
    <div style="display: flex; flex-direction: column; gap: 12px;">

      <!-- Leader -->
      <div class="ink-border" style="background: var(--color-on-surface); color: var(--color-surface); padding: 16px;">
        <div class="flex items-center justify-between">
          <div class="flex items-center gap-3">
            <span style="font-size: 20px;">🧠</span>
            <div>
              <div style="font-size: 14px; font-weight: 900; text-transform: uppercase;">LEADER</div>
              <div style="font-size: 10px; opacity: 0.7;">{project?.agent_name || 'Agent'}</div>
            </div>
          </div>
          <span style="font-size: 9px; padding: 2px 8px; border: 1px solid var(--color-primary-container); color: var(--color-primary-container);">COORDINATOR</span>
        </div>
        <div style="font-size: 11px; opacity: 0.8; margin-top: 8px;">Routes requests to the right specialist. Synthesizes final answers. Decides between Fast and Deep reasoning modes.</div>
        <div style="font-size: 10px; opacity: 0.5; margin-top: 6px;">DB: NONE · Tools: delegate_to_analyst, delegate_to_engineer</div>
      </div>

      <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 12px;">
        <!-- Analyst -->
        <div class="ink-border" style="background: var(--color-surface-bright); padding: 16px;">
          <div class="flex items-center gap-3 mb-2">
            <span style="font-size: 20px;">🔍</span>
            <div>
              <div style="font-size: 14px; font-weight: 900; text-transform: uppercase;">ANALYST</div>
              <div style="font-size: 10px; color: var(--color-on-surface-dim);">Data Specialist</div>
            </div>
          </div>
          <div style="font-size: 11px; color: var(--color-on-surface-dim); margin-bottom: 8px;">SQL queries, data analysis, insights, schema introspection. Searches knowledge base before executing.</div>
          <div style="font-size: 10px; font-weight: 700; margin-bottom: 4px; color: var(--color-primary);">DB: READ-ONLY</div>
          <div style="font-size: 9px; color: var(--color-on-surface-dim);">
            <strong>Tools:</strong> run_sql_query · introspect_schema · save_query · search_knowledge · think · analyze
          </div>
          <div style="font-size: 9px; color: var(--color-on-surface-dim); margin-top: 4px;">
            <strong>Features:</strong> learnings · knowledge search · chat history (5 runs)
          </div>
        </div>

        <!-- Engineer -->
        <div class="ink-border" style="background: var(--color-surface-bright); padding: 16px;">
          <div class="flex items-center gap-3 mb-2">
            <span style="font-size: 20px;">🏗</span>
            <div>
              <div style="font-size: 14px; font-weight: 900; text-transform: uppercase;">ENGINEER</div>
              <div style="font-size: 10px; color: var(--color-on-surface-dim);">Data Builder</div>
            </div>
          </div>
          <div style="font-size: 11px; color: var(--color-on-surface-dim); margin-bottom: 8px;">Creates views, summary tables, computed data. Updates knowledge when schema changes.</div>
          <div style="font-size: 10px; font-weight: 700; margin-bottom: 4px; color: var(--color-warning);">DB: WRITE (project schema)</div>
          <div style="font-size: 9px; color: var(--color-on-surface-dim);">
            <strong>Tools:</strong> run_sql_query · introspect_schema · update_knowledge · search_knowledge · think · analyze
          </div>
          <div style="font-size: 9px; color: var(--color-on-surface-dim); margin-top: 4px;">
            <strong>Features:</strong> learnings · knowledge search · chat history (5 runs)
          </div>
        </div>
      </div>
    </div>

    <!-- Reasoning Modes -->
    <div style="margin-top: 20px; font-size: 14px; font-weight: 900; text-transform: uppercase; margin-bottom: 12px;">Reasoning Modes</div>
    <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 12px;">
      <div class="ink-border" style="background: var(--color-surface-bright); padding: 14px;">
        <div class="flex items-center gap-2 mb-2">
          <span class="mode-badge mode-badge-fast">FAST</span>
          <span style="font-size: 12px; font-weight: 900;">Quick Analysis</span>
        </div>
        <div style="font-size: 11px; color: var(--color-on-surface-dim);">
          Direct SQL → answer. Used for simple lookups, counts, and straightforward queries. Auto-selected by the Leader when the question is simple.
        </div>
      </div>
      <div class="ink-border" style="background: var(--color-surface-bright); padding: 14px;">
        <div class="flex items-center gap-2 mb-2">
          <span class="mode-badge mode-badge-deep">DEEP</span>
          <span style="font-size: 12px; font-weight: 900;">Deep Reasoning</span>
        </div>
        <div style="font-size: 11px; color: var(--color-on-surface-dim);">
          Uses think() + analyze() for multi-step reasoning. Auto-selected for "why", "compare", "explain", "recommend" questions. Multiple SQL queries + synthesis.
        </div>
      </div>
    </div>

    <!-- Self-Evolution: Evolved Instructions -->
    <div style="margin-top: 20px; font-size: 11px; font-weight: 900; text-transform: uppercase; letter-spacing: 0.08em; margin-bottom: 8px;">EVOLVED INSTRUCTIONS (auto-learned)</div>
    {#if evolvedInstructions.current}
      <div class="ink-border" style="padding: 12px 14px; background: var(--color-surface-bright); margin-bottom: 8px;">
        <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 8px;">
          <span style="font-size: 9px; font-weight: 900; padding: 2px 8px; background: var(--color-primary); color: white;">v{evolvedInstructions.current.version}</span>
          <span style="font-size: 10px; color: var(--color-on-surface-dim);">{evolvedInstructions.current.created_at?.slice(0, 16)}</span>
        </div>
        <details>
          <summary style="font-size: 10px; font-weight: 700; cursor: pointer; text-transform: uppercase;">VIEW INSTRUCTIONS</summary>
          <pre style="font-size: 10px; white-space: pre-wrap; margin-top: 8px; padding: 10px; background: var(--color-surface-dim); font-family: var(--font-family-display);">{evolvedInstructions.current.instructions}</pre>
        </details>
        {#if evolvedInstructions.current.reasoning}
          <div style="font-size: 10px; color: var(--color-on-surface-dim); margin-top: 6px;"><strong>Why:</strong> {evolvedInstructions.current.reasoning}</div>
        {/if}
      </div>
      {#if evolvedInstructions.history?.length > 1}
        <details style="margin-bottom: 12px;">
          <summary style="font-size: 10px; font-weight: 700; cursor: pointer; text-transform: uppercase;">VERSION HISTORY ({evolvedInstructions.history.length})</summary>
          {#each evolvedInstructions.history as ver}
            <div style="display: flex; align-items: center; gap: 8px; padding: 6px 0; border-bottom: 1px solid var(--color-surface-dim);">
              <span style="font-size: 9px; font-weight: 900; padding: 1px 6px; background: var(--color-on-surface); color: var(--color-surface);">v{ver.version}</span>
              <span style="font-size: 10px; flex: 1;">{ver.reasoning || 'No reasoning'}</span>
              <span style="font-size: 9px; color: var(--color-on-surface-dim);">{ver.created_at?.slice(0, 16)}</span>
              <button class="feedback-btn" style="font-size: 8px; padding: 2px 6px;" onclick={async () => { await fetch(`/api/projects/${slug}/evolved-instructions/${ver.id}/revert`, { method: 'POST', headers: _h() }); loadEvolvedInstructions(); }}>REVERT</button>
            </div>
          {/each}
        </details>
      {/if}
    {:else}
      <div style="font-size: 11px; color: var(--color-on-surface-dim); margin-bottom: 12px;">No evolved instructions yet. They auto-generate after 20+ chats, or click EVOLVE NOW.</div>
    {/if}
    <button class="send-btn" style="font-size: 10px; padding: 6px 14px; margin-bottom: 16px;" onclick={async () => {
      cLog(`${ts()} ── evolving instructions...`);
      const r = await fetch(`/api/projects/${slug}/evolve-instructions`, { method: 'POST', headers: _h() });
      const d = await r.json();
      if (d.status === 'ok') { cLog(`${ts()} │  ✓ instructions evolved to v${d.version}`); loadEvolvedInstructions(); }
      else cLog(`${ts()} │  ✗ ${d.detail || 'failed'}`);
    }}>EVOLVE NOW</button>

    <!-- Self-Evolution: Resource Registry -->
    <div style="font-size: 11px; font-weight: 900; text-transform: uppercase; letter-spacing: 0.08em; margin-bottom: 8px;">RESOURCE REGISTRY</div>
    <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 10px;">
      <span style="font-size: 24px; font-weight: 900; color: {registryOverall >= 70 ? 'var(--color-primary)' : registryOverall >= 40 ? 'var(--color-warning)' : 'var(--color-error)'};">{registryOverall}</span>
      <span style="font-size: 10px; text-transform: uppercase; color: var(--color-on-surface-dim);">/ 100 overall health</span>
      <button class="feedback-btn" style="font-size: 8px; padding: 2px 8px; margin-left: auto;" onclick={async () => { await fetch(`/api/projects/${slug}/resource-registry/refresh`, { method: 'POST', headers: _h() }); loadResourceRegistry(); }}>REFRESH</button>
    </div>
    <div style="display: grid; grid-template-columns: repeat(auto-fill, minmax(140px, 1fr)); gap: 8px; margin-bottom: 16px;">
      {#each resourceRegistry as res}
        <div class="ink-border" style="padding: 8px 10px; background: var(--color-surface-bright); text-align: center;">
          <div style="font-size: 8px; font-weight: 900; text-transform: uppercase; color: var(--color-on-surface-dim); letter-spacing: 0.06em;">{res.type}</div>
          <div style="font-size: 18px; font-weight: 900; color: var(--color-on-surface);">{res.count}</div>
          <div style="height: 4px; background: var(--color-surface-dim); margin-top: 4px;"><div style="height: 100%; background: {res.health >= 70 ? 'var(--color-primary)' : res.health >= 40 ? 'var(--color-warning)' : 'var(--color-error)'}; width: {res.health}%;"></div></div>
          <div style="font-size: 8px; margin-top: 2px; color: {res.health >= 70 ? 'var(--color-primary)' : res.health >= 40 ? 'var(--color-warning)' : 'var(--color-error)'};">{res.health}%</div>
        </div>
      {/each}
    </div>

    <!-- Self-Evolution: Evolution Cycle -->
    <div style="font-size: 11px; font-weight: 900; text-transform: uppercase; letter-spacing: 0.08em; margin-bottom: 8px;">EVOLUTION CYCLE (Autogenesis)</div>
    <div class="flex gap-2 mb-3">
      <button class="send-btn" disabled={evolving} style="font-size: 10px; padding: 6px 14px;" onclick={async () => {
        evolving = true;
        cLog(`${ts()} ── running evolution cycle (Reflect → Select → Improve → Evaluate → Commit)...`);
        try {
          const r = await fetch(`/api/projects/${slug}/evolve`, { method: 'POST', headers: _h() });
          const d = await r.json();
          if (d.results) {
            if (d.results.reflect) cLog(`${ts()} │  ✓ reflect: ${d.results.reflect.slice(0, 80)}`);
            if (d.results.select) cLog(`${ts()} │  ✓ select: ${d.results.select.slice(0, 80)}`);
            if (d.results.improve) cLog(`${ts()} │  ✓ improve: ${d.results.improve.slice(0, 80)}`);
            if (d.results.evaluate) cLog(`${ts()} │  ✓ evaluate: ${d.results.evaluate.slice(0, 80)}`);
            if (d.results.commit) cLog(`${ts()} │  ✓ commit: ${d.results.commit.slice(0, 80)}`);
          }
          if (d.status === 'ok') { cLog(`${ts()} ── ✓ evolution complete. Health: ${d.overall_health}/100`); loadResourceRegistry(); loadEvolvedInstructions(); loadEvolutionHistory(); loadConsolidationStatus(); }
          else cLog(`${ts()} │  ✗ ${d.detail || 'evolution failed'}`);
        } catch {} finally { evolving = false; }
      }}>{evolving ? 'EVOLVING...' : 'RUN EVOLUTION CYCLE'}</button>
    </div>
    {#if evolutionHistory.length > 0}
      <div style="font-size: 10px; font-weight: 700; text-transform: uppercase; margin-bottom: 6px;">PAST RUNS</div>
      {#each evolutionHistory as run}
        <div class="ink-border" style="padding: 8px 12px; margin-bottom: 4px; background: var(--color-surface-bright); display: flex; align-items: center; gap: 8px; font-size: 10px;">
          <span style="font-weight: 900; padding: 1px 6px; background: {run.status === 'completed' ? 'var(--color-primary)' : run.status === 'failed' ? 'var(--color-error)' : 'var(--color-warning)'}; color: white; font-size: 8px; text-transform: uppercase;">{run.status}</span>
          <span style="flex: 1;">{run.reflect?.slice(0, 60) || '...'}</span>
          <span style="color: var(--color-on-surface-dim);">{run.started_at?.slice(0, 16)}</span>
        </div>
      {/each}
    {/if}

  <!-- ═══ WORKFLOWS ═══ -->
  {:else if activeTab === 'workflows'}
    <div class="cli-terminal" style="margin-bottom: 16px; padding: 8px 14px;">
      <div class="cli-line">
        <span class="cli-prompt">$</span>
        <span class="cli-command">dash workflows</span>
        <span class="cli-output">--list</span>
        <span class="cli-dim" style="margin-left: auto;">{workflows.length} workflows</span>
      </div>
    </div>
    <div class="flex items-center justify-between mb-4">
      <div style="font-size: 18px; font-weight: 900; text-transform: uppercase;">Workflows</div>
      <div>
        <input type="file" accept=".pptx,.pdf,.docx" onchange={async (e) => {
          const file = (e.target as HTMLInputElement).files?.[0];
          if (!file) return;
          // 1. Upload the doc
          const fd = new FormData(); fd.append('file', file);
          cLog(`${ts()} ── uploading ${file.name}...`);
          try {
            const upRes = await fetch(`/api/upload-doc?project=${slug}`, { method: 'POST', body: fd, headers: _h() });
            if (!upRes.ok) { cLog(`${ts()} │  ✗ upload failed`); return; }
            cLog(`${ts()} │  ✓ uploaded`);
            // 2. Extract workflow from doc
            cLog(`${ts()} ── extracting workflow structure...`);
            const wfRes = await fetch(`/api/projects/${slug}/doc-to-workflow`, {
              method: 'POST', headers: { ..._h(), 'Content-Type': 'application/json' },
              body: JSON.stringify({ filename: file.name })
            });
            if (wfRes.ok) {
              const data = await wfRes.json();
              docWorkflowPreview = data.workflow;
              cLog(`${ts()} │  ✓ found ${data.workflow?.steps?.length || 0} steps`);
            } else {
              cLog(`${ts()} │  ✗ extraction failed — try from DOCS tab`);
            }
          } catch { cLog(`${ts()} │  ✗ error`); }
          (e.target as HTMLInputElement).value = '';
        }} style="display: none;" id="wf-import-input" />
        <button class="send-btn" onclick={() => (document.getElementById('wf-import-input') as HTMLInputElement)?.click()} style="padding: 6px 14px; font-size: 10px; cursor: pointer;">↑ IMPORT ANALYSIS</button>
      </div>
    </div>
    <div style="font-size: 10px; color: var(--color-on-surface-dim); margin-bottom: 12px;">Upload a past PPTX/PDF/DOCX report to auto-create a reusable workflow from its structure.</div>
    {#if workflows.length > 0}
      {#each workflows as wf, wi}
        <div class="ink-border mb-2" style="background: var(--color-surface); padding: 12px 16px;">
          <div class="flex items-center justify-between">
            <div class="flex items-center gap-2">
              <span style="font-weight: 900; text-transform: uppercase; font-size: 12px;">{wf.name}</span>
              {#if wf.source === 'document'}
                <span style="font-size: 7px; font-weight: 900; padding: 1px 5px; background: var(--color-warning); color: white; text-transform: uppercase;">FROM DOC</span>
              {:else if wf.source === 'mined'}
                <span style="font-size: 7px; font-weight: 900; padding: 1px 5px; background: #6366f1; color: white; text-transform: uppercase;">DISCOVERED</span>
              {:else if wf.source === 'user'}
                <span style="font-size: 7px; font-weight: 900; padding: 1px 5px; background: var(--color-primary); color: white; text-transform: uppercase;">USER</span>
              {:else}
                <span style="font-size: 7px; font-weight: 900; padding: 1px 5px; background: var(--color-on-surface-dim); color: white; text-transform: uppercase;">AUTO</span>
              {/if}
            </div>
            <button class="send-btn" style="font-size: 9px; padding: 3px 10px;" onclick={async () => {
              window.dispatchEvent(new CustomEvent('dash-cli-log', { detail: { text: `  ${new Date().toLocaleTimeString('en-US', {hour:'2-digit',minute:'2-digit',second:'2-digit',hour12:false})} ── running workflow: ${wf.name}` } }));
              try {
                const res = await fetch(`/api/projects/${slug}/workflows-db/${wf.id}/run`, { method: 'POST', headers: _h() });
                if (res.ok) {
                  const d = await res.json();
                  for (const r of d.results || []) {
                    window.dispatchEvent(new CustomEvent('dash-cli-log', { detail: { text: `  ${new Date().toLocaleTimeString('en-US', {hour:'2-digit',minute:'2-digit',second:'2-digit',hour12:false})} │  ✓ step ${r.step}: ${r.prompt?.slice(0, 60)}` } }));
                  }
                }
              } catch {}
            }}>RUN</button>
          </div>
          <div style="font-size: 11px; color: var(--color-on-surface-dim); margin-top: 4px;">{wf.description}</div>
          {#if wf.steps?.length}
            <div style="margin-top: 6px;">
              {#each (Array.isArray(wf.steps) ? wf.steps : []) as step, si}
                <div style="font-size: 10px; color: var(--color-on-surface-dim); padding-left: 8px;">
                  {si + 1}. {typeof step === 'string' ? step : step.description || step}
                </div>
              {/each}
            </div>
          {/if}
        </div>
      {/each}
    {:else}<div style="font-size: 12px; color: var(--color-on-surface-dim);">No workflows yet. Click TRAIN ALL to auto-generate sample workflows.</div>{/if}

    <!-- Discover Patterns -->
    <div style="margin-top: 16px;">
      <button class="send-btn" disabled={mining} style="font-size: 10px; padding: 6px 14px;" onclick={async () => {
        mining = true;
        cLog(`${ts()} ── mining conversation patterns...`);
        try {
          const r = await fetch(`/api/projects/${slug}/mine-patterns`, { method: 'POST', headers: _h() });
          const d = await r.json();
          if (d.status === 'ok') { cLog(`${ts()} │  ✓ discovered ${d.workflows_created} new workflows`); loadWorkflows(); }
          else cLog(`${ts()} │  · ${d.detail || 'no patterns found'}`);
        } catch {} finally { mining = false; }
      }}>{mining ? 'MINING...' : 'DISCOVER PATTERNS'}</button>
      <span style="font-size: 10px; color: var(--color-on-surface-dim); margin-left: 8px;">Analyze past conversations to find recurring analysis workflows</span>
    </div>

  <!-- ═══ SCHEDULES ═══ -->
  {:else if activeTab === 'schedules'}
    <div class="cli-terminal" style="margin-bottom: 16px; padding: 8px 14px;">
      <div class="cli-line">
        <span class="cli-prompt">$</span>
        <span class="cli-command">dash schedules</span>
        <span class="cli-output">--list</span>
        <span class="cli-dim" style="margin-left: auto;">{schedules.length} schedules · {schedules.filter((s: any) => s.enabled).length} active</span>
      </div>
    </div>
    <div class="flex items-center justify-between mb-4">
      <div style="font-size: 18px; font-weight: 900; text-transform: uppercase;">Scheduled Reports</div>
      <button class="send-btn" style="font-size: 10px; padding: 6px 14px;" onclick={() => showAddSchedule = true}>+ ADD SCHEDULE</button>
    </div>
    <div style="font-size: 11px; color: var(--color-on-surface-dim); margin-bottom: 16px;">
      Set up recurring queries that run automatically. Results are saved and can be exported.
    </div>

    {#if showAddSchedule}
      <div class="ink-border stamp-shadow" style="background: var(--color-surface-bright); padding: 16px; margin-bottom: 16px;">
        <div style="font-size: 11px; font-weight: 900; text-transform: uppercase; margin-bottom: 10px;">NEW SCHEDULE</div>
        <div style="margin-bottom: 8px;">
          <div style="font-size: 9px; font-weight: 700; text-transform: uppercase; margin-bottom: 3px;">NAME</div>
          <input type="text" bind:value={newSchedName} placeholder="Weekly Revenue Report" style="width: 100%; border: 2px solid var(--color-on-surface); padding: 6px 10px; font-family: var(--font-family-display); font-size: 12px; background: var(--color-surface);" />
        </div>
        <div style="margin-bottom: 8px;">
          <div style="font-size: 9px; font-weight: 700; text-transform: uppercase; margin-bottom: 3px;">PROMPT</div>
          <textarea bind:value={newSchedPrompt} placeholder="What is our MRR this month? Show trends and breakdown by plan." rows="3" style="width: 100%; border: 2px solid var(--color-on-surface); padding: 6px 10px; font-family: var(--font-family-display); font-size: 12px; background: var(--color-surface); resize: vertical;"></textarea>
        </div>
        <div style="margin-bottom: 12px;">
          <div style="font-size: 9px; font-weight: 700; text-transform: uppercase; margin-bottom: 3px;">FREQUENCY</div>
          <select bind:value={newSchedCron} style="border: 2px solid var(--color-on-surface); padding: 6px 10px; font-family: var(--font-family-display); font-size: 12px; background: var(--color-surface);">
            <option value="daily">Daily (8am)</option>
            <option value="weekly">Weekly (Monday 8am)</option>
            <option value="monthly">Monthly (1st, 8am)</option>
          </select>
        </div>
        <div class="flex gap-2">
          <button class="send-btn" style="font-size: 10px; padding: 6px 14px;" onclick={addSchedule} disabled={schedSaving || !newSchedPrompt}>
            {schedSaving ? 'SAVING...' : 'CREATE'}
          </button>
          <button class="feedback-btn" style="font-size: 10px; padding: 6px 14px;" onclick={() => showAddSchedule = false}>CANCEL</button>
        </div>
      </div>
    {/if}

    {#if schedules.length > 0}
      <div style="display: flex; flex-direction: column; gap: 8px;">
        {#each schedules as sched}
          <div class="ink-border" style="background: var(--color-surface-bright); padding: 12px 16px;">
            <div class="flex items-center justify-between">
              <div>
                <span style="font-size: 13px; font-weight: 900;">{sched.name}</span>
                <span class="tag-label" style="font-size: 8px; margin-left: 8px;">{sched.cron}</span>
                {#if !sched.enabled}
                  <span class="tag-label" style="font-size: 8px; margin-left: 4px; background: var(--color-error);">PAUSED</span>
                {/if}
              </div>
              <div class="flex gap-2">
                <button class="feedback-btn" style="font-size: 9px; padding: 3px 8px;" onclick={() => runScheduleNow(sched.id)} disabled={runningSchedule === sched.id}>
                  {runningSchedule === sched.id ? 'RUNNING...' : 'RUN NOW'}
                </button>
                <button class="feedback-btn" style="font-size: 9px; padding: 3px 8px;" onclick={() => toggleSchedule(sched.id, sched.enabled)}>
                  {sched.enabled ? 'PAUSE' : 'ENABLE'}
                </button>
                <button class="feedback-btn" style="font-size: 9px; padding: 3px 8px; color: var(--color-error);" onclick={() => deleteSchedule(sched.id)}>
                  DELETE
                </button>
              </div>
            </div>
            <div style="font-size: 12px; color: var(--color-on-surface-dim); margin-top: 6px;">{sched.prompt}</div>
            {#if sched.last_run_at}
              <div style="font-size: 9px; color: var(--color-on-surface-dim); margin-top: 6px; text-transform: uppercase;">
                Last run: {sched.last_run_at}
              </div>
            {/if}
          </div>
        {/each}
      </div>
    {:else}
      <div style="text-align: center; padding: 40px 20px; color: var(--color-on-surface-dim); font-size: 12px;">
        No schedules yet. Create one to automate recurring reports.
      </div>
    {/if}

  <!-- ═══ EVALS ═══ -->
  {:else if activeTab === 'evals'}
    <div class="cli-terminal" style="margin-bottom: 16px; padding: 8px 14px;">
      <div class="cli-line">
        <span class="cli-prompt">$</span>
        <span class="cli-command">dash evals</span>
        <span class="cli-output">--status</span>
        <span class="cli-dim" style="margin-left: auto;">{brainEvals.length} test cases · {brainEvals.filter((e: any) => e.last_score === 'PASS').length} passing</span>
      </div>
    </div>

    <div class="flex items-center justify-between mb-4">
      <div style="font-size: 18px; font-weight: 900; text-transform: uppercase;">Eval Test Suite</div>
      <button class="send-btn" style="font-size: 10px; padding: 6px 14px; {evalsRunning ? 'opacity: 0.5;' : ''}" disabled={evalsRunning} onclick={async () => {
        evalsRunning = true;
        try { await fetch(`/api/projects/${slug}/evals/run`, { method: 'POST', headers: _h() }); await loadBrainData(); } catch {}
        evalsRunning = false;
      }}>{evalsRunning ? 'RUNNING...' : 'RUN ALL'}</button>
    </div>

    <div style="font-size: 11px; color: var(--color-on-surface-dim); margin-bottom: 16px;">
      Golden Q&A test cases. Add expected questions + SQL, run to verify agent accuracy.
    </div>

    <!-- Add eval form -->
    <div class="ink-border" style="background: var(--color-surface-bright); padding: 12px 16px; margin-bottom: 16px;">
      <div style="font-size: 10px; font-weight: 900; text-transform: uppercase; margin-bottom: 8px;">ADD TEST CASE</div>
      <div style="margin-bottom: 6px;">
        <input type="text" bind:value={newEvalQ} placeholder="Question: e.g., What is the total revenue?" style="width: 100%; border: 2px solid var(--color-on-surface); padding: 6px 10px; font-family: var(--font-family-display); font-size: 11px; background: var(--color-surface);" />
      </div>
      <div style="margin-bottom: 8px;">
        <textarea bind:value={newEvalSQL} placeholder="Expected SQL: e.g., SELECT SUM(revenue) FROM orders" rows="2" style="width: 100%; border: 2px solid var(--color-on-surface); padding: 6px 10px; font-family: var(--font-family-display); font-size: 11px; background: var(--color-surface); resize: vertical;"></textarea>
      </div>
      <button class="feedback-btn" style="font-size: 9px; font-weight: 700; padding: 4px 12px;" onclick={async () => {
        if (!newEvalQ || !newEvalSQL) return;
        await fetch(`/api/projects/${slug}/evals`, { method: 'POST', headers: { ..._h(), 'Content-Type': 'application/json' }, body: JSON.stringify({ question: newEvalQ, expected_sql: newEvalSQL }) });
        newEvalQ = ''; newEvalSQL = ''; await loadBrainData();
      }}>ADD</button>
    </div>

    <!-- Eval list -->
    {#if brainEvals.length > 0}
      <div style="display: flex; flex-direction: column; gap: 6px;">
        {#each brainEvals as ev}
          <div class="ink-border" style="background: var(--color-surface-bright); padding: 10px 14px; border-left: 3px solid {ev.last_score === 'PASS' ? 'var(--color-primary)' : ev.last_score === 'ERROR' ? 'var(--color-error)' : 'var(--color-on-surface-dim)'};">
            <div class="flex items-center justify-between">
              <div style="font-size: 11px; font-weight: 900;">Q: {ev.question}</div>
              <div class="flex items-center gap-2">
                {#if ev.last_score}
                  <span class="tag-label" style="font-size: 8px; background: {ev.last_score === 'PASS' ? 'var(--color-primary)' : 'var(--color-error)'}; color: white;">{ev.last_score}</span>
                {:else}
                  <span class="tag-label" style="font-size: 8px;">NOT RUN</span>
                {/if}
                <button class="feedback-btn" style="font-size: 8px; padding: 2px 6px; color: var(--color-error);" onclick={async () => {
                  await fetch(`/api/projects/${slug}/evals/${ev.id}`, { method: 'DELETE', headers: _h() }); await loadBrainData();
                }}>DEL</button>
              </div>
            </div>
            <div class="cli-terminal" style="margin-top: 4px; padding: 6px 10px; font-size: 10px;">
              <code style="color: #e0e0e0;">{ev.expected_sql}</code>
            </div>
            {#if ev.last_run_at}
              <div style="font-size: 9px; color: var(--color-on-surface-dim); margin-top: 4px;">Last run: {ev.last_run_at?.slice(0, 19)}</div>
            {/if}
          </div>
        {/each}
      </div>
    {:else}
      <div style="text-align: center; padding: 30px; color: var(--color-on-surface-dim); font-size: 12px;">
        No test cases yet. Add golden Q&A pairs to verify agent accuracy.
      </div>
    {/if}

    <!-- Self-Evaluation + Trend Chart -->
    <div style="margin-top: 20px; font-size: 11px; font-weight: 900; text-transform: uppercase; letter-spacing: 0.08em; margin-bottom: 8px;">EVALUATION HISTORY</div>
    <div class="flex gap-2 mb-3">
      <button class="send-btn" disabled={selfEvaluating} style="font-size: 10px; padding: 6px 14px;" onclick={async () => {
        selfEvaluating = true;
        cLog(`${ts()} ── running self-evaluation...`);
        try {
          const r = await fetch(`/api/projects/${slug}/self-evaluate`, { method: 'POST', headers: _h() });
          const d = await r.json();
          if (d.regression_report) { evalRegression = d.regression_report; cLog(`${ts()} │  regression report generated`); }
          if (d.eval_result) { cLog(`${ts()} │  ✓ ${d.eval_result.passed}/${d.eval_result.total} passed`); loadBrainData(); loadEvalHistory(); }
          cLog(`${ts()} ── ✓ self-evaluation complete`);
        } catch {} finally { selfEvaluating = false; }
      }}>{selfEvaluating ? 'EVALUATING...' : 'SELF-EVALUATE'}</button>
    </div>
    {#if evalHistory.length > 0}
      <div class="ink-border" style="padding: 10px; background: var(--color-surface-bright); margin-bottom: 12px;">
        <div style="height: 180px;">
          <EChartView headers={["Run", "Passed", "Failed"]} rows={evalHistory.slice().reverse().map(r => [r.run_at?.slice(5, 16) || '', String(r.passed), String(r.failed)])} chartType="line" />
        </div>
      </div>
    {/if}
    {#if evalRegression}
      <div class="ink-border" style="padding: 10px 14px; background: var(--color-surface-bright); margin-bottom: 12px;">
        <div style="font-size: 9px; font-weight: 900; text-transform: uppercase; color: var(--color-on-surface-dim); margin-bottom: 4px;">REGRESSION REPORT</div>
        <div style="font-size: 11px; white-space: pre-wrap;">{evalRegression}</div>
      </div>
    {/if}

  <!-- ═══ USERS ═══ -->
  {:else if activeTab === 'users'}
    <div class="cli-terminal" style="margin-bottom: 16px; padding: 8px 14px;">
      <div class="cli-line">
        <span class="cli-prompt">$</span>
        <span class="cli-command">dash users</span>
        <span class="cli-output">--project {slug}</span>
        <span class="cli-dim" style="margin-left: auto;">{sharedUsers.length} shared</span>
      </div>
      {#each sharedUsers as u}
        <div class="cli-line">
          <span style="color: #555;">&gt;</span>
          <span class="cli-check">&#10003;</span>
          <span class="cli-command">{u.username}</span>
          <span class="cli-dim">shared by {u.shared_by}</span>
        </div>
      {/each}
    </div>

    <div class="flex items-center justify-between mb-4">
      <div style="font-size: 18px; font-weight: 900; text-transform: uppercase;">Shared Users</div>
    </div>
    <div style="font-size: 11px; color: var(--color-on-surface-dim); margin-bottom: 16px;">
      Share this project with other users on the platform. They'll see it in their "Shared with me" tab.
    </div>

    <!-- Add user form -->
    <div class="flex gap-2 items-end mb-4">
      <div style="flex: 1;">
        <div style="font-size: 9px; font-weight: 700; text-transform: uppercase; margin-bottom: 3px;">USERNAME</div>
        <input type="text" bind:value={shareUsername} placeholder="Enter username..." style="width: 100%; border: 2px solid var(--color-on-surface); padding: 6px 10px; font-family: var(--font-family-display); font-size: 12px; background: var(--color-surface);" />
      </div>
      <div>
        <div style="font-size: 9px; font-weight: 700; text-transform: uppercase; margin-bottom: 3px;">ROLE</div>
        <select bind:value={shareRole} style="border: 2px solid var(--color-on-surface); padding: 6px 10px; font-family: var(--font-family-display); font-size: 12px; background: var(--color-surface);">
          <option value="viewer">VIEWER</option>
          <option value="editor">EDITOR</option>
          <option value="admin">ADMIN</option>
        </select>
      </div>
      <button class="send-btn" style="font-size: 10px; padding: 6px 14px;" onclick={async () => { await shareProject(); await loadSharedUsers(); }}>+ ADD USER</button>
    </div>
    {#if shareError}
      <div style="font-size: 11px; font-weight: 700; margin-bottom: 12px; color: {shareError === 'Shared!' ? 'var(--color-primary)' : 'var(--color-error)'};">{shareError}</div>
    {/if}

    <!-- User list -->
    {#if sharedUsers.length > 0}
      <div style="display: flex; flex-direction: column; gap: 8px;">
        {#each sharedUsers as u}
          <div class="ink-border" style="background: var(--color-surface-bright); padding: 12px 16px;">
            <div class="flex items-center justify-between">
              <div class="flex items-center gap-3">
                <div style="background: var(--color-primary-container); color: var(--color-on-surface); width: 32px; height: 32px; display: flex; align-items: center; justify-content: center; font-weight: 900; font-size: 14px; border: 2px solid var(--color-on-surface);">
                  {u.username.charAt(0).toUpperCase()}
                </div>
                <div>
                  <div style="font-size: 13px; font-weight: 900;">{u.username}</div>
                  <div style="font-size: 9px; color: var(--color-on-surface-dim); text-transform: uppercase;">
                    Shared by {u.shared_by} &middot; {u.created_at?.slice(0, 10) || ''}
                  </div>
                </div>
              </div>
              <div class="flex items-center gap-2">
                <select value={u.role || 'viewer'} onchange={async (e) => {
                  const newRole = (e.target as HTMLSelectElement).value;
                  await fetch(`/api/projects/${slug}/share?username=${encodeURIComponent(u.username)}&role=${newRole}`, { method: 'POST', headers: _h() });
                  await loadSharedUsers();
                }} style="border: 2px solid var(--color-on-surface); padding: 2px 6px; font-family: var(--font-family-display); font-size: 9px; font-weight: 700; text-transform: uppercase; background: var(--color-surface);">
                  <option value="viewer">VIEWER</option>
                  <option value="editor">EDITOR</option>
                  <option value="admin">ADMIN</option>
                </select>
                <button class="feedback-btn" style="font-size: 9px; padding: 3px 10px; color: var(--color-error); border-color: var(--color-error);" onclick={() => unshareUser(u.username)}>REMOVE</button>
              </div>
            </div>
          </div>
        {/each}
      </div>
    {:else}
      <div style="text-align: center; padding: 30px; color: var(--color-on-surface-dim); font-size: 12px;">
        No users shared yet. Add a username above to share this project.
      </div>
    {/if}

  <!-- ═══ CONFIG ═══ -->
  {:else if activeTab === 'config'}
    <!-- Persona CLI -->
    {#if persona}
      <div class="cli-terminal" style="margin-bottom: 16px; padding: 10px 14px;">
        <div class="cli-line">
          <span class="cli-prompt">$</span>
          <span class="cli-command">dash persona</span>
          <span class="cli-output">--project {slug}</span>
          <span class="cli-success" style="margin-left: auto;">&#10003; trained</span>
        </div>
        <div class="cli-line" style="margin-top: 4px;">
          <span class="cli-info">IDENTITY</span>
        </div>
        <div class="cli-line">
          <span style="color: #555;">&gt;</span>
          <textarea bind:value={editPersonaText} rows="3" style="background: transparent; border: 1px solid #333; color: #e0e0e0; font-family: 'Space Grotesk', monospace; font-size: 11px; width: 100%; padding: 4px 6px; resize: vertical;">{persona.persona_prompt}</textarea>
          <button onclick={async () => {
            try {
              const p = { ...persona, persona_prompt: editPersonaText };
              await fetch(`/api/projects/${slug}/persona`, { method: 'PUT', headers: { ..._h(), 'Content-Type': 'application/json' }, body: JSON.stringify(p) });
            } catch {}
          }} style="background: #00fc40; color: #1a1a1a; border: none; padding: 2px 8px; font-family: 'Space Grotesk', monospace; font-size: 9px; font-weight: 900; cursor: pointer; margin-top: 4px;">SAVE PERSONA</button>
        </div>
        {#if persona.domain_terms?.length}
          <div class="cli-line" style="margin-top: 4px;">
            <span class="cli-info">DOMAIN</span>
            <span class="cli-dim" style="margin-left: 8px;">{persona.domain_terms.join(' · ')}</span>
          </div>
        {/if}
        {#if persona.expertise_areas?.length}
          <div class="cli-line">
            <span class="cli-info">EXPERTISE</span>
            <span class="cli-dim" style="margin-left: 8px;">{persona.expertise_areas.join(' · ')}</span>
          </div>
        {/if}
        {#if persona.communication_style}
          <div class="cli-line">
            <span class="cli-info">STYLE</span>
            <span class="cli-dim" style="margin-left: 8px;">{persona.communication_style}</span>
          </div>
        {/if}
        {#if persona.greeting}
          <div class="cli-line">
            <span class="cli-info">GREETING</span>
            <span class="cli-dim" style="margin-left: 8px;">"{persona.greeting}"</span>
          </div>
        {/if}
      </div>
    {:else}
      <div class="cli-terminal" style="margin-bottom: 16px; padding: 10px 14px;">
        <div class="cli-line">
          <span class="cli-prompt">$</span>
          <span class="cli-command">dash persona</span>
          <span class="cli-output">--project {slug}</span>
          <span style="color: var(--color-warning); margin-left: auto;">no persona trained — click RETRAIN in TRAINING tab</span>
        </div>
      </div>
    {/if}

    <div style="font-size: 18px; font-weight: 900; text-transform: uppercase; margin-bottom: 16px;">Configuration</div>
    {#if project}
      <div style="display: flex; flex-direction: column; gap: 12px; max-width: 500px;">
        <div>
          <div style="font-size: 9px; font-weight: 700; text-transform: uppercase; margin-bottom: 3px;">PROJECT NAME</div>
          <div class="ink-border" style="padding: 8px 12px; font-size: 12px; background: var(--color-surface-dim);">{project.name}</div>
        </div>
        <div>
          <div style="font-size: 9px; font-weight: 700; text-transform: uppercase; margin-bottom: 3px;">AGENT NAME</div>
          <input type="text" bind:value={editName} style="width: 100%; border: 2px solid var(--color-on-surface); padding: 8px 12px; font-family: var(--font-family-display); font-size: 12px; background: var(--color-surface);" />
        </div>
        <div>
          <div style="font-size: 9px; font-weight: 700; text-transform: uppercase; margin-bottom: 3px;">ROLE / EXPERTISE</div>
          <input type="text" bind:value={editRole} placeholder="Revenue, pipeline, forecasting..." style="width: 100%; border: 2px solid var(--color-on-surface); padding: 8px 12px; font-family: var(--font-family-display); font-size: 12px; background: var(--color-surface);" />
        </div>
        <div>
          <div style="font-size: 9px; font-weight: 700; text-transform: uppercase; margin-bottom: 3px;">PERSONALITY</div>
          <div class="flex gap-2">
            {#each [['friendly', 'Friendly'], ['formal', 'Formal'], ['technical', 'Technical']] as [val, label]}
              <button onclick={() => editPersonality = val} style="flex: 1; padding: 6px; font-size: 10px; font-weight: 700; text-transform: uppercase; border: 2px solid var(--color-on-surface); background: {editPersonality === val ? 'var(--color-on-surface)' : 'var(--color-surface)'}; color: {editPersonality === val ? 'var(--color-surface)' : 'var(--color-on-surface)'}; cursor: pointer; font-family: var(--font-family-display);">{label}</button>
            {/each}
          </div>
        </div>
        <div>
          <div style="font-size: 9px; font-weight: 700; text-transform: uppercase; margin-bottom: 3px;">SCHEMA</div>
          <div class="ink-border" style="padding: 8px 12px; font-size: 12px; background: var(--color-surface-dim); font-family: var(--font-family-display);">{project.schema_name}</div>
        </div>
        <div>
          <div style="font-size: 9px; font-weight: 700; text-transform: uppercase; margin-bottom: 3px;">CREATED</div>
          <div class="ink-border" style="padding: 8px 12px; font-size: 12px; background: var(--color-surface-dim);">{project.created_at?.slice(0, 19)}</div>
        </div>
        <button class="send-btn" style="padding: 10px; font-size: 11px; justify-content: center; display: flex; max-width: 200px;" onclick={async () => {
          const params = new URLSearchParams();
          if (editName) params.set('agent_name', editName);
          params.set('agent_role', editRole);
          if (editPersonality) params.set('agent_personality', editPersonality);
          try {
            await fetch(`/api/projects/${slug}?${params}`, { method: 'PUT', headers: _h() });
            await loadDetail();
          } catch {}
        }}>SAVE CHANGES</button>
      </div>

      <!-- Cross-Project Transfer -->
      <div style="margin-top: 30px; font-size: 11px; font-weight: 900; text-transform: uppercase; letter-spacing: 0.08em; margin-bottom: 8px;">IMPORT LEARNINGS FROM ANOTHER PROJECT</div>
      {#if transferCandidates.length > 0}
        <div style="display: flex; flex-direction: column; gap: 6px; margin-bottom: 12px;">
          {#each transferCandidates as tc}
            <div class="ink-border" style="padding: 10px 14px; background: var(--color-surface-bright); display: flex; align-items: center; gap: 10px;">
              <div style="flex: 1;">
                <div style="font-size: 12px; font-weight: 900;">{tc.name}</div>
                <div style="font-size: 9px; color: var(--color-on-surface-dim);">{tc.overlap_pct}% column overlap &middot; {tc.memories} memories &middot; {tc.patterns} patterns</div>
              </div>
              <button class="feedback-btn" style="font-size: 9px; padding: 3px 10px; font-weight: 700;" onclick={async () => {
                try {
                  const r = await fetch(`/api/projects/${slug}/preview-import?source=${tc.slug}`, { headers: _h() });
                  if (r.ok) importPreview = { ...(await r.json()), slug: tc.slug, name: tc.name };
                } catch {}
              }}>PREVIEW</button>
              <button class="send-btn" style="font-size: 9px; padding: 3px 10px;" onclick={async () => {
                const r = await fetch(`/api/projects/${slug}/import-learnings`, {
                  method: 'POST', headers: { ..._h(), 'Content-Type': 'application/json' },
                  body: JSON.stringify({ from_slug: tc.slug, types: ['memories', 'patterns', 'annotations'] })
                });
                const d = await r.json();
                if (d.status === 'ok') { alert(`Imported: ${d.imported.memories} memories, ${d.imported.patterns} patterns, ${d.imported.annotations} annotations`); loadBrainData(); }
              }}>IMPORT</button>
            </div>
          {/each}
        </div>
      {:else}
        <div style="font-size: 11px; color: var(--color-on-surface-dim);">No similar projects found. Create another project with overlapping data to enable transfer.</div>
      {/if}
      {#if importPreview}
        <div class="ink-border" style="padding: 12px 14px; background: var(--color-surface-bright); margin-bottom: 12px;">
          <div style="font-size: 10px; font-weight: 900; text-transform: uppercase; margin-bottom: 6px;">PREVIEW: {importPreview.name}</div>
          {#if importPreview.memories?.length}<div style="font-size: 10px; margin-bottom: 4px;"><strong>{importPreview.memories.length}</strong> memories</div>{/if}
          {#if importPreview.patterns?.length}<div style="font-size: 10px; margin-bottom: 4px;"><strong>{importPreview.patterns.length}</strong> query patterns</div>{/if}
          {#if importPreview.annotations?.length}<div style="font-size: 10px; margin-bottom: 4px;"><strong>{importPreview.annotations.length}</strong> annotations</div>{/if}
        </div>
      {/if}
    {/if}
  {/if}

  </div>
  </div>
{/if}
</div>
</div>

<!-- Old upload modal removed — now inline in DATASETS tab -->

<!-- Doc Upload Modal -->
{#if showDocUpload}
<!-- svelte-ignore a11y_no_static_element_interactions -->
<div style="position: fixed; inset: 0; background: rgba(56,56,50,0.7); z-index: 100; display: flex; align-items: center; justify-content: center; padding: 20px;" onclick={(e) => { if (e.target === e.currentTarget) showDocUpload = false; }}>
  <div class="ink-border stamp-shadow" style="background: var(--color-surface); width: 100%; max-width: 450px;">
    <div class="dark-title-bar flex items-center justify-between" style="padding: 8px 14px; font-size: 11px;"><span>ADD DOCUMENT</span><button onclick={() => showDocUpload = false} style="background: none; border: none; color: var(--color-surface); cursor: pointer; font-weight: 900;">✕</button></div>
    <div style="padding: 16px;">
      <!-- svelte-ignore a11y_no_static_element_interactions -->
      <div class="drop-zone" style="padding: 16px; cursor: pointer;" onclick={() => docFileInput?.click()} ondragover={(e) => e.preventDefault()} ondrop={(e) => { e.preventDefault(); const f = e.dataTransfer?.files?.[0]; if (f) docFile = f; }}>
        <input type="file" accept=".sql,.py,.txt,.md,.pptx,.docx,.pdf" onchange={(e) => { const f = (e.target as HTMLInputElement).files?.[0]; if (f) docFile = f; }} bind:this={docFileInput} style="display: none;" />
        {#if docFile}<span style="font-weight: 900;">{docFile.name}</span>{:else}<span style="font-size: 11px; text-transform: uppercase;">Drop .sql, .py, .txt, or .md</span>{/if}
      </div>
      {#if docFile}
        <button class="send-btn mt-2" onclick={uploadDoc} disabled={docUploading} style="padding: 6px 14px; font-size: 10px; cursor: pointer;">{docUploading ? '...' : '▶ INDEX'}</button>
      {/if}
      {#if docResult}<div style="margin-top: 8px; font-size: 11px; color: var(--color-primary); font-weight: 700;">✓ Indexed: {docResult.filename}</div>{/if}
    </div>
  </div>
</div>
{/if}

<!-- Inspect Modal -->
{#if showInspect && inspectTable}
<!-- svelte-ignore a11y_no_static_element_interactions -->
<div style="position: fixed; inset: 0; background: rgba(56,56,50,0.7); z-index: 100; display: flex; align-items: center; justify-content: center; padding: 20px;" onclick={(e) => { if (e.target === e.currentTarget) showInspect = false; }}>
  <div class="ink-border stamp-shadow" style="background: var(--color-surface); width: 100%; max-width: 600px; max-height: 90vh; overflow-y: auto;">
    <div class="dark-title-bar flex items-center justify-between" style="padding: 8px 14px; font-size: 11px;"><span>{inspectTable.name?.toUpperCase()}</span><button onclick={() => showInspect = false} style="background: none; border: none; color: var(--color-surface); cursor: pointer; font-weight: 900;">✕</button></div>
    <div style="padding: 16px; font-size: 12px;">
      <div style="margin-bottom: 8px;"><strong>{inspectTable.rows?.toLocaleString()}</strong> rows · <strong>{inspectTable.columns}</strong> columns</div>
      {#if inspectData?.columns?.length}
        <table style="width: 100%; font-size: 11px; border-collapse: collapse;">
          <thead><tr style="border-bottom: 2px solid var(--color-on-surface);"><th style="text-align: left; padding: 4px 8px;">Column</th><th style="text-align: left; padding: 4px 8px;">Type</th><th style="text-align: left; padding: 4px 8px;">Null</th></tr></thead>
          <tbody>{#each inspectData.columns as col}<tr style="border-bottom: 1px solid var(--color-surface-dim);"><td style="padding: 3px 8px; font-weight: 700;">{col.name}</td><td style="padding: 3px 8px;">{col.type}</td><td style="padding: 3px 8px;">{col.nullable ? 'Yes' : 'No'}</td></tr>{/each}</tbody>
        </table>
      {/if}
    </div>
  </div>
</div>
{/if}

<style>
  .train-spinner {
    display: inline-block;
    animation: train-spin 1s linear infinite;
    color: var(--color-on-surface);
  }
  @keyframes train-spin {
    0% { opacity: 1; }
    50% { opacity: 0.3; }
    100% { opacity: 1; }
  }
</style>
