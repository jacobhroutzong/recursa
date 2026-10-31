import {createRoot} from 'react-dom/client';
import {Counter} from './Counter';

const root = document.getElementById('root');
if (!root) throw new Error('Missing root');
createRoot(root).render(<Counter initial={0}/>);
