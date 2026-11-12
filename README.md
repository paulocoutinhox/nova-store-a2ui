# Nova Store A2UI — Conversational Commerce

Uma loja apresentada **inteiramente como conversa**. O cliente fala com a NOVA, recebe recomendações feitas por um agente **PydanticAI + OpenAI GPT-5**, vê produtos e formulários **A2UI 1.0 dentro das mensagens** e finaliza pedidos no chat. Não há menu de e-commerce, landing page ou dashboard.

Interface reconstruída com **React 19 + Tailwind CSS 4 + daisyUI 5**. Backend **FastAPI + SQLite**. Catálogo de 12 produtos e respectivas imagens WebP incluídos no pacote. **O pagamento é uma simulação local — nenhuma cobrança, cartão real ou integração bancária.**

## Executar

Requisitos: macOS ou Linux, Python 3.12+, Node.js 20.19+ e GNU Make.

```sh
make configure
```

Abra `backend/.env` e informe uma chave válida:

```dotenv
OPENAI_API_KEY=sk-sua-chave-real
AI_MODEL=gpt-5
AI_ENABLED=true
```

Depois rode **um único comando**, na raiz:

```sh
make
```

Acesse http://localhost:5173. O Makefile instala as dependências Python e npm, abre o frontend na porta 5173 e o backend na porta 8000; `Ctrl+C` encerra ambos. Se a chave estiver ausente, `make` para imediatamente com uma orientação clara no terminal. Não há fallback por palavras-chave fingindo ser IA. Para atender às mensagens é preciso ter crédito e acesso ao modelo informado.

O arquivo `.env` é privado e não é enviado ao frontend. Não coloque a chave em variáveis `VITE_*`.

## Fluxo

1. Escreva algo natural: "Quero um fone com ANC até R$ 700 para viajar".
2. O PydanticAI utiliza `find_products` contra o SQLite, responde em português e anexa uma superfície A2UI com fotos e botões.
3. Continue a conversa: "Qual é mais confortável?", "Mostre mais detalhes", "Coloque esse no carrinho" ou clique nos cards.
4. Os **cliques são eventos A2UI estruturados**, não mensagens de texto do usuário. O backend executa a ação validada e pede ao modelo uma confirmação natural sobre o resultado, sem permitir que o clique execute a mutação novamente.
5. Veja o carrinho, altere quantidades, preencha o formulário de entrega, escolha Pix/cartão/boleto no simulador e confirme o pedido.
6. O SQLite guarda conversa, carrinho, pedidos, estoque reservado, pagamentos de teste e histórico do modelo.

Para testar desconto: cupom `BEMVINDO10`. Para testar o pagamento, use dados fictícios de entrega; não informe número de cartão nem CVV. A tela de pagamento deixa claro que se trata de uma simulação.

## Comandos

| Comando | Ação |
| --- | --- |
| `make` / `make dev` | Verifica chave, instala dependências ausentes e inicia frontend/backend |
| `make setup` | Cria `.env` e instala dependências sem iniciar |
| `make test` | Executa testes de backend, SQLite, ações e protocolo A2UI |
| `make test-ai` | Faz uma chamada **real e cobrada** à OpenAI e verifica o uso de ferramenta |
| `make build` | Compila a aplicação React |
| `make check` | Testes + build de produção |
| `make start` | Build e aplicação servida na porta 8000 |
| `make reset-db` | Apaga conversas/pedidos e restaura o catálogo |
| `make clean` | Remove temporários; preserva dados e dependências |
| `make doctor` | Mostra versões instaladas |

## Estrutura

```text
nova-chat-profissional/
├── Makefile
├── README.md
├── AGENTS.md
├── backend/
│   ├── .env.example
│   ├── app/
│   │   ├── ai.py                  # agente GPT-5 e ferramentas de e-commerce
│   │   ├── db.py                  # catálogo, busca, transações, conversas
│   │   ├── main.py                # API e validação de ações A2UI
│   │   └── ui.py                  # superfícies A2UI oficiais, dados locais
│   ├── assets/                    # 12 imagens de produtos
│   ├── data/commerce.sqlite3     # banco local populado
│   └── tests/
├── frontend/
│   ├── package.json
│   ├── src/
│   │   ├── app.jsx               # conversa + API + histórico
│   │   ├── components/           # cabeçalho, bolhas, composer, widgets
│   │   ├── lib/a2ui.js           # parser e eventos A2UI 1.0
│   │   └── styles.css            # Tailwind 4, daisyUI 5 e tokens
│   └── tests/
└── scripts/
```

### Sobre o renderer A2UI

O backend emite **envelopes A2UI 1.0 (`version: "1.0"`)** com componentes do Basic Catalog oficial. Para impedir os problemas de CSS, legibilidade e incompatibilidade entre versões npm anteriores, **o frontend implementa um renderer React de escopo limitado**, com os componentes que o projeto realmente usa: `Text`, `Image`, `Row`, `Column`, `Card`, `Button`, `TextField` e `ChoicePicker`. Campos utilizam `@path`, e cliques devolvem ações A2UI completas (`sourceComponentId`, `surfaceId`, `timestamp`, `context`).

Esse renderer **não pretende suportar todo o catálogo A2UI** nem substitui o protocolo. A integração é uma implementação React específica do Basic Catalog usado nesta aplicação, não uma instalação do renderer genérico `@a2ui/react`. A camada de apresentação utiliza daisyUI e componentes próprios para manter contraste, layout e identidade visual consistentes. A especificação de referência é https://a2ui.org/specification/v1.0-a2ui/.

### Regras de confiabilidade

- Apenas o backend escreve preços, estoque, pedidos e pagamentos no SQLite.
- `Agent.run()` do PydanticAI processa toda **mensagem livre**. Não há roteador por palavras-chave nem respostas de IA simuladas.
- Cliques usam ações A2UI estruturadas, verificadas contra os botões emitidos pelo servidor. Não surgem balões de usuário fabricados.
- Cada ação recebida usa um identificador implícito de gesto para evitar duplicação no reenvio.
- O modelo pode gerar a explicação natural de uma ação concluída, mas **não tem ferramentas de mutação** nesse segundo passo. Caso a IA fique indisponível após a mutação, é exibida apenas a confirmação factual do backend, sem fingir uma resposta da IA.
- Pedidos reservam estoque de modo transacional; pagamentos simulados são idempotentes; cancelamentos pendentes devolvem o estoque.
- O front-end não revela modelo, APIs, versões, infraestrutura ou mensagens técnicas de desenvolvimento aos clientes. Informações do simulador aparecem apenas onde são relevantes ao pagamento.

## Validação

Os testes automatizados cobrem o banco, compra simulada, recuperação de conversa, ferramentas do PydanticAI com modelo de teste, evento A2UI sem balão falso, integridade dos argumentos, idempotência de cliques e vínculo de formulários. **Uma chamada real à OpenAI não faz parte da suíte padrão**; execute `make test-ai` com sua própria chave.

O build React depende dos pacotes do npm. Se o ambiente de geração estiver sem acesso ao registro npm, o código pode ter validação sintática sem que a compilação real tenha sido executada. `make check` é a validação final recomendada na sua máquina.
