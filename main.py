"""
Main AI Agent

Autonomous agent that periodically executes tasks based on instructions.
"""

import logging
import os
import signal
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

import yaml
from apscheduler.schedulers.blocking import BlockingScheduler
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

from agent.ollama_client import OllamaClient
from agent.tool_registry import get_registry
from agent.state_manager import StateManager

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('logs/agent.log')
    ]
)

logger = logging.getLogger(__name__)


class AIAgent:
    """Main AI Agent coordinating all components."""
    
    def __init__(self, config_path: str = "config.yaml"):
        logger.info("=" * 60)
        logger.info("Initializing AI Agent")
        logger.info("=" * 60)
        
        # Load configuration
        self.config = self._load_config(config_path)
        
        # Initialize components
        self.ollama = OllamaClient(
            base_url=self.config['ollama']['base_url'],
            model=self.config['ollama']['model'],
            timeout=self.config['ollama']['timeout'],
            max_retries=self.config['ollama']['max_retries'],
            temperature=self.config['ollama']['temperature']
        )
        
        self.registry = get_registry()
        self.state_manager = StateManager(
            db_path=self.config['state']['database']
        )
        
        self.running = False
        self.scheduler = None
    
    def _load_config(self, config_path: str) -> dict:
        """Load configuration from YAML file."""
        with open(config_path, 'r') as f:
            return yaml.safe_load(f)
    
    def initialize(self):
        """Initialize the agent (discover tools, load instructions, etc.)."""
        logger.info("Starting initialization...")
        
        # Create necessary directories
        Path("logs").mkdir(exist_ok=True)
        Path("state").mkdir(exist_ok=True)
        
        # Health check Ollama
        logger.info("Checking Ollama connection...")
        if not self.ollama.health_check():
            logger.error("Ollama health check failed. Is Ollama running?")
            logger.error("Run: ./setup-ollama.sh")
            sys.exit(1)
        
        # Discover tools
        logger.info("Discovering tools...")
        tool_count = self.registry.discover_tools("tools")
        logger.info(f"Registered {tool_count} tools")
        
        # List discovered tools
        for tool in self.registry.list_tools():
            logger.info(f"  - {tool.name} ({tool.permissions}): {tool.description}")
        
        # Cleanup old data
        retention_days = self.config['state'].get('retention_days', 90)
        self.state_manager.cleanup_old_data(retention_days)
        
        logger.info("Initialization complete!")
        return True
    
    def execute_goal(self, goal: str):
        """
        Execute a natural language goal using micro-prompting agent.
        
        Perfect for small models (3B params) - uses many tiny LLM calls
        instead of few large ones.
        
        Args:
            goal: Natural language description (e.g., "List my last 3 activities")
        """
        from agent.micro_prompt_agent import MicroPromptAgent
        
        logger.info("============================================================")
        logger.info("🧠 Micro-Prompting Agent (Neuron-Like Architecture)")
        logger.info("============================================================")
        logger.info(f"Goal: {goal}")
        logger.info("")
        
        # Create micro-prompt agent
        agent = MicroPromptAgent(
            ollama=self.ollama,
            tool_registry=self.registry,
            max_retries=3
        )
        
        # Get dry_run setting
        dry_run = self.config.get('agent', {}).get('dry_run', False)
        
        start_time = time.time()
        
        try:
            # Execute goal with micro-prompting
            result = agent.execute_goal(goal, dry_run=dry_run)
            
            duration = time.time() - start_time
            
            # Display output
            logger.info("")
            logger.info("============================================================")
            logger.info("📊 Execution Summary")
            logger.info("============================================================")
            logger.info(f"Goal: {goal}")
            
            # Handle both old multi-task and new single-step formats
            if 'tasks_completed' in result:
                logger.info(f"Tasks completed: {result['tasks_completed']}/{result['tasks_total']}")
            elif 'plan' in result:
                logger.info(f"Plan: {result['plan'].get('description', 'Single-step execution')}")
                logger.info(f"Validated: {'✅' if result.get('validated', False) else '⚠️'}")
            
            logger.info(f"Duration: {duration:.2f}s")
            logger.info("")
            logger.info("Output:")
            logger.info(result.get('output', str(result.get('result', 'No output'))))
            logger.info("============================================================")
            
            return result
            
        except Exception as e:
            duration = time.time() - start_time
            logger.error(f"Execution failed: {e}", exc_info=True)
            return {
                'success': False,
                'error': str(e),
                'duration': duration
            }
    
    def run_once(self, instruction_name: Optional[str] = None):
        """
        Run enabled instructions once using micro-prompting.
        
        Args:
            instruction_name: Optional specific instruction to run. If None, runs all enabled instructions.
        """
        logger.info("Running instructions with micro-prompting...")
        
        # Load instruction files
        instructions_dir = Path("instructions")
        instruction_files = list(instructions_dir.glob("*.yaml"))
        
        if not instruction_files:
            logger.warning("No instruction files found in instructions/")
            return
        
        # Filter to specific instruction if provided
        if instruction_name:
            instruction_files = [
                f for f in instruction_files 
                if f.stem == instruction_name
            ]
            if not instruction_files:
                logger.error(f"Instruction not found: {instruction_name}")
                return
        
        # Execute each instruction
        for instruction_file in instruction_files:
            try:
                with open(instruction_file, 'r') as f:
                    instruction_data = yaml.safe_load(f)
                
                # Check if enabled (default to True if not specified)
                if not instruction_data.get('enabled', True):
                    logger.info(f"Skipping disabled instruction: {instruction_file.stem}")
                    continue
                
                # Get goal from instruction
                goal = instruction_data.get('goal')
                if not goal:
                    logger.warning(f"No goal found in {instruction_file.name}, skipping")
                    continue
                
                logger.info(f"Executing instruction: {instruction_file.stem}")
                self.execute_goal(goal)
                
            except Exception as e:
                logger.error(f"Error loading {instruction_file.name}: {e}")
        
        logger.info("One-time execution complete!")
    
    def start_scheduler(self):
        """
        Start the scheduler for periodic execution using micro-prompting.
        Reads instruction files and schedules them based on 'schedule' field.
        """
        logger.info("Starting scheduler with micro-prompting...")
        
        self.scheduler = BlockingScheduler()
        
        # Load all instruction files
        instructions_dir = Path("instructions")
        instruction_files = list(instructions_dir.glob("*.yaml"))
        
        for instruction_file in instruction_files:
            try:
                with open(instruction_file, 'r') as f:
                    instruction_data = yaml.safe_load(f)
                
                # Check if enabled
                if not instruction_data.get('enabled', True):
                    continue
                
                goal = instruction_data.get('goal')
                schedule = instruction_data.get('schedule', '').lower()
                
                if not goal or not schedule:
                    continue
                
                instruction_name = instruction_file.stem
                
                # Schedule based on frequency
                if schedule == 'hourly':
                    self.scheduler.add_job(
                        lambda g=goal: self.execute_goal(g),
                        'interval',
                        hours=1,
                        id=f"hourly_{instruction_name}",
                        name=instruction_name
                    )
                    logger.info(f"Scheduled hourly: {instruction_name}")
                    
                elif schedule == 'daily':
                    self.scheduler.add_job(
                        lambda g=goal: self.execute_goal(g),
                        'cron',
                        hour=9,  # Run at 9 AM
                        id=f"daily_{instruction_name}",
                        name=instruction_name
                    )
                    logger.info(f"Scheduled daily: {instruction_name}")
                    
            except Exception as e:
                logger.error(f"Error loading {instruction_file.name}: {e}")
        
        if not self.scheduler.get_jobs():
            logger.warning("No scheduled jobs found!")
            return
        
        # Setup signal handlers
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
        
        self.running = True
        logger.info("Scheduler started! Press Ctrl+C to stop.")
        logger.info(f"Jobs scheduled: {len(self.scheduler.get_jobs())}")
        
        try:
            self.scheduler.start()
        except (KeyboardInterrupt, SystemExit):
            logger.info("Scheduler stopped")
    
    def _signal_handler(self, signum, frame):
        """Handle shutdown signals."""
        logger.info("Received shutdown signal")
        if self.scheduler:
            self.scheduler.shutdown(wait=False)
        self.running = False
        sys.exit(0)


