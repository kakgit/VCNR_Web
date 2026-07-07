import {
  FragmentedMp4Assembler,
  joinBytes,
  mimeFromInitializationSegment,
} from "./mp4_segments.js";

const DEMO_STREAM_URL = "https://test-streams.mux.dev/x36xhzz/x36xhzz.m3u8";
const MAGIC = new TextEncoder().encode("VCNRCMP3");
const VERSION = 3;
const END_MARKER = 0xffffffff;
const MAX_HEADER = 1024 * 1024;
const MAX_CIPHER = 1024 * 1024 + 16;
const SAMPLE_CONFIG_PATH = "sample-config.json";

const video = document.getElementById("video");
const form = document.getElementById("streamForm");
const streamUrlInput = document.getElementById("streamUrl");
const vcnrUrlInput = document.getElementById("vcnrUrl");
const vcnrFileInput = document.getElementById("vcnrFile");
const passcodeInput = document.getElementById("passcode");
const statusText = document.getElementById("status");
const metadataPanel = document.getElementById("metadata");
const liveBadge = document.getElementById("liveBadge");
const loadDemoButton = document.getElementById("loadDemo");
const stopButton = document.getElementById("stopStream");
const playVcnrButton = document.getElementById("playVcnr");
const sampleBox = document.getElementById("sampleBox");
const sampleLabel = document.getElementById("sampleLabel");
const sampleLoadButton = document.getElementById("sampleLoad");
const modeTabs = Array.from(document.querySelectorAll(".mode-tab"));
const modePanels = Array.from(document.querySelectorAll(".mode-panel"));

let hlsInstance = null;
let activeObjectUrl = null;
let activeReader = null;
let activeMediaSource = null;
let activeAbortController = null;
let stopped = false;
let sampleUrl = null;

class ExactReader {
  constructor(stream) {
    this.reader = stream.getReader();
    this.pending = new Uint8Array(0);
  }

  async readExact(length) {
    const output = new Uint8Array(length);
    let written = 0;

    while (written < length) {
      if (this.pending.length) {
        const count = Math.min(this.pending.length, length - written);
        output.set(this.pending.subarray(0, count), written);
        written += count;
        this.pending = this.pending.subarray(count);
        continue;
      }

      const { value, done } = await this.reader.read();
      if (done) {
        throw new Error("The VCNR stream ended unexpectedly.");
      }
      this.pending = value;
    }

    return output;
  }

  async uint32() {
    const bytes = await this.readExact(4);
    return new DataView(bytes.buffer, bytes.byteOffset, 4).getUint32(0, false);
  }

  cancel() {
    return this.reader.cancel().catch(() => {});
  }
}

function setStatus(message, isError = false) {
  statusText.textContent = message;
  statusText.style.color = isError ? "#ffd0d0" : "";
}

function setMetadata(value = "") {
  metadataPanel.textContent = value;
}

function setLiveState(isLive) {
  liveBadge.textContent = isLive ? "LIVE" : "OFFLINE";
  liveBadge.style.background = isLive ? "rgba(255, 107, 107, 0.22)" : "rgba(255, 255, 255, 0.08)";
  liveBadge.style.color = isLive ? "#ffe3e3" : "#d5e2ea";
}

function resetVideoSource() {
  video.pause();
  video.removeAttribute("src");
  video.load();

  if (activeObjectUrl) {
    URL.revokeObjectURL(activeObjectUrl);
    activeObjectUrl = null;
  }

  activeMediaSource = null;
}

function destroyCurrentStream() {
  if (hlsInstance) {
    hlsInstance.destroy();
    hlsInstance = null;
  }

  if (activeAbortController) {
    activeAbortController.abort();
    activeAbortController = null;
  }

  if (activeReader) {
    activeReader.cancel();
    activeReader = null;
  }

  stopped = true;
  resetVideoSource();
  setLiveState(false);
}

async function startPlayback() {
  try {
    await video.play();
    setLiveState(true);
  } catch {
    setStatus("Media is ready. Press play if your browser blocked autoplay.");
    setLiveState(true);
  }
}

function setMode(mode) {
  modeTabs.forEach((tab) => {
    tab.classList.toggle("is-active", tab.dataset.mode === mode);
  });

  modePanels.forEach((panel) => {
    panel.classList.toggle("is-active", panel.dataset.panel === mode);
  });

  setMetadata("");
  setStatus(
    mode === "stream"
      ? "Enter a live stream URL ending in .m3u8 to begin."
      : "Choose a VCNR file or URL, enter its passcode, and unlock playback."
  );
}

