import { cpSync, existsSync, mkdirSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const here = dirname(fileURLToPath(import.meta.url));
const root = resolve(here, "..");

const copies = [
  {
    from: resolve(root, "node_modules", "@fortawesome", "fontawesome-free", "css", "all.min.css"),
    to: resolve(root, "static", "vendor", "fontawesome", "css", "all.min.css"),
  },
  {
    from: resolve(root, "node_modules", "@fortawesome", "fontawesome-free", "webfonts"),
    to: resolve(root, "static", "vendor", "fontawesome", "webfonts"),
  },
];

for (const copy of copies) {
  if (!existsSync(copy.from)) {
    throw new Error(`Missing source asset: ${copy.from}`);
  }

  mkdirSync(dirname(copy.to), { recursive: true });
  cpSync(copy.from, copy.to, { recursive: true, force: true });
  console.log(`Synced ${copy.from} -> ${copy.to}`);
}
