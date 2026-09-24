import { computed, ref } from "vue";
import * as tus from "tus-js-client";

export type UploadStatus = "queued" | "uploading" | "success" | "error" | "cancelled";

export interface UploadItem {
  id: string;
  file: File;
  name: string;
  status: UploadStatus;
  progress: number;
  error?: string;
  upload?: tus.Upload;
}

const ALLOWED = new Set([
  "image/jpeg",
  "image/png",
  "image/webp",
  "video/mp4",
  "video/webm",
  "video/quicktime",
]);

export function uploadRejectReason(file: File): string | null {
  if (ALLOWED.has(file.type)) return null;
  return `Тип ${file.type || "невідомий"} не підтримується`;
}

export function isAllowedUpload(file: File): boolean {
  return uploadRejectReason(file) === null;
}

interface Options {
  getToken: () => string | null;
  onUploaded?: () => void;
}

export function useUploadQueue(opts: Options) {
  const items = ref<UploadItem[]>([]);
  const hasActive = computed(() =>
    items.value.some((i) => i.status === "uploading" || i.status === "queued"),
  );

  function addFile(file: File, name: string) {
    const reason = uploadRejectReason(file);
    if (reason) {
      items.value.push({
        id: crypto.randomUUID(),
        file,
        name,
        status: "error",
        progress: 0,
        error: reason,
      });
      return;
    }
    items.value.push({
      id: crypto.randomUUID(),
      file,
      name,
      status: "queued",
      progress: 0,
    });
    startAll();
  }

  function startAll() {
    const active = items.value.filter((i) => i.status === "uploading").length;
    if (active >= 1) return;
    const next = items.value.find((i) => i.status === "queued");
    if (next) startOne(next);
  }

  function startOne(it: UploadItem) {
    const token = opts.getToken();
    if (!token) {
      it.status = "error";
      it.error = "Немає токена авторизації";
      return;
    }
    const upload = new tus.Upload(it.file, {
      endpoint: "/files/",
      retryDelays: [0, 1000, 3000, 5000, 10000],
      chunkSize: 8 * 1024 * 1024,
      onShouldRetry(err) {
        const code = (err as tus.DetailedError).originalResponse?.getStatus() ?? 0;
        if (code >= 400 && code < 500) return false;
        return true;
      },
      metadata: {
        auth_token: token,
        filename: it.file.name,
        filetype: it.file.type,
        name: it.name,
      },
      onError(err) {
        const detailed = err as tus.DetailedError;
        let msg = err.message;
        try {
          const body = detailed.originalResponse?.getBody();
          if (body) {
            const parsed = JSON.parse(body);
            if (parsed.error) msg = parsed.error;
          }
        } catch {
          /* ignore */
        }
        it.status = "error";
        it.error = msg;
        startAll();
      },
      onProgress(sent, total) {
        it.progress = total > 0 ? Math.round((sent / total) * 100) : 0;
      },
      onSuccess() {
        it.status = "success";
        it.progress = 100;
        opts.onUploaded?.();
        startAll();
      },
    });
    it.upload = upload;
    it.status = "uploading";
    upload.start();
  }

  function reset() {
    if (!hasActive.value) items.value = [];
  }

  return { items, hasActive, addFile, reset };
}
