<p align="center">
  <a href="https://github.com/paulocoutinhox/nova-store-a2ui">
    <picture>
      <source media="(prefers-color-scheme: dark)" srcset="extras/images/logo-dark.svg">
      <img width="440" src="extras/images/logo.svg" alt="Nova Store">
    </picture>
  </a>
</p>

<p align="center">
  <a href="https://github.com/paulocoutinhox/nova-store-a2ui/actions/workflows/ci.yml"><img src="https://github.com/paulocoutinhox/nova-store-a2ui/actions/workflows/ci.yml/badge.svg" alt="CI"></a>
  <a href="https://react.dev/"><img src="https://img.shields.io/badge/React-19-149ECA" alt="React 19"></a>
  <a href="https://a2ui.org/"><img src="https://img.shields.io/badge/A2UI-1.0-2563EB" alt="A2UI 1.0"></a>
  <a href="https://github.com/pydantic/pydantic-ai"><img src="https://img.shields.io/badge/PydanticAI-agent-E92063" alt="PydanticAI"></a>
</p>

<p align="center">
A conversational shopping experience powered by a real AI agent, structured A2UI interfaces, and a local demonstration store.
</p>

<br>

## 🚀 Project

**Nova Store A2UI** is a chat-first e-commerce prototype. Customers discover and compare products, build a cart, enter shipping details, and complete a simulated payment without leaving the chat. There is no separate storefront, dashboard, or product-navigation website.

Every free-text message is sent to **PydanticAI** using a configured OpenAI model. The agent calls tools for product discovery, recommendations, and cart operations. The backend builds **A2UI 1.0** surfaces for products, actions, checkout forms, and orders. A focused React renderer presents the supported Basic Catalog components inside chat messages.

The project includes 12 products with local WebP images and a SQLite database. **Pix, card, and boleto payments are simulated. No real charges occur.**

## ✨ Features

- 💬 **Conversational shopping:** natural-language product discovery, recommendations, and saved history.
- 🛍️ **Interactive A2UI:** product cards, details, comparisons, cart controls, and forms.
- 🧠 **Real agent:** typed messages go to PydanticAI; unavailable model calls are not replaced with canned answers.
- 🛒 **Cart and inventory:** quantities, discounts, shipping, and totals are calculated by the server.
- 💳 **Demo checkout:** simulated payment flows and persistent order history.
- 🗃️ **SQLite:** stores products, carts, sessions, orders, and conversation history.
- 🧪 **CI:** backend integration tests, A2UI protocol checks, and a React production build.

## ⚡ Quick start

Requires macOS or Linux, Python 3.12+, Node.js 20.19+, npm, and GNU Make.

```bash
git clone https://github.com/paulocoutinhox/nova-store-a2ui.git
cd nova-store-a2ui
make configure
```

Edit `backend/.env` and provide an OpenAI API key:

```dotenv
OPENAI_API_KEY=your-openai-api-key
AI_MODEL=gpt-5
AI_ENABLED=true
```

Start both services from the repository root:

```bash
make
```

Open **http://localhost:5173**. The frontend runs on port 5173 and FastAPI runs on port 8000. Stop both with Ctrl+C. API credentials stay server-side; never place the key in `VITE_*` variables.

## 🧭 How it works

1. Ask for a product naturally, for example: "Find noise-canceling headphones under $200."
2. PydanticAI uses database-backed tools and generates a concise answer with an A2UI product surface when useful.
3. Continue with comparisons, product details, or shopping-cart actions. A2UI clicks are structured events—not fabricated chat messages.
4. Review your cart, provide delivery details, choose a simulated payment method, and review the resulting order.
5. SQLite persists the catalog, sessions, orders, and AI history.

Prices in this sample catalog are denominated in Brazilian reais (BRL). The coupon `BEMVINDO10` is available for testing. Do not enter real payment-card details, financial credentials, or sensitive customer information.

## 🛠️ Commands

| Command | Purpose |
| --- | --- |
| `make` or `make dev` | Install missing dependencies and launch frontend and backend |
| `make configure` | Create a local backend environment file if missing |
| `make setup` | Initialize the environment and install dependencies |
| `make test` | Run backend and A2UI tests |
| `make test-ai` | Call OpenAI through PydanticAI (requires access and API credits) |
| `make build` | Build the React frontend for production |
| `make check` | Run tests and the production build |
| `make start` | Build and serve the application on port 8000 |
| `make reset-db` | **Delete all local demo sessions, orders, and carts** and restore the catalog |
| `make clean` | Remove temporary build/cache files while preserving stored data |

## 🏗️ Architecture

```text
.
├── .github/
│   ├── FUNDING.yml
│   └── workflows/ci.yml
├── backend/
│   ├── app/           # API, PydanticAI tools, A2UI surfaces, SQLite
│   ├── assets/        # Local product images
│   └── tests/         # Database and API integration tests
├── extras/images/     # Light and dark project logos
├── frontend/
│   ├── src/           # React chat and focused A2UI renderer
│   └── tests/         # A2UI protocol tests
├── scripts/           # Local setup, validation, and development
├── AGENTS.md
├── Makefile
└── README.md
```

### A2UI rendering

The backend emits A2UI 1.0 messages using `version: "1.0"` and components from the official Basic Catalog. The frontend implements a **focused React renderer** for the components this application uses: `Text`, `Image`, `Row`, `Column`, `Card`, `Button`, `TextField`, and `ChoicePicker`. It is not the generic `@a2ui/react` package and does not claim complete protocol coverage.

The backend owns authoritative prices, inventory, orders, and simulated payments. Interactive events are validated against server-issued controls and do not create fake user messages.

## 🧪 Testing and CI

```bash
make check
```

The GitHub Actions [CI workflow](.github/workflows/ci.yml) runs tests and the frontend production build on pushes and pull requests. It does not use paid OpenAI requests. For an optional live model integration check, use `make test-ai` locally with a configured API key.

A passing CI result does not imply production payment security. This is a local demonstration that requires authentication, production-grade session security, and a real payment provider before handling customer transactions.

## 🤝 Contributing

Read [AGENTS.md](AGENTS.md) for project conventions. Open an issue for a reproducible bug or a focused feature proposal, and submit changes through a pull request with relevant tests.

## ❤️ Support

If this project is useful, you can support its maintenance through the [GitHub Sponsors](https://github.com/sponsors/paulocoutinhox) or [Ko-fi](https://ko-fi.com/paulocoutinho) links configured in [.github/FUNDING.yml](.github/FUNDING.yml).
