interface Consumer<T> {
  resolve: (value: T) => void;
  reject: (error: unknown) => void;
  cleanup: () => void;
}
interface Job<T> {
  key: string;
  controller: AbortController;
  consumers: Set<Consumer<T>>;
}
const aborted = () => new DOMException("预览请求已取消", "AbortError");

/** 完成的预览按 LRU 限容；共享在途任务，并限制重型解析并发。 */
export class PreviewCache<T> {
  private ready = new Map<string, T>();
  private jobs = new Map<string, Job<T>>();
  private queue: Job<T>[] = [];
  private active = 0;
  private load: (key: string, signal: AbortSignal) => Promise<T>;
  private dispose: (value: T) => void;
  private capacity: number;
  private concurrency: number;
  constructor(
    load: (key: string, signal: AbortSignal) => Promise<T>,
    dispose: (value: T) => void,
    capacity = 24,
    concurrency = 2,
  ) {
    this.load = load;
    this.dispose = dispose;
    this.capacity = capacity;
    this.concurrency = concurrency;
  }

  get(key: string, signal: AbortSignal): Promise<T> {
    if (signal.aborted) return Promise.reject(aborted());
    if (this.ready.has(key)) {
      const value = this.ready.get(key)!;
      this.ready.delete(key);
      this.ready.set(key, value);
      return Promise.resolve(value);
    }
    let job = this.jobs.get(key);
    if (!job) {
      job = { key, controller: new AbortController(), consumers: new Set() };
      this.jobs.set(key, job);
      this.queue.push(job);
    }
    const current = job;
    const promise = new Promise<T>((resolve, reject) => {
      const cancel = () => {
        current.consumers.delete(consumer);
        consumer.cleanup();
        reject(aborted());
        if (!current.consumers.size) {
          if (this.jobs.get(key) === current) this.jobs.delete(key);
          this.queue = this.queue.filter((item) => item !== current);
          current.controller.abort();
        }
      };
      const consumer: Consumer<T> = {
        resolve,
        reject,
        cleanup: () => signal.removeEventListener("abort", cancel),
      };
      current.consumers.add(consumer);
      signal.addEventListener("abort", cancel, { once: true });
    });
    this.drain();
    return promise;
  }

  private drain() {
    while (this.active < this.concurrency && this.queue.length) {
      const job = this.queue.shift()!;
      if (!job.consumers.size || job.controller.signal.aborted) continue;
      this.active++;
      void Promise.resolve()
        .then(() => this.load(job.key, job.controller.signal))
        .then((value) => {
          if (job.controller.signal.aborted || this.jobs.get(job.key) !== job) {
            this.dispose(value);
            return;
          }
          this.ready.set(job.key, value);
          while (this.ready.size > this.capacity) {
            const oldest = this.ready.keys().next().value!;
            this.dispose(this.ready.get(oldest)!);
            this.ready.delete(oldest);
          }
          if (this.jobs.get(job.key) === job) this.jobs.delete(job.key);
          for (const consumer of job.consumers) {
            consumer.cleanup();
            consumer.resolve(value);
          }
        })
        .catch((error) => {
          if (this.jobs.get(job.key) === job) this.jobs.delete(job.key);
          for (const consumer of job.consumers) {
            consumer.cleanup();
            consumer.reject(error);
          }
        })
        .finally(() => {
          job.consumers.clear();
          if (this.jobs.get(job.key) === job) this.jobs.delete(job.key);
          this.active--;
          this.drain();
        });
    }
  }
}
