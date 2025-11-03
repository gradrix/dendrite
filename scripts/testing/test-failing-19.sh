#!/bin/bash
# Run only the 19 failing tests
# This script should be run until all tests pass
# Only THEN run the full test suite

echo "🧪 Running 19 Failing Tests"
echo "=============================="
echo ""

./scripts/test.sh \
  neural_engine/tests/test_autonomous_improvement_neuron.py::test_detect_failing_tool \
  neural_engine/tests/test_orchestrator_logging.py::test_statistics_update_after_executions \
  neural_engine/tests/test_phase3_tool_selection.py::test_selector_chooses_memory_read_for_recall \
  neural_engine/tests/test_phase3_tool_selection.py::test_selector_raises_error_for_nonexistent_tool \
  "neural_engine/tests/test_phase3_tool_selection.py::test_tool_selection_accuracy[What did I tell you?-memory_read]" \
  neural_engine/tests/test_phase4_code_generation.py::test_different_tools_generate_different_code \
  neural_engine/tests/test_phase6_full_pipeline.py::test_pipeline_memory_read \
  neural_engine/tests/test_phase6_full_pipeline.py::test_pipeline_multiple_goals_sequential \
  neural_engine/tests/test_phase6_full_pipeline.py::test_pipeline_depth_tracking \
  neural_engine/tests/test_phase6_full_pipeline.py::test_pipeline_depth_increments \
  neural_engine/tests/test_phase6_full_pipeline.py::test_pipeline_handles_sandbox_execution_error \
  neural_engine/tests/test_phase6_full_pipeline.py::test_full_pipeline_end_to_end \
  neural_engine/tests/test_self_investigation_neuron.py::test_investigate_health_detects_failing_tools \
  neural_engine/tests/test_stage3_integration.py::test_selection_without_semantic_uses_all_tools \
  neural_engine/tests/test_tool_discovery.py::test_semantic_search_prime_checker \
  neural_engine/tests/test_tool_discovery.py::test_discover_tools_prime_query \
  neural_engine/tests/test_tool_selector_neuron.py::test_process_selects_tool_correctly \
  neural_engine/tests/test_tool_use_pipeline.py::test_tool_use_pipeline \
  neural_engine/tests/test_phase6_full_pipeline.py::test_pipeline_hello_world \
  --tb=line -q
