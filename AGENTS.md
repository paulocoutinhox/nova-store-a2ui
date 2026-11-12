# NOVA Conversational Store

This is a single-conversation React shopping application. Keep all visible customer journeys inside chat messages. Do not add dashboards, model names, build/runtime details, engineering labels, or permanent demo banners to the customer interface.

## Architecture

- `frontend/src/app.jsx` owns session lifecycle and API transport. The app never receives the OpenAI key.
- `frontend/src/components/` contains one component per file; widgets are rendered from A2UI messages.
- `frontend/src/lib/a2ui.js` interprets the supported subset of A2UI 1.0 wire messages and creates structured action events. Do not turn button events into user chat text.
- `frontend/src/styles.css` is the Tailwind CSS 4 entrypoint and daisyUI 5 theme. Respect semantic contrast, focus states, mobile layouts, and reduced motion. Avoid global selectors overriding widget colors.
- `backend/app/ai.py` runs PydanticAI with the real configured model for every free-text message. Tools are authoritative for products and state. After UI actions, a separate read-only model call may generate natural follow-up, but must not repeat mutations.
- `backend/app/main.py` validates incoming session and A2UI action data, source component, gesture ID, and request boundaries.
- `backend/app/db.py` owns atomic stock, order/payment persistence, and conversation history.
- `backend/app/ui.py` produces version `1.0` Basic Catalog envelopes and no HTML.

## Invariants

1. Never create fake user turns when someone clicks a button. All visible user chat text must be explicitly typed or selected as a prompt.
2. Never substitute keyword routes or canned assistant messages for a failed model request.
3. Prices, stock, freight, order totals, and payment status must come from SQLite. Payment is only simulated.
4. Validate server-side button source and static arguments before any mutation. Do not repeat mutations when acknowledging them through the model.
5. Do not expose internal model/provider information or secrets to the customer UI.
6. Keep the same UI design system: neutral surfaces, dark text, blue primary actions, clear disabled/focus states.

## Commands

`make configure`, edit `backend/.env` with `OPENAI_API_KEY`, then `make`.
`make test` runs local tests. `make check` runs tests and a production frontend build. `make test-ai` makes a real paid provider call. `make reset-db` is destructive. Do not claim live-model or browser validations without running them.
