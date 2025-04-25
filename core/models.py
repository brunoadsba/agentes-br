import asyncio
import re # Importa módulo regex
import json
import logging
from typing import List, Optional, Dict, Any
from dataclasses import dataclass, field
import os
# Imports específicos de LLM removidos daqui, gerenciados pelo LLMManager
from playwright.async_api import async_playwright, Browser, Page, Download

# Importa LLMManager
from .llm_manager import LLMManager # Assumindo que llm_manager está no mesmo diretório
# Importa ContextualMemory de memory.py
from .memory import ContextualMemory

# Importa utilidades de prompt
try:
    from .prompt_utils import (
        optimize_prompt_for_tokens, 
        create_tool_specific_prompts, 
        calculate_token_count, 
        get_model_context_window,
        create_optimized_system_prompt,
        truncate_text_to_tokens
    )
    PROMPT_UTILS_AVAILABLE = True
except ImportError:
    PROMPT_UTILS_AVAILABLE = False
    print("Aviso: Utilitários de otimização de prompt não disponíveis. Usando prompts não otimizados.")

# Configuração básica de logging (ajuste se necessário)
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# A classe ContextualMemory foi removida deste arquivo e está sendo importada de core/memory.py

# Interface base para ferramentas
class BaseTool:
    async def run(self, *args, **kwargs) -> str:
        raise NotImplementedError("Subclasses devem implementar o método run.")

