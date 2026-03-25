// ── Flash alert auto-dismiss ──────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
  const alerts = document.querySelectorAll('.alert');
  alerts.forEach(a => {
    setTimeout(() => fadeOut(a), 4500);
    const closeBtn = a.querySelector('.alert-close');
    if (closeBtn) closeBtn.addEventListener('click', () => fadeOut(a));
  });

  // ── Tab switching ─────────────────────────────────────────────
  document.querySelectorAll('.tab-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      const target = btn.dataset.tab;
      const parent = btn.closest('.tab-container') || document;
      parent.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
      parent.querySelectorAll('.tab-panel').forEach(p => p.classList.remove('active'));
      btn.classList.add('active');
      const panel = parent.querySelector(`#${target}`);
      if (panel) panel.classList.add('active');
    });
  });

  // ── Password visibility toggle ────────────────────────────────
  document.querySelectorAll('.password-toggle').forEach(toggle => {
    toggle.addEventListener('click', () => {
      const input = toggle.previousElementSibling || toggle.parentElement.querySelector('input');
      if (input) {
        const isText = input.type === 'text';
        input.type = isText ? 'password' : 'text';
        toggle.textContent = isText ? '👁️' : '🙈';
      }
    });
  });

  // ── CGPA slider ───────────────────────────────────────────────
  const cgpaInput = document.getElementById('cgpa');
  const cgpaDisplay = document.getElementById('cgpa-display');
  if (cgpaInput && cgpaDisplay) {
    cgpaInput.addEventListener('input', () => {
      cgpaDisplay.textContent = parseFloat(cgpaInput.value).toFixed(1);
    });
  }

  // ── Password strength meter ───────────────────────────────────
  const pwInput = document.getElementById('password');
  const strengthBar = document.getElementById('pw-strength-bar');
  const strengthText = document.getElementById('pw-strength-text');
  if (pwInput && strengthBar) {
    pwInput.addEventListener('input', () => {
      const val = pwInput.value;
      let score = 0;
      if (val.length >= 8)  score++;
      if (/[A-Z]/.test(val)) score++;
      if (/[0-9]/.test(val)) score++;
      if (/[^A-Za-z0-9]/.test(val)) score++;
      const pct = score * 25;
      const colors = ['#EF4444','#F59E0B','#F59E0B','#10B981','#10B981'];
      const labels = ['','Weak','Fair','Good','Strong'];
      strengthBar.style.width = pct + '%';
      strengthBar.style.background = colors[score];
      if (strengthText) strengthText.textContent = labels[score] || '';
    });
  }

  // ── Animate stat numbers ──────────────────────────────────────
  document.querySelectorAll('.stat-value[data-target]').forEach(el => {
    const target = parseInt(el.dataset.target, 10);
    let current = 0;
    const step = Math.max(1, Math.ceil(target / 40));
    const interval = setInterval(() => {
      current = Math.min(current + step, target);
      el.textContent = current;
      if (current >= target) clearInterval(interval);
    }, 30);
  });

  // ── Copy JWT token ────────────────────────────────────────────
  const copyBtn = document.getElementById('copy-token');
  if (copyBtn) {
    copyBtn.addEventListener('click', () => {
      const box = document.querySelector('.token-box');
      if (box) {
        navigator.clipboard.writeText(box.textContent.trim())
          .then(() => { copyBtn.textContent = '✅ Copied!'; setTimeout(() => copyBtn.textContent = '📋 Copy', 2000); });
      }
    });
  }
});

function fadeOut(el) {
  el.style.transition = 'opacity .4s ease';
  el.style.opacity = '0';
  setTimeout(() => el.remove(), 400);
}
