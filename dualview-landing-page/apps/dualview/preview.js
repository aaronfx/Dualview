const outputPanel = document.querySelector('.outputs');
const formatButtons = document.querySelectorAll('[data-format]');
for (const button of formatButtons) {
  button.addEventListener('click', () => {
    outputPanel.dataset.focus = button.dataset.format;
    for (const item of formatButtons) item.setAttribute('aria-pressed', String(item === button));
  });
}

const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)');
const videos = [...document.querySelectorAll('.demo-video')];
const masterVideo = videos[0];
const toggleButtons = [...document.querySelectorAll('[data-demo-toggle]')];
let wantsPlayback = false;

function updatePlaybackUI(playing) {
  document.body.classList.toggle('demo-playing', playing);
  for (const button of toggleButtons) {
    button.setAttribute('aria-label', playing ? 'Pause video recording demo' : 'Play video recording demo');
    if (button.classList.contains('playback-control')) button.textContent = playing ? 'Pause video demo Ⅱ' : 'Play video demo ▶';
  }
  for (const label of document.querySelectorAll('[data-rec-label]')) label.textContent = playing ? 'REC' : 'PAUSED';
}

async function playDemo() {
  wantsPlayback = true;
  try {
    // The user sees recording cues only after the video actually starts playing.
    for (const video of videos) video.muted = true;
    await masterVideo.play();
    if (!wantsPlayback) { pauseDemo(); return; }
    updatePlaybackUI(true);
    for (const video of videos.slice(1)) {
      video.currentTime = masterVideo.currentTime;
      video.play().catch(() => {});
    }
  } catch {
    wantsPlayback = false;
    updatePlaybackUI(false);
  }
}

function pauseDemo() {
  wantsPlayback = false;
  for (const video of videos) video.pause();
  updatePlaybackUI(false);
}

for (const button of toggleButtons) button.addEventListener('click', () => {
  if (wantsPlayback) pauseDemo(); else playDemo();
});

masterVideo.addEventListener('timeupdate', () => {
  const seconds = Math.floor(masterVideo.currentTime);
  const time = `${String(Math.floor(seconds / 60)).padStart(2, '0')}:${String(seconds % 60).padStart(2, '0')}`;
  for (const timer of document.querySelectorAll('[data-timer]')) timer.textContent = time;
  if (!masterVideo.paused) {
    for (const video of videos.slice(1)) {
      if (video.readyState >= 2 && Math.abs(video.currentTime - masterVideo.currentTime) > 0.15) video.currentTime = masterVideo.currentTime;
    }
  }
});
masterVideo.addEventListener('error', pauseDemo);
masterVideo.addEventListener('waiting', () => updatePlaybackUI(false));
masterVideo.addEventListener('playing', () => updatePlaybackUI(true));

let resumeAfterVisibility = false;
document.addEventListener('visibilitychange', () => {
  if (document.hidden) { resumeAfterVisibility = wantsPlayback; pauseDemo(); }
  else if (resumeAfterVisibility && !reducedMotion.matches) { resumeAfterVisibility = false; playDemo(); }
});
reducedMotion.addEventListener('change', () => { if (reducedMotion.matches) pauseDemo(); });

updatePlaybackUI(false);
if (!reducedMotion.matches) playDemo();

if ('IntersectionObserver' in window && !reducedMotion.matches) {
  const observer = new IntersectionObserver(entries => {
    for (const entry of entries) {
      if (entry.isIntersecting) { entry.target.classList.remove('pre-reveal'); observer.unobserve(entry.target); }
    }
  }, { threshold: 0.05 });
  document.querySelectorAll('.reveal').forEach(section => {
    section.classList.add('pre-reveal');
    observer.observe(section);
  });
}
