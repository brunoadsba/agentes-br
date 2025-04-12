import asyncio
import os

# Configuração inicial (carrega .env e configura Gemini API)
from config.setup import configure_gemini

# Modelos principais do framework de agentes
from core.models import Agent, Task, Crew, GeminiModel, ContextualMemory

# Importa a ferramenta de navegação web
from tools.web_navigator import WebNavigatorTool

async def main():
    """Função principal para configurar e executar a equipe de agentes."""
    print("Iniciando o processo de agentes...")

    # 1. Configurar a API do Gemini
    if not configure_gemini():
        print("Falha ao configurar a API do Gemini. Verifique o .env e a chave.")
        return

    # 2. Inicializar componentes
    memory = ContextualMemory() # Memória compartilhada
    model = GeminiModel()      # Modelo LLM

    # 3. Definir Ferramentas
    web_tool = WebNavigatorTool()

    # 4. Definir Agentes
    navegador = Agent(
        name="Navegador",
        role=(
            "Responsável por navegar em páginas web. "
            "Dada uma tarefa para navegar para uma URL, extraia APENAS a URL da descrição da tarefa "
            "e passe SOMENTE a URL para a ferramenta WebNavigatorTool."
        ),
        model=model,
        tools=[web_tool], # Passa a ferramenta de navegação
        memory=memory
    )
    # TODO: Adicionar outros agentes conforme necessário (ex: PreenchedorDeFormulario, AnalisadorDePagina)

    # 5. Definir Tarefas
    # A URL alvo do projeto
    target_url = "https://precificacao-sistema.onrender.com/"

    tarefa_acessar_site = Task(
        description=f"Navegue até a página inicial do sistema de precificação em {target_url}",
        agent=navegador # Agente responsável
    )
    # TODO: Definir tarefas subsequentes (ex: preencher campos, clicar em botões)

    # 6. Criar e Executar a Crew
    equipe = Crew(agents=[navegador], tasks=[tarefa_acessar_site])

    print("\nIniciando a execução da equipe...")
    resultados = await equipe.run()
    print("\nExecução da equipe concluída.")

    # 7. Processar Resultados
    print("\nResultados das tarefas:")
    if resultados:
        for descricao, resultado in resultados.items():
            print(f"- {descricao}: {resultado[:200]}...") # Imprime os primeiros 200 caracteres
    else:
        print("Nenhum resultado retornado pela equipe.")

if __name__ == "__main__":
    # Configura e executa o loop de eventos assíncronos
    asyncio.run(main())