function basename(value) {
  try {
    const url = new URL(value, window.location.href);
    const parts = url.pathname.split("/");
    return decodeURIComponent(parts[parts.length - 1] || "sample.vcnr");
  } catch {
    return "sample.vcnr";
  }
}

function showSample(url) {
  sampleUrl = new URL(url, window.location.href).href;
  sampleLabel.textContent = `Load ${basename(sampleUrl)} from this hosted player.`;
  sampleBox.classList.remove("hidden");
}

function loadSampleFile() {
  if (!sampleUrl) {
    return;
  }

  vcnrFileInput.value = "";
  vcnrUrlInput.value = sampleUrl;
  setStatus(`Sample file loaded: ${basename(sampleUrl)}. Enter the passcode and press Unlock And Play.`);
}

function prefillSharedUrl() {
  const pageUrl = new URL(window.location.href);
  let sharedUrl = pageUrl.searchParams.get("url");

  if (!sharedUrl && pageUrl.hash.startsWith("#url=")) {
    sharedUrl = decodeURIComponent(pageUrl.hash.slice(5));
  }

  if (sharedUrl && !vcnrUrlInput.value.trim()) {
    vcnrUrlInput.value = sharedUrl;
    setStatus("Shared VCNR URL loaded. Enter the passcode and press Unlock And Play.");
  }
}

async function probeSampleFile() {
  const pageUrl = new URL(window.location.href);
  const configuredSample = pageUrl.searchParams.get("sample");

  if (configuredSample) {
    showSample(configuredSample);
    return;
  }

  try {
    const response = await fetch(new URL(SAMPLE_CONFIG_PATH, pageUrl).href, {
      cache: "no-store",
    });

    if (!response.ok) {
      return;
    }

    const config = await response.json();
    if (config && typeof config.sample === "string" && config.sample.trim()) {
      showSample(config.sample.trim());
      return;
    }
  } catch {
    // Ignore missing or invalid config files.
  }

  try {
    const defaultSample = new URL("media/sample.vcnr", pageUrl).href;
    const response = await fetch(defaultSample, {
      method: "HEAD",
      cache: "no-store",
    });

    if (response.ok) {
      showSample(defaultSample);
    }
  } catch {
    // Ignore when no hosted sample exists.
  }
}

function loadStream(streamUrl) {
  destroyCurrentStream();
  stopped = false;

  if (!streamUrl) {
    setStatus("Please enter a valid live stream URL.", true);
    return;
  }

  if (window.Hls && window.Hls.isSupported()) {
    hlsInstance = new window.Hls({
      enableWorker: true,
      lowLatencyMode: true,
    });

    hlsInstance.loadSource(streamUrl);
    hlsInstance.attachMedia(video);

    hlsInstance.on(window.Hls.Events.MANIFEST_PARSED, () => {
      setStatus("Live stream loaded. Connecting player...");
      startPlayback();
    });

    hlsInstance.on(window.Hls.Events.ERROR, (_, data) => {
      if (data.fatal) {
        setStatus("The stream could not be played. Check the URL or stream availability.", true);
        setLiveState(false);
      }
    });

    return;
  }

  if (video.canPlayType("application/vnd.apple.mpegurl")) {
    video.src = streamUrl;
    video.addEventListener(
      "loadedmetadata",
      () => {
        setStatus("Native HLS playback is ready.");
        startPlayback();
      },
      { once: true }
    );
    return;
  }

  setStatus("This browser does not support HLS playback.", true);
}

function u32Pair(first, second) {
  const bytes = new Uint8Array(8);
  const view = new DataView(bytes.buffer);
  view.setUint32(0, first, false);
  view.setUint32(4, second, false);
  return bytes;
}

async function appendBuffer(sourceBuffer, bytes, description) {
  if (stopped) {
    throw new Error("Playback stopped.");
  }

  await new Promise((resolve, reject) => {
    const cleanup = () => {
      sourceBuffer.removeEventListener("updateend", onSuccess);
      sourceBuffer.removeEventListener("error", onFailure);
    };

    const onSuccess = () => {
      cleanup();
      resolve();
    };

    const onFailure = () => {
      cleanup();
      reject(new Error(`Browser rejected the ${description}.`));
    };

    sourceBuffer.addEventListener("updateend", onSuccess, { once: true });
    sourceBuffer.addEventListener("error", onFailure, { once: true });

    try {
      sourceBuffer.appendBuffer(bytes);
    } catch (error) {
      cleanup();
      reject(error);
    }
  });
}

