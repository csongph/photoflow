/**
 * CS.BXXM STUDIO - Real-Time Photo Booth Gallery Script
 * High-performance mobile viewer, Web Share API, and 1-Tap Downloads.
 */

const params = new URLSearchParams(location.search);
const configuredApi = window.MOMENTLINK_API_URL || "";
const API = (params.get("api") || configuredApi || location.origin).replace(/\/$/, "");
const pathPublicId = location.pathname.split("/").filter(Boolean).pop() || "";
const publicId = params.get("event") || (pathPublicId === "gallery" || pathPublicId === "index.html" ? "" : pathPublicId);
const slideshowOnOpen = params.get("slideshow") === "1";

let knownPhotoCount = 0;
let loadingPhotos = false;
let galleryRefreshTimer = null;
let galleryRetryTimer = null;
let galleryInitializing = false;
let galleryInitialized = false;
let galleryRetryDelay = 3000;
let galleryUrl = location.href.split("#")[0];
let galleryMeta = {
  eventName: "CS.BXXM Gallery",
  creditText: "Photo Booth Experience by CS.BXXM STUDIO",
  reportContact: "",
  allowDownload: true,
  cardMakerEnabled: false,
  cardTemplateName: "",
  photoStripEnabled: false,
  photoStripTheme: null
};

let galleryPhotos = [];
let currentFilter = "all"; // "all" | "recent"
let photoSearchQuery = "";
let photoTimeFilter = "all";
let currentPhotoIndex = -1;
let touchStartX = 0;
let touchStartY = 0;
let selectionMode = false;
let cardMakerSelection = false;
let photoStripSelection = false;
let photoStripCount = 0;
let photoStripEditor = null;
let preparedPhotoStripFile = null;
const selectedPhotoIds = new Set();
const preparedFiles = new Map();
const preparingPhotoIds = new Set();
const failedPreparationIds = new Set();
const preparationControllers = new Map();
let fallbackObjectUrls = [];
let androidDownloadQueue = null;
const MAX_SHARE_SELECTION = 10;
let publicSlideshowState = null;
let sessionStartTime = Date.now();
let preparedCardFile = null;

// Utility Toast
function showToast(message, type = "info") {
  const container = document.querySelector("#toastContainer") || document.body;
  const toast = document.createElement("div");
  toast.className = `toast ${type}`;
  toast.innerHTML = `<span class="toast-dot"></span><span>${escapeHtml(message)}</span>`;
  container.appendChild(toast);
  setTimeout(() => {
    toast.style.opacity = "0";
    toast.style.transform = "translateY(-6px)";
    setTimeout(() => toast.remove(), 250);
  }, 3200);
}

function escapeHtml(value) {
  return String(value || "").replace(/[&<>"']/g, ch => ({
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    '"': "&quot;",
    "'": "&#39;"
  })[ch]);
}

async function getJson(url) {
  const r = await fetch(url, { cache: "no-store", credentials: "include" });
  if (!r.ok) throw new Error(await r.text());
  return r.json();
}

function freshDownloadUrl(url) {
  const result = new URL(url, API);
  result.searchParams.set("_download", `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`);
  return result.toString();
}

function isAppleMobileDevice() {
  return /iPhone|iPad|iPod/i.test(navigator.userAgent) || (navigator.platform === "MacIntel" && navigator.maxTouchPoints > 1);
}

function isAndroidDevice() {
  const platform = navigator.userAgentData?.platform || navigator.platform || "";
  return /Android/i.test(`${navigator.userAgent} ${platform}`) && !isAppleMobileDevice();
}

// -------------------------------------------------------------------------
// INITIALIZATION
// -------------------------------------------------------------------------

async function initGallery() {
  if (galleryInitializing) return;
  if (!publicId) {
    const controls = document.querySelector(".gallery-controls");
    const shareCard = document.querySelector(".qr-share-card");
    const statusBar = document.querySelector(".bar-status");
    if (controls) controls.style.display = "none";
    if (shareCard) shareCard.style.display = "none";
    if (statusBar) statusBar.style.display = "none";
    const floatingQr = document.querySelector("#floatingGalleryQr");
    if (floatingQr) floatingQr.hidden = true;
    document.querySelector("#grid").innerHTML = `
      <div class="empty-gallery">
        <span class="empty-icon">📷</span>
        <h4>ยังไม่ได้ระบุ Gallery</h4>
        <p>กรุณาสแกน QR Code จากหน้างานโฟโต้บูทใหม่อีกครั้ง</p>
      </div>`;
    return;
  }

  galleryInitializing = true;
  clearTimeout(galleryRetryTimer);
  try {
    setupScreenQr();
    const meta = await getJson(`${API}/api/gallery/${publicId}`);
    
    // Page Title & Header
    const eventName = meta.event?.name || "CS.BXXM Gallery";
    document.title = `${eventName} · CS.BXXM STUDIO`;
    const eventTitleEl = document.querySelector("#eventTitle");
    if (eventTitleEl) eventTitleEl.textContent = eventName;
    
    galleryUrl = meta.event?.gallery_url || galleryUrl;
    galleryInitialized = true;
    galleryRetryDelay = 3000;
    const brandHome = document.querySelector("#brandHome");
    if (brandHome) brandHome.href = galleryUrl;

    // Gallery settings
    const s = meta.settings || {};
    galleryMeta = {
      eventName,
      creditText: s.credit_text || "Photo Booth Experience by CS.BXXM STUDIO",
      reportContact: s.report_contact || "",
      allowDownload: Boolean(s.allow_download),
      cardMakerEnabled: Boolean(s.card_maker_enabled && s.allow_download && !s.locked),
      cardTemplateName: s.card_template_name || "",
      photoStripEnabled: Boolean(s.photo_strip_enabled && s.allow_download && !s.locked),
      photoStripTheme: s.photo_strip_theme || null
    };

    renderGalleryInfo();

    const dateEl = document.querySelector("#eventDate");
    if (dateEl) dateEl.textContent = meta.event?.event_date || "LIVE PHOTO BOOTH";

    knownPhotoCount = meta.event?.photo_count || 0;
    updatePhotoCountUI(knownPhotoCount);

    const allowDl = s.allow_download && !s.locked;
    const dlBtn = document.querySelector("#downloadLinks");
    if (dlBtn) dlBtn.style.display = allowDl ? "inline-flex" : "none";
    const selectModeBtn = document.querySelector("#selectModeBtn");
    if (selectModeBtn) selectModeBtn.style.display = allowDl ? "inline-flex" : "none";
    const cardMakerStartBtn = document.querySelector("#cardMakerStartBtn");
    if (cardMakerStartBtn) cardMakerStartBtn.hidden = !allowDl || !galleryMeta.cardMakerEnabled;
    const photoStripStartBtn = document.querySelector("#photoStripStartBtn");
    if (photoStripStartBtn) photoStripStartBtn.hidden = !allowDl || !galleryMeta.photoStripEnabled;

    const pinPanel = document.querySelector("#pinPanel");
    if (pinPanel) pinPanel.style.display = s.locked ? "flex" : "none";
    const floatingQr = document.querySelector("#floatingGalleryQr");
    if (floatingQr) floatingQr.hidden = Boolean(s.locked);

    if (!s.locked) {
      await loadPhotos(true);
      if (slideshowOnOpen) startEventSlideshow();
    }

    clearInterval(galleryRefreshTimer);
    if (!s.locked) {
      galleryRefreshTimer = setInterval(() => {
        if (!document.hidden) loadPhotos(false);
      }, 3000);
    }
  } catch (err) {
    console.error(err);
    document.querySelector("#grid").innerHTML = `
      <div class="empty-gallery">
        <span class="empty-icon">⚠️</span>
        <h4>ไม่สามารถเปิด Gallery ได้</h4>
        <p>กำลังลองเชื่อมต่อใหม่อัตโนมัติ…</p>
      </div>`;
    galleryRetryTimer = setTimeout(() => {
      galleryRetryTimer = null;
      initGallery();
    }, galleryRetryDelay);
    galleryRetryDelay = Math.min(galleryRetryDelay * 2, 30000);
  } finally {
    galleryInitializing = false;
  }
}

function updatePhotoCountUI(count) {
  const countEl = document.querySelector("#count");
  if (countEl) countEl.textContent = `${count} รูป`;
  const subEl = document.querySelector("#heroSub");
  if (subEl) {
    subEl.textContent = count > 0 
      ? `รูปภาพในงานพร้อมดาวน์โหลดความละเอียดสูง ${count} รูป`
      : "รูปภาพจากโฟโต้บูทจะปรากฏที่นี่ทันทีหลังการถ่ายภาพ";
  }
}

function setupScreenQr() {
  const mobileQr = document.querySelector("#mobileQr");
  const qrUrl = `${API}/api/gallery/${publicId}/qr.png`;
  if (mobileQr) mobileQr.src = qrUrl;
  const floatingQr = document.querySelector("#floatingQrImage");
  if (floatingQr) floatingQr.src = qrUrl;
  const largeQr = document.querySelector("#largeQrImage");
  if (largeQr) largeQr.src = qrUrl;
}

function openGalleryQrDialog() {
  const dialog = document.querySelector("#galleryQrDialog");
  if (dialog && !dialog.open) dialog.showModal();
}

function closeGalleryQrDialog() {
  const dialog = document.querySelector("#galleryQrDialog");
  if (dialog?.open) dialog.close();
}

function renderGalleryInfo() {
  const creditEl = document.querySelector("#creditFooter");
  if (creditEl) creditEl.textContent = galleryMeta.creditText;

  const reportEl = document.querySelector("#reportFooter");
  const contactEl = document.querySelector("#contactOwner");
  const contactUrl = normalizeContactUrl(galleryMeta.reportContact);
  if (contactEl && contactUrl) {
    contactEl.href = contactUrl;
    contactEl.target = "_blank";
    contactEl.rel = "noopener noreferrer";
    contactEl.hidden = false;
  }
  if (reportEl) reportEl.textContent = galleryMeta.reportContact ? "ติดต่อฉันผ่านช่องทางด้านบนได้เลย" : "แชร์แกลเลอรีนี้ให้เพื่อน แล้วดาวน์โหลดรูปที่ชอบได้ทันที";
}

