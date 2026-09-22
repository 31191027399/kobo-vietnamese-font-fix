const $ = (selector) => document.querySelector(selector);
const state = { status: null, busy: false, selectedDevice: null, polling: false, deviceKey: null, actionId: null, actionTimer: null };

const translations = {
  en: {
    eyebrow: "Vietnamese add-on", title: "Kobo Vietnamese Installer", lede: "Add Vietnamese fonts and English–Vietnamese dictionaries without replacing your Kobo tools or personal data.", language: "Language", checking: "Checking for Kobo…", connect_prompt: "Connect the device by USB and tap Connect.", choose_kobo: "Choose Kobo", kobo_folder_path: "Kobo folder path", kobo_folder_placeholder: "Folder that contains a .kobo folder", use_folder: "Use this folder", check_kobo: "Check Kobo", open_folder: "Open Kobo folder", choose_folder: "Choose Kobo folder", optional_prerequisite: "Optional prerequisite", install_tools_first: "Install tools first", tools_first_text: "If you want NickelMenu or KOReader, install them with <a href=\"https://kp.nicoverbruggen.be\" target=\"_blank\" rel=\"noreferrer\">KoboPatch Web UI</a>, safely eject, and let the Kobo restart. Then reconnect it and return here. Already installed? Continue below.", connect: "Connect", connect_usb: "Connect your Kobo by USB", connect_text: "On the Kobo screen, tap <strong>Connect</strong>. Your books, reading progress, settings, and plugins stay on the device.", install: "Install", install_support: "Install Vietnamese support", install_support_text: "This installs the font fix and Kobo dictionary. If KOReader is already present, it also installs the KOReader dictionary. Existing target files are backed up first.", dictionary_hint: "Dictionary files are downloaded directly from redphx’s official release and verified before installation.", eject: "Eject", eject_restart: "Safely eject and restart", eject_text: "After installation completes, eject the Kobo. Unplug the cable and let the Kobo restart. The Vietnamese fonts activate during that restart.", eject_button: "Safely eject Kobo", advanced: "Advanced options", install_one: "Install only one item", install_one_text: "Use this only when repairing or updating part of the setup.", font_fix: "Vietnamese font fix", font_fix_detail: "Font-only KoboRoot.tgz for firmware 4.x", kobo_dictionary: "Kobo dictionary", kobo_dictionary_detail: "English–Vietnamese for the built-in reader", koreader_dictionary: "KOReader dictionary", koreader_dictionary_detail: "Requires an existing KOReader installation", install_selected: "Install selected items", rebuild_package: "Rebuild the font package", rebuild_text: "Creates a font-only KoboRoot.tgz from the 20 fonts sourced from Kobo Tiếng Việt by redphx. No compiler, Docker, NickelMenu, or KOReader is added.", rebuild_button: "Rebuild KoboRoot.tgz", repair_package: "Repair a KoboRoot.tgz only", repair_text: "Use this for a custom KoboRoot.tgz that is not NickelMenu. It keeps every non-font file unchanged and adds the Vietnamese fonts. It does not install or update NickelMenu.", choose_koboroot: "Choose KoboRoot.tgz", package_label: "Package label", package_placeholder: "for example, custom font patch", repair_button: "Repair KoboRoot.tgz only", progress: "Progress", installer_status: "Installer status", ready: "Ready", initial_status: "Connect your Kobo, then choose Install Vietnamese support.", vietnamese_guide: "Vietnamese guide", footer: "Runs locally; nothing from your Kobo is uploaded. Fonts sourced from <a href=\"https://github.com/redphx/kobo-tieng-viet\">Kobo Tiếng Việt by redphx</a> (font payload only). Dictionaries by <a href=\"https://github.com/redphx/tudien\">redphx/tudien</a>. Prerequisite workflow by <a href=\"https://github.com/nicoverbruggen/kobopatch-webui\">KoboPatch Web UI by Nico Verbruggen</a>.", phase_queued: "Queued", phase_starting: "Starting", phase_preparing: "Preparing", phase_downloading: "Downloading", phase_cached: "Using cached files", phase_backing_up: "Backing up", phase_copying: "Copying to Kobo", phase_validating: "Validating", phase_verifying: "Verifying", phase_complete: "Complete", phase_error: "Needs attention", working: "Working", complete: "Complete", needs_attention: "Needs attention", no_kobo: "Connect your Kobo, then tap Connect on its screen.", multiple_kobo: "More than one Kobo is connected. Select the device to change.", kobo_ready: "Ready for Vietnamese support.", firmware_review: "Dictionaries can still be installed, but the font fix needs Kobo firmware 4.x.", koreader_detected: "KOReader detected; its dictionary will be included.", koreader_missing: "KOReader was not detected, so only the Kobo dictionary will be included.", package_ready: "Ready: font-only package with {count} fonts.", package_missing: "The Vietnamese font package needs rebuilding.", installed_prefix: "Installed: {items}. Existing target files were backed up when present. Now choose Safely eject Kobo.", build_complete: "The Vietnamese font package is ready. You can now install it on your Kobo.", repair_complete: "Repaired {file} with the 20 Vietnamese fonts from redphx/kobo-tieng-viet. No NickelMenu files were added or changed.", eject_complete: "Your Kobo was safely ejected. Unplug it, then wait for its restart to finish.", opened_folder: "Opened your Kobo in the file manager.", folder_selected: "Kobo folder selected.", choose_wait: "Waiting for a folder to be chosen…", no_folder: "No folder was chosen."
  },
  vi: {
    eyebrow: "Tiện ích tiếng Việt", title: "Bộ cài tiếng Việt cho Kobo", lede: "Thêm font và từ điển Anh–Việt mà không thay thế công cụ hoặc dữ liệu cá nhân trên Kobo.", language: "Ngôn ngữ", checking: "Đang kiểm tra Kobo…", connect_prompt: "Kết nối Kobo bằng USB rồi chọn Connect.", choose_kobo: "Chọn Kobo", kobo_folder_path: "Đường dẫn thư mục Kobo", kobo_folder_placeholder: "Thư mục chứa thư mục .kobo", use_folder: "Dùng thư mục này", check_kobo: "Kiểm tra Kobo", open_folder: "Mở thư mục Kobo", choose_folder: "Chọn thư mục Kobo", optional_prerequisite: "Điều kiện tùy chọn", install_tools_first: "Cài công cụ trước", tools_first_text: "Nếu muốn dùng NickelMenu hoặc KOReader, hãy cài chúng bằng <a href=\"https://kp.nicoverbruggen.be\" target=\"_blank\" rel=\"noreferrer\">KoboPatch Web UI</a>, tháo Kobo an toàn và chờ máy khởi động lại. Sau đó kết nối lại rồi quay lại đây. Đã cài rồi? Tiếp tục bên dưới.", connect: "Kết nối", connect_usb: "Kết nối Kobo bằng USB", connect_text: "Trên màn hình Kobo, chọn <strong>Connect</strong>. Sách, tiến độ đọc, thiết lập và plugin vẫn được giữ nguyên.", install: "Cài đặt", install_support: "Cài hỗ trợ tiếng Việt", install_support_text: "Cài bản sửa font và từ điển Kobo. Nếu đã có KOReader, công cụ cũng cài từ điển cho KOReader. Các tệp đích hiện có sẽ được sao lưu trước.", dictionary_hint: "Từ điển được tải trực tiếp từ bản phát hành chính thức của redphx và xác minh trước khi cài.", eject: "Tháo thiết bị", eject_restart: "Tháo an toàn và khởi động lại", eject_text: "Sau khi cài xong, tháo Kobo an toàn. Rút cáp và chờ Kobo khởi động lại để áp dụng font tiếng Việt.", eject_button: "Tháo Kobo an toàn", advanced: "Tùy chọn nâng cao", install_one: "Chỉ cài một mục", install_one_text: "Chỉ dùng khi sửa chữa hoặc cập nhật một phần cài đặt.", font_fix: "Bản sửa font tiếng Việt", font_fix_detail: "KoboRoot.tgz chỉ chứa font cho firmware 4.x", kobo_dictionary: "Từ điển Kobo", kobo_dictionary_detail: "Anh–Việt cho trình đọc mặc định", koreader_dictionary: "Từ điển KOReader", koreader_dictionary_detail: "Yêu cầu KOReader đã được cài", install_selected: "Cài các mục đã chọn", rebuild_package: "Dựng lại gói font", rebuild_text: "Tạo KoboRoot.tgz chỉ chứa 20 font lấy từ Kobo Tiếng Việt của redphx. Không thêm compiler, Docker, NickelMenu hoặc KOReader.", rebuild_button: "Dựng lại KoboRoot.tgz", repair_package: "Chỉ sửa KoboRoot.tgz", repair_text: "Dùng cho KoboRoot.tgz tùy chỉnh không phải NickelMenu. Công cụ giữ nguyên mọi tệp không phải font và thêm font tiếng Việt. Không cài hoặc cập nhật NickelMenu.", choose_koboroot: "Chọn KoboRoot.tgz", package_label: "Nhãn gói", package_placeholder: "ví dụ: bản sửa font tùy chỉnh", repair_button: "Chỉ sửa KoboRoot.tgz", progress: "Tiến trình", installer_status: "Trạng thái bộ cài", ready: "Sẵn sàng", initial_status: "Kết nối Kobo rồi chọn Cài hỗ trợ tiếng Việt.", vietnamese_guide: "Hướng dẫn tiếng Việt", footer: "Chạy cục bộ; dữ liệu từ Kobo không được tải lên. Font lấy từ <a href=\"https://github.com/redphx/kobo-tieng-viet\">Kobo Tiếng Việt của redphx</a> (chỉ lấy phần font). Từ điển từ <a href=\"https://github.com/redphx/tudien\">redphx/tudien</a>. Quy trình cài công cụ dựa trên <a href=\"https://github.com/nicoverbruggen/kobopatch-webui\">KoboPatch Web UI của Nico Verbruggen</a>.", phase_queued: "Đang chờ", phase_starting: "Đang khởi động", phase_preparing: "Đang chuẩn bị", phase_downloading: "Đang tải xuống", phase_cached: "Dùng tệp đã lưu", phase_backing_up: "Đang sao lưu", phase_copying: "Đang chép vào Kobo", phase_validating: "Đang kiểm tra", phase_verifying: "Đang xác minh", phase_complete: "Hoàn tất", phase_error: "Cần chú ý", working: "Đang thực hiện", complete: "Hoàn tất", needs_attention: "Cần chú ý", no_kobo: "Kết nối Kobo rồi chọn Connect trên màn hình thiết bị.", multiple_kobo: "Có nhiều Kobo đang kết nối. Hãy chọn thiết bị cần thay đổi.", kobo_ready: "Sẵn sàng cài hỗ trợ tiếng Việt.", firmware_review: "Vẫn có thể cài từ điển, nhưng bản sửa font yêu cầu firmware Kobo 4.x.", koreader_detected: "Đã phát hiện KOReader; từ điển KOReader sẽ được cài.", koreader_missing: "Không phát hiện KOReader; chỉ cài từ điển Kobo.", package_ready: "Sẵn sàng: gói chỉ chứa font với {count} font.", package_missing: "Gói font tiếng Việt cần được dựng lại.", installed_prefix: "Đã cài: {items}. Các tệp đích hiện có đã được sao lưu. Bây giờ hãy tháo Kobo an toàn.", build_complete: "Gói font tiếng Việt đã sẵn sàng. Bạn có thể cài vào Kobo.", repair_complete: "Đã sửa {file} với 20 font từ redphx/kobo-tieng-viet. Không thêm hoặc thay đổi tệp NickelMenu.", eject_complete: "Đã tháo Kobo an toàn. Rút cáp và chờ thiết bị khởi động lại.", opened_folder: "Đã mở Kobo trong trình quản lý tệp.", folder_selected: "Đã chọn thư mục Kobo.", choose_wait: "Đang chờ bạn chọn thư mục…", no_folder: "Chưa chọn thư mục nào." }
};

