<script lang="ts">
  import { onMount } from 'svelte';

  let slug = $state('proj_admin_sales_analysis');
  let loading = $state(true);
  let error = $state('');

  // All data
  let training = $state<any>(null);
  let feedback = $state<any[]>([]);
  let patterns = $state<any[]>([]);
  let memories = $state<any[]>([]);
  let annotations = $state<any[]>([]);
  let trainingRuns = $state<any[]>([]);
  let driftAlerts = $state<any[]>([]);
  let evals = $state<any[]>([]);

  function _h(): Record<string, string> {
    const t = typeof localStorage !== 'undefined' ? localStorage.getItem('dash_token') : null;
    return t ? { Authorization: `Bearer ${t}` } : {};
  }

  // Memory add
  let newFact = $state('');
  let newScope = $state('project');

  onMount(async () => {
    try {
      const [t, fb, pt, mem, ann, runs, drift, ev] = await Promise.all([
        fetch(`/api/training?project=${slug}`, { headers: _h() }).then(r => r.json()),
        fetch(`/api/projects/${slug}/feedback`, { headers: _h() }).then(r => r.json()),
        fetch(`/api/projects/${slug}/query-patterns`, { headers: _h() }).then(r => r.json()),
        fetch(`/api/projects/${slug}/memories`, { headers: _h() }).then(r => r.json()),
        fetch(`/api/projects/${slug}/annotations`, { headers: _h() }).then(r => r.json()),
        fetch(`/api/projects/${slug}/training-runs`, { headers: _h() }).then(r => r.json()),
        fetch(`/api/projects/${slug}/drift-alerts`, { headers: _h() }).then(r => r.json()),
        fetch(`/api/projects/${slug}/evals`, { headers: _h() }).then(r => r.json()),
      ]);
      training = t;
      feedback = fb.feedback || [];
      patterns = pt.patterns || [];
      memories = mem.memories || [];
      annotations = ann.annotations || [];
      trainingRuns = runs.runs || [];
      driftAlerts = drift.drift_alerts || [];
      evals = ev.evals || [];
    } catch (e: any) {
      error = e.message;
    }
    loading = false;
  });

  async function addMemory() {
    if (!newFact) return;
    await fetch(`/api/projects/${slug}/memories`, {
      method: 'POST', headers: { ..._h(), 'Content-Type': 'application/json' },
      body: JSON.stringify({ fact: newFact, scope: newScope })
    });
    newFact = '';
    const r = await fetch(`/api/projects/${slug}/memories`, { headers: _h() });
    if (r.ok) { const d = await r.json(); memories = d.memories || []; }
  }

  async function deleteMemory(id: number) {
    await fetch(`/api/projects/${slug}/memories/${id}`, { method: 'DELETE', headers: _h() });
    const r = await fetch(`/api/projects/${slug}/memories`, { headers: _h() });
    if (r.ok) { const d = await r.json(); memories = d.memories || []; }
  }

  const feedbackGood = $derived(feedback.filter(f => f.rating === 'up'));
  const feedbackBad = $derived(feedback.filter(f => f.rating === 'down'));
</script>

