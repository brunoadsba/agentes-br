"""
Utilitários para otimização e gerenciamento de prompts.
"""
import logging
import re
from typing import List, Dict, Any, Optional, Union, Tuple

logger = logging.getLogger(__name__)

try:
    import tiktoken
    TIKTOKEN_AVAILABLE = True
except ImportError:
    logger.warning("Tiktoken não encontrado. Usando estimativa mais simples para contagem de tokens.")
    TIKTOKEN_AVAILABLE = False

# Constantes para otimização de prompts
DEFAULT_MODEL = "gpt-3.5-turbo"
TOKEN_LIMIT_MAP = {
    "gpt-3.5-turbo": 16385,
    "gpt-4": 8192,
    "gpt-4-turbo": 128000,
    "claude-3-opus": 200000,
    "claude-3-sonnet": 180000,
    "claude-3-haiku": 150000,
    "gemini-pro": 32768,
    "gemini-ultra": 32768,
}

def calculate_token_count(text: str, model: str = DEFAULT_MODEL) -> int:
    """
    Calcula o número aproximado de tokens em um texto.
    
    Args:
        text: Texto para calcular os tokens
        model: Nome do modelo para usar encoder específico
        
    Returns:
        int: Número estimado de tokens
    """
    if not text:
        return 0
        
    if TIKTOKEN_AVAILABLE:
        try:
            # Determina o encoding apropriado para o modelo
            if "gpt" in model.lower():
                encoding_name = "cl100k_base"  # Para modelos GPT
            else:
                encoding_name = "cl100k_base"  # Default para outros modelos
                
            encoding = tiktoken.get_encoding(encoding_name)
            return len(encoding.encode(text))
        except Exception as e:
            logger.warning(f"Erro ao calcular tokens com tiktoken: {str(e)}. Usando estimativa simples.")
    
    # Estimativa simples como fallback (4 caracteres ~= 1 token)
    words = re.findall(r'\b\w+\b', text)
    return len(words) + len(text) // 4

def get_model_context_window(model: str) -> int:
    """
    Retorna o tamanho da janela de contexto para um modelo.
    
    Args:
        model: Nome do modelo
        
    Returns:
        int: Tamanho da janela de contexto em tokens
    """
    model_key = model.lower()
    
    # Encontra a correspondência mais próxima no mapa
    for key, value in TOKEN_LIMIT_MAP.items():
        if key.lower() in model_key:
            return value
            
    # Valor padrão conservador para modelos desconhecidos
    return 4096

def truncate_text_to_tokens(text: str, max_tokens: int, model: str = DEFAULT_MODEL) -> str:
    """
    Trunca um texto para caber dentro do limite de tokens.
    
    Args:
        text: Texto a ser truncado
        max_tokens: Número máximo de tokens permitidos
        model: Nome do modelo para calcular tokens
        
    Returns:
        str: Texto truncado para caber no limite especificado
    """
    if not text:
        return ""
        
    current_tokens = calculate_token_count(text, model)
    
    if current_tokens <= max_tokens:
        return text
        
    # Divide o texto em parágrafos
    paragraphs = text.split("\n\n")
    
    # Se for apenas um parágrafo, divide por frases
    if len(paragraphs) <= 1:
        sentences = re.split(r'(?<=[.!?])\s+', text)
        
        result = ""
        for sentence in sentences:
            potential_result = result + sentence + " "
            if calculate_token_count(potential_result, model) > max_tokens:
                break
            result = potential_result
            
        return result.strip()
    
    # Calcula metade dos tokens para a parte inicial e metade para a final
    half_tokens = max_tokens // 2
    
    # Tenta manter o início e o fim do documento
    start_text = ""
    for para in paragraphs:
        if calculate_token_count(start_text + para + "\n\n", model) > half_tokens:
            break
        start_text += para + "\n\n"
    
    end_text = ""
    for para in reversed(paragraphs):
        if calculate_token_count(para + "\n\n" + end_text, model) > half_tokens:
            break
        end_text = para + "\n\n" + end_text
    
    # Adiciona indicador que houve truncamento
    middle_indicator = "...\n[Conteúdo truncado para caber no limite de tokens]\n...\n\n"
    
    return start_text + middle_indicator + end_text

