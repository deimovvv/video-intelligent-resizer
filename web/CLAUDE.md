# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Development Commands

- **Development server**: `npm run dev` (uses Turbopack for faster builds)
- **Build**: `npm run build` (production build with Turbopack)
- **Start**: `npm start` (serves production build)
- **Lint**: `npm run lint` (ESLint with Next.js config)

## Architecture Overview

This is a **Next.js 15** application using the **App Router** architecture with:

- **Frontend**: React 19 with TypeScript, Tailwind CSS v4
- **Main application**: Single-page video batch resizer tool (`src/app/page.tsx`)
- **Backend integration**: Communicates with external API at `API_BASE` (default: http://127.0.0.1:8000)
- **File structure**: Standard Next.js App Router layout with components in `src/components/`

### Key Components

- **Main application** (`src/app/page.tsx`): Complex form handling video processing with three modes:
  - `resize`: Basic FFmpeg resizing
  - `tracked`: Face detection + CSRT tracking
  - `tracked_yolo`: YOLOv8-based object tracking
- **URL normalization** (`src/lib/urlNormalize.ts`): Handles Google Drive, Dropbox, and OneDrive URL conversion for direct downloads
- **Reusable components**: `FieldLabel`, `Toast`, `Progress`, `Sidebar` - all with consistent dark theme styling

### Application Flow

1. User inputs video URLs (one per line) - supports cloud storage links
2. Selects processing mode, codec (H.264/ProRes), and aspect ratios (9:16, 1:1, 16:9)
3. Configures tracking parameters if using tracked modes
4. Submits to backend API at `/resize` endpoint
5. Receives and downloads ZIP file with processed videos

### State Management

Uses React hooks for local state management:
- Form inputs and validation
- Loading states and progress indication  
- Toast notifications for user feedback
- URL normalization and validation

### Styling

- **Dark theme**: Neutral-950 background with consistent neutral color palette
- **Tailwind CSS v4**: Modern utility-first styling
- **Component styling**: Consistent rounded corners, shadows, and hover states

## TypeScript Configuration

- Path aliases: `@/*` maps to `./src/*`
- Strict mode enabled with Next.js plugin integration
- ES2017 target with modern module resolution