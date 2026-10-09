// Separate playback intent from native state; invalidate stale asynchronous requests.
function createMediaDemo({ videos, onState, onError = () => {}, environment }) {
  let visible = false, userPaused = false, wanted = false, pending = false, generation = 0;
  const render = () => onState({ playing: wanted && videos.every(v => !v.paused), pending });
  const sync = () => {
    const [lead, ...followers] = videos;
    if (lead.readyState < 1) return;
    for (const video of followers) if (video.readyState >= 1 && Math.abs(video.currentTime - lead.currentTime) > .1) {
      try { video.currentTime = lead.currentTime; } catch { /* Retry on a later media event. */ }
    }
  };
  function pause(manual = false) {
    if (manual) userPaused = true;
    generation++;
    wanted = pending = false;
    videos.forEach(v => v.pause());
    render();
  }
  async function play(manual = false) {
    if (environment.hidden()) return;
    if (manual) userPaused = false;
    if (wanted) return;
    const request = ++generation;
    wanted = pending = true;
    onError(''); render(); sync();
    try {
      await Promise.all(videos.map(v => v.play()));
      if (request !== generation) {
        if (!wanted) videos.forEach(v => v.pause());
        return;
      }
      pending = false; sync(); render();
    } catch {
      if (request !== generation) return;
      pause();
      onError('The video could not play. Try Play demo again; the sample image is still available.');
    }
  }
  const resumeAutomatic = () => {
    if (visible && !userPaused && !environment.hidden() && !environment.reduced()) play();
  };
  videos.forEach(video => {
    video.addEventListener('play', () => {
      if (!wanted || environment.hidden()) video.pause();
      render();
    });
    video.addEventListener('pause', render);
    video.addEventListener('loadedmetadata', sync);
    video.addEventListener('timeupdate', sync);
    video.addEventListener('error', () => {
      pause(); onError('The sample video is unavailable. The image illustrates the same recording flow.');
    });
  });
  render();
  return {
    toggle() { if (wanted) pause(true); else play(true); },
    setVisible(value) { visible = value; if (!visible) pause(); else resumeAutomatic(); },
    visibilityChanged() { if (environment.hidden()) pause(); else resumeAutomatic(); },
    preferenceChanged() { if (environment.reduced()) pause(); else resumeAutomatic(); },
    pause,
  };
}
