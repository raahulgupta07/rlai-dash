<script lang="ts">
  import { onMount, onDestroy } from 'svelte';

  let { tables = [], relationships = [], memories = [], rules = [], onNodeClick = (node: any) => {} }: {
    tables: any[];
    relationships: any[];
    memories: any[];
    rules: any[];
    onNodeClick?: (node: any) => void;
  } = $props();

  let chartEl: HTMLDivElement;
  let chart: any;

  function buildGraph() {
    const nodes: any[] = [];
    const links: any[] = [];
    const categories = [
      { name: 'Table', itemStyle: { color: '#00fc40' } },
      { name: 'Memory', itemStyle: { color: '#ff9d00' } },
      { name: 'Rule', itemStyle: { color: '#00b4d8' } },
      { name: 'Column', itemStyle: { color: '#555' } },
    ];

    // Table nodes
    tables.forEach((t: any, i: number) => {
      nodes.push({
        id: `table_${t.name}`,
        name: t.name,
        category: 0,
        symbolSize: Math.max(30, Math.min(60, 20 + Math.sqrt(t.rows || 0) * 5)),
        value: t.rows || 0,
        label: { show: true, fontSize: 11, fontWeight: 'bold', color: '#e0e0e0', formatter: (p: any) => `${p.name}\n${t.rows} rows` },
        itemStyle: { color: '#1a1a1a', borderColor: '#00fc40', borderWidth: 2.5 },
        data: { type: 'table', ...t },
      });

      // Column nodes for each table (top 6)
      const cols = t.inspectData?.columns || [];
      cols.slice(0, 6).forEach((col: any, ci: number) => {
        const colId = `col_${t.name}_${col.name}`;
        nodes.push({
          id: colId,
          name: col.name,
          category: 3,
          symbolSize: 10,
          label: { show: true, fontSize: 8, color: '#8a8a9a', position: 'right' },
          itemStyle: { color: '#333', borderColor: '#555', borderWidth: 1 },
          data: { type: 'column', table: t.name, ...col },
        });
        links.push({
          source: `table_${t.name}`,
          target: colId,
          lineStyle: { color: '#333', width: 1 },
        });
      });
    });

    // Relationship links between tables
    relationships.forEach((rel: any) => {
      const src = `table_${rel.from_table}`;
      const tgt = `table_${rel.to_table}`;
      if (nodes.some(n => n.id === src) && nodes.some(n => n.id === tgt)) {
        links.push({
          source: src,
          target: tgt,
          lineStyle: { color: '#00fc40', width: 2, type: 'dashed' },
          label: { show: true, formatter: `${rel.from_column} → ${rel.to_column}`, fontSize: 8, color: '#8a8a9a' },
        });
      }
    });

    // Memory nodes
    memories.slice(0, 6).forEach((m: any, i: number) => {
      const memId = `mem_${i}`;
      nodes.push({
        id: memId,
        name: (m.fact || '').slice(0, 30) + ((m.fact || '').length > 30 ? '...' : ''),
        category: 1,
        symbolSize: 18,
        symbol: 'rect',
        label: { show: true, fontSize: 7, color: '#ff9d00', position: 'bottom', width: 100, overflow: 'truncate' },
        itemStyle: { color: '#1a1a1a', borderColor: '#ff9d00', borderWidth: 1.5 },
        data: { type: 'memory', ...m },
      });
      // Link to nearest table
      if (tables.length > 0) {
        links.push({
          source: memId,
          target: `table_${tables[i % tables.length].name}`,
          lineStyle: { color: '#ff9d00', width: 0.5, type: 'dotted', opacity: 0.4 },
        });
      }
    });

    // Rule nodes
    rules.slice(0, 5).forEach((r: any, i: number) => {
      const ruleId = `rule_${i}`;
      nodes.push({
        id: ruleId,
        name: (r.name || '').slice(0, 25) + ((r.name || '').length > 25 ? '...' : ''),
        category: 2,
        symbolSize: 16,
        symbol: 'diamond',
        label: { show: true, fontSize: 7, color: '#00b4d8', position: 'bottom', width: 90, overflow: 'truncate' },
        itemStyle: { color: '#1a1a1a', borderColor: '#00b4d8', borderWidth: 1.5 },
        data: { type: 'rule', ...r },
      });
      // Link to a table
      if (tables.length > 0) {
        links.push({
          source: ruleId,
          target: `table_${tables[i % tables.length].name}`,
          lineStyle: { color: '#00b4d8', width: 0.5, type: 'dotted', opacity: 0.3 },
        });
      }
    });

    return { nodes, links, categories };
  }

  function renderChart() {
    if (!chartEl || !chart) return;
    const { nodes, links, categories } = buildGraph();

    chart.setOption({
      backgroundColor: '#1a1a1a',
      tooltip: {
        trigger: 'item',
        backgroundColor: '#2a2a2a',
        borderColor: '#00fc40',
        borderWidth: 1,
        textStyle: { color: '#e0e0e0', fontFamily: 'Space Grotesk, monospace', fontSize: 11 },
        formatter: (params: any) => {
          const d = params.data?.data;
          if (!d) return params.name;
          if (d.type === 'table') return `<b>${d.name}</b><br/>Rows: ${d.rows}<br/>Cols: ${d.columns}<br/><span style="font-size:10px;color:#8a8a9a;">Click to inspect</span>`;
          if (d.type === 'column') return `<b>${d.name}</b><br/>Type: ${d.type || d.type}<br/>Table: ${d.table}<br/>Nullable: ${d.nullable ? 'Yes' : 'No'}`;
          if (d.type === 'memory') return `<b>Memory</b><br/>${d.fact}<br/><span style="font-size:10px;">Scope: ${d.scope || 'project'}</span>`;
          if (d.type === 'rule') return `<b>${d.name}</b><br/>${(d.definition || '').slice(0, 100)}`;
          return params.name;
        }
      },
      legend: {
        data: categories.map(c => c.name),
        right: 10,
        top: 6,
        textStyle: { color: '#8a8a9a', fontFamily: 'Space Grotesk, monospace', fontSize: 9 },
        itemWidth: 10,
        itemHeight: 10,
      },
      series: [{
        type: 'graph',
        layout: 'force',
        data: nodes,
        links: links,
        categories: categories,
        roam: true,
        draggable: true,
        force: {
          repulsion: 300,
          gravity: 0.1,
          edgeLength: [80, 200],
          friction: 0.6,
        },
        emphasis: {
          focus: 'adjacency',
          lineStyle: { width: 3 },
          itemStyle: { borderWidth: 4 },
        },
        lineStyle: { curveness: 0.15 },
      }],
    });

    chart.on('click', (params: any) => {
      if (params.data?.data) {
        onNodeClick(params.data.data);
      }
    });
  }

  onMount(async () => {
    const echarts = await import('echarts');
    chart = echarts.init(chartEl, undefined, { renderer: 'canvas' });
    renderChart();
    window.addEventListener('resize', () => chart?.resize());
  });

  onDestroy(() => {
    chart?.dispose();
  });

  $effect(() => {
    // Re-render when data changes
    if (tables && chart) renderChart();
  });
</script>

<div bind:this={chartEl} style="width: 100%; height: 450px; border: 2px solid #383832; border-bottom-width: 4px;"></div>
