/**
 * Session Store — JSON file-based persistent storage for session reports.
 *
 * Each session is saved as a JSON file in data/sessions/.
 * An index file (_index.json) maintains a fast-lookup summary list.
 */

import * as fs from "fs";
import * as path from "path";
import { dataDir } from "./data-dir";

export interface SessionSummary {
    id: string;
    name?: string;
    startTime: number;
    endTime: number;
    durationS: number;
    totalFrames: number;
    targetClassification: string;
    classificationConfidence: number;
    avgDistanceCm: number;
    avgSpeedMs: number;
    dataSource: string;
}

export interface StoredSession extends SessionSummary {
    classificationBreakdown: Record<string, number>;
    spatialMetrics: {
        minDistanceCm: number;
        maxDistanceCm: number;
        avgDistanceCm: number;
        boundingBox: { xMin: number; xMax: number; zMin: number; zMax: number };
    };
    kinematicData: {
        avgSpeedMs: number;
        maxSpeedMs: number;
    };
    eventTimeline: {
        time: number;
        elapsed: number;
        elapsedFormatted: string;
        description: string;
        distance?: number;
    }[];
}

const DATA_DIR = dataDir("sessions");
const INDEX_FILE = path.join(DATA_DIR, "_index.json");

function ensureDir() {
    if (!fs.existsSync(DATA_DIR)) {
        fs.mkdirSync(DATA_DIR, { recursive: true });
    }
}

function readIndex(): SessionSummary[] {
    ensureDir();
    if (!fs.existsSync(INDEX_FILE)) return [];
    try {
        return JSON.parse(fs.readFileSync(INDEX_FILE, "utf-8"));
    } catch {
        return [];
    }
}

function writeIndex(index: SessionSummary[]) {
    ensureDir();
    fs.writeFileSync(INDEX_FILE, JSON.stringify(index, null, 2), "utf-8");
}

export class SessionStore {
    /** Save a session report to disk and add to index. */
    save(session: StoredSession, customName?: string): void {
        ensureDir();
        const index = readIndex();

        // Calculate next sequential index
        const maxIndex = index.reduce((max, s) => {
            if (!s.id) return max;
            const numStr = s.id.split(' - ')[0];
            const num = parseInt(numStr, 10);
            return !isNaN(num) ? Math.max(max, num) : max;
        }, 0);
        const nextIndex = maxIndex + 1;

        // Generate ID: 000000001 - YYYY-MM-DD
        const dateStr = new Date(session.startTime).toISOString().split('T')[0];
        const newId = `${String(nextIndex).padStart(9, '0')} - ${dateStr}`;

        session.id = newId;
        if (customName && customName.trim() !== "") {
            (session as any).name = customName.trim();
        }

        const filePath = path.join(DATA_DIR, `${session.id}.json`);
        fs.writeFileSync(filePath, JSON.stringify(session, null, 2), "utf-8");

        const existing = index.findIndex((s) => s.id === session.id);
        const summary: SessionSummary = {
            id: session.id,
            name: (session as any).name,
            startTime: session.startTime,
            endTime: session.endTime,
            durationS: session.durationS,
            totalFrames: session.totalFrames,
            targetClassification: session.targetClassification,
            classificationConfidence: session.classificationConfidence,
            avgDistanceCm: session.spatialMetrics.avgDistanceCm,
            avgSpeedMs: session.kinematicData.avgSpeedMs,
            dataSource: session.dataSource,
        };

        if (existing >= 0) {
            index[existing] = summary;
        } else {
            index.unshift(summary); // newest first
        }

        writeIndex(index);
        console.log(`[SESSION] Saved session ${session.id} (${session.totalFrames} frames)`);
    }

    /** Get full session data by ID. */
    getById(id: string): StoredSession | null {
        const filePath = path.join(DATA_DIR, `${id}.json`);
        if (!fs.existsSync(filePath)) return null;
        try {
            return JSON.parse(fs.readFileSync(filePath, "utf-8"));
        } catch {
            return null;
        }
    }

    /** List all sessions (summary only), optionally filtered. */
    list(options?: {
        search?: string;
        classification?: string;
        limit?: number;
        offset?: number;
    }): { sessions: SessionSummary[]; total: number } {
        let index = readIndex();

        // Search filter
        if (options?.search) {
            const q = options.search.toLowerCase();
            index = index.filter(
                (s) =>
                    s.id.toLowerCase().includes(q) ||
                    (s.name && s.name.toLowerCase().includes(q)) ||
                    s.targetClassification.toLowerCase().includes(q) ||
                    s.dataSource.toLowerCase().includes(q) ||
                    new Date(s.startTime).toLocaleString().toLowerCase().includes(q)
            );
        }

        // Classification filter
        if (options?.classification) {
            index = index.filter(
                (s) => s.targetClassification === options.classification
            );
        }

        const total = index.length;
        const offset = options?.offset ?? 0;
        const limit = options?.limit ?? 50;
        const sessions = index.slice(offset, offset + limit);

        return { sessions, total };
    }

    /** Delete a session by ID. */
    delete(id: string): boolean {
        const filePath = path.join(DATA_DIR, `${id}.json`);
        if (fs.existsSync(filePath)) {
            fs.unlinkSync(filePath);
        }

        const index = readIndex();
        const newIndex = index.filter((s) => s.id !== id);
        if (newIndex.length === index.length) return false;

        writeIndex(newIndex);
        console.log(`[SESSION] Deleted session ${id}`);
        return true;
    }

    /** Get count of stored sessions. */
    count(): number {
        return readIndex().length;
    }
}

export const sessionStore = new SessionStore();
