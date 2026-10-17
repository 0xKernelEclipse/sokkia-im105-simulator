# Sokkia iM-105 Total Station Web Simulator

> An authentic, interactive single-page web simulator of the **Sokkia iM-105 Total Station** (iM-100 Series) designed and developed by **Eyad Mohamed Mekky**.

[![Live Demo](https://img.shields.io/badge/Live_Demo-Vercel-black?style=for-the-badge&logo=vercel)](https://sokkia-im105-simulator.vercel.app/)
[![JavaScript](https://img.shields.io/badge/ES6+-Vanilla_JS-F7DF1E?style=for-the-badge&logo=javascript&logoColor=black)](https://developer.mozilla.org/en-US/docs/Web/JavaScript)
[![HTML5](https://img.shields.io/badge/HTML5-Semantic-E34F26?style=for-the-badge&logo=html5&logoColor=white)](https://developer.mozilla.org/en-US/docs/Web/HTML)
[![CSS3](https://img.shields.io/badge/CSS3-Modern-1572B6?style=for-the-badge&logo=css3&logoColor=white)](https://developer.mozilla.org/en-US/docs/Web/CSS)

---

## 🌟 Overview

The **Sokkia iM-105 Total Station Simulator** faithfully reproduces both the physical hardware faceplate and the onboard firmware operating system of the Sokkia iM-100 Series Total Station according to the official manufacturer manual (`im-100_e_ab.pdf`).

Designed for **civil engineering students**, **surveying professors**, and **field technicians**, it provides a zero-installation, browser-based environment to practice equipment operations, leveling, angle measurement, EDM distance calculation, resection, and stake-out.

---

## 🚀 Key Features

* **Authentic Dot-Matrix LCD Display:** Multi-page menu system with real graphical fonts, status bar indicators (Battery, Tilt sensor, Reflector mode, EDM active, Face 1/Face 2, Shift).
* **Complete Physical Keypad:** 
  - Alphanumeric keypad with triple-tap character entry (`0-9`, `A-Z`, symbols).
  - Softkeys `F1`–`F4` corresponding to dynamic on-screen function legends.
  - Directional 4-way D-Pad, dedicated red `ENT` button, `ESC`, `B.S.`, `FUNC` (page switch), and `SHIFT` (reflector mode toggle).
* **Dual-Axis Electronic Tilt Bubble:**
  - Real-time graphic circular (bullseye) and tubular spirit bubble levels.
  - Live angular tilt readouts in arc-seconds ($X$ and $Y$ axes) with out-of-range sensor alerts.
* **Observation Mode (OBS):**
  - **Page 1:** Slope Distance (`SD`), Horizontal Angle Right (`HA-R`), Zenith Angle (`ZA`).
  - **Page 2:** Horizontal Distance (`HD`), Vertical Distance (`VD`), Zenith Angle (`ZA`).
  - **Page 3:** Coordinate Jump, Station Orientation (`Occ.Orien`), Configuration (`CNFG`).
* **Advanced Surveying Routines:**
  - **Occ.Orien:** Set occupied station coordinates $(N_0, E_0, Z_0)$, instrument height, and backsight azimuth/coordinates.
  - **COORD:** Live 3D coordinate calculation with target height offset.
  - **RESECTION:** 2-point free-station resection solver calculating instrument position with standard error checks.
  - **S-O (Stake-Out):** Real-time directional angle difference ($dHA$) and distance difference ($dHD$) with frequency-modulated audio alignment beeps.
  - **MLM (Missing Line Measurement):** Computes horizontal distance, slope distance, height difference, and percentage grade between survey targets.
  - **AREA:** Sequential coordinate boundary measurement with automatic 2D surface area ($m^2$ / $ft^2$) and perimeter calculation.
  - **REM (Remote Elevation Measurement):** Calculates overhead heights of inaccessible objects (wires, bridges) from baseline ground sightings.
* **Interactive Field Sighting Bar:**
  - Live crosshair reticle telescope view with fine tangent adjustment screws.
  - Realistic target presets: Survey Prism, Building Corner, Traverse Control, Boundary Stake.
  - Telescope Plunge: 180° transit between Face 1 (Direct) and Face 2 (Reverse) with automatic vertical circle zenith angle index reversal ($360^\circ - ZA$).
* **Audio Synthesizer Engine:** Web Audio API sound synthesis providing authentic mechanical key clicks, double-beeps for zero-set/EDM, and proximity beeps for stake-out.
* **Data Memory Manager:** View recorded points and export job coordinates directly to **CSV** format.
* **Progressive Web App (PWA):** Offline Service Worker caching and 1-click device installation on desktop PCs, laptops, Android phones, and iOS.
* **Mobile & Tablet Optimized:** Frosted-glass desktop site guidance popup and smooth horizontal pan container for small screens.

---

## 📱 Mobile & PWA Device Installation

- **Device Installation:** Click the **"Install App"** button in the header bar or your browser's address bar to install the simulator natively on Windows, macOS, ChromeOS, or Android.
- **Mobile Browsing:** Designed to maintain the physical faceplate's exact dimensions. On mobile devices, users can pan horizontally, rotate to **Landscape**, or tap the browser menu (three dots `⋮` in Chrome or `aA` in Safari) and select **"Desktop site"** for an authentic desktop instrument layout.

---

## ⌨️ PC Keyboard Shortcuts

| Key | Total Station Action |
|---|---|
| <kbd>F1</kbd> – <kbd>F4</kbd> | Softkeys F1 through F4 |
| <kbd>0</kbd> – <kbd>9</kbd>, <kbd>.</kbd>, <kbd>±</kbd> | Numeric / Alphanumeric keypad |
| <kbd>Enter</kbd> | ENT (Confirm / Select) |
| <kbd>Esc</kbd> | ESC (Back / Cancel) |
| <kbd>Backspace</kbd> | B.S. (Backspace text) |
| <kbd>Tab</kbd> | FUNC (Switch OBS page / toggle alpha) |
| <kbd>Shift</kbd> | SHIFT (Cycle Prism / Sheet / Reflectorless) |
| <kbd>*</kbd> | Starkey (Quick illumination & tilt menu) |
| <kbd>Arrow Keys</kbd> | 4-Way D-Pad navigation |

---

## 🛠️ Deployment & Local Setup

### Running Locally
Simply open `index.html` in any modern web browser (Google Chrome, Microsoft Edge, Safari, Mozilla Firefox):
```bash
# On Windows
start index.html

# Or run the included launcher
Launch_Sokkia_iM105.bat
```

### Deploying to Vercel
The repository includes a ready-to-deploy `vercel.json` with pre-configured security headers and caching:
```bash
# Using Vercel CLI
vercel --prod
```

---

## 👨‍💻 Author & Credits

**Engineered and Developed by:**  
**Eyad Mohamed Mekky**

- 📧 Email: [eyadmohamedmekky@gmail.com](mailto:eyadmohamedmekky@gmail.com)
- 🎵 TikTok: [@eyad.mo7amed.mekky](https://www.tiktok.com/@eyad.mo7amed.mekky)
- 📸 Instagram: [@eyad_mo7amed_mekky](https://www.instagram.com/eyad_mo7amed_mekky/)

---

## 📄 License & References

- Firmware specifications and operating workflows modeled according to the official Topcon / Sokkia iM-100 Series Manual (`im-100_e_ab.pdf`).
- Licensed under the **MIT License**.
