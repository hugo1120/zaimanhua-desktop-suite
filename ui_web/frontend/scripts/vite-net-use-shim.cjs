const childProcess = require("node:child_process");
const { EventEmitter } = require("node:events");

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
