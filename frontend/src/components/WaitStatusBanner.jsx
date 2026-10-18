import React from 'react';
import { WAIT_STAGES } from '../utils/waitStatus.js';

/**
 * Renders a progressive latency notification banner when backend queue/LLM latency is elevated.
 *
 * @param {Object} props
 * @param {string} props.stage - Current wait stage ('thinking' | 'queued' | 'extended')
 * @param {string} props.message - Descriptive reassurance message
 * @param {string} [props.variant='bubble'] - 'bubble' for in-chat bubble, 'dock' for above input
 */
export function WaitStatusBanner({ stage, message, variant = 'bubble' }) {
  if (stage === WAIT_STAGES.IDLE || stage === WAIT_STAGES.THINKING) {
    return null;
  }

  const isQueued = stage === WAIT_STAGES.QUEUED;
  const isExtended = stage === WAIT_STAGES.EXTENDED;

  const badgeClass = isQueued
    ? 'wait-badge-queued'
    : isExtended
    ? 'wait-badge-extended'
    : 'wait-badge-default';

  const icon = isQueued ? '⏳' : '🔨';

  return (
    <div
      className={`wait-status-banner ${badgeClass} variant-${variant}`}
      role="status"
      aria-live="polite"
    >
      <div className="wait-status-icon-wrapper">
        <span className="wait-pulse-ring"></span>
        <span className="wait-status-icon">{icon}</span>
      </div>
      <div className="wait-status-content">
        <p className="wait-status-text">{message}</p>
        <span className="wait-status-subtext">
          {isQueued
            ? 'Server is handling concurrent requests. Please keep this tab open.'
            : 'Generating comprehensive contractor tenders and matching categories.'}
        </span>
      </div>
    </div>
  );
}
