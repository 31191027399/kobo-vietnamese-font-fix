const $ = (selector) => document.querySelector(selector);
const state = { status: null, busy: false };
const allComponents = ["nickelmenu", "koreader", "simpleui"];

function setLog(message, kind = "ready") {
  $("#log").textContent = message;
  const badge = $("#busy-badge");
  badge.className = `badge ${kind === "ready" ? "" : kind}`;
  badge.textContent = kind === "busy" ? "Working" : kind === "success" ? "Complete" : kind === "error" ? "Needs attention" : "Ready";
}

function formatResult(action, result) {
  if (action === "build") return "The Vietnamese font package is ready. You can now install it on your Kobo.";
  if (action === "repair-upload") return `Repaired ${result.sourceFile} with the 16 Vietnamese fonts. You can now install it on your Kobo.`;
  if (action === "eject") return "Your Kobo was safely ejected. Unplug it, then wait for its restart to finish.";
  const names = { nickelmenu: "Vietnamese font fix", koreader: "KOReader", simpleui: "SimpleUI" };
  return `Installed: ${Object.keys(result || {}).map((item) => names[item] || item).join(", ")}. A recovery backup was created before the changes. Now choose Safely eject Kobo.`;
}

function renderStatus(status) {
  state.status = status;
  const dot = $("#device-dot");
  dot.className = "status-dot";
  if (!status.mounted) {
    $("#device-title").textContent = "Connect your Kobo";
    $("#device-detail").textContent = "Plug it in by USB, then tap Connect on the Kobo screen.";
  } else {
    dot.classList.add(status.firmwareSupported ? "connected" : "unsupported");
    $("#device-title").textContent = status.firmwareSupported ? "Kobo ready" : "Firmware needs review";
    const parts = [`Firmware ${status.firmware || "unknown"}`];
    if (status.koreader) parts.push(`KOReader ${status.koreader}`);
    if (status.simpleui) parts.push(`SimpleUI ${status.simpleui}`);
    $("#device-detail").textContent = status.firmwareSupported ? `${parts.join(" · ")}. Choose Install everything below.` : `${parts.join(" · ")}. The Vietnamese font fix needs Kobo firmware 4.x.`;
  }
  const pkg = status.nickelmenuPackage;
  $("#build-facts").textContent = pkg ? `Ready: Vietnamese font package with ${pkg.fonts} fonts.` : `The Vietnamese font package needs rebuilding${status.nickelmenuPackageError ? `: ${status.nickelmenuPackageError}` : "."}`;
  updateButtons();
}

function updateButtons() {
  const connected = Boolean(state.status?.mounted);
  const supported = Boolean(state.status?.firmwareSupported);
  const packageReady = Boolean(state.status?.nickelmenuPackage);
  const selected = [...document.querySelectorAll('input[name="component"]:checked')].map((input) => input.value);
  $("#install-all").disabled = state.busy || !connected || !supported || !packageReady;
  $("#install-custom").disabled = state.busy || !connected || !supported || selected.length === 0 || (selected.includes("nickelmenu") && !packageReady);
  $("#eject").disabled = state.busy || !connected;
  $("#build").disabled = state.busy;
  $("#repair-upload").disabled = state.busy || !$("#nickelmenu-upload").files.length;
  $("#refresh").disabled = state.busy;
}

async function request(path, options = {}) {
  const response = await fetch(path, options);
  const payload = await response.json();
  if (payload.status) renderStatus(payload.status);
  if (!response.ok || !payload.ok) throw new Error(payload.error || `Request failed: ${response.status}`);
  return payload.result;
}

async function refresh() {
  try {
    const response = await fetch("/api/status", { cache: "no-store" });
    renderStatus((await response.json()).status);
  } catch (error) { setLog(`Could not reach the local installer: ${error.message}`, "error"); }
}

async function runAction(label, action, path, body = {}) {
  state.busy = true; updateButtons(); setLog(`${label}…`, "busy");
  try {
    const result = await request(path, { method: "POST", headers: { "Content-Type": "application/json", "X-Kobo-Installer": "1" }, body: JSON.stringify(body) });
    setLog(formatResult(action, result), "success");
  } catch (error) { setLog(error.message, "error");
  } finally { state.busy = false; await refresh(); updateButtons(); }
}

$("#refresh").addEventListener("click", refresh);
$("#build").addEventListener("click", () => runAction("Rebuilding the font package", "build", "/api/build"));
$("#nickelmenu-upload").addEventListener("change", updateButtons);
$("#repair-upload").addEventListener("click", async () => {
  const file = $("#nickelmenu-upload").files[0];
  if (!file) return;
  const bytes = new Uint8Array(await file.arrayBuffer());
  let binary = "";
  for (let index = 0; index < bytes.length; index += 0x8000) binary += String.fromCharCode(...bytes.subarray(index, index + 0x8000));
  runAction("Adding Vietnamese fonts to the uploaded package", "repair-upload", "/api/repair-upload", {
    filename: file.name,
    version: $("#nickelmenu-version").value,
    archiveBase64: btoa(binary),
  });
});
$("#install-all").addEventListener("click", () => runAction("Installing your Kobo setup", "install", "/api/install", { components: allComponents }));
$("#install-custom").addEventListener("click", () => runAction("Installing selected items", "install", "/api/install", { components: [...document.querySelectorAll('input[name="component"]:checked')].map((input) => input.value) }));
$("#eject").addEventListener("click", () => runAction("Safely ejecting Kobo", "eject", "/api/eject"));
document.querySelectorAll('input[name="component"]').forEach((input) => input.addEventListener("change", updateButtons));
refresh();
