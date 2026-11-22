.PHONY: help install demo demo-app index lint format test test-llm run app label eval judge retrieval logs-to-cases fetch docker-up docker-fetch docker-index

help:            ## list the targets
	@grep -E '^[a-z-]+:.*##' $(MAKEFILE_LIST) | sed 's/:.*##/ -/'

install:         ## install dependencies (including the Streamlit app group)
	uv sync --group app

demo:            ## chat with the bundled sample data: no fetch or index needed (still needs OPENAI_API_KEY)
	@touch data/sample/topics.txt
	LICK_DATA_DIR=data/sample uv run python -m lick_finder

demo-app:        ## the Streamlit chat on the bundled sample data
	@touch data/sample/topics.txt
	LICK_DATA_DIR=data/sample uv run --group app streamlit run streamlit_app/app.py

index:           ## label new lessons and embed new chunks (the only step that calls OpenAI to prepare data)
	uv run python -m lick_finder.integrations.index

lint:            ## ruff lint and format check (what CI runs)
	uv run ruff check .
	uv run ruff format --check .

format:          ## format the code with ruff
	uv run ruff format .

test:            ## free tests: no model calls, no network
	uv run pytest

test-llm:        ## also the tests that call a real model (costs a few cents)
	uv run pytest --llm

run:             ## terminal chat
	uv run python -m lick_finder

app:             ## Streamlit chat on http://localhost:8501
	uv run --group app streamlit run streamlit_app/app.py

fetch:           ## fetch new lesson topics from YouTube into data/lessons.json
	uv run python -m lick_finder.integrations.youtube_data

eval:            ## run all scenarios in evals/scenarios.csv with the LLM judge (costs money)
	uv run python -m evals.run_scenarios

retrieval:       ## score search alone (hit rate, MRR, latency) on the dev questions
	uv run python -m evals.retrieval

label:           ## open the good/bad labeling app
	uv run --group app streamlit run evals/label_app.py

judge:           ## score the judge against your labels
	uv run python -m evals.run_judge

logs-to-cases:   ## turn real Logfire questions into candidate scenarios
	uv run python -m evals.logs_to_cases

docker-up:       ## start the app in Docker on http://localhost:8501
	docker compose up --build

docker-fetch:    ## fetch lesson data inside Docker (writes to ./data)
	docker compose --profile fetch run --rm fetch

docker-index:    ## label and embed inside Docker (writes to ./data)
	docker compose --profile fetch run --rm index