def optimize_prompt_for_tokens(
    prompt: str, 
    available_tokens: int, 
    model: str = DEFAULT_MODEL,
    keep_sections: Optional[List[str]] = None
) -> str:
    """
    Otimiza um prompt para caber dentro do limite de tokens disponíveis.
    
    Args:
        prompt: Prompt original
        available_tokens: Número de tokens disponíveis para o prompt
        model: Nome do modelo para calcular tokens
        keep_sections: Lista de cabeçalhos de seções para garantir que não sejam truncadas
        
    Returns:
        str: Prompt otimizado para caber nos tokens disponíveis
    """
    current_tokens = calculate_token_count(prompt, model)
    
    if current_tokens <= available_tokens:
        return prompt
        
    # Se não houver seções específicas para manter, usa truncamento simples
    if not keep_sections:
        return truncate_text_to_tokens(prompt, available_tokens, model)
    
    # Divide o prompt em seções baseadas em cabeçalhos (#, ##, etc)
    sections = re.split(r'(^|\n)(#+ .*?)(?=\n)', prompt)
    
    # Agrupa os pedaços em seções reais
    grouped_sections = []
    current_section = ""
    current_header = ""
    
    for i, section in enumerate(sections):
        if re.match(r'^#+ ', section.strip()):
            # É um cabeçalho
            if current_section:
                grouped_sections.append((current_header, current_section))
            current_header = section.strip()
            current_section = ""
        else:
            current_section += section
    
    # Adiciona a última seção
    if current_section:
        grouped_sections.append((current_header, current_section))
    
    # Identifica seções que devem ser mantidas
    must_keep = []
    can_truncate = []
    
    for header, content in grouped_sections:
        keep_this = False
        for keep_header in (keep_sections or []):
            if keep_header.lower() in header.lower():
                keep_this = True
                break
        
        if keep_this:
            must_keep.append((header, content))
        else:
            can_truncate.append((header, content))
    
    # Calcula tokens para seções obrigatórias
    required_tokens = sum(calculate_token_count(header + content, model) 
                          for header, content in must_keep)
    
    # Verifica se as seções obrigatórias já excedem o limite
    if required_tokens > available_tokens:
        # Prioriza as seções obrigatórias, mas reduz seu conteúdo
        optimized_must_keep = []
        remaining_tokens = available_tokens
        
        for header, content in must_keep:
            header_tokens = calculate_token_count(header, model)
            remaining_tokens -= header_tokens
            
            if remaining_tokens <= 0:
                break
                
            section_tokens = min(remaining_tokens, calculate_token_count(content, model))
            optimized_content = truncate_text_to_tokens(content, section_tokens, model)
            
            optimized_must_keep.append((header, optimized_content))
            remaining_tokens -= calculate_token_count(optimized_content, model)
        
        # Remonta o prompt apenas com as seções obrigatórias otimizadas
        return "".join(header + content for header, content in optimized_must_keep)
    
    # Se as seções obrigatórias cabem, distribua tokens restantes para as demais seções
    remaining_tokens = available_tokens - required_tokens
    
    # Ordena as seções truncáveis por ordem de importância (assumindo que as primeiras são mais importantes)
    optimized_can_truncate = []
    
    for header, content in can_truncate:
        header_tokens = calculate_token_count(header, model)
        
        if header_tokens >= remaining_tokens:
            # Não há espaço nem para o cabeçalho
            continue
        
        remaining_tokens -= header_tokens
        
        if remaining_tokens <= 0:
            break
            
        # Aloca tokens para o conteúdo
        content_tokens = min(remaining_tokens, calculate_token_count(content, model))
        optimized_content = truncate_text_to_tokens(content, content_tokens, model)
        
        optimized_can_truncate.append((header, optimized_content))
        remaining_tokens -= calculate_token_count(optimized_content, model)
    
    # Remonta o prompt com todas as seções
    all_sections = must_keep + optimized_can_truncate
    all_sections.sort(key=lambda x: prompt.find(x[0]))  # Ordena na ordem original do prompt
    
    return "".join(header + content for header, content in all_sections)

