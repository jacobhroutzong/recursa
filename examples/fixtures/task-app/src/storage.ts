import type { Task } from './model';
const KEY = 'recursa-task-fixture-v1';

export function readTasks(): Task[] {
  try {
    const value: unknown = JSON.parse(localStorage.getItem(KEY) || '[]');
    if (!Array.isArray(value)) return [];
    return value.filter((task): task is Task => Boolean(task) && typeof task.id === 'string'
      && typeof task.title === 'string' && typeof task.completed === 'boolean');
  } catch { return []; }
}

export function saveTasks(tasks: Task[]): void {
  localStorage.setItem(KEY, JSON.stringify(tasks));
}
