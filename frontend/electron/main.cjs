const { app, BrowserWindow, ipcMain, dialog } = require('electron');
const path = require('path');
const fs = require('fs');

let mainWindow = null;

// JSON file-based storage with task migration
function getDbPath() {
  return path.join(app.getPath('userData'), 'pgimcode-data.json');
}

function migrateTask(task) {
  return {
    id: task.id,
    title: task.title || '',
    description: task.description || '',
    status: task.status || 'planning',
    model: task.model || 'gemini-3.5-flash',
    plan: task.plan || '',
    plan_conversation: task.plan_conversation || '',
    stream_response: task.stream_response || '',
    created_at: task.created_at || new Date().toISOString(),
    updated_at: task.updated_at || new Date().toISOString(),
    position: typeof task.position === 'number' ? task.position : 0,
  };
}

function readData() {
  try {
    const raw = fs.readFileSync(getDbPath(), 'utf-8');
    const data = JSON.parse(raw);
    return {
      tasks: (data.tasks || []).map(migrateTask),
      chat_messages: data.chat_messages || [],
      workspace_dir: data.workspace_dir || '',
    };
  } catch {
    return { tasks: [], chat_messages: [], workspace_dir: '' };
  }
}

function writeData(data) {
  fs.writeFileSync(getDbPath(), JSON.stringify(data, null, 2));
}

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1400,
    height: 900,
    minWidth: 1000,
    minHeight: 600,
    titleBarStyle: 'hiddenInset',
    title: 'pgimcode',
    backgroundColor: '#020617',
    webPreferences: {
      preload: path.join(__dirname, 'preload.cjs'),
      contextIsolation: true,
      nodeIntegration: false,
    },
  });

  if (process.env.VITE_DEV_SERVER_URL) {
    mainWindow.loadURL(process.env.VITE_DEV_SERVER_URL);
    mainWindow.webContents.openDevTools();
  } else {
    mainWindow.loadFile(path.join(__dirname, '..', 'dist', 'index.html'));
  }
}

// IPC Handlers - Tasks
ipcMain.handle('tasks:getAll', () => {
  const data = readData();
  return data.tasks.sort((a, b) => a.position - b.position);
});

ipcMain.handle('tasks:create', (_event, task) => {
  const data = readData();
  data.tasks.push(task);
  writeData(data);
  return task;
});

ipcMain.handle('tasks:update', (_event, task) => {
  const data = readData();
  const idx = data.tasks.findIndex((t) => t.id === task.id);
  if (idx !== -1) {
    data.tasks[idx] = task;
  } else {
    data.tasks.push(task);
  }
  writeData(data);
  return task;
});

ipcMain.handle('tasks:delete', (_event, id) => {
  const data = readData();
  data.tasks = data.tasks.filter((t) => t.id !== id);
  writeData(data);
  return { success: true };
});

ipcMain.handle('tasks:getByStatus', (_event, status) => {
  const data = readData();
  return data.tasks.filter((t) => t.status === status).sort((a, b) => a.position - b.position);
});

// IPC Handlers - Chat
ipcMain.handle('chat:getAll', () => {
  const data = readData();
  return data.chat_messages.sort((a, b) => new Date(a.created_at).getTime() - new Date(b.created_at).getTime());
});

ipcMain.handle('chat:add', (_event, msg) => {
  const data = readData();
  data.chat_messages.push(msg);
  writeData(data);
  return msg;
});

ipcMain.handle('chat:clear', () => {
  const data = readData();
  data.chat_messages = [];
  writeData(data);
  return { success: true };
});

// IPC Handlers - Workspace
ipcMain.handle('workspace:get', () => {
  const data = readData();
  return data.workspace_dir || '';
});

ipcMain.handle('workspace:set', (_event, dir) => {
  const data = readData();
  data.workspace_dir = dir;
  writeData(data);
  return { success: true };
});

ipcMain.handle('workspace:select', async () => {
  const result = await dialog.showOpenDialog(mainWindow, {
    properties: ['openDirectory'],
    title: 'Select Working Directory',
  });
  if (result.canceled) return '';
  const dir = result.filePaths[0];
  const data = readData();
  data.workspace_dir = dir;
  writeData(data);
  return dir;
});

app.whenReady().then(() => {
  createWindow();
  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) createWindow();
  });
});

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') app.quit();
});
