# Agentes BR 🤖

Sistema de agentes autônomos em português brasileiro para automação de tarefas com múltiplos LLMs.

## 🔍 Visão Geral

Este projeto implementa um sistema de agentes inteligentes capaz de:
*   Executar tarefas complexas usando diferentes modelos de linguagem (OpenRouter, Groq, Gemini).
*   Automatizar a interação com aplicações web usando Playwright.
*   Gerenciar memória contextual para tarefas longas.
*   Otimizar prompts e o uso de tokens para melhor custo-benefício.
*   Trabalhar totalmente em português 🇧🇷.

**Exemplo Principal:** O script `main.py` demonstra a automação do preenchimento de um formulário de orçamento na aplicação web [Sistema de Precificação](https://precificacao-sistema.onrender.com/) e o download do PDF resultante.

## ⚙️ Requisitos

*   Python 3.8+
*   Chaves de API para os LLMs desejados (OpenRouter, Groq, Google Gemini) configuradas no arquivo `.env`.
*   Dependências listadas em `requirements.txt`.

## 🚀 Instalação

1.  Clone o repositório:
    ```bash
    git clone <repo-url>
    cd agentes-br
    ```

2.  Crie um ambiente virtual (recomendado):
    ```bash
    python -m venv .venv
    source .venv/bin/activate  # Linux/macOS
    # OU
    # .venv\\Scripts\\activate  # Windows
    ```

3.  Instale as dependências:
    ```bash
    pip install -r requirements.txt
    ```

4.  Configure as variáveis de ambiente:
    ```bash
    # Crie um arquivo .env na raiz do projeto
    # Adicione suas chaves de API, por exemplo:
    # GOOGLE_API_KEY=SUA_CHAVE_GEMINI
    # GROQ_API_KEY=SUA_CHAVE_GROQ
    # OPENROUTER_API_KEY=SUA_CHAVE_OPENROUTER
    ```

5.  Instale os navegadores para o Playwright:
    ```bash
    playwright install chromium
    ```

## ✨ Características Principais

*   **Múltiplos LLMs:** Suporte para OpenRouter, Groq e Gemini com fallbacks automáticos (`core/llm_manager.py`).
*   **Otimização de Tokens/Prompts:** Cálculo, truncamento e otimização de prompts para limites de contexto (`core/prompt_utils.py`).
*   **Memória Contextual:** Armazenamento e sumarização de histórico com LLM (`core/memory.py`).
*   **Ferramentas Web:** Navegação (`tools/web_navigator.py`) e Interação (`tools/web_interactor.py`) com Playwright.
*   **Orquestração:** Definição de Agentes, Tarefas e execução em sequência com a `Crew` (`core/models.py`).

## 💻 Utilização

O ponto de entrada principal é `main.py`. Ele está configurado para automatizar a geração de orçamento na aplicação web de precificação.

Execute o script:

```bash
python main.py
```

Por padrão, ele roda em modo *headless* (sem abrir a janela do navegador). Para ver o navegador em ação, use:

```bash
python main.py --no-headless
```

### Saída

O script executará as tarefas definidas e, se bem-sucedido, salvará o arquivo PDF do orçamento gerado na pasta `output/`. Os logs detalhados da execução são exibidos no terminal.

## 📁 Estrutura do Projeto

```
agentes-br/
├── core/             # Núcleo do sistema de agentes, LLM, memória, prompts
├── tools/            # Ferramentas de interação web (Playwright)
├── external_site/    # Código-fonte da aplicação web de precificação (para referência)
│   └── Precificacao-Sistema/
├── output/           # Pasta onde os PDFs gerados são salvos
├── tests/            # Testes unitários e de integração
├── .env              # Arquivo para chaves de API (NÃO versionar)
├── main.py           # Ponto de entrada principal (Exemplo de automação)
├── requirements.txt  # Dependências do projeto
└── README.md         # Este arquivo
```

## 🧪 Testes

Execute os testes com:

```bash
pytest
```

## 🤝 Contribuição

Contribuições são bem-vindas! Sinta-se à vontade para abrir issues ou pull requests.

## 📄 Licença

MIT