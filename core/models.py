import asyncio
import re # Importa módulo regex
import json
from typing import List, Optional, Dict, Any
from dataclasses import dataclass, field
import os
# Imports específicos de LLM removidos daqui, gerenciados pelo LLMManager
from playwright.async_api import async_playwright, Browser, Page

# Importa LLMManager
from .llm_manager import LLMManager # Assumindo que llm_manager está no mesmo diretório

# TODO: Adicionar ferramentas de interação web (Selenium/Playwright) aqui ou em tools/

class ContextualMemory:
    """Gerencia a memória contextual para agentes, incluindo histórico individual e global."""
    def __init__(self, max_context_size: int = 10):
        self.individual_data: Dict[str, List[str]] = {}
        self.global_data: List[str] = []
        self.max_context_size = max_context_size

    def store_individual(self, agent_name: str, content: str):
        """Armazena conteúdo na memória individual de um agente."""
        agent_history = self.individual_data.setdefault(agent_name, [])
        agent_history.append(content)
        if len(agent_history) > self.max_context_size:
            agent_history.pop(0)

    def store_global(self, content: str):
        """Armazena conteúdo na memória global."""
        self.global_data.append(content)
        if len(self.global_data) > self.max_context_size:
            self.global_data.pop(0)

    def retrieve_individual(self, agent_name: str) -> List[str]:
        """Recupera a memória individual de um agente."""
        return self.individual_data.get(agent_name, [])

    def retrieve_global(self) -> List[str]:
        """Recupera a memória global."""
        return self.global_data

# Interface base para ferramentas
class BaseTool:
    async def run(self, *args, **kwargs) -> str:
        raise NotImplementedError("Subclasses devem implementar o método run.")

