import { useState, useEffect } from 'react';
import { getUsers } from '../services/api';
import type { User } from '../types';

export function useUsers() {
  const [users, setUsers] = useState<User[]>([]);
  const [selectedUser, setSelectedUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    getUsers()
      .then((data) => {
        if (cancelled) return;
        setUsers(data);
        if (data.length > 0) setSelectedUser(data[0]);
      })
      .catch((err: Error) => {
        if (cancelled) return;
        setError(err.message);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => { cancelled = true; };
  }, []);

  function switchUser(userId: string) {
    const found = users.find((u) => u.id === userId) ?? null;
    setSelectedUser(found);
  }

  return { users, selectedUser, setSelectedUser, switchUser, loading, error };
}
