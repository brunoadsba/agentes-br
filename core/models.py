import asyncio
import re # Import regex module
import json
from typing import List, Optional, Dict, Any
from dataclasses import dataclass, field
import os
import google.generativeai as genai
from openai import AsyncOpenAI # Para OpenAI/DeepSeek (se reativado)
from groq import AsyncGroq # Para Groq (se reativado)
from playwright.async_api import async_playwright, Browser, Page

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

class GeminiModel:
    """Wrapper para interação com o modelo Gemini do Google Generative AI."""
    def __init__(self, model_name: str = "gemini-1.5-flash", temperature: float = 0.7, top_k: int = 40):
        self.model = genai.GenerativeModel(model_name)
        self.temperature = temperature
        self.top_k = top_k
        # TODO: Configurar API Key via config/setup.py ou .env
        # Exemplo: genai.configure(api_key="SUA_API_KEY")
        print(f"[GeminiModel] Wrapper inicializado para {model_name}. Certifique-se que genai.configure() foi chamado.")

    async def generate(self, prompt: str) -> str:
        """Gera conteúdo usando o modelo Gemini configurado."""
        print(f"[GeminiModel] Enviando prompt para Gemini...")
        try:
            # Simula latência para evitar rate limits e dar tempo para APIs externas
            await asyncio.sleep(0.5)
            response = self.model.generate_content(
                prompt,
                generation_config=genai.types.GenerationConfig(
                    temperature=self.temperature,
                    top_k=self.top_k
                )
            )
            # TODO: Adicionar tratamento mais robusto para possíveis erros de API ou conteúdo bloqueado
            # Tenta extrair o conteúdo de 'text' ou lida com a falta dele
            return response.text if hasattr(response, 'text') else str(response) # Retorna str(response) se .text não existir
        except Exception as e:
            # TODO: Implementar logging adequado
            print(f"Erro na geração Gemini: {type(e).__name__} - {e}")
            # Retorna o erro para ser tratado pela Crew/Agent
            return f"Erro na geração Gemini: {str(e)}"

# Interface base para ferramentas (Placeholder)
class BaseTool:
    async def run(self, *args, **kwargs) -> str:
        raise NotImplementedError("Subclasses devem implementar o método run.")

