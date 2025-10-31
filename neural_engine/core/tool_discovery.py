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
    
    def find_similar_tools(self, 
                          tool_name: str, 
                          similarity_threshold: float = 0.9,
                          limit: int = 10) -> List[Dict]:
        """
        Find tools similar to the given tool (potential duplicates).
        
        Phase 9g: Uses embeddings to detect similar/duplicate tools.
        
        Args:
            tool_name: Name of reference tool
            similarity_threshold: Cosine similarity threshold (0.9 = 90% similar)
            limit: Maximum number of similar tools to return
        
        Returns:
            List of similar tools with similarity scores, sorted by similarity
        """
        # Get the reference tool
        tool_class = self.tool_registry.get_tool(tool_name)
        if tool_class is None:
            return []
        
        # Build query from tool description
        description = getattr(tool_class, 'description', '')
        params = getattr(tool_class, 'parameters', {})
        
        param_desc = " ".join([
            f"{name}: {info.get('description', '')}"
            for name, info in params.items()
        ])
        
        query = f"{description} {param_desc}"
        
        # Search for similar tools
        results = self.collection.query(
            query_texts=[query],
            n_results=min(limit + 1, self.collection.count())  # +1 to exclude self
        )
        
        similar_tools = []
        if results['ids'] and len(results['ids']) > 0:
            tool_ids = results['ids'][0]
            metadatas = results['metadatas'][0]
            distances = results['distances'][0] if results['distances'] else [0] * len(tool_ids)
            
            for tool_id, metadata, distance in zip(tool_ids, metadatas, distances):
                # Skip the reference tool itself
                if tool_id == tool_name:
                    continue
                
                # Calculate similarity (1 - distance for cosine distance)
                similarity = 1.0 - distance
                
                # Only include if above threshold
                if similarity >= similarity_threshold:
                    similar_tools.append({
                        "tool_name": tool_id,
                        "description": metadata.get('description', ''),
                        "parameter_count": metadata.get('parameter_count', 0),
                        "similarity": similarity,
                        "is_potential_duplicate": similarity >= 0.95  # 95%+ is likely duplicate
                    })
                    
                    # Stop if we've reached the limit
                    if len(similar_tools) >= limit:
                        break
        
        # Sort by similarity (highest first)
        similar_tools.sort(key=lambda x: x['similarity'], reverse=True)
        
        return similar_tools
    
    def find_all_duplicates(self, 
                           similarity_threshold: float = 0.9) -> List[Dict]:
        """
        Find all potential duplicate tool pairs across the entire registry.
        
        Phase 9g: Scans all tools to find duplicates.
        
        Args:
            similarity_threshold: Cosine similarity threshold
        
        Returns:
            List of duplicate pairs with similarity scores
        """
        print(f"Scanning for duplicate tools (threshold: {similarity_threshold:.0%})...")
        
        all_tools = self.tool_registry.get_all_tools()
        duplicate_pairs = []
        checked_pairs = set()
        
        for tool_name in all_tools.keys():
            # Find similar tools
            similar = self.find_similar_tools(
                tool_name=tool_name,
                similarity_threshold=similarity_threshold,
                limit=20
            )
            
            for sim_tool in similar:
                # Create sorted pair to avoid duplicates (A,B) vs (B,A)
                pair = tuple(sorted([tool_name, sim_tool['tool_name']]))
                
                if pair not in checked_pairs:
                    checked_pairs.add(pair)
                    
                    # Get statistics for both tools
                    stats_a = self.execution_store.get_tool_statistics(pair[0])
                    stats_b = self.execution_store.get_tool_statistics(pair[1])
                    
                    duplicate_pairs.append({
                        "tool_a": pair[0],
                        "tool_b": pair[1],
                        "similarity": sim_tool['similarity'],
                        "is_potential_duplicate": sim_tool['is_potential_duplicate'],
                        "stats_a": stats_a or {"total_executions": 0, "success_rate": None},
                        "stats_b": stats_b or {"total_executions": 0, "success_rate": None},
                        "recommendation": self._generate_consolidation_recommendation(
                            pair[0], pair[1], 
                            stats_a or {}, stats_b or {},
                            sim_tool['similarity']
                        )
                    })
        
        # Sort by similarity (highest first)
        duplicate_pairs.sort(key=lambda x: x['similarity'], reverse=True)
        
        print(f"  Found {len(duplicate_pairs)} potential duplicate pairs")
        
        return duplicate_pairs
    
    def _generate_consolidation_recommendation(self,
                                              tool_a: str,
                                              tool_b: str,
                                              stats_a: Dict,
                                              stats_b: Dict,
                                              similarity: float) -> Dict:
        """
        Generate recommendation for consolidating duplicate tools.
        
        Considers:
        - Usage frequency (keep more used tool)
        - Success rate (keep more reliable tool)
        - Recency (keep more recently used)
        """
        execs_a = stats_a.get('total_executions', 0)
        execs_b = stats_b.get('total_executions', 0)
        success_a = stats_a.get('success_rate', 0)
        success_b = stats_b.get('success_rate', 0)
        
        # Calculate scores for each tool
        score_a = execs_a * (success_a or 0.5)
        score_b = execs_b * (success_b or 0.5)
        
        # Determine which to keep
        if score_a > score_b * 1.2:  # 20% better
            keep = tool_a
            deprecate = tool_b
            reason = f"{tool_a} has better usage and reliability"
        elif score_b > score_a * 1.2:
            keep = tool_b
            deprecate = tool_a
            reason = f"{tool_b} has better usage and reliability"
        elif execs_a > execs_b:
            keep = tool_a
            deprecate = tool_b
            reason = f"{tool_a} is used more frequently ({execs_a} vs {execs_b} executions)"
        elif execs_b > execs_a:
            keep = tool_b
            deprecate = tool_a
            reason = f"{tool_b} is used more frequently ({execs_b} vs {execs_a} executions)"
        else:
            # If usage is equal, keep alphabetically first
            keep = tool_a if tool_a < tool_b else tool_b
            deprecate = tool_b if tool_a < tool_b else tool_a
            reason = "Usage is similar - alphabetical selection"
        
        return {
            "action": "consolidate",
            "keep": keep,
            "deprecate": deprecate,
            "reason": reason,
            "confidence": "high" if similarity >= 0.95 else "medium"
        }
    
    def compare_tools_side_by_side(self, tool_a: str, tool_b: str) -> Dict:
        """
        Detailed side-by-side comparison of two tools.
        
        Phase 9g: Compare everything - description, parameters, code, statistics.
        
        Args:
            tool_a: First tool name
            tool_b: Second tool name
        
        Returns:
            Comprehensive comparison dictionary
        """
        # Get tool classes
        class_a = self.tool_registry.get_tool(tool_a)
        class_b = self.tool_registry.get_tool(tool_b)
        
        if not class_a or not class_b:
            return {"error": "One or both tools not found"}
        
        # Get descriptions
        desc_a = getattr(class_a, 'description', '')
        desc_b = getattr(class_b, 'description', '')
        
        # Get parameters
        params_a = getattr(class_a, 'parameters', {})
        params_b = getattr(class_b, 'parameters', {})
        
        # Get statistics
        stats_a = self.execution_store.get_tool_statistics(tool_a)
        stats_b = self.execution_store.get_tool_statistics(tool_b)
        
        # Calculate similarity between descriptions
        query_a = f"{tool_a} {desc_a}"
        results = self.collection.query(query_texts=[query_a], n_results=50)
        
        similarity = 0.0
        if results['ids'] and tool_b in results['ids'][0]:
            idx = results['ids'][0].index(tool_b)
            distance = results['distances'][0][idx] if results['distances'] else 0
            similarity = 1.0 - distance
        
        # Compare parameters
        params_a_names = set(params_a.keys())
        params_b_names = set(params_b.keys())
        common_params = params_a_names & params_b_names
        unique_to_a = params_a_names - params_b_names
        unique_to_b = params_b_names - params_a_names
        
        return {
            "tool_a": {
                "name": tool_a,
                "description": desc_a,
                "parameters": list(params_a.keys()),
                "parameter_count": len(params_a),
                "statistics": stats_a or {"total_executions": 0, "success_rate": None}
            },
            "tool_b": {
                "name": tool_b,
                "description": desc_b,
                "parameters": list(params_b.keys()),
                "parameter_count": len(params_b),
                "statistics": stats_b or {"total_executions": 0, "success_rate": None}
            },
            "comparison": {
                "similarity": similarity,
                "is_likely_duplicate": similarity >= 0.95,
                "common_parameters": list(common_params),
                "unique_to_a": list(unique_to_a),
                "unique_to_b": list(unique_to_b),
                "parameter_overlap": len(common_params) / max(len(params_a_names), len(params_b_names)) if params_a_names or params_b_names else 0
            },
            "recommendation": self._generate_consolidation_recommendation(
                tool_a, tool_b,
                stats_a or {}, stats_b or {},
                similarity
            )
        }
    
    def close(self):
        """Close connections."""
        if self.execution_store:
            self.execution_store.close()