Object.assign(translations.en, {
  lede: "Add Vietnamese fonts, the optional Kobo Vietnamese language, and English–Vietnamese dictionaries without replacing your Kobo tools or personal data.",
  install_support_text: "This installs the font fix, adds Extra: vi to Kobo’s language list, and installs the Kobo dictionary. If KOReader is already present, it also installs the KOReader dictionary. Existing target files are backed up first.",
  eject_text: "After installation completes, eject the Kobo. Unplug the cable and let the Kobo restart. The font and language pack activate during that restart.",
  language_pack: "Vietnamese language pack",
  language_pack_detail: "Adds Extra: vi to Kobo’s Language and dictionaries list and installs Vietnamese translation support",
  language_status_installed: "Vietnamese language: installed",
  language_status_missing: "Vietnamese language: not installed",
  installed_prefix: "Installed: {items}. The language pack adds Extra: vi. Existing target files were backed up when present. Now choose Safely eject Kobo.",
  footer: "Runs locally; nothing from your Kobo is uploaded. Fonts and language support are sourced from <a href=\"https://github.com/redphx/kobo-tieng-viet\">Kobo Tiếng Việt by redphx</a>. Dictionaries by <a href=\"https://github.com/redphx/tudien\">redphx/tudien</a>. Prerequisite workflow by <a href=\"https://github.com/nicoverbruggen/kobopatch-webui\">KoboPatch Web UI by Nico Verbruggen</a>."
});
Object.assign(translations.vi, {
  lede: "Thêm font, gói ngôn ngữ Kobo tiếng Việt và từ điển Anh–Việt mà không thay thế công cụ hoặc dữ liệu cá nhân trên Kobo.",
  install_support_text: "Cài bản sửa font, thêm Extra: vi vào danh sách ngôn ngữ Kobo và cài từ điển Kobo. Nếu đã có KOReader, công cụ cũng cài từ điển KOReader. Các tệp đích hiện có sẽ được sao lưu trước.",
  eject_text: "Sau khi cài xong, tháo Kobo an toàn. Rút cáp và chờ Kobo khởi động lại để áp dụng font và gói ngôn ngữ.",
  language_pack: "Gói ngôn ngữ tiếng Việt",
  language_pack_detail: "Thêm Extra: vi vào Language and dictionaries và cài phần dịch tiếng Việt cho Kobo",
  language_status_installed: "Ngôn ngữ tiếng Việt: đã cài",
  language_status_missing: "Ngôn ngữ tiếng Việt: chưa cài",
  installed_prefix: "Đã cài: {items}. Gói ngôn ngữ đã thêm Extra: vi. Các tệp đích hiện có đã được sao lưu. Bây giờ hãy tháo Kobo an toàn.",
  footer: "Chạy cục bộ; dữ liệu từ Kobo không được tải lên. Font và phần ngôn ngữ lấy từ <a href=\"https://github.com/redphx/kobo-tieng-viet\">Kobo Tiếng Việt của redphx</a>. Từ điển từ <a href=\"https://github.com/redphx/tudien\">redphx/tudien</a>. Quy trình cài công cụ dựa trên <a href=\"https://github.com/nicoverbruggen/kobopatch-webui\">KoboPatch Web UI của Nico Verbruggen</a>."
});

