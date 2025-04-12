import os
import google.generativeai as genai
from dotenv import load_dotenv

def configure_gemini():
    """Carrega a chave da API Gemini do arquivo .env e configura a biblioteca genai."""
    load_dotenv()  # Carrega variáveis do arquivo .env para o ambiente
    
    api_key = os.getenv("GEMINI_API_KEY")
    
    if not api_key:
        raise ValueError("A variável de ambiente GEMINI_API_KEY não foi definida. "
                         "Certifique-se de que ela está no arquivo .env")
    
    try:
        genai.configure(api_key=api_key)
        print("Biblioteca Gemini configurada com sucesso.")
        return True
    except Exception as e:
        print(f"Erro ao configurar a biblioteca Gemini: {e}")
        # Você pode querer lançar a exceção ou retornar False dependendo do fluxo desejado
        # raise e 
        return False

# Exemplo de como chamar (será usado no main.py):
# if __name__ == '__main__':
#     configure_gemini() 