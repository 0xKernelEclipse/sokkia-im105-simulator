const fs = require('fs');
const path = require('path');
const zlib = require('zlib');

function createPng(width, height, getPixel) {
  const rowSize = 1 + width * 4;
  const rawData = Buffer.alloc(rowSize * height);
  for (let y = 0; y < height; y++) {
    const rowOffset = y * rowSize;
    rawData[rowOffset] = 0; // Filter: None
    for (let x = 0; x < width; x++) {
      const [r, g, b, a] = getPixel(x, y, width, height);
      const pxOffset = rowOffset + 1 + x * 4;
      rawData[pxOffset] = Math.max(0, Math.min(255, Math.round(r)));
      rawData[pxOffset + 1] = Math.max(0, Math.min(255, Math.round(g)));
      rawData[pxOffset + 2] = Math.max(0, Math.min(255, Math.round(b)));
      rawData[pxOffset + 3] = Math.max(0, Math.min(255, Math.round(a)));
    }
  }
  const compressed = zlib.deflateSync(rawData, { level: 9 });

  const table = new Uint32Array(256);
  for (let i = 0; i < 256; i++) {
    let c = i;
    for (let j = 0; j < 8; j++) c = (c & 1) ? (0xedb88320 ^ (c >>> 1)) : (c >>> 1);
    table[i] = c;
  }
  function crc32(buf) {
    let crc = -1;
    for (let i = 0; i < buf.length; i++) {
      crc = (crc >>> 8) ^ table[(crc ^ buf[i]) & 0xff];
    }
    return (crc ^ -1) >>> 0;
  }
  function makeChunk(type, data) {
    const len = Buffer.alloc(4);
    len.writeUInt32BE(data.length, 0);
    const typeBuf = Buffer.from(type, 'ascii');
    const crcBuf = Buffer.alloc(4);
    crcBuf.writeUInt32BE(crc32(Buffer.concat([typeBuf, data])), 0);
    return Buffer.concat([len, typeBuf, data, crcBuf]);
  }
  const sig = Buffer.from([0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a]);
  const ihdr = Buffer.alloc(13);
  ihdr.writeUInt32BE(width, 0);
  ihdr.writeUInt32BE(height, 4);
  ihdr[8] = 8;
  ihdr[9] = 6;
  ihdr[10] = 0; ihdr[11] = 0; ihdr[12] = 0;
  return Buffer.concat([
    sig,
    makeChunk('IHDR', ihdr),
    makeChunk('IDAT', compressed),
    makeChunk('IEND', Buffer.alloc(0))
  ]);
}

// Icon Pixel Generator (Sokkia Optical Target & Crosshair)
function iconPixel(x, y, w, h) {
  const cx = w / 2;
  const cy = h / 2;
  const dx = x - cx;
  const dy = y - cy;
  const dist = Math.sqrt(dx * dx + dy * dy);

  // Background chassis dark
  let r = 24, g = 26, b = 31, a = 255;

  // Outer red ring (radius ~ 0.38 of width)
  const ringR = w * 0.375;
  const ringThickness = Math.max(1.5, w * 0.04);
  if (Math.abs(dist - ringR) < ringThickness) {
    const factor = 1 - Math.abs(dist - ringR) / ringThickness;
    return [223, 68, 51, Math.round(255 * factor + (1 - factor) * 31)];
  }

  // Inner ring
  const innerR = w * 0.22;
  const innerThickness = Math.max(1.2, w * 0.025);
  if (Math.abs(dist - innerR) < innerThickness) {
    return [60, 67, 80, 255];
  }
  if (dist < innerR) {
    r = 34; g = 38; b = 46;
  }

  // Crosshair lines
  const hw = Math.max(1, Math.round(w * 0.025));
  if ((Math.abs(dx) <= hw && dist > innerR * 0.4 && dist < ringR * 1.1) ||
      (Math.abs(dy) <= hw && dist > innerR * 0.4 && dist < ringR * 1.1)) {
    return [255, 255, 255, 255];
  }

  // Center bullseye
  const bullseyeR = Math.max(2, w * 0.08);
  if (dist <= bullseyeR) {
    if (dist <= bullseyeR * 0.35) {
      return [255, 255, 255, 255]; // white center pin
    }
    return [223, 68, 51, 255]; // coral bullseye
  }

  return [r, g, b, a];
}

