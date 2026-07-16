<script>
  import { fetchDecks, createDeck } from '/api/deckServiceClient';

  let decks = ([]);
  let newDeckName = ('');

  async function handleFetch() {
    decks = await fetchDecks();
  }

  async function handleCreate() {
    await createDeck(newDeckName);
    newDeckName = '';
    handleFetch();
  }

  handleFetch();
</script>

<h1 class="text-2xl font-bold mb-4">Deck AI Stack</h1>

<form onsubmit={handleCreate} class="mb-4">
  <input 
    bind:value={newDeckName} 
    placeholder="New Deck Name" 
    required 
    class="border p-2 mr-2"
  />
  <button type="submit" class="bg-blue-500 text-white px-4 py-2">Create</button>
</form>

<ul>
  {#each decks as deck (deck.id)}
    <li class="border-b py-2">{deck.name}</li>
  {/each}
</ul>
