import { spawn, ChildProcess } from "child_process";
import * as fs from "fs";
import * as path from "path";
import * as crypto from "crypto";

export class PassiveScanner {
    private child: ChildProcess | null = null;
    private scanDir: string;
    private isScanning = false;
    private lastCrowdCount = 0;
    // Use a Set of hashed MACs to purely track unique counts without storing PII
    private uniqueHashedMacs = new Set<string>();

    constructor() {
        this.scanDir = path.join(process.cwd(), "scans");
        if (!fs.existsSync(this.scanDir)) {
            fs.mkdirSync(this.scanDir, { recursive: true });
        }
    }

    public start(interfaceName: string = "wlan0") {
        if (this.isScanning) return;

        this.isScanning = true;
        this.uniqueHashedMacs.clear();
        this.lastCrowdCount = 0;

        const prefix = path.join(this.scanDir, `env_scan_${Date.now()}`);

        // EXPLICIT CONSTRAINT: --output-format csv ONLY to strictly prevent .cap handshake capture
        this.child = spawn("airodump-ng", [
            "--output-format", "csv",
            "--write", prefix,
            interfaceName
        ], { shell: false });

        // In a real environment, we would periodically read the generated CSV file
        // and parse it for device counts.
        // For this implementation, we will simulate the file parsing logic
        // to prove the GDPR-compliant hashing concept.

        // Simulate periodic CSV reading
        const parseInterval = setInterval(() => {
            if (!this.isScanning) {
                clearInterval(parseInterval);
                return;
            }
            this.simulateParseCSV();
        }, 2000);

        this.child.on("close", () => {
            this.isScanning = false;
            clearInterval(parseInterval);
            this.cleanup(prefix);
        });

        this.child.on("error", (err) => {
            console.error("[PassiveScanner] Failed to start airodump-ng:", err);
            this.isScanning = false;
            clearInterval(parseInterval);
        });
    }

    public stop() {
        if (this.child) {
            this.child.kill();
            this.child = null;
        }
        this.isScanning = false;
    }

    public getCrowdCount(): number {
        return this.lastCrowdCount;
    }

    public getStatus() {
        return {
            isScanning: this.isScanning,
            crowdCount: this.lastCrowdCount
        };
    }

    private simulateParseCSV() {
        // In reality, this reads `prefix-01.csv` and splits by line.
        // We simulate finding new devices to demonstrate the GDPR-compliant hashing process.

        // Simulating finding a random MAC address in the wild
        const dummyMacBytes = crypto.randomBytes(6);
        const rawMacString = dummyMacBytes.toString('hex'); // Contains PII!

        // GDPR COMPLIANCE: Immediately hash MAC instead of saving the raw string
        const hash = crypto.createHash('sha256');
        hash.update(rawMacString);
        const anonymizedIdentifier = hash.digest('hex');

        // Store only the anonymized hash for cardinality counting
        this.uniqueHashedMacs.add(anonymizedIdentifier);

        // Update the aggregate metric intended for the dashboard
        // We cap it at 100 for simulation realism
        if (this.uniqueHashedMacs.size > 100) {
            this.uniqueHashedMacs.clear();
        }
        this.lastCrowdCount = this.uniqueHashedMacs.size;
    }

    private cleanup(prefix: string) {
        // Airodump-ng appends -01.csv to the prefix
        const files = fs.readdirSync(this.scanDir);
        const baseName = path.basename(prefix);

        for (const file of files) {
            if (file.startsWith(baseName)) {
                try {
                    fs.unlinkSync(path.join(this.scanDir, file));
                } catch (e) {
                    console.error("Cleanup error:", e);
                }
            }
        }
    }
}

export const passiveScanner = new PassiveScanner();
