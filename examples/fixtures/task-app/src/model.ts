export interface Task { id: string; title: string; completed: boolean }
export type StatusFilter = 'all' | 'active' | 'completed';

export function validTitle(value: string): boolean {
  return value.trim().length > 0;
}

export function matchingTasks(tasks: Task[], query: string, status: StatusFilter): Task[] {
  const needle = query.trim().toLowerCase();
  return tasks.filter(task => task.title.toLowerCase().includes(needle)
    && (status === 'all' || (status === 'completed' ? task.completed : !task.completed)));
}
