import childProcess from "node:child_process";
import { EventEmitter } from "node:events";
import { fileURLToPath } from "node:url";
import path from "node:path";

const originalExec = childProcess.exec.bind(childProcess);

function createNoopChildProcess() {
  const proc = new EventEmitter();
  proc.stdout = null;
  proc.stderr = null;
  proc.kill = () => true;
  return proc;
}

childProcess.exec = function patchedExec(command, options, callback) {
  let resolvedOptions = options;
  let resolvedCallback = callback;
  if (typeof resolvedOptions === "function") {
    resolvedCallback = resolvedOptions;
    resolvedOptions = undefined;
  }

  if (String(command).trim().toLowerCase() === "net use") {
    const proc = createNoopChildProcess();
    queueMicrotask(() => {
      if (typeof resolvedCallback === "function") {
        resolvedCallback(null, "", "");
      }
      proc.emit("exit", 0);
      proc.emit("close", 0);
    });
    return proc;
  }

  return originalExec(command, resolvedOptions, resolvedCallback);
};

const scriptDir = path.dirname(fileURLToPath(import.meta.url));
const frontendRoot = path.resolve(scriptDir, "..");
const configFile = path.resolve(frontendRoot, "vite.config.ts");
const { build } = await import("vite");

await build({
  configFile,
  root: frontendRoot,
  build: {
    outDir: path.resolve(frontendRoot, "dist"),
    emptyOutDir: true,
    write: true,
  },
});
