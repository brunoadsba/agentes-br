import asyncio
import os
from dotenv import load_dotenv

# --- Ajuste de Path --- 
import sys
# Adiciona o diretório pai (raiz do projeto) ao path para encontrar 'core'
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
# --- Fim Ajuste de Path ---

# Importa classes de cliente específicas necessárias para o teste
# Usaremos OpenRouterClient para testar o modelo Grok via API OpenRouter
from core.llm_manager import OpenRouterClient

async def test_grok_beta_via_openrouter():
    """Testa o modelo x-ai/grok-3-beta acessado via OpenRouter."""
    print("--- Testando x-ai/grok-3-beta via OpenRouter ---")
    # Usando a chave nomeada GROK_API_KEY no .env para este teste
    api_key = os.getenv("GROK_API_KEY")
    model_name = "x-ai/grok-3-beta"

    if not api_key:
        print(f"PULANDO TESTE: GROK_API_KEY não encontrada no .env")
        return

    try:
        print(f"Instanciando OpenRouterClient para o modelo: {model_name}")
        # Instancia OpenRouterClient especificamente para este modelo e chave
        client = OpenRouterClient(api_key=api_key, model_name=model_name)

        # Verifica se o cliente AsyncOpenRouter subjacente foi realmente criado
        if client.client is None:
            print("Falha ao inicializar o cliente AsyncOpenRouter subjacente na instância OpenRouterClient.")
            # Isso pode acontecer se houver um erro durante __init__ apesar da biblioteca estar disponível
            return

        prompt = "Qual é o significado da vida de acordo com Grok?"
        print(f"Enviando prompt: '{prompt}'")
        response = await client.generate(prompt)
        print(f"\nResposta de {model_name}:")
        print(response)

    except Exception as e:
        print(f"Ocorreu um erro durante o teste: {e}")
        import traceback
        traceback.print_exc() # Imprime traceback detalhado para depuração
    finally:
        print("--- Teste Finalizado ---\n")

async def test_optimus_alpha_via_openrouter():
    """Testa o modelo openrouter/optimus-alpha acessado via OpenRouter."""
    print("--- Testando openrouter/optimus-alpha via OpenRouter ---")
    # Usa a chave OPENROUTER_API_KEY para acessar modelos via OpenRouter
    api_key = os.getenv("OPENROUTER_API_KEY")
    model_name = "openrouter/optimus-alpha"

    if not api_key:
        print(f"PULANDO TESTE: OPENROUTER_API_KEY não encontrada no .env")
        return

    try:
        print(f"Instanciando OpenRouterClient para o modelo: {model_name}")
        # Instancia OpenRouterClient especificamente para este modelo e chave OpenRouter
        client = OpenRouterClient(api_key=api_key, model_name=model_name)

        if client.client is None:
            print("Falha ao inicializar o cliente AsyncOpenAI subjacente na instância OpenRouterClient.")
            return

        prompt = "Conte-me uma pequena história sobre um robô descobrindo música."
        print(f"Enviando prompt: '{prompt}'")

        # Adiciona print da resposta completa para depuração
        # Chamada direta ao cliente OpenAI subjacente para obter a resposta bruta
        print("Aguardando resposta da API...")
        raw_response = await client.client.chat.completions.create(
                    model=model_name,
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.7
        )
        print("\n--- Resposta Bruta da API ---")
        print(raw_response) # Imprime o objeto de resposta completo
        print("--- Fim Resposta Bruta ---")

        # Tenta extrair a resposta como antes (adaptado do método generate)
        if raw_response.choices and raw_response.choices[0].message:
            response_content = raw_response.choices[0].message.content or ""
        else:
            response_content = "Erro: Nenhuma estrutura de conteúdo encontrada na resposta bruta."

        print(f"\nResposta de {model_name}:")
        print(response_content)

    except Exception as e:
        print(f"Ocorreu um erro durante o teste: {e}")
        import traceback
        traceback.print_exc()
    finally:
        print("--- Teste Finalizado ---\n")

async def run_tests():
    load_dotenv() # Carrega variáveis de ambiente do .env

    # Chama testes específicos
    await test_grok_beta_via_openrouter()
    await test_optimus_alpha_via_openrouter()

    # Adicione chamadas para outras funções de teste aqui se necessário
    # ex: await test_gemini_client()
    #     await test_openai_client()

if __name__ == "__main__":
    print("Iniciando testes de cliente LLM...")
    asyncio.run(run_tests())
    print("Testes de cliente LLM finalizados.")
