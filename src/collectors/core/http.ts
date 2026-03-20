import axios, { AxiosInstance, AxiosRequestConfig, AxiosResponse } from "axios";
import { sleep } from "./sleep";

export function createHttpClient({
  baseURL,
  timeoutMs,
  headers = {},
}: {
  baseURL: string;
  timeoutMs: number;
  headers?: Record<string, string>;
}): AxiosInstance {
  const client = axios.create({
    baseURL,
    timeout: timeoutMs,
    headers,
    // Many public APIs are sensitive to keep-alive issues; keep defaults.
    validateStatus: () => true,
  });
  return client;
}

interface RetryOptions {
  retries?: number;
  minDelayMs?: number;
  maxDelayMs?: number;
  log?: Pick<Console, "warn">;
}

interface HttpError extends Error {
  status?: number;
  data?: unknown;
}

export async function requestWithRetry(
  client: AxiosInstance,
  config: AxiosRequestConfig,
  { retries = 3, minDelayMs = 500, maxDelayMs = 6000, log = console }: RetryOptions = {}
): Promise<AxiosResponse> {
  let attempt = 0;
  while (true) {
    attempt++;
    try {
      const res = await client.request(config);

      // Success-ish
      if (res.status >= 200 && res.status < 300) return res;

      // Retry on throttling / transient errors
      const retryable = [408, 429, 500, 502, 503, 504].includes(res.status);
      if (!retryable || attempt > retries) {
        const msg = `[HTTP] ${config.method || "GET"} ${config.url} -> ${res.status}`;
        const err: HttpError = new Error(msg);
        err.status = res.status;
        err.data = res.data;
        throw err;
      }

      const backoff = Math.min(maxDelayMs, minDelayMs * Math.pow(2, attempt - 1));
      const jitter = Math.floor(Math.random() * 250);
      const wait = backoff + jitter;

      const ra = res.headers?.["retry-after"] as string | undefined;
      const waitMs = ra ? Math.max(wait, Number(ra) * 1000) : wait;

      log.warn(
        `[HTTP] retry ${attempt}/${retries} status=${res.status} wait=${waitMs}ms url=${config.url}`
      );
      await sleep(waitMs);
    } catch (e) {
      // Network errors: retry
      if (attempt > retries) throw e;
      const backoff = Math.min(maxDelayMs, minDelayMs * Math.pow(2, attempt - 1));
      const jitter = Math.floor(Math.random() * 250);
      const waitMs = backoff + jitter;
      log.warn(
        `[HTTP] network retry ${attempt}/${retries} wait=${waitMs}ms err=${(e as Error).message}`
      );
      await sleep(waitMs);
    }
  }
}
