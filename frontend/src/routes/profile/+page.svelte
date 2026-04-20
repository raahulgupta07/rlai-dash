<script lang="ts">
  import { onMount } from 'svelte';

  let profile = $state<any>(null);
  let loading = $state(true);
  let saving = $state(false);
  let saveMsg = $state('');

  // Editable fields
  let firstName = $state('');
  let lastName = $state('');
  let email = $state('');
  let department = $state('');
  let jobTitle = $state('');
  let phone = $state('');
  let bio = $state('');
  let timezone = $state('UTC');

  function _h(): Record<string, string> {
    const t = typeof localStorage !== 'undefined' ? localStorage.getItem('dash_token') : null;
    return t ? { Authorization: `Bearer ${t}` } : {};
  }

  onMount(async () => {
    const username = localStorage.getItem('dash_user') || '';
    try {
      const res = await fetch(`/api/auth/users/${username}/profile`, { headers: _h() });
      if (res.ok) {
        profile = await res.json();
        firstName = profile.first_name || '';
        lastName = profile.last_name || '';
        email = profile.email || '';
        department = profile.department || '';
        jobTitle = profile.job_title || '';
        phone = profile.phone || '';
        bio = profile.bio || '';
        timezone = profile.timezone || 'UTC';
      }
    } catch {}
    loading = false;
  });

  async function saveProfile() {
    saving = true; saveMsg = '';
    const username = localStorage.getItem('dash_user') || '';
    const params = new URLSearchParams({
      first_name: firstName, last_name: lastName, email, department, job_title: jobTitle, phone, bio, timezone,
    });
    try {
      const res = await fetch(`/api/auth/users/${username}/profile?${params}`, { method: 'PUT', headers: _h() });
      if (res.ok) saveMsg = 'Profile saved!';
      else saveMsg = 'Failed to save';
    } catch { saveMsg = 'Error'; }
    saving = false;
  }
</script>

<div style="padding: 24px; overflow-y: auto; height: 100%;">
  <div style="max-width: 600px; margin: 0 auto;">

    <div style="font-size: 24px; font-weight: 900; text-transform: uppercase; margin-bottom: 20px;">My Profile</div>

    {#if loading}
      <div style="font-size: 12px; color: var(--color-on-surface-dim);">Loading...</div>
    {:else if profile}

      <!-- CLI Status -->
      <div class="cli-terminal" style="margin-bottom: 20px; padding: 10px 14px;">
        <div class="cli-line">
          <span class="cli-prompt">$</span>
          <span class="cli-command">dash whoami</span>
        </div>
        <div class="cli-line">
          <span class="cli-info">USER</span>
          <span class="cli-dim" style="margin-left: 8px;">{profile.username}</span>
        </div>
        <div class="cli-line">
          <span class="cli-info">AUTH</span>
          <span class="cli-dim" style="margin-left: 8px;">{profile.auth_provider || 'local'}</span>
        </div>
        <div class="cli-line">
          <span class="cli-info">SINCE</span>
          <span class="cli-dim" style="margin-left: 8px;">{profile.created_at?.slice(0, 10)}</span>
        </div>
      </div>

      <div style="display: flex; flex-direction: column; gap: 12px;">
        <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 12px;">
          <div>
            <div style="font-size: 9px; font-weight: 700; text-transform: uppercase; margin-bottom: 3px;">FIRST NAME</div>
            <input type="text" bind:value={firstName} style="width: 100%; border: 2px solid var(--color-on-surface); padding: 8px 12px; font-family: var(--font-family-display); font-size: 12px; background: var(--color-surface);" />
          </div>
          <div>
            <div style="font-size: 9px; font-weight: 700; text-transform: uppercase; margin-bottom: 3px;">LAST NAME</div>
            <input type="text" bind:value={lastName} style="width: 100%; border: 2px solid var(--color-on-surface); padding: 8px 12px; font-family: var(--font-family-display); font-size: 12px; background: var(--color-surface);" />
          </div>
        </div>
        <div>
          <div style="font-size: 9px; font-weight: 700; text-transform: uppercase; margin-bottom: 3px;">EMAIL</div>
          <input type="email" bind:value={email} style="width: 100%; border: 2px solid var(--color-on-surface); padding: 8px 12px; font-family: var(--font-family-display); font-size: 12px; background: var(--color-surface);" />
        </div>
        <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 12px;">
          <div>
            <div style="font-size: 9px; font-weight: 700; text-transform: uppercase; margin-bottom: 3px;">DEPARTMENT</div>
            <input type="text" bind:value={department} style="width: 100%; border: 2px solid var(--color-on-surface); padding: 8px 12px; font-family: var(--font-family-display); font-size: 12px; background: var(--color-surface);" />
          </div>
          <div>
            <div style="font-size: 9px; font-weight: 700; text-transform: uppercase; margin-bottom: 3px;">JOB TITLE</div>
            <input type="text" bind:value={jobTitle} style="width: 100%; border: 2px solid var(--color-on-surface); padding: 8px 12px; font-family: var(--font-family-display); font-size: 12px; background: var(--color-surface);" />
          </div>
        </div>
        <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 12px;">
          <div>
            <div style="font-size: 9px; font-weight: 700; text-transform: uppercase; margin-bottom: 3px;">PHONE</div>
            <input type="text" bind:value={phone} style="width: 100%; border: 2px solid var(--color-on-surface); padding: 8px 12px; font-family: var(--font-family-display); font-size: 12px; background: var(--color-surface);" />
          </div>
          <div>
            <div style="font-size: 9px; font-weight: 700; text-transform: uppercase; margin-bottom: 3px;">TIMEZONE</div>
            <input type="text" bind:value={timezone} placeholder="UTC" style="width: 100%; border: 2px solid var(--color-on-surface); padding: 8px 12px; font-family: var(--font-family-display); font-size: 12px; background: var(--color-surface);" />
          </div>
        </div>
        <div>
          <div style="font-size: 9px; font-weight: 700; text-transform: uppercase; margin-bottom: 3px;">BIO</div>
          <textarea bind:value={bio} rows="3" placeholder="Tell us about yourself..." style="width: 100%; border: 2px solid var(--color-on-surface); padding: 8px 12px; font-family: var(--font-family-display); font-size: 12px; background: var(--color-surface); resize: vertical;"></textarea>
        </div>

        {#if saveMsg}
          <div style="font-size: 11px; font-weight: 700; color: {saveMsg === 'Profile saved!' ? 'var(--color-primary)' : 'var(--color-error)'};">{saveMsg}</div>
        {/if}

        <button class="send-btn" onclick={saveProfile} disabled={saving} style="padding: 10px; font-size: 11px; justify-content: center; display: flex; max-width: 200px;">
          {saving ? 'SAVING...' : 'SAVE PROFILE'}
        </button>
      </div>
    {/if}
  </div>
</div>