function normalizeContactUrl(value) {
  const contact = String(value || "").trim();
  if (!contact) return "";
  if (/^(https?:\/\/|mailto:|tel:)/i.test(contact)) return contact;
  if (/^[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}$/.test(contact)) return `mailto:${contact}`;
  if (/^\+?[\d\s().-]{7,}$/.test(contact)) return `tel:${contact.replace(/[^+\d]/g, "")}`;
  if (/^@?[\w.-]{2,}$/.test(contact)) {
    return contact.startsWith("@")
      ? `https://line.me/R/ti/p/~${encodeURIComponent(contact.slice(1))}`
      : `https://instagram.com/${contact}`;
  }
  return `https://line.me/R/ti/p/~${encodeURIComponent(contact)}`;
}

// -------------------------------------------------------------------------
// INTERACTIONS & COPY
// -------------------------------------------------------------------------

async function copyShareText() {
  const text = `เปิดดูรูปถ่ายและดาวน์โหลดความคมชัดสูงจากงาน ${galleryMeta.eventName}:\n${galleryUrl}`;
  try {
    await navigator.clipboard.writeText(text);
    showToast("คัดลอกลิงก์แกลเลอรีเรียบร้อยแล้ว", "success");
  } catch (err) {
    console.error(err);
  }
}

async function shareGalleryNative() {
  if (navigator.share) {
    try {
      await navigator.share({
        title: `${galleryMeta.eventName} · CS.BXXM STUDIO`,
        text: `ชมและดาวน์โหลดรูปถ่ายจากงาน ${galleryMeta.eventName} ที่นี่:`,
        url: galleryUrl
      });
      return;
    } catch (err) {
      if (err.name !== "AbortError") copyShareText();
    }
  } else {
    copyShareText();
  }
}

async function reportIssue() {
  const text = [
    "แจ้งปัญหา Photo Booth Gallery (CS.BXXM STUDIO)",
    `งาน: ${galleryMeta.eventName}`,
    `ลิงก์: ${galleryUrl}`,
    galleryMeta.reportContact ? `ทีมงาน: ${galleryMeta.reportContact}` : "",
    "รายละเอียดปัญหา: "
  ].filter(Boolean).join("\n");
  try {
    await navigator.clipboard.writeText(text);
    showToast("คัดลอกข้อความแจ้งปัญหาแล้ว นำไปส่งให้ทีมงานได้เลยครับ", "success");
  } catch (err) {
    alert(text);
  }
}

// -------------------------------------------------------------------------
// PHOTO LOADING & RENDERING
// -------------------------------------------------------------------------

async function loadPhotos(reset = false) {
  if (loadingPhotos) return;
  loadingPhotos = true;

  const syncText = document.querySelector("#syncStateText");
  if (syncText) syncText.textContent = "SYNCING...";

  try {
    const photos = [];
    let requestPage = 1;
    let batch = [];
    do {
      batch = await getJson(`${API}/api/gallery/${publicId}/photos?page=${requestPage}&page_size=100`);
      photos.push(...batch);
      requestPage += 1;
    } while (reset && batch.length === 100 && requestPage <= 50);

    const grid = document.querySelector("#grid");
    if (reset) {
      grid.innerHTML = "";
      galleryPhotos = [];
      currentPhotoIndex = -1;
    }

    if (!photos.length && !grid.children.length) {
      grid.innerHTML = `
        <div class="empty-gallery">
          <span class="empty-icon">⏳</span>
          <h4>กำลังรอรูปภาพจากโฟโต้บูท</h4>
          <p>เมื่อถ่ายรูปแล้ว รูปจะเด้งขึ้นที่นี่อัตโนมัติ คุณสามารถเปิดหน้านี้รอได้เลยครับ</p>
        </div>`;
      if (syncText) syncText.textContent = "STANDBY";
      return;
    }

    // Remove empty state / initial skeletons if real photos arrive
    if (photos.length) {
      grid.querySelectorAll(".empty-gallery, .skeleton-card").forEach(el => el.remove());
    }

    const newPhotos = photos.filter(photo => !document.querySelector(`[data-id='${photo.id}']`));
    const isInitial = galleryPhotos.length === 0;

    // The API returns newest first. Keep that order in both the data model
    // and the DOM so customers see the latest event photos at the top.
    const addedPhotos = newPhotos.map(photo => {
      const thumb = photo.variants?.find(v => v.kind === "thumbnail")?.url || "";
      const preview = photo.variants?.find(v => v.kind === "preview")?.url || thumb;
      const finished = photo.variants?.find(v => v.kind === "finished")?.url || "";
      const isRecent = (Date.now() - sessionStartTime < 300000) || !isInitial;

      return {
        id: photo.id, 
        filename: photo.filename,
        createdAt: photo.created_at || "",
        thumb, 
        preview, 
        finished,
        download: `/api/gallery/${publicId}/photos/${photo.id}/download`,
        isRecent
      };
    });
    if (addedPhotos.length) {
      galleryPhotos = [...addedPhotos, ...galleryPhotos];
      [...addedPhotos].reverse().forEach(photo => grid.prepend(createPhotoCard(photo)));
    }

    knownPhotoCount = Math.max(knownPhotoCount, galleryPhotos.length);
    updatePhotoCountUI(knownPhotoCount);
    updateRecentCount();
    applyPhotoFilters();

    if (syncText) syncText.textContent = "LIVE SYNC";
    if (publicSlideshowState) {
      const currentIndex = galleryPhotos.findIndex(photo => photo.id === publicSlideshowState.photoId);
      if (currentIndex >= 0) publicSlideshowState.index = currentIndex;
      else showPublicSlideshowPhoto(publicSlideshowState.index);
    }
  } catch (err) {
    console.error(err);
    if (syncText) syncText.textContent = "OFFLINE";
  } finally {
    loadingPhotos = false;
  }
}

function createPhotoCard(photo) {
  const card = document.createElement("div");
  card.className = "photo-card";
  card.dataset.id = photo.id;
  card.dataset.recent = photo.isRecent ? "true" : "false";
  card.dataset.filename = String(photo.filename || "").toLocaleLowerCase();
  card.dataset.createdAt = photo.createdAt || "";

  const safeName = escapeHtml(photo.filename);
  const timeLabel = formatGalleryPhotoTime(photo.createdAt);
  
  card.innerHTML = `
    ${photo.isRecent ? `<span class="photo-badge-new">NEW</span>` : ""}
    <img src="${photo.thumb || photo.preview}" alt="${safeName}" loading="lazy">
    ${timeLabel.short ? `<time class="photo-card-time" datetime="${escapeHtml(photo.createdAt)}" title="เพิ่มในแกลเลอรี: ${escapeHtml(timeLabel.full)}">${escapeHtml(timeLabel.short)}</time>` : ""}
    <div class="photo-select-mark" aria-hidden="true">✓</div>
  `;

  card.onclick = () => {
    if (selectionMode) {
      togglePhotoSelection(photo.id, card);
    } else {
      const idx = galleryPhotos.findIndex(item => item.id === photo.id);
      openLightbox(idx);
    }
  };

  return card;
}

function formatGalleryPhotoTime(value) {
  const date = new Date(value);
  if (!value || !Number.isFinite(date.getTime())) return { short: "", full: "" };
  const short = new Intl.DateTimeFormat("th-TH", {
    day: "numeric", month: "short", hour: "2-digit", minute: "2-digit"
  }).format(date);
  const full = new Intl.DateTimeFormat("th-TH", {
    dateStyle: "long", timeStyle: "short"
  }).format(date);
  return { short, full };
}

function filterGalleryPhotos(value) {
  photoSearchQuery = String(value || "").trim().toLocaleLowerCase();
  applyPhotoFilters();
}

function clearGallerySearch() {
  const input = document.querySelector("#gallerySearch");
  if (input) input.value = "";
  photoSearchQuery = "";
  applyPhotoFilters();
  input?.focus();
}

function applyPhotoFilters() {
  const cards = [...document.querySelectorAll(".photo-card")];
  let visibleCount = 0;
  cards.forEach(card => {
    const matchesRecent = currentFilter !== "recent" || card.dataset.recent === "true";
    const matchesSearch = !photoSearchQuery || (card.dataset.filename || "").includes(photoSearchQuery);
    const photoTime = Date.parse(card.dataset.createdAt || "");
    let matchesTime = photoTimeFilter === "all";
    if (photoTimeFilter === "today") {
      const todayStart = new Date();
      todayStart.setHours(0, 0, 0, 0);
      matchesTime = Number.isFinite(photoTime) && photoTime >= todayStart.getTime() && photoTime <= Date.now();
    } else if (photoTimeFilter !== "all") {
      const limits = { "15m": 15 * 60 * 1000, "1h": 60 * 60 * 1000, "3h": 3 * 60 * 60 * 1000 };
      const duration = limits[photoTimeFilter];
      matchesTime = Number.isFinite(photoTime) && duration !== undefined && photoTime >= Date.now() - duration && photoTime <= Date.now();
    }
    const visible = matchesRecent && matchesSearch && matchesTime;
    card.style.display = visible ? "" : "none";
    if (visible) visibleCount += 1;
  });

  let empty = document.querySelector("#searchEmptyState");
  const hasActiveFilter = Boolean(photoSearchQuery) || photoTimeFilter !== "all" || currentFilter === "recent";
  if (hasActiveFilter && cards.length && visibleCount === 0) {
    if (!empty) {
      empty = document.createElement("div");
      empty.id = "searchEmptyState";
      empty.className = "search-empty";
      document.querySelector("#grid")?.appendChild(empty);
    }
    empty.textContent = photoSearchQuery ? "ไม่พบรูปที่ตรงกับชื่อไฟล์นี้" : "ไม่พบรูปในช่วงเวลาที่เลือก";
  } else {
    empty?.remove();
  }

  const status = document.querySelector("#searchStatus");
  if (status) status.textContent = hasActiveFilter
    ? "พบ " + visibleCount + " จาก " + cards.length + " รูป"
    : "";
}

function setPhotoTimeFilter(value) {
  photoTimeFilter = ["all", "15m", "1h", "3h", "today"].includes(value) ? value : "all";
  document.querySelector(".time-filter")?.classList.toggle("is-active", photoTimeFilter !== "all");
  applyPhotoFilters();
}

function setPhotoFilter(filter) {
  currentFilter = filter === "recent" ? "recent" : "all";
  document.querySelector("#filterAll")?.classList.toggle("active", currentFilter === "all");
  document.querySelector("#filterRecent")?.classList.toggle("active", currentFilter === "recent");
  applyPhotoFilters();
}

