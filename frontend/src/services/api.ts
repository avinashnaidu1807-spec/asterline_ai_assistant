import type { User, Conversation, Message, Memory, HealthStatus } from '../types';

const BASE = '/api';

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    headers: { 'Content-Type': 'application/json', ...options?.headers },
    ...options,
  });
  if (!res.ok) {
    let errorMsg = `API error ${res.status}`;
    try {
      const body = await res.json();
      errorMsg = body.detail || body.message || errorMsg;
    } catch {
      // ignore parse error
    }
    throw new Error(errorMsg);
  }
  if (res.status === 204) return undefined as T;
  return res.json() as Promise<T>;
}

// ── Users ────────────────────────────────────────────────────────────────────

export async function getUsers(): Promise<User[]> {
  return request<User[]>('/users');
}

// ── Conversations ─────────────────────────────────────────────────────────────

export async function getConversations(userId: string): Promise<Conversation[]> {
  return request<Conversation[]>(`/conversations?user_id=${encodeURIComponent(userId)}`);
}

export async function createConversation(userId: string, title?: string): Promise<Conversation> {
  return request<Conversation>('/conversations', {
    method: 'POST',
    body: JSON.stringify({ user_id: userId, title: title ?? 'New Conversation' }),
  });
}

export async function getConversation(
  convId: string,
): Promise<Conversation & { messages: Message[] }> {
  return request<Conversation & { messages: Message[] }>(`/conversations/${encodeURIComponent(convId)}`);
}

// ── Messages ──────────────────────────────────────────────────────────────────

export async function sendMessage(
  convId: string,
  userId: string,
  content: string,
): Promise<Message> {
  return request<Message>(`/conversations/${encodeURIComponent(convId)}/messages`, {
    method: 'POST',
    body: JSON.stringify({ user_id: userId, content }),
  });
}

// ── Memories ──────────────────────────────────────────────────────────────────

export async function getMemories(userId: string, category?: string): Promise<Memory[]> {
  const params = new URLSearchParams({ user_id: userId });
  if (category) params.set('category', category);
  return request<Memory[]>(`/memories?${params.toString()}`);
}

export async function createMemory(
  userId: string,
  category: Memory['category'],
  content: string,
): Promise<Memory> {
  return request<Memory>('/memories', {
    method: 'POST',
    body: JSON.stringify({ user_id: userId, category, content }),
  });
}

export async function updateMemory(
  memoryId: string,
  content: string,
  userId: string,
): Promise<Memory> {
  return request<Memory>(`/memories/${encodeURIComponent(memoryId)}`, {
    method: 'PUT',
    body: JSON.stringify({ content, user_id: userId }),
  });
}

export async function deleteMemory(memoryId: string, userId: string): Promise<void> {
  return request<void>(`/memories/${encodeURIComponent(memoryId)}?user_id=${encodeURIComponent(userId)}`, {
    method: 'DELETE',
  });
}

export async function deleteAllMemories(userId: string): Promise<{ deleted_count: number }> {
  return request<{ deleted_count: number }>(`/memories?user_id=${encodeURIComponent(userId)}`, {
    method: 'DELETE',
  });
}

// ── Health ────────────────────────────────────────────────────────────────────

export async function getHealth(): Promise<HealthStatus> {
  return request<HealthStatus>('/health');
}