def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(description='AI Agent with Micro-Prompting')
    parser.add_argument(
        '--config',
        default='config.yaml',
        help='Path to configuration file'
    )
    parser.add_argument(
        '--goal',
        type=str,
        help='Natural language goal (e.g., "List my last 3 activities")'
    )
    parser.add_argument(
        '--instruction',
        type=str,
        help='Load goal from instruction file (YAML with goal field)'
    )
    parser.add_argument(
        '--once',
        action='store_true',
        help='Run all instructions once'
    )
    
    args = parser.parse_args()
    
    # Create agent
    agent = AIAgent(config_path=args.config)
    
    # Initialize
    if not agent.initialize():
        logger.error("Initialization failed")
        sys.exit(1)
    
    # Run based on mode
    if args.goal:
        # Direct goal execution
        agent.execute_goal(args.goal)
    elif args.instruction:
        # Load goal from instruction file
        instruction_path = Path("instructions") / f"{args.instruction}.yaml"
        if not instruction_path.exists():
            logger.error(f"Instruction file not found: {instruction_path}")
            sys.exit(1)
        
        with open(instruction_path) as f:
            data = yaml.safe_load(f)
        
        goal = data.get('goal')
        if not goal:
            logger.error(f"Instruction file must have 'goal' field")
            sys.exit(1)
        
        logger.info(f"Loaded instruction: {data.get('name', args.instruction)}")
        agent.execute_goal(goal)
    elif args.once:
        # Run all instructions once
        instructions_dir = Path("instructions")
        for filepath in instructions_dir.glob("*.yaml"):
            if filepath.stem.startswith("_") or filepath.stem.endswith("_v2"):
                continue  # Skip private and old v2 files
            
            with open(filepath) as f:
                data = yaml.safe_load(f)
            
            goal = data.get('goal')
            if goal:
                logger.info(f"\n{'='*60}")
                logger.info(f"Executing: {filepath.stem}")
                logger.info(f"{'='*60}")
                agent.execute_goal(goal)
    else:
        # Start scheduler
        logger.info("Scheduler mode not yet implemented for micro-prompting")
        logger.info("Use --goal or --instruction or --once")
        sys.exit(1)


if __name__ == "__main__":
    main()
