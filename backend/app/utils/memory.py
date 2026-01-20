# In nexustrader/backend/app/utils/memory.py

"""
Financial Memory System for NexusTrader
Stores past analyses and outcomes to enable agent learning.
"""

import chromadb
from chromadb.config import Settings
from typing import List, Dict, Any, Optional
import json
from datetime import datetime


class FinancialMemory:
    """
    Stores and retrieves financial analysis history using ChromaDB.
    Enables agents to learn from past mistakes and successes.
    """
    
    def __init__(self, persist_directory: str = "./chroma_db", collection_name: str = "nexustrader_memory"):
        """
        Initialize the financial memory system.
        
        Args:
            persist_directory: Directory to persist ChromaDB data
            collection_name: Name of the collection for storing memories
        """
        # Create ChromaDB client with persistence
        self.client = chromadb.Client(Settings(
            persist_directory=persist_directory,
            anonymized_telemetry=False
        ))
        
        # Get or create collection
        # Using default embedding function (all-MiniLM-L6-v2) - no API needed!
        try:
            self.collection = self.client.get_collection(name=collection_name)
            print(f"[MEMORY] Loaded existing collection: {collection_name}")
        except:
            self.collection = self.client.create_collection(
                name=collection_name,
                metadata={"description": "NexusTrader financial analysis memory"}
            )
            print(f"[MEMORY] Created new collection: {collection_name}")
    
    def store_analysis(
        self,
        ticker: str,
        analysis_summary: str,
        bull_arguments: str,
        bear_arguments: str,
        final_decision: str,
        strategy: Dict[str, Any],
        metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Store a completed analysis in memory.
        
        Args:
            ticker: Stock ticker
            analysis_summary: Summary of the complete analysis
            bull_arguments: Bull researcher's arguments
            bear_arguments: Bear researcher's arguments
            final_decision: Research manager's final decision
            strategy: Trading strategy details
            metadata: Additional metadata (market conditions, date, etc.)
            
        Returns:
            Memory ID (string)
        """
        # Create a unique ID
        memory_id = f"{ticker}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        # Combine text for embedding (this is what ChromaDB will search on)
        document_text = f"""
Ticker: {ticker}
Analysis Summary: {analysis_summary}
Bull Arguments: {bull_arguments}
Bear Arguments: {bear_arguments}
Final Decision: {final_decision}
Strategy Action: {strategy.get('action', 'UNKNOWN')}
"""
        
        # Prepare metadata
        meta = {
            "ticker": ticker,
            "timestamp": datetime.now().isoformat(),
            "action": strategy.get('action', 'UNKNOWN'),
            "entry_price": str(strategy.get('entry_price', 'N/A')),
            "outcome": "PENDING",  # Will be updated later
            **(metadata or {})
        }
        
        # Store in ChromaDB
        self.collection.add(
            documents=[document_text],
            metadatas=[meta],
            ids=[memory_id]
        )
        
        print(f"[MEMORY] Stored analysis for {ticker} with ID: {memory_id}")
        return memory_id
    
    def update_outcome(
        self,
        memory_id: str,
        actual_outcome: str,
        profit_loss_pct: float,
        lessons_learned: str
    ):
        """
        Update a past analysis with actual outcome.
        
        Args:
            memory_id: ID of the memory to update
            actual_outcome: What actually happened (e.g., "Hit take profit", "Stopped out")
            profit_loss_pct: Actual profit/loss percentage
            lessons_learned: What went right or wrong
        """
        # Get existing data
        result = self.collection.get(ids=[memory_id], include=["metadatas", "documents"])
        
        if not result['ids']:
            print(f"[MEMORY] Warning: Memory ID {memory_id} not found")
            return
        
        # Update metadata
        meta = result['metadatas'][0].copy()
        meta['outcome'] = actual_outcome
        meta['profit_loss_pct'] = str(profit_loss_pct)  # Store as string for JSON compatibility
        meta['lessons_learned'] = lessons_learned
        meta['updated_at'] = datetime.now().isoformat()
        
        # ChromaDB doesn't have direct update, so we delete and re-add with same ID
        document = result['documents'][0]
        
        self.collection.delete(ids=[memory_id])
        self.collection.add(
            documents=[document],
            metadatas=[meta],
            ids=[memory_id]
        )
        
        print(f"[MEMORY] Updated outcome for {memory_id}: {actual_outcome} ({profit_loss_pct:+.2f}%)")
    
    def get_similar_past_analyses(
        self,
        current_situation: str,
        ticker: Optional[str] = None,
        n_results: int = 3,
        min_similarity: float = 0.3  # Lowered default for better matches
    ) -> List[Dict[str, Any]]:
        """
        Find similar past analyses based on current situation.
        
        Args:
            current_situation: Description of current market/stock situation
            ticker: Optional ticker to filter by
            n_results: Maximum number of results to return
            min_similarity: Minimum similarity score (0-1)
            
        Returns:
            List of similar past analyses with similarity scores
        """
        # Check if collection is empty
        count = self.collection.count()
        if count == 0:
            print(f"[MEMORY] No memories stored yet")
            return []
        
        # Build where filter if ticker specified
        where_filter = {"ticker": ticker} if ticker else None
        
        # Query ChromaDB
        try:
            results = self.collection.query(
                query_texts=[current_situation],
                n_results=min(n_results, count),  # Don't request more than available
                where=where_filter,
                include=["documents", "metadatas", "distances"]
            )
        except Exception as e:
            print(f"[MEMORY] Query error: {str(e)}")
            return []
        
        # Format results
        similar_analyses = []
        if results['ids'] and results['ids'][0]:
            for i in range(len(results['ids'][0])):
                # ChromaDB uses distance, convert to similarity (1 - distance)
                distance = results['distances'][0][i]
                similarity = 1 - distance
                
                # Filter by minimum similarity
                if similarity >= min_similarity:
                    similar_analyses.append({
                        "id": results['ids'][0][i],
                        "document": results['documents'][0][i],
                        "metadata": results['metadatas'][0][i],
                        "similarity": similarity,
                        "distance": distance  # Include raw distance for debugging
                    })
        
        print(f"[MEMORY] Found {len(similar_analyses)} similar past analyses (from {count} total)")
        return similar_analyses
    
    def get_past_mistakes(
        self,
        ticker: Optional[str] = None,
        min_loss_pct: float = -5.0,
        n_results: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Retrieve past analyses that resulted in losses.
        
        Args:
            ticker: Optional ticker to filter by
            min_loss_pct: Minimum loss percentage to consider (negative number)
            n_results: Maximum number of results
            
        Returns:
            List of past mistakes with lessons learned
        """
        # Get all memories with outcomes
        all_results = self.collection.get(
            where={"ticker": ticker} if ticker else None,
            include=["documents", "metadatas"]
        )
        
        # Filter for losses
        mistakes = []
        if all_results['ids']:
            for i, meta in enumerate(all_results['metadatas']):
                profit_loss = meta.get('profit_loss_pct')
                if profit_loss and float(profit_loss) <= min_loss_pct:
                    mistakes.append({
                        "id": all_results['ids'][i],
                        "document": all_results['documents'][i],
                        "metadata": meta
                    })
        
        # Sort by loss (worst first) and limit
        mistakes.sort(key=lambda x: float(x['metadata'].get('profit_loss_pct', 0)))
        return mistakes[:n_results]
    
    def get_success_patterns(
        self,
        min_profit_pct: float = 5.0,
        n_results: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Retrieve past analyses that resulted in profits.
        
        Args:
            min_profit_pct: Minimum profit percentage to consider
            n_results: Maximum number of results
            
        Returns:
            List of successful analyses
        """
        all_results = self.collection.get(
            include=["documents", "metadatas"]
        )
        
        # Filter for successes
        successes = []
        if all_results['ids']:
            for i, meta in enumerate(all_results['metadatas']):
                profit_loss = meta.get('profit_loss_pct')
                if profit_loss and float(profit_loss) >= min_profit_pct:
                    successes.append({
                        "id": all_results['ids'][i],
                        "document": all_results['documents'][i],
                        "metadata": meta
                    })
        
        # Sort by profit (best first) and limit
        successes.sort(key=lambda x: float(x['metadata'].get('profit_loss_pct', 0)), reverse=True)
        return successes[:n_results]
    
    def get_all_analyses(
        self,
        limit: int = 20
    ) -> List[Dict[str, Any]]:
        """
        Retrieve all past analyses sorted by most recent.
        """
        all_results = self.collection.get(
            include=["documents", "metadatas"]
        )
        
        analyses = []
        if all_results['ids']:
            for i, _id in enumerate(all_results['ids']):
                analyses.append({
                    "id": _id,
                    "document": all_results['documents'][i],
                    "metadata": all_results['metadatas'][i]
                })
        
        # Sort by timestamp (descending)
        # ID format is often TICKER_YYYYMMDD_HHMMSS
        analyses.sort(key=lambda x: x['id'], reverse=True)
        return analyses[:limit]

    def get_statistics(self) -> Dict[str, Any]:
        """
        Get memory statistics.
        
        Returns:
            Dictionary with statistics (total memories, win rate, etc.)
        """
        all_results = self.collection.get(include=["metadatas"])
        
        total = len(all_results['ids']) if all_results['ids'] else 0
        
        if total == 0:
            return {
                "total_analyses": 0,
                "completed_analyses": 0,
                "win_rate": 0,
                "average_pnl": 0
            }
        
        # Count outcomes
        completed = 0
        wins = 0
        total_pnl = 0
        
        for meta in all_results['metadatas']:
            if meta.get('outcome') != 'PENDING':
                completed += 1
                pnl = meta.get('profit_loss_pct')
                if pnl:
                    pnl_float = float(pnl)
                    total_pnl += pnl_float
                    if pnl_float > 0:
                        wins += 1
        
        win_rate = (wins / completed * 100) if completed > 0 else 0
        avg_pnl = (total_pnl / completed) if completed > 0 else 0
        
        return {
            "total_analyses": total,
            "completed_analyses": completed,
            "pending_analyses": total - completed,
            "wins": wins,
            "losses": completed - wins,
            "win_rate": win_rate,
            "average_pnl": avg_pnl
        }
    
    def clear_all(self):
        """
        Clear all memories (use with caution!).
        """
        # Delete collection and recreate
        collection_name = self.collection.name
        self.client.delete_collection(name=collection_name)
        self.collection = self.client.create_collection(
            name=collection_name,
            metadata={"description": "NexusTrader financial analysis memory"}
        )
        print(f"[MEMORY] Cleared all memories from {collection_name}")


# Global memory instance (initialized in main.py)
_memory_instance = None


def get_memory() -> FinancialMemory:
    """
    Get the global memory instance.
    """
    global _memory_instance
    if _memory_instance is None:
        _memory_instance = FinancialMemory()
    return _memory_instance


def initialize_memory(persist_directory: str = "./chroma_db") -> FinancialMemory:
    """
    Initialize the global memory instance.
    Call this in main.py on startup.
    """
    global _memory_instance
    _memory_instance = FinancialMemory(persist_directory=persist_directory)
    return _memory_instance
