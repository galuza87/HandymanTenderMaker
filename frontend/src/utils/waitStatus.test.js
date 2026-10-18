import test, { describe, it } from 'node:test';
import assert from 'node:assert/strict';
import {
  WAIT_STAGES,
  WAIT_THRESHOLDS_MS,
  WAIT_MESSAGES,
  getWaitStatusForDuration,
  ProgressiveWaitTracker,
} from './waitStatus.js';

describe('Progressive Wait Status Logic', () => {
  it('should define valid wait stages and thresholds', () => {
    assert.equal(WAIT_STAGES.IDLE, 'idle');
    assert.equal(WAIT_STAGES.THINKING, 'thinking');
    assert.equal(WAIT_STAGES.QUEUED, 'queued');
    assert.equal(WAIT_STAGES.EXTENDED, 'extended');

    assert.equal(typeof WAIT_THRESHOLDS_MS.QUEUED, 'number');
    assert.equal(typeof WAIT_THRESHOLDS_MS.EXTENDED, 'number');
    assert.ok(WAIT_THRESHOLDS_MS.QUEUED < WAIT_THRESHOLDS_MS.EXTENDED);
  });

  it('should return IDLE state when not loading', () => {
    const status = getWaitStatusForDuration(0, false);
    assert.equal(status.stage, WAIT_STAGES.IDLE);
    assert.equal(status.isBannerVisible, false);
    assert.equal(status.message, '');
  });

  it('should return THINKING state for short durations (< 4s)', () => {
    const status = getWaitStatusForDuration(1500, true);
    assert.equal(status.stage, WAIT_STAGES.THINKING);
    assert.equal(status.isBannerVisible, false);
    assert.equal(status.message, WAIT_MESSAGES.THINKING);
  });

  it('should return QUEUED state when duration exceeds queued threshold (>= 4s and < 12s)', () => {
    const status = getWaitStatusForDuration(4500, true);
    assert.equal(status.stage, WAIT_STAGES.QUEUED);
    assert.equal(status.isBannerVisible, true);
    assert.equal(status.message, WAIT_MESSAGES.QUEUED);
  });

  it('should return EXTENDED state when duration exceeds extended threshold (>= 12s)', () => {
    const status = getWaitStatusForDuration(15000, true);
    assert.equal(status.stage, WAIT_STAGES.EXTENDED);
    assert.equal(status.isBannerVisible, true);
    assert.equal(status.message, WAIT_MESSAGES.EXTENDED);
  });

  it('ProgressiveWaitTracker should notify subscribers on stage transitions and clear timers', async () => {
    const transitions = [];
    const tracker = new ProgressiveWaitTracker({
      queuedDelayMs: 30,
      extendedDelayMs: 60,
      onStageChange: (stage, info) => {
        transitions.push({ stage, banner: info.isBannerVisible });
      },
    });

    tracker.start();
    assert.equal(transitions.length, 1);
    assert.equal(transitions[0].stage, WAIT_STAGES.THINKING);
    assert.equal(transitions[0].banner, false);

    // Wait for queued transition (30ms)
    await new Promise((resolve) => setTimeout(resolve, 40));
    assert.equal(transitions.length, 2);
    assert.equal(transitions[1].stage, WAIT_STAGES.QUEUED);
    assert.equal(transitions[1].banner, true);

    // Wait for extended transition (60ms)
    await new Promise((resolve) => setTimeout(resolve, 40));
    assert.equal(transitions.length, 3);
    assert.equal(transitions[2].stage, WAIT_STAGES.EXTENDED);
    assert.equal(transitions[2].banner, true);

    // Stop should reset to idle and prevent further callbacks
    tracker.stop();
    assert.equal(transitions.length, 4);
    assert.equal(transitions[3].stage, WAIT_STAGES.IDLE);
    assert.equal(transitions[3].banner, false);
  });

  it('ProgressiveWaitTracker should stop cleanly if response arrives early without showing banner', async () => {
    const transitions = [];
    const tracker = new ProgressiveWaitTracker({
      queuedDelayMs: 50,
      extendedDelayMs: 100,
      onStageChange: (stage, info) => {
        transitions.push({ stage, banner: info.isBannerVisible });
      },
    });

    tracker.start();
    assert.equal(transitions[0].stage, WAIT_STAGES.THINKING);

    // Stop after 10ms (before queued threshold)
    await new Promise((resolve) => setTimeout(resolve, 10));
    tracker.stop();

    // Wait past the threshold to verify no delayed trigger fired
    await new Promise((resolve) => setTimeout(resolve, 60));
    assert.equal(transitions.length, 2);
    assert.equal(transitions[1].stage, WAIT_STAGES.IDLE);
    // Banner was never shown
    assert.ok(transitions.every((t) => t.banner === false));
  });
});
