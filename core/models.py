import asyncio
import re # Import regex module
from typing import List, Optional, Dict, Any
from dataclasses import dataclass, field
import google.generativeai as genai

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

    async def generate(self, prompt: str) -> str:
        """Gera conteúdo usando o modelo Gemini configurado."""
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
            print(f"Erro na geração Gemini: {e}")
            return f"Erro na geração: {str(e)}"

# Interface base para ferramentas (Placeholder)
class BaseTool:
    async def run(self, *args, **kwargs) -> str:
        raise NotImplementedError("Subclasses devem implementar o método run.")

class Agent:
    """Representa um agente autônomo com um papel, modelo e ferramentas."""
    def __init__(self, name: str, role: str, model: GeminiModel, tools: Optional[List[BaseTool]] = None, memory: Optional[ContextualMemory] = None):
        self.name = name
        self.role = role
        self.model = model
        self.tools = {tool.__class__.__name__: tool for tool in (tools or [])} # Mapeia nome da classe para instância
        self.memory = memory

    async def execute(self, input_text: str, dependencies_results: Optional[List[str]] = None) -> str:
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
        # Instrução específica para planejamento e extração
        plan_prompt_parts.append(
            "\n--- Instrução ---\n"
            "Com base na tarefa atual e no seu papel, qual ferramenta você deve usar (se alguma)? "
            "Se for usar uma ferramenta, quais parâmetros EXATOS você deve passar para ela? "
            "Para WebNavigatorTool, extraia apenas a URL. Responda APENAS com o nome da ferramenta e o parâmetro a ser usado, no formato: FERRAMENTA: PARAMETRO. "
            "Se nenhuma ferramenta for necessária, responda 'Nenhuma ferramenta'."
        )
        
        planning_prompt = "\n".join(plan_prompt_parts)
        print(f"[{self.name}] Enviando prompt de planejamento para o LLM...")
        llm_plan_response = await self.model.generate(planning_prompt)
        print(f"[{self.name}] Resposta do planejamento do LLM: {llm_plan_response}")

        # --- Passo 2: Executar a ferramenta com base no plano --- 
        tool_output = "Nenhuma ferramenta utilizada."
        tool_used = None
        tool_param = None

        if "Nenhuma ferramenta" not in llm_plan_response:
            # Tenta extrair FERRAMENTA: PARAMETRO da resposta do LLM
            match = re.match(r"\s*([\w\d_]+)\s*:\s*(.*)\s*", llm_plan_response, re.IGNORECASE)
            if match:
                tool_name = match.group(1).strip()
                tool_param = match.group(2).strip()
                
                if tool_name in self.tools:
                    tool_to_run = self.tools[tool_name]
                    print(f"[{self.name}] Executando ferramenta '{tool_name}' com parâmetro: '{tool_param}'")
                    try:
                        # Assumindo que ferramentas esperam um único argumento posicional por enquanto
                        # TODO: Adaptar para kwargs se ferramentas ficarem mais complexas
                        tool_output = await tool_to_run.run(tool_param) 
                        tool_used = tool_name
                        print(f"[{self.name}] Saída da ferramenta '{tool_name}': {tool_output[:150]}...")
                    except Exception as e:
                        tool_output = f"Erro ao executar ferramenta {tool_name}: {str(e)}"
                        print(f"[{self.name}] {tool_output}")
                else:
                    tool_output = f"Erro: LLM sugeriu ferramenta desconhecida '{tool_name}'. Ferramentas disponíveis: {list(self.tools.keys())}"
                    print(f"[{self.name}] {tool_output}")
            else:
                 tool_output = f"Erro: Não foi possível extrair 'FERRAMENTA: PARAMETRO' da resposta do LLM: '{llm_plan_response}'."
                 print(f"[{self.name}] {tool_output}")
        else:
             print(f"[{self.name}] Nenhuma ferramenta será utilizada conforme planejado pelo LLM.")
             
        # --- Passo 3: LLM resume o resultado --- 
        summary_prompt_parts = [
            f"Você é {self.name}, seu papel é: {self.role}.",
            f"Sua tarefa era: {input_text}"
        ]
        if tool_used:
            summary_prompt_parts.append(f"Você usou a ferramenta '{tool_used}' com o parâmetro '{tool_param}'.")
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
            memory_entry = f"Tarefa: {input_text}\nAção: {tool_output}\nResultado: {final_response}"
            self.memory.store_individual(self.name, memory_entry)
            self.memory.store_global(f"[{self.name}]: {final_response}")

        print(f"[{self.name}] Tarefa concluída. Resultado: {final_response[:100]}...")
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
        return [task.result for task in self.dependencies if task.result is not None]

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

    async def _execute_task(self, task: Task):
        """Executa uma única tarefa, garantindo que suas dependências foram concluídas."""
        if task in self._task_results: # Já executada ou em execução
            return self._task_results[task]
        if task.executed: # Segurança adicional
             return task.result

        # Marca como "em execução" para detectar ciclos (embora não implementado aqui)
        self._task_results[task] = None

        # Espera pelas dependências
        dependency_results = []
        if task.dependencies:
            dep_futures = [self._execute_task(dep) for dep in task.dependencies]
            await asyncio.gather(*dep_futures) # Espera todas as dependências terminarem
            dependency_results = task.get_dependencies_results() # Pega os resultados agora que terminaram

        # Executa a tarefa
        agent = self.agents[task.agent.name]
        result = await agent.execute(task.description, dependency_results)
        task.result = result
        task.executed = True
        self._task_results[task] = result # Armazena resultado final
        print(f"--- Tarefa Concluída: {task.description} por {agent.name} ---")
        return result

    async def run(self):
        """Executa todas as tarefas na ordem correta de dependência."""
        print("--- Iniciando execução da Crew ---")
        # Executa todas as tarefas. O asyncio.gather garante o paralelismo onde possível.
        # A lógica em _execute_task lida com as dependências sequenciais.
        await asyncio.gather(*(self._execute_task(task) for task in self.tasks))
        print("--- Execução da Crew Concluída ---")
        # Retorna os resultados finais, se necessário
        return {task.description: task.result for task in self.tasks} 