class Agent:
    """Representa um agente autônomo com um papel, modelo e ferramentas."""
    def __init__(self, name: str, role: str, model, tools: Optional[List[BaseTool]] = None, memory: Optional[ContextualMemory] = None):
        self.name = name
        self.role = role
        self.model = model
        self.tools = {tool.__class__.__name__: tool for tool in (tools or []) if tool is not None}
        self.memory = memory

    async def execute(self, input_text: str, dependencies_results: Optional[List[str]] = None, page: Optional[Page] = None) -> str:
        """Executa uma tarefa: 1. LLM planeja qual ferramenta/parâmetro usar. 2. Executa ferramenta. 3. LLM resume."""
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
                plan_prompt_parts.append(f"\n--- Seu Histórico Recente ---\n{history_str}")
            if global_context:
                global_history_str = "\n".join(global_context[-3:])
                plan_prompt_parts.append(f"\n--- Histórico Global Recente ---\n{global_history_str}")
        
        if dependencies_results:
            deps_str = "\n".join(dependencies_results)
            plan_prompt_parts.append(f"\n--- Resultados de Tarefas Anteriores ---\n{deps_str}")

        plan_prompt_parts.append(f"\n--- Tarefa Atual ---\n{input_text}")
        # Instrução para formato JSON (importante)
        plan_prompt_parts.append(
            "\n--- Instrução ---\n"
            "Com base na tarefa atual, seu papel e ferramentas, decida a próxima ação. "
            "Responda APENAS com o nome da ferramenta e os parâmetros **como uma string JSON válida**: FERRAMENTA: {\"param1\": \"valor1\", ...}. "
            "Exemplos: WebNavigatorTool: {\"url\": \"...\"}, WebInteractorTool: {\"action\": \"fill\", \"selector\": \"...\", \"value\": \"...\"}, WebInteractorTool: {\"action\": \"click\", \"selector\": \"...\"}, WebInteractorTool: {\"action\": \"select_option\", \"selector\": \"...\", \"label\": \"...\"}. "
            "Se nenhuma ferramenta for necessária, responda 'Nenhuma ferramenta'."
        )
        
        planning_prompt = "\n".join(plan_prompt_parts)
        print(f"[{self.name}] Enviando prompt de planejamento para o LLM ({self.model.__class__.__name__})...")
        llm_plan_response = await self.model.generate(planning_prompt)
        print(f"[{self.name}] Resposta do planejamento do LLM: {llm_plan_response}")

        # Verifica se a resposta do LLM indica erro
        if "Erro na geração" in llm_plan_response:
             print(f"[{self.name}] Erro detectado na resposta do LLM. Abortando tarefa.")
             # Armazena o erro na memória se aplicável
             if self.memory: self.memory.store_individual(self.name, f"Tarefa: {input_text}\nErro LLM: {llm_plan_response}")
             return llm_plan_response # Retorna o erro

        # --- Passo 2: Executar a ferramenta com base no plano --- 
        tool_output = "Nenhuma ferramenta utilizada ou necessária para esta tarefa."
        tool_used = None
        tool_params_dict = None

        if "Nenhuma ferramenta" not in llm_plan_response:
            match = re.match(r"\s*([^\s]+)\s*:\s*(\{.*?\})\s*", llm_plan_response, re.DOTALL | re.IGNORECASE)
            if match:
                tool_name = match.group(1).strip()
                tool_params_json = match.group(2).strip()
                if tool_name in self.tools:
                    tool_to_run = self.tools[tool_name]
                    try:
                        tool_params_dict = json.loads(tool_params_json)
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
                                tool_output = f"Erro: Ferramenta '{tool_name}' requer página ativa."
                                raise Exception(tool_output) # Levanta exceção para bloco catch
                        
                        # Executa a ferramenta
                        tool_output = await tool_to_run.run(**kwargs_for_tool)
                        tool_used = tool_name
                        print(f"[{self.name}] Saída da ferramenta '{tool_name}': {tool_output[:150]}..." )
                    except json.JSONDecodeError:
                         tool_output = f"Erro: Falha ao decodificar JSON '{tool_params_json}' para '{tool_name}'."
                         print(f"[{self.name}] {tool_output}")
                    except Exception as e:
                        tool_output = f"Erro ao executar '{tool_name}' com {tool_params_dict}: {type(e).__name__} - {str(e)}"
                        print(f"[{self.name}] {tool_output}")
                else:
                    tool_output = f"Erro: LLM sugeriu ferramenta desconhecida '{tool_name}'."
                    print(f"[{self.name}] {tool_output}")
            else:
                 tool_output = f"Erro: Formato inválido na resposta do LLM: '{llm_plan_response}'. Esperado 'FERRAMENTA: {{JSON}}'."
                 print(f"[{self.name}] {tool_output}")
        else:
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
                 summary_prompt_parts.insert(2, f"\n--- Seu Histórico Recente ---\n{history_str}") # Insere após papel e tarefa
            if global_context:
                 global_history_str = "\n".join(global_context[-3:])
                 summary_prompt_parts.insert(2, f"\n--- Histórico Global Recente ---\n{global_history_str}")
        
        summary_prompt = "\n".join(summary_prompt_parts)
        print(f"[{self.name}] Enviando prompt de resumo para o LLM...")
        final_response = await self.model.generate(summary_prompt)

        # Armazenar na memória
        if self.memory:
            memory_action = f"Ferramenta: {tool_used}, Params: {tool_params_dict}" if tool_used else "Nenhuma ferramenta usada"
            memory_entry = f"Tarefa: {input_text}\nAção: {memory_action}\nResultado: {final_response}"
            self.memory.store_individual(self.name, memory_entry)
            self.memory.store_global(f"[{self.name}]: {final_response}")

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
        return [task.result for task in self.dependencies if task.executed and task.result is not None and "Erro" not in str(task.result)]

    def __hash__(self):
        # Necessário para usar Task como chave em dicionários ou sets, se preciso
        return hash(self.description + self.agent.name)

