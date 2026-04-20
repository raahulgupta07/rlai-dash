<script lang="ts">
  import { onMount } from 'svelte';
  import EChartView from '$lib/echart.svelte';
  import { markdownToHtml } from '$lib';

  let dashboards = $state<any[]>([]);
  let activeDashboard = $state<any>(null);
  let editMode = $state(false);
  let loading = $state(true);
  let newDashName = $state('');
  let newDashProject = $state('');
  let showCreate = $state(false);
  let view = $state<'list' | 'detail'>('list');
  let activeListTab = $state<'all' | 'my' | 'shared' | 'favorites'>('all');
  let projects = $state<any[]>([]);
  let deleteTarget = $state<any>(null);
  let deleteTypedName = $state('');

  function _h(): Record<string, string> {
    const t = typeof localStorage !== 'undefined' ? localStorage.getItem('dash_token') : null;
    return t ? { Authorization: `Bearer ${t}` } : {};
  }

  onMount(async () => {
    await Promise.all([loadDashboards(), loadProjects()]);
    loading = false;
  });

  async function loadDashboards() {
    try {
      const res = await fetch('/api/all-dashboards', { headers: _h() });
      if (res.ok) { const d = await res.json(); dashboards = d.dashboards || []; }
    } catch {}
  }

  async function loadProjects() {
    try {
      const res = await fetch('/api/user-projects-brief', { headers: _h() });
      if (res.ok) { const d = await res.json(); projects = d.projects || []; }
    } catch {}
  }

  async function loadDashboard(id: number, projectSlug: string) {
    try {
      const res = await fetch(`/api/projects/${projectSlug}/dashboards/${id}`, { headers: _h() });
      if (res.ok) {
        activeDashboard = { ...(await res.json()), project_slug: projectSlug };
        view = 'detail'; editMode = false;
      }
    } catch {}
  }

  async function createDashboard() {
    const name = newDashName.trim() || 'Dashboard';
    const slug = newDashProject || projects[0]?.slug;
    if (!slug) return;
    try {
      const res = await fetch(`/api/projects/${slug}/dashboards?name=${encodeURIComponent(name)}`, { method: 'POST', headers: _h() });
      if (res.ok) { const d = await res.json(); newDashName = ''; showCreate = false; await loadDashboards(); await loadDashboard(d.id, slug); }
    } catch {}
  }

  async function removeWidget(widgetId: string) {
    if (!activeDashboard) return;
    try { await fetch(`/api/projects/${activeDashboard.project_slug}/dashboards/${activeDashboard.id}/widgets/${widgetId}`, { method: 'DELETE', headers: _h() }); await loadDashboard(activeDashboard.id, activeDashboard.project_slug); } catch {}
  }

  async function deleteDashboard() {
    if (!activeDashboard) return;
    try { await fetch(`/api/projects/${activeDashboard.project_slug}/dashboards/${activeDashboard.id}`, { method: 'DELETE', headers: _h() }); activeDashboard = null; view = 'list'; await loadDashboards(); } catch {}
  }

  function goBack() { activeDashboard = null; view = 'list'; editMode = false; loadDashboards(); }

  function timeAgo(ts: string | null): string {
    if (!ts) return '';
    const diff = Date.now() - new Date(ts).getTime();
    if (diff < 3600000) return Math.floor(diff / 60000) + 'm ago';
    if (diff < 86400000) return Math.floor(diff / 3600000) + 'h ago';
    return new Date(ts).toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
  }

  const filteredDashboards = $derived(
    activeListTab === 'all' ? dashboards :
    activeListTab === 'my' ? dashboards :
    activeListTab === 'shared' ? [] :
    []
  );
</script>