def create_optimized_system_prompt(
    base_prompt: str, 
    context: str,
    max_tokens: int,
    model: str = DEFAULT_MODEL,
    essential_sections: Optional[List[str]] = None
) -> str:
    """
    Cria um prompt de sistema otimizado que incorpora o contexto.
    
    Args:
        base_prompt: Prompt base com instruções do sistema
        context: Contexto a ser incorporado (pode ser truncado)
        max_tokens: Limite máximo de tokens
        model: Nome do modelo para cálculo de tokens
        essential_sections: Seções do prompt base que não devem ser truncadas
        
    Returns:
        str: Prompt de sistema otimizado
    """
    if not essential_sections:
        essential_sections = ["instruções", "diretrizes", "regras", "personalidade"]
        
    # Calcula tokens disponíveis para o contexto
    base_tokens = calculate_token_count(base_prompt, model)
    context_tokens = max_tokens - base_tokens
    
    # Se o base prompt já é maior que o limite
    if base_tokens >= max_tokens:
        return optimize_prompt_for_tokens(base_prompt, max_tokens, model, essential_sections)
        
    # Se houver espaço insuficiente para o contexto, reserve pelo menos 20% dos tokens para ele
    if context_tokens < (max_tokens * 0.2):
        context_tokens = int(max_tokens * 0.2)
        base_tokens = max_tokens - context_tokens
        base_prompt = optimize_prompt_for_tokens(base_prompt, base_tokens, model, essential_sections)
    
    # Otimiza o contexto
    optimized_context = truncate_text_to_tokens(context, context_tokens, model)
    
    # Combina o prompt base e o contexto
    if "## Contexto" in base_prompt:
        # Substitui a seção de contexto existente
        pattern = r"(## Contexto\n)(.*?)(\n##|\Z)"
        replacement = f"\\1{optimized_context}\\3"
        return re.sub(pattern, replacement, base_prompt, flags=re.DOTALL)
    else:
        # Adiciona o contexto no final
        return base_prompt + "\n\n## Contexto\n" + optimized_context

def create_tool_specific_prompts() -> Dict[str, Dict[str, str]]:
    """
    Cria prompts específicos para cada tipo de ferramenta.
    
    Returns:
        Dicionário com prompts específicos por ferramenta
    """
    return {
        "WebNavigatorTool": {
            "pre_execution": """
# Avaliação de Navegação
Antes de navegar, siga estas etapas:
1. Verifique se a URL está no formato correto (ex: https://dominio.com/caminho).
2. Certifique-se de que a URL é segura e corresponde ao site alvo da tarefa.
3. Aguarde o carregamento completo da página antes de qualquer outra ação.
4. Se a navegação falhar, registre o erro e não tente navegar para múltiplas URLs.

Exemplos de URLs válidas:
- https://exemplo.com
- https://sistema.empresa.com/pagina

Exemplos de URLs inválidas:
- www.exemplo.com (faltando protocolo)
- http:/exemplo.com (erro de sintaxe)

Navegando para: {url}
            """,
            "post_execution": """
# Avaliação de Resultado da Navegação
Após a navegação, avalie:
1. A página foi carregada completamente e sem erros?
2. O título da página ('{page_title}') corresponde ao esperado?
3. Os elementos esperados estão presentes e visíveis?
4. Se houve erro, registre a mensagem e sugira aguardar mais tempo ou revisar a URL.

Resultado: {result}
            """
        },
        "WebInteractorTool": {
            "pre_execution": """
# Análise de Interação Web
Antes de interagir com um elemento:
1. Verifique se o seletor CSS '{selector}' está correto, específico e corresponde ao campo desejado.
2. Certifique-se de que o elemento está visível e interagível antes de executar a ação '{action}'.
3. Aguarde o carregamento do elemento, se necessário.
4. Use apenas os seletores e valores fornecidos na tarefa. Não tente adivinhar.

Exemplo de boa prática:
- Usar '#empresa' para preencher o campo Empresa.
Exemplo de má prática:
- Usar um seletor genérico como 'input' ou tentar preencher campos de outros serviços.
            """,
            "post_execution": """
# Resultado da Interação com a Web
Após a ação '{action}' no elemento '{selector}':
1. A interação foi bem-sucedida? O sistema respondeu como esperado?
2. O campo ou botão foi realmente preenchido/clicado/selecionado?
3. Se houve erro (ex: elemento não encontrado, não visível, etc.), registre a mensagem e sugira aguardar mais tempo, revisar o seletor ou verificar se o campo existe.
4. Não tente repetir a ação automaticamente em caso de erro, a menos que a tarefa peça.

Resultado: {result}
            """
        }
    } 