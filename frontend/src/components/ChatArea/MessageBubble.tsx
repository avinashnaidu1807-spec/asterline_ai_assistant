import React from 'react';
import ReactMarkdown from 'react-markdown';
import type { Message } from '../../types';
import styles from './MessageBubble.module.css';

interface MessageBubbleProps {
  message: Message;
  isActive: boolean;
  onClick: () => void;
}

export default function MessageBubble({ message, isActive, onClick }: MessageBubbleProps) {
  const isUser = message.role === 'user';
  const hasSources = !isUser && message.sources && message.sources.length > 0;
  const hasLimitations = !isUser && message.limitations && message.limitations.length > 0;

  return (
    <div
      className={`${styles.row} ${isUser ? styles.userRow : styles.assistantRow} ${
        isActive ? styles.activeRow : ''
      }`}
      onClick={onClick}
    >
      <div className={styles.avatar}>{isUser ? '👤' : '🤖'}</div>

      <div className={styles.contentWrapper}>
        <div className={styles.bubbleHeader}>
          <span className={styles.author}>{isUser ? 'You' : 'Asterline AI'}</span>
          <span className={styles.time}>
            {new Date(message.created_at).toLocaleTimeString([], {
              hour: '2-digit',
              minute: '2-digit',
            })}
          </span>
          {hasSources && (
            <span className={styles.sourceCountBadge}>
              {message.sources!.length} cited {message.sources!.length === 1 ? 'source' : 'sources'}
            </span>
          )}
        </div>

        <div className={`${styles.bubble} ${isUser ? styles.userBubble : styles.assistantBubble}`}>
          <ReactMarkdown>{message.content}</ReactMarkdown>
        </div>

        {hasLimitations && (
          <div className={styles.limitationsBanner}>
            <span className={styles.warningIcon}>⚠️</span>
            <span>{message.limitations!.join(' ')}</span>
          </div>
        )}

        {hasSources && (
          <div className={styles.citationsRow}>
            <span className={styles.citationLabel}>Citations:</span>
            {message.sources!.slice(0, 5).map((s) => (
              <span key={s.chunk_id} className={styles.citationChip} title={s.title}>
                {s.chunk_id}
              </span>
            ))}
            <span className={styles.inspectHint}>Click to inspect evidence →</span>
          </div>
        )}
      </div>
    </div>
  );
}