class Agent:
    """Representa um agente autônomo com um papel, gerenciador LLM e ferramentas."""
    # __init__ atualizado para aceitar LLMManager
    def __init__(self, name: str, role: str, llm_manager: LLMManager, tools: Optional[List[BaseTool]] = None, memory: Optional[ContextualMemory] = None):
        self.name = name
        self.role = role
        self.llm_manager = llm_manager # Armazena a instância LLMManager
        self.tools = {tool.__class__.__name__: tool for tool in (tools or []) if tool is not None}
        self.memory = memory

    async def execute(self, input_text: str, dependencies_results: Optional[List[str]] = None, page: Optional[Page] = None) -> str:
        """Executa uma tarefa: 1. LLM planeja qual ferramenta/parâmetro usar. 2. Executa ferramenta. 3. LLM resume."""
        # Log em português
        print(f"[{self.name}] Iniciando tarefa: {input_text}")

        # --- Passo 1: LLM planeja a ação e extrai parâmetros ---
        plan_prompt_parts = [
            f"Você é {self.name}, seu papel é: {self.role}.",
            f"Ferramentas disponíveis: {list(self.tools.keys())}", # Informa as ferramentas
        ]

        if self.memory:
            # Adiciona contexto da memória ao prompt de planejamento
            individual_context = self.memory.retrieve_individual(self.name)
            global_context = self.memory.retrieve_global()
            if individual_context:
                history_str = "\n".join(individual_context[-3:])
                # Texto em português
                plan_prompt_parts.append(f"\n--- Seu Histórico Recente ---\n{history_str}")
            if global_context:
                global_history_str = "\n".join(global_context[-3:])
                 # Texto em português
                plan_prompt_parts.append(f"\n--- Histórico Global Recente ---\n{global_history_str}")

        if dependencies_results:
            deps_str = "\n".join(dependencies_results)
             # Texto em português
            plan_prompt_parts.append(f"\n--- Resultados de Tarefas Anteriores ---
{deps_str}")

         # Texto em português
        plan_prompt_parts.append(f"\n--- Tarefa Atual ---
{input_text}")
        # Instrução para formato JSON (importante)
        plan_prompt_parts.append(
            "\n--- Instrução ---\n"
            "Com base na tarefa atual, seu papel e ferramentas, decida a próxima ação. "
            "Responda APENAS com o nome da ferramenta e os parâmetros **como uma string JSON válida**: FERRAMENTA: {\"param1\": \"valor1\", ...}. "
            "Exemplos: WebNavigatorTool: {\"url\": \"...\"}, WebInteractorTool: {\"action\": \"fill\", \"selector\": \"...\", \"value\": \"...\"}, WebInteractorTool: {\"action\": \"click\", \"selector\": \"...\"}, WebInteractorTool: {\"action\": \"select_option\", \"selector\": \"...\", \"label\": \"...\"}. "
            "Se nenhuma ferramenta for necessária, responda 'Nenhuma ferramenta'."
        )

        planning_prompt = "\n".join(plan_prompt_parts)
        # Atualizado para usar llm_manager.generate
        # Log em português
        print(f"[{self.name}] Enviando prompt de planejamento para o LLM via Manager...")
        llm_plan_response = await self.llm_manager.generate(planning_prompt)
         # Log em português
        print(f"[{self.name}] Resposta do planejamento do LLM: {llm_plan_response}")

        # Verifica se a resposta do LLM indica erro
        # Verifica prefixo de erro genérico do LLMManager ou clientes específicos
        if llm_plan_response.startswith("Erro:") or "Erro na geração" in llm_plan_response:
             # Log em português
             print(f"[{self.name}] Erro detectado na resposta do LLM. Abortando tarefa.")
             # Armazena o erro na memória se aplicável
             if self.memory: self.memory.store_individual(self.name, f"Tarefa: {input_text}\nErro LLM: {llm_plan_response}")
             return llm_plan_response # Retorna o erro

        # --- Passo 2: Executar a ferramenta com base no plano ---
        tool_output = "Nenhuma ferramenta utilizada ou necessária para esta tarefa."
        tool_used = None
        tool_params_dict = None

        if "Nenhuma ferramenta" not in llm_plan_response:
            # Pré-processa a resposta para remover potenciais blocos de código markdown
            cleaned_response = re.sub(r"^```(?:json)?\n(.*?)\n```$", r"\1", llm_plan_response.strip(), flags=re.DOTALL | re.MULTILINE)
            cleaned_response = cleaned_response.strip() # Remove espaços em branco no início/fim

            # Regex atualizada para ser menos restritiva no nome da ferramenta (aceita :) 
            match = re.match(r"\s*([^:]+)\s*:\s*(\{.*?\})\s*", cleaned_response, re.DOTALL | re.IGNORECASE)
            if match:
                tool_name = match.group(1).strip()
                tool_params_json = match.group(2).strip()
                if tool_name in self.tools:
                    tool_to_run = self.tools[tool_name]
                    try:
                        tool_params_dict = json.loads(tool_params_json)
                         # Log em português
                        print(f"[{self.name}] Executando ferramenta '{tool_name}' com parâmetros: {tool_params_dict}")
                        kwargs_for_tool = tool_params_dict.copy()

                        if tool_name in ["WebInteractorTool", "WebNavigatorTool"]:
                            if page:
                                # Prepara argumentos específicos para ferramentas web
                                if tool_name == "WebInteractorTool":
                                    kwargs_for_tool = {"page": page, "action_details_json": tool_params_json}
                                elif tool_name == "WebNavigatorTool":
                                    # WebNavigatorTool espera 'url' e 'page_instance'
                                    kwargs_for_tool = {"url": tool_params_dict.get("url"), "page_instance": page}
                            else:
                                 # Mensagem em português
                                tool_output = f"Erro: Ferramenta '{tool_name}' requer página ativa."
                                raise Exception(tool_output) # Levanta exceção para bloco catch

                        # Executa a ferramenta
                        tool_output = await tool_to_run.run(**kwargs_for_tool)
                        tool_used = tool_name
                         # Log em português
                        print(f"[{self.name}] Saída da ferramenta '{tool_name}': {tool_output[:150]}..." )
                    except json.JSONDecodeError:
                          # Mensagem em português
                         tool_output = f"Erro: Falha ao decodificar JSON '{tool_params_json}' para '{tool_name}'."
                         print(f"[{self.name}] {tool_output}")
                    except Exception as e:
                         # Mensagem em português
                        tool_output = f"Erro ao executar '{tool_name}' com {tool_params_dict}: {type(e).__name__} - {str(e)}"
                        print(f"[{self.name}] {tool_output}")
                else:
                     # Mensagem em português
                    tool_output = f"Erro: LLM sugeriu ferramenta desconhecida '{tool_name}'."
                    print(f"[{self.name}] {tool_output}")
            else:
                  # Mensagem em português (usando cleaned_response)
                 tool_output = f"Erro: Formato inválido na resposta do LLM: '{cleaned_response}'. Esperado 'FERRAMENTA: {{JSON}}'."
                 print(f"[{self.name}] {tool_output}")
        else:
             # Log em português
             print(f"[{self.name}] Nenhuma ferramenta utilizada conforme planejado.")

        # --- Passo 3: LLM resume o resultado --- 
        summary_prompt_parts = [
            f"Você é {self.name}, seu papel é: {self.role}.",
            f"Sua tarefa era: {input_text}"
        ]
        if tool_used:
            summary_prompt_parts.append(f"Você usou a ferramenta '{tool_used}' com o parâmetro '{tool_params_dict}'.")
        summary_prompt_parts.append(f"O resultado da ação (ou da ferramenta) foi: {tool_output}")
        summary_prompt_parts.append(
            "\n--- Instrução ---\n"
            "Com base na sua tarefa e no resultado da ação/ferramenta, "
            "forneça uma resposta final concisa sobre a conclusão da tarefa."
        )

        # Adiciona contexto da memória, se disponível
        if self.memory:
            individual_context = self.memory.retrieve_individual(self.name)
            global_context = self.memory.retrieve_global()
            if individual_context:
                 history_str = "\n".join(individual_context[-3:])
                  # Texto em português
                 summary_prompt_parts.insert(2, f"\n--- Seu Histórico Recente ---\n{history_str}") # Insere após papel e tarefa
            if global_context:
                 global_history_str = "\n".join(global_context[-3:])
                  # Texto em português
                 summary_prompt_parts.insert(2, f"\n--- Histórico Global Recente ---\n{global_history_str}")

        summary_prompt = "\n".join(summary_prompt_parts)
        # Log em português
        print(f"[{self.name}] Enviando prompt de resumo para o LLM via Manager...")
        final_response = await self.llm_manager.generate(summary_prompt)

        # Armazenar na memória
        if self.memory:
            memory_action = f"Ferramenta: {tool_used}, Params: {tool_params_dict}" if tool_used else "Nenhuma ferramenta usada"
            memory_entry = f"Tarefa: {input_text}\nAção: {memory_action}\nResultado: {final_response}"
            self.memory.store_individual(self.name, memory_entry)
            self.memory.store_global(f"[{self.name}]: {final_response}")

        # Log em português
        print(f"[{self.name}] Tarefa concluída. Resultado direto: {final_response[:150]}..." )
        return final_response

@dataclass
class Task:
    """Representa uma tarefa a ser executada por um agente."""
    description: str
    agent: Agent
    priority: int = 0
    dependencies: List["Task"] = field(default_factory=list)
    result: Optional[str] = None
    executed: bool = False

    def get_dependencies_results(self) -> List[str]:
        """Obtém os resultados das tarefas dependentes que já foram executadas."""
        # Verificação de string de erro padronizada
        return [task.result for task in self.dependencies if task.executed and task.result is not None and not str(task.result).startswith("Erro:")]

    def __hash__(self):
        # Necessário para usar Task como chave em dicionários ou sets, se preciso
        return hash(self.description + self.agent.name)

class Crew:
    """Gerencia e executa uma coleção de tarefas por uma equipe de agentes."""
    def __init__(self, agents: List[Agent], tasks: List[Task]):
        self.agents = {agent.name: agent for agent in agents}
        # Cria um grafo de tarefas para facilitar o processamento de dependências (não usado diretamente no modo sequencial)
        self.tasks = tasks 
        self._task_results: Dict[Task, Any] = {} # Armazena resultados intermediários
        self.browser: Optional[Browser] = None
        self.page: Optional[Page] = None
        self._playwright = None

    async def setup_browser(self, headless: bool = True):
        # Log em português
        print("[Crew] Configurando o navegador Playwright...")
        try:
            self._playwright = await async_playwright().start()
            self.browser = await self._playwright.chromium.launch(headless=headless)
            self.page = await self.browser.new_page()
             # Log em português
            print("[Crew] Navegador e página configurados com sucesso.")
        except Exception as e:
             # Log em português
            print(f"[Crew] Erro crítico ao configurar o navegador: {e}")
            await self.close_browser()
            raise

    async def close_browser(self):
         # Log em português
        print("[Crew] Fechando o navegador Playwright...")
        if self.page and not self.page.is_closed():
             # Log em português
            try: await self.page.close(); print("[Crew] Página fechada.")
            except Exception as e: print(f"[Crew] Erro ao fechar a página: {e}")
        if self.browser and self.browser.is_connected():
             # Log em português
            try: await self.browser.close(); print("[Crew] Navegador fechado.")
            except Exception as e: print(f"[Crew] Erro ao fechar o navegador: {e}")
        if self._playwright:
             try:
                 await self._playwright.stop()
                  # Log em português
                 print("[Crew] Playwright parado.")
             except Exception as e: print(f"[Crew] Erro ao parar Playwright: {e}")
        self.page = None; self.browser = None; self._playwright = None
         # Log em português
        print("[Crew] Limpeza do navegador concluída.")

    async def _execute_task(self, task: Task):
        """Executa uma única tarefa, garantindo que suas dependências foram concluídas.
           Nota: No modo sequencial de Crew.run, as dependências já terão sido
           processadas sequencialmente antes desta função ser chamada para a tarefa atual.
        """
        # Verifica se a tarefa já foi executada (com ou sem sucesso)
        if task.executed:
            if task.result is not None and not str(task.result).startswith("Erro:"):
                 # Log em português
                print(f"[Crew] Reutilizando resultado da tarefa: {task.description}")
                return task.result
            else:
                  # Log em português
                 print(f"[Crew] Tarefa já falhou anteriormente: {task.description}")
                 return task.result

        # Verifica o status das dependências (importante mesmo no modo sequencial)
        if task.dependencies:
             # Log em português
            print(f"[Crew] Verificando status das dependências para a tarefa: {task.description}")
            # No modo sequencial, as dependências já deveriam ter sido executadas.
            # Apenas verificamos se alguma falhou.
            failed_dependencies = []
            for dep in task.dependencies:
                 dep_result = self._task_results.get(dep)
                 if not dep.executed or (dep_result is not None and str(dep_result).startswith("Erro:")):
                     failed_dependencies.append(dep.description)

            if failed_dependencies:
                 # Mensagem em português
                 error_msg = f"Erro: Tarefa '{task.description}' não pode ser executada. Falha nas dependências: {failed_dependencies}"
                 print(f"[Crew] {error_msg}")
                 task.result = error_msg; task.executed = True; self._task_results[task] = error_msg
                 return error_msg
             # Log em português
            print(f"[Crew] Dependências para '{task.description}' verificadas (OK).")

        agent = self.agents[task.agent.name]
         # Log em português
        print(f"[Crew] Executando tarefa: '{task.description}' pelo agente {agent.name}")
        dependency_results = task.get_dependencies_results()
        result = await agent.execute(input_text=task.description, dependencies_results=dependency_results, page=self.page)
        task.result = result; task.executed = True; self._task_results[task] = result
         # Log em português
        print(f"--- Tarefa Concluída: '{task.description}' por {agent.name} ---")
        return result

    async def run(self, headless: bool = True):
        """Executa todas as tarefas em ordem sequencial, respeitando dependências."""
         # Log em português
        print("--- Iniciando execução da Crew (Modo Sequencial) ---")
        final_results = {} 
        try:
            await self.setup_browser(headless=headless)
            if not self.browser or not self.page:
                  # Log em português
                 print("[Crew] Erro fatal: Navegador não configurado.")
                 return None

            # Executa tarefas sequencialmente usando um loop for simples
            # Log em português
            print("[Crew] Executando tarefas sequencialmente...")
            for task in self.tasks:
                 # Log em português
                print(f"\n[Crew] Iniciando processamento da tarefa: {task.description}")
                await self._execute_task(task)
                # Opcional: Adicionar um pequeno atraso entre tarefas se necessário
                # await asyncio.sleep(0.1)
                # Verifica se a tarefa atual falhou para decidir se continua
                if str(self._task_results.get(task)).startswith("Erro:"):
                     # Log em português
                    print(f"[Crew] Execução encontrou erro na tarefa: {task.description}")
                    # Decide se interrompe ou continua executando outras tarefas independentes
                    # break # Descomente para parar a execução no primeiro erro

             # Log em português
            print("\n--- Execução das Tarefas Concluída ---")
            # Usa description como chave para resultados finais
            final_results = {task.description: self._task_results.get(task, "Erro: Tarefa não executada/sem resultado") for task in self.tasks}
            return final_results
        except Exception as e:
              # Log em português
             print(f"[Crew] Erro crítico durante a execução da Crew: {e}")
             import traceback; traceback.print_exc()
             return None
        finally:
            await self.close_browser()
             # Log em português
            print("--- Execução da Crew Finalizada (navegador fechado) ---") 