# OK Zoomer **Live**

A clean, semi‑professional screen magnifier for Windows with three capture modes — including a smooth **Live** mode that magnifies video and animation in real time without freezing, and stays visible to OBS/Zoom.

## 🚀 How to Run
- Run **`OK Zoomer Live.exe`** for the standalone app (no install needed).
- Or run `python magnifier.py` (requires Python 3.10+ and `PyQt6`).

## 🛠 Capture Modes
- **Live** — Smooth, real‑time magnification (uses the Windows Magnification API). Best for video/animation; visible to OBS/Zoom; no hall‑of‑mirrors recursion. *Requires Windows 10 2004+.*
- **Presentation** — A frozen snapshot you pan around. Visible to OBS, but static.
- **Stealth** — Live magnification that is invisible to screen recording.

## ✨ Features
- **Auto‑calibration** — screen size & display scaling are detected automatically; no DPI setup.
- **Tunable smoothness** — set Live mode's update rate (30–144 FPS) to match your monitor.
- **Shapes** — Circle, Square, Rectangle.
- **Pointer styles** — Normal, Hidden, Laser, Crosshair.
- **Customizable border** — white/off, rainbow cycle, or black.
- **Tabbed, resizable Settings** that remembers its size and position.

## ⌨️ Hotkeys
- **Hold Alt** (or your chosen key / middle mouse) to zoom.
- While zooming (keypad number):
  - `0` Cycle Pointer Styles (Normal, Hidden, Laser, Crosshair)
  - `1` Toggle Border (White / Hidden)
  - `2` Cycle Rainbow Border Colors
  - `3` Set Border to Black
  - `4` Cycle Shapes (Circle, Square, Rectangle)
  - `8` Toggle Spotlight (Dim screen) — snapshot/stealth modes
  - `Arrows` Adjust Zoom level and Magnifier size
