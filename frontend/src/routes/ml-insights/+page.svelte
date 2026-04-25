<script lang="ts">
  import { onMount } from 'svelte';
  import EChartView from '$lib/echart.svelte';

  let models = $state<any[]>([]);
  let experiments = $state<any[]>([]);
  let loading = $state(true);
  let filterType = $state('all');
  let selectedProject = $state('all');
  let projects = $state<any[]>([]);
  let selectedModel = $state<any>(null);  // null = card list, object = detail view
  let detailTab = $state('overview');  // overview, results, history

  function _h(): Record<string, string> {
    const t = typeof localStorage !== 'undefined' ? localStorage.getItem('dash_token') : null;
    return t ? { Authorization: `Bearer ${t}` } : {};
  }

  async function loadData() {
    loading = true;
    try {
      const url = selectedProject !== 'all'
        ? `/api/ml-experiments?project=${selectedProject}`
        : '/api/ml-experiments';
      const res = await fetch(url, { headers: _h() });
      if (res.ok) {
        const d = await res.json();
        models = d.models || [];
        experiments = d.experiments || [];
      }
    } catch {}
    loading = false;
  }

  async function loadProjects() {
    try {
      const res = await fetch('/api/user-projects-brief', { headers: _h() });
      if (res.ok) { const d = await res.json(); projects = d.projects || []; }
    } catch {}
  }

  async function retrain(modelId: number) {
    try {
      await fetch(`/api/ml-experiments/${modelId}/retrain`, { method: 'POST', headers: _h() });
      await loadData();
    } catch {}
  }

  function openDetail(model: any) {
    selectedModel = model;
    detailTab = 'overview';
  }

  function backToList() {
    selectedModel = null;
  }

  function formatDate(ts: string | null): string {
    if (!ts) return '';
    try {
      const d = new Date(ts);
      return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric', hour: '2-digit', minute: '2-digit' });
    } catch { return ''; }
  }

  function formatAccuracy(acc: any): string {
    if (!acc) return 'N/A';
    if (acc.mape) return `MAPE ${acc.mape}`;
    if (acc.r2) return `R\u00B2 ${acc.r2}`;
    if (acc.confidence) return acc.confidence;
    if (acc.method) return acc.method;
    return JSON.stringify(acc);
  }

  let filteredModels = $derived(models.filter(m => filterType === 'all' || m.model_type === filterType));
  let modelExperiments = $derived(selectedModel ? experiments.filter(e => e.model_name === selectedModel.name || e.model_name?.includes(selectedModel.name?.split('_')[0])) : []);

  onMount(async () => {
    const res = await fetch('/api/auth/check', { headers: _h() });
    if (!res.ok) { window.location.href = '/ui/login'; return; }
    await loadProjects();
    await loadData();
  });
</script>

<div style="max-width: 1000px; margin: 0 auto; padding: 20px;">

