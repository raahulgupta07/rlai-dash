<script lang="ts">
  import { page } from '$app/state';
</script>

<div style="min-height: 100vh; background: var(--color-surface); display: flex; align-items: center; justify-content: center; font-family: var(--font-family-display);">
  <div style="text-align: center; max-width: 500px; padding: 40px;">
    <div class="cli-terminal" style="padding: 20px; margin-bottom: 24px; text-align: left;">
      <div class="cli-line">
        <span class="cli-prompt">$</span>
        <span class="cli-command">dash error</span>
        <span class="cli-output">--code {page.status}</span>
      </div>
      <div class="cli-line">
        <span style="color: #ff6b6b;">&gt;</span>
        <span style="color: #ff6b6b;">{page.error?.message || 'Something went wrong'}</span>
      </div>
      <div class="cli-line" style="margin-top: 8px;">
        <span class="cli-prompt">$</span>
        <span class="cli-cursor"></span>
      </div>
    </div>
    <div style="font-size: 48px; font-weight: 900; color: var(--color-on-surface);">{page.status}</div>
    <div style="font-size: 12px; color: var(--color-on-surface-dim); text-transform: uppercase; letter-spacing: 0.1em; margin-top: 8px;">
      {page.status === 404 ? 'Page not found' : page.status === 403 ? 'Access denied' : 'Error occurred'}
    </div>
    <a href="/ui/projects" style="display: inline-block; margin-top: 20px; padding: 10px 24px; background: var(--color-primary-container); border: 2px solid var(--color-on-surface); font-family: var(--font-family-display); font-size: 12px; font-weight: 900; text-transform: uppercase; text-decoration: none; color: var(--color-on-surface);">
      BACK TO PROJECTS
    </a>
  </div>
</div>
