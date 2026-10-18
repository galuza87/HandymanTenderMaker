/**
 * Progressive wait status constants, copy, and tracker for handling
 * server queue delays and LLM latency gracefully.
 */

export const WAIT_STAGES = Object.freeze({
  IDLE: 'idle',
  THINKING: 'thinking',
  QUEUED: 'queued',
  EXTENDED: 'extended',
});

export const WAIT_THRESHOLDS_MS = Object.freeze({
  QUEUED: 4000,
  EXTENDED: 12000,
});

export const WAIT_MESSAGES = Object.freeze({
  THINKING: 'Thinking...',
  QUEUED: 'High demand — your request is queued and being processed...',
  EXTENDED: 'Still working! Crafting your tender specifications...',
});

/**
 * Calculates current wait status object based on elapsed milliseconds and loading flag.
 *
 * @param {number} durationMs - Elapsed time in milliseconds
 * @param {boolean} isLoading - Whether a request is actively in progress
 * @returns {{ stage: string, isBannerVisible: boolean, message: string }}
 */
export function getWaitStatusForDuration(durationMs, isLoading) {
  if (!isLoading) {
    return {
      stage: WAIT_STAGES.IDLE,
      isBannerVisible: false,
      message: '',
    };
  }

  if (durationMs >= WAIT_THRESHOLDS_MS.EXTENDED) {
    return {
      stage: WAIT_STAGES.EXTENDED,
      isBannerVisible: true,
      message: WAIT_MESSAGES.EXTENDED,
    };
  }

  if (durationMs >= WAIT_THRESHOLDS_MS.QUEUED) {
    return {
      stage: WAIT_STAGES.QUEUED,
      isBannerVisible: true,
      message: WAIT_MESSAGES.QUEUED,
    };
  }

  return {
    stage: WAIT_STAGES.THINKING,
    isBannerVisible: false,
    message: WAIT_MESSAGES.THINKING,
  };
}

/**
 * Orchestrates progressive delay timeouts and notifies subscribers on state transitions.
 */
export class ProgressiveWaitTracker {
  /**
   * @param {Object} options
   * @param {number} [options.queuedDelayMs=4000]
   * @param {number} [options.extendedDelayMs=12000]
   * @param {Function} options.onStageChange - Callback receiving (stage, statusInfo)
   */
  constructor({
    queuedDelayMs = WAIT_THRESHOLDS_MS.QUEUED,
    extendedDelayMs = WAIT_THRESHOLDS_MS.EXTENDED,
    onStageChange,
  } = {}) {
    this.queuedDelayMs = queuedDelayMs;
    this.extendedDelayMs = extendedDelayMs;
    this.onStageChange = onStageChange;
    this.currentStage = WAIT_STAGES.IDLE;
    this.timer1 = null;
    this.timer2 = null;
  }

  /**
   * Starts tracking timers from the thinking stage.
   */
  start() {
    this.clear();
    this._setStage(WAIT_STAGES.THINKING, false, WAIT_MESSAGES.THINKING);

    this.timer1 = setTimeout(() => {
      this._setStage(WAIT_STAGES.QUEUED, true, WAIT_MESSAGES.QUEUED);
    }, this.queuedDelayMs);

    this.timer2 = setTimeout(() => {
      this._setStage(WAIT_STAGES.EXTENDED, true, WAIT_MESSAGES.EXTENDED);
    }, this.extendedDelayMs);
  }

  /**
   * Stops all active timers and resets back to idle.
   */
  stop() {
    this.clear();
    this._setStage(WAIT_STAGES.IDLE, false, '');
  }

  /**
   * Clears active timeouts.
   */
  clear() {
    if (this.timer1) {
      clearTimeout(this.timer1);
      this.timer1 = null;
    }
    if (this.timer2) {
      clearTimeout(this.timer2);
      this.timer2 = null;
    }
  }

  _setStage(stage, isBannerVisible, message) {
    this.currentStage = stage;
    if (typeof this.onStageChange === 'function') {
      this.onStageChange(stage, { stage, isBannerVisible, message });
    }
  }
}
