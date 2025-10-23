"""
State Manager

Manages persistent state for the AI agent using SQLite.
"""

import json
import logging
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class StateManager:
    """Manages agent state and execution history."""
    
    def __init__(self, db_path: str = "state/agent_state.db"):
        self.db_path = db_path
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self._init_database()
    
    def _init_database(self):
        """Initialize database schema."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Execution history
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS executions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                instruction_name TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                duration_seconds REAL,
                status TEXT NOT NULL,
                error TEXT
            )
        ''')
        
        # LLM decisions
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS decisions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                execution_id INTEGER,
                timestamp TEXT NOT NULL,
                reasoning TEXT,
                confidence REAL,
                actions_count INTEGER,
                FOREIGN KEY (execution_id) REFERENCES executions(id)
            )
        ''')
        
        # Actions taken
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS actions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                execution_id INTEGER,
                decision_id INTEGER,
                timestamp TEXT NOT NULL,
                tool_name TEXT NOT NULL,
                parameters TEXT,
                result TEXT,
                success INTEGER,
                error TEXT,
                FOREIGN KEY (execution_id) REFERENCES executions(id),
                FOREIGN KEY (decision_id) REFERENCES decisions(id)
            )
        ''')
        
        # Key-value store for misc state
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS state (
                key TEXT PRIMARY KEY,
                value TEXT,
                updated_at TEXT
            )
        ''')
        
        conn.commit()
        conn.close()
        logger.info(f"State database initialized: {self.db_path}")
    
    def start_execution(self, instruction_name: str) -> int:
        """Start a new execution and return its ID."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO executions (instruction_name, timestamp, status)
            VALUES (?, ?, ?)
        ''', (instruction_name, datetime.now().isoformat(), 'running'))
        
        execution_id = cursor.lastrowid
        conn.commit()
        conn.close()
        
        logger.info(f"Started execution {execution_id} for {instruction_name}")
        return execution_id
    
    def end_execution(
        self,
        execution_id: int,
        status: str,
        duration: float,
        error: Optional[str] = None
    ):
        """Mark an execution as complete."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            UPDATE executions
            SET status = ?, duration_seconds = ?, error = ?
            WHERE id = ?
        ''', (status, duration, error, execution_id))
        
        conn.commit()
        conn.close()
        
        logger.info(f"Execution {execution_id} completed: {status}")
    
    def save_decision(
        self,
        execution_id: int,
        reasoning: str,
        confidence: float,
        actions_count: int
    ) -> int:
        """Save an LLM decision."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO decisions (
                execution_id, timestamp, reasoning, confidence, actions_count
            ) VALUES (?, ?, ?, ?, ?)
        ''', (
            execution_id,
            datetime.now().isoformat(),
            reasoning,
            confidence,
            actions_count
        ))
        
        decision_id = cursor.lastrowid
        conn.commit()
        conn.close()
        
        return decision_id
    
    def save_action(
        self,
        execution_id: int,
        decision_id: int,
        tool_name: str,
        parameters: Dict[str, Any],
        result: Any,
        success: bool,
        error: Optional[str] = None
    ):
        """Save an executed action."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO actions (
                execution_id, decision_id, timestamp, tool_name,
                parameters, result, success, error
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            execution_id,
            decision_id,
            datetime.now().isoformat(),
            tool_name,
            json.dumps(parameters),
            json.dumps(result) if result else None,
            1 if success else 0,
            error
        ))
        
        conn.commit()
        conn.close()
    
    def get_recent_executions(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get recent execution history."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT * FROM executions
            ORDER BY timestamp DESC
            LIMIT ?
        ''', (limit,))
        
        rows = cursor.fetchall()
        conn.close()
        
        return [dict(row) for row in rows]
    
    def get_actions_for_execution(self, execution_id: int) -> List[Dict[str, Any]]:
        """Get all actions for an execution."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT * FROM actions
            WHERE execution_id = ?
            ORDER BY timestamp
        ''', (execution_id,))
        
        rows = cursor.fetchall()
        conn.close()
        
        return [dict(row) for row in rows]
    
    def set_state(self, key: str, value: Any):
        """Set a state value."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT OR REPLACE INTO state (key, value, updated_at)
            VALUES (?, ?, ?)
        ''', (key, json.dumps(value), datetime.now().isoformat()))
        
        conn.commit()
        conn.close()
    
    def get_state(self, key: str, default: Any = None) -> Any:
        """Get a state value."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('SELECT value FROM state WHERE key = ?', (key,))
        row = cursor.fetchone()
        conn.close()
        
        if row:
            return json.loads(row[0])
        return default
    
    def cleanup_old_data(self, retention_days: int = 90):
        """Delete data older than retention period."""
        cutoff = datetime.now() - timedelta(days=retention_days)
        cutoff_str = cutoff.isoformat()
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Get old execution IDs
        cursor.execute('''
            SELECT id FROM executions WHERE timestamp < ?
        ''', (cutoff_str,))
        old_ids = [row[0] for row in cursor.fetchall()]
        
        if old_ids:
            placeholders = ','.join('?' * len(old_ids))
            cursor.execute(f'DELETE FROM actions WHERE execution_id IN ({placeholders})', old_ids)
            cursor.execute(f'DELETE FROM decisions WHERE execution_id IN ({placeholders})', old_ids)
            cursor.execute(f'DELETE FROM executions WHERE id IN ({placeholders})', old_ids)
            
            conn.commit()
            logger.info(f"Cleaned up {len(old_ids)} old executions")
        
        conn.close()
