# Design Guidelines: Wi-Fi CSI Signal Processing Dashboard

## Design Approach
**Selected System:** Material Design (data-rich applications focus)  
**Rationale:** Scientific dashboard requiring clear data hierarchy, robust component library, and strong visual feedback for complex interactions. No marketing elements—this is a functional analysis tool.

## Design Principles
- **Data First:** Every pixel serves analytical purpose—no decorative elements
- **Clarity Over Beauty:** Legibility and information hierarchy trump aesthetics
- **Immediate Utility:** All controls and visualizations visible without scrolling on primary viewport

---

## Typography System

**Primary Font:** Inter (via Google Fonts)
- Dashboard Title: text-2xl font-semibold
- Module Headers: text-lg font-medium
- Data Labels: text-sm font-normal
- Metrics/Values: text-base font-mono (tabular numbers)
- Controls/Buttons: text-sm font-medium

---

## Layout Architecture

**Spacing Primitives:** Tailwind units of 2, 4, 6, 8
- Module padding: p-6
- Inter-module gaps: gap-4
- Control spacing: space-y-2
- Button padding: px-4 py-2

**Grid Structure:**
```
Top Bar (h-16): App title, status indicators, global controls
Main Dashboard (remaining height):
  - Left Sidebar (w-80): Control panels, parameter inputs
  - Center Area (flex-1): 3D visualization canvas
  - Right Panel (w-96): Time-series plots, AoA heatmap

Responsive: Stack vertically on <lg screens
```

---

## Component Library

### Navigation & Structure
- **Top Bar:** Fixed header with app title, connection status badge, data source selector
- **Control Panels:** Collapsible sections with clear labels, organized by function (Signal Nulling, ISAR, Gesture Recognition)
- **Module Cards:** Elevation-1 containers (shadow-sm) for each visualization/control group

### Data Visualization
- **3D Point Cloud:** Full-height canvas with rotation controls, axis labels, real-time rendering
- **Heatmap (Time vs. Angle):** 2D grid with color-coded intensity, scrollable time axis
- **Signal Traces:** Line graphs with clear axes, grid lines, hover tooltips for values
- **Status Indicators:** Live signal strength bars, processing state badges

### Input Controls
- **Parameter Inputs:** Labeled number fields with units (e.g., "Threshold: [___] dB")
- **Toggles:** Switches for algorithm enable/disable (nulling, tracking)
- **Dropdowns:** Device selection, algorithm mode selection
- **Action Buttons:** Primary (start/stop processing), secondary (reset, export data)

### Data Display
- **Metrics Cards:** Grid layout showing key values (AoA, amplitude, gesture detected)
- **Tables:** Scrollable data logs with monospace font, zebra striping
- **Alerts:** Toast notifications for system events (connection lost, gesture detected)

---

## Visual Hierarchy

**Information Layers:**
1. Live visualizations (highest priority—center stage)
2. Control parameters (left sidebar—immediate access)
3. Derived metrics (right panel—supporting data)
4. System status (top bar—always visible)

**Contrast Principles:**
- Strong borders (border-2) for visualization containers
- Subtle backgrounds (bg-gray-50) for input groups
- Elevated cards (shadow-md) for active/focused modules
- Grid lines at 10-15% opacity for chart readability

---

## Dashboard Sections

### 1. Top Control Bar
- Application title, hardware connection status (green/red indicator), data source dropdown, emergency stop button

### 2. Signal Processing Panel (Left)
- **Nulling Controls:** h1/h2 ratio display, precoding threshold slider, enable toggle
- **ISAR Parameters:** Array length input, MUSIC algorithm settings, AoA range selector
- **Gesture Filters:** Centroid tracking toggle, matched filter thresholds

### 3. Main Visualization Area (Center)
- **3D Point Cloud:** Interactive canvas showing (x,y,z) coordinates, color-coded by amplitude
- **Controls Overlay:** Rotation buttons, zoom slider, axis toggle (subtle, bottom-right)

### 4. Analysis Panel (Right)
- **AoA Heatmap:** Time (vertical) × Angle (horizontal), scrollable
- **Signal Traces:** Real-time amplitude plots for h1/h2 channels
- **Gesture Log:** List of detected 0/1 bits with timestamps

---

## No Images/Marketing Elements
This is a functional scientific tool—no hero images, no decorative graphics. All visual elements are data-driven (plots, charts, 3D renders).

---

## Accessibility & Performance
- Keyboard shortcuts for start/stop (Space), reset (R)
- High-contrast mode for data visualization (toggle in top bar)
- Frame rate limiter for 3D rendering (30 fps default)
- Clear loading states during signal processing

---

**Final Note:** Prioritize information density and immediate tool access over visual flourish. Every component serves the analytical workflow.