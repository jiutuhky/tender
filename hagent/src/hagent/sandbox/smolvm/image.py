"""hagent boot image 烘焙 — DockerRootfsBuilder 封装 + 进程内单飞缓存。

镜像物料与 docker provider 的 ``sandbox/docker/images/hagent-base/Dockerfile``
同源维护(spec D3):python:3.12-slim 基座 + bash/git/ripgrep/coreutils。
差异项仅为 VM 形态所需:openssh-server + iproute2(init 网络配置)、
smolvm-guest-agent(vsock 控制面,DockerRootfsBuilder 不自动注入,见 F7)、
/init(PID 1,复用 SDK 的 base init 脚本,版本已锁 0.0.25)。
"""

from __future__ import annotations

import logging
import os
import threading
from typing import TYPE_CHECKING, Any

from smolvm import DockerRootfsBuilder, ImageBuilder
from smolvm.images.builder import SSH_BOOT_ARGS

if TYPE_CHECKING:
    from smolvm import BootImage

logger = logging.getLogger(__name__)

HAGENT_IMAGE_NAME = "hagent-sandbox"
DEFAULT_DISK_MIB = 4096

# docker export 只保留文件系统,Dockerfile ENV 不会进 VM 进程树——
# HOME/TERM 等运行期语义由 provider 的命令包装负责(sandbox.py)。
HAGENT_DOCKERFILE = """\
FROM python:3.12-slim

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update \\
    && apt-get install -y --no-install-recommends \\
        bash \\
        ca-certificates \\
        curl \\
        git \\
        ripgrep \\
        coreutils \\
        procps \\
        openssh-server \\
        iproute2 \\
    && rm -rf /var/lib/apt/lists/*

# uv: 与 docker provider 对齐的 Python 包安装器
RUN curl -LsSf https://astral.sh/uv/install.sh | env UV_INSTALL_DIR=/usr/local/bin sh

# LLM 可见工作目录:Firecracker 无 bind-mount,/workspace 随镜像内建(spec §7)
RUN mkdir -p /workspace

# host keys 烘焙期生成(ssh-keygen -A):init 的存在性守卫会跳过运行期 keygen——
# 运行期生成依赖 boot 后熵,crng 未就绪时 getrandom 阻塞不定长,sshd 迟迟不起
# (实测 init 卡在 ssh-hostkey 段数分钟)。一次性沙箱 + per-TAP 隔离网络,
# 共享 host key 无安全代价(客户端本就 StrictHostKeyChecking=no)。
RUN rm -f /etc/ssh/ssh_host_* \\
    && mkdir -p /run/sshd /root/.ssh && chmod 700 /root/.ssh \\
    && sed -ri 's/^#?PermitRootLogin .*/PermitRootLogin prohibit-password/' /etc/ssh/sshd_config \\
    && sed -ri 's/^#?PasswordAuthentication .*/PasswordAuthentication no/' /etc/ssh/sshd_config \\
    && sed -ri 's/^#?PubkeyAuthentication .*/PubkeyAuthentication yes/' /etc/ssh/sshd_config \\
    && ssh-keygen -A

# SSH 兜底通道:烘焙宿主默认公钥;为空时 SSH 不可用,vsock 主通道不受影响(F10)
COPY authorized_keys /root/.ssh/authorized_keys
RUN chmod 600 /root/.ssh/authorized_keys

# SmolVM guest agent(vsock 控制面,/init 启动;F7:必须显式注入)
COPY smolvm-guest-agent /usr/local/bin/smolvm-guest-agent
RUN chmod +x /usr/local/bin/smolvm-guest-agent

COPY init /init
RUN chmod +x /init
"""

_lock = threading.Lock()
_cache: dict[int, "BootImage"] = {}


def reset_cache() -> None:
    """清空进程内 BootImage 缓存(测试与显式重建用)。"""
    with _lock:
        _cache.clear()


def _disk_mib() -> int:
    raw = os.environ.get("HAGENT_SMOLVM_DISK_MIB", "").strip()
    return int(raw) if raw else DEFAULT_DISK_MIB


def _authorized_keys() -> str:
    """宿主默认 SSH 公钥内容;缺失时生成,失败时降级为空(仅 vsock)。"""
    try:
        from smolvm.utils import ensure_ssh_key

        _, public_key = ensure_ssh_key()
        return public_key.read_text(encoding="utf-8")
    except Exception as exc:  # noqa: BLE001
        logger.warning("SSH 公钥不可用,镜像仅 vsock 通道可达: %s", exc)
        return ""


def _build_context() -> dict[str, Any]:
    """Dockerfile COPY 物料:init 脚本、guest-agent 二进制、SSH 公钥。

    guest-agent 走 SDK 私有解析器(env 覆盖 → 源码构建 → release 下载),
    版本锁 0.0.25,SDK 升级任务须复核此引用。
    """
    from smolvm.images.builder import _guest_agent_binary

    return {
        "init": ImageBuilder()._base_init_script(custom_hostname="hagent"),
        "smolvm-guest-agent": _guest_agent_binary(),
        "authorized_keys": _authorized_keys(),
    }


def ensure_boot_image() -> "BootImage":
    """构建(或命中缓存)hagent boot image。

    两层缓存:DockerRootfsBuilder 自带内容指纹磁盘缓存(Dockerfile/context
    变更自动重建);此处再加进程内单飞——并发调用在锁上排队,首个完成构建,
    其余醒来直接命中,避免同进程重复 docker build。
    """
    disk_mib = _disk_mib()
    with _lock:
        cached = _cache.get(disk_mib)
        if cached is not None:
            return cached
        builder = DockerRootfsBuilder(
            name=HAGENT_IMAGE_NAME,
            dockerfile=HAGENT_DOCKERFILE,
            context=_build_context(),
            rootfs_size_mb=disk_mib,
            ssh_capable=True,
        )
        image = builder.build_boot_image(backend="firecracker", boot_args=SSH_BOOT_ARGS)
        _cache[disk_mib] = image
        return image
