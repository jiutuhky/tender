"""NodeClient — 多机调度接缝(Task C5,spec §10:仅接口预留,无跨机实现)。

单机形态下沙箱由本进程工厂直接创建;多机形态下 pool 的供给线换成
远端节点客户端(RPC 到目标宿主起 VM),pool/manager 的其余逻辑不变。
本模块只固化这条缝的协议与本地实现;调度策略、节点发现、跨机迁移
均在范围外。sessions 表的 ``node`` 列记录会话沙箱所在节点,单机恒 local。
"""

from __future__ import annotations

from typing import Callable, Protocol, runtime_checkable

from hagent.sandbox.protocol import HagentSandboxProtocol

LOCAL_NODE_ID = "local"


@runtime_checkable
class NodeClient(Protocol):
    """一个可供给沙箱的节点。"""

    @property
    def node_id(self) -> str: ...

    def create_sandbox(self) -> HagentSandboxProtocol: ...


class LocalNodeClient:
    """本进程工厂的 NodeClient 适配——现有单机行为的显式命名。"""

    def __init__(
        self,
        factory: Callable[[], HagentSandboxProtocol],
        *,
        node_id: str = LOCAL_NODE_ID,
    ) -> None:
        self._factory = factory
        self._node_id = node_id

    @property
    def node_id(self) -> str:
        return self._node_id

    def create_sandbox(self) -> HagentSandboxProtocol:
        return self._factory()
