"""Main orchestrator for coordinating marketing agents using LangGraph."""

import logging
import asyncio
from typing import Dict, List, Any, Optional, TypedDict
from datetime import datetime
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver
from config import settings
from utils.database import db_manager
from agents.content_generator import content_generator
from agents.visual_creator import visual_creator
from agents.campaign_launcher import campaign_launcher
from agents.performance_tracker import performance_tracker
from agents.optimizer import optimizer
from agents.budget_controller import budget_controller

logger = logging.getLogger(__name__)


class MarketingAgentState(TypedDict):
    """State shared across all marketing agents."""
    campaign_id: str
    campaign_data: Dict[str, Any]
    content_data: Optional[Dict[str, Any]]
    image_data: Optional[Dict[str, Any]]
    creative_id: Optional[str]
    approval_status: str
    launch_results: Optional[Dict[str, Any]]
    performance_data: Optional[Dict[str, Any]]
    optimization_needed: bool
    error: Optional[str]
    step: str
    retries: int
    max_retries: int


class MarketingOrchestrator:
    """Main orchestrator for coordinating marketing campaign creation and optimization."""
    
    def __init__(self):
        self.graph = self._build_graph()
        self.memory = MemorySaver()
    
    def _build_graph(self) -> StateGraph:
        """Build the LangGraph workflow for marketing campaigns."""
        
        workflow = StateGraph(MarketingAgentState)
        
        # Add nodes for each step
        workflow.add_node("generate_content", self._generate_content_node)
        workflow.add_node("create_visuals", self._create_visuals_node)
        workflow.add_node("request_approval", self._request_approval_node)
        workflow.add_node("check_approval", self._check_approval_node)
        workflow.add_node("launch_campaign", self._launch_campaign_node)
        workflow.add_node("monitor_performance", self._monitor_performance_node)
        workflow.add_node("check_budgets", self._check_budgets_node)
        workflow.add_node("optimize_campaign", self._optimize_campaign_node)
        workflow.add_node("handle_error", self._handle_error_node)
        
        # Set entry point
        workflow.set_entry_point("generate_content")
        
        # Add edges for normal flow
        workflow.add_edge("generate_content", "create_visuals")
        workflow.add_edge("create_visuals", "request_approval")
        workflow.add_edge("request_approval", "check_approval")
        workflow.add_edge("launch_campaign", "monitor_performance")
        workflow.add_edge("monitor_performance", "check_budgets")
        workflow.add_edge("check_budgets", "optimize_campaign")
        
        # Add conditional edges
        workflow.add_conditional_edges(
            "check_approval",
            self._approval_condition,
            {
                "approved": "launch_campaign",
                "rejected": END,
                "pending": "check_approval"
            }
        )
        
        workflow.add_conditional_edges(
            "optimize_campaign",
            self._optimization_condition,
            {
                "continue": "monitor_performance",
                "complete": END,
                "error": "handle_error"
            }
        )
        
        # Error handling edges
        workflow.add_conditional_edges(
            "generate_content",
            self._error_condition,
            {"error": "handle_error", "continue": "create_visuals"}
        )
        
        workflow.add_conditional_edges(
            "create_visuals",
            self._error_condition,
            {"error": "handle_error", "continue": "request_approval"}
        )
        
        workflow.add_conditional_edges(
            "launch_campaign",
            self._error_condition,
            {"error": "handle_error", "continue": "monitor_performance"}
        )
        
        workflow.add_edge("handle_error", END)
        
        return workflow.compile(checkpointer=self.memory)
    
    async def create_campaign(self, campaign_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create and manage a complete marketing campaign."""
        
        try:
            # Initialize state
            initial_state = MarketingAgentState(
                campaign_id=campaign_data.get('campaign_id', ''),
                campaign_data=campaign_data,
                content_data=None,
                image_data=None,
                creative_id=None,
                approval_status='pending',
                launch_results=None,
                performance_data=None,
                optimization_needed=False,
                error=None,
                step='start',
                retries=0,
                max_retries=3
            )
            
            # Create campaign in database if not exists
            if not initial_state['campaign_id']:
                campaign_id = await db_manager.create_campaign(campaign_data)
                initial_state['campaign_id'] = campaign_id
                campaign_data['campaign_id'] = campaign_id
            
            # Run the workflow
            config = {"thread_id": initial_state['campaign_id']}
            
            final_state = await self.graph.ainvoke(initial_state, config=config)
            
            # Log workflow completion
            await db_manager.log_agent_execution(
                agent_name="MarketingOrchestrator",
                campaign_id=initial_state['campaign_id'],
                action="create_campaign",
                status="completed" if not final_state.get('error') else "failed",
                input_data=campaign_data,
                output_data=final_state,
                error_message=final_state.get('error')
            )
            
            return {
                'success': not bool(final_state.get('error')),
                'campaign_id': initial_state['campaign_id'],
                'final_state': final_state
            }
            
        except Exception as e:
            logger.error(f"Error in campaign orchestration: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    async def _generate_content_node(self, state: MarketingAgentState) -> MarketingAgentState:
        """Generate marketing content."""
        logger.info(f"Generating content for campaign {state['campaign_id']}")
        
        try:
            result = await content_generator.generate_ad_copy(state['campaign_data'])
            
            if result['success']:
                state['content_data'] = result['content']
                state['step'] = 'content_generated'
                logger.info(f"Content generated successfully for campaign {state['campaign_id']}")
            else:
                state['error'] = f"Content generation failed: {result['error']}"
                state['retries'] += 1
                
        except Exception as e:
            state['error'] = f"Content generation error: {str(e)}"
            state['retries'] += 1
        
        return state
    
    async def _create_visuals_node(self, state: MarketingAgentState) -> MarketingAgentState:
        """Create visual assets."""
        logger.info(f"Creating visuals for campaign {state['campaign_id']}")
        
        try:
            result = await visual_creator.generate_ad_image(
                state['campaign_data'],
                state['content_data'] or {}
            )
            
            if result['success']:
                state['image_data'] = result
                state['step'] = 'visuals_created'
                # Update content data with image information
                if state['content_data']:
                    state['content_data']['image_url'] = result['image_url']
                    state['content_data']['image_prompt'] = result['image_prompt']
                logger.info(f"Visuals created successfully for campaign {state['campaign_id']}")
            else:
                # Continue without image if generation fails
                logger.warning(f"Visual creation failed for campaign {state['campaign_id']}: {result['error']}")
                state['step'] = 'visuals_failed'
                
        except Exception as e:
            logger.error(f"Visual creation error for campaign {state['campaign_id']}: {e}")
            state['step'] = 'visuals_failed'
        
        return state
    
    async def _request_approval_node(self, state: MarketingAgentState) -> MarketingAgentState:
        """Request human approval if required."""
        logger.info(f"Requesting approval for campaign {state['campaign_id']}")
        
        try:
            if not settings.human_approval_required:
                state['approval_status'] = 'approved'
                state['step'] = 'approval_bypassed'
                return state
            
            # Create ad creative in database
            creative_data = {
                'campaign_id': state['campaign_id'],
                'headline': state['content_data'].get('headlines', [''])[0] if state['content_data'] else '',
                'description': state['content_data'].get('description', '') if state['content_data'] else '',
                'call_to_action': state['content_data'].get('call_to_action', 'Learn More') if state['content_data'] else 'Learn More',
                'image_url': state['content_data'].get('image_url') if state['content_data'] else None,
                'image_prompt': state['content_data'].get('image_prompt') if state['content_data'] else None,
                'status': 'pending_approval'
            }
            
            creative_id = await db_manager.create_ad_creative(creative_data)
            state['creative_id'] = creative_id
            
            # Request approval
            approval_id = await db_manager.request_approval(
                campaign_id=state['campaign_id'],
                creative_id=creative_id,
                approval_type='creative',
                details={
                    'content': state['content_data'],
                    'image_data': state['image_data'],
                    'budget_daily': state['campaign_data'].get('budget_daily'),
                    'platform': state['campaign_data'].get('platform')
                }
            )
            
            state['approval_id'] = approval_id
            state['approval_status'] = 'pending'
            state['step'] = 'approval_requested'
            
            # Update campaign status
            await db_manager.update_campaign_status(state['campaign_id'], 'pending_approval')
            
            logger.info(f"Approval requested for campaign {state['campaign_id']}")
            
        except Exception as e:
            state['error'] = f"Approval request error: {str(e)}"
            state['retries'] += 1
        
        return state
    
    async def _check_approval_node(self, state: MarketingAgentState) -> MarketingAgentState:
        """Check approval status."""
        logger.info(f"Checking approval status for campaign {state['campaign_id']}")
        
        try:
            if state.get('approval_id'):
                approval_status = await db_manager.check_approval_status(state['approval_id'])
                state['approval_status'] = approval_status or 'pending'
            
            state['step'] = f'approval_checked_{state["approval_status"]}'
            
        except Exception as e:
            state['error'] = f"Approval check error: {str(e)}"
            state['retries'] += 1
        
        return state
    
    async def _launch_campaign_node(self, state: MarketingAgentState) -> MarketingAgentState:
        """Launch the approved campaign."""
        logger.info(f"Launching campaign {state['campaign_id']}")
        
        try:
            result = await campaign_launcher.launch_campaign(
                state['campaign_data'],
                state['content_data'] or {}
            )
            
            state['launch_results'] = result
            
            if result['success']:
                state['step'] = 'campaign_launched'
                await db_manager.update_campaign_status(state['campaign_id'], 'active')
                logger.info(f"Campaign {state['campaign_id']} launched successfully")
            else:
                state['error'] = f"Campaign launch failed: {result['error']}"
                state['retries'] += 1
                
        except Exception as e:
            state['error'] = f"Campaign launch error: {str(e)}"
            state['retries'] += 1
        
        return state
    
    async def _monitor_performance_node(self, state: MarketingAgentState) -> MarketingAgentState:
        """Monitor campaign performance."""
        logger.info(f"Monitoring performance for campaign {state['campaign_id']}")
        
        try:
            # Get performance summary
            performance_summary = await performance_tracker.get_campaign_performance_summary(
                state['campaign_id'], hours=1
            )
            
            if performance_summary['success']:
                state['performance_data'] = performance_summary
                
                # Check if optimization is needed
                status = performance_summary.get('status', 'green')
                state['optimization_needed'] = status in ['yellow', 'red']
                
                state['step'] = 'performance_monitored'
                logger.info(f"Performance monitored for campaign {state['campaign_id']}, status: {status}")
            else:
                logger.warning(f"Performance monitoring failed for campaign {state['campaign_id']}")
                state['step'] = 'performance_monitoring_failed'
                
        except Exception as e:
            logger.error(f"Performance monitoring error for campaign {state['campaign_id']}: {e}")
            state['step'] = 'performance_monitoring_failed'
        
        return state
    
    async def _check_budgets_node(self, state: MarketingAgentState) -> MarketingAgentState:
        """Check campaign budgets."""
        logger.info(f"Checking budgets for campaign {state['campaign_id']}")
        
        try:
            # Get campaign data for budget check
            campaigns = await db_manager.get_active_campaigns()
            campaign = next((c for c in campaigns if c['id'] == state['campaign_id']), None)
            
            if campaign:
                budget_status = await budget_controller._check_campaign_budget(campaign)
                state['budget_status'] = budget_status
                
                # Handle budget alerts if needed
                if budget_status['needs_action']:
                    await budget_controller._handle_budget_alert(campaign, budget_status)
                
                state['step'] = 'budgets_checked'
                logger.info(f"Budget checked for campaign {state['campaign_id']}")
            else:
                state['step'] = 'budget_check_failed'
                
        except Exception as e:
            logger.error(f"Budget check error for campaign {state['campaign_id']}: {e}")
            state['step'] = 'budget_check_failed'
        
        return state
    
    async def _optimize_campaign_node(self, state: MarketingAgentState) -> MarketingAgentState:
        """Optimize campaign if needed."""
        logger.info(f"Optimizing campaign {state['campaign_id']}")
        
        try:
            if not state['optimization_needed']:
                state['step'] = 'optimization_skipped'
                return state
            
            # Use the optimizer agent for comprehensive optimization
            if state['performance_data']:
                optimization_result = await optimizer.optimize_campaign(
                    state['campaign_id'],
                    state['performance_data']['metrics'],
                    'Automated optimization triggered by performance monitoring'
                )
                
                if optimization_result['success']:
                    state['optimization_results'] = optimization_result
                    state['step'] = 'campaign_optimized'
                    logger.info(f"Campaign {state['campaign_id']} optimized successfully")
                else:
                    logger.warning(f"Campaign optimization failed for {state['campaign_id']}")
                    state['step'] = 'optimization_failed'
            
        except Exception as e:
            logger.error(f"Campaign optimization error for {state['campaign_id']}: {e}")
            state['step'] = 'optimization_failed'
        
        return state
    
    async def _handle_error_node(self, state: MarketingAgentState) -> MarketingAgentState:
        """Handle errors and retries."""
        logger.error(f"Handling error for campaign {state['campaign_id']}: {state.get('error', 'Unknown error')}")
        
        if state['retries'] < state['max_retries']:
            logger.info(f"Retrying operation for campaign {state['campaign_id']} (attempt {state['retries'] + 1})")
            state['error'] = None  # Clear error for retry
        else:
            logger.error(f"Max retries exceeded for campaign {state['campaign_id']}")
            await db_manager.update_campaign_status(state['campaign_id'], 'failed')
        
        state['step'] = 'error_handled'
        return state
    
    # Condition functions for routing
    def _approval_condition(self, state: MarketingAgentState) -> str:
        """Determine next step based on approval status."""
        approval_status = state.get('approval_status', 'pending')
        return approval_status
    
    def _optimization_condition(self, state: MarketingAgentState) -> str:
        """Determine if optimization loop should continue."""
        if state.get('error') and state['retries'] >= state['max_retries']:
            return "error"
        elif state.get('optimization_needed'):
            return "continue"
        else:
            return "complete"
    
    def _error_condition(self, state: MarketingAgentState) -> str:
        """Check if there's an error that needs handling."""
        if state.get('error') and state['retries'] < state['max_retries']:
            return "error"
        return "continue"


# Global orchestrator instance
marketing_orchestrator = MarketingOrchestrator() 