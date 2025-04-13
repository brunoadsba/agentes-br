import asyncio
from playwright.async_api import async_playwright, Page, Error
from typing import Optional
from core.models import BaseTool

class WebNavigatorTool(BaseTool):
    """Navega para URL, reutilizando página se fornecida."""
    async def run(self, url: str, page_instance: Optional[Page] = None, max_retries: int = 3, retry_delay: int = 5) -> str:
        print(f"[WebNavigatorTool] Tentando navegar para: {url}")
        page_to_use: Optional[Page] = page_instance
        browser_created_locally = False
        playwright_context = None
        local_browser = None
        last_error = None
        result_message = None # Inicializa a mensagem de resultado

        # try...finally externo para garantir a limpeza
        try: 
            for attempt in range(max_retries):
                try:
                    # --- Configuração do Navegador/Página (dentro do loop se temporário) ---
                    if not page_to_use or page_to_use.is_closed():
                        print(f"[WebNavigatorTool Tentativa {attempt+1}/{max_retries}] Criando navegador temporário.")
                        # Fecha recursos temporários anteriores se existirem de uma tentativa falha
                        if browser_created_locally:
                            if page_to_use and not page_to_use.is_closed(): await page_to_use.close()
                            if local_browser and local_browser.is_connected(): await local_browser.close()
                            if playwright_context: await playwright_context.stop()
                            page_to_use = None; local_browser = None; playwright_context = None
                        
                        browser_created_locally = True
                        playwright_context = await async_playwright().start()
                        local_browser = await playwright_context.chromium.launch(headless=True)
                        page_to_use = await local_browser.new_page()
                        if not page_to_use: raise Error("Falha ao criar página.")
                    
                    # --- Navegação e Verificação ---
                    print(f"[WebNavigatorTool Tentativa {attempt+1}/{max_retries}] Iniciando goto para {url} (timeout=90s, wait_until='networkidle')")
                    await page_to_use.goto(url, timeout=90000, wait_until='networkidle')
                    print(f"[WebNavigatorTool Tentativa {attempt+1}/{max_retries}] goto concluído. Esperando campo #empresa...")
                    await page_to_use.locator("#empresa").wait_for(state='visible', timeout=30000)
                    print(f"[WebNavigatorTool Tentativa {attempt+1}/{max_retries}] Campo #empresa visível.")
                    page_title = await page_to_use.title()
                    result_message = f"Navegação para {url} OK. Título: {page_title}"
                    print(f"[WebNavigatorTool] {result_message}")
                    break # Sucesso, interrompe o loop de tentativas

                except Error as pe:
                    last_error = pe
                    error_message = f"Erro Playwright (Tentativa {attempt+1}/{max_retries}): {type(pe).__name__} - {str(pe)}"
                    print(f"[WebNavigatorTool] {error_message}")
                    # Tentar novamente apenas em TimeoutError
                    if "TimeoutError" in type(pe).__name__ and attempt < max_retries - 1:
                        print(f"[WebNavigatorTool] Tentando novamente em {retry_delay} segundos...")
                        await asyncio.sleep(retry_delay)
                        # Importante: Se o navegador foi criado localmente, feche-o antes de tentar novamente para começar do zero
                        if browser_created_locally:
                             if page_to_use and not page_to_use.is_closed(): await page_to_use.close()
                             page_to_use = None # Garante que uma nova página seja criada
                    else:
                        result_message = f"Erro: Falha ao navegar para {url} após {attempt+1} tentativas. Último erro: {error_message}" # Armazena a mensagem de erro
                        break # Interrompe o loop em erros não-Timeout ou na última tentativa
                except Exception as e:
                    last_error = e
                    error_message = f"Erro Inesperado (Tentativa {attempt+1}/{max_retries}): {type(e).__name__} - {str(e)}"
                    print(f"[WebNavigatorTool] {error_message}")
                    result_message = error_message # Armazena a mensagem de erro
                    break # Interrompe o loop em erros inesperados
            
            # Após o loop, verifica se result_message indica sucesso ou contém um erro
            if result_message and "OK" in result_message:
                return result_message # Retorna mensagem de sucesso
            else:
                # Se o loop terminou devido a falha nas tentativas ou outros erros
                final_error_message = f"Erro: Falha ao navegar para {url} após {max_retries} tentativas. Último erro: {type(last_error).__name__} - {str(last_error)}"
                print(f"[WebNavigatorTool] {final_error_message}")
                return final_error_message

        finally:
            # Limpeza: Fecha o navegador SOMENTE se foi criado localmente nesta execução
            # E se uma page_instance NÃO foi passada (significa que o chamador gerencia o navegador principal)
            if browser_created_locally and not page_instance:
                print("[WebNavigatorTool] Fechando navegador temporário criado pela ferramenta.")
                if page_to_use and not page_to_use.is_closed():
                    try: await page_to_use.close()
                    except Exception: pass # Ignora erros ao fechar página temporária
                if local_browser and local_browser.is_connected():
                     try: await local_browser.close()
                     except Exception: pass # Ignora erros ao fechar navegador temporário
                if playwright_context:
                     try: await playwright_context.stop()
                     except Exception: pass # Ignora erros ao parar contexto temporário

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
    # Chama a função de teste definida acima
    asyncio.run(test_navigation())