const slides = [...document.querySelectorAll('.slide')];
const deck = document.querySelector('#deck');
const count = document.querySelector('#slideCount');
const progress = document.querySelector('#progressBar');
const notesPanel = document.querySelector('#speakerNotes');
const notesText = document.querySelector('#notesText');
let current = 0;
let touchStartX = null;

function showSlide(index, updateHash = true) {
  const next = Math.max(0, Math.min(slides.length - 1, index));
  slides[current].classList.remove('is-active');
  slides[current].setAttribute('aria-hidden', 'true');
  current = next;
  slides[current].classList.add('is-active');
  slides[current].removeAttribute('aria-hidden');
  slides[current].scrollTop = 0;
  deck.dataset.theme = slides[current].classList.contains('orange') ? 'orange' : slides[current].classList.contains('light') ? 'light' : 'dark';
  count.textContent = `${String(current + 1).padStart(2, '0')} / ${String(slides.length).padStart(2, '0')}`;
  progress.style.width = `${((current + 1) / slides.length) * 100}%`;
  notesText.textContent = slides[current].querySelector('.notes')?.textContent.trim() || '';
  document.querySelector('#prevButton').disabled = current === 0;
  document.querySelector('#nextButton').disabled = current === slides.length - 1;
  if (updateHash) history.replaceState(null, '', `#${current + 1}`);
}

function toggleNotes() {
  notesPanel.hidden = !notesPanel.hidden;
  document.querySelector('#notesButton').setAttribute('aria-pressed', String(!notesPanel.hidden));
}

function toggleFullScreen() {
  if (document.fullscreenElement) document.exitFullscreen();
  else document.documentElement.requestFullscreen?.();
}

document.querySelector('#prevButton').addEventListener('click', () => showSlide(current - 1));
document.querySelector('#nextButton').addEventListener('click', () => showSlide(current + 1));
document.querySelector('#notesButton').addEventListener('click', toggleNotes);
document.querySelector('#closeNotes').addEventListener('click', toggleNotes);
document.querySelector('#fullButton').addEventListener('click', toggleFullScreen);

document.addEventListener('keydown', event => {
  if (['ArrowRight', 'PageDown', ' ', 'Enter'].includes(event.key)) {
    if (event.target.closest('a,button')) return;
    event.preventDefault();
    showSlide(current + 1);
  } else if (['ArrowLeft', 'PageUp', 'Backspace'].includes(event.key)) {
    event.preventDefault();
    showSlide(current - 1);
  } else if (event.key.toLowerCase() === 'n') toggleNotes();
  else if (event.key.toLowerCase() === 'f') toggleFullScreen();
  else if (event.key === 'Escape' && !notesPanel.hidden) toggleNotes();
});

document.addEventListener('touchstart', event => {
  touchStartX = event.changedTouches[0]?.screenX ?? null;
}, { passive: true });
document.addEventListener('touchend', event => {
  if (touchStartX === null) return;
  const distance = (event.changedTouches[0]?.screenX ?? touchStartX) - touchStartX;
  if (Math.abs(distance) > 70) {
    showSlide(current + (distance < 0 ? 1 : -1));
  }
  touchStartX = null;
}, { passive: true });

window.addEventListener('hashchange', () => {
  const index = Number(location.hash.slice(1)) - 1;
  if (Number.isInteger(index)) showSlide(index, false);
});

slides.forEach((slide, index) => { if (index !== 0) slide.setAttribute('aria-hidden', 'true'); });
const initial = Number(location.hash.slice(1)) - 1;
showSlide(Number.isInteger(initial) ? initial : 0, false);
