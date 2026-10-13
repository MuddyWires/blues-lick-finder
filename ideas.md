# Ideas for the next iterations

## Validation: manual ranking and level labels

This is the most important next step. Without my own labels, every comparison so far (search weights, prompt changes, comments) is judged by eye or against the rough `topic` field.

- **Label 10–15 videos by hand.** Pick them from `data/lessons.json`, mostly the BB King box and Hide Away videos, so there are several lessons per query to rank. For each video, record:
  - my rank within its query (1 = best)
  - my score from 1 to 5, using the same rubric as the prompt (Breakdown, Demonstration, Specifics, Why, Focus)
  - level: beginner, intermediate, advanced, or unclear
  - a short note on why
- **Store the labels in a file in the repo**, for example `data/manual_labels.csv` with columns `video_id, query, my_rank, my_score, my_level, note`. Unlike `lessons.json`, it holds only my own judgements and video IDs, so it can be committed.
- **Compare the model against the labels:**
  - Ranking: does the model's #1 match mine? How many of my top 3 are in its top 3? Rank correlation (Spearman) if there are enough videos per query.
  - Level: share of videos where the model's level matches mine.
  - Run each query 3+ times, because scores move by about 1 point between runs with the same data.
- **Reuse `03-search-eval.ipynb`.** Replace the `relevant` cell (built from `topic`) with my labels, then re-test the search weights and chunk sizes against real judgements.

## Prompt fixes

- **Tags regression.** With the level instructions added, the model returns the field names as tags ("technique, song") instead of real values ("BB King box, licks, key of G"). Fix by giving an example in `instructions`, e.g. `Tags: BB King box, bending, key of A`.
- **Missing comments are penalised.** GuitarJamz has no comments, and the model listed that as a reason for a low score. Add to `instructions`: "Missing or empty comments are neutral. Never lower a score because there are no comments."
- **Not every quoted comment is about teaching.** The model quoted "I don't often put my guitar down and just watch and listen" (28 likes), which praises the playing, not the lesson. It seems to pick high-like comments. Remind it that relevance to teaching matters more than likes.
- **Stop the LLM inventing lessons.** In one run it added a 6th lesson that wasn't in the search results (a made-up title with another result's URL). It hasn't happened since the quoting rule, but it's cheap to guard against: "Rank exactly the candidates in the CONTEXT. Never add, repeat, or rename a lesson."
- **Verify quotes in code.** Check every quoted comment and transcript quote against `lessons.json` automatically after each run, instead of by hand. All quotes checked so far were real.

## Level: decide it once per video

Right now the ranking LLM estimates the level on every run, from one transcript chunk. Better: classify each video once at fetch time (title, tags, start of transcript, comments), store it as a `level` field in `lessons.json`, and add `level` to the index's `keyword_fields`. Then:

- the same video always has the same level, which the practice log needs
- searches can filter: `index.search(query, filter_dict={"level": "beginner"})`
- it costs about 40 small LLM calls, once

## Comments

- **Sort by likes before keeping the top 20.** YouTube's "top" sort isn't strictly by likes (one video's first comments have 17, 24, 36 likes). Sort by `likes` in `fetch_comments` before slicing.
- **Filter comments with an LLM at fetch time** if the noise starts hurting rankings or prompts get too long. A keyword filter was tested and dropped: it kept noise like Patreon links and missed useful comments like "you get stuck right into it".

## Search: get past the intro chunk

For broad queries like "Which lessons teach the BB King box licks best?", the best chunk of every video is the first one (`start: 0`). The intro mentions the topic the most, so the LLM still sees mostly intros.

- **Excerpt rule (done, Oct 9).** `instructions` now say the excerpt is often the intro and that specific comments about the teaching can outweigh it. "5 Essential B.B. King Blues Licks" moved from 4th–5th (3/5) to 3rd (4/5), with the same order in 3 runs.
- **More specific queries.** For example "the BB King lick with the bend on the 10th fret". These match the middle of a lesson better than its intro.
- **Small search, large window — tested Oct 9, not adopted.** Search 800-character chunks (step 400, fetch 200 results before keeping the best chunk per video), then give the LLM a ~3,200-character window around the match (800 before, 2,400 from the match on). Results on 264 lessons:
  - Retrieval (9 topic questions, `topic` labels): same videos found (hit@5 89% both, prec@5 60% vs 58%), but the best chunk is the intro 40% of the time instead of 71%.
  - Ranking (BB King query + "slide into the 9th fret of the G string", 2 runs each): same order on the broad query; on the specific query Marty and "& Beyond" swapped, but neither window mentions the 9th fret, so the swap isn't explained by the question.
  - Conclusion: better location in the video, no clear ranking gain. Revisit together with transcript timestamps, where precise locations become visible as links. Fetching only 50 results is too few with small chunks (fewer than 5 videos come back).
- **Top 2 chunks per video.** Send the intro plus the next-best section to the LLM instead of only one chunk. Roughly doubles the transcript text per prompt; only worth it if labels show the model regularly underrates lessons whose teaching starts after the intro.

## Search: weight the transcript higher

Use `boost_dict` in `index.search`:

```python
index.search(query, num_results=50, boost_dict={"content": 3})
# or turn the metadata down too:
boost_dict={"content": 3, "title": 0.5, "description": 0.5, "tags": 0.5}
```

This doesn't change which chunk wins inside a video, because `title`, `description` and `tags` are the same in every chunk of a video. It changes which videos make the top 5.

Tested in `03-search-eval.ipynb` against the `topic` field: `content` x2 or x3 found 1 more relevant video out of 40 result slots, which is within noise. Removing the metadata fields entirely made results worse. Not worth changing until there are manual labels to test against.

## Data

- **Two topics have no usable videos.** "Texas blues shuffle rhythm" and "slow blues soloing" have 0 videos with transcripts, so they're missing from the index. Fetch more results per topic (e.g. 10 instead of 5) to fill them.
- **Keep transcript timestamps — deferred.** `fetch_transcript` joins the snippet text and drops `snippet.start`. Keeping it wouldn't need new chunking logic (`chunk_documents` already returns a character `start` offset per chunk); it would need a `(char_offset, video_seconds)` mapping built per video and a re-fetch of every cached transcript. Decided not worth it right now: it only gives a rough "chunk starts around here" link, not the exact lick, and doesn't affect ranking/retrieval quality at all. Revisit only once the practice log is actually being built. Until then, the cheaper partial substitute is the viewer-comment timestamps below.
- **Use timestamp comments.** Viewers often post lick timestamps, e.g. "Lick 1 03:00, Lick 2 04:40, Lick 3 05:43…" (36 likes on "5 Essential B.B. King Blues Licks"). Parsing these is a cheap way to get practice-log timestamps without re-fetching transcripts.

## Housekeeping

- **`.env.example` is a staged deletion.** Restore it (`git restore --staged --worktree .env.example`) or commit the deletion and update the README setup step, which tells people to `cp .env.example .env`.
