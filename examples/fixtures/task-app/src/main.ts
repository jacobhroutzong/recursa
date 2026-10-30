import { matchingTasks, validTitle, type Task, type StatusFilter } from './model';
import { readTasks, saveTasks } from './storage';

function required<T extends HTMLElement>(selector: string): T {
  const element = document.querySelector<T>(selector);
  if (!element) throw new Error('Required fixture control is missing');
  return element;
}

let tasks: Task[] = readTasks();
const form = required<HTMLFormElement>('#task-form');
const title = required<HTMLInputElement>('#task-title');
const search = required<HTMLInputElement>('#search');
const status = required<HTMLSelectElement>('#status');
const list = required<HTMLUListElement>('#task-list');
const error = required<HTMLParagraphElement>('#task-error');

function render(): void {
  list.replaceChildren();
  const visible = matchingTasks(tasks, search.value, status.value as StatusFilter);
  required('#task-count').textContent = `${visible.length} of ${tasks.length} tasks shown`;
  for (const task of visible) {
    const item = document.createElement('li');
    const label = document.createElement('label');
    const toggle = document.createElement('input');
    toggle.type = 'checkbox'; toggle.checked = task.completed;
    toggle.setAttribute('aria-label', `Complete ${task.title}`);
    toggle.addEventListener('change', () => {
      tasks = tasks.map(current => current.id === task.id ? {...current, completed: toggle.checked} : current);
      saveTasks(tasks); render();
    });
    const text = document.createElement('span'); text.textContent = task.title;
    if (task.completed) text.className = 'completed';
    label.append(toggle, text); item.append(label); list.append(item);
  }
  if (!visible.length) {
    const empty = document.createElement('li'); empty.className = 'empty';
    empty.textContent = 'No tasks match your filters.'; list.append(empty);
  }
}

form.addEventListener('submit', event => {
  event.preventDefault();
  if (!validTitle(title.value)) { error.textContent = 'Enter a task title.'; title.focus(); return; }
  tasks = [...tasks, {id: crypto.randomUUID(), title: title.value.trim(), completed: false}];
  error.textContent = ''; title.value = ''; saveTasks(tasks); render(); title.focus();
});
search.addEventListener('input', render); status.addEventListener('change', render);
for (const view of ['tasks', 'about']) {
  required<HTMLButtonElement>(`#show-${view}`).addEventListener('click', () => {
    required('#tasks-panel').hidden = view !== 'tasks';
    required('#about-panel').hidden = view !== 'about';
    required('#show-tasks').setAttribute('aria-pressed', String(view === 'tasks'));
    required('#show-about').setAttribute('aria-pressed', String(view === 'about'));
  });
}
render();
