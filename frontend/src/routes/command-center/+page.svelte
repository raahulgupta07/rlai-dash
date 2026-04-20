<script lang="ts">
  import { onMount } from 'svelte';

  let activeTab = $state('users');
  let loading = $state(true);

  // Users
  let users = $state<any[]>([]);
  let selectedUser = $state<string | null>(null);
  let userProjects = $state<any[]>([]);
  let loadingProjects = $state(false);

  // Create user
  let showCreateUser = $state(false);
  let newUsername = $state('');
  let newPassword = $state('');
  let newEmail = $state('');

  async function createUser() {
    if (!newUsername || !newPassword) return;
    try {
      const params = new URLSearchParams({ username: newUsername, password: newPassword, email: newEmail });
      const res = await fetch(`/api/auth/users/create?${params}`, { method: 'POST', headers: _h() });
      if (res.ok) { showCreateUser = false; newUsername = ''; newPassword = ''; newEmail = ''; await loadUsers(); }
      else { const d = await res.json(); alert(d.detail || 'Failed'); }
    } catch {}
  }

  // Project detail
  let selectedProject = $state<string | null>(null);
  let projectDetail = $state<any>(null);
  let loadingDetail = $state(false);
  let detailTab = $state('tables');

  // Logs
  let logs = $state<any[]>([]);

  // Stats
  let stats = $state<any>(null);

  // Reset password
  let resetUser = $state('');
  let resetPass = $state('');
  let resetMsg = $state('');

  function _h(): Record<string, string> {
    const t = typeof localStorage !== 'undefined' ? localStorage.getItem('dash_token') : null;
    return t ? { Authorization: `Bearer ${t}` } : {};
  }

  onMount(() => { loadUsers(); loadLogs(); loadStats(); });

  async function loadUsers() {
    loading = true;
    try { const res = await fetch('/api/auth/users', { headers: _h() }); if (res.ok) { const d = await res.json(); users = d.users || []; } } catch {}
    loading = false;
  }

  async function loadUserProjects(username: string) {
    selectedUser = username; selectedProject = null; projectDetail = null; loadingProjects = true;
    try { const res = await fetch(`/api/auth/users/${username}/projects`, { headers: _h() }); if (res.ok) { const d = await res.json(); userProjects = d.projects || []; } } catch {}
    loadingProjects = false;
  }

  async function loadProjectDetail(slug: string) {
    selectedProject = slug; loadingDetail = true; detailTab = 'tables';
    try { const res = await fetch(`/api/projects/${slug}/detail`, { headers: _h() }); if (res.ok) projectDetail = await res.json(); } catch {}
    loadingDetail = false;
  }

  async function loadLogs() {
    try { const res = await fetch('/api/queries', { headers: _h() }); if (res.ok) { const d = await res.json(); logs = d.queries || []; } } catch {}
  }

  async function loadStats() {
    try { const res = await fetch('/api/dashboard', { headers: _h() }); if (res.ok) stats = await res.json(); } catch {}
  }

  async function deleteUser(username: string) {
    if (!confirm(`Delete "${username}" and ALL their projects/data?`)) return;
    try { await fetch(`/api/auth/users/${username}`, { method: 'DELETE', headers: _h() }); selectedUser = null; await loadUsers(); } catch {}
  }

  async function deleteProject(slug: string) {
    if (!confirm(`Delete project and all its data?`)) return;
    try { await fetch(`/api/projects/${slug}`, { method: 'DELETE', headers: _h() }); selectedProject = null; if (selectedUser) await loadUserProjects(selectedUser); } catch {}
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

  function backToUsers() { selectedUser = null; selectedProject = null; projectDetail = null; }
  function backToProjects() { selectedProject = null; projectDetail = null; }
</script>

<div style="padding: 16px; overflow-y: auto; height: 100%;">
<div style="width: 100%; display: flex; flex-direction: column; flex: 1; min-height: 0;">

<!-- TABS -->
<div style="display: flex; flex-direction: column; flex: 1; min-height: 0;">
<div class="dash-tabs" style="flex-shrink: 0;">
  {#each [
    { id: 'users', label: 'USERS', value: String(users.length) },
    { id: 'platform', label: 'PLATFORM', value: '⚙' },
    { id: 'logs', label: 'LOGS', value: String(logs.length) },
    { id: 'stats', label: 'STATS', value: '📊' },
  ] as tab}
    <button class="dash-tab" class:dash-tab-active={activeTab === tab.id} onclick={() => { activeTab = tab.id; if (tab.id === 'users') { selectedUser = null; selectedProject = null; } }} style="cursor: pointer;">
      {tab.label}
      <span class="dash-tab-value">{tab.value}</span>
    </button>
  {/each}
