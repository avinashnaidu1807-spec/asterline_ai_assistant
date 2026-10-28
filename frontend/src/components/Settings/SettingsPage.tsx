import React, { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { getHealth } from '../../services/api';
import type { User, HealthStatus } from '../../types';
import styles from './SettingsPage.module.css';

interface SettingsPageProps {
  selectedUser: User | null;
}

export default function SettingsPage({ selectedUser }: SettingsPageProps) {
  const [health, setHealth] = useState<HealthStatus | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    getHealth()
      .then(setHealth)
      .catch(() => setHealth(null))
      .finally(() => setLoading(false));
  }, []);

  return (
    <div className={styles.container}>
      <header className={styles.header}>
        <Link to="/" className={styles.backLink}>
          ← Back to Chat
        </Link>
        <h1 className={styles.title}>System Settings & Status</h1>
      </header>

      <main className={styles.main}>
        {/* Status card */}
        <section className={styles.card}>
          <h2 className={styles.cardTitle}>System Health & Architecture</h2>
          {loading ? (
            <p>Checking service status...</p>
          ) : health ? (
            <div className={styles.grid}>
              <div className={styles.statItem}>
                <span className={styles.statLabel}>Overall Status</span>
                <span className={`${styles.statValue} ${styles.statGreen}`}>
                  ● {health.status.toUpperCase()}
                </span>
              </div>
              <div className={styles.statItem}>
                <span className={styles.statLabel}>Database (SQLite)</span>
                <span className={styles.statValue}>{health.database}</span>
              </div>
              <div className={styles.statItem}>
                <span className={styles.statLabel}>Local Vector Store (ChromaDB)</span>
                <span className={styles.statValue}>{health.vector_store}</span>
              </div>
              <div className={styles.statItem}>
                <span className={styles.statLabel}>LLM Provider</span>
                <span className={styles.statValue}>{health.llm}</span>
              </div>
              <div className={styles.statItem}>
                <span className={styles.statLabel}>Corpus Ingestion</span>
                <span className={styles.statValue}>{health.ingestion}</span>
              </div>
              <div className={styles.statItem}>
                <span className={styles.statLabel}>LangSmith Observability</span>
                <span className={styles.statValue}>{health.langsmith}</span>
              </div>
            </div>
          ) : (
            <p className={styles.errorText}>Unable to reach backend health endpoint.</p>
          )}
        </section>

        {/* User Context */}
        <section className={styles.card}>
          <h2 className={styles.cardTitle}>Active User Identity</h2>
          <div className={styles.userBox}>
            <p>
              Current simulated user:{' '}
              <strong>{selectedUser?.display_name ?? 'None'}</strong> (
              <code>{selectedUser?.username}</code>)
            </p>
            <p className={styles.securityNote}>
              Note: This user selector is a demonstration mechanism. Memory queries, updates, and
              deletions are strictly enforced per-user on the backend database layer to guarantee
              isolation.
            </p>
          </div>
        </section>

        {/* Knowledge Base info */}
        <section className={styles.card}>
          <h2 className={styles.cardTitle}>Authoritative Knowledge Base</h2>
          <p className={styles.kbDesc}>
            Asterline Research Assistant operates on the immutable company knowledge base containing
            75 chunks across 25 documents. Embeddings are generated locally using the ONNX-optimized
            MiniLM-L6-v2 model.
          </p>
        </section>
      </main>
    </div>
  );
}

