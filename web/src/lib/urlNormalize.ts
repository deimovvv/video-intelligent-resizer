export function normalizeUrl(input: string): string {
  let u = input.trim();

  // --- Google Drive: /file/d/<ID>/view?usp=sharing  -> uc?export=download&id=<ID>
  const driveFileMatch = u.match(/https:\/\/drive\.google\.com\/file\/d\/([^/]+)\/view/i);
  if (driveFileMatch?.[1]) {
    const id = driveFileMatch[1];
    return `https://drive.google.com/uc?export=download&id=${id}`;
  }
  // Google Drive: open?id=<ID>
  const driveOpenMatch = u.match(/https:\/\/drive\.google\.com\/open\?id=([^&]+)/i);
  if (driveOpenMatch?.[1]) {
    const id = driveOpenMatch[1];
    return `https://drive.google.com/uc?export=download&id=${id}`;
  }

  // --- Dropbox: www.dropbox.com/s/XXXXX?dl=0 -> dl=1 (o dl.dropboxusercontent.com)
  if (/^https:\/\/www\.dropbox\.com\/s\//i.test(u)) {
    // Fuerza descarga directa
    if (u.includes('?')) {
      u = u.replace(/(\?|\&)dl=\d/i, '').replace(/\?$/, '');
      return u + (u.includes('?') ? '&dl=1' : '?dl=1');
    }
    return u + '?dl=1';
  }

  // --- OneDrive: agregar ?download=1 (variantes share)
  if (/^https:\/\/(1drv\.ms|onedrive\.live\.com)\//i.test(u)) {
    if (u.includes('?')) {
      return u + '&download=1';
    }
    return u + '?download=1';
  }

  // Lo demás: devolver tal cual
  return u;
}

export function looksLikeHttp(u: string) {
  return /^https?:\/\//i.test(u.trim());
}
