import { streamMessage } from './api.ts';
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { emptyModelRecovery, reduceModelRecovery, acceptsModelEvent, retryCountdown } from './modelRecovery.ts';
import { reduceChatEvent } from './timeline.ts';
import { reduceBotSignals, emptyBotSignals } from './botSignals.ts';

function project(events) {
  let recovery = emptyModelRecovery(), timeline = [], signals = emptyBotSignals();
  for (const event of events) {
    if (!acceptsModelEvent(recovery, event)) continue;
    recovery = reduceModelRecovery(recovery, event);
    timeline = reduceChatEvent(timeline, event);
    signals = reduceBotSignals(signals, event);
  }
  return { recovery, timeline, signals };
}
const ev = (event, data = {}) => ({ event, data });
const attempt = (id, number = 1, parent = null) => ({ model_call_id: id, attempt: number, parent_tool_use_id: parent });

test('失败尝试的正文、思考、工具参数被替换，已完成工具保留', () => {
  const first = attempt('call');
  const second = attempt('call', 2);
  const { timeline, recovery, signals } = project([
    ev('tool_call.started', { call_id: 'saved', tool_name: 'Write', args_chunk: '{}' }),
    ev('tool_call.completed', { call_id: 'saved', result_summary: '成果' }),
    ev('model.attempt.started', first),
    ev('message.delta', { ...first, content_chunk: [{ type: 'thinking', thinking: '旧思考' }, { type: 'text', text: '半截' }] }),
    ev('tool_call.started', { ...first, call_id: 'bad', tool_name: 'Write', args_chunk: '{"path":' }),
    ev('model.retry', { ...first, retry: 1, next_attempt_at: 2000, max_retries: 10 }),
    ev('message.delta', { ...first, content_chunk: '迟到旧输出' }),
    ev('tool_call.started', { ...first, call_id: 'late', tool_name: 'Write', args_chunk: '{}' }),
    ev('model.attempt.started', second),
    ev('message.delta', { ...second, content_chunk: '完整输出' }),
    ev('model.call.completed', second),
  ]);
  assert.deepEqual(timeline.map(m => m.role), ['tool', 'assistant_text']);
  assert.equal(timeline[0].call.status, 'done');
  assert.equal(timeline[1].content, '完整输出');
  assert.equal(recovery.calls.call.status, 'completed');
  assert.equal(signals.failed, false);
  assert.equal(signals.ended, false);
  assert.deepEqual(signals.scopes[''].active, {});
});

test('并发子任务独立归属与预算，重试不清空其他子任务', () => {
  const a = attempt('a', 1, 'parent-a'), b = attempt('b', 1, 'parent-b');
  const { recovery, timeline } = project([
    ...['a', 'b'].map(id => ev('tool_call.started', { call_id: `parent-${id}`, tool_name: 'Agent', args_chunk: `{"description":"子任务 ${id}"}` })),
    ev('model.attempt.started', a), ev('model.attempt.started', b),
    ev('message.delta', { ...a, content_chunk: '会替换' }),
    ev('message.delta', { ...b, content_chunk: '保留' }),
    ev('model.retry', { ...a, retry: 1, next_attempt_at: 6000 }),
  ]);
  assert.equal(timeline[0].run.children.length, 0);
  assert.equal(timeline[1].run.children[0].content, '保留');
  assert.equal(recovery.calls.a.status, 'retrying');
  assert.equal(recovery.calls.b.status, 'requesting');
  assert.equal(retryCountdown(recovery.calls.a, 1001), 5);
  assert.equal(retryCountdown(recovery.calls.a, 7000), 0);
});

test('取消标记未完成步骤，保存提示仅来自 checkpoint 确认', () => {
  const events = [
    ev('run.started', { run_id: 'run' }),
    ev('tool_call.started', { call_id: 'parent', tool_name: 'Agent' }),
    ev('tool_call.started', { call_id: 'done', parent_tool_use_id: 'parent', tool_name: 'Read' }),
    ev('tool_call.completed', { call_id: 'done', parent_tool_use_id: 'parent' }),
    ev('tool_call.started', { call_id: 'unfinished', parent_tool_use_id: 'parent', tool_name: 'Write' }),
    ev('run.cancelled', { checkpoint_saved: false }),
  ];
  const { recovery, timeline, signals } = project(events);
  assert.equal(recovery.cancelled, true);
  assert.equal(recovery.checkpointSaved, false);
  assert.equal(signals.ended, true);
  assert.equal(signals.cancelled, true);
  assert.equal(timeline[0].run.status, 'cancelled');
  assert.equal(timeline[0].run.children[0].call.status, 'done');
  assert.equal(timeline[0].run.children[1].call.status, 'cancelled');
  assert.equal(project([...events.slice(0,-1), ev('run.cancelled', { checkpoint_saved: true })]).recovery.checkpointSaved, true);
});

test('最终错误只生成一条错误节点并清除失败模型输出', () => {
  const data = attempt('call', 11);
  const { timeline, recovery } = project([
    ev('model.attempt.started', data),
    ev('message.delta', { ...data, content_chunk: '残留正文' }),
    ev('error', { ...data, category: 'overloaded', message: '服务暂时过载，已尝试 11 次。', attempts: 11, checkpoint_saved: true }),
  ]);
  assert.equal(timeline.length, 1);
  assert.equal(timeline[0].role, 'error');
  assert.equal(recovery.failure.attempts, 11);
  assert.equal(recovery.checkpointSaved, true);
});


test('流重新出现有效输出后清除较慢提示，继续保持运行态', () => {
  const data = attempt('slow');
  const { recovery, signals } = project([
    ev('model.attempt.started', data), ev('model.slow', { ...data, message: '响应较慢' }),
    ev('message.delta', { ...data, content_chunk: '继续输出' }),
  ]);
  assert.equal(recovery.calls.slow.status, 'requesting');
  assert.equal(recovery.calls.slow.message, undefined);
  assert.equal(signals.ended, false);
});


test('SSE 心跳不进入事件投影，消费结束释放读取锁', async () => {
  const originalFetch = globalThis.fetch;
  const body = new ReadableStream({ start(controller) {
    controller.enqueue(new TextEncoder().encode(': heartbeat\n\nevent: run.started\ndata: {"run_id":"r"}\n\n: heartbeat\n\nevent: done\ndata: {}\n\n'));
    controller.close();
  }});
  globalThis.fetch = async () => new Response(body);
  try {
    const events = [];
    for await (const event of streamMessage('s', '请求')) events.push(event.event);
    assert.deepEqual(events, ['run.started', 'done']);
    assert.equal(body.locked, false);
  } finally { globalThis.fetch = originalFetch; }
});

test('提前关闭前端消费迭代器会取消响应读取', async () => {
  const originalFetch = globalThis.fetch;
  let cancelled = false;
  const body = new ReadableStream({ start(controller) {
    controller.enqueue(new TextEncoder().encode('event: run.started\ndata: {"run_id":"r"}\n\n'));
  }, cancel() { cancelled = true; }});
  globalThis.fetch = async () => new Response(body);
  try {
    const iterator = streamMessage('s', '请求');
    await iterator.next();
    await iterator.return();
    assert.equal(cancelled, true);
    assert.equal(body.locked, false);
  } finally { globalThis.fetch = originalFetch; }
});
