"""
Módulo para gerenciamento de memória contextual em agentes.
"""
import logging
import time
import json
from typing import List, Dict, Optional, Any, Tuple, Set, Union

# Importa utilidades de prompt se disponíveis
try:
    from .prompt_utils import (
        calculate_token_count,
        truncate_text_to_tokens,
        optimize_prompt_for_tokens
    )
    PROMPT_UTILS_AVAILABLE = True
except ImportError:
    PROMPT_UTILS_AVAILABLE = False
    print("Aviso: Utilitários de otimização de prompt não disponíveis na memória contextual.")

logger = logging.getLogger(__name__)

class ContextualMemory:
    """Gerencia a memória contextual para agentes, incluindo histórico individual e global."""
    def __init__(
        self, 
        max_items: int = 20, 
        max_tokens: int = 8000,
        summarize_threshold: int = 30, 
        keep_recent_items: int = 5,
        model: str = "gpt-3.5-turbo"
    ):
        """
        Inicializa uma nova instância de memória contextual.
        
        Args:
            max_items: Número máximo de itens a manter na memória.
            max_tokens: Número máximo de tokens para toda a memória.
            summarize_threshold: Número de itens que dispara a sumarização.
            keep_recent_items: Número de itens recentes a manter após sumarização.
            model: Nome do modelo usado para cálculo de tokens.
        """
        # Armazenamento principal
        self.items: List[Dict[str, Any]] = []
        
        # Parâmetros de configuração
        self.max_items = max_items
        self.max_tokens = max_tokens
        self.summarize_threshold = summarize_threshold
        self.keep_recent_items = keep_recent_items
        self.model = model
        
        # Rastreamento de tokens
        self.current_token_count = 0
        
        # Métricas e metadados
        self.created_at = time.time()
        self.item_count = 0
        self.summary_count = 0
        self.summaries = []
        
        # Referência ao gerenciador LLM para criar resumos
        self.llm_manager = None
        
    def set_llm_manager(self, llm_manager):
        """Define o gerenciador LLM para geração de resumos."""
        self.llm_manager = llm_manager
    
    def add(self, item_type: str, content: str, metadata: Optional[Dict[str, Any]] = None) -> None:
        """
        Adiciona um item à memória.
        
        Args:
            item_type: Tipo do item (ex: "message", "observation", "action").
            content: Conteúdo do item a ser armazenado.
            metadata: Metadados opcionais associados ao item.
        """
        # Gera um timestamp para o item
        timestamp = time.time()
        
        # Cria o item completo
        item = {
            "id": self.item_count + 1,
            "type": item_type,
            "content": content,
            "timestamp": timestamp,
            "metadata": metadata or {}
        }
        
        # Adiciona o item à lista
        self.items.append(item)
        self.item_count += 1
        
        # Atualiza contagem de tokens
        if PROMPT_UTILS_AVAILABLE:
            item_tokens = calculate_token_count(json.dumps(item), model=self.model)
            self.current_token_count += item_tokens
        
        # Otimiza a memória se necessário
        if len(self.items) > self.summarize_threshold:
            self._optimize_memory_for_tokens()
        elif PROMPT_UTILS_AVAILABLE and self.current_token_count > self.max_tokens:
            self._optimize_memory_for_tokens(force=True)
    
    async def summarize_memory(self) -> str:
        """
        Gera um resumo do conteúdo atual da memória usando LLM.
        
        Returns:
            str: Resumo gerado ou mensagem de erro.
        """
        if not self.llm_manager:
            logger.warning("Não é possível gerar resumo sem LLMManager configurado.")
            return "Resumo indisponível: LLMManager não configurado."
        
        if not self.items:
            return "Não há itens na memória para resumir."
            
        # Formata os itens relevantes para o resumo
        memory_text = "\n\n".join([
            f"{i+1}. [{item['type']}] {item['content']}"
            for i, item in enumerate(self.items[-10:])  # Usa no máximo os 10 mais recentes
        ])
        
        prompt = f'''# Resumo de Memória Contextual

## Itens Recentes para Resumir
{memory_text}

## Instruções
1. Crie um resumo CONCISO dos itens de memória acima.
2. DESTAQUE fatos importantes, decisões críticas, padrões recorrentes de sucesso ou erro e conexões entre os itens.
3. MANTENHA detalhes críticos como nomes, datas e valores numéricos.
4. ORGANIZE o resumo em ordem cronológica ou por importância.
5. PRIORIZE informações que seriam mais úteis para tarefas futuras.
6. Se identificar padrões de erro ou sucesso, SUGIRA recomendações para execuções futuras.
7. O resumo deve ser útil para o agente planejar próximas ações e evitar repetir erros.

## Formato Desejado
Gere um resumo de 3-5 frases que capture a essência das memórias, destaque padrões e forneça recomendações, se aplicável.
'''

        try:
            if PROMPT_UTILS_AVAILABLE:
                # Otimiza o prompt se necessário
                prompt = optimize_prompt_for_tokens(
                    prompt, 
                    available_tokens=1000, 
                    model=self.model,
                    keep_sections=["Itens Recentes", "Instruções"]
                )
            
            # Gera o resumo usando o LLM
            summary = await self.llm_manager.generate(prompt)
            
            # Adiciona o resumo à lista de resumos
            self.summaries.append({
                "content": summary,
                "items_summarized": len(self.items),
                "timestamp": time.time()
            })
            self.summary_count += 1
            
            return summary
        except Exception as e:
            error_msg = f"Erro ao gerar resumo com LLM: {e}"
            logger.error(error_msg)
            return f"Falha na geração de resumo: {str(e)}"
    
    def get_recent_by_type(self, item_type: Optional[str] = None, limit: int = 5) -> List[Dict[str, Any]]:
        """
        Recupera os itens mais recentes de um tipo específico.
        
        Args:
            item_type: Tipo de item a recuperar (None para todos os tipos).
            limit: Número máximo de itens a retornar.
            
        Returns:
            Lista dos itens mais recentes do tipo especificado.
        """
        if not item_type:
            return self.items[-limit:]
            
        filtered_items = [item for item in self.items if item["type"] == item_type]
        return filtered_items[-limit:]
    
    def get_formatted_context(self, max_tokens: Optional[int] = None) -> str:
        """
        Retorna o contexto formatado para uso em prompts.
        
        Args:
            max_tokens: Limite opcional de tokens para o contexto.
            
        Returns:
            str: Contexto formatado.
        """
        if not self.items:
            return "Nenhum contexto disponível na memória."
            
        # Define o limite de tokens, usando o padrão se não especificado
        token_limit = max_tokens or self.max_tokens
        
        # Obtém o último resumo se houver
        last_summary = self.summaries[-1]["content"] if self.summaries else ""
        
        # Formata os itens recentes
        recent_items = [
            f"[{item['type']}] {item['content']}"
            for item in self.items[-self.keep_recent_items:]
        ]
        
        # Constrói o contexto completo
        if last_summary:
            context = f"## Resumo da Memória Anterior\n{last_summary}\n\n## Itens Recentes\n" + "\n".join(recent_items)
        else:
            context = "## Contexto\n" + "\n".join(recent_items)
            
        # Otimiza para tokens se disponível
        if PROMPT_UTILS_AVAILABLE and max_tokens:
            return truncate_text_to_tokens(context, token_limit, self.model)
            
        return context
        
    def _optimize_memory_for_tokens(self, force: bool = False) -> None:
        """
        Otimiza a memória para caber dentro dos limites de tokens.
        
        Args:
            force: Forçar otimização mesmo que não tenha atingido o limite de itens.
        """
        if not force and len(self.items) <= self.max_items:
            return
            
        # Verifica se excedeu o limite de itens ou tokens
        if PROMPT_UTILS_AVAILABLE:
            needs_token_optimization = self.current_token_count > self.max_tokens
        else:
            needs_token_optimization = False
            
        needs_item_optimization = len(self.items) > self.max_items
        
        if not (needs_token_optimization or needs_item_optimization or force):
            return
            
        # Seleciona itens para manter (os mais recentes são sempre mantidos)
        items_to_keep = self._select_important_items()
        
        # Cria uma nova lista com apenas os itens importantes
        self.items = items_to_keep
        
        # Recalcula a contagem de tokens
        if PROMPT_UTILS_AVAILABLE:
            self.current_token_count = calculate_token_count(json.dumps(self.items), model=self.model)
            
        logger.info(f"Memória otimizada: {len(self.items)} itens, {self.current_token_count} tokens")
    
    def _select_important_items(self) -> List[Dict[str, Any]]:
        """
        Seleciona os itens mais importantes para manter na memória.
        
        Returns:
            Lista de itens importantes a serem mantidos.
        """
        # Sempre mantém os itens mais recentes
        recent_items = self.items[-self.keep_recent_items:] if self.items else []
        
        # Se não excedemos o limite de itens, retorna todos
        if len(self.items) <= self.max_items:
            return self.items
            
        # Identifica IDs de itens recentes para não duplicar
        recent_ids = {item["id"] for item in recent_items}
        
        # Prioriza itens com base em heurísticas:
        # 1. Mantém todos os itens do tipo "summary"
        # 2. Mantém itens explicitamente marcados como importantes
        # 3. Mantém itens com conteúdo mais longo (assumindo mais informações)
        # 4. Mantém itens mais recentes
        
        candidate_items = []
        for item in self.items[:-self.keep_recent_items]:
            # Pula se já está nos recentes
            if item["id"] in recent_ids:
                continue
                
            # Atribui uma pontuação de importância
            importance = 0
            
            # Prioriza por tipo
            if item["type"] == "summary":
                importance += 50
            elif item["type"] == "action":
                importance += 30
            elif item["type"] == "observation":
                importance += 25
                
            # Prioriza se marcado como importante nos metadados
            if item.get("metadata", {}).get("important", False):
                importance += 40
                
            # Prioriza por comprimento do conteúdo
            importance += min(len(item["content"]) / 20, 15)  # No máximo 15 pontos
            
            # Prioriza por recência
            age_factor = max(0, 1 - (time.time() - item["timestamp"]) / (24 * 3600))  # Fator de 0 a 1
            importance += age_factor * 10
            
            candidate_items.append((importance, item))
            
        # Ordena por importância e seleciona até o limite
        remaining_slots = self.max_items - len(recent_items)
        top_items = [item for _, item in sorted(candidate_items, key=lambda x: -x[0])[:remaining_slots]]
        
        # Combina os itens de maior prioridade com os recentes
        return top_items + recent_items
    
    def clear(self) -> None:
        """Limpa toda a memória."""
        self.items = []
        self.current_token_count = 0
        
        # Preserva o resumo mais recente se houver
        if self.summaries:
            last_summary = self.summaries[-1]
            self.summaries = [last_summary]
        else:
            self.summaries = []
            
        logger.info("Memória contextual limpa, mantendo apenas o último resumo.") 