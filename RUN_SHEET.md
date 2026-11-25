# Run sheet: same question, different data (30 min)

**Model:** Anthropic Claude / `claude-haiku-5-5` · **Sign in:** `demo_presenter` · **App:** http://localhost:4200

## Day before, and again 15 minutes before
- [ ] Start: `colima start`, then `docker compose --profile ollama up -d`. Open the app and sign in. **Backend, Database, pgvector** chips are green.
- [ ] Internet works (have a hotspot ready). Check the Anthropic credit balance.
- [ ] **Day before:** rehearse all of Demo Mode once.
- [ ] **15 minutes before:** one short AI Assistant question. Open Demo Mode and check the 3 saved runs. Keep `demo_backups/` open in another window. Close `.env` and anything showing keys.

## Say first
> "All data is synthetic and the policies are fictional. This is not for clinical use. The model receives our simulated figures and policy excerpts over the internet."

## Live demo: Demo Mode
**Reset and Replay deletes the saved runs.** Press it only when the backup files are there and you are ready to run live. New runs are not added to those files. Then choose the provider and model, and read the fixed question aloud once.

| Click | Expect | While it runs / what to say | Then point at |
|---|---|---|---|
| **Load Normal and Ask** | GREEN · 12 waiting · 15 min · 8 beds | "New records are being written to the database. The agent then reads them with tools." | Tools run, policies found, citations. "Metrics did not change" is normal: reset already loaded Normal. |
| **Load Surge and Ask** | **RED** · 38 · 75 min · 1 bed | **"Same words, new data."** | Data version, changed rows, recommended actions. |
| **Load Recovery and Ask** | GREEN · 9 · 18 min · 10 beds | "Will the answer come back down?" | All three columns side by side. |

Each step took about 20 s in the one rehearsal. Do not read whole answers: show the metrics table, the level and the actions.
The application calculates the level from the policy thresholds; the model is told to report it. Say so.

## Teaching point
> "A verified citation means the app retrieved that page. It does not prove the page supports the sentence, or that the conclusion is sound."

In rehearsal one answer guessed that RED "may have persisted for some time", though it showed no duration. Wording changes each run, so look for statements the data does not support and ask the audience to find one.

## If there is time (load Surge first in Scenario Simulator)
- **Agent Execution:** "Is the department at GREEN, AMBER or RED, and why?" Show each tool call and result.
- **AI Assistant:** "When can the department step down from RED?" Open the retrieved excerpts.
- These screens were rehearsed on Recovery data, not Surge. Try both on Surge the day before.

## Avoid
- **Temperature:** this model accepts only one value, so moving the slider shows nothing.
- **Comparison accuracy %:** it depends on wording. If you show Comparison, talk about the identical prompt and the answers.
- Claims that the model chooses the level, gives clinical advice, or is always right.

## If something fails
| Problem | Do this |
|---|---|
| One step errors or is slow | Read the message, then click that step once more. Each success adds a run column. |
| No internet or provider down | **Do not reset.** Show the saved runs in Demo Mode and say they are earlier runs. If they are gone, open `demo_backups/haiku-…-2026-11-25.md`. |
| Another model is needed | `gpt-6-luna` passed other screens but **not Demo Mode**. Ollama is too slow to run live (6–7 min per step). |
| App not loading | `docker compose ps`, then `docker compose --profile ollama up -d`. |
| Changed `.env` | `docker compose up -d --force-recreate backend` |
| Cannot sign in | After repeated wrong passwords, wait (15 s up to 5 min). |

**Close with:** "What would you need to check before trusting an answer like this?"