translations.en.eject_text = "After installation completes, close any open files, eject the Kobo from Finder or your file manager, then unplug the cable and let the Kobo restart. The font and language pack activate during that restart.";
translations.vi.eject_text = "Sau khi cài xong, hãy đóng các tệp đang mở, tháo Kobo bằng Finder hoặc trình quản lý tệp, rồi rút cáp và chờ Kobo khởi động lại. Font và gói ngôn ngữ sẽ được áp dụng khi khởi động lại.";

state.locale = localStorage.getItem("kobo-installer-language") || "en";
function t(key, values = {}) {
  let value = translations[state.locale]?.[key] || translations.en[key] || key;
  Object.entries(values).forEach(([name, replacement]) => { value = value.replace(`{${name}}`, replacement); });
  return value;
}

function applyLanguage(locale = state.locale) {
  state.locale = translations[locale] ? locale : "en";
  localStorage.setItem("kobo-installer-language", state.locale);
  document.documentElement.lang = state.locale;
  const selector = $("#language-select");
  if (selector) selector.value = state.locale;
  document.querySelectorAll("[data-i18n]").forEach((element) => { element.textContent = t(element.dataset.i18n); });
  document.querySelectorAll("[data-i18n-html]").forEach((element) => { element.innerHTML = t(element.dataset.i18nHtml); });
  document.querySelectorAll("[data-i18n-placeholder]").forEach((element) => { element.placeholder = t(element.dataset.i18nPlaceholder); });
  if (state.status) renderStatus(state.status);
  $("#action-phase").textContent = t("ready");
  if (!state.actionId) {
    $("#action-detail").textContent = t("initial_status");
    $("#log").textContent = t("initial_status");
  }
}

