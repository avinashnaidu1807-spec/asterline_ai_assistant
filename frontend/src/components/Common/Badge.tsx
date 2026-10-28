import React from 'react';
import styles from './Badge.module.css';

type BadgeVariant =
  | 'primary'
  | 'success'
  | 'warning'
  | 'danger'
  | 'purple'
  | 'teal'
  | 'muted'
  | 'confidence-high'
  | 'confidence-medium'
  | 'confidence-low'
  | 'confidence-none'
  | 'verified'
  | 'conflict'
  | 'unverified'
  | 'preferences'
  | 'user_context'
  | 'active_projects'
  | 'decisions'
  | 'conversation_summaries';

interface BadgeProps {
  children: React.ReactNode;
  variant?: BadgeVariant;
  className?: string;
  title?: string;
}

const CATEGORY_VARIANT_MAP: Record<string, BadgeVariant> = {
  preferences: 'preferences',
  user_context: 'user_context',
  active_projects: 'active_projects',
  decisions: 'decisions',
  conversation_summaries: 'conversation_summaries',
};

export function Badge({ children, variant = 'muted', className = '', title }: BadgeProps) {
  return (
    <span
      className={`${styles.badge} ${styles[variant.replace(/-/g, '_')]} ${className}`}
      title={title}
    >
      {children}
    </span>
  );
}

export function categoryBadge(category: string) {
  const v = CATEGORY_VARIANT_MAP[category] ?? 'muted';
  const label = category.replace(/_/g, ' ');
  return <Badge variant={v}>{label}</Badge>;
}
