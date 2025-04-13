# Projeto Agentes Autônomos com LLMs

Este projeto demonstra a criação e orquestração de agentes autônomos baseados em LLMs (Large Language Models) para realizar tarefas complexas, focando na automação de interações web utilizando a biblioteca Playwright. O sistema é projetado para ser extensível, permitindo a integração de diferentes modelos de LLM e ferramentas customizadas.

## ✨ Funcionalidades Principais

*   **Gerenciamento Flexível de LLMs:** Suporte integrado para múltiplos provedores de LLM através de um `LLMManager` (atualmente Gemini e OpenRouter).
*   **Arquitetura de Agentes:** Modelo baseado em Agentes, Tarefas e Equipes (Crew) para organizar e executar fluxos de trabalho.
*   **Interação Web Robusta:** Ferramentas para navegação (`WebNavigatorTool`) e interação (`WebInteractorTool`) com páginas web (preenchimento de formulários, cliques, seleção de opções) usando Playwright.
*   **Execução Orquestrada:** Gerenciamento da execução sequencial de tarefas com tratamento de dependências entre elas.
*   **Memória Contextual:** Implementação básica de memória de curto prazo individual e global para os agentes.
*   **Configuração via `.env`:** Gerenciamento seguro de chaves de API e outras configurações.


## 🛠️ Tecnologias Utilizadas

*   Python 3.x
*   Playwright (para automação de navegador)
*   Google Generative AI (API do Gemini)
*   OpenRouter (API para múltiplos LLMs)
*   Python-Dotenv (para carregar variáveis de ambiente)

## 📂 Estrutura do Projeto

```
.
├── core/               # Núcleo da lógica de agentes, tarefas, LLMs
│   ├── __init__.py
│   ├── llm_manager.py  # Gerenciador de clientes LLM
│   └── models.py       # Definições de Agent, Task, Crew, ContextualMemory, BaseTool
├── tools/              # Ferramentas reutilizáveis para os agentes
│   ├── __init__.py
│   ├── web_interactor.py # Ferramenta para interagir com elementos web
│   └── web_navigator.py  # Ferramenta para navegar em páginas web
├── tests/              # Testes unitários ou de integração
│   └── test_llm_clients.py # Testes para os clientes LLM configurados
├── .env                # Arquivo para armazenar chaves de API (NÃO versionado)
├── .gitignore          # Arquivos e diretórios ignorados pelo Git
├── main.py             # Ponto de entrada principal da aplicação
├── README.md           # Este arquivo
└── requirements.txt    # Dependências do projeto Python
```

## 🚀 Instalação

1.  **Clone o repositório:**
    ```bash
    git clone <url-do-seu-repositorio>
    cd <nome-do-diretorio>
    ```

2.  **Crie e ative um ambiente virtual:**
    ```bash
    python -m venv .venv
    # Linux/macOS
    source .venv/bin/activate
    # Windows (cmd/powershell)
    .venv\Scripts\activate
    ```

3.  **Instale as dependências:**
    ```bash
    pip install -r requirements.txt
    ```

4.  **Instale os navegadores do Playwright:** (O Chromium é usado por padrão no código)
    ```bash
    playwright install --with-deps chromium
    ```

## ⚙️ Configuração

1.  **Crie o arquivo `.env`:**
    Copie ou renomeie `.env.example` (se existir) ou crie um novo arquivo chamado `.env` na raiz do projeto.

2.  **Adicione suas chaves de API:**
    Abra o arquivo `.env` e adicione as chaves necessárias para os LLMs que você pretende usar:
    ```dotenv
    # Chave para a API do Google Gemini
    GEMINI_API_KEY=SUA_CHAVE_GEMINI_AQUI

    # Chave para a API do OpenRouter (usada para Groq e outros modelos)
    OPENROUTER_API_KEY=SUA_CHAVE_OPENROUTER_AQUI

    # Chave específica para o Grok via OpenRouter (opcional, se usar o teste específico)
    GROK_API_KEY=SUA_CHAVE_GROK_OU_OPENROUTER_AQUI 
    ```
    *Substitua `SUA_CHAVE_..._AQUI` pelas suas chaves reais.*

## ▶️ Uso

### Executando o Exemplo Principal

O arquivo `main.py` contém um exemplo que demonstra a automação do preenchimento de um formulário no site `https://precificacao-sistema.onrender.com/`.

*   **Para executar em modo headless (sem interface gráfica):**
    ```bash
    python main.py
    ```

*   **Para executar com o navegador visível:**
    ```bash
    python main.py --no-headless
    ```

### Executando os Testes de LLM

O arquivo `tests/test_llm_clients.py` verifica a comunicação com os LLMs configurados (atualmente Grok e Optimus Alpha via OpenRouter).

```bash
python tests/test_llm_clients.py
```
*(Certifique-se de que as chaves de API correspondentes estejam no seu arquivo `.env`)*

## 📝 Exemplo de Fluxo (`main.py`)

1.  O `LLMManager` é inicializado, carregando os clientes LLM configurados via `.env`.
2.  Um agente (`ExecutorWeb`) é definido com o papel de interagir com a web, utilizando o `LLMManager` e as ferramentas `WebNavigatorTool` e `WebInteractorTool`.
3.  Uma série de tarefas é definida:
    *   Navegar para a URL alvo.
    *   Preencher os campos do formulário (Empresa, Email, Telefone) usando seletores CSS.
    *   Clicar no botão "Adicionar Serviço".
    *   Selecionar um serviço específico em um dropdown.
    *   *(Tarefas futuras poderiam incluir selecionar outras opções e submeter o formulário)*
4.  Uma `Crew` é criada com o agente e as tarefas.
5.  A `Crew` executa as tarefas sequencialmente, usando o Playwright para controlar o navegador. O agente usa o LLM para decidir qual ação tomar (navegar, preencher, clicar, selecionar) e extrair/formatar os parâmetros para as ferramentas.
6.  Os resultados de cada tarefa são impressos no final.

## 🤝 Contribuição

Contribuições são bem-vindas! Sinta-se à vontade para abrir issues ou pull requests.

## 📜 Licença

[Defina a licença do seu projeto aqui, por exemplo: MIT License] 