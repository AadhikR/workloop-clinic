// Post-build script: no-op — type="module" is required for the inlined ES module code.
// The app must be served via HTTP (not file://) — use the .bat launcher which starts Python server.
import { readFileSync } from 'fs';

const path = './dist/index.html';
const html = readFileSync(path, 'utf8');

if (html.includes('type="module"')) {
  console.log('✓ dist/index.html built correctly with type="module" (serve via HTTP, not file://)');
} else {
  console.log('✓ dist/index.html built.');
}
