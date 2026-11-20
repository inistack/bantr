import { api } from "./api.js";

export const listWorkspaces = () => api("/workspaces");
export const createWorkspace = (name, slug) =>
  api("/workspaces", { method: "POST", body: { name, slug } });
export const listChannels = (workspaceId) => api(`/workspaces/${workspaceId}/channels`);
export const createChannel = (workspaceId, name) =>
  api(`/workspaces/${workspaceId}/channels`, { method: "POST", body: { name } });
export const addMember = (workspaceId, email, role = "member") =>
  api(`/workspaces/${workspaceId}/members`, { method: "POST", body: { email, role } });