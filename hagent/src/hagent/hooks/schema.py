"""Hook 配置与输出的 pydantic schema。

配置侧对齐 CC src/schemas/hooks.ts（command/prompt/agent/http 四型
discriminated union）；输出侧对齐 src/types/hooks.ts 的
syncHookResponseSchema + async 响应形态。JSON 字段名与 CC 完全一致，
Python 侧用 alias 承接关键字冲突（if/async/continue）。
"""

from __future__ import annotations

from typing import Annotated, Any, Literal, Union

from pydantic import BaseModel, ConfigDict, Field


class _HookConfigBase(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    if_: str | None = Field(default=None, alias="if")
    timeout: float | None = Field(default=None, gt=0)  # 秒，与 CC 一致
    status_message: str | None = Field(default=None, alias="statusMessage")
    once: bool = False


class CommandHookConfig(_HookConfigBase):
    type: Literal["command"] = "command"
    command: str
    shell: Literal["bash", "powershell"] | None = None
    async_: bool = Field(default=False, alias="async")
    async_rewake: bool = Field(default=False, alias="asyncRewake")

    @property
    def dedup_payload(self) -> str:
        # 对齐 hooks.ts：shell 参与身份，缺省按 bash 归一
        return f"{self.shell or 'bash'}\0{self.command}\0{self.if_ or ''}"


class PromptHookConfig(_HookConfigBase):
    type: Literal["prompt"] = "prompt"
    prompt: str
    model: str | None = None

    @property
    def dedup_payload(self) -> str:
        return f"{self.prompt}\0{self.if_ or ''}"


class AgentHookConfig(_HookConfigBase):
    type: Literal["agent"] = "agent"
    prompt: str
    model: str | None = None

    @property
    def dedup_payload(self) -> str:
        return f"{self.prompt}\0{self.if_ or ''}"


class HttpHookConfig(_HookConfigBase):
    type: Literal["http"] = "http"
    url: str
    headers: dict[str, str] | None = None
    allowed_env_vars: list[str] | None = Field(default=None, alias="allowedEnvVars")

    @property
    def dedup_payload(self) -> str:
        return f"{self.url}\0{self.if_ or ''}"


HookConfig = Annotated[
    Union[CommandHookConfig, PromptHookConfig, AgentHookConfig, HttpHookConfig],
    Field(discriminator="type"),
]


class HookMatcherConfig(BaseModel):
    """settings.json 里 hooks.<事件> 数组的元素：{matcher?, hooks: [...]}"""

    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    matcher: str | None = None
    hooks: list[HookConfig] = Field(default_factory=list)


class HooksSettings(BaseModel):
    """settings.json 顶层（只消费 hooks 键，其余忽略）。"""

    model_config = ConfigDict(extra="ignore")

    hooks: dict[str, list[HookMatcherConfig]] = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# 输出侧（hook stdout 的 JSON 高级控制字段）
# ---------------------------------------------------------------------------


class HookSpecificOutput(BaseModel):
    """CC 按 hookEventName 判别的 union；这里用超集模型 + runner 层事件校验。"""

    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    hook_event_name: str | None = Field(default=None, alias="hookEventName")
    # PreToolUse
    permission_decision: Literal["allow", "deny", "ask"] | None = Field(
        default=None, alias="permissionDecision"
    )
    permission_decision_reason: str | None = Field(
        default=None, alias="permissionDecisionReason"
    )
    updated_input: dict[str, Any] | None = Field(default=None, alias="updatedInput")
    # 多事件共用
    additional_context: str | None = Field(default=None, alias="additionalContext")
    # SessionStart
    initial_user_message: str | None = Field(
        default=None, alias="initialUserMessage"
    )
    # PostToolUse
    updated_mcp_tool_output: Any | None = Field(
        default=None, alias="updatedMCPToolOutput"
    )
    # PermissionDenied
    retry: bool | None = None


class HookJSONOutput(BaseModel):
    """stdout 整体 JSON 时的高级控制字段（syncHookResponseSchema + async 形态）。"""

    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    continue_: bool | None = Field(default=None, alias="continue")
    suppress_output: bool | None = Field(default=None, alias="suppressOutput")
    stop_reason: str | None = Field(default=None, alias="stopReason")
    decision: Literal["approve", "block"] | None = None
    reason: str | None = None
    system_message: str | None = Field(default=None, alias="systemMessage")
    hook_specific_output: HookSpecificOutput | None = Field(
        default=None, alias="hookSpecificOutput"
    )
    # async 响应：{"async": true, "asyncTimeout"?: number}
    async_: bool | None = Field(default=None, alias="async")
    async_timeout: float | None = Field(default=None, alias="asyncTimeout")
