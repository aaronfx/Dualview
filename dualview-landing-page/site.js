'use strict';

// Enable the local-only form after its submit handler is installed.
const briefForm = document.querySelector('#brief-form');
if (briefForm) {
  briefForm.addEventListener('submit', event => {
    event.preventDefault();
    if (!briefForm.reportValidity()) return;
    const form = new FormData(briefForm);
    const project = String(form.get('project') || '').trim();
    const summary = String(form.get('summary') || '').trim();
    const status = document.querySelector('#brief-status');
    if (!project || !summary) {
      status.textContent = 'Please enter a project name and describe the problem; spaces alone are not enough.';
      return;
    }
    const text = `Project brief for CyronTech LTD\n\nProject: ${project}\nType: ${form.get('type')}\n\nProblem and audience:\n${summary}\n\nPrepared locally. This brief has not been sent to CyronTech.\n`;
    const url = URL.createObjectURL(new Blob([text], { type: 'text/plain;charset=utf-8' }));
    const link = document.createElement('a'); link.href = url; link.download = 'cyrontech-project-brief.txt'; link.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
    status.textContent = 'Your brief is ready to download. Attach it to an email to contact@cyrontech.online when you are ready to share it.';
  });
  briefForm.querySelector('fieldset').disabled = false;
}

const reduced = window.matchMedia('(prefers-reduced-motion: reduce)');
const environment = { reduced: () => reduced.matches, hidden: () => document.hidden };
const demos = [];
function watchDemo(root, controller) {
  demos.push(controller);
  if ('IntersectionObserver' in window) {
    new IntersectionObserver(entries => controller.setVisible(entries[0].isIntersecting && entries[0].intersectionRatio >= .15),
      { threshold: [0, .15] }).observe(root);
  } else controller.setVisible(true);
}

const wide = document.querySelector('#wide-video');
const tall = document.querySelector('#tall-video');
const toggle = document.querySelector('#video-toggle');
const capture = document.querySelector('#capture-toggle');
if (wide && tall && toggle && capture && typeof createMediaDemo === 'function') {
  const root = document.querySelector('.mini-demo');
  const controller = createMediaDemo({ videos: [wide, tall], environment,
    onState({ playing, pending }) {
      root.classList.toggle('is-playing', playing);
      toggle.textContent = pending ? 'Stop loading demo' : playing ? 'Pause demo Ⅱ' : 'Play demo ▶';
      toggle.setAttribute('aria-label', pending ? 'Stop loading DualView sample video' : playing ? 'Pause DualView sample video' : 'Play DualView sample video');
      capture.setAttribute('aria-label', pending ? 'Stop loading DualView recording demo' : playing ? 'Pause DualView recording demo' : 'Play DualView recording demo');
      document.querySelector('[data-rec]').textContent = playing ? 'REC' : 'DEMO';
    },
    onError(message) { document.querySelector('#demo-status').textContent = message; }
  });
  [toggle, capture].forEach(button => { button.addEventListener('click', () => controller.toggle()); button.disabled = false; });
  wide.addEventListener('timeupdate', () => {
    const seconds = Math.floor(wide.currentTime);
    document.querySelector('[data-capture-timer]').textContent = `${String(Math.floor(seconds / 60)).padStart(2, '0')}:${String(seconds % 60).padStart(2, '0')}`;
  });
  watchDemo(root, controller);
}

const phoneVideo = document.querySelector('#phone-video');
const phoneToggle = document.querySelector('#phone-toggle');
if (phoneVideo && phoneToggle && typeof createMediaDemo === 'function') {
  const controller = createMediaDemo({ videos: [phoneVideo], environment,
    onState({ playing, pending }) {
      document.querySelector('.modern-phone').classList.toggle('phone-playing', playing);
      phoneToggle.setAttribute('aria-label', pending ? 'Stop loading phone video demo' : playing ? 'Pause phone video demo' : 'Play phone video demo');
      document.querySelector('[data-phone-rec]').textContent = playing ? 'REC' : 'DEMO';
      document.querySelector('.phone-caption').textContent = pending ? 'Loading sample video' : playing ? 'Pause sample video' : 'Play sample video';
    },
    onError(message) { document.querySelector('#phone-demo-status').textContent = message; }
  });
  phoneToggle.addEventListener('click', () => controller.toggle()); phoneToggle.disabled = false;
  watchDemo(phoneVideo, controller);
}
document.addEventListener('visibilitychange', () => demos.forEach(d => d.visibilityChanged()));
reduced.addEventListener('change', () => {
  demos.forEach(d => d.preferenceChanged());
  if (reduced.matches) document.querySelectorAll('.before').forEach(el => el.classList.remove('before'));
});
if ('IntersectionObserver' in window && !reduced.matches) {
  const observer = new IntersectionObserver(entries => entries.forEach(entry => {
    if (entry.isIntersecting) { entry.target.classList.remove('before'); observer.unobserve(entry.target); }
  }), { threshold: .08 });
  document.querySelectorAll('.reveal').forEach(el => { el.classList.add('before'); observer.observe(el); });
}
document.querySelectorAll('.mobile-menu a').forEach(link => link.addEventListener('click', () => {
  document.querySelector('.mobile-menu').open = false;
}));
