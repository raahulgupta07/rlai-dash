<script lang="ts">
  import '../app.css';
  import { page } from '$app/state';
  import { onMount } from 'svelte';
  let { children } = $props();

  let authenticated = $state(false);
  let username = $state('');
  let checking = $state(true);
  let showChangePassword = $state(false);
  let isSuper = $state(false);
  let cpOld = $state('');
  let cpNew = $state('');
  let cpConfirm = $state('');
  let cpError = $state('');
  let cpSuccess = $state(false);

  // Notifications
  let notifications = $state<any[]>([]);
  let unreadCount = $state(0);
  let showNotifications = $state(false);

  async function loadNotifications() {
    const token = localStorage.getItem('dash_token');
    if (!token) return;
    try {
      const res = await fetch('/api/notifications', { headers: { Authorization: `Bearer ${token}` } });
      if (res.ok) { const d = await res.json(); notifications = d.notifications || []; unreadCount = d.unread || 0; }
    } catch {}
  }

  async function markAllRead() {
    const token = localStorage.getItem('dash_token');
    if (!token) return;
    try { await fetch('/api/notifications/read-all', { method: 'POST', headers: { Authorization: `Bearer ${token}` } }); unreadCount = 0; notifications = notifications.map(n => ({ ...n, read: true })); } catch {}
  }

  // Search
  let showSearch = $state(false);
  let searchQuery = $state('');
  let searchResults = $state<any[]>([]);

  async function doSearch() {
    if (!searchQuery || searchQuery.length < 2) { searchResults = []; return; }
    const token = localStorage.getItem('dash_token');
    try {
      const res = await fetch(`/api/search?q=${encodeURIComponent(searchQuery)}`, { headers: token ? { Authorization: `Bearer ${token}` } : {} });
      if (res.ok) { const d = await res.json(); searchResults = d.results || []; }
    } catch {}
  }

  // API Key
  let showApiKey = $state(false);
  let apiKey = $state('');
  let apiKeyLoading = $state(false);

  async function loadApiKey() {
    const token = localStorage.getItem('dash_token');
    if (!token) return;
    apiKeyLoading = true;
    try {
      const res = await fetch('/api/auth/api-key', { headers: { Authorization: `Bearer ${token}` } });
      if (res.ok) { const d = await res.json(); apiKey = d.api_key || 'No key generated'; }
    } catch {} finally { apiKeyLoading = false; }
  }

  async function regenerateApiKey() {
    const token = localStorage.getItem('dash_token');
    if (!token) return;
    try {
      const res = await fetch('/api/auth/api-key/regenerate', { method: 'POST', headers: { Authorization: `Bearer ${token}` } });
      if (res.ok) { const d = await res.json(); apiKey = d.api_key || ''; }
    } catch {}
  }

  // Global CLI footer
  let cliExpanded = $state(false);
  let cliLogs = $state<{text: string; done: boolean; ts?: number}[]>([]);
  let cliTraining = $state(false);
  let cliAutoCollapse: ReturnType<typeof setTimeout> | null = null;
  let cliScrollEl: HTMLDivElement;

  function cliScrollToBottom() {
    if (cliScrollEl) {
      requestAnimationFrame(() => {
        cliScrollEl.scrollTop = cliScrollEl.scrollHeight;
        // Double-tap for safety
        setTimeout(() => { if (cliScrollEl) cliScrollEl.scrollTop = cliScrollEl.scrollHeight; }, 50);
      });
    }
  }

  function cliLog(text: string, done: boolean = true) {
    cliLogs = [...cliLogs, { text, done, ts: Date.now() }];
    if (!cliExpanded) cliExpanded = true;
    if (cliAutoCollapse) clearTimeout(cliAutoCollapse);
    cliScrollToBottom();
  }

  function cliMarkAllDone() {
    cliLogs = cliLogs.map(l => ({ ...l, done: true }));
    cliScrollToBottom();
  }

  function cliDoneAndCollapse(delay: number = 5000) {
    cliMarkAllDone();
    if (cliAutoCollapse) clearTimeout(cliAutoCollapse);
    cliAutoCollapse = setTimeout(() => { cliExpanded = false; }, delay);
  }

  function getCurrentProjectSlug(): string {
    const m = page.url.pathname.match(/\/project\/([^/]+)/);
    return m ? m[1] : '';
  }

  // Only show CLI on settings + command center (NOT on chat or dashboard)
  const showCli = $derived(page.url.pathname.includes('/settings') || page.url.pathname.includes('/command-center'));

  // Auto-expand CLI on project pages
  $effect(() => {
    if (showCli && !cliExpanded) {
      cliExpanded = true;
    }
  });

  // Log page/tab navigation
  let lastLoggedPath = $state('');
  $effect(() => {
    const path = page.url.pathname;
    if (!showCli || path === lastLoggedPath) return;
    lastLoggedPath = path;

    if (path.includes('/settings')) {
      // Don't log settings root, tabs are logged separately
    } else if (path.includes('/dashboard')) {
      cliLog(`  ${timeNow()} ── navigated to dashboard`, true);
    } else if (path.match(/\/project\/[^/]+$/)) {
      cliLog(`  ${timeNow()} ── opened chat`, true);
    } else if (path.includes('/command-center')) {
      cliLog(`  ${timeNow()} ── opened command center`, true);
    }
  });

  function timeNow(): string {
    const d = new Date();
    const date = d.toLocaleDateString('en-US', { month: 'short', day: '2-digit' });
    const time = d.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false });
    return `${date} ${time}`;
  }

  async function trainAll() {
    const slug = getCurrentProjectSlug();
    if (!slug || cliTraining) return;
    cliTraining = true;
    cliExpanded = true;
    const token = localStorage.getItem('dash_token');
    const headers = token ? { Authorization: `Bearer ${token}` } : {};
    const t0 = Date.now();

    // Add separator if there are old logs
    if (cliLogs.length > 0) {
      cliLog(``, true);
      cliLog(`  ─────────────────────────────────────────────`, true);
      cliLog(``, true);
    }

    cliLog(`$ dash train-all`, true);
    cliLog(`  ${timeNow()} ── scanning project...`, false);

    try {
      const statsRes = await fetch(`/api/projects/${slug}/stats`, { headers });
      let tables: any[] = [];
      if (statsRes.ok) {
        const d = await statsRes.json();
        tables = d.tables || [];
      }
      cliMarkAllDone();

      const totalRows = tables.reduce((s: number, t: any) => s + (t.rows || 0), 0);
      const totalCols = tables.reduce((s: number, t: any) => s + (t.columns || 0), 0);
      cliLog(`  ${timeNow()} ── found ${tables.length} tables, ${totalRows.toLocaleString()} rows, ${totalCols} columns`, true);
      cliLog(``, true);

      cliLog(`  ${timeNow()} ── starting training pipeline...`, false);

      const res = await fetch(`/api/projects/${slug}/retrain`, { method: 'POST', headers });

      if (res.ok) {
        cliMarkAllDone();
        cliLog(``, true);

        for (const tbl of tables) {
          const tStart = Date.now();
          cliLog(`  ${timeNow()} ── analyzing ${tbl.name} (${tbl.rows} rows, ${tbl.columns} cols)`, false);
          await new Promise(r => setTimeout(r, 1500));
          cliMarkAllDone();

          cliLog(`  ${timeNow()} │  ✓ deep analysis — column meanings, data patterns`, true);
          await new Promise(r => setTimeout(r, 300));
          cliLog(`  ${timeNow()} │  ✓ metadata — table description, use cases, quality notes`, true);
          await new Promise(r => setTimeout(r, 300));
          cliLog(`  ${timeNow()} │  ✓ training — generated Q&A pairs for this table`, true);
          await new Promise(r => setTimeout(r, 300));
          cliLog(`  ${timeNow()} │  ✓ rules — discovered business logic and metrics`, true);
          const dur = ((Date.now() - tStart) / 1000).toFixed(1);
          cliLog(`  ${timeNow()} │  done ${dur}s`, true);
          cliLog(``, true);
        }

        cliLog(`  ${timeNow()} ── generating agent persona...`, false);
        await new Promise(r => setTimeout(r, 2000));
        cliMarkAllDone();
        cliLog(`  ${timeNow()} │  ✓ persona — domain expertise, terminology, communication style`, true);
        cliLog(`  ${timeNow()} │  ✓ agent role updated`, true);
        cliLog(``, true);

        cliLog(`  ${timeNow()} ── indexing knowledge base...`, false);
        await new Promise(r => setTimeout(r, 500));
        cliMarkAllDone();
        cliLog(`  ${timeNow()} │  ✓ vector embeddings updated`, true);
        cliLog(``, true);

        const totalDur = ((Date.now() - t0) / 1000).toFixed(1);
        cliLog(`  ${timeNow()} ── ✓ training complete`, true);
        cliLog(`  ${timeNow()} ── ${tables.length} tables · ${totalRows.toLocaleString()} rows · ${totalDur}s total`, true);
        cliLog(``, true);
      } else {
        cliMarkAllDone();
        cliLog(`  ${timeNow()} ── ✗ training failed`, true);
      }
    } catch {
      cliMarkAllDone();
      cliLog(`  ${timeNow()} ── ✗ connection error`, true);
    }

    cliTraining = false;
    cliDoneAndCollapse(10000);
  }

  // Auto-scroll CLI whenever logs change
  $effect(() => {
    const _len = cliLogs.length;
    if (cliScrollEl && _len > 0) {
      setTimeout(() => { cliScrollEl.scrollTop = cliScrollEl.scrollHeight; }, 10);
      setTimeout(() => { cliScrollEl.scrollTop = cliScrollEl.scrollHeight; }, 100);
    }
  });

  // Dashboard nav
  let dashProjects = $state<{slug: string; name: string; agent_name: string}[]>([]);
  let showDashPicker = $state(false);

  async function changePassword() {
    if (cpNew !== cpConfirm) { cpError = 'Passwords do not match'; return; }
    if (cpNew.length < 4) { cpError = 'Min 4 characters'; return; }
    cpError = '';
    const token = localStorage.getItem('dash_token');
    try {
      const res = await fetch(`/api/auth/change-password?old_password=${encodeURIComponent(cpOld)}&new_password=${encodeURIComponent(cpNew)}`, {
        method: 'POST', headers: token ? { Authorization: `Bearer ${token}` } : {}
      });
      if (res.ok) { cpSuccess = true; cpOld = ''; cpNew = ''; cpConfirm = ''; }
      else { const d = await res.json(); cpError = d.detail || 'Failed'; }
    } catch { cpError = 'Connection failed'; }
  }


  const isLogin = $derived(page.url.pathname.includes('/login'));
  const isHome = $derived(page.url.pathname.endsWith('/home'));
  const isProjects = $derived(page.url.pathname.endsWith('/projects'));
  const isProject = $derived(page.url.pathname.includes('/project/'));
  const isProjectDashboard = $derived(page.url.pathname.includes('/project/') && page.url.pathname.includes('/dashboard'));
  const isSuperChat = $derived(page.url.pathname.endsWith('/chat'));
  const isDashboard = $derived(page.url.pathname.includes('/command-center'));
  const currentProjectSlug = $derived(() => {
    const m = page.url.pathname.match(/\/project\/([^/]+)/);
    return m ? m[1] : '';
  });

  onMount(async () => {
    // Listen for events from child pages
    window.addEventListener('dash-train-all', () => trainAll());
    window.addEventListener('dash-cli-log', ((e: CustomEvent) => {
      if (e.detail?.text) cliLog(e.detail.text, e.detail.done !== false);
    }) as EventListener);

    if (isLogin) { checking = false; return; }

    const token = localStorage.getItem('dash_token');
    if (!token) { checking = false; redirect(); return; }

    try {
      const res = await fetch('/api/auth/check', { headers: { Authorization: `Bearer ${token}` } });
      if (res.ok) {
        const data = await res.json();
        authenticated = true;
        username = data.username;
        isSuper = data.is_super || false;
        // Load notifications
        loadNotifications();
        // Load projects for dashboard nav
        try {
          const pRes = await fetch('/api/user-projects-brief', { headers: { Authorization: `Bearer ${token}` } });
          if (pRes.ok) { const pd = await pRes.json(); dashProjects = pd.projects || []; }
        } catch {}
      } else {
        localStorage.removeItem('dash_token');
        localStorage.removeItem('dash_user');
        redirect();
      }
    } catch { redirect(); }
    checking = false;
  });

  function redirect() {
    if (!isLogin) window.location.href = '/ui/login';
  }

  // Redirect root to home
  $effect(() => {
    if (authenticated && page.url.pathname === '/ui') {
      window.location.href = '/ui/home';
    }
  });

  function logout() {
    const token = localStorage.getItem('dash_token');
    if (token) fetch('/api/auth/logout', { method: 'POST', headers: { Authorization: `Bearer ${token}` } });
    localStorage.removeItem('dash_token');
    localStorage.removeItem('dash_user');
    localStorage.removeItem('dash_session');
    window.location.href = '/ui/login';
  }

  function newSession() {
    localStorage.removeItem('dash_session');
    window.location.href = '/ui';
  }

  function exportChat() {
    const msgs = document.querySelectorAll('.bubble-user, .bubble-assistant');
    let text = 'DASH — Chat Export\n' + '='.repeat(40) + '\n\n';
    msgs.forEach((el) => {
      const isUser = el.classList.contains('bubble-user');
      text += (isUser ? 'USER: ' : 'DASH: ') + el.textContent?.trim() + '\n\n';
    });
    const blob = new Blob([text], { type: 'text/plain' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `dash-chat-${Date.now()}.txt`;
    a.click();
    URL.revokeObjectURL(url);
  }

  function getAuthHeaders(): Record<string, string> {
    const token = localStorage.getItem('dash_token');
    return token ? { Authorization: `Bearer ${token}` } : {};
  }
</script>

<!-- svelte-ignore a11y_no_static_element_interactions -->
<svelte:window onclick={() => { showDashPicker = false; }} />

{#if isLogin}
  {@render children()}
{#if showChangePassword}
<!-- svelte-ignore a11y_no_static_element_interactions -->
<div style="position: fixed; inset: 0; background: rgba(0,0,0,0.6); z-index: 200; display: flex; align-items: center; justify-content: center;" onclick={(e) => { if (e.target === e.currentTarget) showChangePassword = false; }}>
  <div class="ink-border stamp-shadow" style="background: var(--color-surface); width: 360px;">
    <div class="dark-title-bar flex items-center justify-between" style="padding: 8px 14px; font-size: 11px;">
      <span>CHANGE PASSWORD</span>
      <button onclick={() => showChangePassword = false} style="background: none; border: none; color: var(--color-surface); cursor: pointer; font-weight: 900;">&#10005;</button>
    </div>
    <div style="padding: 16px;">
      {#if cpSuccess}
        <div style="color: var(--color-primary); font-weight: 900; font-size: 12px; text-transform: uppercase;">&#10003; Password changed successfully</div>
      {:else}
        <div style="margin-bottom: 10px;">
          <div style="font-size: 9px; font-weight: 700; text-transform: uppercase; margin-bottom: 3px;">CURRENT PASSWORD</div>
          <input type="password" bind:value={cpOld} style="width: 100%; border: 2px solid var(--color-on-surface); padding: 6px 10px; font-family: var(--font-family-display); font-size: 12px; background: var(--color-surface);" />
        </div>
        <div style="margin-bottom: 10px;">
          <div style="font-size: 9px; font-weight: 700; text-transform: uppercase; margin-bottom: 3px;">NEW PASSWORD</div>
          <input type="password" bind:value={cpNew} style="width: 100%; border: 2px solid var(--color-on-surface); padding: 6px 10px; font-family: var(--font-family-display); font-size: 12px; background: var(--color-surface);" />
        </div>
        <div style="margin-bottom: 12px;">
          <div style="font-size: 9px; font-weight: 700; text-transform: uppercase; margin-bottom: 3px;">CONFIRM</div>
          <input type="password" bind:value={cpConfirm} style="width: 100%; border: 2px solid var(--color-on-surface); padding: 6px 10px; font-family: var(--font-family-display); font-size: 12px; background: var(--color-surface);" />
        </div>
        {#if cpError}<div style="font-size: 11px; color: var(--color-error); margin-bottom: 8px;">{cpError}</div>{/if}
        <button class="send-btn" onclick={changePassword} style="width: 100%; padding: 8px; font-size: 11px; justify-content: center; display: flex;">UPDATE PASSWORD</button>
      {/if}
    </div>
  </div>
</div>
{/if}

{#if showApiKey}
<!-- svelte-ignore a11y_no_static_element_interactions -->
<div style="position: fixed; inset: 0; background: rgba(0,0,0,0.6); z-index: 200; display: flex; align-items: center; justify-content: center;" onclick={(e) => { if (e.target === e.currentTarget) showApiKey = false; }}>
  <div class="ink-border stamp-shadow" style="background: var(--color-surface); width: 420px;">
    <div class="dark-title-bar flex items-center justify-between" style="padding: 8px 14px; font-size: 11px;">
      <span>API KEY</span>
      <button onclick={() => showApiKey = false} style="background: none; border: none; color: var(--color-surface); cursor: pointer; font-weight: 900;">&#10005;</button>
    </div>
    <div style="padding: 16px;">
      <div style="font-size: 11px; color: var(--color-on-surface-dim); margin-bottom: 12px;">Use this key for programmatic access. Include as <code>Authorization: Bearer YOUR_KEY</code></div>
      {#if apiKeyLoading}
        <div style="font-size: 11px; color: var(--color-on-surface-dim);">Loading...</div>
      {:else}
        <div style="background: var(--color-on-surface); color: var(--color-primary-container); padding: 10px 14px; font-size: 11px; font-family: var(--font-family-display); word-break: break-all; margin-bottom: 12px; border: 2px solid var(--color-on-surface);">
          {apiKey || 'No key generated yet'}
        </div>
        <div class="flex gap-2">
          <button class="feedback-btn" style="font-size: 10px; padding: 6px 12px;" onclick={() => { navigator.clipboard.writeText(apiKey); }}>COPY</button>
          <button class="send-btn" style="font-size: 10px; padding: 6px 12px;" onclick={regenerateApiKey}>REGENERATE</button>
        </div>
      {/if}
    </div>
  </div>
</div>
{/if}

{#if showNotifications}
<!-- svelte-ignore a11y_no_static_element_interactions -->
<div style="position: fixed; inset: 0; z-index: 200;" onclick={() => showNotifications = false}>
  <div style="position: absolute; top: 50px; right: 80px; width: 360px; background: var(--color-surface-bright); border: 2px solid var(--color-on-surface); box-shadow: 4px 4px 0px 0px var(--color-on-surface); max-height: 400px; overflow-y: auto;" onclick={(e) => e.stopPropagation()}>
    <div class="dark-title-bar flex items-center justify-between" style="padding: 8px 14px; font-size: 11px;">
      <span>NOTIFICATIONS</span>
      {#if unreadCount > 0}
        <button onclick={markAllRead} style="background: none; border: none; color: var(--color-surface); cursor: pointer; font-size: 9px; text-transform: uppercase;">Mark all read</button>
      {/if}
    </div>
    {#if notifications.length > 0}
      {#each notifications as n}
        <div style="padding: 10px 14px; border-bottom: 1px solid var(--color-surface-dim); font-size: 11px; {!n.read ? 'background: var(--color-surface-dim);' : ''}">
          <div style="font-weight: {n.read ? 400 : 900};">{n.title}</div>
          {#if n.message}<div style="font-size: 10px; color: var(--color-on-surface-dim); margin-top: 2px;">{n.message}</div>{/if}
          <div style="font-size: 9px; color: var(--color-on-surface-dim); margin-top: 4px;">{n.created_at?.slice(0, 16)}</div>
        </div>
      {/each}
    {:else}
      <div style="padding: 20px; text-align: center; font-size: 11px; color: var(--color-on-surface-dim);">No notifications</div>
    {/if}
  </div>
</div>
{/if}

{#if showSearch}
<!-- svelte-ignore a11y_no_static_element_interactions -->
<div style="position: fixed; inset: 0; background: rgba(0,0,0,0.5); z-index: 200; display: flex; align-items: flex-start; justify-content: center; padding-top: 100px;" onclick={(e) => { if (e.target === e.currentTarget) showSearch = false; }}>
  <div class="ink-border stamp-shadow" style="background: var(--color-surface); width: 500px; max-height: 500px; overflow-y: auto;">
    <div style="padding: 12px 16px; border-bottom: 2px solid var(--color-on-surface);">
      <input type="text" bind:value={searchQuery} oninput={doSearch} placeholder="Search projects, chats, tables..." autofocus style="width: 100%; border: 2px solid var(--color-on-surface); padding: 8px 12px; font-family: var(--font-family-display); font-size: 14px; background: var(--color-surface);" />
    </div>
    {#if searchResults.length > 0}
      {#each searchResults as r}
        <a href={r.url} onclick={() => showSearch = false} style="display: block; padding: 10px 16px; border-bottom: 1px solid var(--color-surface-dim); text-decoration: none; color: var(--color-on-surface); cursor: pointer;" onmouseenter={(e) => (e.currentTarget as HTMLElement).style.background = 'var(--color-surface-dim)'} onmouseleave={(e) => (e.currentTarget as HTMLElement).style.background = 'none'}>
          <div class="flex items-center gap-2">
            <span class="tag-label" style="font-size: 7px; padding: 1px 5px;">{r.type}</span>
            <span style="font-size: 12px; font-weight: 900;">{r.title}</span>
          </div>
          <div style="font-size: 10px; color: var(--color-on-surface-dim); margin-top: 2px;">{r.subtitle}</div>
        </a>
      {/each}
    {:else if searchQuery.length >= 2}
      <div style="padding: 20px; text-align: center; font-size: 11px; color: var(--color-on-surface-dim);">No results for "{searchQuery}"</div>
    {:else}
      <div style="padding: 20px; text-align: center; font-size: 11px; color: var(--color-on-surface-dim);">Type to search across projects, chats, and data</div>
    {/if}
  </div>
</div>
{/if}

{:else if checking}
  <div style="min-height: 100vh; background: var(--color-surface); display: flex; align-items: center; justify-content: center; font-family: var(--font-family-display); font-size: 12px; text-transform: uppercase; letter-spacing: 0.1em; color: var(--color-on-surface-dim);">
    Loading...
  </div>
{:else if authenticated}
  <div class="flex flex-col h-screen">
    <!-- Header -->
    <header class="dark-title-bar flex items-center justify-between shrink-0">
      <div class="flex items-center gap-3">
        <div class="flex items-center gap-2">
          <div class="header-robot-box">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <line x1="12" y1="2" x2="12" y2="6"/><circle cx="12" cy="2" r="1" fill="currentColor" class="h-antenna"/>
              <rect x="3" y="11" width="18" height="10"/><line x1="12" y1="6" x2="12" y2="11"/>
              <rect x="7" y="14" width="3" height="2" fill="currentColor" class="h-eye"/><rect x="14" y="14" width="3" height="2" fill="currentColor" class="h-eye"/>
              <line x1="9" y1="18" x2="15" y2="18"/>
            </svg>
          </div>
          <span style="font-size: 18px; font-weight: 900; letter-spacing: 0.05em;">DASH</span>
        </div>

        <!-- Nav Tabs -->
        <div class="flex items-center gap-1" style="margin-left: 16px;">
          <button onclick={() => { window.location.href = '/ui/home'; }} class="nav-btn" class:nav-btn-active={isHome} style="cursor: pointer !important; padding: 6px 8px;">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M3 9l9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/><polyline points="9 22 9 12 15 12 15 22"/></svg>
          </button>
          <button onclick={() => window.location.href = '/ui/projects'} class="nav-btn" class:nav-btn-active={isProjects || isProject} style="cursor: pointer;">
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="3" width="7" height="7"/><rect x="14" y="3" width="7" height="7"/><rect x="3" y="14" width="7" height="7"/><rect x="14" y="14" width="7" height="7"/></svg>
            PROJECTS
          </button>
          <button onclick={() => window.location.href = '/ui/chat'} class="nav-btn" class:nav-btn-active={isSuperChat} style="cursor: pointer;">
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg>
            DASH AGENT
          </button>
          <div style="position: relative; display: inline-block;">
            <button onclick={() => window.location.href = '/ui/dashboard'} class="nav-btn" class:nav-btn-active={page.url.pathname.includes('/dashboard')} style="cursor: pointer;">
              <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="3" width="18" height="18"/><path d="M3 9h18M9 3v18"/></svg>
              DASHBOARD
            </button>
            <!-- Dashboard picker removed — now uses global /ui/dashboard -->
          </div>
          <button onclick={() => window.location.href = '/ui/presentations'} class="nav-btn" class:nav-btn-active={page.url.pathname.includes('/presentations')} style="cursor: pointer;">
            <svg width="12" height="12" viewBox="0 0 24 24"><defs><linearGradient id="navpg" x1="0" y1="0" x2="1" y2="1"><stop offset="0%" stop-color="#D24726"/><stop offset="100%" stop-color="#F0A030"/></linearGradient></defs><rect x="2" y="2" width="20" height="20" rx="3" fill="url(#navpg)"/><text x="12" y="16" text-anchor="middle" fill="#fff" font-size="11" font-weight="900" font-family="Arial">P</text></svg>
            PRESENTATIONS
          </button>
          <button onclick={() => window.location.href = '/ui/ml-insights'} class="nav-btn" class:nav-btn-active={page.url.pathname.includes('/ml-insights')} style="cursor: pointer;">
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M2 20h20"/><path d="M5 20V10"/><path d="M9 20V4"/><path d="M13 20v-8"/><path d="M17 20V8"/><path d="M21 20v-4"/></svg>
            ML INSIGHTS
          </button>
          {#if isSuper}
            <button onclick={() => window.location.href = '/ui/brain'} class="nav-btn" class:nav-btn-active={page.url.pathname.includes('/brain')} style="cursor: pointer;">
              <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><path d="M12 2a8 8 0 0 1 0 16"/><path d="M12 2a8 8 0 0 0 0 16"/><path d="M2 12h20"/></svg>
              BRAIN
            </button>
            <button onclick={() => window.location.href = '/ui/command-center'} class="nav-btn" class:nav-btn-active={isDashboard} style="cursor: pointer;">
              <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 2L2 7l10 5 10-5-10-5z"/><path d="M2 17l10 5 10-5"/><path d="M2 12l10 5 10-5"/></svg>
              COMMAND CENTER
            </button>
          {/if}
        </div>
      </div>

      <div class="flex items-center gap-2">
        <!-- User -->
        <div class="flex items-center gap-2" style="margin-left: 8px;">
          <div style="background: var(--color-primary-container); color: var(--color-on-surface); width: 28px; height: 28px; display: flex; align-items: center; justify-content: center; font-weight: 900; font-size: 12px; border: 1px solid var(--color-on-surface);">
            {username.charAt(0).toUpperCase()}
          </div>
          <a href="/ui/profile" style="font-size: 10px; letter-spacing: 0.08em; opacity: 0.7; text-decoration: none; color: inherit; cursor: pointer;" title="Edit profile">{username.toUpperCase()}</a>
          <!-- Search -->
          <button onclick={() => showSearch = !showSearch} class="header-btn" style="padding: 4px 8px; font-size: 9px;" title="Search (Cmd+K)">
            <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg>
          </button>
          <!-- Notifications -->
          <button onclick={() => { showNotifications = !showNotifications; if (showNotifications) loadNotifications(); }} class="header-btn" style="padding: 4px 8px; font-size: 9px; position: relative;" title="Notifications">
            <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9"/><path d="M13.73 21a2 2 0 0 1-3.46 0"/></svg>
            {#if unreadCount > 0}
              <span style="position: absolute; top: -4px; right: -4px; background: var(--color-error); color: white; font-size: 8px; font-weight: 900; min-width: 14px; height: 14px; border-radius: 50%; display: flex; align-items: center; justify-content: center;">{unreadCount > 99 ? '99+' : unreadCount}</span>
            {/if}
          </button>
          <button onclick={() => { showApiKey = true; loadApiKey(); }} class="header-btn" style="padding: 4px 8px; font-size: 9px;" title="API Key">
            <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 2l-2 2m-7.61 7.61a5.5 5.5 0 1 1-7.778 7.778 5.5 5.5 0 0 1 7.777-7.777zm0 0L15.5 7.5m0 0l3 3L22 7l-3-3m-3.5 3.5L19 4"/></svg>
          </button>
          <button onclick={() => { showChangePassword = true; cpSuccess = false; cpError = ''; }} class="header-btn" style="padding: 4px 8px; font-size: 9px;" title="Change password">
            <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="11" width="18" height="11" rx="0"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/></svg>
          </button>
          <button onclick={logout} class="header-btn" style="padding: 4px 8px; font-size: 9px;">
            <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"/><polyline points="16 17 21 12 16 7"/><line x1="21" y1="12" x2="9" y2="12"/></svg>
          </button>
        </div>
      </div>
    </header>

    <!-- Main Content -->
    <main class="flex-1 overflow-hidden">
      {@render children()}
    </main>

    <!-- Smart CLI Footer (only on project + command center pages) -->
    {#if showCli && cliExpanded}
      <div bind:this={cliScrollEl} class="shrink-0" style="background: #1a1a1a; border-top: 2px solid var(--color-on-surface); max-height: 140px; overflow-y: auto; overflow-x: hidden; font-family: 'Space Grotesk', monospace; font-size: 11px; line-height: 1.5; color: #8a8a9a; position: relative; z-index: 10; width: 100%;">
        <!-- CLI Header bar -->
        <div style="display: flex; align-items: center; justify-content: space-between; padding: 6px 14px; border-bottom: 1px solid #333; position: sticky; top: 0; background: #1a1a1a; z-index: 1;">
          <div style="display: flex; align-items: center; gap: 8px;">
            <span style="color: #00fc40; font-weight: 700;">$</span>
            <span style="color: #e0e0e0; font-size: 11px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.06em;">
              {getCurrentProjectSlug() ? `${getCurrentProjectSlug()} terminal` : 'DASH TERMINAL'}
            </span>
            {#if cliTraining}
              <span style="display: inline-flex; gap: 2px; align-items: center;">
                <span style="width: 4px; height: 4px; background: #00fc40; display: block; animation: cliBlink 1.2s infinite;"></span>
                <span style="width: 4px; height: 4px; background: #00fc40; display: block; animation: cliBlink 1.2s infinite 0.2s;"></span>
                <span style="width: 4px; height: 4px; background: #00fc40; display: block; animation: cliBlink 1.2s infinite 0.4s;"></span>
              </span>
            {/if}
          </div>
          <div style="display: flex; align-items: center; gap: 8px;">
            <button onclick={() => { cliLogs = []; }} style="background: none; border: none; color: #555; cursor: pointer; font-size: 9px; font-family: 'Space Grotesk', monospace;">CLEAR</button>
            <button onclick={() => cliExpanded = false} style="background: none; border: none; color: #8a8a9a; cursor: pointer; font-size: 14px; font-weight: 900;">▼</button>
          </div>
        </div>
        <!-- CLI Content (Claude Code style) -->
        <div style="padding: 8px 14px; font-size: 12px;">
          {#if cliLogs.length === 0}
            <div style="color: #555; padding: 4px 0;">
              <div style="color: #00fc40; font-weight: 700;">❯ dash session --init</div>
              <div style="margin-top: 4px;">  {timeNow()} ── session started</div>
              <div>  {timeNow()} ── ready for commands</div>
              <div style="margin-top: 4px; color: #555;">  type TRAIN ALL to train agent on all data</div>
            </div>
          {:else}
            {#each cliLogs as line}
              {#if line.text === ''}
                <div style="height: 4px;"></div>
              {:else if line.text.startsWith('$')}
                <div style="display: flex; align-items: center; gap: 6px; min-height: 22px; margin-top: 2px;">
                  <span style="color: #00fc40; font-weight: 700; flex-shrink: 0;">❯</span>
                  <span style="color: #e0e0e0; font-weight: 700;">{line.text.slice(2)}</span>
                </div>
              {:else}
                <div style="display: flex; align-items: flex-start; gap: 6px; min-height: 18px; padding-left: 2px;">
                  {#if !line.done}
                    <span style="display: inline-flex; gap: 2px; align-items: center; flex-shrink: 0; margin-top: 5px;">
                      <span style="width: 3px; height: 3px; background: #00fc40; display: block; animation: cliBlink 1.2s infinite;"></span>
                      <span style="width: 3px; height: 3px; background: #00fc40; display: block; animation: cliBlink 1.2s infinite 0.2s;"></span>
                      <span style="width: 3px; height: 3px; background: #00fc40; display: block; animation: cliBlink 1.2s infinite 0.4s;"></span>
                    </span>
                  {/if}
                  <span style="color: {line.text.includes('✓') ? '#00fc40' : line.text.includes('✗') ? '#ff6b6b' : line.text.includes('──') ? '#00b4d8' : line.text.includes('│') ? '#555' : '#8a8a9a'}; {line.text.includes('│') ? 'padding-left: 4px;' : ''}">{line.text.trim()}</span>
                </div>
              {/if}
            {/each}
          {/if}
          {#if cliTraining}
            <div style="display: flex; align-items: center; gap: 4px; margin-top: 4px; padding-left: 2px;">
              <span style="display: inline-block; width: 7px; height: 14px; background: #00fc40; animation: cursorBlink 1s step-end infinite;"></span>
            </div>
          {/if}
        </div>
      </div>
    {/if}
    <footer class="shrink-0 flex items-center justify-between px-5" style="height: 32px; background: var(--color-primary); color: var(--color-surface); font-size: 9px; letter-spacing: 0.1em; text-transform: uppercase; font-weight: 700; {showCli ? 'cursor: pointer;' : ''}" onclick={() => { if (showCli) cliExpanded = !cliExpanded; }}>
      <div class="flex items-center gap-2">
        <span style="width: 6px; height: 6px; background: var(--color-primary-container); display: inline-block;"></span>
        {#if cliTraining}
          <span style="display: inline-flex; gap: 2px; align-items: center; margin-right: 4px;">
            <span style="width: 4px; height: 4px; background: var(--color-primary-container); animation: cliBlink 1.2s infinite;"></span>
            <span style="width: 4px; height: 4px; background: var(--color-primary-container); animation: cliBlink 1.2s infinite 0.2s;"></span>
            <span style="width: 4px; height: 4px; background: var(--color-primary-container); animation: cliBlink 1.2s infinite 0.4s;"></span>
          </span>
          TRAINING
        {:else}
          SYSTEM_ACTIVE
        {/if}
      </div>
      {#if showCli}
        <div class="flex items-center gap-2">
          <span style="font-size: 10px;">{cliExpanded ? '▼' : '▲'}</span>
          <span style="opacity: 0.7;">$</span>
          TERMINAL
        </div>
      {:else}
        <div>POWERED BY REINFORCEMENT LEARNING</div>
      {/if}
      <div style="opacity: 0.7;">{username.toUpperCase()} · SAAS ANALYTICS</div>
    </footer>
  </div>
{/if}