function startEventSlideshow() {
  if (!publicId) {
    showToast("ลิงก์นี้ยังไม่ได้เลือกแกลเลอรีของงาน", "error");
    return;
  }
  if (publicSlideshowState) return;
  const overlay = document.createElement("section");
  overlay.id = "publicSlideshow";
  overlay.className = "public-slideshow";
  overlay.innerHTML = `
    <div class="public-slideshow-stage" id="publicSlideshowStage">
      <img class="public-slideshow-image is-active" id="publicSlideshowImageA" alt="ภาพจากงาน">
      <img class="public-slideshow-image" id="publicSlideshowImageB" alt="ภาพจากงาน" aria-hidden="true">
      <div class="public-slideshow-empty" id="publicSlideshowEmpty">กำลังรอรูปภาพจากงานนี้…</div>
    </div>
    <header class="public-slideshow-heading"><span>CS.BXXM STUDIO</span><strong>${escapeHtml(galleryMeta.eventName)}</strong></header>
    <aside class="public-slideshow-qr"><img src="${escapeHtml(`${API}/api/gallery/${publicId}/qr.png`)}" alt="QR Code เปิดแกลเลอรีงานนี้"><b>สแกน QR Code เพื่อดาวน์โหลดรูปภาพ</b></aside>
    <div class="public-slideshow-controls" id="publicSlideshowControls">
      <button type="button" onclick="closeEventSlideshow()">กลับแกลเลอรี</button>
      <button type="button" onclick="togglePublicSlideshowPlayback()" id="publicSlideshowPlay">พักภาพ</button>
      <button type="button" onclick="stepPublicSlideshow(-1)" aria-label="ภาพก่อนหน้า">‹ ก่อนหน้า</button>
      <button type="button" onclick="stepPublicSlideshow(1)" aria-label="ภาพถัดไป">ถัดไป ›</button>
      <label>เปลี่ยนภาพ<select onchange="setPublicSlideshowTransition(this.value)"><option value="fade">Fade</option><option value="slide">Slide</option><option value="dissolve">Dissolve</option></select></label>
      <label>ความเร็ว<select onchange="setPublicSlideshowInterval(this.value)"><option value="4000">4 วินาที</option><option value="6000" selected>6 วินาที</option><option value="8000">8 วินาที</option><option value="10000">10 วินาที</option></select></label>
      <button type="button" onclick="togglePublicSlideshowFullscreen()">เต็มจอ</button>
    </div>
  `;
  document.body.appendChild(overlay);
  const floatingQr = document.querySelector("#floatingGalleryQr");
  if (floatingQr) floatingQr.hidden = true;
  document.body.classList.add("slideshow-is-open");
  const state = { index: 0, photoId: "", paused: false, transition: "fade", interval: 6000, slideTimer: null, hideTimer: null, sequence: 0, failedUrls: new Set() };
  publicSlideshowState = state;
  state.slideTimer = setInterval(() => { if (publicSlideshowState === state && !state.paused) stepPublicSlideshow(1); }, state.interval);
  const reveal = () => revealPublicSlideshowControls();
  overlay.addEventListener("pointermove", reveal, { passive: true });
  overlay.addEventListener("touchstart", reveal, { passive: true });
  let touchX = 0;
  let touchY = 0;
  overlay.addEventListener("touchstart", event => {
    touchX = event.changedTouches[0]?.clientX || 0;
    touchY = event.changedTouches[0]?.clientY || 0;
  }, { passive: true });
  overlay.addEventListener("touchend", event => {
    const dx = (event.changedTouches[0]?.clientX || touchX) - touchX;
    const dy = (event.changedTouches[0]?.clientY || touchY) - touchY;
    if (Math.abs(dx) > 55 && Math.abs(dx) > Math.abs(dy) * 1.3) stepPublicSlideshow(dx < 0 ? 1 : -1);
  }, { passive: true });
  overlay.addEventListener("click", event => {
    if (event.target.id === "publicSlideshowStage" || event.target.classList.contains("public-slideshow-image")) reveal();
  });
  if (galleryPhotos.length) showPublicSlideshowPhoto(0);
  reveal();
}

function revealPublicSlideshowControls() {
  if (!publicSlideshowState) return;
  const overlay = document.querySelector("#publicSlideshow");
  if (!overlay) return;
  overlay.classList.remove("controls-hidden");
  clearTimeout(publicSlideshowState.hideTimer);
  publicSlideshowState.hideTimer = setTimeout(() => overlay.classList.add("controls-hidden"), 3200);
}

function closeEventSlideshow() {
  if (publicSlideshowState) {
    clearInterval(publicSlideshowState.slideTimer);
    clearTimeout(publicSlideshowState.hideTimer);
    publicSlideshowState = null;
  }
  document.querySelector("#publicSlideshow")?.remove();
  document.body.classList.remove("slideshow-is-open");
  const floatingQr = document.querySelector("#floatingGalleryQr");
  if (floatingQr) floatingQr.hidden = false;
  if (document.fullscreenElement) document.exitFullscreen().catch(() => {});
  const url = new URL(location.href);
  url.searchParams.delete("slideshow");
  history.replaceState({}, "", url);
}

async function showPublicSlideshowPhoto(index) {
  if (!publicSlideshowState || !galleryPhotos.length) return;
  const state = publicSlideshowState;
  const sequence = ++state.sequence;
  let photo = null;
  let imageUrl = "";
  for (let offset = 0; offset < galleryPhotos.length; offset += 1) {
    const candidate = galleryPhotos[(index + offset + galleryPhotos.length) % galleryPhotos.length];
    const candidateUrl = candidate.preview || candidate.thumb;
    if (!candidateUrl || state.failedUrls.has(candidateUrl)) continue;
    const preload = new Image();
    preload.src = candidateUrl;
    try {
      await preload.decode();
      photo = candidate;
      imageUrl = candidateUrl;
      break;
    } catch {
      state.failedUrls.add(candidateUrl);
      console.warn("Skipping unavailable slideshow photo", candidate.id);
    }
  }
  if (publicSlideshowState !== state || state.sequence !== sequence) return;
  if (!photo) {
    const empty = document.querySelector("#publicSlideshowEmpty");
    if (empty) { empty.hidden = false; empty.textContent = "ยังไม่มีรูปภาพที่แสดงได้"; }
    return;
  }
  const stage = document.querySelector("#publicSlideshowStage");
  const active = stage?.querySelector(".public-slideshow-image.is-active");
  const next = active?.id === "publicSlideshowImageA" ? document.querySelector("#publicSlideshowImageB") : document.querySelector("#publicSlideshowImageA");
  if (!stage || !active || !next) return;
  next.src = imageUrl;
  next.alt = photo.filename || "ภาพจากงาน";
  next.dataset.photoId = photo.id;
  next.classList.add("is-active");
  active.classList.remove("is-active");
  stage.dataset.transition = state.transition;
  state.index = galleryPhotos.findIndex(item => item.id === photo.id);
  state.photoId = photo.id;
  const empty = document.querySelector("#publicSlideshowEmpty");
  if (empty) empty.hidden = true;
}

function stepPublicSlideshow(direction) {
  if (!publicSlideshowState || !galleryPhotos.length) return;
  showPublicSlideshowPhoto(publicSlideshowState.index + direction);
}

function togglePublicSlideshowPlayback() {
  if (!publicSlideshowState) return;
  publicSlideshowState.paused = !publicSlideshowState.paused;
  const button = document.querySelector("#publicSlideshowPlay");
  if (button) button.textContent = publicSlideshowState.paused ? "เล่นต่อ" : "พักภาพ";
}

function setPublicSlideshowTransition(value) {
  if (!publicSlideshowState || !["fade", "slide", "dissolve"].includes(value)) return;
  publicSlideshowState.transition = value;
  const stage = document.querySelector("#publicSlideshowStage");
  if (stage) stage.dataset.transition = value;
}

function setPublicSlideshowInterval(value) {
  if (!publicSlideshowState) return;
  const milliseconds = Number(value);
  if (![4000, 6000, 8000, 10000].includes(milliseconds)) return;
  const state = publicSlideshowState;
  clearInterval(state.slideTimer);
  state.interval = milliseconds;
  state.slideTimer = setInterval(() => { if (publicSlideshowState === state && !state.paused) stepPublicSlideshow(1); }, milliseconds);
}

async function togglePublicSlideshowFullscreen() {
  const screen = document.querySelector("#publicSlideshow");
  try {
    if (!document.fullscreenElement) await screen?.requestFullscreen();
    else await document.exitFullscreen();
  } catch (error) {
    showToast("กด F11 เพื่อขยายหน้าต่างเต็มจอ", "info");
  }
}

function updateRecentCount() {
  const recentPhotos = galleryPhotos.filter(p => p.isRecent);
  const countBadge = document.querySelector("#recentCount");
  if (countBadge) {
    if (recentPhotos.length > 0) {
      countBadge.textContent = recentPhotos.length;
      countBadge.style.display = "inline-block";
    } else {
      countBadge.style.display = "none";
    }
  }
}

// -------------------------------------------------------------------------
// SELECTION MODE & DOCK
// -------------------------------------------------------------------------

function toggleSelectionMode() {
  selectionMode = !selectionMode;
  if (!selectionMode) {
    cardMakerSelection = false;
    photoStripSelection = false;
    photoStripCount = 0;
    preparationControllers.forEach(controller => controller.abort());
    preparationControllers.clear();
    preparingPhotoIds.clear();
    selectedPhotoIds.clear();
    preparedFiles.clear();
    failedPreparationIds.clear();
  }

  const normalDock = document.querySelector("#normalDock");
  const selectionDock = document.querySelector("#selectionDock");
  const selectModeBtn = document.querySelector("#selectModeBtn");

  if (normalDock) normalDock.style.display = selectionMode ? "none" : "flex";
  if (selectionDock) selectionDock.style.display = selectionMode ? "flex" : "none";

  if (selectModeBtn) {
    selectModeBtn.classList.toggle("active", selectionMode);
    selectModeBtn.innerHTML = selectionMode 
      ? `<span class="btn-icon">✕</span> ยกเลิกการเลือก` 
      : `<span class="btn-icon">✓</span> เลือกเพื่อบันทึก`;
  }
  const selectAll = document.querySelector("#selectAllBtn");
  if (selectAll) selectAll.textContent = "เลือกทั้งหมด";

  document.querySelectorAll(".photo-card").forEach(card => {
    const isSelected = selectedPhotoIds.has(card.dataset.id);
    card.classList.toggle("selected", isSelected);
  });

  updateSelectionControls();
}

function startCardMakerSelection() {
  if (!galleryMeta.cardMakerEnabled) return;
  if (!selectionMode) toggleSelectionMode();
  cardMakerSelection = true;
  photoStripSelection = false;
  const selectAll = document.querySelector("#selectAllBtn");
  if (selectAll) selectAll.textContent = "เลือกล่าสุด 4 รูป";
  selectedPhotoIds.clear();
  preparedFiles.clear();
  failedPreparationIds.clear();
  document.querySelectorAll(".photo-card.selected").forEach(card => card.classList.remove("selected"));
  showToast("เลือกรูปให้ครบ 4 รูปเพื่อจัดเป็นการ์ด", "info");
  updateSelectionControls();
}

