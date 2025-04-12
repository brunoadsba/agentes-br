import os
import google.generativeai as genai
from dotenv import load_dotenv

def configure_gemini():
    """Carrega a chave da API Gemini do arquivo .env e configura a biblioteca genai."""
    load_dotenv() 
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        print("AVISO: GEMINI_API_KEY não encontrada no .env. A API Gemini pode não funcionar.")
        return False # Indica falha na configuração
    try:
        genai.configure(api_key=api_key)
        print("Biblioteca Gemini configurada com sucesso.")
        return True
    except Exception as e:
        print(f"Erro ao configurar a biblioteca Gemini: {e}")
        return False

# Exemplo de como chamar (será usado no main.py):
# if __name__ == '__main__':
#     configure_gemini() 