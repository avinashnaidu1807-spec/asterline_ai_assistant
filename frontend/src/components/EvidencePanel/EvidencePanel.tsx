import React, { useState } from 'react';
import type { Message, ChunkReference } from '../../types';
import styles from './EvidencePanel.module.css';

interface EvidencePanelProps {
  message: Message | null;
}

export default function EvidencePanel({ message }: EvidencePanelProps) {
  const [selectedChunk, setSelectedChunk] = useState<ChunkReference | null>(null);

  if (!message || message.role !== 'assistant') {
    return (
      <div className={styles.panel}>
        <div className={styles.header}>
          <h2 className={styles.title}>Evidence & Context</h2>
        </div>
        <div className={styles.empty}>
          <div className={styles.emptyIcon}>🔍</div>
          <p className={styles.emptyTitle}>No answer selected</p>
          <p className={styles.emptyText}>
            Click on any assistant message to inspect its supporting documentary citations,
            chunk IDs, and relevant user memories.
          </p>
        </div>
      </div>
    );
  }

  const sources = message.sources ?? [];
  const claims = message.claims ?? [];
  const trace = message.agent_trace;
  const memoryOps = trace?.memory_ops ?? [];

  return (
    <div className={styles.panel}>
      <div className={styles.header}>
        <h2 className={styles.title}>Evidence & Context</h2>
        <span className={styles.chunkCountBadge}>
          {sources.length} {sources.length === 1 ? 'source' : 'sources'}
        </span>
      </div>

      <div className={styles.contentScroll}>
        {/* Authoritative Documentary Evidence Section */}
        <section className={styles.section}>
          <div className={styles.sectionHeader}>
            <span className={styles.sectionTag}>Authoritative Knowledge Base</span>
            <span className={styles.sectionNotice}>Grounded in corpus.jsonl</span>
          </div>

          {sources.length === 0 ? (
            <div className={styles.noEvidenceCard}>
              <p>No document chunks were cited for this response.</p>
            </div>
          ) : (
            <div className={styles.chunkList}>
              {sources.map((chunk) => {
                const isSelected = selectedChunk?.chunk_id === chunk.chunk_id;
                return (
                  <div
                    key={chunk.chunk_id}
                    className={`${styles.chunkCard} ${isSelected ? styles.chunkCardExpanded : ''}`}
                    onClick={() => setSelectedChunk(isSelected ? null : chunk)}
                  >
                    <div className={styles.chunkCardHeader}>
                      <span className={styles.chunkIdBadge}>{chunk.chunk_id}</span>
                      <span className={styles.chunkVersion}>v{chunk.version}</span>
                    </div>

                    <h4 className={styles.docTitle}>{chunk.title}</h4>

                    <div className={styles.metaRow}>
                      <span className={styles.categoryBadge}>{chunk.category}</span>
                      {chunk.published && (
                        <span className={styles.pubDate}>Published: {chunk.published}</span>
                      )}
                      {chunk.relevance_score !== undefined && (
                        <span className={styles.scoreBadge}>
                          Relevance: {Math.round(chunk.relevance_score * 100)}%
                        </span>
                      )}
                    </div>

                    <div className={styles.snippetBox}>
                      <p className={styles.snippetText}>{chunk.text_snippet}</p>
                    </div>

                    {isSelected && (
                      <div className={styles.expandedDetails}>
                        <div className={styles.detailRow}>
                          <span className={styles.detailLabel}>Document ID:</span>
                          <span className={styles.detailVal}>{chunk.doc_id}</span>
                        </div>
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          )}
        </section>

        {/* Verified Claims & Limitations Section */}
        {claims.length > 0 && (
          <section className={styles.section}>
            <div className={styles.sectionHeader}>
              <span className={styles.sectionTag}>Verified Claims</span>
            </div>
            <div className={styles.claimList}>
              {claims.map((claim, idx) => (
                <div key={idx} className={styles.claimCard}>
                  <div className={styles.claimConfidence}>
                    <span
                      className={`${styles.confDot} ${
                        claim.confidence === 'high'
                          ? styles.confHigh
                          : claim.confidence === 'medium'
                          ? styles.confMedium
                          : styles.confLow
                      }`}
                    />
                    <span className={styles.confText}>Confidence: {claim.confidence}</span>
                  </div>
                  <p className={styles.claimText}>{claim.claim}</p>
                  {claim.supporting_chunk_ids.length > 0 && (
                    <div className={styles.claimCitations}>
                      <span>Sources:</span>
                      {claim.supporting_chunk_ids.map((cid) => (
                        <span key={cid} className={styles.miniChip}>
                          {cid}
                        </span>
                      ))}
                    </div>
                  )}
                </div>
              ))}
            </div>
          </section>
        )}

        {/* User Memory Context — Visually Distinct */}
        <section className={styles.memorySection}>
          <div className={styles.memorySectionHeader}>
            <span className={styles.memoryTag}>User Context & Memory</span>
            <span className={styles.memoryNotice}>Not authoritative company fact</span>
          </div>
          <div className={styles.memoryCard}>
            <p className={styles.memoryHelp}>
              Personalized user context is retained across conversations to assist continuity, but
              never overrides official company documentation.
            </p>
            {memoryOps.length > 0 ? (
              <div className={styles.memoryOpsList}>
                <span className={styles.opsLabel}>Agent memory operations this turn:</span>
                {memoryOps.map((op, idx) => (
                  <span key={idx} className={styles.opBadge}>
                    {op}
                  </span>
                ))}
              </div>
            ) : (
              <p className={styles.noMemoryOpText}>No memory updates occurred in this turn.</p>
            )}
          </div>
        </section>
      </div>
    </div>
  );
}