{#if selectedModel}
  <!-- DETAIL VIEW -->
  <button onclick={backToList} style="font-size: 10px; font-weight: 900; text-transform: uppercase; letter-spacing: 0.1em; padding: 4px 12px; border: 2px solid var(--color-on-surface); background: transparent; cursor: pointer; font-family: var(--font-family-display); margin-bottom: 16px;">← BACK TO ML INSIGHTS</button>

  <div style="margin-bottom: 20px;">
    <div style="display: flex; align-items: center; gap: 12px;">
      <span style="font-size: 24px;">{selectedModel.model_type === 'forecast' ? '📊' : selectedModel.model_type === 'anomaly' ? '🔍' : '🎯'}</span>
      <div>
        <div style="font-size: 22px; font-weight: 900; text-transform: uppercase;">{selectedModel.name}</div>
        <div style="font-size: 11px; color: var(--color-on-surface-dim);">
          {selectedModel.algorithm} · {selectedModel.project_slug} · {formatDate(selectedModel.created_at)}
        </div>
      </div>
      <span style="font-size: 8px; font-weight: 900; padding: 2px 8px; background: #007518; color: white; text-transform: uppercase; margin-left: auto;">ACTIVE</span>
    </div>
  </div>

  <!-- Summary cards -->
  <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(120px, 1fr)); gap: 8px; margin-bottom: 16px;">
    <div style="padding: 12px; border: 2px solid var(--color-on-surface); border-bottom-width: 3px; text-align: center;">
      <div style="font-size: 14px; font-weight: 900;">{selectedModel.algorithm}</div>
      <div style="font-size: 9px; font-weight: 700; text-transform: uppercase; color: var(--color-on-surface-dim);">ALGORITHM</div>
    </div>
    <div style="padding: 12px; border: 2px solid var(--color-on-surface); border-bottom-width: 3px; text-align: center;">
      <div style="font-size: 14px; font-weight: 900;">{formatAccuracy(selectedModel.accuracy)}</div>
      <div style="font-size: 9px; font-weight: 700; text-transform: uppercase; color: var(--color-on-surface-dim);">ACCURACY</div>
    </div>
    <div style="padding: 12px; border: 2px solid var(--color-on-surface); border-bottom-width: 3px; text-align: center;">
      <div style="font-size: 14px; font-weight: 900;">{selectedModel.row_count}</div>
      <div style="font-size: 9px; font-weight: 700; text-transform: uppercase; color: var(--color-on-surface-dim);">DATA POINTS</div>
    </div>
    <div style="padding: 12px; border: 2px solid var(--color-on-surface); border-bottom-width: 3px; text-align: center;">
      <div style="font-size: 14px; font-weight: 900;">{modelExperiments.length}</div>
      <div style="font-size: 9px; font-weight: 700; text-transform: uppercase; color: var(--color-on-surface-dim);">RUNS</div>
    </div>
  </div>

  <!-- Detail tabs -->
  <div class="response-tabs" style="margin-bottom: 0;">
    <button class="response-tab" class:response-tab-active={detailTab === 'overview'} onclick={() => detailTab = 'overview'}>Overview</button>
    <button class="response-tab" class:response-tab-active={detailTab === 'results'} onclick={() => detailTab = 'results'}>
      {selectedModel.model_type === 'forecast' ? 'Predictions' : selectedModel.model_type === 'anomaly' ? 'Anomalies' : 'Factors'}
    </button>
    <button class="response-tab" class:response-tab-active={detailTab === 'history'} onclick={() => detailTab = 'history'}>History<span class="tab-badge">{modelExperiments.length}</span></button>
    <button class="response-tab" class:response-tab-active={detailTab === 'chart'} onclick={() => detailTab = 'chart'}>Chart</button>
    {#if modelExperiments.length >= 2}
      <button class="response-tab" class:response-tab-active={detailTab === 'compare'} onclick={() => detailTab = 'compare'}>Compare</button>
    {/if}
  </div>

  <div style="border: 2px solid var(--color-on-surface); border-top: none; padding: 16px;">
    {#if detailTab === 'overview'}
      <!-- Overview -->
      <table class="data-table" style="margin-bottom: 16px;">
        <tbody>
          <tr><td style="font-weight: 900; text-transform: uppercase; font-size: 10px; width: 140px; color: var(--color-on-surface-dim);">TYPE</td><td style="text-transform: uppercase;">{selectedModel.model_type}</td></tr>
          <tr><td style="font-weight: 900; text-transform: uppercase; font-size: 10px; color: var(--color-on-surface-dim);">ALGORITHM</td><td>{selectedModel.algorithm}</td></tr>
          <tr><td style="font-weight: 900; text-transform: uppercase; font-size: 10px; color: var(--color-on-surface-dim);">TARGET</td><td>{selectedModel.target_column || 'N/A'}</td></tr>
          <tr><td style="font-weight: 900; text-transform: uppercase; font-size: 10px; color: var(--color-on-surface-dim);">FEATURES</td><td>{selectedModel.features || 'N/A'}</td></tr>
          <tr><td style="font-weight: 900; text-transform: uppercase; font-size: 10px; color: var(--color-on-surface-dim);">DATA</td><td>{selectedModel.row_count} rows</td></tr>
          <tr><td style="font-weight: 900; text-transform: uppercase; font-size: 10px; color: var(--color-on-surface-dim);">ACCURACY</td><td>{formatAccuracy(selectedModel.accuracy)}</td></tr>
          {#if selectedModel.accuracy?.method}<tr><td style="font-weight: 900; text-transform: uppercase; font-size: 10px; color: var(--color-on-surface-dim);">METHOD</td><td>{selectedModel.accuracy.method}</td></tr>{/if}
          {#if selectedModel.accuracy?.contamination}<tr><td style="font-weight: 900; text-transform: uppercase; font-size: 10px; color: var(--color-on-surface-dim);">CONTAMINATION</td><td>{(selectedModel.accuracy.contamination * 100).toFixed(0)}%</td></tr>{/if}
          {#if selectedModel.accuracy?.features}<tr><td style="font-weight: 900; text-transform: uppercase; font-size: 10px; color: var(--color-on-surface-dim);">FEATURES USED</td><td>{selectedModel.accuracy.features}</td></tr>{/if}
          <tr><td style="font-weight: 900; text-transform: uppercase; font-size: 10px; color: var(--color-on-surface-dim);">PROJECT</td><td>{selectedModel.project_slug}</td></tr>
          <tr><td style="font-weight: 900; text-transform: uppercase; font-size: 10px; color: var(--color-on-surface-dim);">CREATED</td><td>{formatDate(selectedModel.created_at)}</td></tr>
        </tbody>
      </table>
      <div style="display: flex; gap: 8px;">
        <button onclick={() => retrain(selectedModel.id)} style="font-size: 9px; font-weight: 900; padding: 6px 14px; text-transform: uppercase; border: 2px solid var(--color-on-surface); background: var(--color-primary-container); cursor: pointer; font-family: var(--font-family-display);">RETRAIN NOW</button>
        <a href="/ui/project/{selectedModel.project_slug}" style="font-size: 9px; font-weight: 900; padding: 6px 14px; text-transform: uppercase; border: 2px solid var(--color-on-surface); background: var(--color-surface-bright); text-decoration: none; color: var(--color-on-surface); font-family: var(--font-family-display);">ASK IN CHAT</a>
      </div>

    {:else if detailTab === 'results'}
      <!-- Results (type-specific) -->
      {#if modelExperiments.length > 0}
        {@const latest = modelExperiments[0]}
        {@const resultData = latest.result_data || {}}

        {#if latest.experiment_type === 'forecast'}
          <div style="font-size: 10px; font-weight: 900; text-transform: uppercase; margin-bottom: 12px; color: var(--color-on-surface-dim);">LATEST FORECAST</div>
          {#if resultData.predictions}
            <div style="display: flex; gap: 10px; margin-bottom: 16px; flex-wrap: wrap;">
              {#each resultData.predictions as p}
                <div style="flex: 1; min-width: 100px; max-width: 160px; border: 2px solid var(--color-on-surface); padding: 10px; text-align: center; background: var(--color-surface-bright);">
                  <div style="font-size: 18px; font-weight: 900;">{typeof p === 'string' ? p : (p.value ? `$${(p.value/1000000).toFixed(1)}M` : p.period || '?')}</div>
                  <div style="font-size: 9px; text-transform: uppercase; color: var(--color-on-surface-dim);">{typeof p === 'object' ? p.period || '' : ''}</div>
                </div>
              {/each}
            </div>
          {:else}
            <div style="font-size: 12px; color: var(--color-on-surface-dim); padding: 12px; border: 1px dashed var(--color-on-surface-dim);">
              Forecast data available in text format. Run the prediction again for structured output.
            </div>
          {/if}
          {#if resultData.trend}
            <div style="font-size: 12px; margin-top: 8px;"><strong>Trend:</strong> {resultData.trend} · <strong>Growth:</strong> {resultData.growth_rate || 'N/A'} · <strong>Confidence:</strong> {resultData.confidence || latest.accuracy?.confidence || 'N/A'}</div>
          {/if}

        {:else if latest.experiment_type === 'anomaly'}
          <div style="font-size: 10px; font-weight: 900; text-transform: uppercase; margin-bottom: 12px; color: var(--color-on-surface-dim);">ANOMALIES DETECTED</div>
          <div style="display: flex; gap: 10px; margin-bottom: 16px;">
            <div style="padding: 10px 20px; border: 2px solid #dc2626; text-align: center;">
              <div style="font-size: 22px; font-weight: 900; color: #dc2626;">{resultData.total_anomalies || 0}</div>
              <div style="font-size: 9px; text-transform: uppercase; color: var(--color-on-surface-dim);">TOTAL</div>
            </div>
            <div style="padding: 10px 20px; border: 2px solid #dc2626; text-align: center;">
              <div style="font-size: 22px; font-weight: 900; color: #dc2626;">{resultData.high_severity || 0}</div>
              <div style="font-size: 9px; text-transform: uppercase; color: var(--color-on-surface-dim);">HIGH SEVERITY</div>
            </div>
          </div>
          {#if resultData.anomalies?.length}
            <table class="data-table">
              <thead><tr><th>#</th><th>ROW</th><th>SCORE</th><th>SEVERITY</th></tr></thead>
              <tbody>
                {#each resultData.anomalies as a, i}
                  <tr>
                    <td>{i + 1}</td>
                    <td>{a.row}</td>
                    <td>{a.score?.toFixed(3) || 'N/A'}</td>
                    <td style="color: {(a.score || 0) < -0.1 ? '#dc2626' : (a.score || 0) < -0.05 ? '#d97706' : '#666'}; font-weight: 700;">{(a.score || 0) < -0.1 ? '⚠ HIGH' : (a.score || 0) < -0.05 ? '● MEDIUM' : '○ LOW'}</td>
                  </tr>
                {/each}
              </tbody>
            </table>
          {/if}

        {:else if latest.experiment_type === 'importance'}
          <div style="font-size: 10px; font-weight: 900; text-transform: uppercase; margin-bottom: 12px; color: var(--color-on-surface-dim);">FEATURE IMPORTANCE</div>
          {#if latest.accuracy?.r2}
            <div style="font-size: 12px; margin-bottom: 12px;">Model explains <strong>{(latest.accuracy.r2 * 100).toFixed(0)}%</strong> of variance (R² = {latest.accuracy.r2})</div>
          {/if}
          {#if resultData.factors?.length}
            {#each resultData.factors as f}
              <div style="display: flex; align-items: center; gap: 10px; margin-bottom: 6px;">
                <span style="font-size: 11px; font-weight: 700; min-width: 100px;">{f.name}</span>
                <div style="flex: 1; height: 18px; background: var(--color-surface-dim); border: 1px solid var(--color-on-surface);">
                  <div style="height: 100%; width: {f.importance}%; background: {f.importance > 20 ? '#007518' : f.importance > 10 ? '#d97706' : '#888'};"></div>
                </div>
                <span style="font-size: 11px; font-weight: 900; min-width: 45px; text-align: right;">{f.importance}%</span>
              </div>
            {/each}
          {/if}
        {/if}

        {#if latest.question}
          <div style="margin-top: 16px; padding: 10px; background: var(--color-surface-dim); border-left: 3px solid var(--color-primary); font-size: 11px;">
            <span style="font-weight: 900; text-transform: uppercase; font-size: 9px; color: var(--color-on-surface-dim);">TRIGGERED BY:</span> "{latest.question}"
          </div>
        {/if}
      {:else}
        <div style="text-align: center; padding: 30px; color: var(--color-on-surface-dim);">
          <div style="font-size: 13px; font-weight: 900; text-transform: uppercase;">NO EXPERIMENTS YET</div>
          <div style="font-size: 11px; margin-top: 6px;">Ask a prediction or anomaly question in chat to generate results</div>
        </div>
      {/if}

    {:else if detailTab === 'history'}
      <!-- Experiment history -->
      {#if modelExperiments.length > 0}
        <div style="display: flex; flex-direction: column; gap: 8px;">
          {#each modelExperiments as exp, i}
            <div style="border: 2px solid var(--color-on-surface); padding: 12px;">
              <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px;">
                <span style="font-size: 11px; font-weight: 900;">RUN #{modelExperiments.length - i}</span>
                <div style="display: flex; gap: 6px; align-items: center;">
                  {#if i === 0}<span style="font-size: 8px; font-weight: 900; padding: 1px 6px; background: #007518; color: white;">LATEST</span>{/if}
                  <span style="font-size: 10px; color: var(--color-on-surface-dim);">{formatDate(exp.created_at)}</span>
                </div>
              </div>
              <div style="font-size: 11px; color: var(--color-on-surface-dim);">
                {exp.algorithm} · {exp.tier === 'instant' ? '⚡ Pre-trained' : exp.tier === 'llm' ? '🧠 LLM' : exp.tier || ''} · {exp.experiment_type}
              </div>
              {#if exp.question}
                <div style="font-size: 11px; margin-top: 4px; font-style: italic;">"{exp.question}"</div>
              {/if}
              {#if exp.result_data?.predictions}
                <div style="font-size: 10px; margin-top: 4px; color: var(--color-on-surface-dim);">
                  {JSON.stringify(exp.result_data.predictions).slice(0, 100)}...
                </div>
              {/if}
              {#if exp.result_data?.total_anomalies !== undefined}
                <div style="font-size: 10px; margin-top: 4px; color: #dc2626; font-weight: 700;">
                  {exp.result_data.total_anomalies} anomalies found ({exp.result_data.high_severity || 0} high)
                </div>
              {/if}
              {#if exp.result_data?.factors}
                <div style="font-size: 10px; margin-top: 4px;">
                  Top: {exp.result_data.factors.slice(0, 3).map((f: any) => `${f.name} ${f.importance}%`).join(', ')}
                </div>
              {/if}
            </div>
          {/each}
        </div>
      {:else}
        <div style="text-align: center; padding: 30px; color: var(--color-on-surface-dim);">No experiment history yet</div>
      {/if}

    {:else if detailTab === 'chart'}
      <!-- Chart visualizations from experiment data -->
      {#if modelExperiments.length > 0}
        {@const latest = modelExperiments[0]}
        {@const resultData = latest.result_data || {}}

        {#if latest.experiment_type === 'importance'}
          <!-- Importance: horizontal bar from factors -->
          {#if resultData.factors?.length}
            <div style="font-size: 10px; font-weight: 900; text-transform: uppercase; margin-bottom: 12px; color: var(--color-on-surface-dim);">FEATURE IMPORTANCE</div>
            <EChartView
              headers={['Feature', 'Importance']}
              rows={resultData.factors.map((f: any) => [f.name, String(f.importance)])}
              chartType="bar"
            />
          {/if}
          <!-- Importance: scatter from actual_vs_predicted -->
          {#if resultData.actual_vs_predicted?.length}
            <div style="font-size: 10px; font-weight: 900; text-transform: uppercase; margin: 20px 0 12px; color: var(--color-on-surface-dim);">ACTUAL vs PREDICTED</div>
            <EChartView
              headers={['Actual', 'Predicted']}
              rows={resultData.actual_vs_predicted.map((p: any) => [String(p.actual), String(p.predicted)])}
              chartType="scatter"
            />
          {/if}

        {:else if latest.experiment_type === 'anomaly'}
          <!-- Anomaly: pie from severity -->
          {#if resultData.severity?.length}
            <div style="font-size: 10px; font-weight: 900; text-transform: uppercase; margin-bottom: 12px; color: var(--color-on-surface-dim);">SEVERITY DISTRIBUTION</div>
            <EChartView
              headers={['Severity', 'Count']}
              rows={resultData.severity.map((s: any) => [s.level || s.name, String(s.count || s.value)])}
              chartType="pie"
            />
          {/if}
          <!-- Anomaly: scatter from scatter data -->
          {#if resultData.scatter?.length}
            <div style="font-size: 10px; font-weight: 900; text-transform: uppercase; margin: 20px 0 12px; color: var(--color-on-surface-dim);">ANOMALY SCATTER</div>
            <EChartView
              headers={['X', 'Y']}
              rows={resultData.scatter.map((p: any) => [String(p.x), String(p.y)])}
              chartType="scatter"
            />
          {/if}

        {:else if latest.experiment_type === 'forecast'}
          <!-- Forecast: line from predictions -->
          {#if resultData.predictions?.length}
            <div style="font-size: 10px; font-weight: 900; text-transform: uppercase; margin-bottom: 12px; color: var(--color-on-surface-dim);">FORECAST PREDICTIONS</div>
            <EChartView
              headers={['Period', 'Value']}
              rows={resultData.predictions.map((p: any) => typeof p === 'string' ? [p, '0'] : [p.period || String(p.label || ''), String(p.value || p.forecast || 0)])}
              chartType="line"
            />
          {/if}
        {/if}
      {:else}
        <div style="text-align: center; padding: 30px; color: var(--color-on-surface-dim);">
          <div style="font-size: 13px; font-weight: 900; text-transform: uppercase;">NO CHART DATA</div>
          <div style="font-size: 11px; margin-top: 6px;">Run an experiment to generate chart visualizations</div>
        </div>
      {/if}

    {:else if detailTab === 'compare' && modelExperiments.length >= 2}
      {@const exp1 = modelExperiments[0]}
      {@const exp2 = modelExperiments[1]}
      <div style="font-size: 10px; font-weight: 900; text-transform: uppercase; margin-bottom: 12px; color: var(--color-on-surface-dim);">EXPERIMENT COMPARISON</div>
      <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 16px;">
        {#each [exp1, exp2] as exp, ei}
          <div style="border: 2px solid {ei === 0 ? 'var(--color-on-surface)' : 'var(--color-on-surface-dim)'}; padding: 14px;">
            <div style="display: flex; justify-content: space-between; margin-bottom: 10px;">
              <span style="font-size: 11px; font-weight: 900;">RUN #{modelExperiments.length - ei}</span>
              <span style="font-size: 8px; font-weight: 900; padding: 1px 6px; background: {ei === 0 ? '#007518' : 'var(--color-on-surface-dim)'}; color: {ei === 0 ? 'white' : 'var(--color-surface)'};">{ei === 0 ? 'LATEST' : 'PREVIOUS'}</span>
            </div>
            <div style="font-size: 10px; color: var(--color-on-surface-dim); margin-bottom: 8px;">{formatDate(exp.created_at)}</div>
            <table class="data-table" style="font-size: 11px;">
              <tbody>
                <tr><td style="font-weight: 700; font-size: 9px; text-transform: uppercase; color: var(--color-on-surface-dim);">Algorithm</td><td>{exp.algorithm}</td></tr>
                <tr><td style="font-weight: 700; font-size: 9px; text-transform: uppercase; color: var(--color-on-surface-dim);">Tier</td><td>{exp.tier === 'instant' ? '⚡ Pre-trained' : exp.tier === 'llm' ? '🧠 LLM' : exp.tier || '—'}</td></tr>
                {#if exp.accuracy?.r2}<tr><td style="font-weight: 700; font-size: 9px; text-transform: uppercase; color: var(--color-on-surface-dim);">R²</td><td>{exp.accuracy.r2}</td></tr>{/if}
                {#if exp.accuracy?.mape}<tr><td style="font-weight: 700; font-size: 9px; text-transform: uppercase; color: var(--color-on-surface-dim);">MAPE</td><td>{exp.accuracy.mape}%</td></tr>{/if}
                {#if exp.accuracy?.accuracy}<tr><td style="font-weight: 700; font-size: 9px; text-transform: uppercase; color: var(--color-on-surface-dim);">Accuracy</td><td>{(exp.accuracy.accuracy * 100).toFixed(1)}%</td></tr>{/if}
                {#if exp.accuracy?.cv_mean}<tr><td style="font-weight: 700; font-size: 9px; text-transform: uppercase; color: var(--color-on-surface-dim);">CV Score</td><td>{exp.accuracy.cv_mean} ± {exp.accuracy.cv_std}</td></tr>{/if}
                {#if exp.result_data?.total_anomalies !== undefined}<tr><td style="font-weight: 700; font-size: 9px; text-transform: uppercase; color: var(--color-on-surface-dim);">Anomalies</td><td>{exp.result_data.total_anomalies}</td></tr>{/if}
                {#if exp.result_data?.factors}<tr><td style="font-weight: 700; font-size: 9px; text-transform: uppercase; color: var(--color-on-surface-dim);">Top Factor</td><td>{exp.result_data.factors[0]?.name} ({exp.result_data.factors[0]?.importance}%)</td></tr>{/if}
              </tbody>
            </table>
            {#if exp.question}<div style="font-size: 10px; margin-top: 8px; font-style: italic; color: var(--color-on-surface-dim);">"{exp.question}"</div>{/if}
          </div>
        {/each}
      </div>
    {/if}
  </div>

{:else}
  <!-- CARD LIST VIEW -->
  <div style="margin-bottom: 24px;">
    <div style="font-size: 28px; font-weight: 900; letter-spacing: -0.02em;">ML INSIGHTS</div>
    <div style="font-size: 11px; color: var(--color-on-surface-dim); text-transform: uppercase; letter-spacing: 0.1em; margin-top: 4px;">Machine learning experiments across your projects</div>
  </div>

  <!-- Summary -->
  <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(120px, 1fr)); gap: 8px; margin-bottom: 20px;">
    <div style="padding: 14px; border: 2px solid var(--color-on-surface); border-bottom-width: 3px; text-align: center;">
      <div style="font-size: 24px; font-weight: 900;">{models.length}</div>
      <div style="font-size: 9px; font-weight: 700; text-transform: uppercase; color: var(--color-on-surface-dim);">MODELS</div>
    </div>
    <div style="padding: 14px; border: 2px solid var(--color-on-surface); border-bottom-width: 3px; text-align: center;">
      <div style="font-size: 24px; font-weight: 900;">{models.filter(m => m.model_type === 'forecast').length}</div>
      <div style="font-size: 9px; font-weight: 700; text-transform: uppercase; color: var(--color-on-surface-dim);">FORECASTS</div>
    </div>
    <div style="padding: 14px; border: 2px solid var(--color-on-surface); border-bottom-width: 3px; text-align: center;">
      <div style="font-size: 24px; font-weight: 900;">{models.filter(m => m.model_type === 'anomaly').length}</div>
      <div style="font-size: 9px; font-weight: 700; text-transform: uppercase; color: var(--color-on-surface-dim);">ANOMALY</div>
    </div>
    <div style="padding: 14px; border: 2px solid var(--color-on-surface); border-bottom-width: 3px; text-align: center;">
      <div style="font-size: 24px; font-weight: 900;">{experiments.length}</div>
      <div style="font-size: 9px; font-weight: 700; text-transform: uppercase; color: var(--color-on-surface-dim);">EXPERIMENTS</div>
    </div>
  </div>

  <!-- Filters -->
  <div style="display: flex; gap: 4px; margin-bottom: 16px; flex-wrap: wrap; align-items: center;">
    <span style="font-size: 9px; font-weight: 900; text-transform: uppercase; letter-spacing: 0.1em; color: var(--color-on-surface-dim); margin-right: 8px;">TYPE</span>
    {#each [['all','ALL'],['forecast','FORECASTS'],['anomaly','ANOMALIES'],['importance','DRIVERS']] as [val, label]}
      <button style="font-size: 9px; font-weight: 700; padding: 3px 10px; cursor: pointer; text-transform: uppercase; font-family: var(--font-family-display); border: 2px solid {filterType === val ? 'var(--color-on-surface)' : 'var(--color-on-surface-dim)'}; background: {filterType === val ? 'var(--color-on-surface)' : 'transparent'}; color: {filterType === val ? 'var(--color-surface)' : 'var(--color-on-surface-dim)'};" onclick={() => filterType = val}>{label}</button>
    {/each}
    <span style="font-size: 9px; font-weight: 900; text-transform: uppercase; letter-spacing: 0.1em; color: var(--color-on-surface-dim); margin-left: 16px; margin-right: 8px;">PROJECT</span>
    <select bind:value={selectedProject} onchange={() => loadData()} style="font-size: 10px; font-weight: 700; padding: 3px 8px; border: 2px solid var(--color-on-surface); background: var(--color-surface-bright); font-family: var(--font-family-display);">
      <option value="all">ALL PROJECTS</option>
      {#each projects as p}
        <option value={p.slug}>{p.agent_name || p.name}</option>
      {/each}
    </select>
  </div>

  <!-- Model cards (grid like Projects page) -->
  {#if loading}
    <div style="text-align: center; padding: 40px; color: var(--color-on-surface-dim);">Loading...</div>
  {:else if filteredModels.length === 0}
    <div style="text-align: center; padding: 40px; border: 2px dashed var(--color-on-surface-dim);">
      <div style="font-size: 14px; font-weight: 900; text-transform: uppercase;">NO ML MODELS YET</div>
      <div style="font-size: 11px; color: var(--color-on-surface-dim); margin-top: 8px;">Train a project to auto-create ML models</div>
    </div>
  {:else}
    <div style="display: grid; grid-template-columns: repeat(auto-fill, minmax(300px, 1fr)); gap: 16px;">
      {#each filteredModels as model}
        <div style="border: 2px solid var(--color-on-surface); background: var(--color-surface-bright); display: flex; flex-direction: column;">
          <!-- Card header -->
          <div style="padding: 20px 20px 12px 20px;">
            <div style="font-size: 32px; margin-bottom: 12px;">
              {model.model_type === 'forecast' ? '📊' : model.model_type === 'anomaly' ? '🔍' : '🎯'}
            </div>
            <div style="font-size: 16px; font-weight: 900; text-transform: uppercase; letter-spacing: -0.02em;">{model.name}</div>
            <div style="font-size: 11px; color: var(--color-on-surface-dim); margin-top: 4px; line-height: 1.4;">
              {model.algorithm} · {model.project_slug}
            </div>
          </div>

          <!-- Metrics -->
          <div style="display: flex; margin: 0 20px 12px 20px; gap: 0;">
            <div style="flex: 1; padding: 8px 12px; border: 1px solid var(--color-on-surface);">
              <div style="font-size: 8px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.05em; color: var(--color-on-surface-dim);">ACCURACY</div>
              <div style="font-size: 18px; font-weight: 900;">{formatAccuracy(model.accuracy)}</div>
            </div>
            <div style="flex: 1; padding: 8px 12px; border: 1px solid var(--color-on-surface); border-left: none;">
              <div style="font-size: 8px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.05em; color: var(--color-on-surface-dim);">ROWS</div>
              <div style="font-size: 18px; font-weight: 900;">{model.row_count}</div>
            </div>
          </div>

          <!-- Status -->
          <div style="padding: 0 20px 16px 20px; font-size: 10px; margin-top: auto;">
            <span style="color: #007518; font-weight: 900;">ACTIVE</span>
            <span style="color: var(--color-on-surface-dim);"> · {model.created_at ? 'TRAINED ' + formatDate(model.created_at).toUpperCase() : 'NOT TRAINED'}</span>
          </div>

          <!-- Action buttons -->
          <div style="display: flex; border-top: 2px solid var(--color-on-surface);">
            <button onclick={() => openDetail(model)} style="flex: 1; padding: 10px; font-size: 11px; font-weight: 900; text-transform: uppercase; letter-spacing: 0.05em; background: var(--color-primary-container); border: none; border-right: 2px solid var(--color-on-surface); cursor: pointer; font-family: var(--font-family-display); color: var(--color-on-surface);">DETAILS</button>
            <a href="/ui/project/{model.project_slug}" style="flex: 1; padding: 10px; font-size: 11px; font-weight: 900; text-transform: uppercase; letter-spacing: 0.05em; background: transparent; border: none; text-decoration: none; text-align: center; font-family: var(--font-family-display); color: var(--color-on-surface);">CHAT</a>
            <button onclick={() => retrain(model.id)} style="width: 40px; padding: 10px; font-size: 14px; background: transparent; border: none; border-left: 2px solid var(--color-on-surface); cursor: pointer; color: var(--color-on-surface-dim);" title="Retrain">↻</button>
          </div>
        </div>
      {/each}
    </div>
  {/if}
{/if}

</div>
