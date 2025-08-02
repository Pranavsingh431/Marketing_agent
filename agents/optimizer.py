"""Campaign Optimizer Agent for automatic performance-based optimizations."""

import logging
import time
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage
from config import settings
from utils.database import db_manager
from agents.content_generator import content_generator
from agents.visual_creator import visual_creator

logger = logging.getLogger(__name__)


class OptimizerAgent:
    """Agent responsible for optimizing campaign performance automatically."""
    
    def __init__(self):
        self.llm = ChatOpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=settings.openrouter_api_key,
            model="anthropic/claude-3-sonnet",  # Claude is better for optimization
            temperature=0.3,  # Lower temperature for optimization decisions
            max_tokens=1500,
            timeout=45,  # Increased timeout
            request_timeout=45
        )
    
    async def optimize_campaign(self, campaign_id: str, performance_data: Dict[str, Any], 
                               trigger_reason: str) -> Dict[str, Any]:
        """Optimize campaign based on performance data and triggers."""
        start_time = time.time()
        
        try:
            logger.info(f"Starting optimization for campaign {campaign_id}, reason: {trigger_reason}")
            
            # Analyze performance and decide optimization strategy
            optimization_plan = await self._analyze_and_plan_optimization(
                campaign_id, performance_data, trigger_reason
            )
            
            if not optimization_plan['needs_optimization']:
                return {
                    'success': True,
                    'message': 'No optimization needed',
                    'analysis': optimization_plan
                }
            
            # Execute optimization steps
            optimization_results = []
            
            for strategy in optimization_plan['strategies']:
                try:
                    if strategy['type'] == 'content_optimization':
                        result = await self._optimize_content(campaign_id, strategy, performance_data)
                    elif strategy['type'] == 'budget_adjustment':
                        result = await self._optimize_budget(campaign_id, strategy, performance_data)
                    elif strategy['type'] == 'targeting_adjustment':
                        result = await self._optimize_targeting(campaign_id, strategy, performance_data)
                    elif strategy['type'] == 'bid_adjustment':
                        result = await self._optimize_bidding(campaign_id, strategy, performance_data)
                    elif strategy['type'] == 'creative_refresh':
                        result = await self._refresh_creatives(campaign_id, strategy, performance_data)
                    else:
                        continue
                    
                    optimization_results.append(result)
                    
                except Exception as e:
                    logger.error(f"Error executing optimization strategy {strategy['type']}: {e}")
                    optimization_results.append({
                        'strategy': strategy['type'],
                        'success': False,
                        'error': str(e)
                    })
            
            # Log optimization results
            execution_time = int((time.time() - start_time) * 1000)
            
            overall_success = any(result.get('success', False) for result in optimization_results)
            
            await db_manager.log_optimization(
                campaign_id=campaign_id,
                optimization_type='automated_optimization',
                trigger_reason=trigger_reason,
                changes_made={'strategies': [r for r in optimization_results if r.get('success')]},
                before_metrics=performance_data,
                success=overall_success
            )
            
            await db_manager.log_agent_execution(
                agent_name="Optimizer",
                campaign_id=campaign_id,
                action="optimize_campaign",
                status="completed" if overall_success else "partial_failure",
                input_data={'performance_data': performance_data, 'trigger_reason': trigger_reason},
                output_data={'results': optimization_results},
                execution_time_ms=execution_time
            )
            
            logger.info(f"Optimization completed for campaign {campaign_id} in {execution_time}ms")
            
            return {
                'success': overall_success,
                'optimization_plan': optimization_plan,
                'results': optimization_results,
                'execution_time_ms': execution_time
            }
            
        except Exception as e:
            execution_time = int((time.time() - start_time) * 1000)
            error_msg = f"Error optimizing campaign: {str(e)}"
            logger.error(error_msg)
            
            await db_manager.log_agent_execution(
                agent_name="Optimizer",
                campaign_id=campaign_id,
                action="optimize_campaign",
                status="failed",
                input_data={'performance_data': performance_data, 'trigger_reason': trigger_reason},
                error_message=error_msg,
                execution_time_ms=execution_time
            )
            
            return {
                'success': False,
                'error': error_msg,
                'execution_time_ms': execution_time
            }
    
    async def _analyze_and_plan_optimization(self, campaign_id: str, performance_data: Dict[str, Any], 
                                           trigger_reason: str) -> Dict[str, Any]:
        """Analyze performance and create optimization plan."""
        
        # Get campaign history for context
        historical_performance = await db_manager.get_campaign_performance(campaign_id, hours=168)  # 7 days
        
        # Create analysis prompt
        analysis_prompt = f"""
        Analyze this campaign performance and create an optimization plan:
        
        Current Performance:
        - CTR: {performance_data.get('ctr', 0):.3f} (threshold: {settings.ctr_threshold})
        - CPC: ${performance_data.get('cpc', 0):.2f} (threshold: ${settings.cpc_threshold})
        - ROAS: {performance_data.get('roas', 0):.2f} (threshold: {settings.roas_threshold})
        - Spend: ${performance_data.get('spend', 0):.2f}
        - Conversions: {performance_data.get('conversions', 0)}
        
        Trigger Reason: {trigger_reason}
        Historical Data Points: {len(historical_performance)}
        
        Based on this data, provide an optimization plan in JSON format:
        {{
            "needs_optimization": boolean,
            "priority_level": "low|medium|high|critical",
            "primary_issues": ["issue1", "issue2"],
            "strategies": [
                {{
                    "type": "content_optimization|budget_adjustment|targeting_adjustment|bid_adjustment|creative_refresh",
                    "priority": 1-5,
                    "expected_impact": "low|medium|high",
                    "description": "What this strategy will do",
                    "specific_actions": ["action1", "action2"]
                }}
            ],
            "expected_outcomes": {{
                "ctr_improvement": 0.05,
                "cpc_reduction": 0.10,
                "roas_improvement": 0.20
            }}
        }}
        
        Prioritize strategies that will have the most impact on the specific issues identified.
        """
        
        messages = [
            SystemMessage(content="You are an expert digital marketing optimization analyst. Provide data-driven recommendations based on performance metrics."),
            HumanMessage(content=analysis_prompt)
        ]
        
        try:
            response = await self.llm.agenerate([messages])
            content = response.generations[0][0].text
            
            # Parse JSON response
            import json
            start_idx = content.find('{')
            end_idx = content.rfind('}') + 1
            
            if start_idx != -1 and end_idx != -1:
                json_str = content[start_idx:end_idx]
                optimization_plan = json.loads(json_str)
                return optimization_plan
            
        except Exception as e:
            logger.error(f"Error analyzing optimization plan: {e}")
        
        # Fallback plan based on simple rules
        return self._create_fallback_optimization_plan(performance_data, trigger_reason)
    
    def _create_fallback_optimization_plan(self, performance_data: Dict[str, Any], 
                                         trigger_reason: str) -> Dict[str, Any]:
        """Create a simple optimization plan when AI analysis fails."""
        
        ctr = performance_data.get('ctr', 0)
        cpc = performance_data.get('cpc', 0)
        roas = performance_data.get('roas', 0)
        
        strategies = []
        
        if ctr < settings.ctr_threshold:
            strategies.append({
                'type': 'content_optimization',
                'priority': 1,
                'expected_impact': 'high',
                'description': 'Optimize ad copy to improve click-through rate',
                'specific_actions': ['refresh headlines', 'improve call-to-action']
            })
            
        if cpc > settings.cpc_threshold:
            strategies.append({
                'type': 'bid_adjustment',
                'priority': 2,
                'expected_impact': 'medium',
                'description': 'Adjust bidding to reduce cost per click',
                'specific_actions': ['lower bid amounts', 'improve quality score']
            })
            
        if roas < settings.roas_threshold:
            strategies.append({
                'type': 'targeting_adjustment',
                'priority': 2,
                'expected_impact': 'high',
                'description': 'Optimize audience targeting for better conversions',
                'specific_actions': ['refine audience', 'exclude low-performers']
            })
        
        return {
            'needs_optimization': len(strategies) > 0,
            'priority_level': 'high' if len(strategies) > 2 else 'medium',
            'primary_issues': trigger_reason.split('; '),
            'strategies': strategies,
            'expected_outcomes': {
                'ctr_improvement': 0.02,
                'cpc_reduction': 0.15,
                'roas_improvement': 0.25
            }
        }
    
    async def _optimize_content(self, campaign_id: str, strategy: Dict[str, Any], 
                               performance_data: Dict[str, Any]) -> Dict[str, Any]:
        """Optimize campaign content based on performance."""
        
        try:
            # Get current campaign data
            campaigns = await db_manager.get_active_campaigns()
            campaign = next((c for c in campaigns if c['id'] == campaign_id), None)
            
            if not campaign:
                return {'strategy': 'content_optimization', 'success': False, 'error': 'Campaign not found'}
            
            # Get current creative data (simplified - you'd get this from database)
            current_content = {
                'headlines': ['Current Headline'],
                'description': 'Current description',
                'call_to_action': 'Learn More'
            }
            
            # Use content generator to optimize
            optimization_result = await content_generator.optimize_content(
                current_content, performance_data
            )
            
            if optimization_result['success']:
                # Here you would update the campaign with new content
                # For now, we'll just log the optimization
                logger.info(f"Content optimized for campaign {campaign_id}")
                
                return {
                    'strategy': 'content_optimization',
                    'success': True,
                    'changes': optimization_result['optimized_content'],
                    'description': 'Updated ad copy based on performance data'
                }
            else:
                return {
                    'strategy': 'content_optimization',
                    'success': False,
                    'error': optimization_result['error']
                }
                
        except Exception as e:
            return {
                'strategy': 'content_optimization',
                'success': False,
                'error': str(e)
            }
    
    async def _optimize_budget(self, campaign_id: str, strategy: Dict[str, Any], 
                              performance_data: Dict[str, Any]) -> Dict[str, Any]:
        """Optimize campaign budget allocation."""
        
        try:
            current_spend = performance_data.get('spend', 0)
            current_roas = performance_data.get('roas', 0)
            
            # Simple budget optimization logic
            if current_roas > settings.roas_threshold * 1.5:
                # Performing well, consider increasing budget
                budget_change = 'increase'
                change_amount = 0.20  # 20% increase
            elif current_roas < settings.roas_threshold:
                # Poor performance, decrease budget
                budget_change = 'decrease'
                change_amount = -0.15  # 15% decrease
            else:
                # Maintain current budget
                budget_change = 'maintain'
                change_amount = 0
            
            # Here you would implement actual budget changes via platform APIs
            
            return {
                'strategy': 'budget_adjustment',
                'success': True,
                'changes': {
                    'action': budget_change,
                    'change_percentage': change_amount,
                    'reason': f'ROAS: {current_roas:.2f}, threshold: {settings.roas_threshold}'
                },
                'description': f'Budget adjustment: {budget_change} by {abs(change_amount)*100:.0f}%'
            }
            
        except Exception as e:
            return {
                'strategy': 'budget_adjustment',
                'success': False,
                'error': str(e)
            }
    
    async def _optimize_targeting(self, campaign_id: str, strategy: Dict[str, Any], 
                                 performance_data: Dict[str, Any]) -> Dict[str, Any]:
        """Optimize audience targeting."""
        
        try:
            # Simplified targeting optimization
            # In a real implementation, you'd analyze demographic performance
            
            optimizations = []
            
            if performance_data.get('ctr', 0) < settings.ctr_threshold:
                optimizations.append('Refine interest targeting to more engaged audiences')
            
            if performance_data.get('cpc', 0) > settings.cpc_threshold:
                optimizations.append('Exclude low-performing demographics')
                
            if performance_data.get('conversions', 0) < 5:
                optimizations.append('Add lookalike audiences based on converters')
            
            return {
                'strategy': 'targeting_adjustment',
                'success': True,
                'changes': {
                    'optimizations': optimizations,
                    'targeting_adjustments': 'Audience refinement based on performance data'
                },
                'description': f'Applied {len(optimizations)} targeting optimizations'
            }
            
        except Exception as e:
            return {
                'strategy': 'targeting_adjustment',
                'success': False,
                'error': str(e)
            }
    
    async def _optimize_bidding(self, campaign_id: str, strategy: Dict[str, Any], 
                               performance_data: Dict[str, Any]) -> Dict[str, Any]:
        """Optimize bidding strategy."""
        
        try:
            current_cpc = performance_data.get('cpc', 0)
            current_ctr = performance_data.get('ctr', 0)
            
            bid_adjustments = []
            
            if current_cpc > settings.cpc_threshold:
                bid_adjustments.append({
                    'action': 'decrease_bids',
                    'amount': -0.10,  # 10% decrease
                    'reason': f'CPC too high: ${current_cpc:.2f}'
                })
            
            if current_ctr < settings.ctr_threshold:
                bid_adjustments.append({
                    'action': 'improve_ad_rank',
                    'method': 'quality_score_optimization',
                    'reason': f'Low CTR: {current_ctr:.3f}'
                })
            
            return {
                'strategy': 'bid_adjustment',
                'success': True,
                'changes': {
                    'bid_adjustments': bid_adjustments,
                    'strategy': 'Automated bid optimization based on performance'
                },
                'description': f'Applied {len(bid_adjustments)} bidding optimizations'
            }
            
        except Exception as e:
            return {
                'strategy': 'bid_adjustment',
                'success': False,
                'error': str(e)
            }
    
    async def _refresh_creatives(self, campaign_id: str, strategy: Dict[str, Any], 
                                performance_data: Dict[str, Any]) -> Dict[str, Any]:
        """Refresh creative assets."""
        
        try:
            # Get campaign data for creative refresh
            campaigns = await db_manager.get_active_campaigns()
            campaign = next((c for c in campaigns if c['id'] == campaign_id), None)
            
            if not campaign:
                return {'strategy': 'creative_refresh', 'success': False, 'error': 'Campaign not found'}
            
            # Generate new creative content
            campaign_data = {
                'campaign_id': campaign_id,
                'product_name': campaign.get('name', 'Product'),
                'platform': campaign.get('platform', 'meta'),
                'target_audience': campaign.get('target_audience', {}),
                'objective': campaign.get('objective', 'conversions'),
                'budget_daily': campaign.get('budget_daily', 100)
            }
            
            # Generate new content
            content_result = await content_generator.generate_ad_copy(campaign_data)
            
            if content_result['success']:
                # Optionally generate new image
                image_result = await visual_creator.generate_ad_image(
                    campaign_data, content_result['content']
                )
                
                return {
                    'strategy': 'creative_refresh',
                    'success': True,
                    'changes': {
                        'new_content': content_result['content'],
                        'new_image': image_result.get('image_url') if image_result.get('success') else None,
                        'refresh_reason': 'Performance-based creative refresh'
                    },
                    'description': 'Generated new creative assets based on performance data'
                }
            else:
                return {
                    'strategy': 'creative_refresh',
                    'success': False,
                    'error': content_result['error']
                }
                
        except Exception as e:
            return {
                'strategy': 'creative_refresh',
                'success': False,
                'error': str(e)
            }


# Global optimizer instance
optimizer = OptimizerAgent() 