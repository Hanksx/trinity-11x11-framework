import fs from 'node:fs';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
const app = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const source = path.resolve(app, '../core/trinity_solver_engine_v1.py');
const dest = path.resolve(app, 'src-tauri/solver_backend/trinity_solver_engine_v1.py');
if (!fs.existsSync(source)) throw new Error(`Trinity 11×11 core não encontrado: ${source}`);
fs.copyFileSync(source, dest);
console.log('Solver Python sincronizado:', source, '->', dest);
