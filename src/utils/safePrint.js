import DOMPurify from 'dompurify';

export function safePrint(html, { width = 820, height = 920 } = {}) {
  const clean = DOMPurify.sanitize(html, {
    WHOLE_DOCUMENT: true,
    ADD_TAGS: ['style', 'link', 'title', 'head', 'body', 'html'],
  });
  const win = window.open('', '_blank', `width=${width},height=${height}`);
  if (!win) {
    alert('Pop-up blocked — please allow pop-ups for this site.');
    return null;
  }
  win.document.write(clean);
  win.document.close();
  return win;
}
