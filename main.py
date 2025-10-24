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
    
    def execute_instruction_v2(self, instruction_name: str):
        """
        Execute instruction using step-by-step execution (v2).
        Each step gets fresh LLM context instead of accumulated context.
        Better for small models.
        """
        from agent.instruction_parser_v2 import InstructionV2
        from agent.step_executor import StepExecutor
        from agent.template_engine import TemplateEngine
        
        logger.info(f"🚀 Starting execution (v2): {instruction_name}")
        
        try:
            # Load instruction with new parser
            instruction_path = Path("instructions") / f"{instruction_name}.yaml"
            if not instruction_path.exists():
                logger.error(f"Instruction file not found: {instruction_path}")
                return
            
            instruction = InstructionV2(instruction_path)
            logger.info(f"Loaded: {instruction.name}")
            logger.info(f"Execution mode: {instruction.execution_mode}")
            
            # Create execution record
            execution_id = self.state_manager.start_execution(instruction.name)
            start_time = time.time()
            
            # Create step executor with fresh template context
            template = TemplateEngine()
            executor = StepExecutor(self.ollama, self.registry, template)
            
            # Get execution order
            steps = instruction.get_execution_order()
            logger.info(f"📋 Execution plan: {len(steps)} steps")
            for idx, step in enumerate(steps, 1):
                logger.info(f"  {idx}. {step.id}: {step.description}")
            
            # Execute each step independently
            step_count = 0
            failed_steps = []
            
            for idx, step in enumerate(steps, 1):
                logger.info(f"\n{'='*60}")
                logger.info(f"Step {idx}/{len(steps)}: {step.id}")
                logger.info(f"Description: {step.description}")
                logger.info(f"Tool: {step.tool}")
                if step.depends_on:
                    logger.info(f"Dependencies: {', '.join(step.depends_on)}")
                if step.is_loop_step():
                    logger.info(f"Loop: {step.loop}")
                logger.info(f"{'='*60}\n")
                
                try:
                    # Execute step with fresh LLM context
                    result = executor.execute_step(
                        step, 
                        dry_run=self.config['agent']['dry_run']
                    )
                    
                    step_count += 1
                    
                    if result['success']:
                        logger.info(f"✅ Step {step.id} completed successfully")
                        
                        # Log result summary
                        if result.get('result'):
                            result_summary = executor._summarize_result(result['result'])
                            logger.info(f"Result: {result_summary}")
                    else:
                        logger.error(f"❌ Step {step.id} failed: {result.get('error', 'Unknown error')}")
                        failed_steps.append(step.id)
                        
                        # Stop if required step failed
                        if not step.optional:
                            logger.error(f"Required step failed, stopping execution")
                            break
                
                except Exception as e:
                    logger.error(f"❌ Exception in step {step.id}: {e}", exc_info=True)
                    failed_steps.append(step.id)
                    
                    if not step.optional:
                        logger.error(f"Required step failed, stopping execution")
                        break
            
            # Execution summary
            duration = time.time() - start_time
            logger.info(f"\n{'='*60}")
            logger.info(f"📊 Execution Summary")
            logger.info(f"{'='*60}")
            logger.info(f"Instruction: {instruction.name}")
            logger.info(f"Steps completed: {step_count}/{len(steps)}")
            logger.info(f"Duration: {duration:.2f}s")
            
            if failed_steps:
                logger.warning(f"Failed steps: {', '.join(failed_steps)}")
                status = 'partial'
            else:
                logger.info(f"✅ All steps completed successfully!")
                status = 'completed'
            
            # Get all results
            all_results = executor.get_all_results()
            logger.info(f"Stored results: {', '.join(all_results.keys())}")
            
            # Mark as complete
            self.state_manager.end_execution(
                execution_id, status, duration
            )
            
            logger.info(f"{'='*60}\n")
            
            return {
                'success': len(failed_steps) == 0,
                'steps_completed': step_count,
                'total_steps': len(steps),
                'failed_steps': failed_steps,
                'results': all_results,
                'duration': duration
            }
            
        except Exception as e:
            logger.error(f"Error during execution (v2): {e}", exc_info=True)
            duration = time.time() - start_time
            self.state_manager.end_execution(
                execution_id, 'error', duration, str(e)
            )
            return {
                'success': False,
                'error': str(e),
                'duration': duration
            }
    
    def run_once(self, use_v2=False):
        """Run all enabled instructions once."""
        logger.info("Running all enabled instructions once...")
        
        if use_v2:
            logger.info("Using v2 step-by-step execution")
        
        instructions = self.instruction_loader.load_all()
        
        for instruction in instructions:
            if instruction.enabled:
                if use_v2:
                    # For v2, convert filename: strava_monitor.yaml -> strava_monitor_v2
                    filename = Path(instruction.file_path).stem  # Get filename without extension
                    v2_name = f"{filename}_v2"
                    
                    # Check if v2 version exists
                    v2_path = Path("instructions") / f"{v2_name}.yaml"
                    if v2_path.exists():
                        logger.info(f"Found v2 instruction: {v2_name}")
                        self.execute_instruction_v2(v2_name)
                    else:
                        logger.warning(f"V2 instruction not found for {instruction.name} ({v2_name}.yaml), skipping")
                else:
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
    parser.add_argument(
        '--v2',
        action='store_true',
        help='Use v2 step-by-step execution (better for small models)'
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
        if args.v2:
            logger.info("Using v2 step-by-step execution")
            agent.execute_instruction_v2(args.instruction)
        else:
            agent.execute_instruction(args.instruction)
    elif args.once:
        # Run all instructions once
        agent.run_once(use_v2=args.v2)
    else:
        # Start scheduler
        agent.start_scheduler()


if __name__ == "__main__":
    main()
