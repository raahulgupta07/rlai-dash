const API_BASE = '';

export interface ToolCall {
  name: string;
  status: 'running' | 'done' | 'error';
  args?: Record<string, unknown>;
  duration?: string;
  sqlQuery?: string;
  tokens?: { input: number; output: number };
}

export async function sendMessage(
  message: string,
  sessionId: string,
  onToken: (text: string) => void,
  onDone: () => void,
  onError: (error: string) => void,
  onToolCall?: (tool: ToolCall) => void,
  projectSlug?: string,
  reasoning?: string,
  analysisType?: string,
  signal?: AbortSignal
): Promise<void> {
  try {
    const formData = new FormData();
    formData.append('message', message);
    formData.append('stream', 'true');
    formData.append('session_id', sessionId);
    if (reasoning) formData.append('reasoning', reasoning);
    if (analysisType) formData.append('analysis_type', analysisType);

    const token = typeof localStorage !== 'undefined' ? localStorage.getItem('dash_token') : null;
    const headers: Record<string, string> = {};
    if (token) headers['Authorization'] = `Bearer ${token}`;

    const endpoint = projectSlug ? `${API_BASE}/api/projects/${projectSlug}/chat` : `${API_BASE}/teams/dash/runs`;
    const response = await fetch(endpoint, {
      method: 'POST',
      headers,
      body: formData,
      signal
    });

    if (!response.ok) {
      const text = await response.text();
      onError(`Error ${response.status}: ${text}`);
      return;
    }

    const reader = response.body?.getReader();
    if (!reader) { onError('No response body'); return; }

    const decoder = new TextDecoder();
    let buffer = '';
    let currentEvent = '';
    const toolTimers: Record<string, number> = {};

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split('\n');
      buffer = lines.pop() || '';

      for (const line of lines) {
        if (line.startsWith('event: ')) {
          currentEvent = line.slice(7).trim();
          continue;
        }

        if (!line.startsWith('data: ')) continue;
        const raw = line.slice(6).trim();
        if (raw === '[DONE]') continue;

        try {
          const data = JSON.parse(raw);

          switch (currentEvent) {
            // ── Member tool calls (Analyst/Engineer running tools) ──
            case 'ToolCallStarted': {
              const tool = data.tool;
              if (tool && onToolCall) {
                const name = tool.tool_name || 'unknown';
                toolTimers[name] = Date.now();
                onToolCall({ name, status: 'running', args: tool.tool_args });
              }
              break;
            }

            case 'ToolCallCompleted': {
              const tool = data.tool;
              if (tool && onToolCall) {
                const name = tool.tool_name || 'unknown';
                const start = toolTimers[name];
                const duration = start ? ((Date.now() - start) / 1000).toFixed(2) + 's' : undefined;
                const sqlQuery = (name === 'run_sql_query' || name === 'run_sql')
                  ? (tool.tool_args?.query || tool.tool_args?.sql || undefined)
                  : undefined;
                onToolCall({ name, status: 'done', duration, sqlQuery });
              }
              break;
            }

            // ── Team tool calls (Leader delegating to member) ──
            case 'TeamToolCallStarted': {
              const tool = data.tool;
              if (tool && onToolCall) {
                const name = tool.tool_name || 'unknown';
                toolTimers[`team_${name}`] = Date.now();
                onToolCall({ name, status: 'running', args: tool.tool_args });
              }
              break;
            }

            case 'TeamToolCallCompleted': {
              const tool = data.tool;
              if (tool && onToolCall) {
                const name = tool.tool_name || 'unknown';
                const start = toolTimers[`team_${name}`];
                const duration = start ? ((Date.now() - start) / 1000).toFixed(2) + 's' : undefined;
                onToolCall({ name, status: 'done', duration });
              }
              break;
            }

            // ── Member run started ──
            case 'RunStarted': {
              if (data.agent_name && onToolCall) {
                onToolCall({ name: `${data.agent_name} agent`, status: 'running' });
              }
              break;
            }

            case 'RunCompleted': {
              if (data.agent_name && onToolCall) {
                onToolCall({ name: `${data.agent_name} agent`, status: 'done' });
              }
              break;
            }

            // ── Show content from TeamRunContent OR RunContent ──
            case 'TeamRunContent':
            case 'RunContent': {
              if (data.content && typeof data.content === 'string') {
                onToken(data.content);
              }
              break;
            }

            default:
              break;
          }
        } catch {
          // Not JSON — skip
        }
      }
    }
    onDone();
  } catch (err) {
    onError(err instanceof Error ? err.message : 'Connection failed');
  }
}

export function generateSessionId(): string {
  return crypto.randomUUID();
}
