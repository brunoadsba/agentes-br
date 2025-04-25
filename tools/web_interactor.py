import asyncio
import json
from playwright.async_api import Page, Error, TimeoutError
from core.models import BaseTool

class WebInteractorTool(BaseTool):
    """Interage com elementos da página (fill, click, select_option)."""
    async def run(self, page: Page, action_details_json: str, max_retries: int = 2, retry_delay: int = 2) -> str:
        if not page or page.is_closed(): 
            return "Erro Crítico: Página inválida ou fechada."
        
        print(f"[WebInteractorTool] Recebido JSON: {action_details_json}")
        
        # Variáveis para controlar o fluxo de tentativas e armazenar informações de erro
        action = None
        selector = None
        last_error = None
        
        try:
            # Validação inicial do JSON
            params = json.loads(action_details_json)
            action = params.get("action", "").lower()
            selector = params.get("selector")
            if not action or not selector: 
                return "Erro: JSON inválido (action/selector são campos obrigatórios)."
            
            # Função auxiliar para fazer scroll e destacar o elemento
            async def scroll_to_and_highlight(selector):
                # Pula o JS se for um seletor avançado do Playwright
                if ":" in selector and ("text=" in selector or "has-text" in selector or "text-matches" in selector):
                    print(f"[WebInteractorTool] Aviso: Pulando scroll/destaque JS para seletor Playwright: {selector}")
                    return True # Assume sucesso para não bloquear
                try:
                    # Verifica se o elemento existe
                    element = await page.query_selector(selector)
                    if not element:
                        print(f"[WebInteractorTool] Elemento '{selector}' não encontrado para scroll.")
                        return False
                    
                    # Scroll para o elemento
                    print(f"[WebInteractorTool] Fazendo scroll para o elemento '{selector}'")
                    await page.evaluate(f"""(selector) => {{
                        const element = document.querySelector(selector);
                        if (element) {{
                            // Scroll com margem para cima para melhor visualização
                            element.scrollIntoView({{ behavior: 'smooth', block: 'center' }});
                        }}
                    }}""", selector)
                    
                    # Destaca o elemento visualmente
                    await page.evaluate(f"""(selector) => {{
                        const element = document.querySelector(selector);
                        if (element) {{
                            // Salva o estilo original
                            element.setAttribute('data-original-style', element.style.cssText);
                            
                            // Aplica destaque
                            element.style.boxShadow = '0 0 0 3px rgba(66, 153, 225, 0.6)';
                            element.style.transition = 'box-shadow 0.3s ease';
                        }}
                    }}""", selector)
                    
                    # Pequena pausa para o usuário ver o destaque
                    await asyncio.sleep(0.5)
                    return True
                except Exception as e:
                    print(f"[WebInteractorTool] Erro ao fazer scroll/destacar: {str(e)}")
                    return False
            
            # Função auxiliar para remover o destaque
            async def remove_highlight(selector):
                # Pula o JS se for um seletor avançado do Playwright
                if ":" in selector and ("text=" in selector or "has-text" in selector or "text-matches" in selector):
                    # Não precisa fazer nada aqui, apenas evita o erro
                    return
                try:
                    await page.evaluate(f"""(selector) => {{
                        const element = document.querySelector(selector);
                        if (element) {{
                            // Restaura o estilo original
                            const originalStyle = element.getAttribute('data-original-style');
                            if (originalStyle) {{
                                element.style.cssText = originalStyle;
                            }} else {{
                                element.style.boxShadow = '';
                            }}
                        }}
                    }}""", selector)
                except Exception as e:
                    print(f"[WebInteractorTool] Erro ao remover destaque: {str(e)}")
            
            # Preparar parâmetros específicos por tipo de ação
            if action == "fill":
                value = params.get("value")
                if value is None: 
                    return "Erro: Ação 'fill' requer o campo 'value' no JSON."
                
                # Loop de tentativas para fill
                for attempt in range(max_retries):
                    try:
                        print(f"[WebInteractorTool] Tentativa {attempt+1}/{max_retries}: Preenchendo '{selector}' com '{value}'")
                        
                        # Scroll e destaque antes da interação
                        await scroll_to_and_highlight(selector)
                        
                        # Ação de preenchimento
                        await page.locator(selector).fill(value, timeout=30000)
                        
                        # Pausa para visualização
                        await asyncio.sleep(1)
                        
                        # Remove destaque
                        await remove_highlight(selector)
                        
                        return f"Campo '{selector}' preenchido com sucesso."
                    except TimeoutError as te:
                        last_error = te
                        print(f"[WebInteractorTool] TimeoutError na tentativa {attempt+1}: {str(te)}")
                        if attempt < max_retries - 1:
                            print(f"[WebInteractorTool] Aguardando {retry_delay}s antes da próxima tentativa...")
                            await asyncio.sleep(retry_delay)
                        else:
                            # Última tentativa falhou
                            error_msg = f"Erro: Falha ao preencher '{selector}' após {max_retries} tentativas. Elemento não encontrado ou não interagível."
                            print(f"[WebInteractorTool] {error_msg}")
                            return error_msg
                    except Error as pe:
                        # Outros erros do Playwright não requerem nova tentativa
                        error_msg = f"Erro ao preencher '{selector}': {type(pe).__name__} - {str(pe)}"
                        print(f"[WebInteractorTool] {error_msg}")
                        return error_msg
            
            elif action == "click":
                # Loop de tentativas para click
                for attempt in range(max_retries):
                    try:
                        print(f"[WebInteractorTool] Tentativa {attempt+1}/{max_retries}: Clicando em '{selector}'")
                        
                        # Scroll e destaque antes da interação
                        await scroll_to_and_highlight(selector)
                        
                        # Ação de clique
                        await page.locator(selector).click(timeout=30000)
                        
                        # Pausa para visualização
                        await asyncio.sleep(1)
                        
                        # Remove destaque (pode falhar após o clique, então ignoramos erros)
                        try:
                            await remove_highlight(selector)
                        except:
                            pass
                        
                        return f"Elemento '{selector}' clicado com sucesso."
                    except TimeoutError as te:
                        last_error = te
                        print(f"[WebInteractorTool] TimeoutError na tentativa {attempt+1}: {str(te)}")
                        if attempt < max_retries - 1:
                            print(f"[WebInteractorTool] Aguardando {retry_delay}s antes da próxima tentativa...")
                            await asyncio.sleep(retry_delay)
                        else:
                            # Última tentativa falhou
                            error_msg = f"Erro: Falha ao clicar em '{selector}' após {max_retries} tentativas. Elemento não encontrado ou não interagível."
                            print(f"[WebInteractorTool] {error_msg}")
                            return error_msg
                    except Error as pe:
                        # Outros erros do Playwright não requerem nova tentativa
                        error_msg = f"Erro ao clicar em '{selector}': {type(pe).__name__} - {str(pe)}"
                        print(f"[WebInteractorTool] {error_msg}")
                        return error_msg
            
            elif action == "select_option":
                # Aceita 'label' ou 'value' para seleção
                label_to_select = params.get("label") or params.get("value") 
                if label_to_select is None:
                    return "Erro: Ação 'select_option' requer 'label' ou 'value' no JSON."
                
                # Verificação especial para seleção de serviços para evitar "Serviço (2)"
                if selector == "#servico-1-nome" and label_to_select and "Serviço (2)" in label_to_select:
                    print(f"[WebInteractorTool] DETECTADO: Agente tentou selecionar '{label_to_select}' para o seletor '{selector}'. Aplicando correção para usar 'Elaboração e acompanhamento do PGR'.")
                    # Força para o serviço correto independentemente do que o LLM disse
                    label_to_select = "Elaboração e acompanhamento do PGR"
                    print(f"[WebInteractorTool] Forçando seleção para o serviço correto: '{label_to_select}'")
                
                # Loop de tentativas para select_option
                for attempt in range(max_retries):
                    try:
                        print(f"[WebInteractorTool] Tentativa {attempt+1}/{max_retries}: Selecionando '{label_to_select}' em '{selector}'")
                        
                        # *** ADICIONA ESPERA ANTES DE INTERAGIR COM DROPDOWNS CRÍTICOS ***
                        if selector in ["#servico-1-nome", "#grau-risco-1", "#numTrabalhadores-1", "#regiao-1"]:
                            print(f"[WebInteractorTool] Aguardando um pouco mais para o dropdown '{selector}' estabilizar...")
                            await asyncio.sleep(1.5) # Espera extra de 1.5s
                            # Poderia adicionar page.wait_for_selector(selector, state='visible', timeout=5000) aqui também
                            
                        # Scroll e destaque antes da interação (agora com verificação)
                        await scroll_to_and_highlight(selector)
                        
                        # Para seletores de serviço, tenta listar opções disponíveis primeiro
                        if selector == "#servico-1-nome":
                            try:
                                # Tenta obter as opções disponíveis para debug
                                options = await page.eval_on_selector_all(f"{selector} option", "options => options.map(o => o.text)")
                                print(f"[WebInteractorTool] Opções disponíveis no dropdown: {options}")
                                
                                # Se "Elaboração e acompanhamento do PGR" existir nas opções, força usar esse
                                if "Elaboração e acompanhamento do PGR" in options:
                                    label_to_select = "Elaboração e acompanhamento do PGR"
                                    print(f"[WebInteractorTool] Usando opção validada: '{label_to_select}'")
                            except Exception as e:
                                print(f"[WebInteractorTool] Não foi possível listar opções: {str(e)}")
                        
                        # Abre o dropdown para melhor visualização
                        try:
                            await page.click(selector, timeout=10000)
                            await asyncio.sleep(0.5)  # Pequena pausa para ver as opções
                        except:
                            print("[WebInteractorTool] Não foi possível abrir o dropdown visualmente")
                        
                        # Aumenta um pouco o timeout específico para select_option
                        await page.select_option(selector, label=label_to_select, timeout=40000) # Aumentado para 40s
                        
                        # Pausa para visualização
                        await asyncio.sleep(1)
                        
                        # Verifica se a seleção foi bem-sucedida
                        if selector == "#servico-1-nome":
                            try:
                                selected_value = await page.eval_on_selector(selector, "el => el.options[el.selectedIndex].text")
                                print(f"[WebInteractorTool] Valor realmente selecionado: '{selected_value}'")
                                
                                # Se ainda estiver com Serviço (2), tenta novamente com value em vez de label
                                if "Serviço (2)" in selected_value and "PGR" not in selected_value:
                                    print(f"[WebInteractorTool] Correção: Tentando selecionar por índice/valor em vez de texto")
                                    # Tenta encontrar o índice correto
                                    options = await page.eval_on_selector_all(f"{selector} option", 
                                        "options => options.map((o, i) => ({index: i, text: o.text}))")
                                    for option in options:
                                        if "PGR" in option.get("text", ""):
                                            print(f"[WebInteractorTool] Encontrado índice {option.get('index')} para PGR")
                                            await page.select_option(selector, index=option.get("index"), timeout=30000)
                                            break
                            except Exception as e:
                                print(f"[WebInteractorTool] Erro ao verificar seleção: {str(e)}")
                        
                        # Remove destaque
                        await remove_highlight(selector)
                        
                        return f"Opção '{label_to_select}' selecionada com sucesso em '{selector}'."
                    except Exception as e:
                        # Se for o dropdown problemático e a seleção por label falhou, tenta por valor
                        if selector == "#numTrabalhadores-1" and attempt < max_retries -1: # Tenta apenas se não for a última tentativa
                             print(f"[WebInteractorTool] Falha ao selecionar por label '{label_to_select}' (Tentativa {attempt+1}). Tentando por valor '{label_to_select}'...")
                             try:
                                 # Tenta selecionar usando o atributo 'value'
                                 await page.select_option(selector, value=label_to_select, timeout=20000) # Timeout menor para a retentativa
                                 await asyncio.sleep(1)
                                 await remove_highlight(selector)
                                 print(f"[WebInteractorTool] SUCESSO ao selecionar por valor '{label_to_select}' em '{selector}'.")
                                 return f"Opção '{label_to_select}' (via valor) selecionada com sucesso em '{selector}'."
                             except Exception as e_val:
                                 print(f"[WebInteractorTool] Falha também ao selecionar por valor '{label_to_select}'. Erro: {type(e_val).__name__}")
                                 # Continua para a próxima tentativa do loop externo se houver
                                 last_error = e # Mantém o erro original da seleção por label como principal
                        else:
                           last_error = e # Armazena o erro para possível log ou uso futuro
                           
                        # Log do erro específico da tentativa
                        print(f"[WebInteractorTool] Erro na tentativa {attempt+1} de selecionar '{label_to_select}' em '{selector}': {type(e).__name__}")
                        
                        # Se for a última tentativa, formata a mensagem de erro final e retorna
                        if attempt >= max_retries - 1:
                            error_msg = f"Erro: Falha ao selecionar '{label_to_select}' em '{selector}' após {max_retries} tentativas (label e valor, se aplicável). Dropdown ou opção indisponível/não interagível."
                            print(f"[WebInteractorTool] {error_msg} Último erro: {type(last_error).__name__}")
                            return error_msg
                        else:
                            # Aguarda antes da próxima tentativa do loop principal
                            print(f"[WebInteractorTool] Aguardando {retry_delay}s antes da próxima tentativa...")
                            await asyncio.sleep(retry_delay)
            
            else:
                error_msg = f"Erro: Ação '{action}' não suportada. Ações válidas: fill, click, select_option."
                print(f"[WebInteractorTool] {error_msg}")
                return error_msg
        
        except json.JSONDecodeError as jde:
            error_msg = f"Erro: Falha ao decodificar JSON. Input: '{action_details_json}'. Detalhes: {str(jde)}"
            print(f"[WebInteractorTool] {error_msg}")
            return error_msg
        except Exception as e:
            # Captura quaisquer outros erros inesperados
            error_msg = f"Erro inesperado ao processar ação '{action}' em '{selector}': {type(e).__name__} - {str(e)}"
            print(f"[WebInteractorTool] {error_msg}")
            return error_msg

# Nota: O bloco de teste __main__ foi omitido aqui pois requereria
# um setup complexo para passar uma instância de 'page' válida.
# O teste real será feito integrando esta ferramenta no fluxo do agente.
