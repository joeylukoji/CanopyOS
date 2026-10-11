'use strict';

const $ = (selector) => document.querySelector(selector);
const dialog = $('#capture-dialog');
let stream = null;
let selectedImage = null;
let previewUrl = null;
let notificationTimer;
let cameraRequest = 0;

function notify(message) {
  const element = $('#notification');
  element.textContent = message;
  element.hidden = false;
  clearTimeout(notificationTimer);
  notificationTimer = setTimeout(() => { element.hidden = true; }, 8000);
}

async function api(url, options = {}) {
  const response = await fetch(url, { credentials: 'same-origin', ...options });
  if (!response.ok) {
    let message = 'Something went wrong. Please try again.';
    try {
      const body = await response.json();
      message = typeof body.detail === 'string' ? body.detail : 'Please check the file and try again.';
    } catch { /* A proxy may return a non-JSON error. */ }
    throw new Error(message);
  }
  return response.status === 204 ? null : response.json();
}

function stopCamera() {
  cameraRequest += 1;
  if (stream) stream.getTracks().forEach((track) => track.stop());
  stream = null;
  if ($('#camera')) $('#camera').srcObject = null;
}

function clearPreview() {
  selectedImage = null;
  $('#analyze-photo').disabled = true;
  $('#preview').hidden = true;
  $('#preview').removeAttribute('src');
  if (previewUrl) URL.revokeObjectURL(previewUrl);
  previewUrl = null;
}

async function startCamera() {
  clearPreview();
  $('#image-file').value = '';
  $('#retake').hidden = true;
  $('#take-photo').hidden = true;
  $('#camera').hidden = true;
  $('#camera-placeholder').hidden = false;
  $('#camera-status').textContent = 'Requesting camera access…';
  stopCamera();
  const request = cameraRequest;
  try {
    if (!navigator.mediaDevices?.getUserMedia) throw new Error('Camera unavailable');
    const opened = await navigator.mediaDevices.getUserMedia({
      video: { facingMode: { ideal: 'environment' }, width: { ideal: 1600 } }, audio: false,
    });
    if (!dialog.open || request !== cameraRequest) {
      opened.getTracks().forEach((track) => track.stop()); return;
    }
    stream = opened;
    $('#camera').srcObject = stream;
    $('#camera').hidden = false;
    $('#camera-placeholder').hidden = true;
    $('#take-photo').hidden = false;
    $('#camera-status').textContent = 'Stand outside and capture the full area.';
  } catch {
    if (!dialog.open || request !== cameraRequest) return;
    $('#camera').hidden = true;
    $('#camera-status').textContent = 'Camera access is unavailable. Allow camera permission on HTTPS or choose a photo below.';
  }
}

function preview(blob) {
  if (!blob) { notify('We could not capture this frame. Please try again.'); return; }
  let error = null;
  if (blob.size > 8 * 1024 * 1024) error = 'Choose a photo smaller than 8 MiB.';
  else if (!['image/jpeg', 'image/png', 'image/webp'].includes(blob.type)) {
    error = 'Please choose a JPEG, PNG or WebP image.';
  }
  if (error) {
    clearPreview();
    stopCamera();
    $('#camera').hidden = true;
    $('#camera-placeholder').hidden = false;
    $('#take-photo').hidden = true;
    $('#retake').hidden = false;
    $('#image-file').value = '';
    $('#camera-status').textContent = error;
    notify(error);
    return;
  }
  selectedImage = blob;
  if (previewUrl) URL.revokeObjectURL(previewUrl);
  previewUrl = URL.createObjectURL(blob);
  $('#preview').src = previewUrl;
  $('#preview').hidden = false;
  $('#camera').hidden = true;
  $('#camera-placeholder').hidden = true;
  $('#take-photo').hidden = true;
  $('#retake').hidden = false;
  $('#analyze-photo').disabled = false;
  $('#camera-status').textContent = 'Take a moment to check your photo before analyzing.';
  stopCamera();
}

$('#start-scan')?.addEventListener('click', () => { dialog.showModal(); startCamera(); });
$('#close-camera')?.addEventListener('click', () => dialog.close());
dialog?.addEventListener('close', stopCamera);
$('#retake')?.addEventListener('click', startCamera);
$('#image-file')?.addEventListener('change', (event) => {
  const file = event.target.files[0];
  if (file) preview(file);
});
$('#take-photo')?.addEventListener('click', () => {
  const video = $('#camera');
  if (!video.videoWidth) { notify('The camera is still starting. Try again in a moment.'); return; }
  const canvas = document.createElement('canvas');
  const scale = Math.min(1, 1600 / video.videoWidth);
  canvas.width = Math.round(video.videoWidth * scale);
  canvas.height = Math.round(video.videoHeight * scale);
  canvas.getContext('2d').drawImage(video, 0, 0, canvas.width, canvas.height);
  canvas.toBlob(preview, 'image/jpeg', 0.9);
});
$('#capture-form')?.addEventListener('submit', async (event) => {
  event.preventDefault();
  if (!selectedImage) return;
  const button = $('#analyze-photo');
  button.disabled = true;
  button.textContent = 'Saving your observation…';
  const body = new FormData();
  body.append('image', selectedImage, 'observation.jpg');
  body.append('area_type', $('#area-type').value);
  try {
    const scan = await api('/api/v1/scans', { method: 'POST', body });
    try { await api(`/api/v1/scans/${scan.scan_id}/analyze`, { method: 'POST' }); }
    catch { /* The saved page exposes a retry if the worker is busy. */ }
    location.assign(`/scans/${scan.scan_id}`);
  } catch (error) {
    $('#camera-status').textContent = error.message;
    button.disabled = false;
    button.textContent = 'Analyze this place ↗';
  }
});

document.addEventListener('click', async (event) => {
  const remove = event.target.closest('.delete-scan');
  const retry = event.target.closest('.retry-analysis');
  if (remove && confirm('Delete this scan and its images permanently?')) {
    remove.disabled = true;
    try { await api(`/api/v1/scans/${remove.dataset.scan}`, { method: 'DELETE' }); location.assign('/history'); }
    catch (error) { remove.disabled = false; notify(error.message); }
  }
  if (retry) {
    retry.disabled = true;
    try { await api(`/api/v1/scans/${retry.dataset.scan}/analyze`, { method: 'POST' }); location.reload(); }
    catch (error) { retry.disabled = false; notify(error.message); }
  }
});
document.addEventListener('htmx:responseError', () => notify('Connection interrupted. Your scan is saved. Reload this page to check its progress.'));
window.addEventListener('pagehide', () => { stopCamera(); if (previewUrl) URL.revokeObjectURL(previewUrl); });
document.addEventListener('visibilitychange', () => { if (document.hidden) stopCamera(); });