async function openVcnrInput() {
  const file = vcnrFileInput.files?.[0];
  const url = vcnrUrlInput.value.trim();

  if (file) {
    return file.stream();
  }

  if (!url) {
    throw new Error("Choose a VCNR file or enter its URL.");
  }

  activeAbortController = new AbortController();

  let response;
  try {
    response = await fetch(url, {
      signal: activeAbortController.signal,
      cache: "no-store",
      mode: "cors",
    });
  } catch (error) {
    if (error && error.name === "AbortError") {
      throw new Error("Playback stopped.");
    }
    if (window.location.protocol === "https:" && url.toLowerCase().startsWith("http://")) {
      throw new Error("This page uses HTTPS, so the VCNR URL must use HTTPS too.");
    }
    throw new Error("Browser could not download the VCNR URL. Check the address and confirm the file server allows CORS.");
  }

  if (!response.ok || !response.body) {
    throw new Error(`VCNR server returned HTTP ${response.status}.`);
  }

  return response.body;
}

async function createSourceBuffer(mime) {
  if (!("MediaSource" in window)) {
    throw new Error("This browser does not support Media Source playback.");
  }

  if (!MediaSource.isTypeSupported(mime)) {
    throw new Error(`This browser does not support the VCNR codec: ${mime}`);
  }

  const mediaSource = new MediaSource();
  activeMediaSource = mediaSource;
  activeObjectUrl = URL.createObjectURL(mediaSource);
  video.src = activeObjectUrl;

  await new Promise((resolve, reject) => {
    mediaSource.addEventListener("sourceopen", resolve, { once: true });
    mediaSource.addEventListener("error", () => reject(new Error("Media player failed.")), { once: true });
  });

  return mediaSource.addSourceBuffer(mime);
}

async function playMemoryFallback(parts) {
  resetVideoSource();
  const blob = new Blob(parts, { type: "video/mp4" });
  activeObjectUrl = URL.createObjectURL(blob);
  video.src = activeObjectUrl;

  await new Promise((resolve, reject) => {
    const cleanup = () => {
      video.removeEventListener("loadedmetadata", onLoaded);
      video.removeEventListener("error", onFailed);
    };

    const onLoaded = () => {
      cleanup();
      resolve();
    };

    const onFailed = () => {
      cleanup();
      reject(new Error("This browser could not decode the decrypted H.264/AAC video."));
    };

    video.addEventListener("loadedmetadata", onLoaded, { once: true });
    video.addEventListener("error", onFailed, { once: true });
  });

  setStatus("Compatibility mode: decrypted in memory and ready to play.");
  startPlayback();
}