function recommendedComponents() {
  const components = ["fonts", "language", "kobo_dictionary"];
  if (state.status?.koreader) components.push("koreader_dictionary");
  return components;
}

function setLog(message, kind = "ready") {
  $("#log").textContent = message;
  const badge = $("#busy-badge");
  badge.className = `badge ${kind === "ready" ? "" : kind}`;
  badge.textContent = kind === "busy" ? t("working") : kind === "success" ? t("complete") : kind === "error" ? t("needs_attention") : t("ready");
  if (!state.actionId || kind !== "busy") $("#action-detail").textContent = message;
}

function setProgress(action) {
  if (!action) return;
  const phase = t(`phase_${action.phase}`) || action.phase || t("working");
  const detail = action.phase === "complete" ? action.message || phase : t(`phase_${action.phase}`) || action.message || phase;
  const phaseEl = $("#action-phase");
  const percentEl = $("#action-percent");
  const progressEl = $("#action-progress");
  const track = document.querySelector(".progress-track");
  phaseEl.textContent = phase;
  $("#action-detail").textContent = detail;
  progressEl.classList.toggle("indeterminate", action.progress == null && !["complete", "error"].includes(action.phase));
  if (action.progress == null) {
    percentEl.textContent = t("working") + "…";
    track.removeAttribute("aria-valuenow");
  } else {
    const value = Math.max(0, Math.min(100, Number(action.progress)));
    progressEl.style.width = `${value}%`;
    percentEl.textContent = `${value}%`;
    track.setAttribute("aria-valuenow", String(value));
  }
  if (action.phase === "complete") {
    progressEl.classList.remove("indeterminate");
    progressEl.style.width = "100%";
  }
  if (action.phase === "error") {
    progressEl.classList.remove("indeterminate");
    progressEl.style.width = "100%";
    progressEl.style.background = "var(--red)";
  } else {
    progressEl.style.background = "var(--green)";
  }
}

