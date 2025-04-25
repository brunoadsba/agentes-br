import asyncio
from playwright.async_api import async_playwright, Page, Error, TimeoutError
from typing import Optional, Dict, Any
from core.models import BaseTool
import logging

class WebNavigatorTool(BaseTool):
    """Navega para URL, reutilizando página se fornecida ou criando uma temporária se necessário."""
    async def run(self, url: str, page_instance: Optional[Page] = None, max_retries: int = 3, retry_delay: int = 5, 
                 wait_for_selector: Optional[str] = "#empresa", timeout_goto: int = 90000, 
                 timeout_selector: int = 30000, headless: bool = True) -> dict:
        """
        Navega para uma URL específica.
        
        Args:
            url: A URL para navegar.
            page_instance: Instância de página existente ou None para criar uma temporária.
            max_retries: Número máximo de tentativas em caso de erro.
            retry_delay: Atraso em segundos entre tentativas.
            wait_for_selector: Seletor opcional para esperar ficar visível após navegar.
                               Se None, não espera por nenhum elemento específico.
            timeout_goto: Tempo limite em ms para a navegação.
            timeout_selector: Tempo limite em ms para esperar o seletor ficar visível.
            headless: Se True, o navegador será executado em modo invisível. Se False, o navegador será visível.
            
        Returns:
            dict contendo 'result_message' (str) e 'page' (Page ou None).
        """
        # Log inicial e configuração de variáveis
        print(f"[WebNavigatorTool] Iniciando navegação para: {url}")
        page_to_use: Optional[Page] = page_instance
        browser_created_locally = False
        playwright_context = None
        local_browser = None
        last_error = None
        result_message = None 

        # Tratamento de erros e limpeza garantida
        try: 
            for attempt in range(max_retries):
                try:
                    # --- Etapa 1: Configuração do navegador/página ---
                    if not page_to_use or page_to_use.is_closed():
                        print(f"[WebNavigatorTool] Tentativa {attempt+1}/{max_retries}: Configurando navegador temporário")
                        # Fecha recursos de tentativa anterior, se existirem
                        await self._cleanup_temp_resources(page_to_use, local_browser, playwright_context)
                        
                        # Inicializa novos recursos
                        playwright_context = await async_playwright().start()
                        # Lança o navegador com configurações para maximizar a janela
                        local_browser = await playwright_context.chromium.launch(
                            headless=headless, 
                            args=[
                                '--start-maximized',
                                '--window-size=1920,1080',
                                '--no-sandbox'
                            ]
                        )
                        
                        # Cria o contexto do navegador com viewport maximizado
                        context = await local_browser.new_context(
                            viewport={'width': 1920, 'height': 1080},
                            no_viewport=False
                        )
                        
                        # Cria uma nova página no contexto
                        page_to_use = await context.new_page()
                        browser_created_locally = True
                        
                        if not page_to_use: 
                            raise Error("Falha ao criar página no navegador.")
                    
                    # --- Etapa 2: Navegação ---
                    print(f"[WebNavigatorTool] Tentativa {attempt+1}/{max_retries}: Navegando para {url} (timeout={timeout_goto/1000}s)")
                    
                    # Pequena pausa antes de navegar
                    await asyncio.sleep(1)
                    
                    await page_to_use.goto(url, timeout=timeout_goto, wait_until='networkidle')
                    
                    # Espera adicional após o carregamento para garantir que todos os elementos estejam prontos
                    await asyncio.sleep(2)
                    
                    # Maximiza após o carregamento
                    try:
                        # Tenta maximizar via JavaScript
                        await page_to_use.evaluate("""() => {
                            if (document.documentElement.requestFullscreen) {
                                document.documentElement.requestFullscreen().catch(e => console.error('Erro ao ativar fullscreen:', e));
                            }
                            window.moveTo(0,0);
                            window.resizeTo(screen.availWidth, screen.availHeight);
                        }""")
                    except Exception as e:
                        print(f"[WebNavigatorTool] Não foi possível maximizar via JS: {e}")
                    
                    # --- Etapa 3: Verificação (opcional) ---
                    if wait_for_selector:
                        print(f"[WebNavigatorTool] Tentativa {attempt+1}/{max_retries}: Aguardando seletor '{wait_for_selector}'")
                        await page_to_use.locator(wait_for_selector).wait_for(state='visible', timeout=timeout_selector)
                        print(f"[WebNavigatorTool] Tentativa {attempt+1}/{max_retries}: Seletor '{wait_for_selector}' encontrado")
                    
                    # --- Etapa 4: Confirmação de sucesso ---
                    page_title = await page_to_use.title()
                    result_message = f"Navegação para {url} concluída com sucesso. Título da página: {page_title}"
                    print(f"[WebNavigatorTool] {result_message}")
                    
                    return {"result_message": result_message, "page": page_to_use} # Sucesso, interrompe o loop

                except TimeoutError as te:
                    last_error = te
                    error_message = f"Timeout durante {attempt+1}/{max_retries}: {str(te)}"
                    print(f"[WebNavigatorTool] {error_message}")
                    
                    # Tenta novamente se não for a última tentativa
                    if attempt < max_retries - 1:
                        print(f"[WebNavigatorTool] Aguardando {retry_delay}s antes da próxima tentativa...")
                        await asyncio.sleep(retry_delay)
                        
                        # Fecha a página da tentativa atual para começar com uma limpa
                        if browser_created_locally and page_to_use and not page_to_use.is_closed():
                            await page_to_use.close()
                            page_to_use = None
                    else:
                        # Última tentativa falhou
                        final_error = f"Erro: Falha após {max_retries} tentativas de navegar para {url}. Timeout."
                        print(f"[WebNavigatorTool] {final_error}")
                        return {"result_message": final_error, "page": page_to_use}
                        
                except Error as pe:
                    # Outros erros do Playwright 
                    last_error = pe
                    error_message = f"Erro Playwright durante tentativa {attempt+1}/{max_retries}: {type(pe).__name__} - {str(pe)}"
                    print(f"[WebNavigatorTool] {error_message}")
                    
                    # Para alguns erros específicos, podemos tentar novamente
                    if attempt < max_retries - 1:
                        print(f"[WebNavigatorTool] Aguardando {retry_delay}s antes da próxima tentativa...")
                        await asyncio.sleep(retry_delay)
                        
                        if browser_created_locally and page_to_use and not page_to_use.is_closed():
                            await page_to_use.close()
                            page_to_use = None
                    else:
                        # Última tentativa falhou
                        final_error = f"Erro: Falha após {max_retries} tentativas de navegar para {url}. Último erro: {type(pe).__name__} - {str(pe)}"
                        print(f"[WebNavigatorTool] {final_error}")
                        return {"result_message": final_error, "page": page_to_use}
                    
                except Exception as e:
                    # Erros inesperados
                    last_error = e
                    error_message = f"Erro inesperado durante tentativa {attempt+1}/{max_retries}: {type(e).__name__} - {str(e)}"
                    print(f"[WebNavigatorTool] {error_message}")
                    
                    # Geralmente não tentamos novamente para erros inesperados
                    final_error = f"Erro crítico ao navegar para {url}: {type(e).__name__} - {str(e)}"
                    print(f"[WebNavigatorTool] {final_error}")
                    return {"result_message": final_error, "page": page_to_use}
            
            # Este ponto só é alcançado se todas as tentativas falharem e não retornarem diretamente
            if not result_message:
                final_error = f"Erro: Falha após {max_retries} tentativas de navegar para {url}."
                print(f"[WebNavigatorTool] {final_error}")
                return {"result_message": final_error, "page": page_to_use}
                
            return {"result_message": result_message, "page": page_to_use}

        finally:
            # Limpeza de recursos criados localmente, se apropriado
            if browser_created_locally and not page_instance:
                await self._cleanup_temp_resources(page_to_use, local_browser, playwright_context)

    async def _cleanup_temp_resources(self, page: Optional[Page], browser: Any, playwright: Any):
        """Helper para limpar recursos temporários do Playwright."""
        try:
            print("[WebNavigatorTool] Limpando recursos temporários...")
            if page and not page.is_closed():
                try: 
                    await page.close()
                    print("[WebNavigatorTool] Página temporária fechada.")
                except Exception as e: 
                    print(f"[WebNavigatorTool] Erro ao fechar página: {e}")
                    
            if browser and browser.is_connected():
                try: 
                    await browser.close()
                    print("[WebNavigatorTool] Navegador temporário fechado.")
                except Exception as e: 
                    print(f"[WebNavigatorTool] Erro ao fechar navegador: {e}")
                    
            if playwright:
                try: 
                    await playwright.stop()
                    print("[WebNavigatorTool] Contexto Playwright encerrado.")
                except Exception as e: 
                    print(f"[WebNavigatorTool] Erro ao encerrar contexto Playwright: {e}")
                    
        except Exception as e:
            print(f"[WebNavigatorTool] Erro durante limpeza de recursos: {e}")

    async def navigate(self, url):
        """Navega para a URL especificada."""
        try:
            logging.info(f"Navegando para: {url}")
            if not self.browser or not self.page:
                await self.start_browser()
            
            # Navegar para a URL
            await self.page.goto(url, wait_until="networkidle")
            
            # Configura tamanho da janela para tela cheia
            await self.page.set_viewport_size({"width": 1920, "height": 1080})
            
            # Tenta maximizar usando JavaScript
            await self.page.evaluate("""() => {
                if (document.documentElement.requestFullscreen) {
                    document.documentElement.requestFullscreen();
                } 
                window.resizeTo(screen.width, screen.height);
                window.moveTo(0, 0);
            }""")
            
            await self.page.wait_for_timeout(2000)  # Aguarda 2 segundos para garantir carregamento completo
            logging.info(f"Navegação concluída para: {url}")
            return True
        except Exception as e:
            logging.error(f"Erro ao navegar para URL: {e}")
            return False

    async def fill_form_field(self, selector, value, check_visibility=True, wait_time=2000):
        """
        Preenche um campo de formulário com verificação de visibilidade.
        
        Args:
            selector: Seletor CSS do campo
            value: Valor a ser preenchido
            check_visibility: Se deve verificar visibilidade antes de preencher
            wait_time: Tempo de espera em ms antes de preencher
        """
        try:
            logging.info(f"Preenchendo campo '{selector}' com valor: {value}")
            
            # Aguarda o tempo especificado
            await self.page.wait_for_timeout(wait_time)
            
            if check_visibility:
                # Aguarda até que o elemento esteja visível
                await self.page.wait_for_selector(selector, state="visible", timeout=10000)
            
            # Clica fora primeiro para garantir que o foco seja limpo
            await self.page.mouse.click(10, 10)
            await self.page.wait_for_timeout(500)
            
            # Clica no campo para garantir o foco
            await self.page.click(selector)
            await self.page.wait_for_timeout(500)
            
            # Limpa o campo se já houver texto
            await self.page.fill(selector, "")
            await self.page.wait_for_timeout(300)
            
            # Preenche o valor
            await self.page.fill(selector, value)
            logging.info(f"Campo '{selector}' preenchido com sucesso.")
            return True
        except Exception as e:
            logging.error(f"Erro ao preencher campo '{selector}': {e}")
            return False

# Exemplo de uso (para teste direto do arquivo)
async def test_navigation():
    tool = WebNavigatorTool()
    # Teste com um site simples
    result = await tool.run("https://example.com", wait_for_selector="h1")
    print(f"Resultado final: {result}")

if __name__ == "__main__":
    # Adiciona o diretório raiz ao PYTHONPATH para encontrar core.models
    import sys
    import os
    sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
    # Chama a função de teste definida acima
    asyncio.run(test_navigation())