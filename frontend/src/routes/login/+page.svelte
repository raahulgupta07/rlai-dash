<script lang="ts">
  import '../../app.css';
  import { onMount } from 'svelte';

  let username = $state('');
  let password = $state('');
  let showPassword = $state(false);
  let error = $state('');
  let loading = $state(false);
  let showTransition = $state(false);
  let isRegister = $state(false);
  let transLines = $state<{text: string; done: boolean}[]>([]);

  // Keycloak SSO
  let oidcEnabled = $state(false);

  // Terminal animation state
  let terminalLines = $state<{text: string; typed: string; done: boolean; color?: string}[]>([]);
  let cursorVisible = $state(true);
  let bootDone = $state(false);

  const BOOT_SEQUENCE = [
    { text: '[DASH] Waking up...', delay: 70, color: 'dim' },
    { text: '', delay: 200, color: '' },
    { text: '🤖 Hey! I\'m Dash.', delay: 55, color: '' },
    { text: '   Your self-learning data agent.', delay: 40, color: 'dim' },
    { text: '', delay: 300, color: '' },
    { text: '   Let me get everything ready...', delay: 45, color: 'dim' },
    { text: '', delay: 200, color: '' },
    { text: '   ◆ Brain ················ ONLINE', delay: 35, color: 'green' },
    { text: '   ◆ Memory ·············· LOADED', delay: 40, color: 'green' },
    { text: '   ◆ Knowledge ··········· 12 TOPICS', delay: 35, color: 'green' },
    { text: '   ◆ Reasoning ··········· ACTIVE', delay: 40, color: 'green' },
    { text: '   ◆ Data Vault ·········· SECURED', delay: 35, color: 'green' },
    { text: '', delay: 300, color: '' },
    { text: '   All systems go. I can think,', delay: 40, color: '' },
    { text: '   analyze, and learn from mistakes.', delay: 40, color: '' },
    { text: '', delay: 400, color: '' },
    { text: 'DASH', delay: 120, color: 'big' },
    { text: 'DATA', delay: 120, color: 'big' },
    { text: 'AGENT', delay: 120, color: 'big' },
    { text: '', delay: 300, color: '' },
    { text: '   Ready when you are, operator.', delay: 45, color: 'dim' },
    { text: '   Login to start asking questions →', delay: 40, color: 'blink' },
  ];

  onMount(() => {
    // Check if returning from OIDC with token
    const params = new URLSearchParams(window.location.search);
    if (params.get('token') && params.get('username')) {
      localStorage.setItem('dash_token', params.get('token')!);
      localStorage.setItem('dash_user', params.get('username')!);
      window.location.href = '/ui/home';
      return;
    }

    // Check OIDC config
    fetch('/api/auth/oidc/config').then(r => r.json()).then(d => { oidcEnabled = d.enabled; }).catch(() => {});

    // Cursor blink
    const cursorInterval = setInterval(() => { cursorVisible = !cursorVisible; }, 530);

    // Run boot sequence
    runBootSequence();

    return () => clearInterval(cursorInterval);
  });

  async function runBootSequence() {
    for (const line of BOOT_SEQUENCE) {
      const entry = { text: line.text, typed: '', done: false, color: line.color };
      terminalLines = [...terminalLines, entry];

      // Type each character
      for (let i = 0; i < line.text.length; i++) {
        await sleep(line.delay);
        terminalLines = [
          ...terminalLines.slice(0, -1),
          { ...entry, typed: line.text.slice(0, i + 1) }
        ];
      }

      // Mark done
      terminalLines = [
        ...terminalLines.slice(0, -1),
        { ...entry, typed: line.text, done: true }
      ];

      await sleep(100);
    }
    bootDone = true;
  }

  function sleep(ms: number): Promise<void> {
    return new Promise(r => setTimeout(r, ms));
  }

  async function register() {
    if (!username || !password) { error = 'All fields required'; return; }
    if (password.length < 4) { error = 'Password must be at least 4 characters'; return; }
    loading = true; error = '';
    try {
      const res = await fetch(`/api/auth/register?username=${encodeURIComponent(username)}&password=${encodeURIComponent(password)}`, { method: 'POST' });
      if (!res.ok) { const d = await res.json(); error = d.detail || 'Registration failed'; loading = false; return; }
      // Auto-login after register
      isRegister = false;
      await login();
      return;
    } catch { error = 'Connection failed'; }
    loading = false;
  }

  async function login() {
    if (!username || !password) { error = 'All fields required'; return; }
    loading = true; error = '';
    try {
      const res = await fetch('/api/auth/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username, password })
      });
      const data = await res.json();
      if (!res.ok) { error = data.detail || 'Authentication failed'; loading = false; return; }
      localStorage.setItem('dash_token', data.token);
      localStorage.setItem('dash_user', data.username);

      // Go directly to home (home page has its own boot animation)
      window.location.href = '/ui/home';
      return;
    } catch (e: any) { error = e.message || 'Connection failed'; }
    loading = false;
  }

  function handleKey(e: KeyboardEvent) { if (e.key === 'Enter') login(); }