function beginProgress(label) {
  setProgress({ phase: "starting", progress: 2, message: `${label}…` });
}

async function pollAction(actionId) {
  while (state.actionId === actionId) {
    try {
      const response = await fetch(`/api/action-status?id=${encodeURIComponent(actionId)}`, { cache: "no-store" });
      if (response.ok) {
        const payload = await response.json();
        setProgress(payload.action);
        if (["complete", "error"].includes(payload.action.phase)) return;
      }
    } catch (_) {
      // The main request remains the source of truth if a progress poll is interrupted.
    }
    await new Promise((resolve) => { state.actionTimer = setTimeout(resolve, 400); });
  }
}

function formatResult(action, result) {
  if (action === "build") return t("build_complete");
  if (action === "repair-koboroot-upload") return t("repair_complete", { file: result.sourceFile });
  const names = { fonts: t("font_fix"), language: t("language_pack"), kobo_dictionary: t("kobo_dictionary"), koreader_dictionary: t("koreader_dictionary") };
  const installed = Object.keys(result?.results || {}).map((item) => names[item] || item).join(", ");
  return t("installed_prefix", { items: installed });
}

function renderStatus(status) {
  state.status = status;
  const devices = status.devices || [];
  const selector = $("#device-select");
  const selectorWrap = $("#device-selector-wrap");

  if (status.mounted && status.path) {
    state.selectedDevice = status.path;
  } else if (devices.length === 1) {
    if (!state.selectedDevice) state.selectedDevice = devices[0].path;
  } else if (devices.length === 0) {
    state.selectedDevice = null;
  } else if (state.selectedDevice && !devices.some((device) => device.path === state.selectedDevice)) {
    state.selectedDevice = status.path || "";
  }

  const key = devices.map((device) => device.path).join("|");
  const selectorFocused = document.activeElement === selector;
  selectorWrap.hidden = devices.length <= 1;
  if (devices.length > 1 && key !== state.deviceKey && !selectorFocused) {
    selector.replaceChildren(new Option(t("choose_kobo"), ""), ...devices.map((device) => new Option(
      `${device.name} · ${device.model} · firmware ${device.firmware || "unknown"}`,
      device.path,
      false,
      device.path === state.selectedDevice,
    )));
  }
  state.deviceKey = key;

  const dot = $("#device-dot");
  dot.className = "status-dot";
  if (!status.mounted) {
    if (status.selectionError) {
      $("#device-title").textContent = t("checking");
      $("#device-detail").textContent = status.selectionError;
    } else {
      $("#device-title").textContent = devices.length > 1 ? t("choose_kobo") : t("connect");
      $("#device-detail").textContent = devices.length > 1 ? t("multiple_kobo") : t("no_kobo");
    }
  } else {
    dot.classList.add(status.firmwareSupported ? "connected" : "unsupported");
    $("#device-title").textContent = status.firmwareSupported ? "Kobo ready" : "Firmware needs review";
    const parts = [`Firmware ${status.firmware || "unknown"}`];
    if (status.koreader) parts.push(`KOReader ${status.koreader}`);
    $("#device-detail").textContent = status.firmwareSupported ? `${parts.join(" · ")}. ${t("kobo_ready")}` : `${parts.join(" · ")}. ${t("firmware_review")}`;
  }
  const pathEl = $("#device-path");
  const openFolder = $("#open-folder");
  const componentsEl = $("#device-components");
  if (status.mounted && status.path) {
    pathEl.textContent = `${state.locale === "vi" ? "Thư mục" : "Folder"}: ${status.path}`;
    pathEl.hidden = false;
    openFolder.hidden = false;
  } else {
    pathEl.textContent = "";
    pathEl.hidden = true;
    openFolder.hidden = true;
  }
  if (componentsEl) {
    const installed = [];
    installed.push({ name: status.vietnameseLanguage ? t("language_status_installed") : t("language_status_missing"), missing: !status.vietnameseLanguage });
    if (status.koboDictionary) installed.push(t("kobo_dictionary"));
    if (status.koreaderDictionary) installed.push(t("koreader_dictionary"));
    componentsEl.replaceChildren(...installed.map((entry) => {
      const item = document.createElement("span");
      item.className = `status-item${entry.missing ? " missing" : ""}`;
      item.textContent = typeof entry === "string" ? entry : entry.name;
      return item;
    }));
    componentsEl.hidden = !status.mounted;
  }
  const pkg = status.nickelmenuPackage;
  const koReaderNote = status.koreader ? ` ${t("koreader_detected")}` : ` ${t("koreader_missing")}`;
  $("#build-facts").textContent = pkg ? `${t("package_ready", { count: pkg.fonts })} ${koReaderNote}` : `${t("package_missing")}${status.nickelmenuPackageError ? `: ${status.nickelmenuPackageError}` : ""}`;
  const koReaderChoice = document.querySelector('input[value="koreader_dictionary"]');
  if (koReaderChoice && document.activeElement !== koReaderChoice) {
    koReaderChoice.disabled = !status.koreader;
  }
  updateButtons();
}

