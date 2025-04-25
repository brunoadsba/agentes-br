import asyncio
import os
import json
from dotenv import load_dotenv

# Módulos Principais
from core.models import Agent, Task, Crew, ContextualMemory
# Importa LLMManager
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
        # Inicializa o LLMManager
        llm_manager = LLMManager()
        if not llm_manager.clients:
            print("Erro: Nenhum cliente LLM foi inicializado com sucesso. Verifique as chaves de API no .env.")
            return
    except Exception as e: # Captura erros potenciais durante a inicialização do LLMManager
        print(f"Erro ao inicializar LLMManager: {e}")
        return

    # Configura a memória para usar o LLMManager
    memory.set_llm_manager(llm_manager)

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
        llm_manager=llm_manager,
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
        # Seletores antigos para referência (não mais usados diretamente nos dados)
        # "servico_1_regiao": "#regiao-1",
        # "servico_1_variavel": "#variavel-1",
        # Novos seletores adicionados
        "servico_1_grau_risco": "#grau-risco-1",
        "servico_1_num_trabalhadores": "#numTrabalhadores-1",
        "servico_1_regiao": "#regiao-1", # Mantido para clareza
        "servico_1_quantidade": "#quantidade-1",
        "servico_1_custos_logisticos": "#custos-logisticos-1",
        "gerar_orcamento_btn": 'button:has-text("Gerar Orçamento")',
        "confirmar_orcamento_btn": 'button:has-text("Confirmar e Gerar Orçamento")',
        "tema_noturno_btn": "#themeIcon", # Botão de modo noturno
    }
    dados_cliente = {
        "empresa": "Empresa Teste Gemini",
        "email": "contato.gemini@testeia.com",
        "telefone": "71955554444"
    }
    dados_servico_1 = {
        "nome": "Elaboração e acompanhamento do PGR", # Serviço atualizado com base na imagem
        "grau_risco": "1 e 2",
        "num_trabalhadores": "ate19",
        "regiao": "Instituto",
        "quantidade": "1",
        "custos_logisticos": "700.00"
    }
    target_url = "https://precificacao-sistema.onrender.com/"

    # 5. Definir Tarefas (com description)
    tarefa_navegar = Task(
        description=f"Navegue até a página inicial em {target_url}",
        agent=executor_web
    )
    
    # Nova tarefa para ativar o modo noturno
    tarefa_ativar_modo_noturno = Task(
        description=f"Clique no botão de modo noturno ('{selectors['tema_noturno_btn']}') para ativar o tema escuro.",
        agent=executor_web,
        dependencies=[tarefa_navegar]
    )
    
    tarefa_fill_empresa = Task(
        description=f"Preencha o campo Empresa ('{selectors['empresa']}') com '{dados_cliente['empresa']}'. IMPORTANTE: Aguarde pelo menos 2 segundos após a página carregar e verifique se o campo está visível antes de tentar preencher. Se o campo não estiver visível, tente clicar fora e depois no campo.",
        agent=executor_web,
        dependencies=[tarefa_ativar_modo_noturno]
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
    tarefa_select_servico1_nome = Task(
        description=f"Selecione o serviço '{dados_servico_1['nome']}' no dropdown ('{selectors['servico_1_nome']}'). IMPORTANTE: Selecione EXATAMENTE 'Elaboração e acompanhamento do PGR', NÃO selecione 'Serviço (2)' que é uma opção errada. Se o dropdown tiver valor 'Serviço (2)', este deve ser alterado para 'Elaboração e acompanhamento do PGR'.",
        agent=executor_web,
        dependencies=[tarefa_fill_telefone]
    )
    # Novas tarefas para preencher os detalhes do serviço
    tarefa_select_servico1_risco = Task(
        description=f"Selecione o Grau de Risco '{dados_servico_1['grau_risco']}' no dropdown ('{selectors['servico_1_grau_risco']}').",
        agent=executor_web,
        dependencies=[tarefa_select_servico1_nome]
    )
    tarefa_select_servico1_trabalhadores = Task(
        description=f"Selecione o Número de Trabalhadores '{dados_servico_1['num_trabalhadores']}' no dropdown ('{selectors['servico_1_num_trabalhadores']}').",
        agent=executor_web,
        dependencies=[tarefa_select_servico1_risco]
    )
    tarefa_select_servico1_regiao = Task(
        description=f"Selecione a Região '{dados_servico_1['regiao']}' no dropdown ('{selectors['servico_1_regiao']}').",
        agent=executor_web,
        dependencies=[tarefa_select_servico1_trabalhadores]
    )
    tarefa_fill_servico1_quantidade = Task(
        description=f"Preencha a Quantidade ('{selectors['servico_1_quantidade']}') com '{dados_servico_1['quantidade']}'.",
        agent=executor_web,
        dependencies=[tarefa_select_servico1_regiao]
    )
    tarefa_fill_servico1_custos = Task(
        description=f"Preencha os Custos Logísticos ('{selectors['servico_1_custos_logisticos']}') com '{dados_servico_1['custos_logisticos']}'.",
        agent=executor_web,
        dependencies=[tarefa_fill_servico1_quantidade]
    )
    # Tarefa para clicar no primeiro botão "Gerar Orçamento"
    tarefa_click_gerar = Task(
        description=f"Após preencher todos os detalhes do serviço 1 (risco, trabalhadores, região, quantidade, custos), clique no botão 'Gerar Orçamento' ('{selectors['gerar_orcamento_btn']}') para ir para a tela de confirmação.",
        agent=executor_web,
        dependencies=[tarefa_fill_servico1_custos]
    )
    # Tarefa para clicar no botão "Confirmar e Gerar Orçamento" (que deve disparar o download)
    tarefa_click_confirmar_e_gerar = Task(
        description=f"Na tela de confirmação, clique no botão que contém o texto \'orçamento\' (usando o seletor 'button:text-matches(\"orçamento\", \"i\")') para gerar o PDF.",
        agent=executor_web,
        dependencies=[tarefa_click_gerar],
    )

    # 6. Criar e Executar a Crew
    # Atualiza a lista de tarefas para incluir apenas o primeiro serviço
    lista_tarefas = [
        tarefa_navegar,
        tarefa_ativar_modo_noturno,
        tarefa_fill_empresa,
        tarefa_fill_email,
        tarefa_fill_telefone,
        tarefa_select_servico1_nome,
        tarefa_select_servico1_risco,
        tarefa_select_servico1_trabalhadores,
        tarefa_select_servico1_regiao,
        tarefa_fill_servico1_quantidade,
        tarefa_fill_servico1_custos,
        tarefa_click_gerar,
        tarefa_click_confirmar_e_gerar
    ]
    equipe = Crew(agents=[executor_web], tasks=lista_tarefas)

    print("\nIniciando a execução da equipe com LLM Manager...")
    resultados = await equipe.run(headless=headless_mode)
    print("\nExecução da equipe concluída.")

    # 7. Processar Resultados
    print("\nResultados das tarefas:")
    if resultados:
        for tarefa in lista_tarefas:
            resultado = resultados.get(tarefa.description, "Erro: Resultado não encontrado para esta descrição")
            print(f"- {tarefa.description}:")
            print(f"  Resultado: {resultado}")
    else:
        print("Nenhum resultado retornado pela equipe ou ocorreu um erro fatal.")

# Bloco __main__ com argparse
if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--no-headless', action='store_false', dest='headless', help="Executa o navegador em modo visível.")
    parser.set_defaults(headless=True)
    args = parser.parse_args()
    asyncio.run(main(headless_mode=args.headless))
