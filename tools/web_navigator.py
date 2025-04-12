import asyncio
from playwright.async_api import async_playwright, Page, Error
from typing import Optional
from core.models import BaseTool

class WebNavigatorTool(BaseTool):
    """Navega para URL, reutilizando página se fornecida."""
    async def run(self, url: str, page_instance: Optional[Page] = None) -> str:
        print(f"[WebNavigatorTool] Tentando navegar para: {url}")
        page_to_use: Optional[Page] = page_instance
        browser_created_locally = False
        playwright_context = None
        local_browser = None
        try:
            if not page_to_use or page_to_use.is_closed():
                print("[WebNavigatorTool] Criando navegador temporário.")
                browser_created_locally = True
                playwright_context = await async_playwright().start()
                local_browser = await playwright_context.chromium.launch(headless=True)
                page_to_use = await local_browser.new_page()
                if not page_to_use: raise Error("Falha ao criar página.")
            print(f"[WebNavigatorTool] Iniciando goto para {url} (wait_until='networkidle')")
            await page_to_use.goto(url, timeout=90000, wait_until='networkidle')
            print(f"[WebNavigatorTool] goto concluído. Esperando campo #empresa...")
            await page_to_use.locator("#empresa").wait_for(state='visible', timeout=30000)
            print(f"[WebNavigatorTool] Campo #empresa visível.")
            page_title = await page_to_use.title()
            result_message = f"Navegação para {url} OK. Título: {page_title}"
            print(f"[WebNavigatorTool] {result_message}")
            return result_message
        except Error as pe:
            error_message = f"Erro Playwright: {type(pe).__name__} - {str(pe)}"
            print(f"[WebNavigatorTool] {error_message}")
            return error_message
        except Exception as e:
            error_message = f"Erro Inesperado: {type(e).__name__} - {str(e)}"
            print(f"[WebNavigatorTool] {error_message}")
            return error_message
        finally:
            # Fecha o navegador SOMENTE se foi criado localmente nesta execução
            if browser_created_locally:
                print("[WebNavigatorTool] Fechando navegador temporário.")
                # Corrigido: Bloco try/except indentado corretamente
                if page_to_use and not page_to_use.is_closed():
                    try:
                        await page_to_use.close()
                    except Exception:
                        pass # Ignora erros ao fechar página temporária
                if local_browser and local_browser.is_connected():
                     try:
                         await local_browser.close()
                     except Exception:
                         pass # Ignora erros ao fechar browser temporário
                if playwright_context:
                     try:
                         await playwright_context.stop()
                     except Exception:
                         pass # Ignora erros ao parar contexto temporário

# Exemplo de uso (para teste direto do arquivo, se necessário)
async def test_navigation():
    tool = WebNavigatorTool()
    # Teste com um site diferente do alvo final para verificar a ferramenta isoladamente
    result = await tool.run("https://example.com")
    print(result)

if __name__ == "__main__":
    # Adiciona o diretório raiz ao PYTHONPATH para encontrar core.models
    import sys
    import os
    sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
    # Chama a função definida acima
    asyncio.run(test_navigation())