function togglePhotoSelection(photoId, card) {
  if (selectedPhotoIds.has(photoId)) {
    selectedPhotoIds.delete(photoId);
    preparedFiles.delete(photoId);
    failedPreparationIds.delete(photoId);
    preparationControllers.get(photoId)?.abort();
    card.classList.remove("selected");
  } else {
    const maxSelection = cardMakerSelection ? 4 : photoStripSelection ? photoStripCount : MAX_SHARE_SELECTION;
    if (selectedPhotoIds.size >= maxSelection) {
      showToast(cardMakerSelection ? "การ์ดหนึ่งใบเลือกได้สูงสุด 4 รูป" : photoStripSelection ? `Photo Strip นี้เลือกได้ ${photoStripCount} รูป` : `เลือกได้สูงสุด ${MAX_SHARE_SELECTION} รูปต่อครั้ง เพื่อบันทึกได้เสถียร`, "info");
      return;
    }
    selectedPhotoIds.add(photoId);
    card.classList.add("selected");
    if (isAppleMobileDevice()) prepareSelectedPhoto(photoId);
  }
  updateSelectionControls();
}

async function prepareSelectedPhoto(photoId) {
  const photo = galleryPhotos.find(item => item.id === photoId);
  if (!photo || preparedFiles.has(photoId) || preparingPhotoIds.has(photoId)) return;
  preparingPhotoIds.add(photoId);
  failedPreparationIds.delete(photoId);
  const controller = new AbortController();
  preparationControllers.set(photoId, controller);
  updateSelectionControls();
  try {
    const response = await fetch(freshDownloadUrl(photo.download), { credentials: "include", cache: "no-store", signal: controller.signal });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const blob = await response.blob();
    if (!blob.type.startsWith("image/") || !blob.size || blob.size > 40 * 1024 * 1024) throw new Error("ไฟล์รูปใหญ่เกินไปหรือไม่ใช่รูปภาพ");
    if (selectedPhotoIds.has(photoId)) preparedFiles.set(photoId, new File([blob], photo.filename, { type: blob.type }));
  } catch (error) {
    if (error.name !== "AbortError") {
      console.error("Unable to prepare selected photo", photoId, error);
      if (selectedPhotoIds.has(photoId)) failedPreparationIds.add(photoId);
    }
  } finally {
    if (preparationControllers.get(photoId) === controller) preparationControllers.delete(photoId);
    preparingPhotoIds.delete(photoId);
    updateSelectionControls();
  }
}

function selectAllPhotos() {
  if (!selectionMode) toggleSelectionMode();
  const cards = [...document.querySelectorAll(".photo-card")];
  const visibleCards = cards.filter(card => card.offsetParent !== null);
  const available = visibleCards.filter(card => !selectedPhotoIds.has(card.dataset.id));
  const maxSelection = cardMakerSelection ? 4 : photoStripSelection ? photoStripCount : MAX_SHARE_SELECTION;
  const room = maxSelection - selectedPhotoIds.size;
  for (const card of available.slice(0, room)) {
    selectedPhotoIds.add(card.dataset.id);
    card.classList.add("selected");
    if (isAppleMobileDevice()) prepareSelectedPhoto(card.dataset.id);
  }
  if (available.length > room) showToast(cardMakerSelection ? `เลือกได้สูงสุด ${maxSelection} รูปสำหรับการ์ด` : photoStripSelection ? `เลือกได้สูงสุด ${maxSelection} รูปสำหรับ Photo Strip` : `เลือกเพิ่มได้ ${room} รูป · สูงสุด ${MAX_SHARE_SELECTION} รูปต่อครั้ง`, "info");
  updateSelectionControls();
}

function clearPhotoSelection() {
  preparationControllers.forEach(controller => controller.abort());
  preparationControllers.clear();
  preparingPhotoIds.clear();
  selectedPhotoIds.clear();
  preparedFiles.clear();
  failedPreparationIds.clear();
  document.querySelectorAll(".photo-card.selected").forEach(card => card.classList.remove("selected"));
  updateSelectionControls();
}

function updateSelectionControls() {
  const count = selectedPhotoIds.size;
  const ready = [...selectedPhotoIds].filter(id => preparedFiles.has(id)).length;
  const preparing = [...selectedPhotoIds].filter(id => preparingPhotoIds.has(id)).length;
  const failed = [...selectedPhotoIds].filter(id => failedPreparationIds.has(id)).length;
  const needsPreparedFiles = isAppleMobileDevice();
  const countLabel = document.querySelector("#selectedCount");
  const downloadButton = document.querySelector("#downloadSelectedBtn");
  const cardButton = document.querySelector("#makeCardBtn");
  const stripButton = document.querySelector("#makePhotoStripBtn");
  const selectAll = document.querySelector("#selectAllBtn");

  if (countLabel) countLabel.textContent = preparing ? `เตรียมรูป ${ready}/${count}` : `เลือก ${count} รูป`;
  if (downloadButton) {
    downloadButton.hidden = cardMakerSelection || photoStripSelection;
    downloadButton.disabled = count === 0 || (needsPreparedFiles && (preparing > 0 || (ready !== count && failed === 0)));
    const readyLabel = needsPreparedFiles ? `บันทึกลง Photos ${count} รูป` : `ดาวน์โหลด ${count} รูป`;
    downloadButton.innerHTML = `<span class="btn-icon">${preparing ? "…" : "↓"}</span> ${preparing ? `เตรียมรูป ${ready}/${count}` : failed ? `ดาวน์โหลดแยก ${count} รูป` : readyLabel}`;
  }
  if (cardButton) {
    cardButton.hidden = !cardMakerSelection;
    cardButton.disabled = count !== 4;
    cardButton.textContent = count === 4 ? "▤ สร้างการ์ด 4 รูป" : `▤ เลือกอีก ${Math.max(0, 4-count)} รูป`;
  }
  if (stripButton) {
    stripButton.hidden = !photoStripSelection;
    stripButton.disabled = count !== photoStripCount;
    stripButton.textContent = count === photoStripCount ? `▤ สร้าง Photo Strip ${count} ภาพ` : `▤ เลือกอีก ${Math.max(0, photoStripCount-count)} รูป`;
  }
  if (selectAll) selectAll.hidden = (cardMakerSelection && count >= 4) || (photoStripSelection && count >= photoStripCount);
}

