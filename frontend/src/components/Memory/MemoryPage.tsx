import React, { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import {
  getMemories,
  createMemory,
  updateMemory,
  deleteMemory,
  deleteAllMemories,
} from '../../services/api';
import type { User, Memory } from '../../types';
import { Button } from '../Common/Button';
import { Modal } from '../Common/Modal';
import styles from './MemoryPage.module.css';

interface MemoryPageProps {
  selectedUser: User | null;
}

const CATEGORIES: Array<{ key: string; label: string }> = [
  { key: 'all', label: 'All Categories' },
  { key: 'preferences', label: 'Preferences' },
  { key: 'user_context', label: 'User Context' },
  { key: 'active_projects', label: 'Active Projects' },
  { key: 'decisions', label: 'Decisions' },
  { key: 'conversation_summaries', label: 'Summaries' },
];

export default function MemoryPage({ selectedUser }: MemoryPageProps) {
  const [memories, setMemories] = useState<Memory[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedCat, setSelectedCat] = useState('all');
  const [searchQuery, setSearchQuery] = useState('');

  // Modals state
  const [editModalOpen, setEditModalOpen] = useState(false);
  const [editingMemory, setEditingMemory] = useState<Memory | null>(null);
  const [editContent, setEditContent] = useState('');

  const [addModalOpen, setAddModalOpen] = useState(false);
  const [newContent, setNewContent] = useState('');
  const [newCategory, setNewCategory] = useState<Memory['category']>('preferences');

  const [deleteConfirmOpen, setDeleteConfirmOpen] = useState(false);

  useEffect(() => {
    loadMemories();
  }, [selectedUser, selectedCat]);

  async function loadMemories() {
    if (!selectedUser) {
      setMemories([]);
      setLoading(false);
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const catParam = selectedCat === 'all' ? undefined : selectedCat;
      const data = await getMemories(selectedUser.id, catParam);
      setMemories(data);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to load memories');
    } finally {
      setLoading(false);
    }
  }

  async function handleSaveEdit() {
    if (!editingMemory || !selectedUser) return;
    try {
      await updateMemory(editingMemory.id, editContent, selectedUser.id);
      setEditModalOpen(false);
      await loadMemories();
    } catch (err: unknown) {
      alert(err instanceof Error ? err.message : 'Failed to update memory');
    }
  }

  async function handleCreateMemory() {
    if (!selectedUser || !newContent.trim()) return;
    try {
      await createMemory(selectedUser.id, newCategory, newContent.trim());
      setAddModalOpen(false);
      setNewContent('');
      await loadMemories();
    } catch (err: unknown) {
      alert(err instanceof Error ? err.message : 'Failed to create memory');
    }
  }

  async function handleDeleteOne(id: string) {
    if (!selectedUser) return;
    if (!confirm('Are you sure you want to delete this memory?')) return;
    try {
      await deleteMemory(id, selectedUser.id);
      await loadMemories();
    } catch (err: unknown) {
      alert(err instanceof Error ? err.message : 'Failed to delete memory');
    }
  }

  async function handleDeleteAll() {
    if (!selectedUser) return;
    try {
      await deleteAllMemories(selectedUser.id);
      setDeleteConfirmOpen(false);
      await loadMemories();
    } catch (err: unknown) {
      alert(err instanceof Error ? err.message : 'Failed to delete all memories');
    }
  }

  const filtered = memories.filter((m) =>
    searchQuery ? m.content.toLowerCase().includes(searchQuery.toLowerCase()) : true
  );

  return (
    <div className={styles.container}>
      {/* Header */}
      <header className={styles.header}>
        <div className={styles.headerLeft}>
          <Link to="/" className={styles.backLink}>
            ← Back to Chat
          </Link>
          <h1 className={styles.title}>Persistent Memory Management</h1>
          <span className={styles.userBadge}>
            Active User: <strong>{selectedUser?.display_name ?? 'None'}</strong>
          </span>
        </div>
        <div className={styles.headerActions}>
          <Button variant="primary" onClick={() => setAddModalOpen(true)}>
            + Add Memory
          </Button>
          <Button
            variant="danger"
            disabled={memories.length === 0}
            onClick={() => setDeleteConfirmOpen(true)}
          >
            Delete All Memories
          </Button>
        </div>
      </header>

      {/* Info notice about memory policy */}
      <div className={styles.policyNotice}>
        <strong>Memory Policy & Isolation:</strong> Memories are stored strictly per-user in SQLite
        and survive restarts. Remembered statements personal context only and{' '}
        <em>never substitute for authoritative company evidence</em>. You can review, correct, or
        forget any memory at any time.
      </div>

      {/* Filter and Search Bar */}
      <div className={styles.filterBar}>
        <div className={styles.tabs}>
          {CATEGORIES.map((c) => (
            <button
              key={c.key}
              className={`${styles.tab} ${selectedCat === c.key ? styles.activeTab : ''}`}
              onClick={() => setSelectedCat(c.key)}
            >
              {c.label}
            </button>
          ))}
        </div>
        <input
          type="text"
          className={styles.searchInput}
          placeholder="Search remembered facts..."
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
        />
      </div>

      {/* Content */}
      <main className={styles.main}>
        {error && <div className={styles.errorBanner}>{error}</div>}

        {loading ? (
          <div className={styles.loading}>Loading persistent memories...</div>
        ) : filtered.length === 0 ? (
          <div className={styles.empty}>
            <div className={styles.emptyIcon}>🧠</div>
            <h3>No memories found</h3>
            <p>
              {selectedCat !== 'all'
                ? `No memories under category '${selectedCat}'.`
                : 'As you interact with Asterline, the Memory Agent will selectively preserve your workflow preferences and project context.'}
            </p>
          </div>
        ) : (
          <div className={styles.grid}>
            {filtered.map((m) => (
              <div key={m.id} className={styles.card}>
                <div className={styles.cardTop}>
                  <span className={styles.categoryPill}>{m.category.replace('_', ' ')}</span>
                  <span className={styles.statusPill}>{m.status}</span>
                </div>

                <p className={styles.cardContent}>{m.content}</p>

                <div className={styles.cardMeta}>
                  <span>Created: {new Date(m.created_at).toLocaleDateString()}</span>
                  {m.updated_at && m.updated_at !== m.created_at && (
                    <span>Updated: {new Date(m.updated_at).toLocaleDateString()}</span>
                  )}
                </div>

                <div className={styles.cardActions}>
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => {
                      setEditingMemory(m);
                      setEditContent(m.content);
                      setEditModalOpen(true);
                    }}
                  >
                    Edit / Correct
                  </Button>
                  <Button variant="danger" size="sm" onClick={() => handleDeleteOne(m.id)}>
                    Forget
                  </Button>
                </div>
              </div>
            ))}
          </div>
        )}
      </main>

      {/* Edit/Correct Modal */}
      <Modal
        isOpen={editModalOpen}
        onClose={() => setEditModalOpen(false)}
        title="Edit or Correct Memory"
      >
        <div className={styles.modalBody}>
          <p className={styles.modalDesc}>
            Correcting this memory updates the active record in the database and preserves
            provenance.
          </p>
          <textarea
            className={styles.modalTextarea}
            rows={4}
            value={editContent}
            onChange={(e) => setEditContent(e.target.value)}
          />
          <div className={styles.modalFooter}>
            <Button variant="ghost" onClick={() => setEditModalOpen(false)}>
              Cancel
            </Button>
            <Button variant="primary" onClick={handleSaveEdit}>
              Save Correction
            </Button>
          </div>
        </div>
      </Modal>

      {/* Add Memory Modal */}
      <Modal isOpen={addModalOpen} onClose={() => setAddModalOpen(false)} title="Add User Memory">
        <div className={styles.modalBody}>
          <label className={styles.modalLabel}>Category</label>
          <select
            className={styles.modalSelect}
            value={newCategory}
            onChange={(e) => setNewCategory(e.target.value as Memory['category'])}
          >
            <option value="preferences">Preferences</option>
            <option value="user_context">User Context</option>
            <option value="active_projects">Active Projects</option>
            <option value="decisions">Decisions</option>
            <option value="conversation_summaries">Conversation Summaries</option>
          </select>

          <label className={styles.modalLabel}>Content</label>
          <textarea
            className={styles.modalTextarea}
            rows={4}
            placeholder="e.g. Prefer concise answers with bullet points..."
            value={newContent}
            onChange={(e) => setNewContent(e.target.value)}
          />
          <div className={styles.modalFooter}>
            <Button variant="ghost" onClick={() => setAddModalOpen(false)}>
              Cancel
            </Button>
            <Button variant="primary" onClick={handleCreateMemory}>
              Save Memory
            </Button>
          </div>
        </div>
      </Modal>

      {/* Delete All Confirmation Modal */}
      <Modal
        isOpen={deleteConfirmOpen}
        onClose={() => setDeleteConfirmOpen(false)}
        title="Confirm Forget All Memories"
      >
        <div className={styles.modalBody}>
          <p className={styles.modalDesc}>
            Are you sure you want to permanently delete all stored memories for{' '}
            <strong>{selectedUser?.display_name}</strong>? This action cannot be undone.
          </p>
          <div className={styles.modalFooter}>
            <Button variant="ghost" onClick={() => setDeleteConfirmOpen(false)}>
              Cancel
            </Button>
            <Button variant="danger" onClick={handleDeleteAll}>
              Yes, Delete All
            </Button>
          </div>
        </div>
      </Modal>
    </div>
  );
}

