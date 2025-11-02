from typing import Dict, Optional
import time
from neural_engine.core.neuron import BaseNeuron
from neural_engine.core.intent_classifier_neuron import IntentClassifierNeuron
from neural_engine.core.generative_neuron import GenerativeNeuron
from neural_engine.core.tool_registry import ToolRegistry
from neural_engine.core.execution_store import ExecutionStore
from neural_engine.core.tool_discovery import ToolDiscovery
from neural_engine.core.tool_lifecycle_manager import ToolLifecycleManager
from neural_engine.core.error_recovery_neuron import ErrorRecoveryNeuron
from neural_engine.core.ollama_client import OllamaClient

class Orchestrator:
    def __init__(self, intent_classifier=None, tool_selector=None, code_generator=None, 
                 generative_neuron=None, message_bus=None, sandbox=None,
                 neuron_registry: Optional[Dict[str, BaseNeuron]] = None, 
                 tool_registry: Optional[ToolRegistry] = None,
                 execution_store: Optional[ExecutionStore] = None,
                 tool_discovery: Optional[ToolDiscovery] = None,
                 lifecycle_manager: Optional[ToolLifecycleManager] = None,
                 error_recovery: Optional[ErrorRecoveryNeuron] = None,
                 enable_semantic_search: bool = True,
                 enable_lifecycle_sync: bool = True,
                 enable_error_recovery: bool = True,
                 max_depth=10):
        """Initialize Orchestrator with either individual neurons or a neuron registry.
        
        New API (Phase 6+): Pass individual neurons:
            Orchestrator(intent_classifier=..., tool_selector=..., code_generator=..., 
                        generative_neuron=..., message_bus=..., sandbox=..., 
                        execution_store=..., tool_discovery=..., lifecycle_manager=...)
        
        Old API (Phases 0-5): Pass neuron_registry and tool_registry:
            Orchestrator(neuron_registry={...}, tool_registry=..., message_bus=...)
        
        Args:
            execution_store: Optional ExecutionStore for logging executions.
                           If None and PostgreSQL is available, creates one automatically.
            tool_discovery: Optional ToolDiscovery for semantic tool search (Phase 8d).
                          If None and enable_semantic_search=True, creates one automatically.
            lifecycle_manager: Optional ToolLifecycleManager for autonomous tool lifecycle (Phase 9d).
                             If None and enable_lifecycle_sync=True, creates one automatically.
            error_recovery: Optional ErrorRecoveryNeuron for intelligent error recovery (Phase 10d).
                          If None and enable_error_recovery=True, creates one automatically.
            enable_semantic_search: If True, enables 3-stage tool discovery (default: True)
            enable_lifecycle_sync: If True, enables autonomous tool lifecycle management (default: True)
            enable_error_recovery: If True, enables intelligent error recovery (default: True)
        """
        # Support both old and new initialization patterns
        if neuron_registry is not None:
            # Old API
            self.neuron_registry = neuron_registry
            self.tool_registry = tool_registry
            self.message_bus = message_bus
        else:
            # New API - build neuron_registry from individual neurons
            self.intent_classifier = intent_classifier
            self.tool_selector = tool_selector
            self.code_generator = code_generator
            self.generative_neuron = generative_neuron
            self.message_bus = message_bus
            self.sandbox = sandbox
            
            # Create neuron_registry for backward compatibility
            self.neuron_registry = {
                "intent_classifier": intent_classifier,
                "tool_selector": tool_selector,
                "code_generator": code_generator,
                "generative": generative_neuron,
                "sandbox": sandbox
            }
            self.tool_registry = None  # Not used in new API
        
        self.max_depth = max_depth
        self.goal_counter = 0  # Track goals for auto-incrementing goal IDs
        
        # Initialize ExecutionStore for logging
        self.execution_store = execution_store
        if self.execution_store is None:
            try:
                self.execution_store = ExecutionStore()
            except Exception as e:
                # If PostgreSQL is not available, continue without logging
                print(f"Warning: ExecutionStore not available: {e}")
                self.execution_store = None
        
        # Initialize ToolDiscovery for semantic search (Phase 8d)
        self.tool_discovery = tool_discovery
        if self.tool_discovery is None and enable_semantic_search and self.execution_store:
            try:
                # Auto-create ToolDiscovery with execution_store
                # Get tool_registry from ToolSelectorNeuron if available
                if self.tool_selector and hasattr(self.tool_selector, 'tool_registry'):
                    self.tool_discovery = ToolDiscovery(
                        tool_registry=self.tool_selector.tool_registry,
                        execution_store=self.execution_store
                    )
                    # Index all tools on initialization
                    self.tool_discovery.index_all_tools()
                    print(f"✓ Semantic tool discovery enabled ({self.tool_discovery.collection.count()} tools indexed)")
            except Exception as e:
                print(f"Warning: ToolDiscovery not available: {e}")
                self.tool_discovery = None
        
        # Initialize ToolLifecycleManager for autonomous lifecycle management (Phase 9d)
        self.lifecycle_manager = lifecycle_manager
        if self.lifecycle_manager is None and enable_lifecycle_sync and self.execution_store:
            try:
                # Auto-create ToolLifecycleManager with tool_registry and execution_store
                if self.tool_selector and hasattr(self.tool_selector, 'tool_registry'):
                    self.lifecycle_manager = ToolLifecycleManager(
                        tool_registry=self.tool_selector.tool_registry,
                        execution_store=self.execution_store
                    )
                    # Run initial sync to detect any orphaned tools
                    sync_report = self.lifecycle_manager.sync_and_reconcile()
                    if sync_report['newly_deleted'] or sync_report['alerts']:
                        print(f"✓ Tool lifecycle sync enabled")
                        if sync_report['newly_deleted']:
                            print(f"  - Detected {len(sync_report['newly_deleted'])} deleted tools")
                        if sync_report['alerts']:
                            print(f"  ⚠️  {len(sync_report['alerts'])} alerts generated")
                            for alert in sync_report['alerts']:
                                if alert.get('alert'):
                                    print(f"     - {alert['tool_name']}: {alert.get('reason', 'unknown')}")
            except Exception as e:
                print(f"Warning: ToolLifecycleManager not available: {e}")
                self.lifecycle_manager = None
        
        # Initialize ErrorRecoveryNeuron for intelligent error recovery (Phase 10d)
        self.error_recovery = error_recovery
        if self.error_recovery is None and enable_error_recovery:
            try:
                # Auto-create ErrorRecoveryNeuron
                ollama_client = None
                tool_reg = None
                
                # Get OllamaClient from generative_neuron if available
                if self.generative_neuron and hasattr(self.generative_neuron, 'ollama_client'):
                    ollama_client = self.generative_neuron.ollama_client
                elif self.intent_classifier and hasattr(self.intent_classifier, 'ollama_client'):
                    ollama_client = self.intent_classifier.ollama_client
                else:
                    ollama_client = OllamaClient()
                
                # Get tool_registry from tool_selector if available
                if self.tool_selector and hasattr(self.tool_selector, 'tool_registry'):
                    tool_reg = self.tool_selector.tool_registry
                
                if ollama_client and tool_reg:
                    self.error_recovery = ErrorRecoveryNeuron(
                        ollama_client=ollama_client,
                        tool_registry=tool_reg,
                        execution_store=self.execution_store
                    )
                    print(f"✓ Error recovery enabled (retry, fallback, adapt strategies)")
            except Exception as e:
                print(f"Warning: ErrorRecoveryNeuron not available: {e}")
                self.error_recovery = None
    
    def process(self, goal: str, goal_id: Optional[str] = None, depth=0):
        """Process a user goal through the complete pipeline.
        
        Args:
            goal: The user's goal/request as a string
            goal_id: Optional goal ID (will auto-generate if not provided)
            depth: Recursion depth (default 0)
            
        Returns:
            Result from the pipeline (either generative response or tool execution result)
        """
        # Auto-generate goal_id if not provided
        if goal_id is None:
            self.goal_counter += 1
            goal_id = f"goal_{self.goal_counter}"
        
        # Track execution timing
        start_time = time.time()
        
        # Execute the pipeline
        result = self.execute(goal_id, goal, depth)
        
        # Calculate duration
        duration_ms = int((time.time() - start_time) * 1000)
        
        # Log execution to database if available
        if self.execution_store:
            try:
                self._log_execution(goal_id, goal, result, duration_ms, depth)
            except Exception as e:
                print(f"Warning: Failed to log execution: {e}")
        
        return result

    def execute(self, goal_id, goal: str, depth=0):
        if depth > self.max_depth:
            return {"error": "Maximum recursion depth exceeded."}

        intent_classifier = self.neuron_registry["intent_classifier"]
        intent_data = intent_classifier.process(goal_id, goal, depth)
        intent = intent_data["intent"]

        if intent == "generative":
            return self._execute_generative_pipeline(goal_id, intent_data, depth)

        elif intent == "tool_use":
            return self._execute_tool_use_pipeline(goal_id, intent_data, depth)

        else:
            return {"error": f"Unknown or unsupported intent: {intent}"}

    def _execute_generative_pipeline(self, goal_id, data, depth):
        return self.neuron_registry["generative"].process(goal_id, data, depth)

    def _execute_tool_use_pipeline(self, goal_id, data, depth):
        # 1. Select the tool (with optional semantic search)
        tool_selector = self.neuron_registry["tool_selector"]
        
        # If ToolDiscovery was created but ToolSelectorNeuron doesn't have it yet, inject it
        if self.tool_discovery and not hasattr(tool_selector, 'tool_discovery'):
            tool_selector.tool_discovery = self.tool_discovery
        
        tool_selection_data = tool_selector.process(goal_id, data['goal'], depth)

        # 2. Generate the code
        code_generator = self.neuron_registry["code_generator"]
        code_generation_data = code_generator.process(goal_id, tool_selection_data, depth)

        # 3. Execute the code in the sandbox (with error recovery if enabled)
        # Support both "code" and "generated_code" keys
        code = code_generation_data.get("generated_code") or code_generation_data.get("code")
        sandbox = self.neuron_registry["sandbox"]
        
        # Inject error recovery into sandbox if available
        if self.error_recovery and not hasattr(sandbox, 'error_recovery'):
            sandbox.error_recovery = self.error_recovery
            sandbox.error_recovery_context = {
                'goal': data.get('goal', ''),
                'tool_name': tool_selection_data.get('tool_name', 'unknown'),
                'goal_id': goal_id,
                'depth': depth
            }
        
        execution_result = sandbox.execute(code, goal_id=goal_id, depth=depth)
        
        # NEW: Store in pattern cache AFTER successful execution (execution validation!)
        execution_success = execution_result.get('success', False) or not execution_result.get('error')
        
        # Update pattern caches with execution validation
        if hasattr(tool_selector, 'pattern_cache') and tool_selector.pattern_cache:
            # Store tool selection with execution validation
            tool_selector.pattern_cache.store_after_execution(
                query=data.get('goal', ''),
                decision={"selected_tools": tool_selection_data.get('selected_tools', [])},
                execution_success=execution_success,
                confidence=0.90 if execution_success else 0.0,
                metadata={
                    "method": tool_selection_data.get('method', 'unknown'),
                    "execution_validated": True,
                    "execution_success": execution_success
                }
            )
        
        # Also update intent classifier cache with execution result
        intent_classifier_neuron = self.neuron_registry["intent_classifier"]
        if hasattr(intent_classifier_neuron, 'pattern_cache') and intent_classifier_neuron.pattern_cache:
            intent_classifier_neuron.pattern_cache.store_after_execution(
                query=data.get('goal', ''),
                decision={"intent": data.get('intent', 'tool_use')},
                execution_success=execution_success,
                confidence=0.90 if execution_success else 0.0,
                metadata={
                    "method": data.get('method', 'unknown'),
                    "execution_validated": True,
                    "execution_success": execution_success
                }
            )

        return execution_result
    
    def _log_execution(self, goal_id: str, goal_text: str, result: Dict, duration_ms: int, depth: int):
        """Log execution to ExecutionStore.
        
        Args:
            goal_id: The goal identifier
            goal_text: Original user request
            result: Pipeline result dictionary
            duration_ms: Execution duration in milliseconds
            depth: Recursion depth
        """
        # Extract key information from result
        intent = result.get('intent', 'unknown')
        success = result.get('success', False)
        error = result.get('error')
        
        # Store main execution
        execution_id = self.execution_store.store_execution(
            goal_id=goal_id,
            goal_text=goal_text,
            intent=intent,
            success=success,
            error=error,
            duration_ms=duration_ms,
            metadata={
                'depth': depth,
                'result': result,
                'timestamp': time.time()
            }
        )
        
        # If tool was used, log tool execution
        if intent == "tool_use" and 'selected_tools' in result:
            selected_tools = result['selected_tools']
            if isinstance(selected_tools, str):
                selected_tools = [selected_tools]
            
            for tool_name in selected_tools:
                # Extract tool-specific data
                tool_params = result.get('tool_parameters', {})
                tool_result = result.get('execution_result')
                tool_success = result.get('success', False)
                tool_error = result.get('error')
                
                self.execution_store.store_tool_execution(
                    execution_id=execution_id,
                    tool_name=tool_name,
                    parameters=tool_params,
                    result=tool_result,
                    success=tool_success,
                    error=tool_error,
                    duration_ms=None  # Individual tool timing not tracked yet
                )
        
        # Run lifecycle sync after tool operations (Phase 9d)
        if self.lifecycle_manager and intent == "tool_use":
            try:
                sync_report = self.lifecycle_manager.sync_and_reconcile()
                # Log any alerts from sync
                if sync_report.get('alerts'):
                    for alert in sync_report['alerts']:
                        if alert.get('alert'):
                            print(f"⚠️  Lifecycle Alert: {alert['tool_name']} - {alert.get('suggestion', alert.get('reason'))}")
            except Exception as e:
                print(f"Warning: Lifecycle sync failed: {e}")
        
        return execution_id
    
    def run_lifecycle_maintenance(self, dry_run: bool = False) -> Dict:
        """
        Run tool lifecycle maintenance tasks.
        
        This should be called periodically (e.g., daily) to:
        - Sync filesystem and database
        - Detect deleted tools
        - Alert on valuable tool deletions
        - Auto-archive old deleted tools
        
        Args:
            dry_run: If True, only preview what would be done
        
        Returns:
            Maintenance report with sync, cleanup, and alert details
        """
        if not self.lifecycle_manager:
            return {
                'error': 'LifecycleManager not available',
                'status': 'disabled'
            }
        
        try:
            report = self.lifecycle_manager.maintenance(dry_run=dry_run)
            
            # Print summary
            print("\n=== Tool Lifecycle Maintenance ===")
            print(f"Timestamp: {report.get('timestamp')}")
            
            if report.get('sync_report'):
                sync = report['sync_report']
                print(f"\nSync Report:")
                print(f"  Newly deleted: {len(sync.get('newly_deleted', []))}")
                print(f"  Restored: {len(sync.get('restored', []))}")
                print(f"  New manual tools: {len(sync.get('new_manual_tools', []))}")
                
                if sync.get('alerts'):
                    print(f"\n  ⚠️  Alerts ({len(sync['alerts'])}):")
                    for alert in sync['alerts']:
                        if alert.get('alert'):
                            severity = alert.get('severity', 'info').upper()
                            print(f"    [{severity}] {alert['tool_name']}: {alert.get('suggestion', alert.get('reason'))}")
            
            if report.get('cleanup_report'):
                cleanup = report['cleanup_report']
                if cleanup.get('preview'):
                    print(f"\nCleanup Preview:")
                    print(f"  Would archive: {cleanup.get('total_would_archive', 0)} tools")
                    print(f"  Would keep: {cleanup.get('total_would_keep', 0)} tools")
                else:
                    print(f"\nCleanup Report:")
                    print(f"  Archived: {cleanup.get('total_archived', 0)} tools")
                    print(f"  Kept: {cleanup.get('total_kept', 0)} tools")
            
            print("\n" + "=" * 35)
            
            return report
            
        except Exception as e:
            print(f"❌ Maintenance failed: {e}")
            return {
                'error': str(e),
                'status': 'failed'
            }
