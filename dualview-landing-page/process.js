const processSection = document.querySelector('#how');
const processControl = document.querySelector('[data-process-control]');
const processTimer = document.querySelector('[data-process-timer]');
let processFrame = 0;
let processElapsed = 0;
let processPrevious = 0;
let processPlaying = false;
let processStarted = false;
let processFinished = false;

function advanceProcess(now) {
  if (!processPlaying) return;
  processElapsed += now - processPrevious;
  processPrevious = now;
  const recordingSeconds = Math.min(2, Math.max(0, Math.floor((processElapsed - 2200) / 750)));
  processTimer.textContent = `00:0${recordingSeconds}`;
  if (processElapsed >= 6500) {
    processPlaying = false;
    processFinished = true;
    processControl.textContent = 'Replay animation ↻';
    processControl.setAttribute('aria-label', 'Replay the three-step animation');
    return;
  }
  processFrame = requestAnimationFrame(advanceProcess);
}

function startProcess() {
  if (reducedMotion.matches) return;
  if (!processStarted || processFinished) {
    processElapsed = 0;
    processFinished = false;
    processSection.classList.remove('process-running');
    // Restart the finite CSS sequence when the visitor asks to replay it.
    void processSection.offsetWidth;
    processSection.classList.add('process-running');
    processStarted = true;
  }
  processSection.classList.remove('process-paused');
  processPlaying = true;
  processPrevious = performance.now();
  processControl.textContent = 'Pause animation Ⅱ';
  processControl.setAttribute('aria-label', 'Pause the three-step animation');
  cancelAnimationFrame(processFrame);
  processFrame = requestAnimationFrame(advanceProcess);
}

function pauseProcess() {
  processPlaying = false;
  cancelAnimationFrame(processFrame);
  processSection.classList.add('process-paused');
  processControl.textContent = 'Resume animation ▶';
  processControl.setAttribute('aria-label', 'Resume the three-step animation');
}

processControl.addEventListener('click', () => {
  processSection.dataset.autoResume = 'false';
  if (processPlaying) pauseProcess(); else startProcess();
});

if ('IntersectionObserver' in window) {
  const processObserver = new IntersectionObserver(entries => {
    for (const entry of entries) {
      if (entry.isIntersecting) {
        if (!processStarted || processSection.dataset.autoResume === 'true') startProcess();
        processSection.dataset.autoResume = 'false';
      } else if (processPlaying) {
        pauseProcess();
        processSection.dataset.autoResume = 'true';
      }
    }
  }, {threshold:0.2});
  processObserver.observe(processSection);
}
document.addEventListener('visibilitychange', () => {
  if (document.hidden && processPlaying) pauseProcess();
});
reducedMotion.addEventListener('change', () => {
  if (reducedMotion.matches) {
    pauseProcess();
    processSection.classList.remove('process-running', 'process-paused');
    processStarted = false;
    processFinished = false;
    processElapsed = 0;
    processControl.textContent = 'Play animation ▶';
  }
});
