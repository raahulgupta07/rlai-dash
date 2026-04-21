<script lang="ts">
  import { onMount } from 'svelte';

  let presentations = $state<any[]>([]);
  let loading = $state(true);

  function _h(): Record<string, string> {
    const t = typeof localStorage !== 'undefined' ? localStorage.getItem('dash_token') : null;
    return t ? { 'Authorization': `Bearer ${t}` } : {};
  }

  function timeAgo(ts: string | null): string {
    if (!ts) return '';
    const diff = Date.now() - new Date(ts).getTime();
    const mins = Math.floor(diff / 60000);
    if (mins < 60) return `${mins}m ago`;
    const hrs = Math.floor(mins / 60);
    if (hrs < 24) return `${hrs}h ago`;
    return `${Math.floor(hrs / 24)}d ago`;
  }

  onMount(async () => {
    try {
      // Get all projects first
      const projRes = await fetch('/api/projects', { headers: _h() });
      if (projRes.ok) {
        const projData = await projRes.json();
        const allPres: any[] = [];
        for (const p of projData.projects || []) {
          const presRes = await fetch(`/api/export/presentations?project=${p.slug}`, { headers: _h() });
          if (presRes.ok) {
            const presData = await presRes.json();
            for (const pr of presData.presentations || []) {
              allPres.push({ ...pr, project_slug: p.slug, project_name: p.agent_name });
            }
          }
        }
        presentations = allPres.sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime());
      }
    } catch {}
    loading = false;
  });

  async function deletePres(id: number) {
    if (!confirm('Delete this presentation?')) return;
    await fetch(`/api/export/presentations/${id}`, { method: 'DELETE', headers: _h() });
    presentations = presentations.filter(p => p.id !== id);
  }

  async function downloadPptx(id: number, title: string) {
    const res = await fetch(`/api/export/presentations/${id}/pptx`, { method: 'POST', headers: _h() });
    if (res.ok) {
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `${title}.pptx`;
      a.click();
      URL.revokeObjectURL(url);
    }
  }
</script>

<div style="max-width: 1200px; margin: 0 auto; padding: 24px;">
  <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 24px;">
    <div>
      <h1 style="font-size: 24px; font-weight: 900; text-transform: uppercase; letter-spacing: 0.02em; margin: 0;">Presentations</h1>
      <div style="font-size: 11px; color: var(--color-on-surface-dim); margin-top: 4px;">{presentations.length} saved presentations</div>
    </div>
  </div>

  {#if loading}
    <div style="text-align: center; padding: 60px; font-size: 12px; color: var(--color-on-surface-dim); text-transform: uppercase;">Loading...</div>
  {:else if presentations.length === 0}
    <div class="ink-border" style="padding: 60px; text-align: center; border-style: dashed;">
      <div style="font-size: 14px; font-weight: 900; text-transform: uppercase; margin-bottom: 8px;">No presentations yet</div>
      <div style="font-size: 12px; color: var(--color-on-surface-dim);">Chat with an agent, then click the P button to create a presentation. Click SAVE to keep it here.</div>
    </div>
  {:else}
    <div style="display: grid; grid-template-columns: repeat(auto-fill, minmax(300px, 1fr)); gap: 16px;">
      {#each presentations as pres}
        <div class="ink-border" style="background: var(--color-surface-bright); display: flex; flex-direction: column;">
          <div style="padding: 16px; flex: 1;">
            <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 8px;">
              <svg width="20" height="20" viewBox="0 0 24 24"><defs><linearGradient id="ppg" x1="0" y1="0" x2="1" y2="1"><stop offset="0%" stop-color="#D24726"/><stop offset="100%" stop-color="#F0A030"/></linearGradient></defs><rect x="2" y="2" width="20" height="20" rx="3" fill="url(#ppg)"/><text x="12" y="16" text-anchor="middle" fill="#fff" font-size="12" font-weight="900" font-family="Arial">P</text></svg>
              <span style="font-size: 8px; font-weight: 900; padding: 1px 6px; background: var(--color-primary-container); text-transform: uppercase;">v{pres.version}</span>
            </div>
            <div style="font-size: 15px; font-weight: 900; margin-bottom: 4px;">{pres.title}</div>
            <div style="font-size: 10px; color: var(--color-on-surface-dim); margin-bottom: 8px;">
              {pres.project_name} · {timeAgo(pres.created_at)}
            </div>
            {#if pres.thinking?.narrative}
              <div style="font-size: 11px; color: var(--color-on-surface-dim); line-height: 1.4; border-left: 2px solid #D24726; padding-left: 8px;">{pres.thinking.narrative}</div>
            {/if}
          </div>
          <div style="display: flex; border-top: 2px solid var(--color-on-surface);">
            <a href="/ui/project/{pres.project_slug}" style="flex: 1; padding: 8px; text-align: center; font-size: 10px; font-weight: 900; text-transform: uppercase; text-decoration: none; color: var(--color-on-surface); border-right: 2px solid var(--color-on-surface);">
              OPEN
            </a>
            <button onclick={() => downloadPptx(pres.id, pres.title)} style="flex: 1; padding: 8px; text-align: center; font-size: 10px; font-weight: 900; text-transform: uppercase; background: none; border: none; border-right: 2px solid var(--color-on-surface); cursor: pointer; color: #D24726;">
              PPTX
            </button>
            <button onclick={() => deletePres(pres.id)} style="padding: 8px 14px; background: none; border: none; cursor: pointer; color: var(--color-error); font-size: 10px; font-weight: 900;">
              ✕
            </button>
          </div>
        </div>
      {/each}
    </div>
  {/if}
</div>
