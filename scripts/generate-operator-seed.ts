import { generateOperatorSeed } from "../server/auth/service";
import fs from "fs";
import path from "path";

const [, , username, password, ...rest] = process.argv;
const outputIndex = rest.findIndex((arg) => arg === "--output");
const outputPath = outputIndex >= 0 ? rest[outputIndex + 1] : undefined;

if (!username || !password) {
  console.error("Usage: tsx scripts/generate-operator-seed.ts <username> <password> [--output <path>]");
  process.exit(1);
}

const seed = generateOperatorSeed(username, password);
const payload = `${JSON.stringify(seed, null, 2)}\n`;

if (outputPath) {
  const resolved = path.resolve(outputPath);
  fs.mkdirSync(path.dirname(resolved), { recursive: true });
  fs.writeFileSync(resolved, payload, "utf-8");
  console.log(`Wrote operator seed to ${resolved}`);
} else {
  console.log(payload.trimEnd());
}
