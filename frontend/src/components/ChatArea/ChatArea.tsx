import { useRef, useEffect } from 'react';
import type { Message, User } from '../../types';
import MessageBubble from './MessageBubble';
import styles from './ChatArea.module.css';
import { Button } from '../Common/Button';

const EXAMPLE_QUESTIONS = [
  { label: 'HR', question: 'What is the current on-call stipend for employees?' },
  { label: 'Compliance', question: 'How long are my run records retained after the searchable period?' },
  { label: 'Product', question: 'What is the current ingestion limit for the Launch tier?' },
  { label: 'Operations', question: 'What happened in the March 2026 Signals incident?' },
];

interface ChatAreaProps {
  messages: Message[];
  isLoading: boolean;
  loadingStage: string;
  error: string | null;
  onClearError: () => void;
  onSend: (content: string) => Promise<void>;
  selectedUser: User | null;
  onSelectMessage: (msg: Message | null) => void;
  activeMessageId: string | null;
  evidenceOpen: boolean;
  onToggleEvidence: () => void;
}

export default function ChatArea({
  messages,
  isLoading,
  loadingStage,
  error,
  onClearError,
  onSend,
  selectedUser,
  onSelectMessage,
  activeMessageId,
  evidenceOpen,
  onToggleEvidence,
}: ChatAreaProps) {
  const bottomRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  // Auto-scroll on new messages
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, isLoading]);

  function autoResizeTextarea() {
    const el = textareaRef.current;
    if (!el) return;
    el.style.height = 'auto';
    el.style.height = `${Math.min(el.scrollHeight, 180)}px`;
  }

  async function handleSend() {
    const el = textareaRef.current;
    if (!el) return;
    const content = el.value.trim();
    if (!content || isLoading || !selectedUser) return;
    el.value = '';
    el.style.height = 'auto';
    await onSend(content);
  }

  function handleKeyDown(e: React.KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  }

  function handleExampleClick(q: string) {
    const el = textareaRef.current;
    if (!el) return;
    el.value = q;
    autoResizeTextarea();
    el.focus();
  }

  const showWelcome = messages.length === 0 && !isLoading;

  return (
    <div className={styles.chatArea}>
      {/* Topbar */}
      <div className={styles.topbar}>
        <span className={styles.topbarTitle}>
          {selectedUser ? `Research Chat — ${selectedUser.display_name}` : 'Research Chat'}
        </span>
        <Button
          variant="ghost"
          size="sm"
          onClick={onToggleEvidence}
          title={evidenceOpen ? 'Hide evidence panel' : 'Show evidence panel'}
        >
          {evidenceOpen ? '▶ Hide Evidence' : '◀ Show Evidence'}
        </Button>
      </div>

      {/* Messages / Welcome */}
      <div className={styles.messageList}>
        {showWelcome && (
          <div className={styles.welcome}>
            <div className={styles.welcomeIcon}>⭐</div>
            <h1 className={styles.welcomeTitle}>Asterline Research Assistant</h1>
            <p className={styles.welcomeSubtitle}>
              Ask research questions across company docs, policies, and operational records.
              Answers are grounded in verified source chunks with full citations.
            </p>
            <div className={styles.exampleGrid}>
              {EXAMPLE_QUESTIONS.map((eq) => (
                <button
                  key={eq.question}
                  className={styles.exampleCard}
                  onClick={() => handleExampleClick(eq.question)}
                >
                  <span className={styles.exampleLabel}>{eq.label}</span>
                  <span className={styles.exampleQuestion}>{eq.question}</span>
                </button>
              ))}
            </div>
          </div>
        )}

        {messages.map((msg) => (
          <MessageBubble
            key={msg.id}
            message={msg}
            isActive={msg.id === activeMessageId}
            onClick={() => onSelectMessage(msg)}
          />
        ))}

        {/* Loading indicator */}
        {isLoading && (
          <div className={styles.loadingRow}>
            <div className={styles.loadingDots}>
              <span /><span /><span />
            </div>
            <span className={styles.loadingStage}>
              {loadingStage || 'Agents working…'}
            </span>
          </div>
        )}

        {/* Error banner */}
        {error && (
          <div className={styles.errorBanner}>
            <span>⚠️ {error}</span>
            <button className={styles.errorDismiss} onClick={onClearError}>✕</button>
          </div>
        )}

        <div ref={bottomRef} />
      </div>

      {/* Composer */}
      <div className={styles.composer}>
        <div className={styles.composerInner}>
          <textarea
            ref={textareaRef}
            className={styles.textarea}
            placeholder={
              selectedUser
                ? 'Ask a research question… (Enter to send, Shift+Enter for newline)'
                : 'Select a user to start chatting'
            }
            disabled={!selectedUser || isLoading}
            onInput={autoResizeTextarea}
            onKeyDown={handleKeyDown}
            rows={1}
          />
          <Button
            variant="primary"
            size="md"
            onClick={handleSend}
            disabled={!selectedUser || isLoading}
            loading={isLoading}
            className={styles.sendBtn}
            aria-label="Send message"
          >
            Send
          </Button>
        </div>
        <p className={styles.composerHint}>
          Answers are grounded in documentary evidence. Memories personalise but never replace sources.
        </p>
      </div>
    </div>
  );
}
