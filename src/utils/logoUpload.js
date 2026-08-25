/**
 * logoUpload.js — Client-side company logo processing.
 *
 * Reads a File from an <input type="file">, resizes it to a payslip-friendly
 * max dimension, and returns a data URL string that can be stored directly in
 * `companies.logo_url`. Data URIs work everywhere the logo is consumed:
 *   - payslipGenerator.js  →  new Image(); img.src = url  (native support)
 *   - letterTemplates.js   →  <img src={url}>              (native support)
 *
 * Kept as a small utility (no external dependencies) so it works offline in
 * the single-file distribution build.
 */

// Max final width or height in pixels. The payslip header logo renders around
// 50mm ≈ 190px at 96dpi; 300 gives a bit of headroom for retina rendering
// without bloating the base64 string.
const MAX_DIMENSION_PX = 300;

// Hard cap on the resulting data URL length. 200KB is safely under Supabase's
// row size limits and far under Postgres TEXT limits. A 300x300 PNG is
// typically 20–80KB; we only reject when someone uploads a huge photograph
// as their "logo".
const MAX_DATA_URL_BYTES = 200 * 1024;

const ACCEPTED_TYPES = ['image/png', 'image/jpeg', 'image/jpg', 'image/svg+xml', 'image/webp'];

/**
 * Read a File → data URL string (Promise). Rejects on read failure.
 */
function readFileAsDataURL(file) {
  return new Promise((resolve, reject) => {
    const r = new FileReader();
    r.onload  = () => resolve(r.result);
    r.onerror = () => reject(new Error('Failed to read file.'));
    r.readAsDataURL(file);
  });
}

/**
 * Load a data URL into an HTMLImageElement (Promise). Rejects if the file is
 * not a decodable image.
 */
function loadImage(dataUrl) {
  return new Promise((resolve, reject) => {
    const img = new Image();
    img.onload  = () => resolve(img);
    img.onerror = () => reject(new Error('File is not a valid image.'));
    img.src = dataUrl;
  });
}

/**
 * Resize the image via <canvas>, preserving aspect ratio. Returns a data URL.
 * PNG output preserves transparency for logos with transparent backgrounds;
 * JPEG input is re-encoded as JPEG at 0.9 to keep the file compact.
 */
function resizeToDataURL(img, sourceMime) {
  // SVGs without an intrinsic width/height (viewBox-only) report 0 here on
  // some browsers. Fall back to a square at the target size in that case.
  const w0 = img.naturalWidth  || img.width  || MAX_DIMENSION_PX;
  const h0 = img.naturalHeight || img.height || MAX_DIMENSION_PX;
  const scale = Math.min(1, MAX_DIMENSION_PX / Math.max(w0, h0));
  const w = Math.round(w0 * scale);
  const h = Math.round(h0 * scale);

  const canvas = document.createElement('canvas');
  canvas.width  = w;
  canvas.height = h;
  const ctx = canvas.getContext('2d');
  ctx.drawImage(img, 0, 0, w, h);

  // PNGs and WebPs may carry transparency — keep PNG output so the payslip
  // logo doesn't sit on an unwanted white rectangle.
  const outMime = sourceMime === 'image/jpeg' || sourceMime === 'image/jpg'
    ? 'image/jpeg'
    : 'image/png';
  return canvas.toDataURL(outMime, 0.9);
}

/**
 * Process a File selected from an <input type="file"> and return a data URL
 * ready to store as company.logoUrl.
 *
 * Throws with a user-friendly message on validation failures (bad type, too
 * large after resize, corrupt image, etc.) so callers can just try/catch.
 *
 * @param {File} file
 * @returns {Promise<string>} data URL, e.g. "data:image/png;base64,iVBORw0KGgo..."
 */
export async function processLogoFile(file) {
  if (!file) throw new Error('No file selected.');
  if (!ACCEPTED_TYPES.includes(file.type)) {
    throw new Error('Unsupported format. Use PNG, JPG, WebP, or SVG.');
  }

  const rawDataUrl = await readFileAsDataURL(file);

  // Always rasterize — even SVG — so every downstream consumer (jsPDF payslip
  // in particular, which cannot draw vector SVG natively) gets a guaranteed
  // PNG/JPEG. Browsers decode SVG data URIs into <img> just fine, so we can
  // paint them into a canvas at the target size.
  const img = await loadImage(rawDataUrl);
  const resized = resizeToDataURL(img, file.type);

  if (resized.length > MAX_DATA_URL_BYTES) {
    // Extremely unusual after a 300px resize, but guard anyway.
    throw new Error(`Logo is too large after resize (${Math.round(resized.length / 1024)}KB). Try a simpler image (under 200KB).`);
  }
  return resized;
}
