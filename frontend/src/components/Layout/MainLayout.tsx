import { useState } from 'react';
import Sidebar from '../Sidebar/Sidebar';
import ChatArea from '../ChatArea/ChatArea';
import EvidencePanel from '../EvidencePanel/EvidencePanel';
import { useConversation } from '../../hooks/useConversation';
import type { User, Conversation, Message } from '../../types';
import styles from './MainLayout.module.css';

interface MainLayoutProps {
  users: User[];
  selectedUser: User | null;
  setSelectedUser: (user: User | null) => void;
  usersLoading: boolean;
}

export default function MainLayout({
  users,
  selectedUser,
  setSelectedUser,
  usersLoading,
}: MainLayoutProps) {
  const [selectedConvId, setSelectedConvId] = useState<string | null>(null);
  const [convListVersion, setConvListVersion] = useState(0); // bump to refresh list
  const [activeMessage, setActiveMessage] = useState<Message | null>(null);
  const [evidenceOpen, setEvidenceOpen] = useState(true);

  const { messages, isLoading, loadingStage, error, setError, sendMessage } = useConversation(
    selectedConvId,
    selectedUser?.id ?? null,
  );

  // Keep activeMessage in sync with last assistant message
  const lastAssistantMsg = [...messages].reverse().find((m) => m.role === 'assistant') ?? null;

  function handleSelectConversation(conv: Conversation) {
    setSelectedConvId(conv.id);
    setActiveMessage(null);
  }

  function handleNewConversation(conv: Conversation) {
    setSelectedConvId(conv.id);
    setActiveMessage(null);
    setConvListVersion((v) => v + 1);
  }

  async function handleSend(content: string) {
    await sendMessage(content);
    // activeMessage will update naturally via lastAssistantMsg
  }

  const displayMessage = activeMessage ?? lastAssistantMsg;

  return (
    <div className={styles.layout}>
      <aside className={styles.sidebar}>
        <Sidebar
          users={users}
          selectedUser={selectedUser}
          setSelectedUser={setSelectedUser}
          usersLoading={usersLoading}
          selectedConvId={selectedConvId}
          onSelectConversation={handleSelectConversation}
          onNewConversation={handleNewConversation}
          convListVersion={convListVersion}
        />
      </aside>

      <main className={styles.center}>
        <ChatArea
          messages={messages}
          isLoading={isLoading}
          loadingStage={loadingStage}
          error={error}
          onClearError={() => setError(null)}
          onSend={handleSend}
          selectedUser={selectedUser}
          onSelectMessage={setActiveMessage}
          activeMessageId={displayMessage?.id ?? null}
          evidenceOpen={evidenceOpen}
          onToggleEvidence={() => setEvidenceOpen((o) => !o)}
        />
      </main>

      {evidenceOpen && (
        <aside className={styles.evidence}>
          <EvidencePanel message={displayMessage} />
        </aside>
      )}
    </div>
  );
}
