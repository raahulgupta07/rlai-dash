<script lang="ts">
  import { onMount } from 'svelte';

  let projects = $state<any[]>([]);
  let username = $state('');
  let isSuper = $state(false);
  let loading = $state(true);
  let bootStep = $state(0);
  let bootDone = $state(false);

  function _h(): Record<string, string> {
    const t = typeof localStorage !== 'undefined' ? localStorage.getItem('dash_token') : null;
    return t ? { Authorization: `Bearer ${t}` } : {};
  }

  onMount(async () => {
    username = localStorage.getItem('dash_user') || '';

    // Animate boot
    for (let i = 1; i <= 7; i++) {
      bootStep = i;
      await new Promise(r => setTimeout(r, 180));
    }

    try {
      const [pRes, aRes] = await Promise.all([
        fetch('/api/projects', { headers: _h() }),
        fetch('/api/auth/check', { headers: _h() }),
      ]);
      if (pRes.ok) { const d = await pRes.json(); projects = d.projects || []; }
      if (aRes.ok) { const d = await aRes.json(); username = d.username || ''; isSuper = d.is_super || false; }
    } catch {}

    bootStep = 8;
    await new Promise(r => setTimeout(r, 200));
    bootStep = 9;
    loading = false;
    await new Promise(r => setTimeout(r, 300));
    bootDone = true;
  });

  const totalTables = $derived(projects.reduce((s, p) => s + (p.tables || 0), 0));
  const totalRows = $derived(projects.reduce((s, p) => s + (p.rows || 0), 0));
  const maxVal = $derived(Math.max(projects.length, totalTables, totalRows, 1));

  function timeNow(): string {
    const d = new Date();
    return `${d.toLocaleDateString('en-US', { month: 'short', day: '2-digit' })} ${d.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false })}`;
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

  function bar(val: number, max: number): string {
    const len = Math.max(1, Math.min(28, Math.round((val / Math.max(max, 1)) * 28)));
    return '█'.repeat(len) + '░'.repeat(28 - len);
  }
</script>

<div style="background: #1a1a1a; height: 100%; overflow-y: auto;">
  <div style="padding: 24px 32px; max-width: 1000px; margin: 0 auto; font-family: 'Space Grotesk', monospace; font-size: 12px; line-height: 1.6; color: #e0e0e0;">

      {#if !bootDone}
        <div style="color: #00fc40; font-weight: 700; margin-bottom: 4px;">[DASH] Access granted.</div>
        <div style="color: #8a8a9a; margin-bottom: 12px;">Welcome back, {username}.</div>
      {/if}

      <!-- Boot Steps (friendly, no secrets) -->
      {#if bootStep >= 1}<div style="color: #8a8a9a;">{bootStep >= 8 ? '✓' : '>'} Setting up your session...</div>{/if}
      {#if bootStep >= 2}<div style="color: #8a8a9a;">{bootStep >= 8 ? '✓' : '>'} Loading your data...</div>{/if}
      {#if bootStep >= 3}<div style="color: #8a8a9a;">{bootStep >= 8 ? '✓' : '>'} Waking up AI brain...</div>{/if}
      {#if bootStep >= 4}<div style="color: #8a8a9a;">{bootStep >= 8 ? '✓' : '>'} Preparing knowledge...</div>{/if}
      {#if bootStep >= 5}<div style="color: #8a8a9a;">{bootStep >= 8 ? '✓' : '>'} Loading your agents...</div>{/if}
      {#if bootStep >= 6}<div style="color: #8a8a9a;">{bootStep >= 8 ? '✓' : '>'} Almost there...</div>{/if}
      {#if bootStep >= 8}<div style="color: #00fc40; font-weight: 700; margin-top: 4px;">✓ Ready.</div>{/if}

      {#if !bootDone && bootStep < 8}
        <div style="margin-top: 12px; background: #333; height: 3px; max-width: 300px;">
          <div style="background: #00fc40; height: 100%; width: {Math.round((bootStep / 7) * 100)}%; transition: width 0.2s;"></div>
        </div>
        <div style="margin-top: 8px;">
          <span style="display: inline-block; width: 7px; height: 14px; background: #00fc40; animation: cursorBlink 1s step-end infinite;"></span>
        </div>
      {/if}

      <!-- Full Dashboard (appears after boot) -->
      {#if bootDone}
        <div style="margin-top: 16px; border-top: 1px solid #333; padding-top: 16px;">

          <!-- ASCII Logo -->
          <pre style="color: #00fc40; font-size: 9px; line-height: 1.1; margin: 0 0 4px 0; white-space: pre;"> ██████╗  █████╗ ███████╗██╗  ██╗
 ██╔══██╗██╔══██╗██╔════╝██║  ██║
 ██║  ██║███████║███████╗███████║
 ██║  ██║██╔══██║╚════██║██╔══██║
 ██████╔╝██║  ██║███████║██║  ██║
 ╚═════╝ ╚═╝  ╚═╝╚══════╝╚═╝  ╚═╝</pre>
          <div style="color: #555; font-size: 10px; margin-bottom: 16px;"> Self-Learning Data Notebook · v1.0</div>

          <!-- System Info -->
          <div style="border: 1px solid #333; margin-bottom: 14px; padding: 10px 14px;">
            <div style="color: #00b4d8; font-weight: 700; margin-bottom: 6px; font-size: 9px; text-transform: uppercase; letter-spacing: 0.1em;">SYSTEM</div>
            <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 1px 32px; font-size: 11px;">
              <div><span style="color: #555; display: inline-block; width: 70px;">USER</span> <span>{username}</span></div>
              <div><span style="color: #555; display: inline-block; width: 70px;">ROLE</span> <span style="color: {isSuper ? '#ff9d00' : '#8a8a9a'};">{isSuper ? 'super_admin' : 'user'}</span></div>
              <div><span style="color: #555; display: inline-block; width: 70px;">SESSION</span> <span>{new Date().toLocaleDateString('en-US', { weekday: 'short', month: 'short', day: 'numeric' })}</span></div>
              <div><span style="color: #555; display: inline-block; width: 70px;">STATUS</span> <span style="color: #00fc40;">online</span></div>
            </div>
          </div>

          <!-- Workspace -->
          <div style="border: 1px solid #333; margin-bottom: 14px; padding: 10px 14px;">
            <div style="color: #00b4d8; font-weight: 700; margin-bottom: 6px; font-size: 9px; text-transform: uppercase; letter-spacing: 0.1em;">WORKSPACE</div>
            {#each [
              { label: 'AGENTS', value: projects.length, color: '#00fc40' },
              { label: 'TABLES', value: totalTables, color: '#00b4d8' },
              { label: 'ROWS', value: totalRows, color: '#ff9d00' },
              { label: 'FAVORITES', value: projects.filter(p => p.is_favorite).length, color: '#e0e0e0' },
            ] as stat}
              <div style="display: flex; align-items: center; gap: 10px; margin-bottom: 1px; font-size: 11px;">
                <span style="color: #555; width: 70px; text-align: right;">{stat.label}</span>
                <span style="color: {stat.color}; width: 40px; text-align: right; font-weight: 700;">{stat.value.toLocaleString()}</span>
                <span style="color: {stat.color}; opacity: 0.4; font-size: 9px;">{bar(stat.value, maxVal)}</span>
              </div>
            {/each}
          </div>

          <!-- Agents -->
          <div style="color: #00fc40; font-weight: 700; margin-bottom: 8px;">❯ ls agents/</div>
          {#if projects.length > 0}
            {#each projects as p}
              <div style="border: 1px solid #333; margin-bottom: 8px; padding: 10px 14px;">
                <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 4px;">
                  <div style="display: flex; align-items: center; gap: 6px;">
                    <span style="font-size: 16px;">🤖</span>
                    <span style="font-weight: 900; font-size: 13px; text-transform: uppercase;">{p.agent_name}</span>
                    {#if p.is_favorite}<span style="font-size: 11px;">⭐</span>{/if}
                  </div>
                  <span style="color: #00fc40; font-size: 8px; border: 1px solid #00fc40; padding: 1px 5px; text-transform: uppercase;">active</span>
                </div>
                <div style="color: #8a8a9a; font-size: 10px; margin-bottom: 6px;">{p.agent_role || 'data agent'} · {p.tables} tables · {p.rows.toLocaleString()} rows · {timeAgo(p.updated_at)}</div>
                <div style="display: flex; gap: 4px;">
                  <a href="/ui/project/{p.slug}" style="background: #00fc40; color: #1a1a1a; border: none; padding: 3px 10px; font-family: 'Space Grotesk', monospace; font-size: 9px; font-weight: 900; text-transform: uppercase; text-decoration: none;">▶ CHAT</a>
                  <a href="/ui/project/{p.slug}/settings" style="background: #333; color: #e0e0e0; border: 1px solid #555; padding: 3px 10px; font-family: 'Space Grotesk', monospace; font-size: 9px; font-weight: 700; text-transform: uppercase; text-decoration: none;">SETTINGS</a>
                  <a href="/ui/project/{p.slug}/dashboard" style="background: #333; color: #e0e0e0; border: 1px solid #555; padding: 3px 10px; font-family: 'Space Grotesk', monospace; font-size: 9px; font-weight: 700; text-transform: uppercase; text-decoration: none;">DASHBOARD</a>
                </div>
              </div>
            {/each}
          {:else}
            <div style="border: 1px dashed #555; padding: 16px; text-align: center; color: #555; margin-bottom: 8px;">
              no agents found · <a href="/ui/projects" style="color: #00fc40; text-decoration: none;">+ create first agent</a>
            </div>
          {/if}

          <!-- Commands -->
          <div style="margin-top: 14px; color: #00fc40; font-weight: 700;">❯ help</div>
          <div style="margin-top: 4px; font-size: 11px;">
            {#each [
              { cmd: 'new-agent', desc: 'create a new data agent', url: '/ui/projects' },
              { cmd: 'dash-agent', desc: 'chat across all agents', url: '/ui/chat' },
              ...(isSuper ? [{ cmd: 'cmd-center', desc: 'platform administration', url: '/ui/command-center' }] : []),
              { cmd: 'profile', desc: 'edit your profile', url: '/ui/profile' },
            ] as c}
              <div style="display: flex; gap: 8px; margin-bottom: 2px;">
                <a href={c.url} style="color: #00b4d8; text-decoration: none; width: 110px;">{c.cmd}</a>
                <span style="color: #555;">{c.desc}</span>
              </div>
            {/each}
          </div>

          <!-- Cursor -->
          <div style="margin-top: 12px; display: flex; align-items: center; gap: 4px;">
            <span style="color: #00fc40; font-weight: 700;">❯</span>
            <span style="display: inline-block; width: 7px; height: 14px; background: #00fc40; animation: cursorBlink 1s step-end infinite;"></span>
          </div>
        </div>
      {/if}
  </div>
</div>
