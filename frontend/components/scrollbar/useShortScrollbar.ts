"use client";

import { useEffect } from "react";

interface Options {
  shrink: number;
  min: number;
  gutter: number;
  right: number;
}

const clamp = (v: number, lo: number, hi: number) =>
  Math.min(Math.max(v, lo), hi);

export function useShortScrollbar(selector: string, opts: Options) {
  useEffect(() => {
    const scroller = document.querySelector<HTMLElement>(selector);
    if (!scroller) return;

    const bar = document.createElement("div");
    bar.className = "short-scrollbar";
    bar.innerHTML =
      '<div class="short-scrollbar-track"><div class="short-scrollbar-thumb"></div></div>';
    document.body.appendChild(bar);

    const track = bar.querySelector(
      ".short-scrollbar-track",
    ) as HTMLElement | null;
    const thumb = bar.querySelector(
      ".short-scrollbar-thumb",
    ) as HTMLElement | null;
    if (!track || !thumb) {
      bar.remove();
      return;
    }

    let metrics = { top: 0, height: 0, travel: 0, thumbHeight: 0 };
    let raf = 0;
    let dragging = false;
    let dragStartY = 0;
    let dragStartTop = 0;

    const update = () => {
      raf = 0;
      const rect = scroller.getBoundingClientRect();
      const maxScroll = scroller.scrollHeight - scroller.clientHeight;
      const hidden = maxScroll <= 1 || rect.height <= 0 || rect.width <= 0;
      bar.classList.toggle("is-visible", !hidden);
      if (hidden) return;

      const trackHeight = Math.max(0, rect.height - opts.gutter * 2);
      const rawRatio = scroller.clientHeight / scroller.scrollHeight;
      const maxThumb = Math.max(40, trackHeight - 8);
      const minThumb = Math.min(opts.min, maxThumb);
      const thumbHeight = clamp(
        trackHeight * rawRatio * opts.shrink,
        minThumb,
        maxThumb,
      );
      const travel = Math.max(0, trackHeight - thumbHeight);
      const scrollRatio = maxScroll > 0 ? scroller.scrollTop / maxScroll : 0;
      const thumbTop = travel * scrollRatio;

      metrics = {
        top: rect.top + opts.gutter,
        height: trackHeight,
        travel,
        thumbHeight,
      };
      bar.style.top = `${metrics.top}px`;
      bar.style.left = `${rect.right - opts.right}px`;
      bar.style.height = `${trackHeight}px`;
      thumb.style.height = `${thumbHeight}px`;
      thumb.style.transform = `translateY(${thumbTop}px)`;
    };

    const schedule = () => {
      if (!raf) raf = requestAnimationFrame(update);
    };

    const onTrackDown = (event: PointerEvent) => {
      if (event.target === thumb || metrics.travel <= 0) return;
      const maxScroll = scroller.scrollHeight - scroller.clientHeight;
      const nextTop = event.clientY - metrics.top - metrics.thumbHeight / 2;
      scroller.scrollTop = clamp(nextTop / metrics.travel, 0, 1) * maxScroll;
    };
    const onThumbDown = (event: PointerEvent) => {
      event.preventDefault();
      dragging = true;
      dragStartY = event.clientY;
      dragStartTop = scroller.scrollTop;
      bar.classList.add("is-dragging");
      thumb.setPointerCapture(event.pointerId);
    };
    const onThumbMove = (event: PointerEvent) => {
      if (!dragging || metrics.travel <= 0) return;
      const maxScroll = scroller.scrollHeight - scroller.clientHeight;
      const deltaRatio = (event.clientY - dragStartY) / metrics.travel;
      scroller.scrollTop = dragStartTop + deltaRatio * maxScroll;
    };
    const stopDrag = (event: PointerEvent) => {
      if (!dragging) return;
      dragging = false;
      bar.classList.remove("is-dragging");
      if (
        event.pointerId !== undefined &&
        thumb.hasPointerCapture(event.pointerId)
      ) {
        thumb.releasePointerCapture(event.pointerId);
      }
    };

    track.addEventListener("pointerdown", onTrackDown);
    thumb.addEventListener("pointerdown", onThumbDown);
    thumb.addEventListener("pointermove", onThumbMove);
    thumb.addEventListener("pointerup", stopDrag);
    thumb.addEventListener("pointercancel", stopDrag);
    scroller.addEventListener("scroll", schedule, { passive: true });
    window.addEventListener("resize", schedule);

    const resizeObserver = new ResizeObserver(schedule);
    resizeObserver.observe(scroller);
    resizeObserver.observe(document.body);

    // 只监听节点增减（新消息行），不监听 characterData：流式逐 token 的纯文本增长会
    // 每帧触发 update() 里的 getBoundingClientRect 强制重排，越跑越卡。文本变长导致的
    // 滚动比例变化由下方 scroll 事件与 ResizeObserver 兜底，无需逐字符重算。
    const mutationObserver = new MutationObserver(schedule);
    mutationObserver.observe(scroller, {
      childList: true,
      subtree: true,
    });

    schedule();

    return () => {
      resizeObserver.disconnect();
      mutationObserver.disconnect();
      scroller.removeEventListener("scroll", schedule);
      window.removeEventListener("resize", schedule);
      bar.remove();
    };
  }, [selector, opts.shrink, opts.min, opts.gutter, opts.right]);
}