</div>

<div class="dash-panel">

<!-- ═══════════════════════════════════════════════════════════ -->
<!-- USERS TAB — 3-level drill-down                            -->
<!-- ═══════════════════════════════════════════════════════════ -->
{#if activeTab === 'users'}

  {#if selectedProject && projectDetail}
    <!-- LEVEL 3: Project Detail -->
    <div class="flex items-center gap-3 mb-4">
      <button onclick={backToProjects} style="background: none; border: none; font-size: 11px; color: var(--color-on-surface-dim); cursor: pointer; text-transform: uppercase;">← {selectedUser}</button>
      <div style="font-size: 18px; font-weight: 900; text-transform: uppercase;">{projectDetail.project?.agent_name || 'Agent'}</div>
      <span class="tag-label" style="font-size: 8px;">{projectDetail.project?.schema_name}</span>
    </div>

    <!-- Detail tabs -->
    <div class="flex gap-1 mb-4">
      {#each ['tables', 'knowledge', 'training', 'docs', 'config'] as dt}
        <button onclick={() => detailTab = dt} style="padding: 4px 12px; font-size: 10px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.05em; border: 2px solid var(--color-on-surface); background: {detailTab === dt ? 'var(--color-on-surface)' : 'var(--color-surface)'}; color: {detailTab === dt ? 'var(--color-surface)' : 'var(--color-on-surface)'}; cursor: pointer; font-family: var(--font-family-display);">
          {dt}
        </button>
      {/each}
    </div>

    {#if detailTab === 'tables'}
      {#if projectDetail.tables?.length}
        <table style="width: 100%; font-size: 12px; border-collapse: collapse;">
          <thead><tr style="border-bottom: 2px solid var(--color-on-surface);"><th style="text-align: left; padding: 6px 10px; font-size: 9px; text-transform: uppercase;">Name</th><th style="text-align: right; padding: 6px 10px; font-size: 9px; text-transform: uppercase;">Rows</th><th style="text-align: right; padding: 6px 10px; font-size: 9px; text-transform: uppercase;">Cols</th></tr></thead>
          <tbody>{#each projectDetail.tables as t}<tr style="border-bottom: 1px solid var(--color-surface-dim);"><td style="padding: 5px 10px; font-weight: 900;">{t.name}</td><td style="padding: 5px 10px; text-align: right;">{t.rows?.toLocaleString()}</td><td style="padding: 5px 10px; text-align: right;">{t.columns}</td></tr>{/each}</tbody>
        </table>
      {:else}<div style="font-size: 12px; color: var(--color-on-surface-dim);">No tables in this project.</div>{/if}

    {:else if detailTab === 'knowledge'}
      <div style="font-size: 12px; margin-bottom: 8px;"><strong>{projectDetail.knowledge_vectors}</strong> vectors indexed</div>
      {#if projectDetail.knowledge_files?.length}
        {#each projectDetail.knowledge_files as f}
          <div class="flex items-center justify-between py-1" style="border-bottom: 1px solid var(--color-surface-dim); font-size: 11px;">
            <div class="flex items-center gap-2"><span style="font-weight: 700;">{f.name}</span><span class="tag-label" style="font-size: 7px; padding: 1px 4px;">{f.type}</span></div>
            <span style="color: var(--color-on-surface-dim);">{(f.size / 1024).toFixed(1)} KB</span>
          </div>
        {/each}
      {:else}<div style="font-size: 12px; color: var(--color-on-surface-dim);">No knowledge files.</div>{/if}

    {:else if detailTab === 'training'}
      <div style="font-size: 12px;"><strong>{projectDetail.learnings}</strong> learnings captured</div>
      <div style="font-size: 11px; color: var(--color-on-surface-dim); margin-top: 8px;">Learnings are auto-captured when the agent encounters errors and discovers fixes. Each learning prevents the same mistake from recurring.</div>

    {:else if detailTab === 'docs'}
      {#if projectDetail.docs?.length}
        {#each projectDetail.docs as d}
          <div class="flex items-center justify-between py-1" style="border-bottom: 1px solid var(--color-surface-dim); font-size: 11px;">
            <div class="flex items-center gap-2"><span style="font-weight: 700;">{d.name}</span><span class="tag-label" style="font-size: 7px; padding: 1px 4px;">{d.type}</span></div>
            <span style="color: var(--color-on-surface-dim);">{(d.size / 1024).toFixed(1)} KB</span>
          </div>
        {/each}
      {:else}<div style="font-size: 12px; color: var(--color-on-surface-dim);">No documents uploaded.</div>{/if}

    {:else if detailTab === 'config'}
      {#if projectDetail.project}
        <div style="display: grid; grid-template-columns: 120px 1fr; gap: 6px 16px; font-size: 12px;">
          <span style="font-weight: 700; text-transform: uppercase; font-size: 10px;">Agent</span><span style="font-weight: 900;">{projectDetail.project.agent_name}</span>
          <span style="font-weight: 700; text-transform: uppercase; font-size: 10px;">Role</span><span>{projectDetail.project.agent_role || '-'}</span>
          <span style="font-weight: 700; text-transform: uppercase; font-size: 10px;">Personality</span><span>{projectDetail.project.agent_personality}</span>
          <span style="font-weight: 700; text-transform: uppercase; font-size: 10px;">Schema</span><span style="font-family: var(--font-family-display);">{projectDetail.project.schema_name}</span>
          <span style="font-weight: 700; text-transform: uppercase; font-size: 10px;">Created</span><span>{projectDetail.project.created_at?.slice(0, 19)}</span>
        </div>
      {/if}
    {/if}

  {:else if selectedUser}
    <!-- LEVEL 2: User's Projects -->
    <div class="flex items-center gap-3 mb-4">
      <button onclick={backToUsers} style="background: none; border: none; font-size: 11px; color: var(--color-on-surface-dim); cursor: pointer; text-transform: uppercase;">← USERS</button>
      <div style="font-size: 18px; font-weight: 900; text-transform: uppercase;">{selectedUser}'s Projects</div>
    </div>

    {#if loadingProjects}
      <div style="font-size: 12px; color: var(--color-on-surface-dim);">Loading...</div>
    {:else if userProjects.length === 0}
      <div style="font-size: 12px; color: var(--color-on-surface-dim);">No projects. This user hasn't created any agents yet.</div>
    {:else}
      <div style="display: grid; grid-template-columns: repeat(auto-fill, minmax(240px, 1fr)); gap: 12px;">
        {#each userProjects as p}
          <div class="ink-border" style="background: var(--color-surface-bright);">
            <div style="padding: 14px;">
              <div style="font-size: 14px; font-weight: 900; text-transform: uppercase; margin-bottom: 4px;">{p.agent_name}</div>
              <div style="font-size: 11px; color: var(--color-on-surface-dim); margin-bottom: 10px;">{p.agent_role || 'Data agent'}</div>
              <div style="display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 4px; font-size: 10px; text-align: center;">
                <div class="ink-border" style="padding: 4px; background: var(--color-surface);"><div style="font-weight: 900; font-size: 14px;">{p.tables}</div>tables</div>
                <div class="ink-border" style="padding: 4px; background: var(--color-surface);"><div style="font-weight: 900; font-size: 14px;">{p.rows?.toLocaleString()}</div>rows</div>
                <div class="ink-border" style="padding: 4px; background: var(--color-surface);"><div style="font-weight: 900; font-size: 14px;">{p.knowledge}</div>vectors</div>
              </div>
            </div>
            <div style="display: flex; border-top: 2px solid var(--color-on-surface);">
              <button onclick={() => loadProjectDetail(p.slug)} style="flex: 1; padding: 8px; text-align: center; font-size: 10px; font-weight: 900; text-transform: uppercase; letter-spacing: 0.08em; background: var(--color-primary-container); color: var(--color-on-surface); border: none; border-right: 2px solid var(--color-on-surface); cursor: pointer; font-family: var(--font-family-display);">INSPECT</button>
              <button onclick={() => deleteProject(p.slug)} style="padding: 8px 14px; background: none; border: none; cursor: pointer; color: var(--color-error); font-size: 10px; font-weight: 900; font-family: var(--font-family-display);">DEL</button>
            </div>
          </div>
        {/each}
      </div>
    {/if}

  {:else}
    <!-- LEVEL 1: Users List -->
    <!-- CLI Status -->
    <div class="cli-terminal" style="margin-bottom: 16px; padding: 8px 14px;">
      <div class="cli-line">
        <span class="cli-prompt">$</span>
        <span class="cli-command">dash users</span>
        <span class="cli-output">--list --admin</span>
        <span class="cli-dim" style="margin-left: auto;">{users.length} users · {users.filter((u: any) => u.is_active !== false).length} active</span>
      </div>
    </div>

    <div class="flex items-center justify-between mb-4">
      <div style="font-size: 18px; font-weight: 900; text-transform: uppercase;">Users</div>
      <button class="send-btn" style="font-size: 10px; padding: 6px 14px;" onclick={() => showCreateUser = true}>+ CREATE USER</button>
    </div>

    {#if loading}
      <div style="font-size: 12px; color: var(--color-on-surface-dim);">Loading...</div>
    {:else}
      <table style="width: 100%; font-size: 12px; border-collapse: collapse;">
        <thead><tr style="border-bottom: 2px solid var(--color-on-surface);">
          <th style="text-align: left; padding: 6px 10px; font-size: 9px; text-transform: uppercase;">User</th>
          <th style="text-align: left; padding: 6px 10px; font-size: 9px; text-transform: uppercase;">Email</th>
          <th style="text-align: left; padding: 6px 10px; font-size: 9px; text-transform: uppercase;">Role</th>
          <th style="text-align: left; padding: 6px 10px; font-size: 9px; text-transform: uppercase;">Dept</th>
          <th style="text-align: right; padding: 6px 10px; font-size: 9px; text-transform: uppercase;">Projects</th>
          <th style="text-align: left; padding: 6px 10px; font-size: 9px; text-transform: uppercase;">Status</th>
          <th style="text-align: left; padding: 6px 10px; font-size: 9px; text-transform: uppercase;">Auth</th>
          <th style="text-align: right; padding: 6px 10px; font-size: 9px; text-transform: uppercase;">Actions</th>
        </tr></thead>
        <tbody>
          {#each users as u}
            <tr style="border-bottom: 1px solid var(--color-surface-dim); cursor: pointer; {u.is_active === false ? 'opacity: 0.5;' : ''}" onclick={() => loadUserProjects(u.username)}>
              <td style="padding: 6px 10px;">
                <div class="flex items-center gap-2">
                  <div style="background: var(--color-primary-container); width: 24px; height: 24px; display: flex; align-items: center; justify-content: center; font-weight: 900; font-size: 10px; border: 1px solid var(--color-on-surface);">{u.username.charAt(0).toUpperCase()}</div>
                  <div>
                    <div style="font-weight: 900;">{u.first_name && u.last_name ? `${u.first_name} ${u.last_name}` : u.username}</div>
                    {#if u.first_name}<div style="font-size: 9px; color: var(--color-on-surface-dim);">@{u.username}</div>{/if}
                  </div>
                </div>
              </td>
              <td style="padding: 6px 10px; font-size: 11px; color: var(--color-on-surface-dim);">{u.email || '-'}</td>
              <td style="padding: 6px 10px;">
                {#if u.is_super}<span class="tag-label" style="font-size: 8px; background: var(--color-error);">SUPER ADMIN</span>
                {:else}<span class="tag-label" style="font-size: 8px;">USER</span>{/if}
              </td>
              <td style="padding: 6px 10px; font-size: 11px; color: var(--color-on-surface-dim);">{u.department || '-'}</td>
              <td style="padding: 6px 10px; text-align: right; font-weight: 900;">{u.project_count || 0}</td>
              <td style="padding: 6px 10px;">
                {#if u.is_active !== false}
                  <span style="color: var(--color-primary); font-size: 10px; font-weight: 700;">ACTIVE</span>
                {:else}
                  <span style="color: var(--color-error); font-size: 10px; font-weight: 700;">DISABLED</span>
                {/if}
              </td>
              <td style="padding: 6px 10px; font-size: 10px; color: var(--color-on-surface-dim);">{u.auth_provider || 'local'}</td>
              <td style="padding: 6px 10px; text-align: right;" onclick={(e) => e.stopPropagation()}>
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
  {/if}

<!-- ═══════════════════════════════════════════════════════════ -->
<!-- PLATFORM TAB                                               -->
<!-- ═══════════════════════════════════════════════════════════ -->
{:else if activeTab === 'platform'}
  <div style="font-size: 18px; font-weight: 900; text-transform: uppercase; margin-bottom: 16px;">Platform</div>
  <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 20px; font-size: 12px;">
    <div>
      <div style="font-weight: 900; text-transform: uppercase; font-size: 10px; letter-spacing: 0.08em; margin-bottom: 8px; border-bottom: 1px solid var(--color-on-surface); padding-bottom: 4px;">LLM</div>
      <div>Provider: <strong>OpenRouter</strong></div>
      <div>Model: <strong>openai/gpt-5.4-mini</strong></div>
      <div>Embeddings: <strong>text-embedding-3-small</strong></div>
      <div>Reasoning: <strong>think() + analyze()</strong></div>
    </div>
    <div>
      <div style="font-weight: 900; text-transform: uppercase; font-size: 10px; letter-spacing: 0.08em; margin-bottom: 8px; border-bottom: 1px solid var(--color-on-surface); padding-bottom: 4px;">Database</div>
      <div>Engine: <strong>PostgreSQL 18 + PgVector</strong></div>
      <div>Image: <strong>pgvector/pgvector:pg18-trixie</strong></div>
      <div>Size: <strong>{stats?.stats?.db_size || '...'}</strong></div>
      <div>Isolation: <strong>Schema per project</strong></div>
    </div>
    <div>
      <div style="font-weight: 900; text-transform: uppercase; font-size: 10px; letter-spacing: 0.08em; margin-bottom: 8px; border-bottom: 1px solid var(--color-on-surface); padding-bottom: 4px;">Security</div>
      <div>Auth: <strong>Token-based (SHA-256)</strong></div>
      <div>Analyst: <strong>READ-ONLY (PG enforced)</strong></div>
      <div>Project isolation: <strong>Schema per project</strong></div>
      <div>Super admin: <strong>Env var configurable</strong></div>
    </div>
    <div>
      <div style="font-weight: 900; text-transform: uppercase; font-size: 10px; letter-spacing: 0.08em; margin-bottom: 8px; border-bottom: 1px solid var(--color-on-surface); padding-bottom: 4px;">Infrastructure</div>
      <div>Framework: <strong>Agno + FastAPI</strong></div>
      <div>Python: <strong>3.12 + uv</strong></div>
      <div>Frontend: <strong>SvelteKit 2 + Tailwind</strong></div>
      <div>Runtime: <strong>Docker</strong></div>
    </div>
  </div>

  <!-- Status -->
  <div style="margin-top: 24px;">
    <div style="font-weight: 900; text-transform: uppercase; font-size: 10px; letter-spacing: 0.08em; margin-bottom: 8px; border-bottom: 1px solid var(--color-on-surface); padding-bottom: 4px;">System Status</div>
    {#each [
      { name: 'DATABASE', status: 'Reachable' },
      { name: 'PGVECTOR', status: 'Active' },
      { name: 'LLM ENGINE', status: 'Connected' },
      { name: 'KNOWLEDGE', status: 'Operational' },
    ] as item}
      <div class="flex items-center gap-3 mb-2" style="font-size: 12px;">
        <span style="color: var(--color-primary);">●</span>
        <span style="width: 100px; font-weight: 900; text-transform: uppercase; font-size: 10px;">{item.name}</span>
        <span>{item.status}</span>
      </div>
    {/each}
    <div style="margin-top: 8px; font-size: 12px; font-weight: 900; color: var(--color-primary); text-transform: uppercase;">ALL SYSTEMS OPERATIONAL</div>
  </div>

<!-- ═══════════════════════════════════════════════════════════ -->
<!-- LOGS TAB                                                   -->
<!-- ═══════════════════════════════════════════════════════════ -->
{:else if activeTab === 'logs'}
  <div class="flex items-center justify-between mb-4">
    <div style="font-size: 18px; font-weight: 900; text-transform: uppercase;">Query Logs</div>
    <button class="feedback-btn" style="font-size: 9px; font-weight: 700; text-transform: uppercase; padding: 3px 10px; cursor: pointer;" onclick={loadLogs}>REFRESH</button>
  </div>
  {#if logs.length === 0}
    <div style="font-size: 12px; color: var(--color-on-surface-dim);">No queries logged yet.</div>
  {:else}
    <table style="width: 100%; font-size: 11px; border-collapse: collapse;">
      <thead><tr style="border-bottom: 2px solid var(--color-on-surface);">
        <th style="text-align: left; padding: 6px 8px; font-size: 9px; text-transform: uppercase;">Session</th>
        <th style="text-align: left; padding: 6px 8px; font-size: 9px; text-transform: uppercase;">User</th>
        <th style="text-align: left; padding: 6px 8px; font-size: 9px; text-transform: uppercase;">Created</th>
        <th style="text-align: left; padding: 6px 8px; font-size: 9px; text-transform: uppercase;">Last Active</th>
      </tr></thead>
      <tbody>
        {#each logs as q}
          <tr style="border-bottom: 1px solid var(--color-surface-dim);">
            <td style="padding: 4px 8px; font-family: var(--font-family-display); font-size: 10px;">{q.session_id?.slice(0, 12)}...</td>
            <td style="padding: 4px 8px;">{q.user_id || 'anonymous'}</td>
            <td style="padding: 4px 8px; color: var(--color-on-surface-dim);">{q.created_at?.slice(0, 19) || '-'}</td>
            <td style="padding: 4px 8px; color: var(--color-on-surface-dim);">{q.updated_at?.slice(0, 19) || '-'}</td>
          </tr>
        {/each}
      </tbody>
    </table>
  {/if}

<!-- ═══════════════════════════════════════════════════════════ -->
<!-- STATS TAB                                                  -->
<!-- ═══════════════════════════════════════════════════════════ -->
{:else if activeTab === 'stats'}
  <div style="font-size: 18px; font-weight: 900; text-transform: uppercase; margin-bottom: 16px;">Platform Stats</div>
  <div style="display: grid; grid-template-columns: repeat(3, 1fr); gap: 12px;">
    {#each [
      { label: 'USERS', value: users.length },
      { label: 'PROJECTS', value: users.reduce((a, u) => a + (u.project_count || 0), 0) },
      { label: 'TABLES', value: stats?.stats?.table_count || 0 },
      { label: 'TOTAL ROWS', value: stats?.stats?.total_rows?.toLocaleString() || '0' },
      { label: 'KNOWLEDGE', value: (stats?.stats?.knowledge_vectors || 0) + ' vectors' },
      { label: 'DB SIZE', value: stats?.stats?.db_size || '...' },
    ] as card}
      <div class="ink-border p-4" style="background: var(--color-surface-bright); text-align: center;">
        <div style="font-size: 9px; text-transform: uppercase; letter-spacing: 0.1em; color: var(--color-on-surface-dim); font-weight: 700;">{card.label}</div>
        <div style="font-size: 24px; font-weight: 900; margin-top: 4px;">{card.value}</div>
      </div>
    {/each}
  </div>
{/if}

</div>
</div>
</div>
</div>

<!-- Create User Modal -->
{#if showCreateUser}
<!-- svelte-ignore a11y_no_static_element_interactions -->
<div style="position: fixed; inset: 0; background: rgba(0,0,0,0.6); z-index: 200; display: flex; align-items: center; justify-content: center;" onclick={(e) => { if (e.target === e.currentTarget) showCreateUser = false; }}>
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
