"""入库任务登记处：上传即起解析，消息流在起 agent 前等它跑完。

OCR 是**上传后的确定性前置异步任务**，不是 agent 工具——确定性 ETL 不该由 LLM
决定何时跑、跑几次，失败/重试/断点续跑的语义要干净。

时序：`POST /projects/{pid}/files` 收下 PDF 就地起后台线程解析并立刻返回，用户
在前端看到「原文解析 N/M 页」；`POST /sessions/{sid}/messages` 先把该 project
的在跑任务等完（沿既有 SSE 通道上报进度），md 与 sidecar 就绪后才起 agent。
"""

from __future__ import annotations

import logging
import threading
from dataclasses import dataclass
from typing import Callable

from hagent.ingest.pipeline import IngestPipeline, IngestResult, UploadRejected

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class IngestProgress:
    done: int
    total: int


class IngestJob:
    """一份 PDF 的解析任务；线程安全地对外暴露进度与终态。"""

    def __init__(self, project_id: str, pdf_path: str, total_pages: int):
        self.project_id = project_id
        self.pdf_path = pdf_path
        self._lock = threading.Lock()
        self._done_event = threading.Event()
        self._progress = IngestProgress(done=0, total=total_pages)
        self._result: IngestResult | None = None
        self._error: BaseException | None = None
        self._claimed = False

    @property
    def progress(self) -> IngestProgress:
        with self._lock:
            return self._progress

    @property
    def finished(self) -> bool:
        return self._done_event.is_set()

    @property
    def result(self) -> IngestResult | None:
        return self._result

    @property
    def error(self) -> BaseException | None:
        return self._error

    def wait(self, timeout: float | None = None) -> bool:
        return self._done_event.wait(timeout)

    def report_progress(self, done: int, total: int) -> None:
        with self._lock:
            self._progress = IngestProgress(done=done, total=total)

    def finish(self, result: IngestResult | None, error: BaseException | None) -> None:
        self._result = result
        self._error = error
        self._done_event.set()

    def claim(self) -> bool:
        """认领上报权；只有第一个认领者为 True。"""
        with self._lock:
            if self._claimed:
                return False
            self._claimed = True
            return True


class IngestRegistry:
    """project → 最近一次入库任务。进程内内存态，重启即散——重启后本就没有在跑的解析。"""

    def __init__(self, pipeline_factory: Callable[[], IngestPipeline] | None = None):
        self._jobs: dict[str, IngestJob] = {}
        self._lock = threading.Lock()
        self._pipeline_factory = pipeline_factory or IngestPipeline

    def submit(self, project_id: str, *, data: bytes, pdf_path: str, total_pages: int) -> IngestJob:
        job = IngestJob(project_id, pdf_path, total_pages)
        with self._lock:
            current = self._jobs.get(project_id)
            if current is not None and not current.finished:
                raise UploadRejected("当前项目正在解析文件，请等待完成后再上传")
            self._jobs[project_id] = job

        def run() -> None:
            try:
                result = self._pipeline_factory().ingest_pdf(
                    project_id,
                    data=data,
                    pdf_path=pdf_path,
                    on_progress=job.report_progress,
                )
            except BaseException as exc:  # noqa: BLE001 —— 后台线程不能把异常吞进虚空
                logger.exception("project %s 原文解析失败: %s", project_id, exc)
                job.finish(None, exc)
            else:
                job.finish(result, None)

        threading.Thread(
            target=run, name=f"ingest-{project_id}", daemon=True
        ).start()
        return job

    def claim(self, project_id: str) -> IngestJob | None:
        """认领该 project 尚未被上报过的任务，认领一次即用尽。

        用「未上报」而非「未完成」作判据：解析在首条消息之前就跑完时，结果（尤其
        是失败）仍要报给用户一次；之后的消息不再重复上报，也不再等待。
        """
        with self._lock:
            job = self._jobs.get(project_id)
        return job if job is not None and job.claim() else None


_REGISTRY: IngestRegistry | None = None


def set_ingest_registry(registry: IngestRegistry | None) -> None:
    global _REGISTRY
    _REGISTRY = registry


def get_ingest_registry() -> IngestRegistry:
    global _REGISTRY
    if _REGISTRY is None:
        _REGISTRY = IngestRegistry()
    return _REGISTRY