class Agent:
    """Representa um agente autônomo com um papel, gerenciador LLM e ferramentas."""
    # __init__ atualizado para aceitar LLMManager
    def __init__(self, name: str, role: str, llm_manager: LLMManager, tools: Optional[List[BaseTool]] = None,
                memory: Optional[ContextualMemory] = None, max_prompt_tokens: int = 4000):
        self.name = name
        self.role = role
        self.llm_manager = llm_manager # Armazena a instância LLMManager
        self.tools = {tool.__class__.__name__: tool for tool in (tools or []) if tool is not None}
        self.memory = memory
        self.max_prompt_tokens = max_prompt_tokens

        # Configura a memória para usar o LLM Manager para sumarização
        if self.memory and not self.memory.llm_manager:
            # Passa o LLMManager para a memória para que ela possa usá-lo
            self.memory.set_llm_manager(self.llm_manager)

    def _create_planning_prompt(self, input_text: str, dependencies_results: Optional[List[str]] = None) -> str:
        """Cria um prompt estruturado para planejar a próxima ação com Chain-of-Thought."""

        # Seção principal com informações do agente e ferramentas
        main_sections = [
            f"# Agente: {self.name}",
            f"## Seu Papel\\n{self.role}",
            f"## Ferramentas Disponíveis\\n{', '.join(self.tools.keys()) if self.tools else 'Nenhuma ferramenta disponível'}"
        ]

        # Seção de instruções com raciocínio Chain-of-Thought
        instructions = [
            "## Instruções Gerais",
            "Siga rigorosamente o passo a passo abaixo para cada tarefa:",
            "",
            "1. **FOCO TOTAL NO PRIMEIRO SERVIÇO:** Sua missão é preencher **APENAS UM** serviço. Ignore completamente quaisquer campos, botões ou seletores relacionados a um segundo ou terceiro serviço (ex: `#servico-2-nome`, `#adicionarServico` DEPOIS que já foi clicado uma vez).",
            "2. **NÃO ADICIONE OUTRO SERVIÇO:** NUNCA clique no botão 'Adicionar Serviço' (`#adicionarServico`) se ele já foi clicado uma vez nesta execução.",
            "3. Aguarde o carregamento completo da página antes de qualquer ação.",
            "4. Sempre ative o modo escuro (clicando no botão de tema `#themeIcon`) antes de preencher qualquer campo, se a tarefa pedir.",
            "5. Antes de preencher qualquer campo, certifique-se de que o campo está visível e interagível. Aguarde se necessário.",
            "6. Preencha os campos na ordem especificada nas tarefas. Não pule etapas.",
            "7. Após preencher um campo, aguarde pelo menos 1 segundo antes de passar para o próximo.",
            "8. Use exatamente o seletor CSS fornecido na tarefa (geralmente entre aspas ou parênteses na descrição da tarefa). Não tente adivinhar seletores.",
            "9. Não repita ações já realizadas, a menos que a tarefa peça explicitamente.",
            "10. Se encontrar um erro ou campo não visível, registre o erro claramente na sua resposta e pare a execução da tarefa.",
            "",
            "## O que NÃO fazer:",
            "- NÃO clique em 'Adicionar Serviço' (`#adicionarServico`) mais de uma vez.",
            "- NÃO preencha ou interaja com campos de outros serviços além do primeiro (ex: `#servico-2-...`, `#servico-3-...`).",
            "- NÃO clique em botões que não estejam especificados na tarefa atual.",
            "- NÃO tente adivinhar valores ou seletores.",
            "- NÃO continue se um campo obrigatório não estiver visível ou interagível.",
            "",
            "## Boas Práticas:",
            "- Sempre aguarde o carregamento e a visibilidade dos elementos antes de interagir.",
            "- Siga a ordem das tarefas exatamente como especificada.",
            "- Use os seletores CSS EXATOS fornecidos na descrição da tarefa.",
            "- Registre mensagens claras de sucesso ou erro para cada ação.",
            "",
            "## Exemplos de Decisões",
            "Tarefa: 'Preencha o campo email com usuario@teste.com'",
            "Pensamento: Preciso interagir com um elemento da página para preencher um valor. A ferramenta WebInteractorTool com ação 'fill' é adequada.",
            "Decisão: {\"tool_name\": \"WebInteractorTool\", \"parameters\": {\"action\": \"fill\", \"selector\": \"#email\", \"value\": \"usuario@teste.com\"}}",
            "",
            "Tarefa: 'Navegue para https://exemplo.com'",
            "Pensamento: Preciso navegar para uma nova URL. A ferramenta WebNavigatorTool é adequada.",
            "Decisão: {\"tool_name\": \"WebNavigatorTool\", \"parameters\": {\"url\": \"https://exemplo.com\"}}",
            "",
            "Tarefa: 'Ative o modo escuro'",
            "Pensamento: Preciso clicar no botão de tema para ativar o modo escuro. A ferramenta WebInteractorTool com ação 'click' é adequada.",
            "Decisão: {\"tool_name\": \"WebInteractorTool\", \"parameters\": {\"action\": \"click\", \"selector\": \"#themeIcon\"}}",
            "",
            "Tarefa: 'Analise os resultados anteriores e resuma-os'",
            "Pensamento: Esta tarefa requer apenas análise e não interação com a web.",
            "Decisão: {\"tool_name\": \"Nenhuma ferramenta\", \"parameters\": {}}"
        ]

        # Seção de exemplos (few-shot learning)
        examples = [
            "## Exemplos de Decisões",
            "Tarefa: \"Preencha o campo email com usuario@teste.com\"",
            "Pensamento: Preciso interagir com um elemento da página para preencher um valor. A ferramenta WebInteractorTool com ação \"fill\" é adequada.",
            "Decisão: {\"tool_name\": \"WebInteractorTool\", \"parameters\": {\"action\": \"fill\", \"selector\": \"#email\", \"value\": \"usuario@teste.com\"}}",
            "",
            "Tarefa: \"Navegue para https://exemplo.com\"",
            "Pensamento: Preciso navegar para uma nova URL. A ferramenta WebNavigatorTool é adequada.",
            "Decisão: {\"tool_name\": \"WebNavigatorTool\", \"parameters\": {\"url\": \"https://exemplo.com\"}}",
            "",
            "Tarefa: \"Analise os resultados anteriores e resuma-os\"",
            "Pensamento: Esta tarefa requer apenas análise e não interação com a web.",
            "Decisão: {\"tool_name\": \"Nenhuma ferramenta\", \"parameters\": {}}"
        ]

        # Adiciona contexto da memória, se disponível
        memory_sections = []
        if self.memory:
            # Usa get_formatted_context para obter o contexto relevante da memória
            # Limita o tamanho do contexto para não exceder o limite do prompt
            context_tokens = int(self.max_prompt_tokens * 0.3) # Reserva 30% para contexto
            memory_context = self.memory.get_formatted_context(max_tokens=context_tokens)
            if memory_context and memory_context != "Nenhum contexto disponível na memória.":
                memory_sections.append(f"## Contexto da Memória\\n{memory_context}")

        # Adiciona resultados de tarefas anteriores, se disponíveis
        task_results_section = []
        if dependencies_results:
            deps_str = "\\n".join(dependencies_results)
            task_results_section.append(f"## Resultados de Tarefas Anteriores\\n{deps_str}")

        # Tarefa atual e instruções finais
        final_sections = [
            f"## Tarefa Atual\\n{input_text}",
            "## Decisão Final",
            "1. RACIOCINE em 2-3 frases sobre a melhor abordagem para esta tarefa.",
            "2. DECIDA qual ferramenta usar (ou se nenhuma é necessária).",
            "3. ESPECIFIQUE a ferramenta e parâmetros no formato JSON abaixo. MUITO IMPORTANTE: Se a 'Tarefa Atual' mencionar um seletor CSS específico (ex: entre parênteses ou aspas como 'button:has-text(...)'), VOCÊ DEVE USAR ESSE SELETOR EXATO no parâmetro 'selector' da ferramenta escolhida.",
            "",
            "Responda APENAS com a estrutura JSON no formato: {\"tool_name\": \"NOME_DA_FERRAMENTA\", \"parameters\": {...}}",
            "Se nenhuma ferramenta for necessária, use: {\"tool_name\": \"Nenhuma ferramenta\", \"parameters\": {}}",
            "NÃO inclua nenhum outro texto antes ou depois do JSON."
        ]

        # Combina todas as seções
        all_sections = main_sections + instructions + examples + memory_sections + task_results_section + final_sections
        prompt = "\\n\\n".join(all_sections)

        # Otimiza o prompt se o módulo estiver disponível
        if PROMPT_UTILS_AVAILABLE:
            # Seções que devem ser preservadas mesmo com restrição de tokens
            keep_sections = [
                "Tarefa Atual",
                "Decisão Final",
                "Seu Papel",
                "Ferramentas Disponíveis",
                "Instruções",
                "Contexto da Memória", # Mantém a seção de contexto
                "Resultados de Tarefas Anteriores"
            ]

            # Determina o modelo a ser usado para calcular tokens
            model = self.llm_manager.default_model if hasattr(self.llm_manager, 'default_model') else "gpt-3.5-turbo"

            return optimize_prompt_for_tokens(
                prompt=prompt,
                available_tokens=self.max_prompt_tokens,
                model=model,
                keep_sections=keep_sections
            )

        return prompt

    def _create_summary_prompt(self, input_text: str, tool_used: Optional[str], tool_params_dict: Optional[Dict[str, Any]],
                             tool_output: str) -> str:
        """Cria um prompt estruturado para resumir o resultado de uma ação."""

        # Informações básicas
        base_info = [
            f"# Resumo de Ação: {self.name}",
            f"## Seu Papel\\n{self.role}",
            f"## Contexto da Tarefa\n{input_text}"
        ]

        # Informações sobre a ação realizada
        if tool_used and tool_used != "Nenhuma ferramenta":
            action_info = [f"## Ação Realizada\nFerramenta: {tool_used}\nParâmetros: {tool_params_dict}"]

            # Adiciona análise específica para a ferramenta se disponível
            if PROMPT_UTILS_AVAILABLE:
                tool_prompts = create_tool_specific_prompts()
                if tool_used in tool_prompts and "post_execution" in tool_prompts[tool_used]:
                    # Prepara os parâmetros para formatação
                    format_params = {"result": tool_output}
                    if tool_used == "WebNavigatorTool" and tool_params_dict:
                        format_params["url"] = tool_params_dict.get("url", "")
                        # Tenta extrair o título da página do resultado
                        page_title_match = re.search(r"Título:\s*([^\.]+)", tool_output)
                        format_params["page_title"] = page_title_match.group(1) if page_title_match else "desconhecido"
                    elif tool_used == "WebInteractorTool" and tool_params_dict:
                        format_params["action"] = tool_params_dict.get("action", "")
                        format_params["selector"] = tool_params_dict.get("selector", "")

                    # Formata e adiciona o prompt específico
                    tool_analysis = tool_prompts[tool_used]["post_execution"].format(**format_params)
                    action_info.append(f"## Análise da Ferramenta\n{tool_analysis}")
        else:
            action_info = ["## Ação Realizada\nNenhuma ferramenta foi utilizada."]

        # Resultado obtido
        result_info = [f"## Resultado Obtido\n{tool_output}"]

        # Contexto da memória, se disponível
        memory_sections = []
        if self.memory:
            # Usa get_formatted_context para obter o contexto relevante da memória
            # Limita o tamanho do contexto para o resumo (menor que o planejamento)
            context_tokens = int(self.max_prompt_tokens * 0.2) # Reserva 20% para contexto
            memory_context = self.memory.get_formatted_context(max_tokens=context_tokens)
            if memory_context and memory_context != "Nenhum contexto disponível na memória.":
                memory_sections.append(f"## Contexto da Memória Recente\n{memory_context}")

        # Instruções para a resposta
        instructions = [
            "## Instruções para Resposta",
            "1. Avalie se a tarefa foi concluída com sucesso, parcialmente ou falhou.",
            "2. Se houve erro, explique brevemente o problema encontrado e sugira possíveis causas ou correções.",
            "3. Se foi bem-sucedida, descreva exatamente o que foi realizado e o resultado obtido.",
            "4. Se aplicável, sugira o próximo passo lógico para a sequência de tarefas.",
            "5. Registre recomendações para execuções futuras, se identificar padrões de erro ou sucesso.",
            "6. Mantenha sua resposta concisa, direta e informativa (máximo 2-3 frases).",
            "",
            "## Exemplos de Resposta:",
            "- Sucesso: 'O campo Empresa foi preenchido corretamente e o formulário avançou para o próximo passo.'",
            "- Falha: 'Erro ao localizar o seletor #empresa. O campo não estava visível após o carregamento da página. Recomenda-se aguardar mais tempo ou revisar o seletor.'",
            "- Parcial: 'O modo escuro foi ativado, mas o campo de email não pôde ser preenchido. Verifique se o campo está disponível após a troca de tema.'"
        ]

        # Combina todas as seções
        all_sections = base_info + action_info + result_info + memory_sections + instructions
        prompt = "\n\n".join(all_sections)

        # Otimiza o prompt se o módulo estiver disponível
        if PROMPT_UTILS_AVAILABLE:
            # Seções prioritárias que devem ser mantidas
            keep_sections = [
                "Resultado Obtido",
                "Contexto da Tarefa",
                "Ação Realizada",
                "Análise da Ferramenta",
                "Instruções para Resposta",
                "Contexto da Memória Recente" # Mantém a seção de contexto
            ]

            # Determina o modelo a ser usado
            model = self.llm_manager.default_model if hasattr(self.llm_manager, 'default_model') else "gpt-3.5-turbo"

            # Limita o tamanho do prompt para análise (um pouco menor que o planning)
            summary_max_tokens = int(self.max_prompt_tokens * 0.75)  # 75% do tamanho máximo

            return optimize_prompt_for_tokens(
                prompt=prompt,
                available_tokens=summary_max_tokens,
                model=model,
                keep_sections=keep_sections
            )

        return prompt

    async def execute(self, input_text: str, dependencies_results: Optional[List[str]] = None, page: Optional[Page] = None) -> str:
        """Executa uma tarefa: 1. LLM planeja. 2. Parse. 3. Executa ferramenta. 4. LLM resume."""
        logger.info(f"[{self.name}] Iniciando tarefa: {input_text[:100]}...")

        # --- Passo 1: LLM planeja a ação --- 
        planning_prompt = self._create_planning_prompt(input_text, dependencies_results)
        logger.info(f"[{self.name}] Enviando prompt de planejamento para o LLM...")
        llm_plan_response = await self.llm_manager.generate(planning_prompt)
        logger.info(f"[{self.name}] Resposta bruta do planejamento do LLM: {llm_plan_response[:150]}...")

        # *** VERIFICAÇÃO DE ERRO IMEDIATA DO LLM ***
        if llm_plan_response.startswith("Erro:") or "Erro na geração" in llm_plan_response:
            logger.error(f"[{self.name}] Erro direto do LLM Manager no planejamento: {llm_plan_response}")
            if self.memory:
                memory_content = f"Tarefa: {input_text}\nErro LLM (Planejamento): {llm_plan_response}"
                self.memory.add(item_type="error", content=memory_content, metadata={"agent": self.name})
            return llm_plan_response # Retorna o erro

        # --- Passo 2: Parse da resposta do LLM --- 
        tool_name, tool_params_dict = self._parse_llm_response(llm_plan_response)

        # Verifica se o parse falhou
        if tool_name is None:
            error_msg = f"Erro: Falha ao parsear a decisão do LLM. Resposta original: {llm_plan_response}"
            logger.error(f"[{self.name}] {error_msg}")
            if self.memory:
                memory_content = f"Tarefa: {input_text}\nErro Parse: {error_msg}"
                self.memory.add(item_type="error", content=memory_content, metadata={"agent": self.name})
            # Decide se retorna o erro ou tenta resumir a falha?
            # Por enquanto, retorna o erro.
            return error_msg
        
        # --- Passo 3: Executar a Ferramenta (se aplicável) ---
        tool_output = f"Nenhuma ferramenta necessária conforme planejado pelo LLM para: {input_text}"
        if tool_name.lower() != "nenhuma ferramenta":
            if tool_name not in self.tools:
                tool_output = f"Erro: LLM sugeriu ferramenta desconhecida: '{tool_name}'. Ferramentas disponíveis: {list(self.tools.keys())}"
                logger.error(f"[{self.name}] {tool_output}")
            else:
                tool_to_run = self.tools[tool_name]
                logger.info(f"[{self.name}] Executando ferramenta '{tool_name}' com parâmetros: {tool_params_dict}")
                try:
                    kwargs_for_tool = {}
                    # Adaptação específica para ferramentas conhecidas
                    if tool_name == "WebInteractorTool":
                        if not page:
                            raise ValueError(f"Erro: Ferramenta '{tool_name}' requer uma instância de página ativa.")
                        action_details_json_str = json.dumps(tool_params_dict) 
                        kwargs_for_tool = {
                            "page": page,
                            "action_details_json": action_details_json_str,
                            # Passa retries do dict se existirem, senão usa padrão da ferramenta
                            "max_retries": tool_params_dict.get("max_retries", 2),
                            "retry_delay": tool_params_dict.get("retry_delay", 2)
                        }
                    elif tool_name == "WebNavigatorTool":
                        url_from_params = tool_params_dict.get("url")
                        if not url_from_params:
                             raise ValueError("Erro: Parâmetro 'url' não fornecido para WebNavigatorTool.")
                        kwargs_for_tool = {
                            "url": url_from_params,
                            "page_instance": page,
                            "max_retries": tool_params_dict.get("max_retries", 3),
                            "retry_delay": tool_params_dict.get("retry_delay", 5),
                            "wait_for_selector": tool_params_dict.get("wait_for_selector", "#empresa"),
                            "timeout_goto": tool_params_dict.get("timeout_goto", 90000),
                            "timeout_selector": tool_params_dict.get("timeout_selector", 30000),
                            "headless": tool_params_dict.get("headless", False) # Usa o valor do dict ou False
                        }
                    else:
                        # Para outras ferramentas, passa os parâmetros diretamente
                        # CUIDADO: Isso assume que os parâmetros no dict correspondem aos args da ferramenta
                        kwargs_for_tool = tool_params_dict

                    # Executa a ferramenta
                    tool_output = await tool_to_run.run(**kwargs_for_tool)
                    logger.info(f"[{self.name}] Saída da ferramenta '{tool_name}': {str(tool_output)[:150]}...")

                    # ** TRATAMENTO ESPECIAL PARA WebNavigatorTool **
                    # Se WebNavigatorTool retornar um dict, significa que ele gerenciou a página.
                    # A Crew precisa dessa informação para atualizar sua instância de página.
                    if tool_name == "WebNavigatorTool" and isinstance(tool_output, dict):
                        # Não resumimos, apenas retornamos o dict para a Crew
                        logger.info(f"[{self.name}] WebNavigatorTool retornou dict. Repassando para Crew.")
                        # Adiciona info à memória antes de retornar
                        if self.memory:
                             memory_content = f"Tarefa: {input_text}\nAção: Navegação para {tool_params_dict.get('url')}\nResultado: {tool_output.get('result_message')}"
                             self.memory.add(item_type="navigation_success", content=memory_content, metadata={"agent": self.name})
                        return tool_output

                except Exception as exec_err:
                    error_msg = f"Erro Crítico durante a execução da ferramenta '{tool_name}' com parâmetros '{tool_params_dict}'. Erro: {type(exec_err).__name__} - {str(exec_err)}"
                    logger.exception(f"[{self.name}] {error_msg}") # Loga com stack trace
                    tool_output = error_msg # Armazena o erro para o resumo
                    if self.memory:
                         self.memory.add(item_type="error", content=error_msg, metadata={"agent": self.name, "tool": tool_name, "params": tool_params_dict})
                    # Considerar retornar o erro diretamente aqui se for crítico?
                    # Por ora, deixamos o LLM resumir o erro.

        # --- Passo 4: LLM resume o resultado (se não for WebNavigator retornando dict) ---
        # Garante que tool_output seja string para o resumo
        tool_output_str = str(tool_output)
        
        # Otimiza o output se for muito grande ANTES de enviar para resumo
        llm_model = self.llm_manager.default_model if hasattr(self.llm_manager, 'default_model') else "gpt-3.5-turbo"
        if PROMPT_UTILS_AVAILABLE:
            tool_output_tokens = calculate_token_count(tool_output_str, model=llm_model)
            # Limite um pouco menor para resumo
            max_output_tokens = int(self.max_prompt_tokens * 0.5)
            if tool_output_tokens > max_output_tokens:
                logger.warning(f"[{self.name}] Output da ferramenta muito longo ({tool_output_tokens} tokens). Truncando para resumo.")
                tool_output_str = truncate_text_to_tokens(tool_output_str, max_output_tokens, model=llm_model)
                
        final_response = await self.summarize(input_text, tool_name, tool_params_dict, tool_output_str)
        
        # Armazena na memória o resumo final
        if self.memory:
            memory_action = f"Ferramenta: {tool_name}, Params: {tool_params_dict}" if tool_name.lower() != "nenhuma ferramenta" else "Nenhuma ferramenta usada"
            item_type = "action_summary" if not tool_output_str.startswith("Erro:") and not final_response.startswith("Erro:") else "error_summary"
            memory_content = f"Tarefa: {input_text}\nAção: {memory_action}\nResultado Bruto (truncado se longo): {tool_output_str}\nResumo LLM: {final_response}"
            self.memory.add(item_type=item_type, content=memory_content, metadata={"agent": self.name})
            
        logger.info(f"[{self.name}] Tarefa concluída. Resumo: {final_response[:150]}...")
        return final_response

    # Adiciona um método interno para parsear a resposta, que pode ser chamado por execute
    def _parse_llm_response(self, llm_response: str) -> tuple[Optional[str], Optional[Dict[str, Any]]]:
        """Interpreta a resposta JSON do LLM para obter nome da ferramenta e parâmetros."""
        try:
            # Tenta extrair o bloco JSON da resposta
            json_match = re.search(r'\{.*\}', llm_response, re.DOTALL)
            if not json_match:
                raise ValueError("Nenhum bloco JSON encontrado na resposta do LLM.")

            json_string = json_match.group(0)
            parsed_plan = json.loads(json_string)
            # Log em português
            print(f"[{self.name}] JSON extraído e parseado com sucesso: {parsed_plan}")

            tool_name = parsed_plan.get("tool_name")
            tool_params_dict = parsed_plan.get("parameters")

            if not tool_name:
                raise ValueError("Chave 'tool_name' não encontrada no JSON retornado pelo LLM.")
            
            # Garante que parameters seja um dict, mesmo que vazio
            if tool_params_dict is None:
                tool_params_dict = {}
            elif not isinstance(tool_params_dict, dict):
                raise ValueError("Chave 'parameters' no JSON não é um dicionário.")

            return tool_name, tool_params_dict

        except json.JSONDecodeError as json_err:
            error_msg = f"Erro Crítico: Falha ao decodificar o JSON extraído da resposta do LLM ('{json_string}'). Erro: {json_err}"
            print(f"[{self.name}] {error_msg}")
            # Retorna None para indicar falha no parse
            return None, None
        except ValueError as val_err:
            error_msg = f"Erro Crítico: Problema ao validar o plano retornado pelo LLM. Erro: {val_err}"
            print(f"[{self.name}] {error_msg}\nResposta original do LLM: {llm_response}")
            return None, None
        except Exception as e:
            error_msg = f"Erro inesperado ao parsear resposta LLM: {type(e).__name__} - {str(e)}"
            print(f"[{self.name}] {error_msg}")
            return None, None

    # Método de resumo separado
    async def summarize(self, input_text: str, tool_used: Optional[str], tool_params_dict: Optional[Dict[str, Any]], tool_output: str) -> str:
        """Gera um resumo do resultado da ação usando o LLM."""
        summary_prompt = self._create_summary_prompt(input_text, tool_used, tool_params_dict, tool_output)
        # Log em português
        print(f"[{self.name}] Enviando prompt de resumo para o LLM via Manager...")
        summary_response = await self.llm_manager.generate(summary_prompt)
        return summary_response

    async def execute_chaining(self, input_text: str, max_steps: int = 5) -> str:
        """Executa uma tarefa usando execução em cadeia, onde uma ferramenta leva à outra."""
        logger.info(f"Iniciando execução em cadeia para: {input_text}")
        
        current_input = input_text
        results = []
        
        for step in range(max_steps):
            logger.info(f"Passo {step+1}/{max_steps}: Executando subtarefa")
            try:
                # Executa um passo individual
                result = await self.execute(current_input)
                results.append(result)
                
                # Prepara prompt para o próximo passo
                if PROMPT_UTILS_AVAILABLE:
                    # Otimiza a entrada para o próximo passo
                    next_step_prompt = (
                        f"Baseado no resultado anterior: '{result}', "
                        f"determine a próxima ação necessária para completar a tarefa original: '{input_text}'. "
                        f"Se a tarefa foi concluída, indique que nenhuma ferramenta é necessária."
                    )
                    
                    # Limita o tamanho do prompt se necessário
                    model = self.llm_manager.default_model if hasattr(self.llm_manager, 'default_model') else "gpt-3.5-turbo"
                    if calculate_token_count(next_step_prompt, model) > self.max_prompt_tokens * 0.7:
                        next_step_prompt = truncate_text_to_tokens(
                            next_step_prompt, 
                            int(self.max_prompt_tokens * 0.7),
                            model=model
                        )
                    current_input = next_step_prompt
                else:
                    # Prompt simples sem otimização
                    current_input = f"Baseado no resultado: '{result}', qual deve ser a próxima ação para '{input_text}'?"
                
                # Verifica se a tarefa foi concluída
                completion_indicators = ["concluída", "finalizada", "completa", "realizada", "executada"]
                if any(indicator in result.lower() for indicator in completion_indicators):
                    logger.info("Tarefa em cadeia concluída com sucesso")
                    break
                    
            except Exception as e:
                error_msg = f"Erro no passo {step+1}: {str(e)}"
                logger.error(error_msg)
                results.append(error_msg)
                break
        
        # Gera um resumo de toda a execução em cadeia
        if self.llm_manager:
            try:
                steps_summary = "\n".join([f"Passo {i+1}: {r}" for i, r in enumerate(results)])
                resumo_prompt = (
                    f"# Resumo de Execução em Cadeia\n\n"
                    f"## Tarefa Original\n{input_text}\n\n"
                    f"## Passos Executados\n{steps_summary}\n\n"
                    f"## Instrução\nResuma os passos acima em um parágrafo conciso, descrevendo o que foi realizado."
                )
                
                # Otimiza o prompt final
                if PROMPT_UTILS_AVAILABLE:
                    model = self.llm_manager.default_model if hasattr(self.llm_manager, 'default_model') else "gpt-3.5-turbo"
                    context_window = get_model_context_window(model)
                    # Usa 80% da janela para o prompt (reserva 20% para resposta)
                    max_prompt_size = int(context_window * 0.8)
                    
                    resumo_prompt = optimize_prompt_for_tokens(
                        resumo_prompt, 
                        available_tokens=max_prompt_size,
                        model=model,
                        keep_sections=["Tarefa Original", "Instrução"]
                    )
                
                final_summary = await self.llm_manager.generate(resumo_prompt)
                return final_summary
            except Exception as e:
                logger.error(f"Erro ao gerar resumo final: {str(e)}")
        
        # Retorna a concatenação dos resultados se não conseguir gerar um resumo
        return "\n".join(results)

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
        self.tasks = tasks
        self._task_results: Dict[Task, Any] = {}
        self.browser: Optional[Browser] = None
        self.page: Optional[Page] = None
        self._playwright = None
        # Define o diretório de download para a pasta 'output' dentro do projeto
        self.download_dir = os.path.join(os.getcwd(), "output") # Usa getcwd() para garantir que é relativo à raiz do projeto
        os.makedirs(self.download_dir, exist_ok=True) # Garante que o diretório exista

    async def setup_browser(self, headless: bool = True):
        # Log em português
        print("[Crew] Configurando o navegador Playwright...")
        try:
            self._playwright = await async_playwright().start()
            
            # Configuração melhorada para visualização
            launch_args = ['--start-maximized']
            if not headless:
                # Adiciona argumentos extras para melhorar a visualização no modo não-headless
                launch_args.extend(['--window-position=50,50'])
            
            self.browser = await self._playwright.chromium.launch(
                headless=headless, 
                args=launch_args
            )
            
            self.page = await self.browser.new_page()
            
            # Define viewport grande para melhor visualização
            await self.page.set_viewport_size({"width": 1280, "height": 800})
            
            # Mensagem em português
            print("[Crew] Navegador e página configurados com sucesso (e maximizada).")
        except Exception as e:
            # Mensagem em português
            print(f"[Crew] Erro crítico ao configurar o navegador: {e}")
            await self.close_browser()
            raise

    async def close_browser(self):
        # Log em português
        print("[Crew] Fechando o navegador Playwright...")
        if self.page and not self.page.is_closed():
            # Mensagem em português
            try: await self.page.close(); print("[Crew] Página fechada.")
            except Exception as e: print(f"[Crew] Erro ao fechar a página: {e}")
        if self.browser and self.browser.is_connected():
            # Mensagem em português
            try: await self.browser.close(); print("[Crew] Navegador fechado.")
            except Exception as e: print(f"[Crew] Erro ao fechar o navegador: {e}")
        if self._playwright:
             try:
                 await self._playwright.stop()
                 # Mensagem em português
                 print("[Crew] Playwright parado.")
             except Exception as e: print(f"[Crew] Erro ao parar Playwright: {e}")
        self.page = None; self.browser = None; self._playwright = None
        # Mensagem em português
        print("[Crew] Limpeza do navegador concluída.")

    async def _execute_task(self, task: Task, page: Optional[Page]) -> Optional[str]:
        """Executa uma única tarefa usando o agente designado e atualiza a página se necessário."""
        if task.executed:
            logger.info(f"Tarefa '{task.description}' já executada. Resultado: {task.result}")
            return task.result

        # Verifica dependências
        dependencies_ready = all(dep.executed for dep in task.dependencies)
        if not dependencies_ready:
            failed_deps = [dep.description for dep in task.dependencies if not dep.executed]
            error_msg = f"Erro: Tarefa '{task.description}' adiada. Dependências não concluídas: {failed_deps}"
            logger.warning(error_msg)
            # Não marca como executada, mas retorna o erro para sinalizar
            return error_msg
        
        # Verifica se alguma dependência falhou
        failed_dependency_results = [dep.result for dep in task.dependencies if dep.executed and str(dep.result).startswith("Erro:")]
        if failed_dependency_results:
            error_msg = f"Erro: Tarefa '{task.description}' não pode ser executada devido a falha nas dependências: {failed_dependency_results}"
            logger.error(error_msg)
            task.result = error_msg
            task.executed = True # Marca como executada com erro
            self._task_results[task] = error_msg
            return error_msg

        logger.info(f"Iniciando execução da tarefa: '{task.description}' pelo agente {task.agent.name}")
        dependencies_results = task.get_dependencies_results()

        try:
            # Chama o método execute do agente, passando a página atual
            # O agente agora é responsável por todo o fluxo (planejar, executar, resumir)
            # A única exceção é WebNavigatorTool, que retorna um dict especial
            result = await task.agent.execute(task.description, dependencies_results, page)

            # Verifica se o resultado é um dicionário (caso especial do WebNavigatorTool)
            if isinstance(result, dict) and 'page' in result and 'result_message' in result:
                logger.info(f"Tarefa '{task.description}': WebNavigatorTool atualizou a instância da página.")
                # Atualiza a página da Crew com a nova instância retornada pela ferramenta
                self.page = result['page']
                # Usa a mensagem do dicionário como resultado da tarefa
                task.result = result['result_message']
            else:
                # Para todos os outros casos, o resultado é o resumo final do agente
                task.result = result

            task.executed = True
            self._task_results[task] = task.result # Armazena o resultado final

            if isinstance(task.result, str) and task.result.startswith("Erro:"):
                logger.error(f"Tarefa '{task.description}' concluída com erro: {task.result}")
                return task.result # Retorna o erro
            else:
                logger.info(f"Tarefa '{task.description}' concluída com sucesso. Resultado: {str(task.result)[:100]}...")
                return task.result # Retorna o resultado de sucesso

        except Exception as e:
            error_message = f"Erro crítico inesperado ao executar a tarefa '{task.description}': {type(e).__name__} - {e}"
            logger.exception(error_message) # Loga o stack trace
            task.result = error_message
            task.executed = True # Marca como executada com erro
            self._task_results[task] = error_message
            return error_message
    
    async def run(self, headless: bool = True):
        """Executa todas as tarefas em ordem sequencial, respeitando dependências e tratando downloads."""
        print("--- Iniciando execução da Crew (Modo Sequencial) ---")
        final_results = {}
        try:
            await self.setup_browser(headless=headless)
            if not self.browser or not self.page:
                print("[Crew] Erro fatal: Navegador não configurado.")
                return None

            print("[Crew] Executando tarefas sequencialmente...")
            for task in self.tasks:
                print(f"\n[Crew] Iniciando processamento da tarefa: {task.description}")

                # *** DEBUG LOGGING ADICIONADO ***
                logger.info(f"[DEBUG] Verificando condição de download para tarefa: '{task.description[:100]}...'")
                desc_lower = task.description.lower()
                check1 = "gerar o pdf" in desc_lower
                check2 = "orçamento" in desc_lower
                is_download_task = check1 and check2
                logger.info(f"[DEBUG] '{desc_lower[:100]}...' - check1 ('gerar o pdf'): {check1}, check2 ('orçamento'): {check2} -> is_download_task: {is_download_task}")
                # *** FIM DEBUG LOGGING ***
                
                # Verifica se esta é a tarefa que dispara o download
                task_result = None
                if is_download_task:
                    # *** CORREÇÃO LÓGICA: Executar a tarefa DENTRO do expect_download ***
                    logger.info(f"Tarefa '{task.description}' identificada como gatilho de download.") # Esta mensagem deve aparecer se is_download_task for True
                    try:
                        async with self.page.expect_download(timeout=120000) as download_info: # Timeout aumentado para 120s
                            logger.info("[Crew] Aguardando clique para iniciar download...")
                            # Executa a tarefa que clica no botão AQUI DENTRO
                            task_result = await self._execute_task(task, self.page)
                            
                            # Se a execução da tarefa falhou, o erro já foi logado e task.result definido
                            # O bloco expect_download será encerrado e podemos verificar o erro abaixo
                            if isinstance(task_result, str) and task_result.startswith("Erro:"):
                                logger.error(f"[Crew] Tarefa '{task.description}' (gatilho de download) falhou durante execução.")
                                # O erro já está em task.result, não precisa fazer nada extra aqui
                            else:
                                logger.info(f"[Crew] Clique da tarefa '{task.description}' realizado. Aguardando início do download...")

                        # Se chegamos aqui sem TimeoutError do expect_download, o download iniciou.
                        # Verifica se a execução da tarefa NÃO retornou erro ANTES de processar o download.
                        if not (isinstance(task.result, str) and task.result.startswith("Erro:")):
                            download = await download_info.value
                            suggested_filename = download.suggested_filename
                            save_path = os.path.join(self.download_dir, suggested_filename)
                            logger.info(f"[Crew] Download detectado: {suggested_filename}. Salvando em: {save_path}")
                            await download.save_as(save_path)
                            
                            success_message = f"PDF do orçamento gerado e salvo com sucesso em: {save_path}"
                            task.result = success_message # Sobrescreve o resultado do clique com o sucesso do download
                            task.executed = True
                            self._task_results[task] = success_message
                            logger.info(f"[Crew] {success_message}")
                        # Se task.result já era um erro, ele será mantido e verificado no final do loop.

                    except TimeoutError as download_timeout:
                        # Este erro acontece se o download NÃO INICIOU dentro dos 60s após o clique
                        error_msg = f"Erro: Timeout esperado pelo download após executar a tarefa '{task.description}'. O clique pode não ter iniciado o download ou demorou >60s."
                        logger.error(f"[Crew] {error_msg}")
                        # Garante que a tarefa seja marcada com erro
                        if not (isinstance(task.result, str) and task.result.startswith("Erro:")):
                            task.result = error_msg 
                        task.executed = True 
                        self._task_results[task] = task.result
                    except Exception as download_err:
                        error_msg = f"Erro inesperado durante o processo de download para a tarefa '{task.description}': {type(download_err).__name__} - {str(download_err)}"
                        logger.exception(f"[Crew] {error_msg}")
                        if not (isinstance(task.result, str) and task.result.startswith("Erro:")):
                            task.result = error_msg
                        task.executed = True
                        self._task_results[task] = task.result
                else:
                    # Se não for a tarefa de download, executa normalmente
                    task_result = await self._execute_task(task, self.page)

                # Adiciona uma pausa visual entre as tarefas
                if not headless:
                    await asyncio.sleep(1)
                    
                # Verifica se a tarefa atual falhou para decidir se continua
                if isinstance(task.result, str) and task.result.startswith("Erro:"):
                    logger.error(f"[Crew] ERRO CRÍTICO na tarefa: \n'{task.description}'. \nResultado: {task.result}. \nInterrompendo a execução da Crew.")
                    break

            print("\n--- Execução das Tarefas Concluída ---")
            final_results = {task.description: self._task_results.get(task, "Erro: Tarefa não registrada nos resultados") for task in self.tasks}
            return final_results
        except Exception as e:
             print(f"[Crew] Erro crítico durante a execução da Crew: {e}")
             import traceback; traceback.print_exc()
             return None
        finally:
            await self.close_browser()
            print("--- Execução da Crew Finalizada (navegador fechado) ---") 