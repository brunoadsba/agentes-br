# Projeto Agentes Web: Comparativo LLM vs. Execução Direta

Este projeto demonstra e compara duas abordagens para automatizar interações web complexas usando um conceito de "agentes":

1.  **Execução Direta (Sem LLM):** Agentes seguem uma sequência de tarefas pré-definidas com lógica explícita.
2.  **Execução via LLM:** Agentes utilizam um Modelo de Linguagem Grande (LLM) para interpretar descrições de tarefas em linguagem natural e decidir quais ferramentas e parâmetros usar.

O objetivo principal é ilustrar as diferenças, vantagens e desvantagens de cada abordagem no contexto da automação do preenchimento de um formulário de orçamento online e o download do PDF resultante.

## Visão Geral da Tarefa Automatizada

O fluxo automatizado visa interagir com o site [Sistema de Precificação](https://precificacao-sistema.onrender.com/) para:

1.  Navegar até o site.
2.  Preencher informações do cliente.
3.  Selecionar e configurar um serviço específico (ex: Elaboração e acompanhamento do PGR).
4.  Navegar pela página de resumo.
5.  Confirmar e gerar o orçamento.
6.  Baixar o arquivo PDF do orçamento gerado.

## Estrutura do Projeto

```
agentes-br/
├── core/             # Modelos principais (Agent, Task, Crew, Memory)
├── tools/            # Ferramentas de interação (WebNavigator, WebInteractor)
├── config/           # Configuração de modelos LLM (Setup)
├── main.py           # Ponto de entrada principal para execução
├── requirements.txt  # Dependências Python
├── .env              # Arquivo para chaves de API (NÃO versionar!)
└── README.md         # Este arquivo
```

## Branches Principais

*   `main` (ou `master`): Pode conter a versão mais estável ou inicial.
*   `feature/web-interaction`: Implementação usando **LLM** para planejamento de tarefas.
*   `feature/direct-execution`: Implementação usando **execução direta** (sem LLM) com lógica explícita.
*   `feature/pdf-generation`: Evolução da `direct-execution` que implementou o download do PDF.
*   `feature/generalization`: Rascunho para explorar generalização (pausado).

**Nota:** Para a comparação direta, os branches relevantes são `feature/web-interaction` (LLM) e `feature/pdf-generation` (Direta).

## Configuração

1.  **Clone o Repositório:**
    ```bash
    git clone <URL_DO_REPOSITORIO>
    cd agentes-br
    ```
2.  **Crie um Ambiente Virtual (Recomendado):**
    ```bash
    python -m venv .venv
    source .venv/bin/activate  # Linux/macOS
    # .\.venv\Scripts\activate  # Windows
    ```
3.  **Instale as Dependências:**
    ```bash
    pip install -r requirements.txt
    playwright install chromium # Instala o navegador necessário
    ```
4.  **Configure as Chaves de API (Necessário para a versão LLM):**
    *   Renomeie (ou copie) `.env.example` para `.env`.
    *   Edite o arquivo `.env` e adicione suas chaves de API para os modelos LLM que deseja usar (ex: Gemini, Groq).
      ```dotenv
      GEMINI_API_KEY=SUA_CHAVE_AQUI
      GROQ_API_KEY=SUA_CHAVE_AQUI
      # DEEPSEEK_API_KEY=...
      # OPENAI_API_KEY=...
      ```

## Execução

Certifique-se de estar no branch desejado (`git checkout <nome-do-branch>`).

### Execução Direta (Sem LLM)

1.  Vá para o branch `feature/pdf-generation`:
    ```bash
    git checkout feature/pdf-generation
    ```
2.  Execute o script:
    ```bash
    python main.py --no-headless # Executa com navegador visível
    # ou
    # python main.py # Executa em modo headless (sem interface gráfica)
    ```
    O PDF do orçamento (`orcamento_*.pdf`) será salvo no diretório `agentes-br`.

### Execução via LLM

1.  Vá para o branch `feature/web-interaction`:
    ```bash
    git checkout feature/web-interaction
    ```
2.  **Configure o Modelo LLM:** Edite `config/setup.py` para garantir que o modelo desejado (ex: `GeminiModel`, `GroqModel`) esteja sendo instanciado e retornado pela função `setup_llm()`.
3.  **Configure as Tarefas:** Edite `main.py` neste branch para definir a sequência de tarefas desejada usando descrições em linguagem natural.
4.  **Execute o script:**
    ```bash
    python main.py --no-headless
    # ou
    # python main.py
    ```
    Acompanhe os logs para ver as decisões do LLM e a execução das ferramentas. A estabilidade pode depender dos limites de taxa da API do LLM.

## Comparativo

A execução dos dois branches lado a lado permite comparar:

*   **Código:** Complexidade da lógica direta vs. abstração via LLM.
*   **Configuração:** Necessidade de chaves de API e configuração de modelos na versão LLM.
*   **Execução:** Velocidade, determinismo, robustez e potenciais problemas (ex: rate limiting, alucinações do LLM).
*   **Flexibilidade:** Facilidade teórica de adaptar a versão LLM a novas tarefas vs. necessidade de codificação explícita na versão direta.

## Contribuindo

Contribuições são bem-vindas! Sinta-se à vontade para abrir issues ou pull requests. 