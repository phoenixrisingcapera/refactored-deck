const API_BASE = 'http://localhost:8000/api/v1';

export async function fetchDecks() {
  const res = await fetch(`${API_BASE}/decks/`);
  if (!res.ok) throw new Error('Failed to fetch decks');
  return res.json();
}

export async function createDeck(name: string) {
  const res = await fetch(`${API_BASE}/decks/`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ name })
  });
  if (!res.ok) throw new Error('Failed to create deck');
  return res.json();
}
