from typing import Dict, Optional, List, Any
import time
import asyncio
from neural_engine.core.neuron import BaseNeuron
from neural_engine.core.intent_classifier_neuron import IntentClassifierNeuron
from neural_engine.core.generative_neuron import GenerativeNeuron
from neural_engine.core.tool_registry import ToolRegistry
from neural_engine.core.execution_store import ExecutionStore
from neural_engine.core.tool_discovery import ToolDiscovery
from neural_engine.core.tool_lifecycle_manager import ToolLifecycleManager
from neural_engine.core.error_recovery_neuron import ErrorRecoveryNeuron
from neural_engine.core.result_validator_neuron import ResultValidatorNeuron
from neural_engine.core.ollama_client import OllamaClient
from neural_engine.core.logging import get_logger, log_event, EventType

# Fractal architecture imports
from neural_engine.core.public_pipe import PublicPipe, NeuronEvent, EventType as PipeEventType
from neural_engine.core.mind_map import MindMap

logger = get_logger(__name__)


class Orchestrator:
    
    @classmethod
    def from_config(cls, config: 'SystemConfig') -> 'Orchestrator':
        """
        Create Orchestrator from a SystemConfig.
        
        This is the preferred way to create an Orchestrator - no optional params!
        
        Usage:
            from neural_engine.core.config import SystemConfig
            
            config = SystemConfig.create()
            orch = Orchestrator.from_config(config)
        """
        neuron_registry = config.create_neuron_registry()
        
        instance = cls(
            neuron_registry=neuron_registry,
            tool_registry=config.tool_registry,
            message_bus=config.message_bus,
            public_pipe=config.public_pipe,
            mind_map=config.mind_map,
            execution_store=config.execution_store,
            enable_fractal=config.enable_fractal,
            enable_semantic_search=config.enable_tool_discovery,
            enable_lifecycle_sync=False,
            enable_error_recovery=False
        )
        
        # Store config reference for later use
        instance._config = config
        return instance
    def __init__(self, intent_classifier=None, tool_selector=None, code_generator=None, 
                 generative_neuron=None, message_bus=None, sandbox=None,
                 neuron_registry: Optional[Dict[str, BaseNeuron]] = None, 
                 tool_registry: Optional[ToolRegistry] = None,
                 execution_store: Optional[ExecutionStore] = None,
                 tool_discovery: Optional[ToolDiscovery] = None,
                 lifecycle_manager: Optional[ToolLifecycleManager] = None,
                 error_recovery: Optional[ErrorRecoveryNeuron] = None,
                 public_pipe: Optional[PublicPipe] = None,
                 mind_map: Optional[MindMap] = None,
                 enable_semantic_search: bool = True,
                 enable_lifecycle_sync: bool = True,
                 enable_error_recovery: bool = True,
                 enable_fractal: bool = True,
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
            public_pipe: Optional PublicPipe for fractal event bus (Phase 1 Fractal).
                        If None and enable_fractal=True, creates one automatically.
            mind_map: Optional MindMap for thought tree storage (Phase 1 Fractal).
                     If None and enable_fractal=True, creates one automatically.
            enable_semantic_search: If True, enables 3-stage tool discovery (default: True)
            enable_lifecycle_sync: If True, enables autonomous tool lifecycle management (default: True)
            enable_error_recovery: If True, enables intelligent error recovery (default: True)
            enable_fractal: If True, enables fractal architecture (Public Pipe + Mind Map)
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
                logger.warning("ExecutionStore not available", error=str(e))
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
                    logger.info("Semantic tool discovery enabled", tools_indexed=self.tool_discovery.collection.count())
            except Exception as e:
                logger.warning("ToolDiscovery not available", error=str(e))
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
                        logger.info("Tool lifecycle sync enabled",
                                   deleted_tools=len(sync_report['newly_deleted']),
                                   alerts=len(sync_report['alerts']))
            except Exception as e:
                logger.warning("ToolLifecycleManager not available", error=str(e))
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
                    logger.info("Error recovery enabled", strategies=["retry", "fallback", "adapt"])
            except Exception as e:
                logger.warning("ErrorRecoveryNeuron not available", error=str(e))
                self.error_recovery = None
        
        # =================================================================
        # Fractal Architecture: Public Pipe and Mind Map (Phase 1)
        # =================================================================
        self.public_pipe = public_pipe
        self.mind_map = mind_map
        self.enable_fractal = enable_fractal
        
        if enable_fractal:
            # Initialize Public Pipe for event streaming
            if self.public_pipe is None:
                try:
                    self.public_pipe = PublicPipe()
                    logger.info("Public Pipe enabled for fractal observation")
                except Exception as e:
                    logger.warning("PublicPipe not available", error=str(e))
                    self.public_pipe = None
            
            # Initialize Mind Map for thought tree storage
            if self.mind_map is None:
                try:
                    self.mind_map = MindMap()
                    logger.info("Mind Map enabled for thought storage")
                except Exception as e:
                    logger.warning("MindMap not available", error=str(e))
                    self.mind_map = None
            
            # Enable fractal on all neurons
            self._enable_fractal_on_neurons()
    
    def _enable_fractal_on_neurons(self):
        """Enable fractal architecture on all registered neurons."""
        if not self.public_pipe and not self.mind_map:
            return
        
        for name, neuron in self.neuron_registry.items():
            if neuron and hasattr(neuron, 'enable_fractal'):
                try:
                    neuron.enable_fractal(self.public_pipe, self.mind_map)
                    logger.debug("Fractal enabled on neuron", neuron=name)
                except Exception as e:
                    logger.warning("Failed to enable fractal on neuron", neuron=name, error=str(e))
    
    def _run_async(self, coro):
        """Run an async coroutine from sync context."""
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # Create a new thread to run the coroutine
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as pool:
                    future = pool.submit(asyncio.run, coro)
                    return future.result(timeout=30)
            else:
                return loop.run_until_complete(coro)
        except RuntimeError:
            return asyncio.run(coro)
    
    async def _start_goal_tracking(self, goal_id: str, goal: str) -> Optional[str]:
        """Start tracking a goal in the fractal systems. Returns root node ID."""
        root_node_id = None
        
        # Emit goal started event to Public Pipe
        if self.public_pipe:
            await self.public_pipe.emit(NeuronEvent(
                event_type=PipeEventType.NEURON_STARTED,
                neuron_type="Orchestrator",
                goal_id=goal_id,
                data={"goal": goal, "type": "goal_start"}
            ))
        
        # Create root node in Mind Map
        if self.mind_map:
            root_node = await self.mind_map.create_root(
                goal_id=goal_id,
                goal_text=goal
            )
            root_node_id = root_node.node_id
        
        return root_node_id
    
    async def _complete_goal_tracking(self, goal_id: str, result: Dict, duration_ms: int, success: bool):
        """Complete goal tracking in fractal systems."""
        # Emit goal completed/failed event
        if self.public_pipe:
            event_type = PipeEventType.NEURON_COMPLETED if success else PipeEventType.NEURON_FAILED
            await self.public_pipe.emit(NeuronEvent(
                event_type=event_type,
                neuron_type="Orchestrator",
                goal_id=goal_id,
                duration_ms=float(duration_ms),
                data={"success": success, "has_error": "error" in result}
            ))
        
        # Update Mind Map
        if self.mind_map:
            if success:
                await self.mind_map.complete_goal(goal_id, result={"success": True})
            else:
                error_msg = result.get("error", "Unknown error")
                await self.mind_map.fail_goal(goal_id, error=str(error_msg))
    
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
        
        # FRACTAL: Start goal tracking in Public Pipe and Mind Map
        root_node_id = None
        if self.enable_fractal and (self.public_pipe or self.mind_map):
            try:
                root_node_id = self._run_async(self._start_goal_tracking(goal_id, goal))
            except Exception as e:
                logger.warning("Failed to start fractal tracking", error=str(e))
        
        # PHASE 2.1: Check Neural Pathway Cache first (System 1 - Fast Path)
        cached_pathway = None
        if hasattr(self, 'pathway_cache') and self.pathway_cache:
            try:
                # Generate goal embedding for similarity search
                goal_embedding = self._generate_goal_embedding(goal)
                
                # Try to find cached pathway
                cached_pathway = self.pathway_cache.find_cached_pathway(
                    goal_text=goal,
                    goal_embedding=goal_embedding
                )
                
                if cached_pathway:
                    # Notify visualizer if available
                    if hasattr(self, 'visualizer') and self.visualizer:
                        self.visualizer.show_cache_check({
                            'similarity': cached_pathway['similarity_score'],
                            'confidence_score': cached_pathway['confidence_score'],
                            'pathway_id': cached_pathway['pathway_id'],
                            'tools_used': cached_pathway.get('tool_names', []),
                            'usage_count': cached_pathway.get('usage_count', 0),
                            'cache_type': 'pathway'
                        })
                    else:
                        print(f"💨 Pathway cache hit! (similarity: {cached_pathway['similarity_score']:.0%}, confidence: {cached_pathway['confidence_score']:.0%})")
                        print(f"   Using cached execution path (System 1)")
                    
                    # Execute from cache (fast path)
                    result = cached_pathway.get('final_result', {})
                    
                    # Update usage statistics
                    self.pathway_cache.update_pathway_result(
                        pathway_id=cached_pathway['pathway_id'],
                        success=True
                    )
                    
                    # Calculate duration
                    duration_ms = int((time.time() - start_time) * 1000)
                    
                    # Log execution
                    if self.execution_store:
                        try:
                            self._log_execution(goal_id, goal, result, duration_ms, depth, 
                                              cache_hit=True, pathway_id=cached_pathway['pathway_id'])
                        except Exception as e:
                            print(f"Warning: Failed to log execution: {e}")
                    
                    # FRACTAL: Complete goal tracking (cache hit path)
                    if self.enable_fractal and (self.public_pipe or self.mind_map):
                        try:
                            self._run_async(self._complete_goal_tracking(goal_id, result, duration_ms, True))
                        except Exception as e:
                            logger.warning("Failed to complete fractal tracking", error=str(e))
                    
                    return result
                else:
                    # Notify visualizer of cache miss
                    if hasattr(self, 'visualizer') and self.visualizer:
                        self.visualizer.show_cache_check(None)
            except Exception as e:
                print(f"⚠️  Pathway cache lookup failed: {e}")
                cached_pathway = None
        
        # PHASE 2.2: Check for learned decomposition patterns (before execution)
        suggested_pattern = None
        if hasattr(self, 'goal_learner') and self.goal_learner:
            try:
                patterns = self.goal_learner.find_similar_patterns(
                    goal_text=goal,
                    similarity_threshold=0.75,  # 75% similarity
                    only_successful=True,
                    limit=1
                )
                
                if patterns and len(patterns) > 0:
                    suggested_pattern = patterns[0]
                    
                    # Notify visualizer if available
                    if hasattr(self, 'visualizer') and self.visualizer:
                        self.visualizer.show_pattern_suggestion(suggested_pattern)
                    else:
                        print(f"📚 Found similar goal pattern (similarity: {suggested_pattern['similarity']:.0%})")
                        print(f"   Suggested decomposition: {suggested_pattern['subgoal_count']} subgoals")
            except Exception as e:
                print(f"⚠️  Pattern lookup failed: {e}")
                suggested_pattern = None
        
        result = self.execute(goal_id, goal, depth)
        
        # Calculate duration
        duration_ms = int((time.time() - start_time) * 1000)
        
        # Log execution to database if available
        if self.execution_store:
            try:
                self._log_execution(goal_id, goal, result, duration_ms, depth)
            except Exception as e:
                print(f"Warning: Failed to log execution: {e}")
        
        # PHASE 2.4: Validate result before caching (with proper validation)
        if hasattr(self, 'pathway_cache') and self.pathway_cache:
            try:
                # Use result validator if available, otherwise fall back to simple check
                if hasattr(self, 'result_validator') and self.result_validator:
                    should_cache, confidence, reasoning = self.result_validator.should_cache_result(
                        goal, result, duration_ms
                    )
                    
                    if should_cache:
                        goal_embedding = self._generate_goal_embedding(goal)
                        pathway_id = self.pathway_cache.store_pathway(
                            goal_text=goal,
                            goal_embedding=goal_embedding,
                            execution_steps=self._extract_execution_steps(goal_id),
                            final_result=result,
                            tool_names=self._extract_tools_used(goal_id),
                            execution_time_ms=duration_ms
                        )
                        if pathway_id:
                            print(f"💾 Pathway cached (confidence: {confidence:.0%}, ID: {pathway_id[:8]}...)")
                            
                        # PHASE 2.2: Store decomposition pattern after successful caching
                        if hasattr(self, 'goal_learner') and self.goal_learner:
                            try:
                                tools_used = self._extract_tools_used(goal_id)
                                subgoals = self._extract_subgoals(goal_id)  # Extract from execution steps
                                
                                pattern_id = self.goal_learner.store_pattern(
                                    goal_text=goal,
                                    subgoals=subgoals,
                                    success=True,
                                    execution_time_ms=duration_ms,
                                    tools_used=tools_used,
                                    goal_type=None  # Could classify later
                                )
                                print(f"📚 Stored decomposition pattern (ID: {pattern_id})")
                            except Exception as e:
                                print(f"⚠️  Failed to store pattern: {e}")
                    else:
                        print(f"⚠️  Result not cached - {reasoning}")
                else:
                    # Fallback to simple validation (legacy)
                    execution_success = result.get('success', False) or not result.get('error')
                    if execution_success:
                        goal_embedding = self._generate_goal_embedding(goal)
                        pathway_id = self.pathway_cache.store_pathway(
                            goal_text=goal,
                            goal_embedding=goal_embedding,
                            execution_steps=self._extract_execution_steps(goal_id),
                            final_result=result,
                            tool_names=self._extract_tools_used(goal_id),
                            execution_time_ms=duration_ms
                        )
                        if pathway_id:
                            print(f"💾 Pathway cached for future use (ID: {pathway_id[:8]}...)")
                            
                        # PHASE 2.2: Store decomposition pattern after successful caching
                        if hasattr(self, 'goal_learner') and self.goal_learner:
                            try:
                                tools_used = self._extract_tools_used(goal_id)
                                subgoals = self._extract_subgoals(goal_id)
                                
                                pattern_id = self.goal_learner.store_pattern(
                                    goal_text=goal,
                                    subgoals=subgoals,
                                    success=True,
                                    execution_time_ms=duration_ms,
                                    tools_used=tools_used
                                )
                                print(f"📚 Stored decomposition pattern (ID: {pattern_id})")
                            except Exception as e:
                                print(f"⚠️  Failed to store pattern: {e}")
            except Exception as e:
                print(f"⚠️  Failed to cache pathway: {e}")
        
        # FRACTAL: Complete goal tracking
        if self.enable_fractal and (self.public_pipe or self.mind_map):
            try:
                success = result.get('success', False) or not result.get('error')
                self._run_async(self._complete_goal_tracking(goal_id, result, duration_ms, success))
            except Exception as e:
                logger.warning("Failed to complete fractal tracking", error=str(e))
        
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
    
    def _log_execution(self, goal_id: str, goal_text: str, result: Dict, duration_ms: int, depth: int, 
                       cache_hit: bool = False, pathway_id: Optional[str] = None):
        """Log execution to PostgreSQL if available."""
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
                'timestamp': time.time()
                # Note: Not storing full result in metadata - too large and contains datetime objects
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
    
    def _generate_goal_embedding(self, goal: str) -> List[float]:
        """Generate vector embedding for goal text."""
        # Use the same embedding model as tool discovery (if available)
        if hasattr(self, 'tool_discovery') and self.tool_discovery:
            # Tool discovery has the embedding model
            return self.tool_discovery.collection._embedding_function([goal])[0]
        else:
            # Fallback: use sentence-transformers directly
            from sentence_transformers import SentenceTransformer
            model = SentenceTransformer('all-MiniLM-L6-v2')
            return model.encode(goal, convert_to_tensor=False).tolist()
    
    def _extract_execution_steps(self, goal_id: str) -> List[Dict[str, Any]]:
        """Extract execution steps from message bus for this goal."""
        # Get messages from message bus for this goal
        steps = []
        try:
            if self.message_bus:
                # Get all messages for this goal_id from message bus
                # This is a simplified version - could be enhanced to parse actual steps
                steps.append({
                    "step": 1,
                    "action": "full_pipeline",
                    "goal_id": goal_id
                })
        except:
            pass
        return steps
    
    def _extract_tools_used(self, goal_id: str) -> List[str]:
        """Extract list of tools used in this execution."""
        tools = []
        try:
            # Extract from message bus or track during execution
            # For now, return empty list - could be enhanced
            pass
        except:
            pass
        return tools
    
    def _extract_subgoals(self, goal_id: str) -> List[str]:
        """Extract subgoals from execution (for decomposition learning)."""
        subgoals = []
        try:
            # For simple tool-use goals, the subgoal is just the tool execution
            # For complex goals with multiple steps, this would extract each step
            # For now, return single subgoal representing the execution
            subgoals.append("execute_tool")  # Placeholder
        except:
            pass
        return subgoals


