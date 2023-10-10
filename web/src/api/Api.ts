import ky from 'ky';

import { Agent, Chat } from '../store/types';

export const BASE_URL = `http://${window.location.hostname}:8000`;


// Inlined URLS here for more readable code and easier refactoring, delete this comment

// TODO: Better types for method parameters
export const Api = (function () {
  const execute = (body: object, signal?: AbortSignal) =>
  ky.post(`${BASE_URL}/execute`, { json: { ...body }, signal, timeout: 60000 });

  const run_code = ({chatId, signal, ...rest }: { chatId: string, language: string, code: string, signal?: AbortSignal }) =>
  ky.post(`${BASE_URL}/chats/${chatId}/run_code`, { json: rest, signal, timeout: 60000 });

  const getCommandHistory = () => ky.get(`${BASE_URL}/commands/history`);

  const getChatsHistory = () => ky.get(`${BASE_URL}/chats/headlines`);

  const getAgents: () => Promise<Agent[]> = async () => await ky.get(`${BASE_URL}/agents`).json();

  const getChat: (id: string) => Promise<Chat> = async (id: string) => await ky.get(`${BASE_URL}/chats/history/${id}`).json();

  const deleteChat = (id: string) => ky.delete(`${BASE_URL}/chats/history/${id}`);

  const saveCommandToHistory = (body: object) =>
    ky.post(`${BASE_URL}/commands/history`, { json: { ...body }, timeout: 60000 });

  const saveHistory = (body: object) =>
    ky.post(`${BASE_URL}/chats/history`, { json: { ...body }, timeout: 60000 });

  const analyse = (body: object, signal?: AbortSignal) =>
    ky.post(`${BASE_URL}/analyse`, { json: { ...body }, signal, timeout: 60000 });

  return {
    execute,
    run_code,
    analyse,
    getAgents,
    getCommandHistory,
    getChatsHistory,
    getChat,
    saveCommandToHistory,
    saveHistory,
    deleteChat,
  };
})()