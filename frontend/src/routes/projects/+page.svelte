<script lang="ts">
  import { onMount } from 'svelte';

  interface Project {
    id: number; slug: string; name: string; agent_name: string; agent_role: string;
    agent_personality: string; tables: number; rows: number; created_at: string; updated_at: string;
    is_favorite?: boolean; shared_by?: string; last_trained?: string;
  }

  let projects = $state<Project[]>([]);
  let sharedProjects = $state<Project[]>([]);
  let loading = $state(true);
  let activeFilter = $state('all');
  let deleteTarget = $state<any>(null);
  let deleteTypedName = $state('');

  // Create modal
  let showCreate = $state(false);
  let cName = $state('');
  let cAgent = $state('');
  let cRole = $state('');
  let cPersonality = $state('friendly');
  let cIcon = $state('');
  let creating = $state(false);
  let createError = $state('');
  let createSteps = $state<{label: string; status: 'pending'|'done'|'error'}[]>([]);
  let createResult = $state<any>(null);
  let fileInput: HTMLInputElement;
  let selectedFile = $state<File | null>(null);

  function _h(): Record<string, string> {
    const t = typeof localStorage !== 'undefined' ? localStorage.getItem('dash_token') : null;
    return t ? { Authorization: `Bearer ${t}` } : {};
  }

  onMount(() => { loadProjects(); loadShared(); });

  async function loadShared() {
    try { const res = await fetch('/api/projects/shared', { headers: _h() }); if (res.ok) { const d = await res.json(); sharedProjects = d.projects || []; } } catch {}
  }

  async function toggleFavorite(slug: string) {
    try { await fetch(`/api/projects/${slug}/favorite`, { method: 'POST', headers: _h() }); await loadProjects(); } catch {}
  }

  const filteredProjects = $derived(() => {
    if (activeFilter === 'mine') return projects;
    if (activeFilter === 'favorites') return projects.filter(p => p.is_favorite);
    if (activeFilter === 'shared') return [];
    return [...projects, ...sharedProjects];
  });

  const allCount = $derived(projects.length + sharedProjects.length);
  const favCount = $derived(projects.filter(p => p.is_favorite).length);

  async function loadProjects() {
    loading = true;
    try {
      const res = await fetch('/api/projects', { headers: _h() });
      if (res.ok) { const d = await res.json(); projects = d.projects || []; }
    } catch {}
    loading = false;
  }

  function openCreate() {
    showCreate = true; cName = ''; cAgent = ''; cRole = ''; cPersonality = 'friendly';
    createError = ''; createSteps = []; createResult = null; selectedFile = null;
  }

  async function doCreate() {
    if (!cName || !cAgent) { createError = 'Name and agent name required'; return; }
    creating = true; createError = ''; createResult = null;

    createSteps = [
      { label: 'Creating project schema', status: 'pending' },
      { label: 'Configuring agent persona', status: 'pending' },
      { label: 'Initializing knowledge base', status: 'pending' },
    ];
    if (selectedFile) createSteps.push(
      { label: `Loading ${selectedFile.name}`, status: 'pending' },
      { label: 'Generating metadata', status: 'pending' },
    );
    createSteps.push({ label: 'Agent ready', status: 'pending' });

    // Animate first steps
    for (let i = 0; i < 2; i++) {
      createSteps = createSteps.map((s, idx) => idx === i ? { ...s, status: 'done' as const } : s);
      await new Promise(r => setTimeout(r, 300));
    }

    try {
      const params = new URLSearchParams({ name: cName, agent_name: cAgent, agent_role: cRole, agent_personality: cPersonality });
      const res = await fetch(`/api/projects?${params}`, { method: 'POST', headers: _h() });
      if (!res.ok) { const e = await res.json().catch(() => ({ detail: 'Failed' })); throw new Error(e.detail); }
      const data = await res.json();

      createSteps = createSteps.map((s, idx) => idx === 2 ? { ...s, status: 'done' as const } : s);
      await new Promise(r => setTimeout(r, 200));

      // Upload file if provided
      if (selectedFile && data.slug) {
        const fd = new FormData();
        fd.append('file', selectedFile);
        const upRes = await fetch(`/api/upload?project=${data.slug}`, { method: 'POST', body: fd, headers: _h() });
        if (upRes.ok) {
          for (let i = 3; i < createSteps.length - 1; i++) {
            createSteps = createSteps.map((s, idx) => idx === i ? { ...s, status: 'done' as const } : s);
            await new Promise(r => setTimeout(r, 200));
          }
        }
      }

      // Mark all done
      createSteps = createSteps.map(s => ({ ...s, status: 'done' as const }));
      createResult = data;
      await loadProjects();
    } catch (e: any) {
      createError = e.message;
      createSteps = createSteps.map(s => s.status === 'pending' ? { ...s, status: 'error' as const } : s);
    }
    creating = false;
  }

  // Share
  let showShare = $state(false);
  let shareSlug = $state('');
  let shareUsername = $state('');
  let shareResult = $state('');

  function openShare(slug: string) { shareSlug = slug; shareUsername = ''; shareResult = ''; showShare = true; }

  async function doShare() {
    if (!shareUsername) return;
    try {
      const res = await fetch(`/api/projects/${shareSlug}/share?username=${encodeURIComponent(shareUsername)}`, { method: 'POST', headers: _h() });
      if (res.ok) { const d = await res.json(); shareResult = d.status === 'already_shared' ? 'Already shared' : 'Shared!'; }
      else { const e = await res.json(); shareResult = e.detail || 'Failed'; }
    } catch { shareResult = 'Error'; }
  }

  async function deleteProject(slug: string, name: string) {
    try {
      await fetch(`/api/projects/${slug}`, { method: 'DELETE', headers: _h() });
      await loadProjects();
    } catch {}
  }

  function timeAgo(ts: string | null): string {
    if (!ts) return '';
    try {
      const d = new Date(ts);
      const diff = Date.now() - d.getTime();
      if (diff < 3600000) return Math.floor(diff / 60000) + 'm ago';
      if (diff < 86400000) return Math.floor(diff / 3600000) + 'h ago';
      return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
    } catch { return ''; }
  }

  const agentIcons: Record<string, string> = {
    sales: '<svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="12" y1="20" x2="12" y2="10"/><line x1="18" y1="20" x2="18" y2="4"/><line x1="6" y1="20" x2="6" y2="16"/></svg>',
    crm: '<svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M23 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/></svg>',
    hr: '<svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M23 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/></svg>',
    support: '<svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg>',
    finance: '<svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="12" y1="1" x2="12" y2="23"/><path d="M17 5H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6"/></svg>',
    marketing: '<svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M22 12h-4l-3 9L9 3l-3 9H2"/></svg>',
    product: '<svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="2" y="3" width="20" height="14" rx="2"/><line x1="8" y1="21" x2="16" y2="21"/><line x1="12" y1="17" x2="12" y2="21"/></svg>',
    engineering: '<svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 2.83-2.83l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z"/></svg>',
    data: '<svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><ellipse cx="12" cy="5" rx="9" ry="3"/><path d="M21 12c0 1.66-4 3-9 3s-9-1.34-9-3"/><path d="M3 5v14c0 1.66 4 3 9 3s9-1.34 9-3V5"/></svg>',
    analytics: '<svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21.21 15.89A10 10 0 1 1 8 2.83"/><path d="M22 12A10 10 0 0 0 12 2v10z"/></svg>',
    inventory: '<svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z"/><polyline points="3.27 6.96 12 12.01 20.73 6.96"/><line x1="12" y1="22.08" x2="12" y2="12"/></svg>',
    daily: '<svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="4" width="18" height="18" rx="2" ry="2"/><line x1="16" y1="2" x2="16" y2="6"/><line x1="8" y1="2" x2="8" y2="6"/><line x1="3" y1="10" x2="21" y2="10"/></svg>',
  };
  const defaultIcon = '<svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="4" y="4" width="16" height="16" rx="2"/><path d="M9 9h6v6H9z"/><path d="M9 1v3M15 1v3M9 20v3M15 20v3M20 9h3M20 14h3M1 9h3M1 14h3"/></svg>';
  function getIconKey(name: string): string {
    const lower = name.toLowerCase();
    for (const k of Object.keys(agentIcons)) { if (lower.includes(k)) return k; }
    return '';
  }
  function getIcon(name: string): string {
    const key = getIconKey(name);
    return key ? agentIcons[key] : defaultIcon;
  }
