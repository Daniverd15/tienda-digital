export function assetUrl(value) {
  if (!value) return '';
  if (/^(https?:|data:|blob:)/i.test(value)) return value;

  const apiBase = import.meta.env.VITE_API_URL || 'http://localhost/api';
  if (value.startsWith('/uploads/')) return `${apiBase}${value}`;
  if (value.startsWith('uploads/')) return `${apiBase}/${value}`;
  return value;
}