</script>

<div class="login-page">

  <!-- Top Bar -->
  <header class="login-header">
    <div style="display: flex; align-items: center; gap: 10px;">
      <div class="login-logo-box">
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <line x1="12" y1="2" x2="12" y2="6"/><circle cx="12" cy="2" r="1" fill="currentColor"/>
          <rect x="3" y="11" width="18" height="10"/><line x1="12" y1="6" x2="12" y2="11"/>
          <rect x="7" y="14" width="3" height="2" fill="currentColor"/><rect x="14" y="14" width="3" height="2" fill="currentColor"/>
          <line x1="9" y1="18" x2="15" y2="18"/>
        </svg>
      </div>
      <div class="login-logo-badge">DASH</div>
    </div>
    <div class="login-header-right">SECURE_TERMINAL</div>
  </header>

  <!-- Main -->
  <div class="login-main">
    <div class="login-container">

      <!-- Left: Terminal -->
      <div class="login-branding">
        <!-- Terminal Window -->
        <div class="terminal-window">
          <div class="terminal-titlebar">
            <span class="terminal-dot" style="background: #ff5f56;"></span>
            <span class="terminal-dot" style="background: #ffbd2e;"></span>
            <span class="terminal-dot" style="background: #27c93f;"></span>
            <span style="margin-left: 8px; font-size: 10px; opacity: 0.5;">dash — thinking...</span>
          </div>
          <div class="terminal-body">
            <!-- Robot inside terminal -->
            <div class="robot-icon" style="margin-bottom: 12px;">
              <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="#00fc40" stroke-width="1.5">
                <line x1="12" y1="2" x2="12" y2="6" class="antenna"/>
                <circle cx="12" cy="2" r="1" fill="#00fc40" class="antenna-dot"/>
                <rect x="3" y="11" width="18" height="10"/>
                <line x1="12" y1="6" x2="12" y2="11"/>
                <rect x="7" y="14" width="3" height="2" fill="#00fc40" class="eye-left"/>
                <rect x="14" y="14" width="3" height="2" fill="#00fc40" class="eye-right"/>
                <line x1="9" y1="18" x2="15" y2="18"/>
              </svg>
            </div>
            {#each terminalLines as line}
              {#if line.color === 'big'}
                <div class="terminal-big">{line.typed}</div>
              {:else if line.color === 'blink'}
                <div class="terminal-line terminal-blink">{line.typed}{#if !line.done}<span class="terminal-cursor" class:terminal-cursor-visible={cursorVisible}>_</span>{/if}</div>
              {:else if line.color === 'dim'}
                <div class="terminal-line terminal-dim">{line.typed}</div>
              {:else if line.color === 'green'}
                <div class="terminal-line">
                  {#if line.typed.endsWith('OK') || line.typed.endsWith('READY') || line.typed.endsWith('ACTIVE')}
                    {line.typed.slice(0, -line.typed.split(' ').pop()?.length)}<span class="terminal-ok">{line.typed.split(' ').pop()}</span>
                  {:else}
                    {line.typed}{#if !line.done}<span class="terminal-cursor" class:terminal-cursor-visible={cursorVisible}>_</span>{/if}
                  {/if}
                </div>
              {:else if line.text === ''}
                <div class="terminal-line">&nbsp;</div>
              {:else}
                <div class="terminal-line">{line.typed}{#if !line.done}<span class="terminal-cursor" class:terminal-cursor-visible={cursorVisible}>_</span>{/if}</div>
              {/if}
            {/each}
            {#if !bootDone && terminalLines.length === 0}
              <div class="terminal-line"><span class="terminal-cursor terminal-cursor-visible">_</span></div>
            {/if}
          </div>
        </div>

      </div>

      <!-- Right: Login Form -->
      <div class="login-form-card">
        <div style="padding: 32px 28px;">
          <div class="login-title">ACCESS_PORTAL</div>
          <div class="login-subtitle">AUTHORIZED ACCESS ONLY. LOGGING ACTIVE.</div>

          <div style="margin-bottom: 16px;">
            <div class="tag-label" style="margin-bottom: 6px; font-size: 9px;">OPERATOR_ID</div>
            <input type="text" bind:value={username} onkeydown={handleKey} placeholder="Enter credentials" class="login-input" />
          </div>

          <div style="margin-bottom: 20px;">
            <div class="tag-label" style="margin-bottom: 6px; font-size: 9px;">ACCESS_KEY</div>
            <div style="position: relative;">
              <input type={showPassword ? 'text' : 'password'} bind:value={password} onkeydown={handleKey} placeholder="Enter passphrase" class="login-input" style="padding-right: 60px;" />
              <button onclick={() => showPassword = !showPassword} class="login-show-btn">{showPassword ? 'HIDE' : 'SHOW'}</button>
            </div>
          </div>

          {#if error}
            <div class="login-error">{error}</div>
          {/if}

          <button onclick={() => isRegister ? register() : login()} disabled={loading} class="login-btn">
            {loading ? 'PROCESSING...' : isRegister ? 'CREATE_ACCOUNT' : 'INITIATE_AUTHENTICATION'}
          </button>

          {#if oidcEnabled}
            <div style="margin-top: 12px; padding-top: 12px; border-top: 1px solid rgba(255,255,255,0.2);">
              <button onclick={async () => {
                const callbackUrl = window.location.origin + '/api/auth/oidc/callback';
                const res = await fetch(`/api/auth/oidc/login?redirect_uri=${encodeURIComponent(callbackUrl)}`);
                if (res.ok) { const d = await res.json(); window.location.href = d.url; }
              }} style="width: 100%; padding: 10px; background: rgba(255,255,255,0.1); border: 1px solid rgba(255,255,255,0.3); color: white; cursor: pointer; font-family: var(--font-family-display); font-size: 11px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.08em;">
                LOGIN WITH SSO (KEYCLOAK)
              </button>
            </div>
          {/if}

          <div class="login-footer-link">
            <button onclick={() => { isRegister = !isRegister; error = ''; }} style="background: none; border: none; cursor: pointer; font-family: var(--font-family-display); font-size: 10px; color: var(--color-primary-container); text-transform: uppercase; letter-spacing: 0.08em;">
              {isRegister ? 'ALREADY HAVE ACCESS? LOGIN' : 'NEW USER? REGISTER'}
            </button>
          </div>
        </div>
      </div>
    </div>
  </div>

  <!-- Transition Screen (after login) -->
  {#if showTransition}
    <div style="position: fixed; inset: 0; background: #0a0a0f; z-index: 999; display: flex; align-items: center; justify-content: center; padding: 20px;">
      <div style="width: 100%; max-width: 700px;">
        <!-- Terminal window -->
        <div style="border: 1px solid rgba(255,255,255,0.15); background: #0d0d14; overflow: hidden;">
          <!-- Title bar -->
          <div style="display: flex; align-items: center; gap: 6px; padding: 8px 12px; background: #1a1a24; border-bottom: 1px solid rgba(255,255,255,0.08);">
            <span style="width: 10px; height: 10px; background: #ff5f56; border-radius: 50% !important; display: inline-block;"></span>
            <span style="width: 10px; height: 10px; background: #ffbd2e; border-radius: 50% !important; display: inline-block;"></span>
            <span style="width: 10px; height: 10px; background: #27c93f; border-radius: 50% !important; display: inline-block;"></span>
            <span style="margin-left: 8px; font-size: 10px; color: rgba(255,255,255,0.3); font-family: 'Space Grotesk', monospace;">dash@workspace — initializing</span>
          </div>
          <!-- Terminal body -->
          <div style="padding: 20px; min-height: 380px; max-height: 500px; overflow-y: auto; font-family: 'Space Grotesk', monospace; font-size: 12px; line-height: 1.8;">
            <!-- Robot -->
            <div class="robot-icon" style="margin-bottom: 16px;">
              <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="#00fc40" stroke-width="1.5">
                <line x1="12" y1="2" x2="12" y2="6" class="antenna"/>
                <circle cx="12" cy="2" r="1" fill="#00fc40" class="antenna-dot"/>
                <rect x="3" y="11" width="18" height="10"/>
                <line x1="12" y1="6" x2="12" y2="11"/>
                <rect x="7" y="14" width="3" height="2" fill="#00fc40" class="eye-left"/>
                <rect x="14" y="14" width="3" height="2" fill="#00fc40" class="eye-right"/>
                <line x1="9" y1="18" x2="15" y2="18"/>
              </svg>
            </div>
            {#each transLines as line, i}
              {#if line.text === ''}
                <div style="height: 8px;"></div>
              {:else if line.text.startsWith('[DASH]')}
                <div style="color: #00fc40; font-weight: 700; font-size: 14px; padding: 1px 0;">{line.text}</div>
              {:else if line.text.startsWith('>')}
                <div style="color: rgba(255,255,255,0.8); font-weight: 700; padding: 1px 0; margin-top: 2px;">{line.text}</div>
              {:else if line.text.startsWith('Entering')}
                <div style="color: #00fc40; font-weight: 900; font-size: 13px; padding: 1px 0;">{line.text}</div>
              {:else if line.text.includes('···')}
                <div style="color: rgba(255,255,255,0.5); padding: 1px 0;">
                  {line.text.slice(0, line.text.lastIndexOf(' ') + 1)}<span style="color: #00fc40; font-weight: 700;">{line.text.split(' ').pop()}</span>
                </div>
              {:else}
                <div style="color: rgba(255,255,255,0.45); padding: 1px 0;">{line.text}</div>
              {/if}
            {/each}
            {#if transLines.length > 0 && transLines.length < 26}
              <span style="color: #00fc40; animation: termBlink 1s step-end infinite;">_</span>
            {/if}
          </div>
          <!-- Progress bar at bottom of terminal -->
          <div style="height: 3px; background: rgba(255,255,255,0.05);">
            <div style="background: #00fc40; height: 100%; width: {Math.min(100, transLines.length * 4)}%; transition: width 0.2s ease-out;"></div>
          </div>
        </div>
        <!-- Status text below terminal -->
        <div style="display: flex; justify-content: space-between; padding: 8px 4px; font-size: 9px; color: rgba(255,255,255,0.2); font-family: 'Space Grotesk', monospace; text-transform: uppercase; letter-spacing: 0.1em;">
          <span>DASH v1.0</span>
          <span>SECURE SESSION</span>
          <span>ENCRYPTED</span>
        </div>
      </div>
    </div>
  {/if}

  <!-- Footer -->
  <footer class="login-footer">
    <span>&copy; 2026 DASH AI</span>
    <span>SECURE_TERMINAL</span>
  </footer>
</div>

<style>
  .login-page { min-height: 100vh; background: #1a1a1e; font-family: 'Space Grotesk', monospace, sans-serif; display: flex; flex-direction: column; }
  .login-header { display: flex; align-items: center; justify-content: space-between; padding: 12px 24px; border-bottom: 1px solid rgba(255,255,255,0.08); }
  .login-header-right { color: rgba(255,255,255,0.3); font-size: 11px; letter-spacing: 0.15em; text-transform: uppercase; font-weight: 700; }
  .login-logo-box { background: #00fc40; color: #1a1a1e; padding: 6px; border: 2px solid #00fc40; display: flex; align-items: center; justify-content: center; }
  .login-logo-badge { background: #00fc40; color: #1a1a1e; padding: 4px 14px; font-size: 13px; font-weight: 900; letter-spacing: 0.08em; }
  .login-main { flex: 1; display: flex; align-items: center; justify-content: center; padding: 24px; }
  .login-container { display: flex; gap: 60px; align-items: center; max-width: 1050px; width: 100%; }
  .login-footer { display: flex; align-items: center; justify-content: space-between; padding: 10px 24px; border-top: 1px solid rgba(255,255,255,0.08); color: rgba(255,255,255,0.2); font-size: 10px; letter-spacing: 0.1em; text-transform: uppercase; }

  /* Branding / Terminal */
  .login-branding { flex: 1; display: none; flex-direction: column; }
  @media (min-width: 768px) { .login-branding { display: flex; } }

  .terminal-window { border: 1px solid rgba(255,255,255,0.15); background: #0d0d12; overflow: hidden; }
  .terminal-titlebar { display: flex; align-items: center; gap: 6px; padding: 8px 12px; background: #2a2a30; border-bottom: 1px solid rgba(255,255,255,0.08); }
  .terminal-dot { width: 10px; height: 10px; border-radius: 50% !important; display: inline-block; }
  .terminal-body { padding: 16px; min-height: 320px; font-size: 12px; line-height: 1.7; font-family: 'Space Grotesk', monospace; }
  .terminal-line { color: rgba(255,255,255,0.6); white-space: nowrap; }
  .terminal-ok { color: #00fc40; font-weight: 700; }
  .terminal-dim { color: rgba(255,255,255,0.35); font-size: 12px; letter-spacing: 0.08em; }
  .terminal-big { color: rgba(255,255,255,0.95); font-size: 52px; font-weight: 900; line-height: 0.95; letter-spacing: -0.03em; }
  .terminal-blink { color: #00fc40; animation: termBlink 1s step-end infinite; }
  .terminal-cursor { color: #00fc40; font-weight: 400; opacity: 0; }
  .terminal-cursor-visible { opacity: 1; }

  @keyframes termBlink { 0%, 100% { opacity: 1; } 50% { opacity: 0.3; } }

  /* Login Form */
  .login-form-card { width: 420px; max-width: 100%; background: #feffd6; border: 2px solid #383832; }
  .login-title { font-size: 28px; font-weight: 900; text-transform: uppercase; letter-spacing: -0.01em; margin-bottom: 6px; color: #383832; }
  .login-subtitle { font-size: 11px; text-transform: uppercase; letter-spacing: 0.1em; color: #6b6b60; margin-bottom: 28px; }
  .login-input { width: 100%; background: #feffd6; border: 2px solid #383832; padding: 12px 14px; font-family: 'Space Grotesk', monospace; font-size: 14px; outline: none; color: #383832; }
  .login-input:focus { border-color: #007518; }
  .login-input::placeholder { color: #a0a090; }
  .login-show-btn { position: absolute; right: 12px; top: 50%; transform: translateY(-50%); background: none; border: none; font-family: 'Space Grotesk', monospace; font-size: 11px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.08em; cursor: pointer; color: #6b6b60; }
  .login-error { font-size: 11px; color: #be2d06; margin-bottom: 12px; font-weight: 700; text-transform: uppercase; }
  .login-btn { width: 100%; background: #00fc40; color: #383832; border: none; padding: 14px; font-family: 'Space Grotesk', monospace; font-size: 13px; font-weight: 900; text-transform: uppercase; letter-spacing: 0.12em; cursor: pointer; }
  .login-btn:hover { opacity: 0.9; }
  .login-btn:disabled { opacity: 0.5; cursor: not-allowed; }
  .login-footer-link { border-top: 1px solid #383832; margin-top: 20px; padding-top: 14px; text-align: center; font-size: 10px; color: #6b6b60; text-transform: uppercase; letter-spacing: 0.1em; }

  /* Robot animation */
  .robot-icon { animation: robotFloat 3s ease-in-out infinite; }
  .robot-icon .antenna-dot { animation: antennaPulse 1.5s ease-in-out infinite; }
  .robot-icon .eye-left, .robot-icon .eye-right { animation: eyeBlink 4s ease-in-out infinite; }
  .robot-icon .eye-right { animation-delay: 0.1s; }
  @keyframes robotFloat { 0%, 100% { transform: translateY(0); } 50% { transform: translateY(-6px); } }
  @keyframes antennaPulse { 0%, 100% { opacity: 0.4; } 50% { opacity: 1; } }
  @keyframes eyeBlink { 0%, 42%, 44%, 100% { height: 2px; } 43% { height: 0.5px; } }
</style>