<div class="flex flex-col h-full" style="overflow-y: auto;">

  {#if view === 'list'}
    <!-- ═══ DASHBOARD LIST (matches projects page style) ═══ -->
    <div style="max-width: 1100px; margin: 0 auto; padding: 30px 20px; width: 100%;">

      <!-- Header -->
      <div class="flex items-center justify-between mb-4">
        <div>
          <div style="font-size: 24px; font-weight: 900; text-transform: uppercase; letter-spacing: -0.01em;">YOUR DASHBOARDS</div>
          <div style="font-size: 12px; color: var(--color-on-surface-dim); text-transform: uppercase; letter-spacing: 0.05em; margin-top: 4px;">PIN CHARTS AND ANALYSIS FROM CHAT TO BUILD DASHBOARDS</div>
        </div>
        <button class="send-btn" style="padding: 10px 20px; font-size: 11px;" onclick={() => { showCreate = true; newDashProject = projects[0]?.slug || ''; }}>+ NEW DASHBOARD</button>
      </div>

      <!-- Tabs (text style like projects page) -->
      <div class="flex gap-4 mb-6" style="border-bottom: 2px solid var(--color-surface-dim); padding-bottom: 2px;">
        {#each [
          { id: 'all', label: 'ALL', count: dashboards.length },
          { id: 'my', label: 'MY DASHBOARDS', count: dashboards.length },
          { id: 'favorites', label: 'FAVORITES', count: 0 },
          { id: 'shared', label: 'SHARED WITH ME', count: 0 },
        ] as tab}
          <button
            style="background: none; border: none; border-bottom: 2px solid {activeListTab === tab.id ? 'var(--color-on-surface)' : 'transparent'}; padding: 8px 4px; font-family: var(--font-family-display); font-size: 11px; font-weight: {activeListTab === tab.id ? 900 : 400}; text-transform: uppercase; letter-spacing: 0.06em; cursor: pointer; color: {activeListTab === tab.id ? 'var(--color-on-surface)' : 'var(--color-on-surface-dim)'}; margin-bottom: -2px;"
            onclick={() => activeListTab = tab.id as any}
          >
            {tab.label} ({tab.count})
          </button>
        {/each}
      </div>

      <!-- Dashboard Cards -->
      {#if loading}
        <div style="text-align: center; padding: 60px; font-size: 12px; color: var(--color-on-surface-dim);">Loading...</div>
      {:else if filteredDashboards.length === 0}
        <div style="text-align: center; padding: 60px;">
          <div style="font-size: 18px; font-weight: 900; margin-bottom: 8px;">
            {activeListTab === 'shared' ? 'NO SHARED DASHBOARDS' : activeListTab === 'favorites' ? 'NO FAVORITES' : 'NO DASHBOARDS YET'}
          </div>
          <div style="font-size: 12px; color: var(--color-on-surface-dim); margin-bottom: 20px;">
            Create a dashboard and pin charts from your chat conversations.
          </div>
          {#if activeListTab !== 'shared'}
            <button class="send-btn" style="font-size: 12px; padding: 10px 20px;" onclick={() => { showCreate = true; newDashProject = projects[0]?.slug || ''; }}>+ CREATE DASHBOARD</button>
          {/if}
        </div>
      {:else}
        <div style="display: grid; grid-template-columns: repeat(auto-fill, minmax(300px, 1fr)); gap: 16px;">
          {#each filteredDashboards as d}
            <div class="ink-border" style="background: var(--color-surface-bright); overflow: hidden;">
              <!-- Card content (clickable) -->
              <button style="width: 100%; text-align: left; background: none; border: none; cursor: pointer; padding: 20px; font-family: var(--font-family-display);" onclick={() => loadDashboard(d.id, d.project_slug)}>
                <!-- Project badge + shared status -->
                <div class="flex items-center gap-2" style="margin-bottom: 8px;">
                  <span style="font-size: 9px; padding: 2px 8px; background: var(--color-primary-container); border: 1px solid var(--color-on-surface); font-weight: 900; text-transform: uppercase; letter-spacing: 0.06em;">{d.project_name || d.project_slug}</span>
                  {#if !d.is_owner}
                    <span style="font-size: 8px; padding: 1px 6px; background: var(--color-secondary); color: white; font-weight: 900; text-transform: uppercase;">SHARED</span>
                  {/if}
                </div>

                <!-- Dashboard name -->
                <div style="font-size: 16px; font-weight: 900; text-transform: uppercase; margin-bottom: 6px;">{d.name}</div>

                <!-- Creator -->
                <div style="font-size: 10px; color: var(--color-on-surface-dim); margin-bottom: 8px;">
                  Created by <strong>{d.creator || 'unknown'}</strong> · {timeAgo(d.created_at)}
                </div>

                <!-- Stats -->
                <div class="flex gap-3">
                  <div class="ink-border" style="padding: 6px 14px; background: var(--color-surface);">
                    <div style="font-size: 8px; text-transform: uppercase; color: var(--color-on-surface-dim); letter-spacing: 0.08em;">WIDGETS</div>
                    <div style="font-size: 18px; font-weight: 900;">{d.widget_count}</div>
                  </div>
                  <div class="ink-border" style="padding: 6px 14px; background: var(--color-surface);">
                    <div style="font-size: 8px; text-transform: uppercase; color: var(--color-on-surface-dim); letter-spacing: 0.08em;">UPDATED</div>
                    <div style="font-size: 12px; font-weight: 700;">{timeAgo(d.updated_at)}</div>
                  </div>
                </div>
              </button>

              <!-- Card Actions -->
              <div style="display: flex; border-top: 2px solid var(--color-on-surface);">
                <button onclick={() => loadDashboard(d.id, d.project_slug)} style="flex: 1; padding: 10px; text-align: center; font-size: 11px; font-weight: 900; text-transform: uppercase; letter-spacing: 0.08em; background: var(--color-primary-container); border: none; border-right: 2px solid var(--color-on-surface); cursor: pointer; font-family: var(--font-family-display); color: var(--color-on-surface);">
                  OPEN
                </button>
                <button onclick={async () => {
                  try {
                    const res = await fetch(`/api/projects/${d.project_slug}/dashboards/${d.id}`, { headers: _h() });
                    if (res.ok) {
                      const full = await res.json();
                      const s = (full.widgets || []).map((w: any) => ({ title: w.title || '', content: w.content || '', headers: w.headers || [], rows: w.rows || [] }));
                      const pptxRes = await fetch('/api/export/pptx', { method: 'POST', headers: { ..._h(), 'Content-Type': 'application/json' }, body: JSON.stringify({ title: d.name, slides: s }) });
                      if (pptxRes.ok) { const blob = await pptxRes.blob(); const url = URL.createObjectURL(blob); const a = document.createElement('a'); a.href = url; a.download = `${d.name}.pptx`; a.click(); URL.revokeObjectURL(url); }
                    }
                  } catch {}
                }} style="flex: 1; padding: 10px; text-align: center; font-size: 11px; font-weight: 900; text-transform: uppercase; letter-spacing: 0.08em; background: none; border: none; border-right: 2px solid var(--color-on-surface); cursor: pointer; font-family: var(--font-family-display); color: var(--color-on-surface);">
                  EXPORT
                </button>
                {#if d.is_owner}
                  <button onclick={() => { deleteTarget = d; deleteTypedName = ''; }} style="padding: 10px 14px; background: none; border: none; cursor: pointer; color: var(--color-error); font-size: 11px; font-weight: 900;">
                    ✕
                  </button>
                {/if}
              </div>
            </div>
          {/each}
        </div>
      {/if}
    </div>

  {:else}
    <!-- ═══ DASHBOARD DETAIL ═══ -->
    <div class="dark-title-bar flex items-center justify-between" style="padding: 10px 20px;">
      <div class="flex items-center gap-3">
        <button onclick={goBack} style="background: none; border: none; cursor: pointer; color: var(--color-surface); font-size: 14px;">&larr;</button>
        <span style="font-size: 14px; font-weight: 900; letter-spacing: 0.05em;">{activeDashboard?.name || 'DASHBOARD'}</span>
        <span style="font-size: 10px; opacity: 0.6;">{activeDashboard?.widgets?.length || 0} widgets</span>
      </div>
      <div class="flex items-center gap-2">
        <button class="header-btn" style="font-size: 9px; padding: 4px 10px;" onclick={async () => {
          if (!activeDashboard?.widgets?.length) return;
          const slides = activeDashboard.widgets.map((w: any) => ({ title: w.title || '', content: w.content || '', headers: w.headers || [], rows: w.rows || [] }));
          try { const res = await fetch('/api/export/pptx', { method: 'POST', headers: { ..._h(), 'Content-Type': 'application/json' }, body: JSON.stringify({ title: activeDashboard.name, slides }) }); if (res.ok) { const blob = await res.blob(); const url = URL.createObjectURL(blob); const a = document.createElement('a'); a.href = url; a.download = `${activeDashboard.name}.pptx`; a.click(); URL.revokeObjectURL(url); } } catch {}
        }}>EXPORT PPTX</button>
        <button class="header-btn" style="font-size: 9px; padding: 4px 10px;" onclick={() => editMode = !editMode}>{editMode ? 'DONE' : 'EDIT'}</button>
      </div>
    </div>

    <div style="flex: 1; padding: 20px; overflow-y: auto;">
      {#if activeDashboard?.widgets?.length > 0}
        <div class="dashboard-grid">
          {#each activeDashboard.widgets as widget, wi}
            <div class="ink-border" class:widget-full={widget.full || widget.type === 'text'} style="background: var(--color-surface-bright); overflow: hidden;">
              <div class="flex items-center justify-between" style="padding: 8px 14px; border-bottom: 2px solid var(--color-on-surface); background: var(--color-on-surface); color: var(--color-surface);">
                <span style="font-size: 11px; font-weight: 900; text-transform: uppercase;">{widget.title}</span>
                <div class="flex items-center gap-2">
                  <span style="font-size: 8px; padding: 1px 6px; background: var(--color-primary); color: white; font-weight: 900;">{widget.type?.toUpperCase()}</span>
                  {#if editMode}<button onclick={() => removeWidget(widget.id)} style="background: none; border: none; cursor: pointer; color: var(--color-error); font-size: 14px; font-weight: 900;">✕</button>{/if}
                </div>
              </div>
              <div style="padding: 14px;">
                {#if widget.type === 'chart' && widget.headers && widget.rows}
                  <div class="flex gap-0 mb-2">
                    {#each ['bar', 'line', 'pie', 'scatter', 'area'] as ct}
                      <button class="chart-type-btn" class:chart-type-btn-active={(widget.chartType || 'bar') === ct} onclick={() => { const w = [...activeDashboard.widgets]; w[wi] = { ...w[wi], chartType: ct }; activeDashboard = { ...activeDashboard, widgets: w }; }}>{ct.toUpperCase()}</button>
                    {/each}
                  </div>
                  <div style="height: 280px;"><EChartView headers={widget.headers} rows={widget.rows} chartType={widget.chartType || 'bar'} /></div>
                  <details style="margin-top: 8px;">
                    <summary style="font-size: 9px; font-weight: 700; text-transform: uppercase; cursor: pointer; color: var(--color-on-surface-dim);">VIEW DATA ({widget.rows?.length} rows)</summary>
                    <div style="overflow-x: auto; margin-top: 6px;"><table class="data-table" style="font-size: 10px;"><thead><tr>{#each widget.headers as h}<th style="padding: 4px 8px;">{h}</th>{/each}</tr></thead><tbody>{#each widget.rows as row}<tr>{#each row as cell}<td style="padding: 3px 8px;">{cell}</td>{/each}</tr>{/each}</tbody></table></div>
                  </details>
                {:else if widget.type === 'metric'}
                  <div style="text-align: center; padding: 20px;"><div style="font-size: 36px; font-weight: 900; color: var(--color-primary);">{widget.content || '0'}</div></div>
                {:else}
                  <div class="prose-chat">{@html markdownToHtml(widget.content || '')}</div>
                {/if}
              </div>
            </div>
          {/each}
        </div>
      {:else}
        <div style="text-align: center; padding: 60px; color: var(--color-on-surface-dim);">
          <div style="font-size: 18px; font-weight: 900; margin-bottom: 8px;">EMPTY DASHBOARD</div>
          <div style="font-size: 12px;">Go to chat and click PIN on any response to add widgets.</div>
        </div>
      {/if}
      {#if editMode}
        <div style="margin-top: 20px; text-align: center;"><button class="feedback-btn" style="font-size: 10px; padding: 6px 14px; color: var(--color-error); border-color: var(--color-error);" onclick={deleteDashboard}>DELETE THIS DASHBOARD</button></div>
      {/if}
    </div>
  {/if}
</div>

<!-- Delete confirmation modal -->
{#if deleteTarget}
  <!-- svelte-ignore a11y_no_static_element_interactions -->
  <div style="position: fixed; inset: 0; background: rgba(0,0,0,0.5); z-index: 200; display: flex; align-items: center; justify-content: center;" onclick={(e) => { if (e.target === e.currentTarget) deleteTarget = null; }}>
    <div class="ink-border stamp-shadow" style="background: var(--color-surface); width: 400px;">
      <div style="background: var(--color-error); color: white; padding: 10px 14px; font-size: 11px; font-weight: 900; text-transform: uppercase; letter-spacing: 0.08em; font-family: var(--font-family-display);">DELETE DASHBOARD</div>
      <div style="padding: 20px;">
        <div style="font-size: 13px; margin-bottom: 16px; line-height: 1.5;">
          This will permanently delete <strong>"{deleteTarget.name}"</strong> and all its widgets. This action cannot be undone.
        </div>
        <div style="font-size: 9px; font-weight: 700; text-transform: uppercase; margin-bottom: 4px; color: var(--color-on-surface-dim);">TYPE THE DASHBOARD NAME TO CONFIRM</div>
        <input type="text" bind:value={deleteTypedName} placeholder={deleteTarget.name} style="width: 100%; border: 2px solid {deleteTypedName === deleteTarget.name ? 'var(--color-error)' : 'var(--color-on-surface)'}; padding: 8px 12px; font-family: var(--font-family-display); font-size: 12px; background: var(--color-surface); margin-bottom: 14px;" />
        <div class="flex gap-2">
          <button disabled={deleteTypedName !== deleteTarget.name} onclick={async () => {
            await fetch(`/api/projects/${deleteTarget.project_slug}/dashboards/${deleteTarget.id}`, { method: 'DELETE', headers: _h() });
            deleteTarget = null; deleteTypedName = ''; await loadDashboards();
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

<!-- Create modal -->
{#if showCreate}
  <!-- svelte-ignore a11y_no_static_element_interactions -->
  <div style="position: fixed; inset: 0; background: rgba(0,0,0,0.5); z-index: 200; display: flex; align-items: center; justify-content: center;" onclick={(e) => { if (e.target === e.currentTarget) showCreate = false; }}>
    <div class="ink-border stamp-shadow" style="background: var(--color-surface); width: 380px;">
      <div class="dark-title-bar" style="padding: 8px 14px; font-size: 11px;">CREATE DASHBOARD</div>
      <div style="padding: 16px;">
        <div style="font-size: 9px; font-weight: 700; text-transform: uppercase; margin-bottom: 3px;">DASHBOARD NAME</div>
        <input type="text" bind:value={newDashName} placeholder="e.g. Sales Overview, Weekly Report..." style="width: 100%; border: 2px solid var(--color-on-surface); padding: 8px 12px; font-family: var(--font-family-display); font-size: 12px; background: var(--color-surface); margin-bottom: 12px;" />
        <div style="font-size: 9px; font-weight: 700; text-transform: uppercase; margin-bottom: 3px;">PROJECT</div>
        <select bind:value={newDashProject} style="width: 100%; border: 2px solid var(--color-on-surface); padding: 8px 12px; font-family: var(--font-family-display); font-size: 12px; background: var(--color-surface); margin-bottom: 14px;">
          {#each projects as p}<option value={p.slug}>{p.agent_name || p.name}</option>{/each}
        </select>
        <div class="flex gap-2">
          <button class="send-btn" onclick={createDashboard} style="flex: 1; padding: 8px; font-size: 11px; justify-content: center; display: flex;">CREATE</button>
          <button class="feedback-btn" onclick={() => showCreate = false} style="flex: 1; padding: 8px; font-size: 11px; justify-content: center; display: flex; font-weight: 700;">CANCEL</button>
        </div>
      </div>
    </div>
  </div>
{/if}
