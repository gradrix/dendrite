"""
Tool Discovery: 3-stage filtering for scalable tool selection.
Phase 8d: Semantic search → Statistical ranking → LLM selection.

Enables efficient tool discovery even with thousands of tools.
"""

import os
from typing import List, Dict, Optional, Tuple
import chromadb
from chromadb.config import Settings
from neural_engine.core.execution_store import ExecutionStore
from neural_engine.core.tool_registry import ToolRegistry


class ToolDiscovery:
    """
    3-stage tool discovery system:
    Stage 1: Semantic Search (Chroma) - 1000+ tools → 20 candidates
    Stage 2: Statistical Ranking (PostgreSQL) - 20 → 5 top performers  
    Stage 3: LLM Selection (ToolSelectorNeuron) - 5 → 1 best tool
    """
    
    def __init__(self,
                 tool_registry: ToolRegistry,
                 execution_store: Optional[ExecutionStore] = None,
                 chroma_path: str = "./chroma_data"):
        """
        Initialize ToolDiscovery.
        
        Args:
            tool_registry: ToolRegistry instance
            execution_store: ExecutionStore for statistics (creates new if None)
            chroma_path: Path to Chroma persistent storage
        """
        self.tool_registry = tool_registry
        self.execution_store = execution_store or ExecutionStore()
        
        # Initialize Chroma with PersistentClient for better isolation
        self.chroma_client = chromadb.PersistentClient(path=chroma_path)
        
        # Get or create collection
        try:
            self.collection = self.chroma_client.get_collection(name="tools")
        except:
            self.collection = self.chroma_client.create_collection(
                name="tools",
                metadata={"hnsw:space": "cosine"}
            )
    
    def index_all_tools(self):
        """
        Index all tools in the registry for semantic search.
        Call this after adding new tools or during initialization.
        """
        print(f"Indexing tools from registry...")
        
        tools = self.tool_registry.get_all_tools()
        tool_count = len(tools)
        
        if tool_count == 0:
            print("  No tools to index")
            return
        
        # Prepare data for Chroma
        documents = []
        metadatas = []
        ids = []
        
        for tool_name, tool_class in tools.items():
            # Create rich description for embeddings
            description = getattr(tool_class, 'description', '')
            params = getattr(tool_class, 'parameters', {})
            
            # Build searchable document
            param_desc = " ".join([
                f"{name}: {info.get('description', '')}"
                for name, info in params.items()
            ])
            
            document = f"{tool_name} {description} {param_desc}"
            
            documents.append(document)
            metadatas.append({
                "tool_name": tool_name,
                "description": description,
                "parameter_count": len(params)
            })
            ids.append(tool_name)
        
        # Add to Chroma (upsert - will update if already exists)
        self.collection.upsert(
            documents=documents,
            metadatas=metadatas,
            ids=ids
        )
        
        print(f"  ✓ Indexed {tool_count} tools")
        return tool_count
    
    def semantic_search(self, goal_text: str, n_results: int = 20) -> List[Dict]:
        """
        Stage 1: Semantic search using Chroma embeddings.
        
        Args:
            goal_text: User's goal/query
            n_results: Number of candidates to return
        
        Returns:
            List of dicts with tool_name and distance/similarity score
        """
        if n_results <= 0:
            return []
            
        if self.collection.count() == 0:
            # No tools indexed yet, index them now
            self.index_all_tools()
        
        # Query Chroma for semantically similar tools
        results = self.collection.query(
            query_texts=[goal_text],
            n_results=min(n_results, self.collection.count())
        )
        
        # Format results as list of dicts
        candidates = []
        if results['ids'] and len(results['ids']) > 0:
            tool_names = results['ids'][0]
            distances = results['distances'][0]
            metadatas = results['metadatas'][0] if results['metadatas'] else [{}] * len(tool_names)
            
            for tool_name, distance, metadata in zip(tool_names, distances, metadatas):
                candidates.append({
                    'tool_name': tool_name,
                    'distance': distance,
                    'description': metadata.get('description', '')
                })
        
        return candidates
    
    def statistical_ranking(self, candidates: List[Dict], limit: int = 5) -> List[Dict]:
        """
        Stage 2: Rank tools by statistical performance.
        
        Uses a scoring formula:
        score = success_rate * log(total_executions + 1) * recency_factor
        
        Args:
            candidates: List of candidate dicts from semantic search (with tool_name, distance)
            limit: Number of top tools to return
        
        Returns:
            List of dicts with tool_name, score, and metadata, sorted by score
        """
        scored_tools = []
        
        for candidate in candidates:
            tool_name = candidate['tool_name']
            stats = self.execution_store.get_tool_statistics(tool_name)
            
            if stats is None:
                # No statistics yet - assign neutral score
                score = 0.5  # Neutral score for new tools
                scored_tools.append({
                    "tool_name": tool_name,
                    "score": score,
                    "success_rate": None,
                    "executions": 0,
                    "reason": "new_tool"
                })
            else:
                # Calculate composite score
                import math
                
                success_rate = stats['success_rate']
                total_execs = stats['total_executions']
                
                # Recency factor (higher score if used recently)
                last_used = stats.get('last_used')
                if last_used:
                    from datetime import datetime
                    days_since_use = (datetime.now() - datetime.fromisoformat(str(last_used))).days
                    recency_factor = max(0.5, 1.0 - (days_since_use / 365))  # Decay over a year
                else:
                    recency_factor = 0.5
                
                # Composite score: success * log(usage) * recency
                # log(usage) prevents over-weighting frequently-used but failing tools
                score = success_rate * math.log(total_execs + 1) * recency_factor
                
                scored_tools.append({
                    "tool_name": tool_name,
                    "score": score,
                    "success_rate": success_rate,
                    "executions": total_execs,
                    "recency_factor": recency_factor,
                    "distance": candidate.get('distance', 0.0),
                    "description": candidate.get('description', ''),
                    "reason": "statistics"
                })
        
        # Sort by score (highest first)
        scored_tools.sort(key=lambda x: x['score'], reverse=True)
        
        return scored_tools[:limit]
    
    def discover_tools(self,
                      goal_text: str,
                      semantic_limit: int = 20,
                      ranking_limit: int = 5) -> List[Dict]:
        """
        Complete 3-stage discovery pipeline (Stages 1 & 2).
        Stage 3 (LLM selection) happens in ToolSelectorNeuron.
        
        Args:
            goal_text: User's goal/query
            semantic_limit: Number of candidates from semantic search
            ranking_limit: Number of top-ranked tools to return
        
        Returns:
            List of top-ranked tools with scores and metadata
        """
        # Stage 1: Semantic search
        candidates = self.semantic_search(goal_text, n_results=semantic_limit)
        
        if not candidates:
            return []
        
        # Stage 2: Statistical ranking
        ranked_tools = self.statistical_ranking(candidates, limit=ranking_limit)
        
        return ranked_tools
    
    def reindex_tool(self, tool_name: str):
        """
        Reindex a single tool (useful after tool updates).
        
        Args:
            tool_name: Name of tool to reindex
        """
        tool_class = self.tool_registry.get_tool(tool_name)
        
        if tool_class is None:
            print(f"  Tool not found: {tool_name}")
            return False
        
        # Create document
        description = getattr(tool_class, 'description', '')
        params = getattr(tool_class, 'parameters', {})
        
        param_desc = " ".join([
            f"{name}: {info.get('description', '')}"
            for name, info in params.items()
        ])
        
        document = f"{tool_name} {description} {param_desc}"
        
        # Upsert to Chroma
        self.collection.upsert(
            documents=[document],
            metadatas=[{
                "tool_name": tool_name,
                "description": description,
                "parameter_count": len(params)
            }],
            ids=[tool_name]
        )
        
        print(f"  ✓ Reindexed: {tool_name}")
        return True
    
    def remove_tool_from_index(self, tool_name: str):
        """
        Remove a tool from the search index.
        
        Args:
            tool_name: Name of tool to remove
        """
        try:
            self.collection.delete(ids=[tool_name])
            print(f"  ✓ Removed from index: {tool_name}")
            return True
        except Exception as e:
            print(f"  Error removing {tool_name}: {e}")
            return False
    
    def get_indexed_tools(self) -> List[str]:
        """
        Get list of all indexed tool names.
        
        Returns:
            List of tool names in the index
        """
        # Get all IDs from collection
        all_data = self.collection.get()
        return all_data['ids'] if all_data['ids'] else []
    
    def get_index_stats(self) -> Dict:
        """
        Get statistics about the search index.
        
        Returns:
            Dictionary with index statistics
        """
        count = self.collection.count()
        indexed_tools = self.get_indexed_tools()
        
        # Get tool registry stats
        all_tools = self.tool_registry.get_all_tools()
        registry_count = len(all_tools)
        
        # Check for tools not indexed
        not_indexed = set(all_tools.keys()) - set(indexed_tools)
        
        # Check for indexed tools no longer in registry
        stale = set(indexed_tools) - set(all_tools.keys())
        
        return {
            "indexed_tools": count,
            "registry_tools": registry_count,
            "not_indexed": list(not_indexed),
            "stale_indexed": list(stale),
            "coverage": count / registry_count if registry_count > 0 else 0
        }
    
    def sync_index(self):
        """
        Synchronize index with tool registry.
        Adds missing tools and removes stale entries.
        """
        print("Synchronizing tool index...")
        
        stats = self.get_index_stats()
        
        # Add missing tools
        if stats['not_indexed']:
            print(f"  Adding {len(stats['not_indexed'])} missing tools...")
            self.index_all_tools()
        
        # Remove stale tools
        if stats['stale_indexed']:
            print(f"  Removing {len(stats['stale_indexed'])} stale tools...")
            for tool_name in stats['stale_indexed']:
                self.remove_tool_from_index(tool_name)
        
        print(f"  ✓ Index synchronized: {self.collection.count()} tools")
    
    def search_by_description(self, query: str, limit: int = 10) -> List[Dict]:
        """
        Search tools by description only (no statistical ranking).
        Useful for browsing/discovery UI.
        
        Args:
            query: Search query
            limit: Max results to return
        
        Returns:
            List of tool metadata with relevance scores
        """
        results = self.collection.query(
            query_texts=[query],
            n_results=min(limit, self.collection.count())
        )
        
        tools = []
        if results['ids'] and len(results['ids']) > 0:
            tool_ids = results['ids'][0]
            metadatas = results['metadatas'][0]
            distances = results['distances'][0] if results['distances'] else [0] * len(tool_ids)
            
            for tool_id, metadata, distance in zip(tool_ids, metadatas, distances):
                tools.append({
                    "tool_name": tool_id,
                    "description": metadata.get('description', ''),
                    "parameter_count": metadata.get('parameter_count', 0),
                    "relevance": 1.0 - distance  # Convert distance to relevance score
                })
        
        return tools
    
    def close(self):
        """Close connections."""
        if self.execution_store:
            self.execution_store.close()
