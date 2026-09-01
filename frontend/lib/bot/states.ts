// 状态目录 —— 表数据在 tables.ts（tables.js 1:1），这里只派生平台用的导出面。

import { GROUPS, EYE_PLAYLIST, type BotState, type StateGroup } from "./tables";

export type { BotState, StateGroup };

export const STATE_GROUPS: StateGroup[] = GROUPS;

export const ALL_STATES: BotState[] = STATE_GROUPS.flatMap((g) => g.states);

export const STATE_COUNT = ALL_STATES.length;

/** 校验外部传入的状态名是否可播 */
export function isBotState(name: string): name is BotState {
  return name in EYE_PLAYLIST;
}
