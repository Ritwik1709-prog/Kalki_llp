export const API_URL = (import.meta.env.VITE_API_URL || "http://localhost:8000").replace(/\/+$/, "");
function url(path: string) { return `${API_URL}/${path.replace(/^\/+/, "")}`; }
export async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(url(path), init);
  if (!response.ok) throw new Error(`Backend returned HTTP ${response.status}`);
  return response.json() as Promise<T>;
}
export function events(path: string): EventSource { return new EventSource(url(path)); }
