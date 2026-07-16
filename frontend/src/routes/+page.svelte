<script>
  let decks = [];
  let newDeckName = '';

  async function fetchDecks() {
    const res = await fetch('http://localhost:8000/api/v1/decks/');
    decks = await res.json();
  }

  async function createDeck() {
    const res = await fetch('http://localhost:8000/api/v1/decks/', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name: newDeckName })
    });
    if (res.ok) {
      newDeckName = '';
      fetchDecks();
    }
  }

  fetchDecks();
</script>

<h1>Deck AI Stack</h1>

<form on:submit|preventDefault={createDeck}>
  <input bind:value={newDeckName} placeholder="New Deck Name" required />
  <button type="submit">Create</button>
</form>

<ul>
  {#each decks as deck}
    <li>{deck.name}</li>
  {/each}
</ul>