async function createCardFromSelection() {
  const selected = [...selectedPhotoIds];
  if (!galleryMeta.cardMakerEnabled || selected.length !== 4) {
    showToast("เลือกภาพให้ครบ 4 รูปก่อนสร้างการ์ด", "info");
    return;
  }
  const dialog = document.querySelector("#cardMakerDialog");
  const canvas = document.querySelector("#cardMakerCanvas");
  const status = document.querySelector("#cardMakerStatus");
  const saveButton = document.querySelector("#saveCardButton");
  const shareButton = document.querySelector("#shareCardButton");
  preparedCardFile = null;
  saveButton.disabled = true;
  shareButton.disabled = true;
  status.textContent = "กำลังจัดวางรูปภาพลงเทมเพลต…";
  if (!dialog.open) dialog.showModal();
  try {
    const templateUrl = `${API}/api/gallery/${encodeURIComponent(publicId)}/card-template.png?v=${Date.now()}`;
    const templateResponse = await fetch(templateUrl, { credentials: "include", cache: "no-store" });
    if (!templateResponse.ok) throw new Error("โหลดเทมเพลตการ์ดไม่สำเร็จ ลองรีเฟรชแกลเลอรีแล้วทำใหม่");
    const templateBlob = await templateResponse.blob();
    const template = await createImageBitmap(templateBlob);
    const outputScale = Math.min(1, 1800 / template.width, 3000 / template.height);
    canvas.width = Math.max(1, Math.round(template.width * outputScale));
    canvas.height = Math.max(1, Math.round(template.height * outputScale));
    const ctx = canvas.getContext("2d", { alpha: true, colorSpace: "srgb" });
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    const x0 = canvas.width * .12;
    const y0 = canvas.height * .16;
    const slotWidth = canvas.width * .76;
    const slotHeight = canvas.height * .165;
    const gapY = canvas.height * .025;
    for (let index = 0; index < selected.length; index++) {
      const photo = galleryPhotos.find(item => item.id === selected[index]);
      if (!photo) throw new Error("หารูปที่เลือกไม่พบในแกลเลอรี");
      let blob = preparedFiles.get(photo.id);
      if (!blob) {
        const response = await fetch(freshDownloadUrl(photo.download), { credentials: "include", cache: "no-store" });
        if (!response.ok) throw new Error(`ดาวน์โหลด ${photo.filename} มาใส่การ์ดไม่สำเร็จ`);
        blob = await response.blob();
      }
      if (!blob.type.startsWith("image/") || blob.size > 40 * 1024 * 1024) throw new Error("รูปภาพใหญ่เกินไปหรือไฟล์ไม่ถูกต้อง");
      const bitmap = await createImageBitmap(blob);
      const x = x0;
      const y = y0 + index * (slotHeight + gapY);
      ctx.save();
      ctx.shadowColor = "rgba(0,0,0,.34)";
      ctx.shadowBlur = Math.max(3, canvas.width * .008);
      ctx.fillStyle = "#fff";
      ctx.fillRect(x-2, y-2, slotWidth+4, slotHeight+4);
      ctx.shadowColor = "transparent";
      const scale = Math.max(slotWidth / bitmap.width, slotHeight / bitmap.height);
      const sw = slotWidth / scale;
      const sh = slotHeight / scale;
      const sx = (bitmap.width - sw) / 2;
      const sy = (bitmap.height - sh) / 2;
      ctx.drawImage(bitmap, sx, sy, sw, sh, x, y, slotWidth, slotHeight);
      ctx.restore();
      bitmap.close();
    }
    ctx.drawImage(template, 0, 0, canvas.width, canvas.height);
    template.close();
    const blob = await new Promise(resolve => canvas.toBlob(resolve, "image/png"));
    if (!blob) throw new Error("สร้างไฟล์การ์ดไม่สำเร็จ กรุณาลองอีกครั้ง");
    const safeName = galleryMeta.eventName.replace(/[\\/:*?"<>|]/g, "-").slice(0, 60) || "photoflow";
    preparedCardFile = new File([blob], `${safeName}-photo-card.png`, { type: "image/png" });
    status.textContent = "การ์ดพร้อมแล้ว บันทึกลงเครื่องหรือแชร์ต่อได้เลย";
    saveButton.disabled = false;
    shareButton.disabled = false;
  } catch (error) {
    console.error("Could not create photo card", error);
    status.textContent = error.message || "สร้างการ์ดไม่สำเร็จ กรุณาลองใหม่";
  }
}

function closeCardMaker() {
  const dialog = document.querySelector("#cardMakerDialog");
  if (dialog?.open) dialog.close();
  preparedCardFile = null;
}

function savePhotoCard() {
  if (!preparedCardFile) return;
  const url = URL.createObjectURL(preparedCardFile);
  const link = document.createElement("a");
  link.href = url;
  link.download = preparedCardFile.name;
  link.style.display = "none";
  document.body.appendChild(link);
  link.click();
  link.remove();
  setTimeout(() => URL.revokeObjectURL(url), 30000);
  showToast("บันทึกการ์ดภาพแล้ว", "success");
}

async function sharePhotoCard() {
  if (!preparedCardFile) return;
  if (navigator.share && navigator.canShare?.({ files: [preparedCardFile] })) {
    try { await navigator.share({ files: [preparedCardFile], title: galleryMeta.eventName, text: "การ์ดภาพจากงาน " + galleryMeta.eventName }); }
    catch (error) { if (error.name !== "AbortError") savePhotoCard(); }
  } else savePhotoCard();
}

function openPhotoStripSetup() {
  const theme = galleryMeta.photoStripTheme;
  if (!galleryMeta.photoStripEnabled || !theme) return showToast("Photo Strip ยังไม่พร้อมใช้งาน", "info");
  document.querySelector("#photoStripThemeTitle").textContent = theme.name || "Photo Strip";
  document.querySelector("#photoStripThemeDescription").textContent = theme.description || "เลือกจำนวนภาพ แล้วเลือกภาพจากแกลเลอรี";
  document.querySelectorAll("[data-strip-count]").forEach(button => {
    const count = Number(button.dataset.stripCount);
    const ready = Boolean(theme.layouts?.[String(count)]?.asset_present);
    button.disabled = !ready;
    button.classList.toggle("active", count === photoStripCount);
  });
  const dialog = document.querySelector("#photoStripCountDialog");
  if (dialog && !dialog.open) dialog.showModal();
}

function choosePhotoStripCount(count) {
  if (![2, 3, 4].includes(count) || !galleryMeta.photoStripTheme?.layouts?.[String(count)]?.asset_present) return;
  photoStripCount = count;
  document.querySelectorAll("[data-strip-count]").forEach(button => button.classList.toggle("active", Number(button.dataset.stripCount) === count));
}

function closePhotoStripSetup() {
  const dialog = document.querySelector("#photoStripCountDialog");
  if (dialog?.open) dialog.close();
}

function beginPhotoStripSelection() {
  if (!photoStripCount) return showToast("เลือกจำนวนภาพก่อน", "info");
  closePhotoStripSetup();
  if (!selectionMode) toggleSelectionMode();
  cardMakerSelection = false;
  photoStripSelection = true;
  selectedPhotoIds.clear();
  preparedFiles.clear();
  failedPreparationIds.clear();
  document.querySelectorAll(".photo-card.selected").forEach(card => card.classList.remove("selected"));
  const selectAll = document.querySelector("#selectAllBtn");
  if (selectAll) selectAll.textContent = `เลือกล่าสุด ${photoStripCount} รูป`;
  showToast(`เลือกรูปให้ครบ ${photoStripCount} รูปสำหรับ Photo Strip`, "info");
  updateSelectionControls();
}

async function createPhotoStripFromSelection() {
  const ids = [...selectedPhotoIds];
  const theme = galleryMeta.photoStripTheme;
  const layout = theme?.layouts?.[String(photoStripCount)];
  if (!galleryMeta.photoStripEnabled || !theme || ids.length !== photoStripCount || !layout?.asset_present) {
    showToast("กรุณาเลือกรูปให้ครบและตรวจสอบ Layout ของธีม", "info");
    return;
  }
  const status = document.querySelector("#photoStripEditorStatus");
  const canvas = document.querySelector("#photoStripCanvas");
  const exportButton = document.querySelector("#exportPhotoStripButton");
  const downloadButton = document.querySelector("#downloadPhotoStripButton");
  const shareButton = document.querySelector("#sharePhotoStripButton");
  const dialog = document.querySelector("#photoStripEditorDialog");
  preparedPhotoStripFile = null;
  downloadButton.disabled = shareButton.disabled = true;
  exportButton.disabled = true;
  status.textContent = "กำลังโหลดภาพและ Layout…";
  if (!dialog.open) dialog.showModal();
  try {
    const templateUrl = `${API}/api/gallery/${encodeURIComponent(publicId)}/photo-strip/${encodeURIComponent(theme.id)}/${photoStripCount}.png`;
    const templateResponse = await fetch(freshDownloadUrl(templateUrl), { credentials: "include", cache: "no-store" });
    if (!templateResponse.ok) throw new Error("โหลด Layout ไม่สำเร็จ กรุณาลองใหม่อีกครั้ง");
    const template = await createImageBitmap(await templateResponse.blob());
    const photos = [];
    for (const id of ids) {
      const photo = galleryPhotos.find(item => item.id === id);
      if (!photo) throw new Error("ไม่พบรูปที่เลือกในแกลเลอรี");
      const response = await fetch(freshDownloadUrl(photo.download), { credentials: "include", cache: "no-store" });
      if (!response.ok) throw new Error(`โหลด ${photo.filename} ไม่สำเร็จ`);
      const blob = await response.blob();
      if (!blob.type.startsWith("image/") || blob.size > 40 * 1024 * 1024) throw new Error("รูปภาพไม่ถูกต้องหรือมีขนาดใหญ่เกินไป");
      photos.push({ id, photo, bitmap: await createImageBitmap(blob, { imageOrientation: "from-image" }), zoom: 1, panX: 0, panY: 0, rotation: 0 });
    }
    photoStripEditor = { theme, layout, count: photoStripCount, template, photos, active: 0, canvasScale: Math.min(1, 1800 / template.width, 3200 / template.height), drag: null, pointers: new Map(), pinch: null, undo: [] };
    const selected = document.querySelector("#photoStripSelectedPhotos");
    selected.innerHTML = photos.map((entry, index) => `<button type="button" class="photo-strip-photo-chip ${index===0?"active":""}" data-strip-slot="${index}"><img src="${freshDownloadUrl(entry.photo.preview)}" alt=""><span>${index+1}. ${escapeHtml(entry.photo.filename)}</span></button>`).join("");
    selected.querySelectorAll("[data-strip-slot]").forEach(button => button.addEventListener("click", () => selectPhotoStripSlot(Number(button.dataset.stripSlot))));
    const zoom = document.querySelector("#photoStripZoom");
    zoom.value = "1";
    zoom.oninput = () => { if (!photoStripEditor) return; savePhotoStripUndo(); activeStripPhoto().zoom = Number(zoom.value); renderPhotoStripPreview(); };
    canvas.width = Math.max(1, Math.round(template.width * photoStripEditor.canvasScale));
    canvas.height = Math.max(1, Math.round(template.height * photoStripEditor.canvasScale));
    canvas.onpointerdown = startPhotoStripPan;
    canvas.onpointermove = movePhotoStripPan;
    canvas.onpointerup = endPhotoStripPan;
    canvas.onpointercancel = endPhotoStripPan;
    renderPhotoStripPreview();
    exportButton.disabled = false;
    status.textContent = "ลากภาพเพื่อจัดตำแหน่ง · เลือกช่องด้านล่างเพื่อแก้แต่ละภาพ";
  } catch (error) {
    console.error("Could not prepare Photo Strip", error);
    status.textContent = error.message || "เตรียม Photo Strip ไม่สำเร็จ";
  } finally {
    exportButton.disabled = !photoStripEditor;
  }
}

function activeStripPhoto() { return photoStripEditor?.photos[photoStripEditor.active]; }
function selectPhotoStripSlot(index) {
  if (!photoStripEditor || index < 0 || index >= photoStripEditor.photos.length) return;
  photoStripEditor.active = index;
  document.querySelectorAll("[data-strip-slot]").forEach(button => button.classList.toggle("active", Number(button.dataset.stripSlot) === index));
  document.querySelector("#photoStripZoom").value = String(activeStripPhoto().zoom);
  renderPhotoStripPreview();
}
function savePhotoStripUndo() {
  if (!photoStripEditor) return;
  const item = activeStripPhoto();
  photoStripEditor.undo.push({ index: photoStripEditor.active, zoom: item.zoom, panX: item.panX, panY: item.panY, rotation: item.rotation });
  if (photoStripEditor.undo.length > 30) photoStripEditor.undo.shift();
}
function drawPhotoCover(ctx, bitmap, slot, edit) {
  const x = slot.x * ctx.canvas.width, y = slot.y * ctx.canvas.height;
  const width = slot.width * ctx.canvas.width, height = slot.height * ctx.canvas.height;
  ctx.save(); ctx.beginPath(); ctx.rect(x, y, width, height); ctx.clip();
  ctx.translate(x + width/2 + edit.panX*width, y + height/2 + edit.panY*height);
  ctx.rotate(edit.rotation * Math.PI / 180);
  const rotated = Math.abs(edit.rotation % 180) === 90;
  const scale = Math.max(width/(rotated?bitmap.height:bitmap.width), height/(rotated?bitmap.width:bitmap.height)) * edit.zoom;
  const renderedWidth = bitmap.width*scale, renderedHeight = bitmap.height*scale;
  const maxPanX = Math.max(0, ((rotated?renderedHeight:renderedWidth)-width)/2), maxPanY = Math.max(0, ((rotated?renderedWidth:renderedHeight)-height)/2);
  const shiftX = Math.max(-maxPanX, Math.min(maxPanX, edit.panX*width));
  const shiftY = Math.max(-maxPanY, Math.min(maxPanY, edit.panY*height));
  ctx.translate(shiftX, shiftY);
  ctx.drawImage(bitmap, -renderedWidth/2, -renderedHeight/2, renderedWidth, renderedHeight);
  ctx.restore();
}
function renderPhotoStripPreview() {
  const state = photoStripEditor; if (!state) return;
  const canvas = document.querySelector("#photoStripCanvas"), ctx = canvas.getContext("2d", { alpha: false, colorSpace: "srgb" });
  ctx.fillStyle = state.theme.background_color || "#fff"; ctx.fillRect(0,0,canvas.width,canvas.height);
  state.photos.forEach((photo,index) => drawPhotoCover(ctx, photo.bitmap, state.layout.slots[index], photo));
  ctx.drawImage(state.template, 0,0,canvas.width,canvas.height);
  const caption = String(state.theme.caption || "").trim();
  if (caption) { ctx.save(); ctx.fillStyle = state.theme.text_color || "#222"; ctx.textAlign="center"; ctx.textBaseline="bottom"; ctx.font=`600 ${Math.max(14,canvas.width*.035)}px system-ui, sans-serif`; ctx.fillText(caption,canvas.width/2,canvas.height*.985,canvas.width*.82); ctx.restore(); }
}
function startPhotoStripPan(event) {
  if (!photoStripEditor) return;
  const state=photoStripEditor,item=activeStripPhoto();
  state.pointers.set(event.pointerId,{x:event.clientX,y:event.clientY});
  if(state.pointers.size===1){savePhotoStripUndo();state.drag={pointerId:event.pointerId,x:event.clientX,y:event.clientY,panX:item.panX,panY:item.panY,rect:event.currentTarget.getBoundingClientRect()};}
  else if(state.pointers.size===2){const pts=[...state.pointers.values()];state.drag=null;state.pinch={distance:Math.hypot(pts[0].x-pts[1].x,pts[0].y-pts[1].y),zoom:item.zoom};savePhotoStripUndo();}
  event.currentTarget.setPointerCapture(event.pointerId);
}
function movePhotoStripPan(event) {
  const state=photoStripEditor;if(!state?.pointers.has(event.pointerId))return;
  state.pointers.set(event.pointerId,{x:event.clientX,y:event.clientY});
  if(state.pinch&&state.pointers.size>=2){const pts=[...state.pointers.values()],distance=Math.max(1,Math.hypot(pts[0].x-pts[1].x,pts[0].y-pts[1].y));const item=activeStripPhoto();item.zoom=Math.max(1,Math.min(3,state.pinch.zoom*distance/state.pinch.distance));document.querySelector("#photoStripZoom").value=String(item.zoom);renderPhotoStripPreview();return;}
  const drag=state.drag;if(!drag||drag.pointerId!==event.pointerId)return;
  const item=activeStripPhoto();
  if (item.zoom===1) { item.zoom=1.15; document.querySelector("#photoStripZoom").value="1.15"; }
  item.panX=drag.panX+(event.clientX-drag.x)/drag.rect.width;
  item.panY=drag.panY+(event.clientY-drag.y)/drag.rect.height;
  renderPhotoStripPreview();
}
function endPhotoStripPan(event) { const state=photoStripEditor;if(!state)return;state.pointers.delete(event.pointerId);if(state.pointers.size<2)state.pinch=null;if(state.drag?.pointerId===event.pointerId)state.drag=null; }
function rotatePhotoStripSlot(degrees) { if (!photoStripEditor) return; savePhotoStripUndo(); const item=activeStripPhoto(); item.rotation=(item.rotation+degrees+360)%360; renderPhotoStripPreview(); }
function movePhotoStripSlot(direction) {
  const state=photoStripEditor; if (!state) return; const next=state.active+direction;
  if (next<0||next>=state.photos.length) return;
  [state.photos[state.active],state.photos[next]]=[state.photos[next],state.photos[state.active]]; state.active=next;
  const selected=document.querySelector("#photoStripSelectedPhotos");
  selected.innerHTML=state.photos.map((entry,index)=>`<button type="button" class="photo-strip-photo-chip ${index===next?"active":""}" data-strip-slot="${index}"><img src="${freshDownloadUrl(entry.photo.preview)}" alt=""><span>${index+1}. ${escapeHtml(entry.photo.filename)}</span></button>`).join("");
  selected.querySelectorAll("[data-strip-slot]").forEach(button=>button.addEventListener("click",()=>selectPhotoStripSlot(Number(button.dataset.stripSlot))));
  renderPhotoStripPreview();
}
function resetPhotoStripSlot() { if (!photoStripEditor) return; savePhotoStripUndo(); const item=activeStripPhoto(); item.zoom=1;item.panX=0;item.panY=0;item.rotation=0;document.querySelector("#photoStripZoom").value="1";renderPhotoStripPreview(); }
function undoPhotoStripEdit() {
  const state=photoStripEditor, edit=state?.undo.pop(); if(!state||!edit)return showToast("ไม่มีการแก้ไขก่อนหน้า", "info");
  const item=state.photos[edit.index];Object.assign(item,{zoom:edit.zoom,panX:edit.panX,panY:edit.panY,rotation:edit.rotation});state.active=edit.index;
  document.querySelector("#photoStripZoom").value=String(item.zoom);renderPhotoStripPreview();
}
function closePhotoStripEditor() {
  const dialog=document.querySelector("#photoStripEditorDialog"); if(dialog?.open)dialog.close();
  photoStripEditor?.photos.forEach(item=>item.bitmap.close()); photoStripEditor?.template.close(); photoStripEditor=null; preparedPhotoStripFile=null;
}
async function exportPhotoStripJpg() {
  const state=photoStripEditor; if(!state)return;
  const button=document.querySelector("#exportPhotoStripButton"),status=document.querySelector("#photoStripEditorStatus");button.disabled=true;status.textContent="กำลังสร้างไฟล์ JPG…";
  try {
    const scale=Math.min(1,3000/state.template.width,5000/state.template.height),out=document.createElement("canvas");out.width=Math.max(1,Math.round(state.template.width*scale));out.height=Math.max(1,Math.round(state.template.height*scale));
    const ctx=out.getContext("2d",{alpha:false,colorSpace:"srgb"});ctx.fillStyle=state.theme.background_color||"#fff";ctx.fillRect(0,0,out.width,out.height);
    state.photos.forEach((photo,index)=>drawPhotoCover(ctx,photo.bitmap,state.layout.slots[index],photo));ctx.drawImage(state.template,0,0,out.width,out.height);
    const caption=String(state.theme.caption||"").trim();if(caption){ctx.fillStyle=state.theme.text_color||"#222";ctx.textAlign="center";ctx.textBaseline="bottom";ctx.font=`600 ${Math.max(18,out.width*.035)}px system-ui, sans-serif`;ctx.fillText(caption,out.width/2,out.height*.985,out.width*.82);}
    const blob=await new Promise(resolve=>out.toBlob(resolve,"image/jpeg",.94));if(!blob||blob.size<100)throw new Error("สร้างไฟล์ JPG ไม่สำเร็จ");
    const safe=galleryMeta.eventName.replace(/[\\/:*?"<>|]/g,"-").slice(0,50)||"photoflow";preparedPhotoStripFile=new File([blob],`${safe}-photo-strip-${state.count}.jpg`,{type:"image/jpeg"});
    document.querySelector("#downloadPhotoStripButton").disabled=false;document.querySelector("#sharePhotoStripButton").disabled=false;status.textContent=`พร้อมดาวน์โหลด · JPG ${out.width} × ${out.height} px`;
  }catch(error){console.error("Photo Strip export failed",error);status.textContent=error.message||"สร้างไฟล์ไม่สำเร็จ ลองอีกครั้ง";}
  finally{button.disabled=false;}
}
function downloadPhotoStripJpg() {
  if(!preparedPhotoStripFile)return;
  const url=URL.createObjectURL(preparedPhotoStripFile),link=document.createElement("a");link.href=url;link.download=preparedPhotoStripFile.name;link.rel="noopener";link.style.display="none";document.body.appendChild(link);link.click();link.remove();setTimeout(()=>URL.revokeObjectURL(url),60000);
  if (!("download" in link)) window.open(url,"_blank","noopener");
  showToast("เริ่มดาวน์โหลดไฟล์ Photo Strip แล้ว", "success");
}
async function sharePhotoStripJpg() {
  if(!preparedPhotoStripFile)return;
  if(navigator.share&&navigator.canShare?.({files:[preparedPhotoStripFile]})){
    try{await navigator.share({files:[preparedPhotoStripFile],title:galleryMeta.eventName,text:"Photo Strip จากงาน "+galleryMeta.eventName});}
    catch(error){if(error.name!=="AbortError")downloadPhotoStripJpg();}
  }else downloadPhotoStripJpg();
}

function downloadSelectedPhotos(event) {
  event.preventDefault();
  const photos = [...selectedPhotoIds];
  if (!photos.length) return;
  if (isAndroidDevice()) {
    startAndroidDownloadQueue(photos);
    return;
  }
  if (!isAppleMobileDevice()) {
    showDownloadFallback(photos, true);
    return;
  }
  if (photos.some(id => !preparedFiles.has(id))) {
    showDownloadFallback(photos);
    return;
  }
  const files = photos.map(id => preparedFiles.get(id)).filter(Boolean);
  if (!files.length || files.length !== photos.length) {
    showDownloadFallback(photos);
    return;
  }
  if (navigator.share && navigator.canShare?.({ files })) {
    showToast("ในเมนูแชร์ เลือก Photos หรือ Gallery เพื่อบันทึกรูป", "info");
    navigator.share({ files, title: galleryMeta.eventName, text: `รูปจากงาน ${galleryMeta.eventName}` })
      .then(() => showToast("ส่งรูปไปยังแอปที่เลือกแล้ว", "success"))
      .catch(error => {
        if (error.name !== "AbortError") {
          console.error("Share sheet failed", error);
          showDownloadFallback(photos, true);
        }
      });
    return;
  }
  showDownloadFallback(photos, true);
}

function startAndroidDownloadQueue(photoIds) {
  showDownloadFallback(photoIds, false, true);
  const panel = document.querySelector("#androidDownloadQueue");
  if (!panel) return;
  androidDownloadQueue = {
    photos: photoIds.map(id => galleryPhotos.find(photo => photo.id === id)).filter(Boolean),
    index: 0,
    status: "ready",
    saveAsState: "",
    saveController: null,
    saveAsRetryable: false
  };
  panel.hidden = false;
  const details = document.querySelector("#androidDownloadIndividualDetails");
  if (details) details.open = false;
  const fallbackMessage = document.querySelector("#downloadFallbackMessage");
  if (fallbackMessage) fallbackMessage.textContent = "Android ดาวน์โหลดทีละรูปไปยัง Downloads/Files ตามการตั้งค่าเบราว์เซอร์ แตะรูปถัดไปได้โดยไม่ต้องรีเฟรช หากมีหน้าแจ้งข้อผิดพลาดให้ย้อนกลับแล้วลองรูปนั้นใหม่";
  updateAndroidDownloadQueue();
}

function updateAndroidDownloadQueue() {
  const queue = androidDownloadQueue;
  const status = document.querySelector("#androidDownloadQueueMessage");
  const link = document.querySelector("#androidDownloadNextLink");
  const retry = document.querySelector("#retryAndroidLastLink");
  const saveAsButton = document.querySelector("#androidSaveAsButton");
  const saveAsProgress = document.querySelector("#androidSaveAsProgress");
  const saveAsStatus = document.querySelector("#androidSaveAsStatus");
  const saveAsRetry = document.querySelector("#androidSaveAsRetry");
  if (!queue || !status || !link) return;
  const isComplete = queue.index >= queue.photos.length;
  if (saveAsButton) {
    saveAsButton.hidden = isComplete || !supportsAndroidSavePicker();
    saveAsButton.disabled = queue.saveAsState === "saving";
  }
  if (saveAsProgress) saveAsProgress.hidden = queue.saveAsState !== "saving";
  if (saveAsStatus) {
    saveAsStatus.hidden = !queue.saveAsMessage;
    saveAsStatus.textContent = queue.saveAsMessage || "";
  }
  if (saveAsRetry) saveAsRetry.hidden = !queue.saveAsRetryable;
  if (retry) {
    retry.hidden = queue.index === 0;
    if (queue.index > 0) {
      const previous = queue.photos[queue.index - 1];
      retry.href = freshDownloadUrl(previous.download);
      retry.removeAttribute("download");
    }
  }
  if (isComplete) {
    status.textContent = `ส่งคำขอดาวน์โหลดครบ ${queue.photos.length} รูปแล้ว ตรวจรายการดาวน์โหลดของเบราว์เซอร์`;
    link.hidden = true;
    return;
  }
  const photo = queue.photos[queue.index];
  if (queue.saveAsState === "saving") {
    status.textContent = `กำลังบันทึก ${photo.filename}…`;
    link.hidden = true;
    return;
  }
  status.textContent = queue.status === "requested"
    ? `ส่งคำขอรูป ${queue.index + 1} จาก ${queue.photos.length} แล้ว · หากยังไม่พบไฟล์ ให้แตะชื่อรูปด้านล่างอีกครั้ง`
    : `รูป ${queue.index + 1} จาก ${queue.photos.length} · แตะเพื่อดาวน์โหลด`;
  link.href = freshDownloadUrl(photo.download);
  link.removeAttribute("download");
  link.textContent = `↓ ดาวน์โหลด ${photo.filename}`;
  link.hidden = false;
}

function supportsAndroidSavePicker() {
  return isAndroidDevice() && window.isSecureContext === true && typeof window.showSaveFilePicker === "function";
}

function safeSuggestedPhotoName(filename) {
  const leafName = String(filename || "photo.jpg").split(/[\\/]/).pop();
  return leafName.replace(/[<>:"|?*\u0000-\u001f]/g, "_").trim().slice(0, 180) || "photo.jpg";
}

function isSupportedPhotoSignature(bytes) {
  if (bytes.length < 12) return false;
  const starts = (...values) => values.every((value, index) => bytes[index] === value);
  if (starts(0xff, 0xd8, 0xff)) return true;
  if (starts(0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a)) return true;
  if (String.fromCharCode(...bytes.slice(0, 6)) === "GIF87a" || String.fromCharCode(...bytes.slice(0, 6)) === "GIF89a") return true;
  if (String.fromCharCode(...bytes.slice(0, 4)) === "RIFF" && String.fromCharCode(...bytes.slice(8, 12)) === "WEBP") return true;
  const brand = String.fromCharCode(...bytes.slice(8, 12)).toLowerCase();
  return String.fromCharCode(...bytes.slice(4, 8)) === "ftyp" && ["heic", "heif", "mif1", "avif", "avis"].includes(brand);
}

async function saveAndroidCurrentWithPicker(event) {
  const queue = androidDownloadQueue;
  if (!queue || !event.isTrusted || queue.status !== "ready" || queue.saveAsState === "saving" || !supportsAndroidSavePicker()) {
    event.preventDefault();
    return;
  }
  event.preventDefault();
  const photo = queue.photos[queue.index];
  let pickerRequest;
  try {
    // Request the save destination before any await so the picker keeps the user's activation.
    pickerRequest = window.showSaveFilePicker({ suggestedName: safeSuggestedPhotoName(photo.filename) });
  } catch (error) {
    queue.saveAsMessage = "เบราว์เซอร์เปิดหน้าต่างเลือกที่เก็บไม่ได้ ใช้ปุ่มดาวน์โหลดปกติได้";
    queue.saveAsRetryable = false;
    updateAndroidDownloadQueue();
    return;
  }

  queue.saveAsState = "saving";
  queue.saveAsMessage = "กำลังเปิดตัวเลือกที่เก็บไฟล์…";
  queue.saveAsRetryable = false;
  queue.saveController = new AbortController();
  const controller = queue.saveController;
  updateAndroidDownloadQueue();
  void streamAndroidPhotoToFile(queue, photo, pickerRequest, controller);
}

async function streamAndroidPhotoToFile(queue, photo, pickerRequest, controller) {
  let writable = null;
  let reader = null;
  let timeoutId = null;
  let timedOut = false;
  const startIdleTimeout = () => {
    window.clearTimeout(timeoutId);
    timeoutId = window.setTimeout(() => {
      timedOut = true;
      controller.abort();
    }, 120000);
  };
  try {
    const fileHandle = await pickerRequest;
    if (androidDownloadQueue !== queue) return;
    startIdleTimeout();
    queue.saveAsMessage = `กำลังรับรูป ${photo.filename}…`;
    updateAndroidDownloadQueue();
    const response = await fetch(freshDownloadUrl(photo.download), {
      credentials: "include", cache: "no-store", signal: controller.signal
    });
    if (!response.ok) {
      const error = new Error(`HTTP ${response.status}`);
      error.httpStatus = response.status;
      throw error;
    }
    const contentType = (response.headers.get("content-type") || "").split(";")[0].trim().toLowerCase();
    if (!contentType.startsWith("image/") && contentType !== "application/octet-stream") {
      throw new Error("เซิร์ฟเวอร์ไม่ได้ส่งไฟล์รูปภาพ");
    }
    const expectedBytes = Number(response.headers.get("content-length") || 0);
    const progress = document.querySelector("#androidSaveAsProgress");
    if (progress) {
      progress.max = 100;
      if (expectedBytes) progress.value = 0;
      else progress.removeAttribute("value");
    }
    reader = response.body?.getReader();
    if (!reader) throw new Error("เบราว์เซอร์อ่านข้อมูลไฟล์ไม่ได้");
    writable = await fileHandle.createWritable();
    let receivedBytes = 0;
    const prefix = new Uint8Array(12);
    let prefixLength = 0;
    let lastUiUpdate = 0;
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      startIdleTimeout();
      if (!value?.byteLength) continue;
      const prefixCount = Math.min(prefix.length - prefixLength, value.byteLength);
      if (prefixCount > 0) {
        prefix.set(value.subarray(0, prefixCount), prefixLength);
        prefixLength += prefixCount;
      }
      receivedBytes += value.byteLength;
      if (prefixLength === prefix.length && !isSupportedPhotoSignature(prefix)) {
        await reader.cancel();
        throw new Error("ไฟล์ที่ได้รับไม่ใช่รูปภาพที่เปิดได้");
      }
      await writable.write(value);
      const now = Date.now();
      if (now - lastUiUpdate > 250) {
        const percent = expectedBytes ? Math.min(100, Math.floor(receivedBytes / expectedBytes * 100)) : null;
        queue.saveAsMessage = percent === null
          ? `กำลังบันทึก ${photo.filename} · ${Math.ceil(receivedBytes / 1024 / 1024)} MB`
          : `กำลังบันทึก ${photo.filename} · ${percent}%`;
        if (progress && percent !== null) progress.value = percent;
        lastUiUpdate = now;
        updateAndroidDownloadQueue();
      }
    }
    if (!receivedBytes || prefixLength < prefix.length || !isSupportedPhotoSignature(prefix)) {
      throw new Error("ไฟล์ว่างหรือข้อมูลรูปภาพไม่ครบ");
    }
    await writable.close();
    writable = null;
    if (androidDownloadQueue !== queue) return;
    queue.index += 1;
    queue.status = "ready";
    queue.saveAsState = "";
    queue.saveAsMessage = `บันทึก ${photo.filename} เรียบร้อย`;
    queue.saveAsRetryable = false;
    showToast(`บันทึก ${photo.filename} แล้ว`, "success");
  } catch (error) {
    if (writable) {
      try { await writable.abort(); } catch { /* Best effort: discard incomplete file. */ }
    }
    if (androidDownloadQueue !== queue) return;
    queue.saveAsState = error.name === "AbortError" && !timedOut ? "cancelled" : "error";
    queue.saveAsRetryable = timedOut || error.name === "TypeError" || error.httpStatus === 408 || error.httpStatus === 429 || error.httpStatus >= 500;
    if (error.name === "AbortError" && !timedOut) {
      queue.saveAsMessage = "ยกเลิกการเลือกที่เก็บ ยังไม่มีการบันทึกรูป";
    } else if (error.httpStatus === 401) {
      queue.saveAsMessage = "เซสชันหมดอายุ กรุณาเปิดแกลเลอรีจาก QR อีกครั้ง";
    } else if (error.httpStatus === 403) {
      queue.saveAsMessage = "แกลเลอรีนี้ปิดการดาวน์โหลดไว้";
    } else if (error.httpStatus === 404) {
      queue.saveAsMessage = "ไม่พบรูปนี้แล้ว กรุณาเลือกภาพอื่น";
    } else if (error.httpStatus === 429) {
      queue.saveAsMessage = "มีคำขอจำนวนมาก รอสักครู่แล้วลองรูปนี้ใหม่";
    } else if (timedOut || error.name === "TypeError" || error.httpStatus >= 500 || error.httpStatus === 408) {
      queue.saveAsMessage = "การเชื่อมต่อสะดุดหรือเซิร์ฟเวอร์ไม่พร้อม ลองบันทึกรูปนี้ใหม่ได้";
    } else {
      queue.saveAsMessage = error.message || "บันทึกรูปไม่สำเร็จ ใช้ปุ่มดาวน์โหลดปกติได้";
    }
    console.error("Android save picker failed", photo.id, error);
  } finally {
    window.clearTimeout(timeoutId);
    if (reader) reader.releaseLock();
    if (queue.saveController === controller) queue.saveController = null;
    updateAndroidDownloadQueue();
  }
}

function retryAndroidSaveAs(event) {
  if (!androidDownloadQueue?.saveAsRetryable) {
    event.preventDefault();
    return;
  }
  androidDownloadQueue.saveAsState = "";
  androidDownloadQueue.saveAsMessage = "";
  androidDownloadQueue.saveAsRetryable = false;
  saveAndroidCurrentWithPicker(event);
}

function advanceAndroidDownloadQueue(event) {
  const queue = androidDownloadQueue;
  if (!queue || !event.isTrusted || queue.status !== "ready") {
    event.preventDefault();
    return;
  }
  queue.status = "requested";
  const status = document.querySelector("#androidDownloadQueueMessage");
  if (status) status.textContent = `ส่งคำขอรูป ${queue.index + 1} จาก ${queue.photos.length} แล้ว กำลังเปิดรูปถัดไป…`;
  window.setTimeout(() => {
    if (androidDownloadQueue !== queue) return;
    queue.index += 1;
    queue.status = "ready";
    updateAndroidDownloadQueue();
  }, 450);
}

function refreshAndroidRetryUrl(event) {
  const queue = androidDownloadQueue;
  if (!queue || !event.isTrusted || queue.index < 1) {
    event.preventDefault();
    return;
  }
  const previousPhoto = queue.photos[queue.index - 1];
  event.currentTarget.href = freshDownloadUrl(previousPhoto.download);
}

function showDownloadFallback(photoIds, startDownloads = false, silent = false) {
  const dialog = document.querySelector("#downloadFallbackDialog");
  const isAndroid = isAndroidDevice();
  const list = document.querySelector(isAndroid ? "#androidDownloadFallbackLinks" : "#downloadFallbackLinks");
  if (!dialog || !list) return;
  fallbackObjectUrls.forEach(url => URL.revokeObjectURL(url));
  fallbackObjectUrls = [];
  const availableIds = photoIds.filter(id => galleryPhotos.some(item => item.id === id));
  list.innerHTML = availableIds.map(id => {
    const photo = galleryPhotos.find(item => item.id === id);
    if (!photo) return "";
    const file = preparedFiles.get(id);
    const preparedUrl = file ? URL.createObjectURL(file) : "";
    if (preparedUrl) fallbackObjectUrls.push(preparedUrl);
    const href = preparedUrl || freshDownloadUrl(photo.download);
    const downloadAttribute = isAndroid ? "" : ` download="${escapeHtml(photo.filename)}"`;
    return `<a class="btn btn-primary download-fallback-link" href="${escapeHtml(href)}"${downloadAttribute} rel="noopener"><span>↓</span>${escapeHtml(photo.filename)}</a>`;
  }).join("");
  list.querySelectorAll("a").forEach((link, index) => {
    const photo = galleryPhotos.find(item => item.id === availableIds[index]);
    if (photo) link.addEventListener("click", event => {
      if (event.isTrusted) link.href = freshDownloadUrl(photo.download);
    });
  });
  const message = document.querySelector("#downloadFallbackMessage");
  const progress = document.querySelector("#downloadFallbackProgress");
  const desktopAppleDetails = document.querySelector("#downloadIndividualDetails");
  const androidDetails = document.querySelector("#androidDownloadIndividualDetails");
  if (desktopAppleDetails) desktopAppleDetails.hidden = isAndroid;
  if (androidDetails) {
    androidDetails.hidden = !isAndroid;
    if (isAndroid) androidDetails.open = false;
  }
  if (message) message.textContent = startDownloads
    ? `กำลังเริ่มดาวน์โหลดรูปแยก ${availableIds.length} ไฟล์ หาก Chrome ถาม ให้กดอนุญาตดาวน์โหลดหลายไฟล์ แล้วตรวจรายการดาวน์โหลดของเบราว์เซอร์`
    : "แตะชื่อไฟล์ด้านล่างเพื่อดาวน์โหลด ระบบจะบันทึกผ่านเบราว์เซอร์ไปยัง Downloads หรือ Files";
  if (progress) progress.hidden = !startDownloads;
  if (startDownloads && desktopAppleDetails) desktopAppleDetails.open = true;
  if (startDownloads) {
    // Trigger every file in the original user gesture so browsers can show
    // their native permission prompt for multiple downloads.
    list.querySelectorAll("a").forEach(link => link.click());
    if (progress) progress.hidden = true;
    if (message) message.textContent = `ส่งคำขอดาวน์โหลด ${availableIds.length} ไฟล์แล้ว ตรวจรายการดาวน์โหลด; หาก Chrome บล็อกไฟล์ใด ให้กดอนุญาตหรือแตะชื่อไฟล์ด้านล่างทีละรูป`;
    if (!silent) showToast("ส่งคำขอดาวน์โหลดรูปที่เลือกแล้ว", "info");
  } else if (!silent) {
    showToast("แตะชื่อรูปเพื่อดาวน์โหลดแยกไฟล์", "info");
  }
  if (!dialog.open) dialog.showModal();
}

document.querySelector("#downloadFallbackDialog")?.addEventListener("close", () => {
  androidDownloadQueue?.saveController?.abort();
  fallbackObjectUrls.forEach(url => URL.revokeObjectURL(url));
  fallbackObjectUrls = [];
  androidDownloadQueue = null;
});

// -------------------------------------------------------------------------
// LIGHTBOX VIEW
// -------------------------------------------------------------------------

function openLightbox(index) {
  const photo = galleryPhotos[index];
  if (!photo) return;
  currentPhotoIndex = index;

  const modal = document.querySelector("#lightbox");
  const safeName = escapeHtml(photo.filename);
  const position = `${index + 1} / ${galleryPhotos.length}`;

  modal.innerHTML = `
    <div class="lightbox-content">
      <div class="lightbox-header">
        <div class="lightbox-title-box">
          <span class="lightbox-title">${safeName}</span>
          <span class="lightbox-counter">${position}</span>
          <span class="hd-badge">HD</span>
        </div>
        <button class="btn btn-ghost" onclick="closeLightbox()">ปิด ✕</button>
      </div>

      <div class="lightbox-stage">
        <button class="stage-nav prev" onclick="moveLightbox(-1)" aria-label="รูปก่อนหน้า">‹</button>
        <img src="${photo.preview}" alt="${safeName}">
        <button class="stage-nav next" onclick="moveLightbox(1)" aria-label="รูปถัดไป">›</button>
      </div>

      ${galleryMeta.allowDownload ? `<div class="lightbox-actions"><button type="button" class="btn btn-primary" id="selectExpandedPhoto"><span class="btn-icon">✓</span> เลือกรูปเพื่อบันทึก</button></div>` : ""}
    </div>
  `;

  modal.querySelector("#selectExpandedPhoto")?.addEventListener("click", () => selectPhotoForSaving(photo.id));
  modal.classList.add("open");
  document.body.style.overflow = "hidden";
}

function selectPhotoForSaving(photoId) {
  closeLightbox();
  if (!selectionMode) toggleSelectionMode();
  const card = [...document.querySelectorAll(".photo-card")].find(item => item.dataset.id === photoId);
  if (card && !selectedPhotoIds.has(photoId)) togglePhotoSelection(photoId, card);
}

function closeLightbox() {
  const modal = document.querySelector("#lightbox");
  if (modal) modal.classList.remove("open");
  currentPhotoIndex = -1;
  document.body.style.overflow = "";
}

function moveLightbox(delta) {
  if (!galleryPhotos.length || currentPhotoIndex < 0) return;
  const next = (currentPhotoIndex + delta + galleryPhotos.length) % galleryPhotos.length;
  openLightbox(next);
}

// -------------------------------------------------------------------------
// PRIVATE GALLERY PIN
// -------------------------------------------------------------------------

async function unlockGallery(ev) {
  ev.preventDefault();
  const pinInput = document.querySelector("#galleryPin");
  const pin = pinInput ? pinInput.value.trim() : "";
  if (!pin) return;

  try {
    const response = await fetch(`${API}/api/gallery/${publicId}/unlock`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      credentials: "include",
      body: JSON.stringify({ pin })
    });

    if (pinInput) pinInput.value = "";

    if (!response.ok) {
      if (response.status === 429) {
        showToast("ใส่รหัสผิดหลายครั้ง กรุณารอสักครู่แล้วลองใหม่", "error");
      } else {
        showToast("รหัส PIN ไม่ถูกต้อง กรุณาลองใหม่", "error");
      }
      return;
    }

    showToast("ปลดล็อกแกลเลอรีสำเร็จ ยินดีต้อนรับครับ!", "success");
    await initGallery();
  } catch (err) {
    console.error(err);
    showToast("เกิดข้อผิดพลาดในการตรวจสอบรหัส", "error");
  }
}

// -------------------------------------------------------------------------
// EVENT LISTENERS & GESTURES
// -------------------------------------------------------------------------

document.addEventListener("visibilitychange", () => {
  if (!document.hidden && publicId) {
    if (galleryInitialized) loadPhotos(false);
    else initGallery();
  }
});

document.addEventListener("keydown", ev => {
  if (publicSlideshowState) {
    if (ev.target instanceof HTMLElement && /^(INPUT|SELECT|TEXTAREA|BUTTON)$/.test(ev.target.tagName)) return;
    if (ev.key === "ArrowLeft") { stepPublicSlideshow(-1); revealPublicSlideshowControls(); }
    else if (ev.key === "ArrowRight") { stepPublicSlideshow(1); revealPublicSlideshowControls(); }
    else if (ev.code === "Space") { ev.preventDefault(); togglePublicSlideshowPlayback(); revealPublicSlideshowControls(); }
    else if (ev.key === "Escape") closeEventSlideshow();
    return;
  }
  if (currentPhotoIndex < 0) return;
  if (ev.key === "ArrowLeft") moveLightbox(-1);
  if (ev.key === "ArrowRight") moveLightbox(1);
  if (ev.key === "Escape") closeLightbox();
});

document.addEventListener("touchstart", ev => {
  if (currentPhotoIndex < 0 || !ev.changedTouches.length) return;
  touchStartX = ev.changedTouches[0].clientX;
  touchStartY = ev.changedTouches[0].clientY;
}, { passive: true });

document.addEventListener("touchend", ev => {
  if (currentPhotoIndex < 0 || !ev.changedTouches.length) return;
  const dx = ev.changedTouches[0].clientX - touchStartX;
  const dy = ev.changedTouches[0].clientY - touchStartY;
  if (Math.abs(dx) > 50 && Math.abs(dx) > Math.abs(dy) * 1.3) {
    moveLightbox(dx < 0 ? 1 : -1);
  }
}, { passive: true });
