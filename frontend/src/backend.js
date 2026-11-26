import { api } from "./api.js";

export const listWorkspaces = () => api("/workspaces");
export const createWorkspace = (name, slug) =>
  api("/workspaces", { method: "POST", body: { name, slug } });
export const listChannels = (workspaceId) => api(`/workspaces/${workspaceId}/channels`);
export const createChannel = (workspaceId, name) =>
  api(`/workspaces/${workspaceId}/channels`, { method: "POST", body: { name } });
export const addMember = (workspaceId, email, role = "member") =>
  api(`/workspaces/${workspaceId}/members`, { method: "POST", body: { email, role } });
export const listMessages = (workspaceId, channelId, { after } = {}) => {
  const query = after === undefined ? "" : `?after=${after}&limit=100`;
  return api(`/workspaces/${workspaceId}/channels/${channelId}/messages${query}`);
};

export const sendMessage = (workspaceId, channelId, body) =>
  api(`/workspaces/${workspaceId}/channels/${channelId}/messages`, {
    method: "POST",
    body: { body },
  });

export const listMembers = (workspaceId) => api(`/workspaces/${workspaceId}/members`);