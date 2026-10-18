import { useState, useRef, useEffect, useCallback } from 'react';
import {
  WAIT_STAGES,
  WAIT_MESSAGES,
  ProgressiveWaitTracker,
} from '../utils/waitStatus.js';

/**
 * Custom hook to manage progressive delay feedback during asynchronous operations.
 *
 * @param {Object} [options]
 * @param {number} [options.queuedDelayMs=4000]
 * @param {number} [options.extendedDelayMs=12000]
 * @returns {{
 *   waitStage: string,
 *   isBannerVisible: boolean,
 *   bannerMessage: string,
 *   startWait: () => void,
 *   stopWait: () => void,
 * }}
 */
export function useProgressiveWait(options = {}) {
  const [waitState, setWaitState] = useState({
    stage: WAIT_STAGES.IDLE,
    isBannerVisible: false,
    message: '',
  });

  const trackerRef = useRef(null);

  useEffect(() => {
    trackerRef.current = new ProgressiveWaitTracker({
      ...options,
      onStageChange: (stage, info) => {
        setWaitState(info);
      },
    });

    return () => {
      if (trackerRef.current) {
        trackerRef.current.clear();
      }
    };
  }, []);

  const startWait = useCallback(() => {
    if (trackerRef.current) {
      trackerRef.current.start();
    }
  }, []);

  const stopWait = useCallback(() => {
    if (trackerRef.current) {
      trackerRef.current.stop();
    }
  }, []);

  return {
    waitStage: waitState.stage,
    isBannerVisible: waitState.isBannerVisible,
    bannerMessage: waitState.message,
    startWait,
    stopWait,
  };
}