// Open Graph Image Pixel Generator (1200 x 630)
function ogPixel(x, y, w, h) {
  // Vignette & dark titanium background gradient
  const nx = x / w;
  const ny = y / h;
  const centerDist = Math.hypot(nx - 0.5, ny - 0.5);

  let r = Math.round(20 - centerDist * 8);
  let g = Math.round(22 - centerDist * 8);
  let b = Math.round(26 - centerDist * 8);

  // Top accent line in Sokkia Coral
  if (y < 4) {
    return [223, 68, 51, 255];
  }

  // Left banner subtle border
  if (x < 16) {
    return [223, 68, 51, Math.round(255 * (1 - x / 16))];
  }

  // Simulated instrument display / reticle preview on the right (cx ~ 920, cy ~ 315)
  const rcx = 900;
  const rcy = 315;
  const rdx = x - rcx;
  const rdy = y - rcy;
  const rdist = Math.hypot(rdx, rdy);

  // Reticle circle background
  if (rdist < 220) {
    const vignette = 1 - (rdist / 220) * 0.4;
    r = Math.round(28 * vignette);
    g = Math.round(33 * vignette);
    b = Math.round(40 * vignette);

    // Coral outer reticle ring
    if (Math.abs(rdist - 190) < 3.5) {
      return [223, 68, 51, 240];
    }
    if (Math.abs(rdist - 110) < 2) {
      return [80, 90, 110, 200];
    }
    // Crosshairs
    if ((Math.abs(rdx) < 1.5 && rdist > 30 && rdist < 210) ||
        (Math.abs(rdy) < 1.5 && rdist > 30 && rdist < 210)) {
      return [255, 255, 255, 255];
    }
    // Stadia ticks
    if (Math.abs(rdx) < 1.5 && (Math.abs(rdy - 60) < 1.5 || Math.abs(rdy + 60) < 1.5)) {
      return [255, 255, 255, 255];
    }
    if (Math.abs(rdy) < 1.5 && (Math.abs(rdx - 60) < 1.5 || Math.abs(rdx + 60) < 1.5)) {
      return [255, 255, 255, 255];
    }
    // Center laser pin
    if (rdist < 18) {
      if (rdist < 6) return [255, 255, 255, 255];
      return [223, 68, 51, 255];
    }
  }

  // Subtle grid lines in background
  if (x % 60 === 0 || y % 60 === 0) {
    r += 3; g += 3; b += 4;
  }

  return [r, g, b, 255];
}

console.log('Generating favicon-48x48.png...');
const fav48 = createPng(48, 48, iconPixel);

console.log('Generating apple-touch-icon.png (180x180)...');
const touch180 = createPng(180, 180, iconPixel);

console.log('Generating icon-192.png...');
const icon192 = createPng(192, 192, iconPixel);

console.log('Generating icon-512.png...');
const icon512 = createPng(512, 512, iconPixel);

console.log('Generating og-image.png (1200x630)...');
const ogImage = createPng(1200, 630, ogPixel);

const targetDirs = [
  path.join(__dirname, 'im105_simulator'),
  __dirname
];

for (const dir of targetDirs) {
  fs.writeFileSync(path.join(dir, 'favicon-48x48.png'), fav48);
  fs.writeFileSync(path.join(dir, 'apple-touch-icon.png'), touch180);
  fs.writeFileSync(path.join(dir, 'icon-192.png'), icon192);
  fs.writeFileSync(path.join(dir, 'icon-512.png'), icon512);
  fs.writeFileSync(path.join(dir, 'og-image.png'), ogImage);
}

console.log('All image assets created successfully across root and im105_simulator directories!');
