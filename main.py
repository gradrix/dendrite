"""
Main AI Agent

Autonomous agent that periodically executes tasks based on instructions.
"""

import logging
import signal
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

import yaml
from apscheduler.schedulers.blocking import BlockingScheduler

from agent.ollama_client import OllamaClient
from agent.tool_registry import get_registry
from agent.instruction_loader import InstructionLoader
from agent.action_executor import ActionExecutor
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
        self.instruction_loader = InstructionLoader()
        self.state_manager = StateManager(
            db_path=self.config['state']['database']
        )
        self.executor = ActionExecutor(
            registry=self.registry,
            dry_run=self.config['agent']['dry_run'],
            max_actions=self.config['safety']['max_actions_per_run'],
            cooldown_seconds=self.config['safety']['action_cooldown_seconds']
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
        
        # Load instructions
        logger.info("Loading instructions...")
        instructions = self.instruction_loader.load_all()
        logger.info(f"Loaded {len(instructions)} instruction files")
        
        for inst in instructions:
            logger.info(f"  - {inst.name} ({inst.schedule})")
        
        # Cleanup old data
        retention_days = self.config['state'].get('retention_days', 90)
        self.state_manager.cleanup_old_data(retention_days)
        
        logger.info("Initialization complete!")
        return True
    
    def execute_instruction(self, instruction_name: str):
        """Execute a single instruction."""
        instruction = self.instruction_loader.get(instruction_name)
        if not instruction:
            logger.error(f"Instruction not found: {instruction_name}")
            return
        
        logger.info("=" * 60)
        logger.info(f"Executing: {instruction.name}")
        logger.info("=" * 60)
        
        start_time = time.time()
        execution_id = self.state_manager.start_execution(instruction.name)
        
        try:
            # Get available tools (filtered by instruction)
            available_tools = [
                tool.to_dict() for tool in self.registry.list_tools()
                if instruction.is_tool_allowed(tool.name)
            ]
            
            if not available_tools:
                logger.warning("No tools available for this instruction")
                self.state_manager.end_execution(
                    execution_id, 'completed', time.time() - start_time
                )
                return
            
            logger.info(f"Available tools: {len(available_tools)}")
            
            # Build context
            context = instruction.get_context_prompt()
            
            # Add recent history
            recent = self.state_manager.get_recent_executions(limit=3)
            if recent:
                context += "\n\nRecent execution history:\n"
                for exec in recent:
                    context += f"  - {exec['instruction_name']} at {exec['timestamp']}: {exec['status']}\n"
            
            # Multi-step execution loop
            max_iterations = self.config.get('agent', {}).get('max_iterations', 10)
            all_results = []
            
            for iteration in range(max_iterations):
                logger.info(f"\n{'='*60}")
                logger.info(f"Iteration {iteration + 1}/{max_iterations}")
                logger.info(f"{'='*60}")
                
                # Build prompt with previous results
                prompt = f"Current time: {datetime.now().isoformat()}\n\n"
                
                if all_results:
                    prompt += "Previous actions and their results:\n"
                    for prev_result in all_results[-5:]:  # Last 5 results
                        tool_name = prev_result.get('tool_name', 'unknown')
                        success = prev_result.get('success', False)
                        result_data = prev_result.get('result', {})
                        prompt += f"  - {tool_name}: {'✅ Success' if success else '❌ Failed'}\n"
                        if result_data:
                            prompt += f"    Result: {str(result_data)[:200]}\n"
                    prompt += "\n"
                
                prompt += "What actions should be taken next? (Return empty actions array if workflow is complete)"
                
                # Query LLM for decision
                logger.info("Querying LLM for decision...")
                decision = self.ollama.function_call(
                    prompt=prompt,
                    tools=available_tools,
                    context=context
                )
                
                logger.info(f"LLM Decision: {decision['reasoning']}")
                logger.info(f"Confidence: {decision['confidence']}")
                logger.info(f"Actions to execute: {len(decision['actions'])}")
                
                # Save decision
                decision_id = self.state_manager.save_decision(
                    execution_id=execution_id,
                    reasoning=decision['reasoning'],
                    confidence=decision['confidence'],
                    actions_count=len(decision['actions'])
                )
                
                # Check if no more actions (workflow complete)
                if not decision['actions']:
                    logger.info("✅ Workflow complete - LLM returned no more actions")
                    break
                
                # Execute actions
                results = self.executor.execute_actions(
                    actions=decision['actions'],
                    instruction=instruction
                )
                
                # Save action results and build result summary
                for action, result in zip(decision['actions'], results):
                    result_record = {
                        'tool_name': action['tool'],
                        'parameters': action.get('params'),
                        'result': result.get('result'),
                        'success': result.get('success', False),
                        'error': result.get('error')
                    }
                    all_results.append(result_record)
                    
                    self.state_manager.save_action(
                        execution_id=execution_id,
                        decision_id=decision_id,
                        **result_record
                    )
                
                # Log iteration summary
                successful = sum(1 for r in results if r.get('success'))
                logger.info(f"Iteration complete: {successful}/{len(results)} actions successful")
            
            if iteration == max_iterations - 1:
                logger.warning(f"⚠️  Reached max iterations ({max_iterations}) - workflow may be incomplete")
            
            # Mark as complete
            duration = time.time() - start_time
            self.state_manager.end_execution(
                execution_id, 'completed', duration
            )
            
            logger.info(f"Execution completed in {duration:.2f}s")
            
        except Exception as e:
            logger.error(f"Error during execution: {e}", exc_info=True)
            duration = time.time() - start_time
            self.state_manager.end_execution(
                execution_id, 'error', duration, str(e)
            )
    
    def run_once(self):
        """Run all enabled instructions once."""
        logger.info("Running all enabled instructions once...")
        
        instructions = self.instruction_loader.load_all()
        
        for instruction in instructions:
            if instruction.enabled:
                self.execute_instruction(instruction.name)
        
        logger.info("One-time execution complete!")
    
    def start_scheduler(self):
        """Start the scheduler for periodic execution."""
        logger.info("Starting scheduler...")
        
        self.scheduler = BlockingScheduler()
        
        # Add jobs for hourly instructions
        hourly_instructions = self.instruction_loader.get_scheduled("hourly")
        for instruction in hourly_instructions:
            self.scheduler.add_job(
                lambda name=instruction.name: self.execute_instruction(name),
                'interval',
                hours=1,
                id=f"hourly_{instruction.name}",
                name=instruction.name
            )
            logger.info(f"Scheduled hourly: {instruction.name}")
        
        # Add jobs for daily instructions
        daily_instructions = self.instruction_loader.get_scheduled("daily")
        for instruction in daily_instructions:
            self.scheduler.add_job(
                lambda name=instruction.name: self.execute_instruction(name),
                'cron',
                hour=9,  # Run at 9 AM
                id=f"daily_{instruction.name}",
                name=instruction.name
            )
            logger.info(f"Scheduled daily: {instruction.name}")
        
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
    
    parser = argparse.ArgumentParser(description='AI Agent for Strava monitoring')
    parser.add_argument(
        '--config',
        default='config.yaml',
        help='Path to configuration file'
    )
    parser.add_argument(
        '--once',
        action='store_true',
        help='Run once instead of starting scheduler'
    )
    parser.add_argument(
        '--instruction',
        help='Run specific instruction only'
    )
    
    args = parser.parse_args()
    
    # Create agent
    agent = AIAgent(config_path=args.config)
    
    # Initialize
    if not agent.initialize():
        logger.error("Initialization failed")
        sys.exit(1)
    
    # Run based on mode
    if args.instruction:
        # Run specific instruction
        agent.execute_instruction(args.instruction)
    elif args.once:
        # Run all instructions once
        agent.run_once()
    else:
        # Start scheduler
        agent.start_scheduler()


if __name__ == "__main__":
    main()
