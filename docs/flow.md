# Flow diagrams

Three views of the system, for anyone reading or evaluating the code: how one question travels through the agent, how the data behind it is prepared, and how the agent is measured. GitHub draws the diagrams from the text below. Orange outlines mark what the latest changes added.

1. [One question, end to end](#1-one-question-end-to-end)
2. [How the data gets ready](#2-how-the-data-gets-ready)
3. [How the agent is measured](#3-how-the-agent-is-measured)

## 1. One question, end to end

The model chooses tools and gives its answer. Code checks the lessons it recommends against the lesson data before anything reaches the screen.

```mermaid
flowchart TB
    you["<b>You</b><br/>CLI or Streamlit"]
    agent["<b>Agent</b><br/>gpt-5.4-mini<br/>+ prompt<br/>8-request limit"]
    tools["<b>Tool layer</b><br/>7 tools<br/>fixed-message results"]
    biz["<b>Business layer</b><br/>PracticeLog (atomic)<br/>TopicQueue<br/>LessonStore"]
    search["<b>Search</b><br/>embed the question,<br/>compare with cached<br/>chunk vectors,<br/>top 5"]
    check["<b>Output check</b><br/>are all video_ids in<br/>our lesson data?"]
    present["<b>present()</b><br/>title, channel,<br/>level, link from<br/>our data"]
    back["<b>Back to you</b><br/>short answer<br/>+ lessons from<br/>our data"]
    dropped["Dropped and flagged,<br/>never shown"]

    you -->|"question + history"| agent
    agent <-->|"call / result"| tools
    tools <-->|"log ops"| biz
    tools <-->|"search_lessons"| search
    agent ==>|"final answer:<br/>Reply or AgentResponse"| check
    check -.->|"unknown id:<br/>retry once"| agent
    check ==>|"ids ok"| present
    present ==>|"show"| back
    present -.->|"still unknown<br/>after the retry"| dropped

    classDef added stroke:#d97706,stroke-width:3px
    class check,present,dropped added
```

- The model returns video_ids and a reason per lesson. It never writes a title or a link; code looks them up.
- A refusal, a history answer or a save confirmation uses `Reply`, which has no lessons field. That kept off-topic questions at 28 of 28 correct in the repeat test.
- One question costs about 2 to 3 model requests and 1 embedding call, roughly $0.007 to $0.01 on mini.

| Step | Where it lives |
|---|---|
| chat loop | `lick_finder/__main__.py` |
| agent, prompt, output check | `lick_finder/agent/agent.py` |
| tools and fixed messages | `lick_finder/agent/tools.py`, `tool_messages.py` |
| practice log, lesson data, topics | `lick_finder/business/` |
| search and embeddings | `lick_finder/integrations/search.py`, `embeddings.py` |
| filling in lessons | `lick_finder/agent/present.py`, `business/lessons.py` |

## 2. How the data gets ready

Fetching and indexing are offline steps you run yourself. The app only reads what they produce.

```mermaid
flowchart LR
    topics[("<b>data/topics.txt</b><br/>searches, channels<br/>queue_topic adds here")]
    fetch["<b>make fetch</b><br/>yt-dlp: metadata, transcripts,<br/>comments. 1-3 min per topic"]
    lessons[("<b>lessons.json</b><br/>750 lessons,<br/>593 with transcript")]

    subgraph idx ["make index: the only step that calls OpenAI to prepare data"]
        direction LR
        label["<b>Label levels</b><br/>10 lessons per call, gpt-5.4-mini<br/>saved after each batch (atomic)"]
        levels[("<b>levels.json</b><br/>750 levels cached")]
        embed["<b>Chunk + embed</b><br/>3000-char chunks, step 1500: 2,535 chunks<br/>100 per call, text-embedding-3-small<br/>only new chunks are sent"]
        npz[("<b>chunk_embeddings.npz</b><br/>one vector per chunk,<br/>cached by text hash")]
    end

    app["<b>App and agent at runtime</b><br/>engine built in memory,<br/>no OpenAI call to label or embed"]

    topics --> fetch --> lessons
    lessons --> label --> levels
    lessons --> embed --> npz
    levels -.->|"reads, never writes"| app
    npz -.->|"reads, never writes"| app
    lessons -.->|"reads"| app

    classDef added stroke:#d97706,stroke-width:3px
    class label,levels,embed,npz,app added
```

- Labelling used to run inside the first search, one call per lesson. It now takes 80 calls instead of 750, in batches of 10, and saves safely after every batch.
- If the embeddings are missing, search returns a fixed "index not built" message to the agent instead of calling OpenAI in the middle of a question.
- Level labels come from `gpt-5.4-mini`, because it agreed with the existing levels 83% of the time on a sample. Nano agreed 71%.

| Step | Command | Where it lives |
|---|---|---|
| fetch | `make fetch` | `integrations/youtube_data.py` |
| label and embed | `make index` | `integrations/index.py`, `levels.py`, `embeddings.py` |
| safe file writes | `write_text_atomic` | `integrations/files.py` |

## 3. How the agent is measured

Scenarios run against the real agent, answers get labelled good or bad, and a judge is scored against those labels. Real questions from Logfire flow back in as new scenarios.

```mermaid
flowchart LR
    scen[("<b>scenarios.csv</b><br/>65 scenarios")]
    run["<b>run_scenarios</b><br/>agent on a temp<br/>copy of your data,<br/>tool check<br/>+ LLM judge"]
    res[("<b>results.csv</b><br/>answers, tools,<br/>cost, verdicts")]
    lab["<b>label_app</b><br/>good / bad,<br/>one click,<br/>+ failure type"]
    labels[("<b>labels.csv</b><br/>saved next to<br/>each results file")]
    judge["<b>run_judge</b><br/>judge vs labels:<br/>accuracy,<br/>precision, recall"]
    prompt["<b>Edit the<br/>judge prompt</b><br/>fix what the<br/>disagreements show"]
    logfire["<b>Logfire traces</b><br/>real sessions"]
    l2c["<b>logs_to_cases</b><br/>candidate scenarios<br/>you review"]

    scen --> run --> res --> lab --> labels --> judge
    judge -->|"disagreements"| prompt
    prompt -->|"re-run"| judge
    logfire --> l2c
    l2c -->|"reviewed,<br/>then added"| scen
```

Search is scored on its own, without the agent:

```mermaid
flowchart LR
    rc[("<b>retrieval_cases.csv</b><br/>31 questions:<br/>19 dev, 12 held-out test")]
    rr["<b>evals.retrieval</b><br/>5 search methods, k=5"]
    out["<b>hit rate, MRR,<br/>latency, text sent</b><br/>plus the misses"]
    pick["<b>Default method</b><br/>vector"]
    rc --> rr --> out --> pick
```

- On the full 65 scenarios the agent passes the tool check 63 times. The two misses (#14 and #33) look up history and then stop without acting.
- The judge prompt loop, v1 to v2, raised accuracy from 65% to 77% on 60 labels.
- The 60 labels so far were written by an AI assistant, not by the repo owner, so the judge numbers show agreement with it. Hand labels made with `make label` would replace them.
- The held-out test questions are only scored with `--test`, so tuning never sees them.

| Step | Command | Where it lives |
|---|---|---|
| run scenarios | `make eval` | `evals/run_scenarios.py` |
| label answers | `make label` | `evals/label_app.py` |
| score the judge | `make judge` | `evals/judge.py`, `run_judge.py` |
| score search | `make retrieval` | `evals/retrieval.py` |
| real questions to cases | `make logs-to-cases` | `evals/logs_to_cases.py` |