async function playVcnr() {
  destroyCurrentStream();
  stopped = false;

  try {
    if (!passcodeInput.value) {
      throw new Error("Enter the VCNR passcode.");
    }

    setStatus("Opening VCNR stream...");
    activeReader = new ExactReader(await openVcnrInput());

    const magic = await activeReader.readExact(8);
    if (!magic.every((value, index) => value === MAGIC[index])) {
      throw new Error("This is not a browser-compatible VCNR v3 file.");
    }

    const version = await activeReader.uint32();
    const headerLength = await activeReader.uint32();
    if (version !== VERSION || headerLength > MAX_HEADER) {
      throw new Error("Unsupported or damaged VCNR file.");
    }

    const salt = await activeReader.readExact(16);
    const headerBytes = await activeReader.readExact(headerLength);
    const header = JSON.parse(new TextDecoder().decode(headerBytes));
    setMetadata(JSON.stringify(header, null, 2));

    setStatus("Deriving encryption key...");
    const keyMaterial = await crypto.subtle.importKey(
      "raw",
      new TextEncoder().encode(passcodeInput.value),
      "PBKDF2",
      false,
      ["deriveKey"]
    );

    const key = await crypto.subtle.deriveKey(
      {
        name: "PBKDF2",
        hash: "SHA-256",
        salt,
        iterations: header.kdf_iterations,
      },
      keyMaterial,
      { name: "AES-GCM", length: 256 },
      false,
      ["decrypt"]
    );

    const headerHash = new Uint8Array(await crypto.subtle.digest("SHA-256", headerBytes));
    const mp4Assembler = new FragmentedMp4Assembler();
    let sourceBuffer = null;
    let memoryFallback = [];
    let mseDisabled = false;
    let mediaAppended = false;
    let expectedId = 0;

    while (!stopped) {
      const chunkId = await activeReader.uint32();
      if (chunkId === END_MARKER) {
        break;
      }

      const plainLength = await activeReader.uint32();
      const nonce = await activeReader.readExact(12);
      const cipherLength = await activeReader.uint32();

      if (
        chunkId !== expectedId ||
        plainLength > 1024 * 1024 ||
        cipherLength !== plainLength + 16 ||
        cipherLength > MAX_CIPHER
      ) {
        throw new Error("Invalid or missing VCNR media chunk.");
      }

      const cipher = await activeReader.readExact(cipherLength);
      const aad = joinBytes(headerHash, u32Pair(VERSION, chunkId));

      let plain;
      try {
        plain = new Uint8Array(
          await crypto.subtle.decrypt(
            { name: "AES-GCM", iv: nonce, additionalData: aad, tagLength: 128 },
            key,
            cipher
          )
        );
      } catch {
        throw new Error("Wrong passcode or damaged VCNR file.");
      }

      if (memoryFallback) {
        memoryFallback.push(plain);
      }

      if (mseDisabled) {
        expectedId += 1;
        setStatus(`Compatibility mode: decrypting chunk ${expectedId}/${header.chunk_count}...`);
        continue;
      }

      const segments = mp4Assembler.push(plain);

      for (const segment of segments) {
        if (!sourceBuffer) {
          const mime = mimeFromInitializationSegment(segment);
          setStatus(`Opening browser decoder: ${mime}`);
          try {
            sourceBuffer = await createSourceBuffer(mime);
            await appendBuffer(sourceBuffer, segment, "MP4 initialization segment");
            memoryFallback = null;
          } catch {
            mseDisabled = true;
            sourceBuffer = null;
            resetVideoSource();
            setStatus("Media Source initialization was rejected. Switching to compatibility mode...");
            break;
          }
          continue;
        }

        await appendBuffer(sourceBuffer, segment, `MP4 media fragment ${mp4Assembler.fragmentCount}`);
        if (!mediaAppended) {
          mediaAppended = true;
          setStatus("Passcode accepted. Streaming video...");
          startPlayback();
        }
      }

      expectedId += 1;
      setStatus(`Streaming encrypted chunk ${expectedId}/${header.chunk_count}...`);
    }

    if (!stopped && expectedId !== header.chunk_count) {
      throw new Error("VCNR stream ended before all chunks arrived.");
    }

    if (mseDisabled) {
      await playMemoryFallback(memoryFallback);
    } else {
      const finalSegments = mp4Assembler.push(new Uint8Array(0), true);
      for (const segment of finalSegments) {
        if (!sourceBuffer) {
          const mime = mimeFromInitializationSegment(segment);
          sourceBuffer = await createSourceBuffer(mime);
          await appendBuffer(sourceBuffer, segment, "MP4 initialization segment");
        } else {
          await appendBuffer(sourceBuffer, segment, "final MP4 media fragment");
        }
      }

      if (!stopped && !mp4Assembler.fragmentCount) {
        throw new Error("VCNR contains no playable fragmented MP4 media.");
      }

      if (!stopped && activeMediaSource?.readyState === "open") {
        activeMediaSource.endOfStream();
        setStatus("Video fully buffered.");
      }
    }
  } finally {
    activeAbortController = null;
    activeReader = null;
  }
}

form.addEventListener("submit", (event) => {
  event.preventDefault();
  loadStream(streamUrlInput.value.trim());
});

modeTabs.forEach((tab) => {
  tab.addEventListener("click", () => {
    setMode(tab.dataset.mode);
  });
});

loadDemoButton.addEventListener("click", () => {
  streamUrlInput.value = DEMO_STREAM_URL;
  loadStream(DEMO_STREAM_URL);
});

sampleLoadButton.addEventListener("click", loadSampleFile);

playVcnrButton.addEventListener("click", async () => {
  try {
    await playVcnr();
  } catch (error) {
    if (!stopped) {
      setStatus(error.message || "VCNR playback failed.", true);
    }
  }
});

stopButton.addEventListener("click", () => {
  destroyCurrentStream();
  resetVideoSource();
  setStatus("Playback stopped. Enter another source to start again.");
});

video.addEventListener("waiting", () => {
  if (liveBadge.textContent === "LIVE") {
    setStatus("Buffering playback...");
  }
});

video.addEventListener("playing", () => {
  if (liveBadge.textContent === "LIVE") {
    setStatus("Playback is live.");
  }
});

setMode("stream");
prefillSharedUrl();
probeSampleFile();