function updateButtons() {
  const connected = Boolean(state.status?.mounted);
  const supported = Boolean(state.status?.firmwareSupported);
  const selected = [...document.querySelectorAll('input[name="component"]:checked')].map((input) => input.value);
  $("#install-all").disabled = state.busy || !connected || !supported;
  $("#install-custom").disabled = state.busy || !connected || selected.length === 0 || (selected.includes("fonts") && !supported);
  $("#open-folder").disabled = state.busy || !connected;
  $("#choose-folder").disabled = state.busy;
  $("#use-folder").disabled = state.busy;
  $("#build").disabled = state.busy;
  const upload = $("#koboroot-upload");
  const repair = $("#repair-koboroot-upload");
  if (repair) repair.disabled = state.busy || !upload?.files?.length;
  $("#refresh").disabled = state.busy;
  document.querySelectorAll('input[name="component"]').forEach((input) => {
    input.disabled = state.busy || (input.value === "koreader_dictionary" && !state.status?.koreader);
  });
  if (upload) upload.disabled = state.busy;
  const version = $("#koboroot-version");
  if (version) version.disabled = state.busy;
}

async function request(path, options = {}) {
  const response = await fetch(path, options);
  const payload = await response.json();
  if (payload.status) renderStatus(payload.status);
  if (!response.ok || !payload.ok) throw new Error(payload.error || `Request failed: ${response.status}`);
  return payload.result;
}

async function refresh() {
  if (state.polling) return;
  state.polling = true;
  try {
    const query = state.selectedDevice ? `?device=${encodeURIComponent(state.selectedDevice)}` : "";
    const response = await fetch(`/api/status${query}`, { cache: "no-store" });
    renderStatus((await response.json()).status);
  } catch (error) { setLog(`Could not reach the local installer: ${error.message}`, "error");
  } finally { state.polling = false; }
}

