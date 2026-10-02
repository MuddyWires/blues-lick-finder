# Ideas for the next iterations

## Search: get past the intro chunk

For broad queries like "Which lessons teach the BB King box licks best?", the best chunk of every video is the first one (`start: 0`). The intro mentions the topic the most, so the LLM still sees mostly intros.

- **More specific queries.** For example "the BB King lick with the bend on the 10th fret". These match the middle of a lesson better than its intro.
- **Smaller chunks.** Try `chunk_documents(..., size=1500, step=750)`. The intro takes up less text, and teaching sections compete more evenly.
- **Top 2 chunks per video.** Send the intro plus the next-best section to the LLM instead of only one chunk.

## Search: weight the transcript higher

Use `boost_dict` in `index.search`:

```python
index.search(query, num_results=50, boost_dict={"content": 3})
# or turn the metadata down too:
boost_dict={"content": 3, "title": 0.5, "description": 0.5, "tags": 0.5}
```

This doesn't change which chunk wins inside a video, because `title`, `description` and `tags` are the same in every chunk of a video. It changes which videos make the top 5: a video that actually talks about the topic can beat one that only has the words in its title or tags.

## Prompt: stop the LLM inventing lessons

In one run the LLM added a 6th lesson that wasn't in the search results (a made-up title with the URL of another result). Add to `instructions`:

> Rank exactly the candidates in the CONTEXT. Never add, repeat, or rename a lesson.

## Data: keep transcript timestamps

`fetch_transcript` joins the snippet text and drops `snippet.start`. If the timestamps were kept and chunks were split by time instead of characters, each result could link straight to the moment in the video (`...watch?v=ID&t=95s`). That's also what the practice log needs ("lick 3 starts at 4:12"). This needs a re-fetch of `data/lessons.json`.
