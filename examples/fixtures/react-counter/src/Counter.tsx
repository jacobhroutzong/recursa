import {useState} from 'react';

export interface CounterProps { initial: number }

export function Counter({initial}: CounterProps) {
  const [count, setCount] = useState(initial);
  return <main>
    <h1>React counter fixture</h1>
    <p role="status" aria-label="Count">Count: {count}</p>
    <button onClick={() => setCount(current => current + 1)}>Increment</button>
    <button disabled={count === initial} onClick={() => setCount(initial)}>Reset</button>
  </main>;
}
