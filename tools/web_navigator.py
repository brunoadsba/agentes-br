import asyncio
from playwright.async_api import async_playwright

# Certifique-se de que a classe BaseTool está acessível.
# Ajuste o import se a estrutura do seu projeto for diferente.
# Se core/models.py estiver em um nível superior, pode ser necessário:
# from ..core.models import BaseTool
# Ou configure seu PYTHONPATH adequadamente.
# Por simplicidade, assumindo execução a partir da raiz 'agentes-br':
from core.models import BaseTool

class WebNavigatorTool(BaseTool):
    """Ferramenta para navegar até uma URL usando Playwright."""

    async def run(self, url: str) -> str:
        """Abre um navegador, navega para a URL e fecha o navegador.

        Args:
            url: A URL para a qual navegar.

        Returns:
            Uma mensagem indicando sucesso ou falha na navegação.
        """
        print(f"[WebNavigatorTool] Tentando navegar para: {url}")
        browser = None # Inicializa browser como None
        try:
            async with async_playwright() as p:
                # Inicia o navegador (Chromium por padrão)
                # headless=True significa que o navegador não será visível
                # headless=False é útil para depuração
                browser = await p.chromium.launch(headless=True)
                page = await browser.new_page()

                # Navega para a URL com um timeout aumentado para lidar com carregamentos lentos (ex: Render free tier)
                await page.goto(url, timeout=90000) # Timeout de 90 segundos

                page_title = await page.title()
                print(f"[WebNavigatorTool] Navegação bem-sucedida. Título da página: {page_title}")

                await browser.close()
                return f"Navegação para {url} concluída com sucesso. Título: {page_title}"
        except Exception as e:
            print(f"[WebNavigatorTool] Erro ao navegar para {url}: {e}")
            # Tenta fechar o navegador se ele foi iniciado e ocorreu um erro
            if browser:
                try:
                    await browser.close()
                except Exception as close_err:
                    print(f"[WebNavigatorTool] Erro adicional ao tentar fechar o navegador: {close_err}")
            return f"Erro ao tentar navegar para {url}: {str(e)}"

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