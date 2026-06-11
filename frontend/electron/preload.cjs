const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('electronAPI', {
  // Tasks
  getTasks: () => ipcRenderer.invoke('tasks:getAll'),
  createTask: (task) => ipcRenderer.invoke('tasks:create', task),
  updateTask: (task) => ipcRenderer.invoke('tasks:update', task),
  deleteTask: (id) => ipcRenderer.invoke('tasks:delete', id),
  getTasksByStatus: (status) => ipcRenderer.invoke('tasks:getByStatus', status),

  // Chat
  getChatMessages: () => ipcRenderer.invoke('chat:getAll'),
  addChatMessage: (msg) => ipcRenderer.invoke('chat:add', msg),
  clearChat: () => ipcRenderer.invoke('chat:clear'),

  // Workspace
  getWorkspace: () => ipcRenderer.invoke('workspace:get'),
  setWorkspace: (dir) => ipcRenderer.invoke('workspace:set', dir),
  selectWorkspace: () => ipcRenderer.invoke('workspace:select'),
});
