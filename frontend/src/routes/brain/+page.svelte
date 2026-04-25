<script lang="ts">
  import { onMount, onDestroy } from 'svelte';

  /* ─── state ─── */
  let activeTab = $state('glossary');
  let entries = $state<any[]>([]);
  let stats = $state<any>({});
  let accessLog = $state<any[]>([]);
  let graphData = $state<any>({ nodes: [], edges: [] });
  let loading = $state(false);

  /* ─── scope filter ─── */
  let scopeFilter = $state('all'); // 'all' | 'global' | 'personal' | project slug
  let userProjects = $state<any[]>([]); // [{slug, name, agent_name}]

  /* ─── add form state ─── */
  let showAdd = $state(false);
  let addCategory = $state('glossary');
  let addName = $state('');
  let addDefinition = $state('');
  let addMetadata = $state('{}');
  let addError = $state('');
  let saving = $state(false);
  let newEntryScope = $state('global');

  /* ─── alias builder (for alias tab form) ─── */
  let aliasInput = $state('');

  /* ─── threshold builder (for threshold tab form) ─── */
  let threshTarget = $state('');
  let threshAlertBelow = $state('');
  let threshAlertAbove = $state('');

  /* ─── formula builder ─── */
  let formulaExpr = $state('');
  let formulaUnit = $state('');

  /* ─── edit state ─── */
  let editId = $state<number | null>(null);

  /* ─── echart ─── */
  let graphContainer: HTMLDivElement | undefined = $state();
  let chartInstance: any = null;

  /* ─── auth helper ─── */
  function _h(): Record<string, string> {
    const t = typeof localStorage !== 'undefined' ? localStorage.getItem('dash_token') : null;
    return t ? { Authorization: `Bearer ${t}` } : {};
  }

  /* ─── tabs ─── */
  const tabs = [
    { id: 'glossary', label: 'GLOSSARY' },
    { id: 'formulas', label: 'FORMULAS' },
    { id: 'aliases', label: 'ALIASES' },
    { id: 'patterns', label: 'PATTERNS' },
    { id: 'org', label: 'ORG MAP' },
    { id: 'thresholds', label: 'RULES' },
    { id: 'graph', label: 'GRAPH' },
    { id: 'log', label: 'LOG' },
  ];

  /* ─── category map (tab id → API category) ─── */
  const tabCategoryMap: Record<string, string> = {
    glossary: 'glossary',
    formulas: 'formula',
    aliases: 'alias',
    patterns: 'pattern',
    org: 'org',
    thresholds: 'threshold',
  };

  /* ─── tab switch ─── */
  let tabLoaded = $state<Record<string, boolean>>({});

  async function switchTab(id: string) {
    activeTab = id;
    if (tabLoaded[id]) return;
    tabLoaded[id] = true;
    loading = true;
    try {
      if (id === 'graph') await loadGraph();
      else if (id === 'log') await loadLog();
      else await loadEntries();
    } catch {}
    loading = false;
  }

  /* ═══════════════════════════════════════════════════════════ */
  /*  DATA LOADERS                                              */
  /* ═══════════════════════════════════════════════════════════ */

  async function loadEntries() {
    try {
      let url = '/api/brain/entries';
      if (activeTab !== 'log') {
        if (scopeFilter !== 'all') {
          if (scopeFilter === 'global') url += '?scope=global';
          else if (scopeFilter === 'personal') url += '?scope=personal';
          else url += `?project_slug=${scopeFilter}`;
        }
        const selectedCategory = tabCategoryMap[activeTab];
        if (selectedCategory) {
          url += (url.includes('?') ? '&' : '?') + `category=${selectedCategory}`;
        }
      }
      const res = await fetch(url, { headers: _h() });
      if (res.ok) { const d = await res.json(); entries = d.entries || d || []; }
    } catch {}
  }

  async function loadStats() {
    try {
      const res = await fetch('/api/brain/stats', { headers: _h() });
      if (res.ok) { stats = await res.json(); }
    } catch {}
  }

  async function loadLog() {
    try {
      const res = await fetch('/api/brain/log', { headers: _h() });
      if (res.ok) { const d = await res.json(); accessLog = d.log || d.entries || d || []; }
    } catch {}
  }

  async function loadGraph() {
    try {
      const res = await fetch('/api/brain/graph', { headers: _h() });
      if (res.ok) { graphData = await res.json(); }
    } catch {}
  }

  async function loadProjects() {
    try {
      const res = await fetch('/api/user-projects-brief', { headers: _h() });
      if (res.ok) {
        const d = await res.json();
        const all = d.projects || [];
        // Only show projects that have brain entries
        try {
          const br = await fetch('/api/brain', { headers: _h() });
          if (br.ok) {
            const bd = await br.json();
            const slugs = new Set((bd.entries || []).filter((e: any) => e.project_slug).map((e: any) => e.project_slug));
            userProjects = slugs.size > 0 ? all.filter((p: any) => slugs.has(p.slug)) : [];
          } else { userProjects = []; }
        } catch { userProjects = []; }
      }
    } catch {}
  }

  /* ═══════════════════════════════════════════════════════════ */
  /*  CRUD                                                      */
  /* ═══════════════════════════════════════════════════════════ */

  function resetForm() {
    addName = '';
    addDefinition = '';
    addMetadata = '{}';
    addError = '';
    aliasInput = '';
    threshTarget = '';
    threshAlertBelow = '';
    threshAlertAbove = '';
    formulaExpr = '';
    formulaUnit = '';
    newEntryScope = 'global';
    editId = null;
    showAdd = false;
  }

  function openAdd() {
    resetForm();
    addCategory = tabCategoryMap[activeTab] || 'glossary';
    showAdd = true;
  }

  function openEdit(entry: any) {
    editId = entry.id;
    addCategory = entry.category || 'glossary';
    addName = entry.name || '';
    addDefinition = entry.definition || '';
    const meta = entry.metadata || {};
    addMetadata = JSON.stringify(meta, null, 2);
    // Populate specialized fields
    if (entry.category === 'alias') {
      aliasInput = '';
    }
    if (entry.category === 'threshold') {
      threshTarget = meta.target ?? '';
      threshAlertBelow = meta.alert_below ?? '';
      threshAlertAbove = meta.alert_above ?? '';
    }
    if (entry.category === 'formula') {
      formulaExpr = meta.formula ?? '';
      formulaUnit = meta.unit ?? '';
    }
    showAdd = true;
  }

  function buildMetadata(): any {
    try {
      let meta = JSON.parse(addMetadata);
      if (addCategory === 'threshold') {
        meta.target = threshTarget ? parseFloat(threshTarget) : undefined;
        meta.alert_below = threshAlertBelow ? parseFloat(threshAlertBelow) : undefined;
        meta.alert_above = threshAlertAbove ? parseFloat(threshAlertAbove) : undefined;
      }
      if (addCategory === 'formula') {
        if (formulaExpr) meta.formula = formulaExpr;
        if (formulaUnit) meta.unit = formulaUnit;
      }
      return meta;
    } catch {
      return {};
    }
  }

  async function addEntry() {
    if (!addName.trim()) { addError = 'Name is required'; return; }
    saving = true;
    addError = '';
    try {
      const body: any = {
        category: addCategory,
        name: addName.trim(),
        definition: addDefinition.trim(),
        metadata: buildMetadata(),
      };
      if (newEntryScope === 'personal') {
        body.scope = 'personal';
      } else if (newEntryScope !== 'global') {
        body.project_slug = newEntryScope;
      }
      const res = await fetch('/api/brain/entries', {
        method: 'POST',
        headers: { ..._h(), 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      });
      if (res.ok) {
        resetForm();
        tabLoaded = {};
        await loadEntries();
        await loadStats();
      } else {
        const d = await res.json();
        addError = d.detail || d.message || 'Failed to save entry';
      }
    } catch (e: any) {
      addError = e.message || 'Network error';
    }
    saving = false;
  }

  async function updateEntry(id: number) {
    if (!addName.trim()) { addError = 'Name is required'; return; }
    saving = true;
    addError = '';
    try {
      const body = {
        category: addCategory,
        name: addName.trim(),
        definition: addDefinition.trim(),
        metadata: buildMetadata(),
      };
      const res = await fetch(`/api/brain/entries/${id}`, {
        method: 'PUT',
        headers: { ..._h(), 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      });
      if (res.ok) {
        resetForm();
        tabLoaded = {};
        await loadEntries();
        await loadStats();
      } else {
        const d = await res.json();
        addError = d.detail || d.message || 'Failed to update entry';
      }
    } catch (e: any) {
      addError = e.message || 'Network error';
    }
    saving = false;
  }

  async function deleteEntry(id: number, name: string) {
    if (!confirm(`Delete "${name}" from the Company Brain?`)) return;
    try {
      await fetch(`/api/brain/entries/${id}`, { method: 'DELETE', headers: _h() });
      tabLoaded = {};
      await loadEntries();
      await loadStats();
    } catch {}
  }

  /* ─── alias helpers ─── */
  function getAliases(entry: any): string[] {
    return entry.metadata?.aliases || [];
  }

  function addAliasTag() {
    if (!aliasInput.trim()) return;
    try {
      let meta = JSON.parse(addMetadata);
      if (!meta.aliases) meta.aliases = [];
      if (!meta.aliases.includes(aliasInput.trim())) {
        meta.aliases.push(aliasInput.trim());
      }
      addMetadata = JSON.stringify(meta, null, 2);
      aliasInput = '';
    } catch {}
  }

  function removeAliasTag(alias: string) {
    try {
      let meta = JSON.parse(addMetadata);
      meta.aliases = (meta.aliases || []).filter((a: string) => a !== alias);
      addMetadata = JSON.stringify(meta, null, 2);
    } catch {}
  }

  function getFormAliases(): string[] {
    try { return JSON.parse(addMetadata).aliases || []; } catch { return []; }
  }

  /* ─── filtered entries ─── */
  function filtered(category: string): any[] {
    return entries.filter((e: any) => e.category === category);
  }

  /* ─── helpers ─── */
  function fmtDate(d: string | null | undefined): string {
    if (!d) return '-';
    try { return new Date(d).toLocaleString('en-US', { month: 'short', day: 'numeric', year: 'numeric', hour: '2-digit', minute: '2-digit' }); }
    catch { return String(d).slice(0, 19); }
  }

  function categoryColor(cat: string): string {
    const map: Record<string, string> = {
      glossary: '#00fc40',
      formula: '#0078d4',
      alias: '#ff9d00',
      pattern: '#9b59b6',
      org: '#e74c3c',
      threshold: '#e67e22',
    };
    return map[cat] || '#888';
  }

  /* ═══════════════════════════════════════════════════════════ */
  /*  GRAPH (ECharts)                                           */
  /* ═══════════════════════════════════════════════════════════ */

  async function renderGraph() {
    if (!graphContainer) return;
    const echarts = await import('echarts');
    if (chartInstance) chartInstance.dispose();
    chartInstance = echarts.init(graphContainer, 'dark');
    chartInstance.setOption({
      backgroundColor: '#1a1a1a',
      tooltip: { trigger: 'item', formatter: (p: any) => p.data?.name || '' },
      series: [{
        type: 'graph',
        layout: 'force',
        data: (graphData.nodes || []).map((n: any) => ({
          name: n.name,
          id: String(n.id),
          symbolSize: n.type === 'org' ? 40 : n.type === 'formula' ? 30 : 20,
          itemStyle: {
            color: n.type === 'metric' ? '#00fc40' : n.type === 'formula' ? '#0078d4' :
                   n.type === 'entity' ? '#ff9d00' : n.type === 'org' ? '#9b59b6' : '#e74c3c',
            borderColor: '#444',
            borderWidth: 1.5,
          },
          label: { show: true, fontSize: 9, color: '#ddd' },
        })),
        links: (graphData.edges || []).map((e: any) => ({
          source: String(e.source),
          target: String(e.target),
          lineStyle: { color: '#555', width: 1.5 },
          label: { show: true, formatter: e.relation || '', fontSize: 7, color: '#666' },
        })),
        roam: true,
        draggable: true,
        force: { repulsion: 300, gravity: 0.1, edgeLength: [80, 200] },
      }],
    });
  }

  /* ─── lifecycle ─── */
  onMount(async () => {
    // Super admin check
    try {
      const res = await fetch('/api/auth/check', { headers: _h() });
      if (res.ok) {
        const me = await res.json();
        if (!me.is_super) {
          window.location.href = '/ui/home';
          return;
        }
      } else {
        window.location.href = '/ui/home';
        return;
      }
    } catch {
      window.location.href = '/ui/home';
      return;
    }
    loadProjects();
    await loadStats();
    await switchTab('glossary');
  });

  onDestroy(() => {
    if (chartInstance) { chartInstance.dispose(); chartInstance = null; }
  });

  // Re-render graph when tab switches to graph and data is loaded
  $effect(() => {
    if (activeTab === 'graph' && graphData.nodes?.length > 0) {
      // Small delay to ensure DOM is mounted
      setTimeout(() => {
        if (graphContainer) renderGraph();
      }, 100);
    }
  });
</script>

<div style="padding: 16px; overflow-y: auto; height: 100%;">
<div style="width: 100%; display: flex; flex-direction: column; flex: 1; min-height: 0;">

<!-- ═══ HEADER ═══ -->
<div class="cli-terminal" style="margin-bottom: 16px; padding: 10px 14px;">
  <div class="cli-line">
    <span class="cli-prompt">$</span>
    <span class="cli-command">dash brain --status</span>
  </div>
  <div class="cli-line">
    <span style="color: #555;">&gt;</span>
    <span class="cli-check">&#10003;</span>
    <span class="cli-output">concepts: {stats.glossary_count ?? filtered('glossary').length}</span>
    <span style="margin-left: 16px; color: #555;">|</span>
    <span class="cli-output" style="margin-left: 8px;">formulas: {stats.formula_count ?? filtered('formula').length}</span>
    <span style="margin-left: 16px; color: #555;">|</span>
    <span class="cli-output" style="margin-left: 8px;">aliases: {stats.alias_count ?? filtered('alias').length}</span>
    <span style="margin-left: 16px; color: #555;">|</span>
    <span class="cli-output" style="margin-left: 8px;">patterns: {stats.pattern_count ?? filtered('pattern').length}</span>
    <span style="margin-left: 16px; color: #555;">|</span>
    <span class="cli-output" style="margin-left: 8px;">access: {stats.access_count ?? accessLog.length}</span>
  </div>
</div>

<div style="font-size: 18px; font-weight: 900; text-transform: uppercase; margin-bottom: 12px; font-family: var(--font-family-display);">Company Brain</div>

<!-- ═══ SCOPE FILTER ═══ -->
<div style="display: flex; gap: 4px; margin-bottom: 12px; flex-wrap: wrap; align-items: center;">
  <span style="font-size: 9px; font-weight: 900; text-transform: uppercase; letter-spacing: 0.1em; color: var(--color-on-surface-dim); margin-right: 8px;">SCOPE</span>
  <button
    style="font-size: 9px; font-weight: 700; padding: 3px 10px; cursor: pointer; text-transform: uppercase; font-family: var(--font-family-display); border: 2px solid {scopeFilter === 'all' ? 'var(--color-on-surface)' : 'var(--color-on-surface-dim)'}; background: {scopeFilter === 'all' ? 'var(--color-on-surface)' : 'transparent'}; color: {scopeFilter === 'all' ? 'var(--color-surface)' : 'var(--color-on-surface-dim)'};"
    onclick={() => { scopeFilter = 'all'; tabLoaded = {}; loadEntries(); }}
  >ALL</button>
  <button
    style="font-size: 9px; font-weight: 700; padding: 3px 10px; cursor: pointer; text-transform: uppercase; font-family: var(--font-family-display); border: 2px solid {scopeFilter === 'global' ? 'var(--color-on-surface)' : 'var(--color-on-surface-dim)'}; background: {scopeFilter === 'global' ? 'var(--color-on-surface)' : 'transparent'}; color: {scopeFilter === 'global' ? 'var(--color-surface)' : 'var(--color-on-surface-dim)'};"
    onclick={() => { scopeFilter = 'global'; tabLoaded = {}; loadEntries(); }}
  >🌐 GLOBAL</button>
  {#each userProjects as proj}
    <button
      style="font-size: 9px; font-weight: 700; padding: 3px 10px; cursor: pointer; text-transform: uppercase; font-family: var(--font-family-display); border: 2px solid {scopeFilter === proj.slug ? 'var(--color-on-surface)' : 'var(--color-on-surface-dim)'}; background: {scopeFilter === proj.slug ? 'var(--color-on-surface)' : 'transparent'}; color: {scopeFilter === proj.slug ? 'var(--color-surface)' : 'var(--color-on-surface-dim)'};"
      onclick={() => { scopeFilter = proj.slug; tabLoaded = {}; loadEntries(); }}
    >📊 {proj.agent_name || proj.name}</button>
  {/each}
  <button
    style="font-size: 9px; font-weight: 700; padding: 3px 10px; cursor: pointer; text-transform: uppercase; font-family: var(--font-family-display); border: 2px solid {scopeFilter === 'personal' ? 'var(--color-on-surface)' : 'var(--color-on-surface-dim)'}; background: {scopeFilter === 'personal' ? 'var(--color-on-surface)' : 'transparent'}; color: {scopeFilter === 'personal' ? 'var(--color-surface)' : 'var(--color-on-surface-dim)'};"
    onclick={() => { scopeFilter = 'personal'; tabLoaded = {}; loadEntries(); }}
  >👤 PERSONAL</button>
</div>

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
<!-- GLOSSARY TAB                                               -->
<!-- ═══════════════════════════════════════════════════════════ -->
{#if activeTab === 'glossary'}
  <div class="flex items-center justify-between mb-4">
    <div style="font-size: 9px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.08em; color: var(--color-on-surface-dim);">Business terms and definitions</div>
    <button class="send-btn" style="font-size: 10px; padding: 6px 14px;" onclick={openAdd}>+ ADD TERM</button>
  </div>
  {#if loading && filtered('glossary').length === 0}
    <div style="font-size: 12px; color: var(--color-on-surface-dim);">Loading...</div>
  {:else if filtered('glossary').length === 0}
    <div style="font-size: 12px; color: var(--color-on-surface-dim);">No glossary entries yet.</div>
  {:else}
    {#each filtered('glossary') as entry}
      <div class="ink-border" style="padding: 12px 14px; margin-bottom: 8px; background: var(--color-surface-bright);">
        <div class="flex items-center justify-between">
          <div class="flex items-center gap-2">
            <span style="font-weight: 900; font-size: 13px;">{entry.name}</span>
            <span style="font-size: 8px; font-weight: 700; padding: 1px 6px; background: {categoryColor(entry.category)}; color: #1a1a1a; text-transform: uppercase;">{entry.category}</span>
            {#if entry.scope === 'global'}
              <span style="font-size: 8px; font-weight: 900; padding: 1px 6px; background: #007518; color: white;">🌐 GLOBAL</span>
            {:else if entry.scope === 'personal'}
              <span style="font-size: 8px; font-weight: 900; padding: 1px 6px; background: #6366f1; color: white;">👤 PERSONAL</span>
            {:else if entry.project_slug}
              <span style="font-size: 8px; font-weight: 900; padding: 1px 6px; background: #d97706; color: white;">📊 {entry.project_slug}</span>
            {/if}
          </div>
          <div class="flex gap-1">
            <button class="feedback-btn" style="font-size: 9px; padding: 2px 6px; cursor: pointer;" onclick={() => openEdit(entry)}>&#9998;</button>
            <button class="feedback-btn" style="font-size: 9px; padding: 2px 6px; cursor: pointer; color: var(--color-error); border-color: var(--color-error);" onclick={() => deleteEntry(entry.id, entry.name)}>&#10005;</button>
          </div>
        </div>
        <div style="font-size: 11px; color: var(--color-on-surface-dim); margin-top: 4px; line-height: 1.5;">{entry.definition || '-'}</div>
      </div>
    {/each}
  {/if}

<!-- ═══════════════════════════════════════════════════════════ -->
<!-- FORMULAS TAB                                               -->
<!-- ═══════════════════════════════════════════════════════════ -->
{:else if activeTab === 'formulas'}
  <div class="flex items-center justify-between mb-4">
    <div style="font-size: 9px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.08em; color: var(--color-on-surface-dim);">Calculations and derived metrics</div>
    <button class="send-btn" style="font-size: 10px; padding: 6px 14px;" onclick={openAdd}>+ ADD FORMULA</button>
  </div>
  {#if loading && filtered('formula').length === 0}
    <div style="font-size: 12px; color: var(--color-on-surface-dim);">Loading...</div>
  {:else if filtered('formula').length === 0}
    <div style="font-size: 12px; color: var(--color-on-surface-dim);">No formulas defined yet.</div>
  {:else}
    {#each filtered('formula') as entry}
      <div class="ink-border" style="padding: 12px 14px; margin-bottom: 8px; background: var(--color-surface-bright);">
        <div class="flex items-center justify-between">
          <div class="flex items-center gap-2">
            <span style="font-weight: 900; font-size: 13px;">{entry.name}</span>
            <span style="font-size: 8px; font-weight: 700; padding: 1px 6px; background: {categoryColor(entry.category)}; color: #1a1a1a; text-transform: uppercase;">FORMULA</span>
            {#if entry.scope === 'global'}
              <span style="font-size: 8px; font-weight: 900; padding: 1px 6px; background: #007518; color: white;">🌐 GLOBAL</span>
            {:else if entry.scope === 'personal'}
              <span style="font-size: 8px; font-weight: 900; padding: 1px 6px; background: #6366f1; color: white;">👤 PERSONAL</span>
            {:else if entry.project_slug}
              <span style="font-size: 8px; font-weight: 900; padding: 1px 6px; background: #d97706; color: white;">📊 {entry.project_slug}</span>
            {/if}
            {#if entry.metadata?.unit}
              <span style="font-size: 9px; color: var(--color-on-surface-dim); font-style: italic;">({entry.metadata.unit})</span>
            {/if}
          </div>
          <div class="flex gap-1">
            <button class="feedback-btn" style="font-size: 9px; padding: 2px 6px; cursor: pointer;" onclick={() => openEdit(entry)}>&#9998;</button>
            <button class="feedback-btn" style="font-size: 9px; padding: 2px 6px; cursor: pointer; color: var(--color-error); border-color: var(--color-error);" onclick={() => deleteEntry(entry.id, entry.name)}>&#10005;</button>
          </div>
        </div>
        {#if entry.metadata?.formula}
          <div class="cli-terminal" style="margin-top: 6px; padding: 6px 10px; font-size: 10px;">
            <code style="color: #e0e0e0;">{entry.metadata.formula}</code>
          </div>
        {/if}
        <div style="font-size: 11px; color: var(--color-on-surface-dim); margin-top: 4px; line-height: 1.5;">{entry.definition || '-'}</div>
      </div>
    {/each}
  {/if}

<!-- ═══════════════════════════════════════════════════════════ -->
<!-- ALIASES TAB                                                -->
<!-- ═══════════════════════════════════════════════════════════ -->
{:else if activeTab === 'aliases'}
  <div class="flex items-center justify-between mb-4">
    <div style="font-size: 9px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.08em; color: var(--color-on-surface-dim);">Alternate names and abbreviations</div>
    <button class="send-btn" style="font-size: 10px; padding: 6px 14px;" onclick={openAdd}>+ ADD ALIAS</button>
  </div>
  {#if loading && filtered('alias').length === 0}
    <div style="font-size: 12px; color: var(--color-on-surface-dim);">Loading...</div>
  {:else if filtered('alias').length === 0}
    <div style="font-size: 12px; color: var(--color-on-surface-dim);">No aliases defined yet.</div>
  {:else}
    {#each filtered('alias') as entry}
      <div class="ink-border" style="padding: 12px 14px; margin-bottom: 8px; background: var(--color-surface-bright);">
        <div class="flex items-center justify-between">
          <div class="flex items-center gap-2">
            <span style="font-weight: 900; font-size: 13px;">{entry.name}</span>
            <span style="font-size: 8px; font-weight: 700; padding: 1px 6px; background: {categoryColor(entry.category)}; color: #1a1a1a; text-transform: uppercase;">ALIAS</span>
            {#if entry.scope === 'global'}
              <span style="font-size: 8px; font-weight: 900; padding: 1px 6px; background: #007518; color: white;">🌐 GLOBAL</span>
            {:else if entry.scope === 'personal'}
              <span style="font-size: 8px; font-weight: 900; padding: 1px 6px; background: #6366f1; color: white;">👤 PERSONAL</span>
            {:else if entry.project_slug}
              <span style="font-size: 8px; font-weight: 900; padding: 1px 6px; background: #d97706; color: white;">📊 {entry.project_slug}</span>
            {/if}
          </div>
          <div class="flex gap-1">
            <button class="feedback-btn" style="font-size: 9px; padding: 2px 6px; cursor: pointer;" onclick={() => openEdit(entry)}>&#9998;</button>
            <button class="feedback-btn" style="font-size: 9px; padding: 2px 6px; cursor: pointer; color: var(--color-error); border-color: var(--color-error);" onclick={() => deleteEntry(entry.id, entry.name)}>&#10005;</button>
          </div>
        </div>
        <div style="font-size: 11px; color: var(--color-on-surface-dim); margin-top: 4px;">{entry.definition || '-'}</div>
        {#if getAliases(entry).length > 0}
          <div style="display: flex; flex-wrap: wrap; gap: 4px; margin-top: 6px;">
            {#each getAliases(entry) as alias}
              <span style="font-size: 9px; font-weight: 700; padding: 2px 8px; background: #ff9d00; color: #1a1a1a; border-radius: 0;">{alias}</span>
            {/each}
          </div>
        {/if}
      </div>
    {/each}
  {/if}

<!-- ═══════════════════════════════════════════════════════════ -->
<!-- PATTERNS TAB                                               -->
<!-- ═══════════════════════════════════════════════════════════ -->
{:else if activeTab === 'patterns'}
  <div class="flex items-center justify-between mb-4">
    <div style="font-size: 9px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.08em; color: var(--color-on-surface-dim);">Recurring business patterns and conventions</div>
    <button class="send-btn" style="font-size: 10px; padding: 6px 14px;" onclick={openAdd}>+ ADD PATTERN</button>
  </div>
  {#if loading && filtered('pattern').length === 0}
    <div style="font-size: 12px; color: var(--color-on-surface-dim);">Loading...</div>
  {:else if filtered('pattern').length === 0}
    <div style="font-size: 12px; color: var(--color-on-surface-dim);">No patterns defined yet.</div>
  {:else}
    {#each filtered('pattern') as entry}
      <div class="ink-border" style="padding: 12px 14px; margin-bottom: 8px; background: var(--color-surface-bright);">
        <div class="flex items-center justify-between">
          <div class="flex items-center gap-2">
            <span style="font-weight: 900; font-size: 13px;">{entry.name}</span>
            <span style="font-size: 8px; font-weight: 700; padding: 1px 6px; background: {categoryColor(entry.category)}; color: #1a1a1a; text-transform: uppercase;">PATTERN</span>
            {#if entry.scope === 'global'}
              <span style="font-size: 8px; font-weight: 900; padding: 1px 6px; background: #007518; color: white;">🌐 GLOBAL</span>
            {:else if entry.scope === 'personal'}
              <span style="font-size: 8px; font-weight: 900; padding: 1px 6px; background: #6366f1; color: white;">👤 PERSONAL</span>
            {:else if entry.project_slug}
              <span style="font-size: 8px; font-weight: 900; padding: 1px 6px; background: #d97706; color: white;">📊 {entry.project_slug}</span>
            {/if}
          </div>
          <div class="flex gap-1">
            <button class="feedback-btn" style="font-size: 9px; padding: 2px 6px; cursor: pointer;" onclick={() => openEdit(entry)}>&#9998;</button>
            <button class="feedback-btn" style="font-size: 9px; padding: 2px 6px; cursor: pointer; color: var(--color-error); border-color: var(--color-error);" onclick={() => deleteEntry(entry.id, entry.name)}>&#10005;</button>
          </div>
        </div>
        <div style="font-size: 11px; color: var(--color-on-surface-dim); margin-top: 4px; line-height: 1.5;">{entry.definition || '-'}</div>
      </div>
    {/each}
  {/if}

<!-- ═══════════════════════════════════════════════════════════ -->
<!-- ORG MAP TAB                                                -->
<!-- ═══════════════════════════════════════════════════════════ -->
{:else if activeTab === 'org'}
  <div class="flex items-center justify-between mb-4">
    <div style="font-size: 9px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.08em; color: var(--color-on-surface-dim);">Organizational structure and hierarchy</div>
    <button class="send-btn" style="font-size: 10px; padding: 6px 14px;" onclick={openAdd}>+ ADD ORG ENTRY</button>
  </div>
  {#if loading && filtered('org').length === 0}
    <div style="font-size: 12px; color: var(--color-on-surface-dim);">Loading...</div>
  {:else if filtered('org').length === 0}
    <div style="font-size: 12px; color: var(--color-on-surface-dim);">No org entries defined yet.</div>
  {:else}
    {#each filtered('org') as entry}
      <div class="ink-border" style="padding: 12px 14px; margin-bottom: 8px; background: var(--color-surface-bright);">
        <div class="flex items-center justify-between">
          <div class="flex items-center gap-2">
            <span style="font-weight: 900; font-size: 13px;">{entry.name}</span>
            <span style="font-size: 8px; font-weight: 700; padding: 1px 6px; background: {categoryColor(entry.category)}; color: #1a1a1a; text-transform: uppercase;">ORG</span>
            {#if entry.scope === 'global'}
              <span style="font-size: 8px; font-weight: 900; padding: 1px 6px; background: #007518; color: white;">🌐 GLOBAL</span>
            {:else if entry.scope === 'personal'}
              <span style="font-size: 8px; font-weight: 900; padding: 1px 6px; background: #6366f1; color: white;">👤 PERSONAL</span>
            {:else if entry.project_slug}
              <span style="font-size: 8px; font-weight: 900; padding: 1px 6px; background: #d97706; color: white;">📊 {entry.project_slug}</span>
            {/if}
          </div>
          <div class="flex gap-1">
            <button class="feedback-btn" style="font-size: 9px; padding: 2px 6px; cursor: pointer;" onclick={() => openEdit(entry)}>&#9998;</button>
            <button class="feedback-btn" style="font-size: 9px; padding: 2px 6px; cursor: pointer; color: var(--color-error); border-color: var(--color-error);" onclick={() => deleteEntry(entry.id, entry.name)}>&#10005;</button>
          </div>
        </div>
        <div style="font-size: 11px; color: var(--color-on-surface-dim); margin-top: 4px; line-height: 1.5;">{entry.definition || '-'}</div>
        {#if entry.metadata?.parent}
          <div style="font-size: 10px; margin-top: 6px;">
            <span style="color: var(--color-on-surface-dim);">Parent:</span>
            <span style="font-weight: 700;">{entry.metadata.parent}</span>
          </div>
        {/if}
        {#if entry.metadata?.children?.length}
          <div style="font-size: 10px; margin-top: 4px;">
            <span style="color: var(--color-on-surface-dim);">Children:</span>
            {#each entry.metadata.children as child}
              <span style="font-weight: 700; margin-left: 6px; padding: 1px 6px; background: var(--color-surface-dim); font-size: 9px;">{child}</span>
            {/each}
          </div>
        {/if}
      </div>
    {/each}
  {/if}

<!-- ═══════════════════════════════════════════════════════════ -->
<!-- RULES (THRESHOLDS) TAB                                     -->
<!-- ═══════════════════════════════════════════════════════════ -->
{:else if activeTab === 'thresholds'}
  <div class="flex items-center justify-between mb-4">
    <div style="font-size: 9px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.08em; color: var(--color-on-surface-dim);">Thresholds, targets, and alert rules</div>
    <button class="send-btn" style="font-size: 10px; padding: 6px 14px;" onclick={openAdd}>+ ADD RULE</button>
  </div>
  {#if loading && filtered('threshold').length === 0}
    <div style="font-size: 12px; color: var(--color-on-surface-dim);">Loading...</div>
  {:else if filtered('threshold').length === 0}
    <div style="font-size: 12px; color: var(--color-on-surface-dim);">No rules defined yet.</div>
  {:else}
    {#each filtered('threshold') as entry}
      <div class="ink-border" style="padding: 12px 14px; margin-bottom: 8px; background: var(--color-surface-bright);">
        <div class="flex items-center justify-between">
          <div class="flex items-center gap-2">
            <span style="font-weight: 900; font-size: 13px;">{entry.name}</span>
            <span style="font-size: 8px; font-weight: 700; padding: 1px 6px; background: {categoryColor(entry.category)}; color: #1a1a1a; text-transform: uppercase;">RULE</span>
            {#if entry.scope === 'global'}
              <span style="font-size: 8px; font-weight: 900; padding: 1px 6px; background: #007518; color: white;">🌐 GLOBAL</span>
            {:else if entry.scope === 'personal'}
              <span style="font-size: 8px; font-weight: 900; padding: 1px 6px; background: #6366f1; color: white;">👤 PERSONAL</span>
            {:else if entry.project_slug}
              <span style="font-size: 8px; font-weight: 900; padding: 1px 6px; background: #d97706; color: white;">📊 {entry.project_slug}</span>
            {/if}
          </div>
          <div class="flex gap-1">
            <button class="feedback-btn" style="font-size: 9px; padding: 2px 6px; cursor: pointer;" onclick={() => openEdit(entry)}>&#9998;</button>
            <button class="feedback-btn" style="font-size: 9px; padding: 2px 6px; cursor: pointer; color: var(--color-error); border-color: var(--color-error);" onclick={() => deleteEntry(entry.id, entry.name)}>&#10005;</button>
          </div>
        </div>
        <div style="font-size: 11px; color: var(--color-on-surface-dim); margin-top: 4px; line-height: 1.5;">{entry.definition || '-'}</div>
        <div style="display: flex; gap: 12px; margin-top: 8px;">
          {#if entry.metadata?.target != null}
            <div class="ink-border" style="padding: 6px 10px; background: var(--color-surface); text-align: center;">
              <div style="font-size: 16px; font-weight: 900; color: #00fc40;">{entry.metadata.target}</div>
              <div style="font-size: 8px; text-transform: uppercase; color: var(--color-on-surface-dim);">TARGET</div>
            </div>
          {/if}
          {#if entry.metadata?.alert_below != null}
            <div class="ink-border" style="padding: 6px 10px; background: var(--color-surface); text-align: center;">
              <div style="font-size: 16px; font-weight: 900; color: #e74c3c;">&lt; {entry.metadata.alert_below}</div>
              <div style="font-size: 8px; text-transform: uppercase; color: var(--color-on-surface-dim);">ALERT BELOW</div>
            </div>
          {/if}
          {#if entry.metadata?.alert_above != null}
            <div class="ink-border" style="padding: 6px 10px; background: var(--color-surface); text-align: center;">
              <div style="font-size: 16px; font-weight: 900; color: #e74c3c;">&gt; {entry.metadata.alert_above}</div>
              <div style="font-size: 8px; text-transform: uppercase; color: var(--color-on-surface-dim);">ALERT ABOVE</div>
            </div>
          {/if}
        </div>
      </div>
    {/each}
  {/if}

<!-- ═══════════════════════════════════════════════════════════ -->
<!-- GRAPH TAB                                                  -->
<!-- ═══════════════════════════════════════════════════════════ -->
{:else if activeTab === 'graph'}
  <div class="flex items-center justify-between mb-4">
    <div style="font-size: 9px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.08em; color: var(--color-on-surface-dim);">Knowledge graph — relationships between brain entries</div>
    <button class="feedback-btn" style="font-size: 9px; padding: 4px 10px; cursor: pointer;" onclick={async () => { tabLoaded['graph'] = false; loading = true; await loadGraph(); loading = false; tabLoaded['graph'] = true; }}>REFRESH</button>
  </div>
  {#if loading && graphData.nodes?.length === 0}
    <div style="font-size: 12px; color: var(--color-on-surface-dim);">Loading graph...</div>
  {:else if graphData.nodes?.length === 0}
    <div style="font-size: 12px; color: var(--color-on-surface-dim);">No graph data available. Add entries to build the knowledge graph.</div>
  {/if}
  <div bind:this={graphContainer} style="width: 100%; height: 500px; background: #1a1a1a; border: 2px solid var(--color-on-surface);"></div>
  <div style="display: flex; gap: 16px; margin-top: 8px; flex-wrap: wrap;">
    {#each [
      { label: 'METRIC', color: '#00fc40' },
      { label: 'FORMULA', color: '#0078d4' },
      { label: 'ENTITY', color: '#ff9d00' },
      { label: 'ORG', color: '#9b59b6' },
      { label: 'OTHER', color: '#e74c3c' },
    ] as legend}
      <div class="flex items-center gap-1">
        <span style="width: 10px; height: 10px; background: {legend.color}; display: inline-block;"></span>
        <span style="font-size: 8px; font-weight: 700; text-transform: uppercase; color: var(--color-on-surface-dim);">{legend.label}</span>
      </div>
    {/each}
  </div>

<!-- ═══════════════════════════════════════════════════════════ -->
<!-- LOG TAB                                                    -->
<!-- ═══════════════════════════════════════════════════════════ -->
{:else if activeTab === 'log'}
  <div class="flex items-center justify-between mb-4">
    <div style="font-size: 9px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.08em; color: var(--color-on-surface-dim);">Brain access log — who queried what</div>
    <button class="feedback-btn" style="font-size: 9px; padding: 4px 10px; cursor: pointer;" onclick={async () => { tabLoaded['log'] = false; loading = true; await loadLog(); loading = false; tabLoaded['log'] = true; }}>REFRESH</button>
  </div>
  {#if loading && accessLog.length === 0}
    <div style="font-size: 12px; color: var(--color-on-surface-dim);">Loading...</div>
  {:else if accessLog.length === 0}
    <div style="font-size: 12px; color: var(--color-on-surface-dim);">No access log entries yet.</div>
  {:else}
    <table class="data-table" style="width: 100%;">
      <thead><tr>
        <th>USER</th>
        <th>ACTION</th>
        <th>ENTRY</th>
        <th>DETAIL</th>
        <th>TIME</th>
      </tr></thead>
      <tbody>
        {#each accessLog as log}
          <tr>
            <td style="font-size: 11px; font-weight: 700;">{log.username || log.user || '-'}</td>
            <td><span class="tag-label" style="font-size: 8px;">{log.action || log.event || '-'}</span></td>
            <td style="font-size: 11px;">{log.entry_name || log.name || '-'}</td>
            <td style="font-size: 10px; color: var(--color-on-surface-dim); max-width: 300px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">{log.detail || log.details || '-'}</td>
            <td style="font-size: 10px; color: var(--color-on-surface-dim);">{fmtDate(log.created_at || log.timestamp)}</td>
          </tr>
        {/each}
      </tbody>
    </table>
  {/if}

{/if}

</div>
</div>
</div>
</div>

<!-- ═══════════════════════════════════════════════════════════ -->
<!-- ADD / EDIT MODAL                                           -->
<!-- ═══════════════════════════════════════════════════════════ -->
{#if showAdd}
<!-- svelte-ignore a11y_no_static_element_interactions -->
<div style="position: fixed; inset: 0; background: rgba(0,0,0,0.6); z-index: 200; display: flex; align-items: center; justify-content: center;" onclick={(e: MouseEvent) => { if (e.target === e.currentTarget) resetForm(); }}>
  <div class="ink-border stamp-shadow" style="background: var(--color-surface); width: 520px; max-height: 90vh; overflow-y: auto;">
    <div class="dark-title-bar flex items-center justify-between" style="padding: 8px 14px; font-size: 11px;">
      <span>{editId ? 'EDIT ENTRY' : 'ADD ENTRY'}</span>
      <button onclick={resetForm} style="background: none; border: none; color: var(--color-surface); cursor: pointer; font-weight: 900;">&#10005;</button>
    </div>
    <div style="padding: 16px;">

      <!-- Category -->
      <div style="margin-bottom: 10px;">
        <div style="font-size: 9px; font-weight: 700; text-transform: uppercase; margin-bottom: 3px;">CATEGORY</div>
        <select bind:value={addCategory} style="width: 100%; border: 2px solid var(--color-on-surface); padding: 6px 10px; font-family: var(--font-family-display); font-size: 11px; background: var(--color-surface);">
          <option value="glossary">GLOSSARY</option>
          <option value="formula">FORMULA</option>
          <option value="alias">ALIAS</option>
          <option value="pattern">PATTERN</option>
          <option value="org">ORG MAP</option>
          <option value="threshold">RULE / THRESHOLD</option>
        </select>
      </div>

      <!-- Scope -->
      <div style="margin-bottom: 10px;">
        <div style="font-size: 9px; font-weight: 700; text-transform: uppercase; margin-bottom: 3px;">SCOPE</div>
        <select bind:value={newEntryScope} style="width: 100%; border: 2px solid var(--color-on-surface); padding: 6px 10px; font-family: var(--font-family-display); font-size: 11px; background: var(--color-surface);">
          <option value="global">🌐 Global</option>
          {#each userProjects as proj}
            <option value={proj.slug}>📊 {proj.agent_name || proj.name}</option>
          {/each}
          <option value="personal">👤 Personal</option>
        </select>
      </div>

      <!-- Name -->
      <div style="margin-bottom: 10px;">
        <div style="font-size: 9px; font-weight: 700; text-transform: uppercase; margin-bottom: 3px;">NAME *</div>
        <input type="text" bind:value={addName} placeholder="e.g. Revenue, NPS Score, APAC Region..." style="width: 100%; border: 2px solid var(--color-on-surface); padding: 6px 10px; font-family: var(--font-family-display); font-size: 12px; background: var(--color-surface);" />
      </div>

      <!-- Definition -->
      <div style="margin-bottom: 10px;">
        <div style="font-size: 9px; font-weight: 700; text-transform: uppercase; margin-bottom: 3px;">DEFINITION</div>
        <textarea bind:value={addDefinition} placeholder="What does this mean in the business context?" rows="3" style="width: 100%; border: 2px solid var(--color-on-surface); padding: 6px 10px; font-family: var(--font-family-display); font-size: 11px; background: var(--color-surface); resize: vertical;"></textarea>
      </div>

      <!-- FORMULA-SPECIFIC FIELDS -->
      {#if addCategory === 'formula'}
        <div style="margin-bottom: 10px;">
          <div style="font-size: 9px; font-weight: 700; text-transform: uppercase; margin-bottom: 3px;">FORMULA EXPRESSION</div>
          <input type="text" bind:value={formulaExpr} placeholder="e.g. (revenue - cost) / revenue * 100" style="width: 100%; border: 2px solid var(--color-on-surface); padding: 6px 10px; font-family: var(--font-family-display); font-size: 11px; background: var(--color-surface);" />
        </div>
        <div style="margin-bottom: 10px;">
          <div style="font-size: 9px; font-weight: 700; text-transform: uppercase; margin-bottom: 3px;">UNIT</div>
          <select bind:value={formulaUnit} style="width: 100%; border: 2px solid var(--color-on-surface); padding: 6px 10px; font-family: var(--font-family-display); font-size: 11px; background: var(--color-surface);">
            <option value="">None</option>
            <option value="%">%</option>
            <option value="$">$ (USD)</option>
            <option value="count">Count</option>
            <option value="ratio">Ratio</option>
            <option value="days">Days</option>
            <option value="hours">Hours</option>
            <option value="kg">kg</option>
            <option value="units">Units</option>
          </select>
        </div>
      {/if}

      <!-- ALIAS-SPECIFIC FIELDS -->
      {#if addCategory === 'alias'}
        <div style="margin-bottom: 10px;">
          <div style="font-size: 9px; font-weight: 700; text-transform: uppercase; margin-bottom: 3px;">ALIAS TAGS</div>
          <div style="display: flex; flex-wrap: wrap; gap: 4px; margin-bottom: 6px;">
            {#each getFormAliases() as alias}
              <span style="font-size: 9px; font-weight: 700; padding: 2px 8px; background: #ff9d00; color: #1a1a1a; display: flex; align-items: center; gap: 4px;">
                {alias}
                <button onclick={() => removeAliasTag(alias)} style="background: none; border: none; color: #1a1a1a; cursor: pointer; font-size: 10px; padding: 0; line-height: 1;">&#10005;</button>
              </span>
            {/each}
          </div>
          <div style="display: flex; gap: 6px;">
            <input type="text" bind:value={aliasInput} placeholder="Type alias and press Add..." style="flex: 1; border: 2px solid var(--color-on-surface); padding: 4px 8px; font-family: var(--font-family-display); font-size: 11px; background: var(--color-surface);"
              onkeydown={(e: KeyboardEvent) => { if (e.key === 'Enter') { e.preventDefault(); addAliasTag(); } }} />
            <button class="feedback-btn" style="font-size: 9px; padding: 4px 10px; cursor: pointer;" onclick={addAliasTag}>ADD</button>
          </div>
        </div>
      {/if}

      <!-- THRESHOLD-SPECIFIC FIELDS -->
      {#if addCategory === 'threshold'}
        <div style="display: flex; gap: 8px; margin-bottom: 10px;">
          <div style="flex: 1;">
            <div style="font-size: 9px; font-weight: 700; text-transform: uppercase; margin-bottom: 3px;">TARGET</div>
            <input type="number" bind:value={threshTarget} placeholder="100" style="width: 100%; border: 2px solid var(--color-on-surface); padding: 6px 10px; font-family: var(--font-family-display); font-size: 11px; background: var(--color-surface);" />
          </div>
          <div style="flex: 1;">
            <div style="font-size: 9px; font-weight: 700; text-transform: uppercase; margin-bottom: 3px;">ALERT BELOW</div>
            <input type="number" bind:value={threshAlertBelow} placeholder="80" style="width: 100%; border: 2px solid var(--color-on-surface); padding: 6px 10px; font-family: var(--font-family-display); font-size: 11px; background: var(--color-surface);" />
          </div>
          <div style="flex: 1;">
            <div style="font-size: 9px; font-weight: 700; text-transform: uppercase; margin-bottom: 3px;">ALERT ABOVE</div>
            <input type="number" bind:value={threshAlertAbove} placeholder="120" style="width: 100%; border: 2px solid var(--color-on-surface); padding: 6px 10px; font-family: var(--font-family-display); font-size: 11px; background: var(--color-surface);" />
          </div>
        </div>
      {/if}

      <!-- Metadata JSON (collapsible) -->
      <details style="margin-bottom: 12px;">
        <summary style="font-size: 9px; font-weight: 700; text-transform: uppercase; cursor: pointer; color: var(--color-on-surface-dim); margin-bottom: 3px;">ADVANCED: RAW METADATA JSON</summary>
        <textarea bind:value={addMetadata} rows="4" style="width: 100%; border: 2px solid var(--color-on-surface); padding: 6px 10px; font-family: var(--font-family-display); font-size: 10px; background: var(--color-surface); resize: vertical; margin-top: 4px;"></textarea>
      </details>

      <!-- Error display -->
      {#if addError}
        <div style="font-size: 11px; color: var(--color-error); margin-bottom: 8px; padding: 6px 10px; border: 1px solid var(--color-error); background: rgba(231, 76, 60, 0.1);">{addError}</div>
      {/if}

      <!-- Actions -->
      <div style="display: flex; gap: 8px;">
        {#if editId}
          <button class="send-btn" onclick={() => updateEntry(editId!)} disabled={saving || !addName.trim()} style="flex: 1; padding: 8px; font-size: 11px; justify-content: center; display: flex;">
            {saving ? 'SAVING...' : 'UPDATE ENTRY'}
          </button>
        {:else}
          <button class="send-btn" onclick={addEntry} disabled={saving || !addName.trim()} style="flex: 1; padding: 8px; font-size: 11px; justify-content: center; display: flex;">
            {saving ? 'SAVING...' : 'SAVE ENTRY'}
          </button>
        {/if}
        <button class="feedback-btn" onclick={resetForm} style="padding: 8px 16px; font-size: 11px; cursor: pointer;">CANCEL</button>
      </div>
    </div>
  </div>
</div>
{/if}
