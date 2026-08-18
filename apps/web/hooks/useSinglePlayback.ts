"use client";

/**
 * Ensures only one <video> plays at a time across the app.
 *
 * A module-level reference tracks the currently playing element. When a new
 * video starts, any other playing video is paused first, so master and short
 * never overlap on the detail page. The browser fires the `pause` event
 * asynchronously, so `onPause` only releases the claim when it's for the active
 * element — pausing the old video can't clear the new one's claim.
 */
import type { SyntheticEvent } from "react";

let activeVideo: HTMLVideoElement | null = null;

export function useSinglePlayback() {
  return {
    onPlay: (event: SyntheticEvent<HTMLVideoElement>) => {
      const video = event.currentTarget;
      if (activeVideo && activeVideo !== video && !activeVideo.paused) {
        activeVideo.pause();
      }
      activeVideo = video;
    },
    onPause: (event: SyntheticEvent<HTMLVideoElement>) => {
      if (activeVideo === event.currentTarget) {
        activeVideo = null;
      }
    },
  };
}