class Crew:
    """Gerencia e executa uma coleção de tarefas por uma equipe de agentes."""
    def __init__(self, agents: List[Agent], tasks: List[Task]):
        self.agents = {agent.name: agent for agent in agents}
        # Cria um grafo de tarefas para facilitar o processamento de dependências
        self.tasks = tasks
        self._task_graph: Dict[Task, List[Task]] = {task: task.dependencies for task in tasks}
        self._task_results: Dict[Task, Any] = {} # Armazena resultados intermediários
        self.browser: Optional[Browser] = None
        self.page: Optional[Page] = None
        self._playwright = None

    async def setup_browser(self, headless: bool = True):
        # ... (código setup_browser como implementado antes) ...
        try:
            print("[Crew] Configurando o navegador Playwright...")
            self._playwright = await async_playwright().start()
            self.browser = await self._playwright.chromium.launch(headless=headless)
            self.page = await self.browser.new_page()
            print("[Crew] Navegador e página configurados com sucesso.")
        except Exception as e:
            print(f"[Crew] Erro crítico ao configurar o navegador: {e}")
            await self.close_browser()
            raise

    async def close_browser(self):
        # ... (código close_browser como implementado antes) ...
        print("[Crew] Fechando o navegador Playwright...")
        if self.page and not self.page.is_closed():
            try: await self.page.close(); print("[Crew] Página fechada.")
            except Exception as e: print(f"[Crew] Erro ao fechar a página: {e}")
        if self.browser and self.browser.is_connected():
            try: await self.browser.close(); print("[Crew] Navegador fechado.")
            except Exception as e: print(f"[Crew] Erro ao fechar o navegador: {e}")
        if self._playwright:
             try:
                 await self._playwright.stop()
                 print("[Crew] Playwright parado.")
             except Exception as e: print(f"[Crew] Erro ao parar Playwright: {e}")
        self.page = None; self.browser = None; self._playwright = None
        print("[Crew] Limpeza do navegador concluída.")

    async def _execute_task(self, task: Task):
        """Executa uma única tarefa, garantindo que suas dependências foram concluídas."""
        if task in self._task_results and task.executed and task.result is not None and "Erro" not in str(task.result):
            print(f"[Crew] Reutilizando resultado da tarefa: {task.description}")
            return self._task_results[task]
        if task.executed and ("Erro" in str(task.result) or task.result is None):
             print(f"[Crew] Tarefa já falhou anteriormente: {task.description}")
             return task.result

        if task.dependencies:
            print(f"[Crew] Verificando dependências para a tarefa: {task.description}")
            dep_futures = [self._execute_task(dep) for dep in task.dependencies]
            await asyncio.gather(*dep_futures)
            # Verifica se ALGUMA dependência falhou
            failed_dependencies = [dep.description for dep in task.dependencies if not dep.executed or (dep.result is not None and "Erro" in str(dep.result))]
            if failed_dependencies:
                 error_msg = f"Tarefa '{task.description}' não pode ser executada. Falha nas dependências: {failed_dependencies}"
                 print(f"[Crew] {error_msg}")
                 task.result = error_msg; task.executed = True; self._task_results[task] = error_msg
                 return error_msg
            print(f"[Crew] Dependências para '{task.description}' concluídas.")

        agent = self.agents[task.agent.name]
        print(f"[Crew] Executando tarefa: '{task.description}' pelo agente {agent.name}")
        # Passa description e page
        result = await agent.execute(input_text=task.description, dependencies_results=[], page=self.page)
        task.result = result; task.executed = True; self._task_results[task] = result
        print(f"--- Tarefa Concluída: '{task.description}' por {agent.name} ---")
        return result

    async def run(self, headless: bool = True, task_interval_seconds: int = 0):
        """Executa todas as tarefas na ordem correta de dependência."""
        print("--- Iniciando execução da Crew (Modo LLM) ---")
        final_results = {} 
        try:
            await self.setup_browser(headless=headless)
            if not self.browser or not self.page:
                 print("[Crew] Erro fatal: Navegador não configurado.")
                 return None
            
            all_tasks_future = asyncio.gather(*(self._execute_task(task) for task in self.tasks))
            await all_tasks_future
            print("--- Execução das Tarefas Concluída ---")
            # Usa description como chave para resultados finais
            final_results = {task.description: self._task_results.get(task, "Erro: Tarefa não executada/sem resultado") for task in self.tasks}
            return final_results
        except Exception as e:
             print(f"[Crew] Erro crítico durante a execução da Crew: {e}")
             import traceback; traceback.print_exc()
             return None
        finally:
            await self.close_browser()
            print("--- Execução da Crew Finalizada (navegador fechado) ---") 