async function runAction(label, action, path, body = {}) {
  const actionId = (window.crypto?.randomUUID && window.crypto.randomUUID()) || `${Date.now()}-${Math.random()}`;
  state.actionId = actionId;
  state.busy = true;
  updateButtons();
  beginProgress(label);
  setLog(`${label}…`, "busy");
  pollAction(actionId);
  try {
    const result = await request(path, { method: "POST", headers: { "Content-Type": "application/json", "X-Kobo-Installer": "1", "X-Kobo-Action": actionId }, body: JSON.stringify(body) });
    setProgress({ phase: "complete", progress: 100, message: formatResult(action, result) });
    setLog(formatResult(action, result), "success");
  } catch (error) {
    setProgress({ phase: "error", progress: null, message: error.message });
    setLog(error.message, "error");
  } finally {
    state.actionId = null;
    if (state.actionTimer) clearTimeout(state.actionTimer);
    state.actionTimer = null;
    state.busy = false;
    await refresh();
    updateButtons();
  }
}

$("#refresh").addEventListener("click", refresh);
$("#device-select").addEventListener("change", (event) => { state.selectedDevice = event.target.value || null; refresh(); });
$("#language-select").addEventListener("change", (event) => applyLanguage(event.target.value));
$("#build").addEventListener("click", () => runAction(t("rebuild_button"), "build", "/api/build"));
$("#koboroot-upload")?.addEventListener("change", updateButtons);
$("#repair-koboroot-upload")?.addEventListener("click", async () => {
  const file = $("#koboroot-upload")?.files?.[0];
  if (!file) return;
  const bytes = new Uint8Array(await file.arrayBuffer());
  let binary = "";
  for (let index = 0; index < bytes.length; index += 0x8000) binary += String.fromCharCode(...bytes.subarray(index, index + 0x8000));
  runAction(t("repair_button"), "repair-koboroot-upload", "/api/repair-koboroot-upload", {
    filename: file.name,
    version: $("#koboroot-version").value,
    archiveBase64: btoa(binary),
  });
});
$("#install-all").addEventListener("click", () => runAction(t("install_support"), "install", "/api/install", { components: recommendedComponents(), devicePath: state.selectedDevice }));
$("#install-custom").addEventListener("click", () => runAction(t("install_selected"), "install", "/api/install", { components: [...document.querySelectorAll('input[name="component"]:checked')].map((input) => input.value), devicePath: state.selectedDevice }));
$("#open-folder").addEventListener("click", async () => {
  try {
    const result = await request("/api/open-folder", { method: "POST", headers: { "Content-Type": "application/json", "X-Kobo-Installer": "1" }, body: JSON.stringify({ devicePath: state.selectedDevice }) });
    setLog(t("opened_folder"), "success");
  } catch (error) { setLog(error.message, "error"); }
});
$("#choose-folder").addEventListener("click", async () => {
  state.busy = true; updateButtons(); setLog(t("choose_wait"), "busy");
  try {
    const response = await fetch("/api/choose-folder", { method: "POST", headers: { "Content-Type": "application/json", "X-Kobo-Installer": "1" }, body: "{}" });
    const payload = await response.json();
    if (!response.ok || !payload.ok) throw new Error(payload.error || "Could not choose a folder.");
    const result = payload.result;
    if (!result.supported) {
      $("#folder-path-wrap").hidden = false;
      setLog(result.message || t("choose_folder"), "ready");
      return;
    }
    if (result.cancelled) { setLog(t("no_folder"), "ready"); return; }
    state.selectedDevice = result.path;
    setLog(t("folder_selected"), "success");
    await refresh();
  } catch (error) { setLog(error.message, "error");
  } finally { state.busy = false; updateButtons(); }
});
$("#use-folder").addEventListener("click", async () => {
  const value = $("#folder-path").value.trim();
  if (!value) return;
  state.selectedDevice = value;
  await refresh();
});
document.querySelectorAll('input[name="component"]').forEach((input) => input.addEventListener("change", updateButtons));
applyLanguage();
document.addEventListener("visibilitychange", () => { if (!document.hidden && !state.busy) refresh(); });
refresh();
setInterval(() => {
  if (state.busy || state.polling || document.hidden) return;
  if (document.activeElement === $("#device-select")) return;
  refresh();
}, 4000);