</script>

<div style="padding: 24px; overflow-y: auto; height: 100%;">
  <div style="max-width: 1100px; margin: 0 auto;">

    <!-- Header -->
    <div class="flex items-center justify-between mb-6">
      <div>
        <div style="font-size: 24px; font-weight: 900; text-transform: uppercase; letter-spacing: -0.01em;">Your Data Agents</div>
        <div style="font-size: 11px; color: var(--color-on-surface-dim); text-transform: uppercase; letter-spacing: 0.1em; margin-top: 4px;">Each agent is an expert on its own dataset</div>
      </div>
      <button class="send-btn" onclick={openCreate} style="padding: 10px 20px; font-size: 12px;">+ NEW AGENT</button>
    </div>

    <!-- Filter Tabs -->
    <div class="flex items-center gap-2 mb-6">
      {#each [
        { id: 'all', label: 'All', count: allCount },
        { id: 'mine', label: 'My Agents', count: projects.length },
        { id: 'favorites', label: 'Favorites', count: favCount },
        { id: 'shared', label: 'Shared with me', count: sharedProjects.length },
      ] as f}
        <button
          onclick={() => activeFilter = f.id}
          style="padding: 6px 14px; font-size: 11px; font-weight: {activeFilter === f.id ? 900 : 400}; text-transform: uppercase; letter-spacing: 0.05em; border: 2px solid {activeFilter === f.id ? 'var(--color-on-surface)' : 'transparent'}; background: {activeFilter === f.id ? 'var(--color-surface-bright)' : 'transparent'}; color: var(--color-on-surface); cursor: pointer; font-family: var(--font-family-display);"
        >
          {f.label} ({f.count})
        </button>
      {/each}
    </div>

    {#if loading}
      <div style="text-align: center; padding: 60px; font-size: 12px; text-transform: uppercase; color: var(--color-on-surface-dim);">Loading...</div>
    {:else}
      <!-- Project Cards Grid -->
      <div style="display: grid; grid-template-columns: repeat(auto-fill, minmax(280px, 1fr)); gap: 16px;">
        {#each (activeFilter === 'shared' ? sharedProjects : filteredProjects()) as p}
          <div class="ink-border stamp-shadow" style="background: var(--color-surface-bright); display: flex; flex-direction: column;">
            <!-- Card Header -->
            <div style="padding: 16px 16px 12px; flex: 1;">
              <div class="flex items-center justify-between" style="margin-bottom: 8px;">
                <span style="display: inline-flex; align-items: center; justify-content: center; width: 36px; height: 36px; border: 2px solid var(--color-on-surface); padding: 4px;">{@html getIcon(p.agent_name)}</span>
                {#if !p.shared_by}
                  <button onclick={(e) => { e.stopPropagation(); toggleFavorite(p.slug); }} style="background: none; border: none; cursor: pointer; font-size: 18px; padding: 0;" title={p.is_favorite ? 'Remove from favorites' : 'Add to favorites'}>
                    {p.is_favorite ? '⭐' : '☆'}
                  </button>
                {:else}
                  <span style="font-size: 9px; color: var(--color-on-surface-dim); text-transform: uppercase;">shared by {p.shared_by}</span>
                {/if}
              </div>
              <div style="font-size: 16px; font-weight: 900; text-transform: uppercase; letter-spacing: 0.02em; margin-bottom: 4px;">{p.agent_name}</div>
              <div style="font-size: 11px; color: var(--color-on-surface-dim); line-height: 1.5; min-height: 33px;">
                {p.agent_role || 'Data analysis agent'}
              </div>

              <!-- Stats -->
              <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 6px; margin-top: 12px;">
                <div class="ink-border" style="padding: 6px 8px; background: var(--color-surface);">
                  <div style="font-size: 9px; text-transform: uppercase; color: var(--color-on-surface-dim); letter-spacing: 0.08em;">Tables</div>
                  <div style="font-size: 16px; font-weight: 900;">{p.tables}</div>
                </div>
                <div class="ink-border" style="padding: 6px 8px; background: var(--color-surface);">
                  <div style="font-size: 9px; text-transform: uppercase; color: var(--color-on-surface-dim); letter-spacing: 0.08em;">Rows</div>
                  <div style="font-size: 16px; font-weight: 900;">{p.rows.toLocaleString()}</div>
                </div>
              </div>

              <div style="font-size: 9px; color: var(--color-on-surface-dim); margin-top: 8px; text-transform: uppercase;">
                {#if p.last_trained}
                  <span style="color: var(--color-primary);">Trained {new Date(p.last_trained).toLocaleString('en-US', {month:'short', day:'numeric', hour:'2-digit', minute:'2-digit'})}</span> ·
                {:else}
                  <span style="color: var(--color-warning);">Not trained</span> ·
                {/if}
                Updated {new Date(p.updated_at).toLocaleString('en-US', {month:'short', day:'numeric', hour:'2-digit', minute:'2-digit'})}
              </div>
            </div>

            <!-- Card Actions -->
            <div style="display: flex; border-top: 2px solid var(--color-on-surface);">
              <a href="/ui/project/{p.slug}" style="flex: 1; padding: 10px; text-align: center; font-size: 11px; font-weight: 900; text-transform: uppercase; letter-spacing: 0.08em; text-decoration: none; color: var(--color-on-surface); background: var(--color-primary-container); border-right: 2px solid var(--color-on-surface);">
                CHAT
              </a>
              {#if !p.shared_by}
                <a href="/ui/project/{p.slug}/settings" style="flex: 1; padding: 10px; text-align: center; font-size: 11px; font-weight: 900; text-transform: uppercase; letter-spacing: 0.08em; text-decoration: none; color: var(--color-on-surface); border-right: 2px solid var(--color-on-surface);">
                  SETTINGS
                </a>
                <button onclick={() => { deleteTarget = p; deleteTypedName = ''; }} style="padding: 10px 14px; background: none; border: none; cursor: pointer; color: var(--color-error); font-size: 11px; font-weight: 900;">
                  ✕
                </button>
              {/if}
            </div>
          </div>
        {/each}

        <!-- Empty state / create card (only when NO projects at all, including shared) -->
        {#if projects.length === 0 && sharedProjects.length === 0}
          <div class="ink-border" style="background: var(--color-surface); padding: 40px 24px; text-align: center; border-style: dashed; grid-column: 1 / -1;">
            <div style="margin-bottom: 12px; display: flex; justify-content: center;">{@html defaultIcon.replace('width="24"', 'width="36"').replace('height="24"', 'height="36"')}</div>
            <div style="font-size: 16px; font-weight: 900; text-transform: uppercase; margin-bottom: 8px;">No agents yet</div>
            <div style="font-size: 12px; color: var(--color-on-surface-dim); margin-bottom: 16px;">Create your first data agent. Upload your data and I'll become an expert on it.</div>
            <button class="send-btn" onclick={openCreate} style="padding: 10px 24px; font-size: 12px;">+ CREATE FIRST AGENT</button>
          </div>
        {/if}
      </div>
    {/if}
  </div>
</div>

<!-- ═══ CREATE MODAL ═══ -->
{#if showCreate}
<!-- svelte-ignore a11y_no_static_element_interactions -->
<div style="position: fixed; inset: 0; background: rgba(56,56,50,0.7); z-index: 100; display: flex; align-items: center; justify-content: center; padding: 20px;" onclick={(e) => { if (e.target === e.currentTarget && !creating) showCreate = false; }}>
  <div class="ink-border stamp-shadow" style="background: var(--color-surface); width: 100%; max-width: 520px; max-height: 90vh; overflow-y: auto;">
    <div class="dark-title-bar flex items-center justify-between" style="padding: 10px 16px; font-size: 12px;">
      <span>CREATE NEW DATA AGENT</span>
      <button onclick={() => { if (!creating) showCreate = false; }} style="background: none; border: none; color: var(--color-surface); cursor: pointer; font-size: 16px; font-weight: 900;">✕</button>
    </div>
    <div style="padding: 20px;">

      <div style="font-size: 12px; color: var(--color-on-surface-dim); margin-bottom: 16px;">
        I'll become an expert on your data. Upload files and tell me what to focus on.
      </div>

      {#if !createResult}
        <div style="margin-bottom: 12px;">
          <div class="tag-label mb-1" style="font-size: 9px;">AGENT NAME</div>
          <input type="text" bind:value={cAgent} placeholder="Sales Agent" style="width: 100%; background: var(--color-surface-dim); border: 2px solid var(--color-on-surface); padding: 8px 12px; font-family: var(--font-family-display); font-size: 13px;" />
        </div>

        <div style="margin-bottom: 12px;">
          <div class="tag-label mb-1" style="font-size: 9px;">ICON</div>
          <div style="display: flex; flex-wrap: wrap; gap: 6px;">
            {#each Object.entries(agentIcons) as [key, svg]}
              <button onclick={() => cIcon = key} style="width: 38px; height: 38px; display: flex; align-items: center; justify-content: center; border: 2px solid {cIcon === key ? 'var(--color-primary)' : 'var(--color-on-surface)'}; background: {cIcon === key ? 'var(--color-primary-container)' : 'var(--color-surface)'}; cursor: pointer; padding: 4px;" title={key}>
                {@html svg}
              </button>
            {/each}
          </div>
        </div>

        <div style="margin-bottom: 12px;">
          <div class="tag-label mb-1" style="font-size: 9px;">PROJECT NAME</div>
          <input type="text" bind:value={cName} placeholder="Sales Analysis" style="width: 100%; background: var(--color-surface-dim); border: 2px solid var(--color-on-surface); padding: 8px 12px; font-family: var(--font-family-display); font-size: 13px;" />
        </div>

        <div style="margin-bottom: 12px;">
          <div class="tag-label mb-1" style="font-size: 9px;">EXPERTISE / FOCUS</div>
          <input type="text" bind:value={cRole} placeholder="Revenue, pipeline, forecasting..." style="width: 100%; background: var(--color-surface-dim); border: 2px solid var(--color-on-surface); padding: 8px 12px; font-family: var(--font-family-display); font-size: 13px;" />
        </div>

        <div style="margin-bottom: 16px;">
          <div class="tag-label mb-1" style="font-size: 9px;">PERSONALITY</div>
          <div class="flex gap-2">
            {#each [['friendly', 'Friendly & insightful'], ['formal', 'Formal & precise'], ['technical', 'Technical & detailed']] as [val, label]}
              <button onclick={() => cPersonality = val} style="flex: 1; padding: 6px; font-size: 10px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.05em; border: 2px solid var(--color-on-surface); background: {cPersonality === val ? 'var(--color-on-surface)' : 'var(--color-surface)'}; color: {cPersonality === val ? 'var(--color-surface)' : 'var(--color-on-surface)'}; cursor: pointer; font-family: var(--font-family-display);">
                {label}
              </button>
            {/each}
          </div>
        </div>

        <!-- Upload moved to Settings page after project creation -->

        {#if createError}<div style="font-size: 11px; color: var(--color-error); margin-bottom: 8px; font-weight: 700;">{createError}</div>{/if}

        <button class="send-btn" onclick={doCreate} disabled={creating} style="width: 100%; padding: 12px; font-size: 12px; justify-content: center; display: flex;">
          {creating ? 'CREATING...' : '▶ CREATE AGENT'}
        </button>
      {/if}

      {#if createSteps.length > 0}
        <div style="margin-top: 16px; padding: 12px; background: var(--color-surface-dim); border-left: 3px solid var(--color-primary);">
          <div class="flex items-center gap-2 mb-2">
            <span class="tag-label" style="font-size: 9px;">AI ONBOARDING</span>
            {#if creating}<span class="status-dots"><span style="background: var(--color-primary);"></span><span style="background: var(--color-warning);"></span><span style="background: var(--color-error);"></span></span>{/if}
          </div>
          {#each createSteps as step}
            <div class="flex items-center gap-2" style="font-size: 11px; padding: 2px 0;">
              {#if step.status === 'done'}<span style="color: var(--color-primary);">✓</span>
              {:else if step.status === 'error'}<span style="color: var(--color-error);">✗</span>
              {:else}<span style="color: var(--color-on-surface-dim);">○</span>{/if}
              <span>{step.label}</span>
            </div>
          {/each}
          {#if createResult}
            <div style="margin-top: 10px; font-size: 12px; color: var(--color-primary); font-weight: 900; text-transform: uppercase;">
              ✓ {cAgent} is ready! Upload data to get started.
            </div>
            <a href="/ui/project/{createResult.slug}/settings" class="send-btn" style="display: flex; justify-content: center; margin-top: 8px; padding: 10px; font-size: 11px; text-decoration: none;">
              UPLOAD DATA & CONFIGURE →
            </a>
          {/if}
        </div>
      {/if}
    </div>
  </div>
</div>
{/if}

<!-- Share Modal -->
{#if showShare}
<!-- svelte-ignore a11y_no_static_element_interactions -->
<div style="position: fixed; inset: 0; background: rgba(56,56,50,0.7); z-index: 100; display: flex; align-items: center; justify-content: center;" onclick={(e) => { if (e.target === e.currentTarget) showShare = false; }}>
  <div class="ink-border stamp-shadow" style="background: var(--color-surface); width: 360px;">
    <div class="dark-title-bar flex items-center justify-between" style="padding: 8px 14px; font-size: 11px;">
      <span>SHARE PROJECT</span>
      <button onclick={() => showShare = false} style="background: none; border: none; color: var(--color-surface); cursor: pointer; font-weight: 900;">&#10005;</button>
    </div>
    <div style="padding: 16px;">
      <div style="font-size: 9px; font-weight: 700; text-transform: uppercase; margin-bottom: 3px;">USERNAME TO SHARE WITH</div>
      <input type="text" bind:value={shareUsername} placeholder="e.g., john" style="width: 100%; border: 2px solid var(--color-on-surface); padding: 6px 10px; font-family: var(--font-family-display); font-size: 12px; background: var(--color-surface); margin-bottom: 12px;" />
      {#if shareResult}
        <div style="font-size: 11px; font-weight: 700; margin-bottom: 8px; color: {shareResult === 'Shared!' ? 'var(--color-primary)' : 'var(--color-error)'};">{shareResult}</div>
      {/if}
      <button class="send-btn" onclick={doShare} style="width: 100%; padding: 8px; font-size: 11px; justify-content: center; display: flex;">SHARE</button>
    </div>
  </div>
</div>
{/if}

<!-- Delete confirmation modal -->
{#if deleteTarget}
  <!-- svelte-ignore a11y_no_static_element_interactions -->
  <div style="position: fixed; inset: 0; background: rgba(0,0,0,0.5); z-index: 200; display: flex; align-items: center; justify-content: center;" onclick={(e) => { if (e.target === e.currentTarget) deleteTarget = null; }}>
    <div class="ink-border stamp-shadow" style="background: var(--color-surface); width: 400px;">
      <div style="background: var(--color-error); color: white; padding: 10px 14px; font-size: 11px; font-weight: 900; text-transform: uppercase; letter-spacing: 0.08em; font-family: var(--font-family-display);">DELETE PROJECT</div>
      <div style="padding: 20px;">
        <div style="font-size: 13px; margin-bottom: 16px; line-height: 1.5;">
          This will permanently delete <strong>"{deleteTarget.name}"</strong> and ALL its data, tables, training, and knowledge. This action cannot be undone.
        </div>
        <div style="font-size: 9px; font-weight: 700; text-transform: uppercase; margin-bottom: 4px; color: var(--color-on-surface-dim);">TYPE THE PROJECT NAME TO CONFIRM</div>
        <input type="text" bind:value={deleteTypedName} placeholder={deleteTarget.name} style="width: 100%; border: 2px solid {deleteTypedName === deleteTarget.name ? 'var(--color-error)' : 'var(--color-on-surface)'}; padding: 8px 12px; font-family: var(--font-family-display); font-size: 12px; background: var(--color-surface); margin-bottom: 14px;" />
        <div class="flex gap-2">
          <button disabled={deleteTypedName !== deleteTarget.name} onclick={async () => {
            await deleteProject(deleteTarget.slug, deleteTarget.name);
            deleteTarget = null; deleteTypedName = '';
          }} style="flex: 1; padding: 10px; font-size: 11px; font-weight: 900; text-transform: uppercase; letter-spacing: 0.08em; font-family: var(--font-family-display); cursor: pointer; border: 2px solid var(--color-error); background: {deleteTypedName === deleteTarget.name ? 'var(--color-error)' : 'var(--color-surface-dim)'}; color: {deleteTypedName === deleteTarget.name ? 'white' : 'var(--color-on-surface-dim)'}; border-bottom-width: 3px;">
            DELETE PERMANENTLY
          </button>
          <button onclick={() => deleteTarget = null} style="flex: 1; padding: 10px; font-size: 11px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.08em; font-family: var(--font-family-display); cursor: pointer; border: 2px solid var(--color-on-surface); background: none; color: var(--color-on-surface);">
            CANCEL
          </button>
        </div>
      </div>
    </div>
  </div>
{/if}
