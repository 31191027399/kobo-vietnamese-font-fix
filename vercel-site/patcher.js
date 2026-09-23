(() => {
  const $ = (selector) => document.querySelector(selector);
  const chooseButton = $("#choose-kobo");
  const patchButton = $("#patch-selected");
  const status = $("#device-status");
  const warning = $("#browser-warning");
  const progress = $("#patch-progress");
  const progressFill = $("#progress-bar-fill");
  const progressLabel = $("#progress-label");
  const deviceDetails = $("#device-details");
  const deviceModel = $("#device-model");
  const deviceFirmware = $("#device-firmware");
  const deviceCompatibility = $("#device-compatibility");
  const vi = document.documentElement.lang === "vi";
  let koboRoot = null;
  let deviceInfo = null;

  const text = {
    unsupported: vi ? "Trình duyệt này chưa hỗ trợ chọn thư mục. Hãy dùng Chrome hoặc Edge trên HTTPS." : "This browser cannot choose a folder. Use Chrome or Edge on HTTPS.",
    cancelled: vi ? "Bạn chưa chọn thư mục Kobo." : "No Kobo folder selected.",
    wrongFolder: vi ? "Thư mục này không phải thư mục gốc của Kobo. Hãy chọn thư mục có .kobo/version." : "That is not the Kobo root. Choose the folder containing .kobo/version.",
    selected: vi ? "Đã chọn Kobo. Bạn có thể cài các mục bên dưới." : "Kobo selected. Choose components below, then patch.",
    noItems: vi ? "Hãy chọn ít nhất một thành phần." : "Choose at least one component.",
    writing: vi ? "Đang ghi dữ liệu vào Kobo…" : "Writing files to the Kobo…",
    done: vi ? "Đã cài xong. Hãy tháo Kobo an toàn rồi rút cáp." : "Patch staged. Eject the Kobo safely, then unplug the cable.",
    failed: vi ? "Không thể cài: " : "Patch failed: ",
    backup: vi ? "Đã sao lưu KoboRoot.tgz cũ." : "Backed up the existing KoboRoot.tgz.",
    firmwareUnknown: vi ? "Không đọc được phiên bản firmware; chỉ có thể tiếp tục với từ điển." : "Firmware version could not be read; only dictionary components can continue.",
    firmwareUnsupported: vi ? "Gói font và giao diện này chỉ dành cho firmware Kobo 4.x. Hãy kiểm tra phiên bản trước khi cài." : "The font and language packages are for Kobo firmware 4.x only. Check the firmware before installing.",
    firmwareSupported: vi ? "Firmware 4.x phù hợp với gói font và giao diện này." : "Firmware 4.x matches the font and language packages.",
  };

  const setProgress = (value, label) => {
    progress.hidden = false;
    progressFill.style.width = `${value}%`;
    progressLabel.textContent = label;
  };

  const setStatus = (message, kind = "") => {
    status.textContent = message;
    status.dataset.state = kind;
  };

  const getDirectory = async (parent, path, create = false) => {
    let current = parent;
    for (const part of path.split("/")) current = await current.getDirectoryHandle(part, { create });
    return current;
  };

  const writeBytes = async (directory, filename, data) => {
    const handle = await directory.getFileHandle(filename, { create: true });
    const writable = await handle.createWritable();
    try { await writable.write(data); } finally { await writable.close(); }
  };

  const fileExists = async (directory, filename) => {
    try { await directory.getFileHandle(filename); return true; } catch { return false; }
  };

  const backupKoboRoot = async (directory) => {
    if (!await fileExists(directory, "KoboRoot.tgz")) return;
    const old = await (await directory.getFileHandle("KoboRoot.tgz")).getFile();
    const stamp = new Date().toISOString().replace(/[:.]/g, "-");
    await writeBytes(directory, `KoboRoot.tgz.backup-${stamp}`, await old.arrayBuffer());
    setProgress(12, text.backup);
  };

  // Extracts the small, standard ZIP files used by the KOReader dictionary.
  // This avoids asking the user to download or unpack anything.
  const unzip = async (blob) => {
    const bytes = new Uint8Array(await blob.arrayBuffer());
    const view = new DataView(bytes.buffer);
    const decoder = new TextDecoder();
    const files = [];
    let offset = 0;
    while (offset + 30 <= bytes.length && view.getUint32(offset, true) === 0x04034b50) {
      const flags = view.getUint16(offset + 6, true);
      const method = view.getUint16(offset + 8, true);
      const compressedSize = view.getUint32(offset + 18, true);
      const nameLength = view.getUint16(offset + 26, true);
      const extraLength = view.getUint16(offset + 28, true);
      if ((flags & 8) || !compressedSize) throw new Error("Unsupported dictionary ZIP layout");
      const name = decoder.decode(bytes.slice(offset + 30, offset + 30 + nameLength));
      const start = offset + 30 + nameLength + extraLength;
      const payload = bytes.slice(start, start + compressedSize);
      let data;
      if (method === 0) data = payload;
      else if (method === 8) data = new Uint8Array(await new Response(new Blob([payload]).stream().pipeThrough(new DecompressionStream("deflate-raw"))).arrayBuffer());
      else throw new Error(`Unsupported ZIP compression: ${method}`);
      files.push({ name, data });
      offset = start + compressedSize;
    }
    return files;
  };

  const fetchAsset = async (name) => {
    const response = await fetch(`/assets/${name}`, { cache: "force-cache" });
    if (!response.ok) throw new Error(`Could not load ${name}`);
    return response.blob();
  };

  const inspectKobo = async (handle) => {
    const kobo = await handle.getDirectoryHandle(".kobo");
    const versionHandle = await kobo.getFileHandle("version");
    const raw = await (await versionHandle.getFile()).text();
    const model = raw.split(",", 1)[0].trim() || "Kobo";
    const match = raw.match(/\b\d+\.\d+\.\d+\b/g);
    const firmware = match ? match[match.length - 1] : null;
    const supported = Boolean(firmware && firmware.startsWith("4."));
    deviceInfo = { model, firmware, supported };
    deviceDetails.hidden = false;
    deviceDetails.dataset.state = supported ? "ok" : "warning";
    deviceModel.textContent = model;
    deviceFirmware.textContent = firmware || (vi ? "Không xác định" : "Unknown");
    deviceCompatibility.textContent = firmware ? (supported ? text.firmwareSupported : text.firmwareUnsupported) : text.firmwareUnknown;
    return kobo;
  };

  const writeKoboDictionary = async (root) => {
    const directory = await getDirectory(root, ".kobo/custom-dict", true);
    await writeBytes(directory, "dicthtml-en-vi.zip", await fetchAsset("tudien-kobo-en-vi.zip"));
  };

  const writeKoreaderDictionary = async (root) => {
    const files = await unzip(await fetchAsset("tudien-stardict-en-vi.zip"));
    const directory = await getDirectory(root, ".adds/koreader/data/dict/tudien-en-vi", true);
    const expected = {
      "tudien-stardict-en-vi-20260411.dict.dz": "tudien.dict.dz",
      "tudien-stardict-en-vi-20260411.idx": "tudien.idx",
      "tudien-stardict-en-vi-20260411.ifo": "tudien.ifo",
    };
    for (const file of files) if (expected[file.name]) await writeBytes(directory, expected[file.name], file.data);
  };

  const patch = async () => {
    const selected = [...document.querySelectorAll('input[name="component"]:checked')].map((input) => input.value);
    if (!selected.length) { setStatus(text.noItems, "error"); return; }
    patchButton.disabled = true;
    chooseButton.disabled = true;
    try {
      setProgress(5, text.writing);
      const kobo = await koboRoot.getDirectoryHandle(".kobo");
      const roots = selected.filter((item) => item === "fonts" || item === "language");
      if (roots.length && (!deviceInfo || !deviceInfo.supported)) throw new Error(deviceInfo?.firmware ? text.firmwareUnsupported : text.firmwareUnknown);
      if (roots.length) {
        await backupKoboRoot(kobo);
        const packageName = roots.length === 2 ? "KoboRoot-combined.tgz" : `KoboRoot-${roots[0]}.tgz`;
        setProgress(30, vi ? `Đang ghi ${packageName}…` : `Writing ${packageName}…`);
        await writeBytes(kobo, "KoboRoot.tgz", await fetchAsset(packageName));
      }
      if (selected.includes("kobo-dictionary")) {
        setProgress(58, vi ? "Đang cài từ điển Kobo…" : "Installing Kobo dictionary…");
        await writeKoboDictionary(koboRoot);
      }
      if (selected.includes("koreader-dictionary")) {
        setProgress(78, vi ? "Đang cài từ điển KOReader…" : "Installing KOReader dictionary…");
        await writeKoreaderDictionary(koboRoot);
      }
      setProgress(100, text.done);
      setStatus(text.done, "success");
    } catch (error) {
      setStatus(`${text.failed}${error.message}`, "error");
      progress.hidden = true;
    } finally {
      patchButton.disabled = false;
      chooseButton.disabled = false;
    }
  };

  const choose = async () => {
    if (!("showDirectoryPicker" in window)) { warning.hidden = false; setStatus(text.unsupported, "error"); return; }
    try {
      const handle = await window.showDirectoryPicker({ mode: "readwrite", id: "kobo-root" });
      await inspectKobo(handle);
      koboRoot = handle;
      setStatus(text.selected, "success");
      patchButton.disabled = false;
      warning.hidden = true;
    } catch (error) {
      deviceInfo = null;
      deviceDetails.hidden = true;
      if (error.name !== "AbortError") setStatus(text.wrongFolder, "error");
      else setStatus(text.cancelled);
      patchButton.disabled = true;
    }
  };

  chooseButton.addEventListener("click", choose);
  patchButton.addEventListener("click", patch);
  if (!("showDirectoryPicker" in window)) warning.hidden = false;
})();
