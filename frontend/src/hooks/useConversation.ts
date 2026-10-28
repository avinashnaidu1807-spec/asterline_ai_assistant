import { useState, useEffect, useCallback } from 'react';
import { getConversation, sendMessage as apiSendMessage } from '../services/api';
import type { Message } from '../types';

export function useConversation(conversationId: string | null, userId: string | null) {
  const [messages, setMessages] = useState<Message[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [loadingStage, setLoadingStage] = useState<string>('');

  // Load messages whenever the selected conversation changes
  useEffect(() => {
    if (!conversationId) {
      setMessages([]);
      return;
    }
    let cancelled = false;
    setIsLoading(true);
    setError(null);
    getConversation(conversationId)
      .then((data) => {
        if (!cancelled) setMessages(data.messages ?? []);
      })
      .catch((err: Error) => {
        if (!cancelled) setError(err.message);
      })
      .finally(() => {
        if (!cancelled) setIsLoading(false);
      });
    return () => { cancelled = true; };
  }, [conversationId]);

  const sendMessage = useCallback(
    async (content: string) => {
      if (!conversationId || !userId) return;

      // Optimistically add user message
      const tempUserMsg: Message = {
        id: `temp-user-${Date.now()}`,
        role: 'user',
        content,
        created_at: new Date().toISOString(),
      };
      setMessages((prev) => [...prev, tempUserMsg]);
      setIsLoading(true);
      setError(null);

      // Simulate multi-stage loading
      const stages = [
        'Research agent retrieving...',
        'Verification agent checking...',
        'Synthesizing answer...',
      ];
      let stageIdx = 0;
      setLoadingStage(stages[0]);
      const stageTimer = setInterval(() => {
        stageIdx = Math.min(stageIdx + 1, stages.length - 1);
        setLoadingStage(stages[stageIdx]);
      }, 1800);

      try {
        const response = await apiSendMessage(conversationId, userId, content);
        setMessages((prev) => [
          ...prev.filter((m) => m.id !== tempUserMsg.id),
          tempUserMsg,
          response,
        ]);
      } catch (err: unknown) {
        const message = err instanceof Error ? err.message : 'Failed to send message';
        setError(message);
        setMessages((prev) => prev.filter((m) => m.id !== tempUserMsg.id));
      } finally {
        clearInterval(stageTimer);
        setIsLoading(false);
        setLoadingStage('');
      }
    },
    [conversationId, userId],
  );

  return { messages, isLoading, loadingStage, error, setError, sendMessage };
}
