/** 身份只依赖稳定的调用/角色标识，状态变化不重新选色。 */
export function botIdentityTone(identity: string): number {
  let hash = 2166136261;
  for (const char of identity)
    hash = Math.imul(hash ^ char.codePointAt(0)!, 16777619);
  return (hash >>> 0) % 8;
}