<div style="max-width: 900px; margin: 20px auto; padding: 20px; font-family: 'Space Grotesk', monospace;">

  <div style="font-size: 24px; font-weight: 900; text-transform: uppercase; margin-bottom: 4px;">AGENT BRAIN</div>
  <div style="font-size: 10px; color: #6b6b60; text-transform: uppercase; letter-spacing: 0.1em; margin-bottom: 20px;">
    Project: {slug} · Standalone test page
  </div>

  {#if loading}
    <div style="font-size: 14px;">Loading...</div>
  {:else if error}
    <div style="color: red;">Error: {error}</div>
  {:else}

    <!-- CLI Status -->
    <div class="cli-terminal" style="margin-bottom: 20px; padding: 12px 16px;">
      <div class="cli-line"><span class="cli-prompt">$</span> <span class="cli-command">dash brain</span> <span class="cli-output">--verbose</span></div>
      <div class="cli-line"><span style="color: #555;">&gt;</span> <span class="cli-check">&#10003;</span> <span class="cli-output">error learnings: {training?.learnings || 0}</span></div>
      <div class="cli-line"><span style="color: #555;">&gt;</span> <span class="cli-check">&#10003;</span> <span class="cli-output">training Q&A: {training?.training_qa?.length || 0}</span></div>
      <div class="cli-line"><span style="color: #555;">&gt;</span> <span class="cli-check">&#10003;</span> <span class="cli-output">approved responses: {feedbackGood.length}</span></div>
      <div class="cli-line"><span style="color: #555;">&gt;</span> <span class="cli-check">&#10003;</span> <span class="cli-output">rejected patterns: {feedbackBad.length}</span></div>
      <div class="cli-line"><span style="color: #555;">&gt;</span> <span class="cli-check">&#10003;</span> <span class="cli-output">proven queries: {patterns.length}</span></div>
      <div class="cli-line"><span style="color: #555;">&gt;</span> <span class="cli-check">&#10003;</span> <span class="cli-output">remembered facts: {memories.length}</span></div>
    </div>

    <!-- Stats Grid -->
    <div style="display: grid; grid-template-columns: repeat(3, 1fr); gap: 8px; margin-bottom: 24px;">
      {#each [
        { label: 'ERROR LEARNINGS', value: training?.learnings || 0, color: '#be2d06' },
        { label: 'TRAINING Q&A', value: training?.training_qa?.length || 0, color: '#007518' },
        { label: 'FEEDBACK', value: feedback.length, color: '#006f7c' },
        { label: 'PROVEN SQL', value: patterns.length, color: '#007518' },
        { label: 'MEMORIES', value: memories.length, color: '#ff9d00' },
        { label: 'ANNOTATIONS', value: annotations.length, color: '#006f7c' },
      ] as stat}
        <div class="ink-border" style="background: #fffff0; padding: 12px; text-align: center;">
          <div style="font-size: 24px; font-weight: 900; color: {stat.color};">{stat.value}</div>
          <div style="font-size: 8px; text-transform: uppercase; color: #6b6b60; letter-spacing: 0.08em;">{stat.label}</div>
        </div>
      {/each}
    </div>

    <!-- Training History -->
    <div style="font-size: 14px; font-weight: 900; text-transform: uppercase; margin-bottom: 8px; border-bottom: 2px solid #383832; padding-bottom: 4px;">TRAINING HISTORY</div>
    {#if trainingRuns.length > 0}
      <div class="cli-terminal" style="padding: 10px 14px; margin-bottom: 20px;">
        {#each trainingRuns.slice(0, 5) as run}
          <div class="cli-line">
            <span style="color: {run.status === 'done' ? '#00fc40' : run.status === 'failed' ? '#ff6b6b' : '#ff9d00'};">
              {run.status === 'done' ? '✓' : run.status === 'failed' ? '✗' : '●'}
            </span>
            <span class="cli-output">{run.started_at?.slice(0, 16)} · {run.tables} table{run.tables !== 1 ? 's' : ''} · {run.status}</span>
          </div>
        {/each}
      </div>
    {:else}
      <div style="font-size: 11px; color: #6b6b60; margin-bottom: 20px;">No training runs recorded yet. Click TRAIN ALL in settings.</div>
    {/if}

    <!-- Drift Alerts -->
    <div style="font-size: 14px; font-weight: 900; text-transform: uppercase; margin-bottom: 8px; border-bottom: 2px solid #383832; padding-bottom: 4px;">DATA DRIFT ALERTS</div>
    {#if driftAlerts.length > 0}
      {#each driftAlerts as da}
        <div class="ink-border" style="background: #fffff0; padding: 10px 14px; margin-bottom: 8px; border-left: 3px solid #ff9d00;">
          <div style="font-size: 11px; font-weight: 900;">⚠ {da.table_name}</div>
          {#each da.alerts || [] as alert}
            <div style="font-size: 10px; color: #ff9d00; margin-top: 2px;">{alert}</div>
          {/each}
        </div>
      {/each}
    {:else}
      <div style="font-size: 11px; color: #6b6b60; margin-bottom: 20px;">No drift alerts. Data matches training patterns.</div>
    {/if}

    <!-- Memories -->
    <div style="font-size: 14px; font-weight: 900; text-transform: uppercase; margin-bottom: 8px; border-bottom: 2px solid #383832; padding-bottom: 4px;">AGENT MEMORIES ({memories.length})</div>
    <div style="display: flex; gap: 8px; margin-bottom: 12px; align-items: stretch;">
      <input type="text" bind:value={newFact} placeholder="Add a fact the agent should remember..." style="flex: 1; border: 2px solid #383832; padding: 6px 10px; font-family: 'Space Grotesk', monospace; font-size: 11px; background: #feffd6;" />
      <select bind:value={newScope} style="border: 2px solid #383832; padding: 6px 8px; font-family: 'Space Grotesk', monospace; font-size: 10px; background: #feffd6;">
        <option value="project">PROJECT</option>
        <option value="personal">PERSONAL</option>
        <option value="global">GLOBAL</option>
      </select>
      <button onclick={addMemory} style="background: #007518; color: white; border: 2px solid #383832; padding: 6px 14px; font-family: 'Space Grotesk', monospace; font-size: 10px; font-weight: 900; cursor: pointer;">+ ADD</button>
    </div>
    {#if memories.length > 0}
      <div class="cli-terminal" style="padding: 10px 14px; margin-bottom: 20px;">
        {#each memories as m}
          <div class="cli-line">
            <span style="color: #ff9d00;">●</span>
            <span class="cli-output">{m.fact}</span>
            <span class="cli-dim" style="margin-left: auto; font-size: 9px; text-transform: uppercase;">{m.scope}</span>
            {#if m.source}<span class="cli-dim" style="font-size: 8px; margin-left: 4px;">{m.source}</span>{/if}
            <button onclick={() => deleteMemory(m.id)} style="background: none; border: none; color: #555; cursor: pointer; font-size: 12px; margin-left: 6px;">✕</button>
          </div>
        {/each}
      </div>
    {:else}
      <div style="font-size: 11px; color: #6b6b60; margin-bottom: 20px;">No memories yet.</div>
    {/if}

    <!-- Proven Queries -->
    <div style="font-size: 14px; font-weight: 900; text-transform: uppercase; margin-bottom: 8px; border-bottom: 2px solid #383832; padding-bottom: 4px;">PROVEN QUERIES ({patterns.length})</div>
    {#if patterns.length > 0}
      {#each patterns.slice(0, 8) as p}
        <div class="ink-border" style="background: #fffff0; padding: 10px 14px; margin-bottom: 8px;">
          <div style="font-size: 11px; font-weight: 900; color: #007518;">Q: {p.question}</div>
          <div class="cli-terminal" style="margin-top: 4px; padding: 6px 10px; font-size: 10px;">
            <code style="color: #e0e0e0;">{p.sql}</code>
          </div>
          <div style="font-size: 9px; color: #6b6b60; margin-top: 3px;">Used {p.uses}x · Last: {p.last_used?.slice(0, 16)}</div>
        </div>
      {/each}
    {:else}
      <div style="font-size: 11px; color: #6b6b60; margin-bottom: 20px;">No proven queries yet. Use 👍 in chat to save SQL patterns.</div>
    {/if}

    <!-- User Feedback -->
    <div style="font-size: 14px; font-weight: 900; text-transform: uppercase; margin-bottom: 8px; border-bottom: 2px solid #383832; padding-bottom: 4px;">USER FEEDBACK ({feedback.length})</div>
    {#if feedback.length > 0}
      {#each feedback.slice(0, 8) as f}
        <div class="ink-border" style="background: #fffff0; padding: 10px 14px; margin-bottom: 8px; border-left: 3px solid {f.rating === 'up' ? '#007518' : '#be2d06'};">
          <div style="display: flex; align-items: center; gap: 8px;">
            <span style="font-size: 16px;">{f.rating === 'up' ? '👍' : '👎'}</span>
            <div style="font-size: 11px; font-weight: 700;">Q: {f.question}</div>
          </div>
          {#if f.answer}<div style="font-size: 10px; color: #6b6b60; margin-top: 4px;">{f.answer?.slice(0, 200)}...</div>{/if}
        </div>
      {/each}
    {:else}
      <div style="font-size: 11px; color: #6b6b60; margin-bottom: 20px;">No feedback yet. Use 👍/👎 in chat.</div>
    {/if}

    <!-- Training Q&A -->
    <div style="font-size: 14px; font-weight: 900; text-transform: uppercase; margin-bottom: 8px; border-bottom: 2px solid #383832; padding-bottom: 4px;">TRAINING Q&A PAIRS ({training?.training_qa?.length || 0})</div>
    {#if training?.training_qa?.length}
      {#each training.training_qa as qa}
        <div class="ink-border" style="background: #fffff0; padding: 10px 14px; margin-bottom: 8px;">
          <div style="font-size: 11px; font-weight: 900; color: #007518;">Q: {qa.question}</div>
          <div class="cli-terminal" style="margin-top: 4px; padding: 6px 10px; font-size: 10px;">
            <code style="color: #e0e0e0;">{qa.sql}</code>
          </div>
          {#if qa.source_table}
            <div style="font-size: 8px; color: #6b6b60; margin-top: 3px; text-transform: uppercase;">TABLE: {qa.source_table}</div>
          {/if}
        </div>
      {/each}
    {:else}
      <div style="font-size: 11px; color: #6b6b60; margin-bottom: 20px;">No training Q&A. Train your data to auto-generate.</div>
    {/if}

    <!-- Evals -->
    <div style="font-size: 14px; font-weight: 900; text-transform: uppercase; margin-bottom: 8px; border-bottom: 2px solid #383832; padding-bottom: 4px;">EVALS ({evals.length})</div>
    {#if evals.length > 0}
      {#each evals as ev}
        <div class="ink-border" style="background: #fffff0; padding: 10px 14px; margin-bottom: 8px; border-left: 3px solid {ev.last_score === 'PASS' ? '#007518' : ev.last_score === 'FAIL' ? '#be2d06' : '#6b6b60'};">
          <div style="font-size: 11px; font-weight: 900;">Q: {ev.question}</div>
          <div style="font-size: 10px; color: #6b6b60; margin-top: 2px;">Expected: {ev.expected_sql?.slice(0, 80)}</div>
          {#if ev.last_score}<div style="font-size: 10px; margin-top: 4px; font-weight: 900; color: {ev.last_score === 'PASS' ? '#007518' : '#be2d06'};">{ev.last_score}</div>{/if}
        </div>
      {/each}
    {:else}
      <div style="font-size: 11px; color: #6b6b60; margin-bottom: 20px;">No evals. Add Q&A test pairs in Settings → EVALS tab.</div>
    {/if}

  {/if}
</div>
