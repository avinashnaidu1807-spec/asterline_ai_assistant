import React from 'react';
import styles from './EmptyState.module.css';

interface EmptyStateProps {
  icon?: React.ReactNode;
  heading: string;
  subtext?: string;
  action?: React.ReactNode;
}

export function EmptyState({ icon, heading, subtext, action }: EmptyStateProps) {
  return (
    <div className={styles.container}>
      {icon && <div className={styles.icon}>{icon}</div>}
      <h3 className={styles.heading}>{heading}</h3>
      {subtext && <p className={styles.subtext}>{subtext}</p>}
      {action && <div className={styles.action}>{action}</div>}
    </div>
  );
}
