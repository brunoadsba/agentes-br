import asyncio
import json
from playwright.async_api import Page, Error
from core.models import BaseTool

class WebInteractorTool(BaseTool):
    """Interage com elementos da página (fill, click, select_option)."""
    async def run(self, page: Page, action_details_json: str) -> str:
        if not page or page.is_closed(): return "Erro Crítico: Página inválida ou fechada."
        print(f"[WebInteractorTool] Recebido JSON: {action_details_json}")
        try:
            params = json.loads(action_details_json)
            action = params.get("action", "").lower()
            selector = params.get("selector")
            if not action or not selector: return "Erro: JSON inválido (action/selector obrigatórios)."

            if action == "fill":
                value = params.get("value")
                if value is None: return "Erro: Ação 'fill' requer 'value' no JSON."
                print(f"[WebInteractorTool] Preenchendo '{selector}' com '{value}'")
                await page.locator(selector).fill(value, timeout=30000)
                return f"Campo '{selector}' preenchido."
            
            elif action == "click":
                print(f"[WebInteractorTool] Clicando em '{selector}'")
                await page.locator(selector).click(timeout=30000)
                return f"Elemento '{selector}' clicado."
            
            elif action == "select_option":
                # Aceita 'label' ou 'value' para seleção
                label_to_select = params.get("label") or params.get("value") 
                if label_to_select is None:
                    return "Erro: Ação 'select_option' requer 'label' ou 'value' no JSON."
                print(f"[WebInteractorTool] Selecionando '{label_to_select}' em '{selector}'")
                await page.select_option(selector, label=label_to_select, timeout=30000)
                return f"Opção '{label_to_select}' selecionada em '{selector}'."
            
            else:
                return f"Erro: Ação '{action}' não suportada."
        
        except json.JSONDecodeError:
            return f"Erro: Falha ao decodificar JSON: {action_details_json}"
        except Error as pe: # Captura erros específicos do Playwright (ex: Timeout)
            error_message = f"Erro Playwright ({action} em {selector}): {type(pe).__name__} - {str(pe)}"
            print(f"[WebInteractorTool] {error_message}")
            return error_message
        except Exception as e:
            error_message = f"Erro Inesperado ({action} em {selector}): {type(e).__name__} - {str(e)}"
            print(f"[WebInteractorTool] {error_message}")
            return error_message

# Nota: O bloco de teste __main__ foi omitido aqui pois requereria
# um setup complexo para passar uma instância de 'page' válida.
# O teste real será feito integrando esta ferramenta no fluxo do agente.
