import asyncio
import os
import json
from dotenv import load_dotenv

# Módulos Principais (com GeminiModel)
from core.models import Agent, Task, Crew, ContextualMemory
# Import LLMManager
from core.llm_manager import LLMManager

# Ferramentas Web
from tools.web_navigator import WebNavigatorTool
from tools.web_interactor import WebInteractorTool

async def main(headless_mode: bool = True):
    load_dotenv()
    print(f"Iniciando o processo de agentes com LLM Manager... (Headless: {headless_mode})")

    # 1. Inicializar Componentes
    memory = ContextualMemory()
    try:
        # Initialize LLMManager
        llm_manager = LLMManager()
        if not llm_manager.clients:
            print("Erro: Nenhum cliente LLM foi inicializado com sucesso. Verifique as chaves de API no .env.")
            return
    except Exception as e: # Catch potential errors during LLMManager initialization
        print(f"Erro ao inicializar LLMManager: {e}")
        return

    # 2. Definir Ferramentas
    web_navigator = WebNavigatorTool()
    web_interactor = WebInteractorTool()

    # 3. Definir Agente
    executor_web = Agent(
        name="ExecutorWeb", 
        role=(
            "Responsável por interagir com páginas web. Pode navegar (WebNavigatorTool) "
            "e interagir (WebInteractorTool - fill, click, select_option). "
            "Planeje sua ação e forneça parâmetros JSON para a ferramenta."
        ), 
        llm_manager=llm_manager, # Pass LLMManager instance
        tools=[web_navigator, web_interactor], 
        memory=memory
    )

    # 4. Definir Seletores e Dados
    selectors = {
        "empresa": "#empresa",
        "email": "#cliente_email",
        "telefone": "#telefone",
        "add_servico_btn": "#adicionarServico",
        "servico_1_nome": "#servico-1-nome",
        "servico_1_regiao": "#regiao-1", # Exemplo
        "servico_1_variavel": "#variavel-1", # Exemplo
        "gerar_orcamento_btn": 'button:has-text("Gerar Orçamento")'
    }
    dados_cliente = {
        "empresa": "Empresa Teste Gemini",
        "email": "contato.gemini@testeia.com",
        "telefone": "71955554444"
    }
    dados_servico_1 = {
        "nome": "Coleta para Avaliação Ambiental",
        "regiao": "Feira de Santana", 
        "variavel": "Pacote (1 a 4 avaliações)" 
    }
    target_url = "https://precificacao-sistema.onrender.com/"

    # 5. Definir Tarefas (com description)
    tarefa_navegar = Task(
        description=f"Navegue até a página inicial em {target_url}", 
        agent=executor_web
    )
    tarefa_fill_empresa = Task(
        description=f"Preencha o campo Empresa ('{selectors['empresa']}') com '{dados_cliente['empresa']}'.", 
        agent=executor_web,
        dependencies=[tarefa_navegar]
    )
    tarefa_fill_email = Task(
        description=f"Preencha o campo Email ('{selectors['email']}') com '{dados_cliente['email']}'.",
        agent=executor_web,
        dependencies=[tarefa_fill_empresa]
    )
    tarefa_fill_telefone = Task(
        description=f"Preencha o campo Telefone ('{selectors['telefone']}') com '{dados_cliente['telefone']}'.",
        agent=executor_web,
        dependencies=[tarefa_fill_email]
    )
    tarefa_click_add = Task(
        description=f"Clique no botão Adicionar Serviço ('{selectors['add_servico_btn']}').",
        agent=executor_web,
        dependencies=[tarefa_fill_telefone]
    )
    tarefa_select_servico1 = Task(
        description=f"Selecione o serviço '{dados_servico_1['nome']}' no dropdown ('{selectors['servico_1_nome']}').",
        agent=executor_web,
        dependencies=[tarefa_click_add]
    )
    # Adicione mais tarefas aqui se necessário (ex: selecionar região/variável, clicar gerar)

    # 6. Criar e Executar a Crew
    lista_tarefas = [
        tarefa_navegar,
        tarefa_fill_empresa,
        tarefa_fill_email,
        tarefa_fill_telefone,
        tarefa_click_add,
        tarefa_select_servico1,
        # Adicionar tarefas futuras aqui
    ]
    equipe = Crew(agents=[executor_web], tasks=lista_tarefas)
    
    print("\nIniciando a execução da equipe com LLM Manager...")
    resultados = await equipe.run(headless=headless_mode) 
    print("\nExecução da equipe concluída.")

    # 7. Processar Resultados
    print("\nResultados das tarefas:")
    if resultados:
        for tarefa in lista_tarefas:
            # Acessa resultado usando a description como chave
            resultado = resultados.get(tarefa.description, "Error: Resultado não encontrado para esta descrição")
            print(f"- {tarefa.description}:")
            print(f"  Resultado: {resultado}") 
    else:
        print("Nenhum resultado retornado pela equipe ou ocorreu um erro fatal.")

# Bloco __main__ com argparse (igual)
if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--no-headless', action='store_false', dest='headless', help="Executa o navegador em modo visível.")
    parser.set_defaults(headless=True)
    args = parser.parse_args()
    asyncio.run(main(headless_mode=args.headless))
