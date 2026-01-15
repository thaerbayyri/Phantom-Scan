# Wi-Vi Dashboard - CSI Signal Processing

## Overview

This is a Wi-Fi Vision (Wi-Vi) signal processing dashboard for real-time CSI (Channel State Information) imaging, human tracking, and gesture recognition. The application processes Wi-Fi signals using ISAR (Inverse Synthetic Aperture Radar) and MUSIC (Multiple Signal Classification) algorithms to detect and track human movement through walls.

The dashboard provides:
- Real-time 3D point cloud visualization of detected objects
- Angle of Arrival (AoA) spectrum analysis and heatmaps
- Signal nulling to remove static reflections
- Gesture recognition for human motion detection
- Live signal trace monitoring

## User Preferences

Preferred communication style: Simple, everyday language.

## System Architecture

### Frontend Architecture
- **Framework**: React 18 with TypeScript
- **Routing**: Wouter (lightweight React router)
- **State Management**: TanStack React Query for server state, React hooks for local state
- **UI Components**: shadcn/ui component library built on Radix UI primitives
- **Styling**: Tailwind CSS with CSS variables for theming (light/dark mode support)
- **Visualization**: Plotly.js via react-plotly.js for 3D plots, heatmaps, and time-series charts
- **Build Tool**: Vite with React plugin

### Backend Architecture
- **Runtime**: Node.js with Express
- **Language**: TypeScript (ESM modules)
- **Real-time Communication**: WebSocket (ws library) for streaming signal data
- **API Style**: REST endpoints for configuration, WebSocket for real-time data streaming

### Data Flow
1. Signal data enters via WebSocket or demo data generator
2. Server-side signal processing applies nulling, MUSIC algorithm, and gesture detection
3. Processed data streams to connected clients via WebSocket
4. React components render visualizations using Plotly.js

### Signal Processing Pipeline
- **Complex number utilities**: Custom implementation for DSP operations
- **Signal nulling**: Removes static reflections using precoding ratio calculation
- **MUSIC algorithm**: Computes AoA spectrum for direction estimation
- **Gesture detection**: Identifies movement patterns from centroid tracking
- **Heatmap accumulation**: Builds time-angle intensity maps

### Database
- **ORM**: Drizzle ORM configured for PostgreSQL
- **Schema Location**: `shared/schema.ts` using Zod for validation
- **Current Usage**: Schema defines signal processing data types; user storage uses in-memory implementation

### Project Structure
```
├── client/src/          # React frontend
│   ├── components/      # UI components (dashboard widgets, shadcn/ui)
│   ├── hooks/           # Custom React hooks (WebSocket, mobile detection)
│   ├── lib/             # Utilities (complex math, query client)
│   └── pages/           # Route components
├── server/              # Express backend
│   ├── lib/             # Signal processing, WebSocket server
│   └── routes.ts        # API endpoints
├── shared/              # Shared TypeScript types and Zod schemas
└── migrations/          # Drizzle database migrations
```

## External Dependencies

### Third-Party Services
- **PostgreSQL**: Database (configured via DATABASE_URL environment variable)
- **Google Fonts**: Inter font family for typography

### Key Libraries
- **Frontend**: React, Plotly.js, Radix UI, TanStack Query, Tailwind CSS
- **Backend**: Express, ws (WebSocket), Drizzle ORM, Zod
- **Build**: Vite, esbuild, TypeScript

### Development Tools
- **Replit Plugins**: Runtime error overlay, cartographer, dev banner (development only)
- **Database Tools**: Drizzle Kit for schema migrations (`npm run db:push`)