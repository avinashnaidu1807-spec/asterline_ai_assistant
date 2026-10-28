import { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { getConversations, createConversation, getHealth } from '../../services/api';
import type { User, Conversation, HealthStatus } from '../../types';
import styles from './Sidebar.module.css';
import { Button } from '../Common/Button';

interface SidebarProps {
  users: User[];
  selectedUser: User | null;
  setSelectedUser: (user: User | null) => void;
  usersLoading: boolean;
  selectedConvId: string | null;
  onSelectConversation: (conv: Conversation) => void;
  onNewConversation: (conv: Conversation) => void;
  convListVersion: number;
}

function formatDate(iso: string) {
  const d = new Date(iso);
  const now = new Date();
  const diff = now.getTime() - d.getTime();
  const days = Math.floor(diff / 86400000);
  if (days === 0) return 'Today';
  if (days === 1) return 'Yesterday';
  if (days < 7) return `${days}d ago`;
  return d.toLocaleDateString(undefined, { month: 'short', day: 'numeric' });
}

export default function Sidebar({
  users,
  selectedUser,
  setSelectedUser,
  usersLoading,
  selectedConvId,
  onSelectConversation,
  onNewConversation,
  convListVersion,
}: SidebarProps) {
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [convsLoading, setConvsLoading] = useState(false);
  const [creating, setCreating] = useState(false);
  const [health, setHealth] = useState<HealthStatus | null>(null);

  // Load conversations when user or version changes
  useEffect(() => {
    if (!selectedUser) { setConversations([]); return; }
    let cancelled = false;
    setConvsLoading(true);
    getConversations(selectedUser.id)
      .then((data) => { if (!cancelled) setConversations(data); })
      .catch(() => { if (!cancelled) setConversations([]); })
      .finally(() => { if (!cancelled) setConvsLoading(false); });
    return () => { cancelled = true; };
  }, [selectedUser, convListVersion]);

  // Poll health every 30 s
  useEffect(() => {
    let cancelled = false;
    function poll() {
      getHealth()
        .then((h) => { if (!cancelled) setHealth(h); })
        .catch(() => { if (!cancelled) setHealth(null); });
    }
    poll();
    const id = setInterval(poll, 30_000);
    return () => { cancelled = true; clearInterval(id); };
  }, []);

  async function handleNewChat() {
    if (!selectedUser || creating) return;
    setCreating(true);
    try {
      const conv = await createConversation(selectedUser.id);
      setConversations((prev) => [conv, ...prev]);
      onNewConversation(conv);
    } catch {
      // ignore
    } finally {
      setCreating(false);
    }
  }

  const isHealthy =
    health !== null &&
    health.status === 'ok' &&
    health.database === 'ok' &&
    health.vector_store === 'ok';

  return (
    <div className={styles.sidebar}>
      {/* Logo */}
      <div className={styles.logo}>
        <div className={styles.logoIcon}>⭐</div>
        <div>
          <div className={styles.logoName}>Asterline Labs</div>
          <div className={styles.logoSubtitle}>Research Assistant</div>
        </div>
      </div>

      {/* User Selector */}
      <div className={styles.section}>
        <label className={styles.sectionLabel}>Active User</label>
        {usersLoading ? (
          <div className={styles.userLoading}>Loading users…</div>
        ) : (
          <select
            className={styles.userSelect}
            value={selectedUser?.id ?? ''}
            onChange={(e) => {
              const u = users.find((u) => u.id === e.target.value) ?? null;
              setSelectedUser(u);
            }}
          >
            {users.map((u) => (
              <option key={u.id} value={u.id}>
                {u.display_name} (@{u.username})
              </option>
            ))}
          </select>
        )}
      </div>

      {/* New Chat */}
      <div className={styles.newChatWrapper}>
        <Button
          variant="primary"
          fullWidth
          loading={creating}
          onClick={handleNewChat}
          disabled={!selectedUser}
          icon={<span>✏️</span>}
        >
          New Chat
        </Button>
      </div>

      {/* Conversation List */}
      <div className={styles.convSection}>
        <div className={styles.sectionLabel}>Conversations</div>
        <div className={styles.convList}>
          {convsLoading && (
            <div className={styles.convLoading}>Loading…</div>
          )}
          {!convsLoading && conversations.length === 0 && (
            <div className={styles.convEmpty}>No conversations yet</div>
          )}
          {conversations.map((conv) => (
            <button
              key={conv.id}
              className={`${styles.convItem} ${conv.id === selectedConvId ? styles.convItemActive : ''}`}
              onClick={() => onSelectConversation(conv)}
              title={conv.title}
            >
              <span className={styles.convTitle}>{conv.title}</span>
              <span className={styles.convDate}>{formatDate(conv.updated_at)}</span>
            </button>
          ))}
        </div>
      </div>

      {/* Bottom Links */}
      <div className={styles.bottomSection}>
        <Link to="/memory" className={styles.navLink}>
          <span>🧠</span> Memory Manager
        </Link>
        <Link to="/settings" className={styles.navLink}>
          <span>⚙️</span> Settings
        </Link>

        {/* Health Status */}
        <div className={styles.healthRow}>
          <span
            className={`${styles.healthDot} ${isHealthy ? styles.healthOk : styles.healthBad}`}
            title={health ? `Status: ${health.status}` : 'API unreachable'}
          />
          <span className={styles.healthLabel}>
            {isHealthy ? 'API connected' : health === null ? 'Connecting…' : 'Degraded'}
          </span>
        </div>
      </div>
    </div>
  );
}
